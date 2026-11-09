"""approvals.py on a stand-in Paperclip and a throwaway submissions folder. Touches neither Paperclip nor the dashboard.
usage: python test_approvals.py
"""
import json
import tempfile
from pathlib import Path

import approvals


class Paperclip:
    """Issues, uploads and review cards as plain dicts. fail_on names methods that answer like Paperclip on an error."""

    def __init__(self, fail_on=()):
        self.ids = {"imported": {"trello1": "i-card"}}
        self.issues = {"i-card": {"id": "i-card", "status": "todo"}}
        self.uploads, self.cards, self.updates, self.fail_on = [], {}, [], set(fail_on)

    def _fail(self, name):
        if name in self.fail_on:
            raise RuntimeError(f"Paperclip answered HTTP 500 on {name}")

    def issue(self, issue_id):
        self._fail("issue")
        if issue_id not in self.issues:
            raise RuntimeError("Paperclip answered HTTP 404")
        return self.issues[issue_id]

    def new_review(self, title, parent):
        self._fail("new_review")
        n = len(self.issues)
        r = {"id": f"r{n}", "identifier": f"BOT-{100 + n}", "title": title, "parentId": parent, "status": "todo"}
        self.issues[r["id"]] = r
        return r

    def upload(self, issue_id, path):
        self._fail("upload")
        self.uploads.append((issue_id, Path(path).name))
        aid = f"a{len(self.uploads)}"
        return {"id": aid, "contentPath": f"/api/attachments/{aid}/content"}

    def post_verdicts(self, issue_id, payload):
        self._fail("post_verdicts")
        cid = f"c{len(self.cards) + 1}"
        self.cards[cid] = {"id": cid, "issue": issue_id, "kind": "request_item_verdicts", "status": "pending",
                           "payload": payload, "result": None}
        return self.cards[cid]

    def verdict_card(self, issue_id, card_id):
        self._fail("verdict_card")
        if card_id in getattr(self, "fail_cards", ()):
            raise RuntimeError("Paperclip answered HTTP 500 on that card")
        return self.cards.get(card_id)

    def update(self, issue_id, body):
        self.updates.append((issue_id, body))
        if "status" in body:
            self.issues[issue_id]["status"] = body["status"]


def make(root, kind_dir, folder, manifest, previews=(), decision=None, review=None):
    """One submission folder. previews: (file name, size in bytes)."""
    d = root / kind_dir / folder
    d.mkdir(parents=True)
    for name, size in previews:
        (d / name).write_bytes(b"x" * size)
    (d / "manifest.json").write_text(json.dumps({**manifest, "previews": [n for n, _ in previews]}), encoding="utf-8")
    if decision:
        (d / "decision.json").write_text(json.dumps(decision), encoding="utf-8")
    if review:
        (d / "review.json").write_text(json.dumps(review), encoding="utf-8")
    return d


NOW = 1_793_000_000.0   # 2026-10-26; Windows can't turn a time near 1970 into a local date
CLAUDE = {"kind": "background", "agent": "Claude (throwaway test)", "name": "Drift test"}


def as_sub(sid, manifest, folder=Path(".")):
    return {"id": sid, "folder": folder, "manifest": manifest}


def test_waiting():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        make(root, "backgrounds", "decided", CLAUDE, decision={"decision": "approve"})
        make(root, "backgrounds", "posted", CLAUDE, review={"issue": "r1"})
        bare = make(root, "backgrounds", "test_method1", CLAUDE)
        found = approvals.waiting(root)
        assert [s["id"] for s in found] == ["backgrounds/test_method1"], found
        assert found[0]["folder"] == bare and found[0]["manifest"]["name"] == "Drift test"
    print("Only submissions with no decision and no review card are waiting")


def test_group_titles():
    three = [as_sub(f"backgrounds/t{k}", CLAUDE) for k in range(3)]
    assert [g["title"] for g in approvals.group(three)] == ["[You] Approve: 3 backgrounds from Claude"]
    one = [as_sub("characters/player13", {"kind": "character", "agent": "Character Artist", "card": "i-card"})]
    g = approvals.group(one)[0]
    assert g["title"] == "[You] Approve: 1 character from the Character Artist" and g["card"] == "i-card", g
    ideas = [as_sub(f"background_ideas/idea_{k:03}", {"kind": "background idea", "agent": "Level Architect (researched list)"})
             for k in range(250)]
    chunks = approvals.group(ideas)
    assert [len(c["subs"]) for c in chunks] == [200, 50], [len(c["subs"]) for c in chunks]
    assert chunks[0]["title"] == "[You] Approve: 200 background ideas from the Level Architect", chunks[0]["title"]
    print("One review card per maker, kind and card, titled by count, at most 200 to a card")


def test_item():
    idea = as_sub("background_ideas/idea_007", {"kind": "background idea", "agent": "Level Architect (researched list)",
                                                "name": "Moonlit pier, gouache. Why: sells the mood"})
    it = approvals.item(idea, [{"id": "a1", "contentPath": "/api/attachments/a1/content"}, "drift.gif"])
    assert it["id"] == "background_ideas/idea_007" and it["label"] == "Moonlit pier, gouache", it
    assert it["description"] == "background idea from the Level Architect", it
    md = it["previewMarkdown"]
    assert md.startswith("Why: sells the mood"), md
    assert "![preview](/api/attachments/a1/content)" in md and "Preview too big to show here: drift.gif" in md, md
    long = approvals.item(as_sub("characters/x", {"kind": "character", "agent": "Character Artist", "name": "Z" * 300}), [])
    assert long["label"] == "Z" * 120, len(long["label"])
    print("Each item shows the name, who made it, the rest of the name, and every preview")


def test_roast_line_item():
    text = "Dead. Even the water looked away out of respect."
    sub = as_sub("roast_lines/rw_drowned_001", {"kind": "roast line", "agent": "Roast Writer", "name": text, "label": text,
                                                "description": "Lifeguard Off Duty, on a loss"})
    it = approvals.item(sub, [])
    assert it["label"] == text and it["description"] == "Lifeguard Off Duty, on a loss" and "previewMarkdown" not in it, it
    g = approvals.group([sub, as_sub("roast_lines/rw_drowned_002", sub["manifest"])])[0]
    assert g["title"] == "[You] Approve: 2 roast lines from the Roast Writer", g["title"]
    print("A roast line shows whole, with its event and outcome, on a card titled in roast lines")
    hats = [as_sub(f"wardrobe/item{k}", {"kind": "wardrobe item", "agent": "Wardrobe Stylist", "name": "Top Hat",
                                         "description": "Hat, 2 color areas"}) for k in range(5)]
    assert approvals.group(hats)[0]["title"] == "[You] Approve: 5 wardrobe items from the Wardrobe Stylist"
    assert approvals.item(hats[0], [])["description"] == "Hat, 2 color areas"
    ideas = [as_sub(f"wardrobe_ideas/idea_{k:02}", {"kind": "wardrobe idea", "agent": "Claude (researched list)"}) for k in range(40)]
    assert approvals.group(ideas)[0]["title"] == "[You] Approve: 40 wardrobe ideas from Claude"
    print("Wardrobe items and ideas are titled in their own plurals")


def test_post():
    approvals._failed.clear()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for k in (1, 2):
            make(root, "backgrounds", f"test_method{k}", {**CLAUDE, "card": "trello1"}, previews=[("drift.gif", 50)])
        board = Paperclip()
        assert approvals.post(board, root, now=NOW, say=lambda *_: None) == 2
        review = [i for i in board.issues.values() if i["id"] != "i-card"]
        assert len(review) == 1 and review[0]["parentId"] == "i-card", review
        assert review[0]["title"] == "[You] Approve: 2 backgrounds from Claude", review[0]["title"]
        assert board.uploads == [(review[0]["id"], "drift.gif")] * 2, board.uploads
        payload = board.cards["c1"]["payload"]
        assert payload["prompt"] == "Approve or reject each one. A reject needs a note, and the note goes to Claude.", payload
        assert payload["reasonLabel"] == "Your note (goes to the agent)" and payload["version"] == 1, payload
        assert payload["items"][0]["id"] == "backgrounds/test_method1", payload["items"]
        for k in (1, 2):
            r = json.loads((root / "backgrounds" / f"test_method{k}" / "review.json").read_text(encoding="utf-8"))
            assert r["issue"] == review[0]["id"] and r["identifier"] == review[0]["identifier"] and r["interaction"] == "c1", r
        assert approvals.waiting(root) == [], "posted submissions aren't waiting any more"
    print("New submissions go up as one review card under the maker's card, and each folder notes where")


def test_post_files_it_cannot_show():
    approvals._failed.clear()
    keep = approvals.MAX_UPLOAD
    approvals.MAX_UPLOAD = 10
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make(root, "backgrounds", "big", CLAUDE, previews=[("drift.gif", 50), ("notes.txt", 5)])
            board = Paperclip()
            assert approvals.post(board, root, now=NOW, say=lambda *_: None) == 1
            assert board.uploads == [], board.uploads
            md = board.cards["c1"]["payload"]["items"][0]["previewMarkdown"]
            assert "Preview too big to show here: drift.gif" in md and "notes.txt" in md, md
    finally:
        approvals.MAX_UPLOAD = keep
    print("A preview too big for Paperclip, or not a picture, is named instead and the item still goes up")


def test_post_failure_waits():
    approvals._failed.clear()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        folder = make(root, "backgrounds", "test_method1", CLAUDE, previews=[("drift.gif", 50)])
        board = Paperclip(fail_on={"post_verdicts"})
        said = []
        assert approvals.post(board, root, now=NOW, say=said.append) == 0
        assert not (folder / "review.json").exists()
        made = [i for i in board.issues.values() if i["id"] != "i-card"]
        assert len(made) == 1 and made[0]["status"] == "cancelled", made
        assert said and "post_verdicts" in said[0], said
        assert approvals.post(board, root, now=NOW + 60, say=said.append) == 0
        assert len(board.issues) == 2, "no second try inside 15 minutes"
        board.fail_on.clear()
        assert approvals.post(board, root, now=NOW + approvals.RETRY_AFTER + 1, say=said.append) == 1
        assert (folder / "review.json").exists()
    print("A post that fails halfway is cancelled, nothing is marked posted, and it tries again after 15 minutes")


def test_post_file_error_waits():
    approvals._failed.clear()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        make(root, "backgrounds", "test_method1", CLAUDE, previews=[("drift.gif", 50)])
        board = Paperclip()

        def locked(issue_id, path):
            raise PermissionError(13, "The process cannot access the file", str(path))
        board.upload = locked
        assert approvals.post(board, root, now=NOW, **QUIET) == 0
        assert approvals.post(board, root, now=NOW + 60, **QUIET) == 0
        made = [i for i in board.issues.values() if i["id"] != "i-card"]
        assert len(made) == 1 and made[0]["status"] == "cancelled", made
    print("A file error halfway through is handled the same way, so the board doesn't fill with copies")


AT = "2026-11-04T20:15:45.738Z"
QUIET = {"say": lambda *_: None}


def posted(root, board, names=("test_method1", "test_method2"), agent="Claude (throwaway test)"):
    """Submissions already on one review card. Returns that card."""
    for n in names:
        make(root, "backgrounds", n, {**CLAUDE, "agent": agent}, previews=[("drift.gif", 50)])
    approvals._failed.clear()
    approvals.post(board, root, now=NOW, **QUIET)
    return board.cards[f"c{len(board.cards)}"]


def verdict(name, decision, reason=None):
    v = {"id": f"backgrounds/{name}", "verdict": decision, "resolvedAt": AT}
    return {**v, "reason": reason} if reason else v


def decision_of(root, name):
    p = root / "backgrounds" / name / "decision.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def test_collect_complete():
    with tempfile.TemporaryDirectory() as tmp:
        root, board = Path(tmp), Paperclip()
        card = posted(root, board)
        card.update(status="answered", result={"outcome": "resolved", "complete": True, "items": [
            verdict("test_method1", "approve"), verdict("test_method2", "reject", "too dark")]})
        assert approvals.collect(board, root, now=NOW + 120, **QUIET) == 2
        one, two = decision_of(root, "test_method1"), decision_of(root, "test_method2")
        assert sorted(one) == ["at", "decision", "id", "note", "written_at"], one
        assert one["id"] == "backgrounds/test_method1" and one["decision"] == "approve" and one["note"] == "" and one["at"] == AT, one
        assert two["decision"] == "reject" and two["note"] == "too dark", two
        assert board.updates[-1] == (card["issue"], {"status": "done", "comment": "All 2 decided: 1 approved, 1 rejected."}), board.updates
        assert approvals.collect(board, root, now=NOW + 180, **QUIET) == 0 and len(board.updates) == 1, "a closed card is left alone"
    print("Each call becomes decision.json with David's note, and a fully decided card is closed")


def test_collect_partial():
    with tempfile.TemporaryDirectory() as tmp:
        root, board = Path(tmp), Paperclip()
        card = posted(root, board)
        card.update(result={"outcome": "resolved", "complete": False, "items": [verdict("test_method1", "approve")]})
        assert approvals.collect(board, root, now=NOW + 120, **QUIET) == 1
        assert decision_of(root, "test_method1")["decision"] == "approve" and decision_of(root, "test_method2") is None
        assert board.updates == [], "the card stays open until the rest are decided"
    print("Items David applied are passed on; the card stays open for the ones he skipped")


def test_collect_keeps_existing():
    with tempfile.TemporaryDirectory() as tmp:
        root, board = Path(tmp), Paperclip()
        card = posted(root, board)
        kept = root / "backgrounds" / "test_method2" / "decision.json"
        kept.write_text('{"decision": "approve"}', encoding="utf-8")
        card.update(status="answered", result={"outcome": "resolved", "complete": True, "items": [
            verdict("test_method1", "approve"), verdict("test_method2", "reject", "too dark")]})
        assert approvals.collect(board, root, now=NOW + 120, **QUIET) == 1
        assert kept.read_text(encoding="utf-8") == '{"decision": "approve"}'
    print("A decision.json that's already there is never overwritten")


def test_collect_cancelled():
    with tempfile.TemporaryDirectory() as tmp:
        root, board = Path(tmp), Paperclip()
        card = posted(root, board)
        board.issues[card["issue"]]["status"] = "cancelled"
        card.update(result={"outcome": "resolved", "complete": False, "items": [verdict("test_method1", "approve")]})
        assert approvals.collect(board, root, now=NOW + 120, **QUIET) == 1
        assert decision_of(root, "test_method1")["decision"] == "approve"
        assert [s["id"] for s in approvals.waiting(root)] == ["backgrounds/test_method2"], approvals.waiting(root)
    with tempfile.TemporaryDirectory() as tmp:
        root, board = Path(tmp), Paperclip()
        card = posted(root, board)
        card["status"] = "expired"
        assert approvals.collect(board, root, now=NOW + 120, **QUIET) == 0
        assert len(approvals.waiting(root)) == 2, "an expired card's items go up again"
        assert board.issues[card["issue"]]["status"] == "cancelled", "and its old issue leaves David's inbox"
    print("A cancelled review issue or an expired card puts its undecided items back up")


def test_collect_unreadable_card():
    with tempfile.TemporaryDirectory() as tmp:
        root, board = Path(tmp), Paperclip()
        bad = posted(root, board, names=("a1",), agent="Claude")
        good = posted(root, board, names=("b1",), agent="Level Architect")
        board.fail_cards = {bad["id"]}
        good.update(status="answered", result={"outcome": "resolved", "complete": True, "items": [verdict("b1", "approve")]})
        assert approvals.collect(board, root, now=NOW + 120, **QUIET) == 1
        assert decision_of(root, "b1")["decision"] == "approve" and (root / "backgrounds" / "a1" / "review.json").exists()
    print("One card Paperclip can't read doesn't stop the others")


def test_sync():
    with tempfile.TemporaryDirectory() as tmp:
        root, board = Path(tmp), Paperclip()
        card = posted(root, board, names=("test_method1",))
        card.update(status="answered", result={"outcome": "resolved", "complete": True, "items": [verdict("test_method1", "approve")]})
        make(root, "backgrounds", "fresh", CLAUDE)
        assert approvals.sync(board, root, now=NOW + 120, **QUIET) == 1
        assert decision_of(root, "test_method1")["decision"] == "approve" and (root / "backgrounds" / "fresh" / "review.json").exists()
    print("One pass passes on David's calls, then posts what's new")


def main():
    test_waiting()
    test_group_titles()
    test_item()
    test_roast_line_item()
    test_post()
    test_post_files_it_cannot_show()
    test_post_failure_waits()
    test_post_file_error_waits()
    test_collect_complete()
    test_collect_partial()
    test_collect_keeps_existing()
    test_collect_cancelled()
    test_collect_unreadable_card()
    test_sync()
    print("all passed")


if __name__ == "__main__":
    main()
