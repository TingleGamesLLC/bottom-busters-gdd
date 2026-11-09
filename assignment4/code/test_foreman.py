"""The Foreman's rules on a stand-in board and stand-in runs and submissions. Touches neither Paperclip nor the dashboard,
and spends nothing.
usage: python test_foreman.py
"""
import json
import tempfile
from pathlib import Path

import common
import foreman
import paperclip_board as pb

AGENTS = {"character-artist": "a-artist", "critic": "a-critic", "builder": "a-builder", "level-architect": "a-level",
          "roast-writer": "a-roast", "wardrobe-stylist": "a-ward"}


class Board:
    """Issues as plain dicts: id, title, status, parentId, assigneeAgentId, assigneeUserId, blockedBy."""

    def __init__(self, issues):
        self.ids = {"agents": AGENTS}
        self.rows = {r["id"]: r for r in issues}
        self.comments, self.asked = [], []
        self.answers = {}   # question issue id: David's answer on its question card

    def answered_questions(self):
        return [(self.rows[q], text) for q, text in self.answers.items() if self.rows[q]["status"] == "todo"]

    def _list(self, r):
        if r["status"] == "in_review":
            return pb.PLAYTEST if r.get("assigneeUserId") == "david" else pb.REVIEW
        return {"todo": pb.BACKLOG, "in_progress": pb.LEASED, "done": pb.DONE}.get(r["status"])

    def cards(self, list_name):
        agent = {v: k for k, v in AGENTS.items()}
        return [{"id": r["id"], "name": r["title"], "list": list_name, "trello_id": None, "agent": agent.get(r.get("assigneeAgentId"))}
                for r in self.rows.values() if not r.get("parentId") and self._list(r) == list_name]

    def move(self, card, list_name):
        r = self.rows[card["id"]]
        r["status"] = pb.STATUS[list_name]
        r["assigneeUserId"] = "david" if list_name == pb.PLAYTEST else None

    def comment(self, card, text):
        self.comments.append((card["id"], text))
        if self.rows[card["id"]]["status"] == "done":
            self.rows[card["id"]]["status"] = "todo"   # Paperclip reopens a finished issue on any comment

    def archive(self, card):
        pass

    def issues(self, status):
        return [r for r in self.rows.values() if r["status"] == status]

    def issue(self, issue_id):
        return self.rows[issue_id]

    def update(self, issue_id, body):
        self.rows[issue_id]["status"] = body.get("status", self.rows[issue_id]["status"])
        if body.get("comment"):
            self.comments.append((issue_id, body["comment"]))

    def ask_david(self, title, text, parent=None):
        self.asked.append(title)
        new_id = f"ask-{len(self.asked)}"
        self.rows[new_id] = {"id": new_id, "title": title, "status": "todo", "parentId": parent, "assigneeUserId": "david"}
        return new_id

    def new_card(self, title, text, agent):
        new_id = f"new-{len(self.rows)}"
        self.rows[new_id] = {"id": new_id, "title": title, "description": text, "status": "todo", "assigneeAgentId": AGENTS[agent]}
        return new_id


def run_folder(name, status, crash=None):
    d = common.RUNS / name
    d.mkdir(parents=True)
    (d / "run.json").write_text(json.dumps({"status": status, "card": "[Character Artist] card"}), encoding="utf-8")
    if crash:
        (d / "crash.txt").write_text(crash, encoding="utf-8")


def submission(name, card, decision=None, note=""):
    d = common.SUBMISSIONS / "characters" / name
    d.mkdir(parents=True)
    (d / "manifest.json").write_text(json.dumps({"card": card, "name": f"{name.title()} (player)"}), encoding="utf-8")
    if decision:
        (d / "decision.json").write_text(json.dumps({"decision": decision, "note": note}), encoding="utf-8")


def check(board, state, running=False):
    c = foreman.Check(board, state, running)
    for step in (c.stalled_cards, c.orphan_tasks, c.failed_runs, c.false_blockers):
        step()
    return c


foreman_real_preflight = dict(foreman.PREFLIGHT)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        common.RUNS, common.SUBMISSIONS = tmp / "runs", tmp / "submissions"
        (common.SUBMISSIONS / "characters").mkdir(parents=True)
        run_folder("old-stop", "stopped: from before the Foreman")

        def fresh():
            return Board([
                {"id": "leased", "title": "[Character Artist] left leased", "status": "in_progress", "assigneeAgentId": "a-artist"},
                {"id": "builder", "title": "[Builder] in review with Claude", "status": "in_review", "assigneeAgentId": "a-builder"},
                {"id": "task", "title": "t1", "status": "in_progress", "parentId": "leased", "assigneeAgentId": "a-artist"},
                {"id": "mine", "title": "David's own subtask", "status": "in_progress", "parentId": "builder", "assigneeUserId": "david"},
                {"id": "freed", "title": "blocked by finished work", "status": "blocked", "blockedBy": [{"status": "done"}]},
                {"id": "steam", "title": "[Waiting] Steam App ID", "status": "blocked", "blockedBy": []},
                {"id": "approved", "title": "[Character Artist] all approved", "status": "in_review", "assigneeUserId": "david"},
                {"id": "rejected", "title": "[Character Artist] one rejected", "status": "in_review", "assigneeUserId": "david"},
                {"id": "waiting", "title": "[Character Artist] still deciding", "status": "in_review", "assigneeUserId": "david"},
                {"id": "sent-back", "title": "[Character Artist] one rejected with a note", "status": "in_review", "assigneeUserId": "david"},
                {"id": "roasts", "title": "[Roast Writer] 250 new roast lines", "status": "in_review", "assigneeUserId": "david"},
                {"id": "wardrobe", "title": "[Wardrobe Stylist] 40 new hats and shades", "status": "todo", "assigneeAgentId": "a-ward"},
            ])
        submission("darnell", "approved", "approve")
        submission("marvin", "approved", "approve", "death splat needs to be frowning")
        submission("puffball", "rejected", "reject")
        submission("fuzzball", "waiting")
        submission("gary", "sent-back", "approve")
        submission("hank", "sent-back", "reject", "hair floats off his head")
        roast = common.SUBMISSIONS / "roast_lines" / "rw_drowned_001"
        roast.mkdir(parents=True)
        (roast / "manifest.json").write_text(json.dumps({"kind": "roast line", "agent": "Roast Writer", "card": "roasts", "name": "Dead. Wet."}), encoding="utf-8")
        (roast / "decision.json").write_text(json.dumps({"decision": "reject", "note": "flat"}), encoding="utf-8")

        # A crew run is alive: nothing it might still be using gets touched.
        board, state = fresh(), {}
        check(board, state, running=True)
        assert board.rows["leased"]["status"] == "in_progress" and board.rows["task"]["status"] == "in_progress", board.rows
        print("While a crew run is alive, its card and tasks are left alone")

        hat = common.SUBMISSIONS / "wardrobe" / "top_hat"
        hat.mkdir(parents=True)
        (hat / "manifest.json").write_text(json.dumps({"kind": "wardrobe item", "agent": "Wardrobe Stylist", "card": "wardrobe",
                                                       "card_name": "[Wardrobe Stylist] 40 new hats and shades", "name": "Top Hat",
                                                       "idea": "idea_01"}), encoding="utf-8")
        (hat / "decision.json").write_text(json.dumps({"decision": "reject", "note": "brim too thin"}), encoding="utf-8")
        board, state = fresh(), {}
        c = check(board, state)
        assert board.rows["leased"]["status"] == "todo" and any(i == "leased" and "back in the queue" in t for i, t in board.comments)
        assert board.rows["builder"]["status"] == "in_review"
        print("A crew card left in progress with no run alive goes back to the queue; a Builder card is left alone")
        assert board.rows["task"]["status"] == "cancelled" and board.rows["mine"]["status"] == "in_progress"
        print("A crew task left open is closed as cancelled; David's own subtask is left alone")
        assert board.rows["freed"]["status"] == "todo" and board.rows["steam"]["status"] == "blocked"
        print("Blocked by finished work goes back to todo; an outside wait stays blocked")
        assert board.rows["approved"]["status"] == "done" and board.rows["rejected"]["status"] == "in_review"
        assert board.rows["waiting"]["status"] == "in_review"
        print("All approved closes; a rejection or an undecided one keeps the card waiting")
        assert "[Foreman] Your note on Marvin (player) needs a task" in board.asked, board.asked
        assert "[Foreman] You rejected Puffball (player) with no note" in board.asked, board.asked
        redo = [r for r in board.rows.values() if r["title"].startswith("[Character Artist] Redo Hank")]
        assert len(redo) == 1 and redo[0]["assigneeAgentId"] == "a-artist" and "David's note: hair floats off his head" in redo[0]["description"], redo
        hank = json.loads((common.SUBMISSIONS / "characters" / "hank" / "manifest.json").read_text(encoding="utf-8"))
        assert hank["redone_by"] == redo[0]["id"] and board.rows["sent-back"]["status"] == "done", (hank, board.rows["sent-back"])
        assert not any("Hank" in a for a in board.asked), board.asked
        print("A rejection with a note goes back to the maker as a redo card, and its old card closes")
        assert not any("Redo Dead" in r["title"] for r in board.rows.values()), [r["title"] for r in board.rows.values()]
        assert "redone_by" not in json.loads((roast / "manifest.json").read_text(encoding="utf-8"))
        assert not any("Dead" in a for a in board.asked), board.asked
        print("A rejected roast line never becomes a redo card; its note goes to the Roast Writer's next batch")
        redo = [r for r in board.rows.values() if r["title"].startswith("[Wardrobe Stylist] Redo Top Hat")]
        assert len(redo) == 1 and redo[0]["assigneeAgentId"] == "a-ward", [r["title"] for r in board.rows.values()]
        assert "David rejected Top Hat (top_hat) from [Wardrobe Stylist] 40 new hats and shades" in redo[0]["description"]
        assert "David's note: brim too thin" in redo[0]["description"] and board.rows["wardrobe"]["status"] == "todo"
        assert json.loads((hat / "manifest.json").read_text(encoding="utf-8"))["redone_by"] == redo[0]["id"]
        print("A wardrobe item rejected with a note becomes a redo card while its card waits in the queue")
        assert not any("Darnell" in a or "Fuzzball" in a for a in board.asked), board.asked
        print("David's note and his no-note rejection are raised with him")
        assert not any("old-stop" in a for a in board.asked) and "old-stop" in state["seen_runs"]
        print("Runs from before the Foreman started aren't reported")

        run_folder("new-stop", "stopped: character-artist lost both cheeks on t1: no eyes")
        run_folder("new-crash", "crashed", crash="Traceback...\nKeyError: 'skin'")
        run_folder("dead", "running")
        run_folder("fine", "waiting on David")
        before = len(board.asked)
        check(board, state)
        new = board.asked[before:]
        assert any("new-stop stopped: character-artist lost both cheeks" in a for a in new), new
        assert any("new-crash crashed: KeyError: 'skin'" in a for a in new), new
        assert any("dead ended without finishing" in a for a in new), new
        assert not any("fine" in a for a in new) and len(new) == 3, new
        print("A stopped run, a crash and a run that died are each raised with the reason; a finished run isn't")

        before = len(board.asked)
        check(board, state)
        assert len(board.asked) == before, board.asked[before:]
        print("Nothing is raised twice")

        # X3: David answers a question card in Paperclip.
        asked_puffball = state["escalated"]["reject:puffball"]
        board.answers = {asked_puffball: "make the poof smaller"}
        foreman.Check(board, state, False).answered_questions()
        redo = [r for r in board.rows.values() if r["title"].startswith("[Character Artist] Redo Puffball")]
        assert len(redo) == 1 and "David's note: make the poof smaller" in redo[0]["description"], redo
        assert board.rows[asked_puffball]["status"] == "done"
        assert any(i == "rejected" and "make the poof smaller" in t for i, t in board.comments), board.comments
        print("An answer to a no-note rejection becomes the note: the work goes back to the maker, and the question closes")
        asked_marvin = state["escalated"]["note:marvin"]
        board.answers = {asked_marvin: "Done, I've handled it"}
        foreman.Check(board, state, False).answered_questions()
        assert board.rows[asked_marvin]["status"] == "done" and any(i == asked_marvin and "handled it" in t for i, t in board.comments)
        assert board.rows["approved"]["status"] == "done" and not any(i == "approved" and "handled it" in t for i, t in board.comments)
        foreman.Check(board, state, False).answered_questions()
        assert len([r for r in board.rows.values() if r["title"].startswith("[Character Artist] Redo Puffball")]) == 1
        print("Any other answer is kept on the question, goes on its card unless that's finished (a comment would reopen it), "
              "and the question closes, once")

        # Pre-flight, on stand-in checks: raised once while it lasts, closed when it clears, raised again if it comes back.
        down = {"pixellab": "PixelLab has 2 generations left"}
        foreman.PREFLIGHT = {name: (lambda name=name: down.get(name)) for name in ("mindrouter", "node-a", "pixellab", "bbust")}
        board, state = fresh(), {}
        c = foreman.Check(board, state, False)
        c.preflight()
        c.preflight()
        assert board.asked == ["[Foreman] PixelLab has 2 generations left"], board.asked
        down.clear()
        c.preflight()
        assert not state["preflight"] and ("ask-1", "Foreman: this cleared on its own check.") in board.comments, (state, board.comments)
        down["pixellab"] = "PixelLab has 0 generations left"
        c.preflight()
        assert len(board.asked) == 2, board.asked
        print("A pre-flight problem is raised once, closed when it clears, and raised again if it comes back")
        state["preflight"]["comfyui"] = "ask-old"
        board.rows["ask-old"] = {"status": "todo"}
        c.preflight()
        assert "comfyui" not in state["preflight"] and ("ask-old", "Foreman: this check isn't needed any more.") in board.comments
        print("An open issue for a check that was taken out is closed on the next pass")

        assert "comfyui" not in foreman_real_preflight
        print("The pre-flight never raises ComfyUI: the Level Architect starts it when it's needed")

        import backup_paperclip
        real_behind = backup_paperclip.behind
        try:
            backup_paperclip.behind = lambda: "Paperclip's backups haven't reached the NAS since never"
            assert "NAS" in foreman_real_preflight["nas-backup"]()
            backup_paperclip.behind = lambda: None
            assert foreman_real_preflight["nas-backup"]() is None
        finally:
            backup_paperclip.behind = real_behind
        print("The pre-flight raises Paperclip's backups falling behind on the NAS, and clears when they catch up")

        c = foreman.Check(fresh(), {}, False)
        assert [s.__name__ for s in foreman.steps(c, decisions_only=True)] == ["false_blockers"]
        assert [s.__name__ for s in foreman.steps(c)] == ["preflight", "stalled_cards", "orphan_tasks", "failed_runs",
                                                          "answered_questions", "false_blockers"]
        print("A decisions-only check runs just the step that acts on David's decisions")
        lock = tmp / "foreman.lock"
        first = foreman.one_at_a_time(lock, wait=0)
        assert first is not None and foreman.one_at_a_time(lock, wait=0) is None
        first.close()
        again = foreman.one_at_a_time(lock, wait=0)
        assert again is not None
        again.close()
        print("Only one Foreman check runs at a time; the next one gets its turn when the first finishes")

        command = foreman.start_command()
        assert command.startswith('cmd /c start "Paperclip" /min "') and command.endswith('start_paperclip.cmd"'), command
        print("The restart command quotes the window title, so Windows doesn't take it for the program")
    print("all passed")


if __name__ == "__main__":
    main()
