"""The Roast Writer: the line checks, the plan, a batch on a stand-in model, storing approved lines, and its run in the
Orchestrator on a stand-in board. Reads the game's roast file and never writes it; spends nothing.
usage: python test_roast_writer.py
"""
import hashlib
import json
import re
import tempfile
from pathlib import Path

import bridge
import common
import critic
import orchestrator
import paperclip_board as pb
import roast_writer as rw

REAL_GAME_ROASTS = rw.GAME_ROASTS


def line(text, topic="drowned", outcome="", flag=False, line_id="rw_drowned_001"):
    return {"id": line_id, "text": text, "topic": topic, "outcome": outcome, "noGauntlet": flag, "placeholder": False}


def problems(l, known=(), taken=()):
    return bridge.check_roast_line(l, rw.EVENTS, list(known), set(taken))


def check_tests():
    good = line("The lifeguard has stopped taking your calls.")
    assert problems(good) == [], problems(good)
    print("A line in the voice passes")
    kept = rw.kept_lines()
    assert len(kept) == 40, len(kept)
    for k in kept:
        assert problems({**k, "id": "rw_x_001"}) == [], (k["text"], problems({**k, "id": "rw_x_001"}))
    print("All 40 kept lines pass every check but the new-id one, so the rules fit what David kept")
    long = line("You stayed in the water for a very long time and nobody at all came to help you.")
    assert any("words" in p for p in problems(long)), problems(long)
    for text in ("Drowned them all!", "Was that a plan?", 'He said "swim."', "Splash \U0001F4A6."):
        assert problems(line(text)), text
    assert any("never named" in p for p in problems(line("They went down with the poop."))), problems(line("x poop."))
    assert any("name" in p for p in problems(line("Ask Gary how that went."))), problems(line("Ask Gary how that went."))
    assert any("capitals" in p for p in problems(line("That was a LOT of WATER."))), problems(line("That was a LOT of WATER."))
    assert any("body" in p for p in problems(line("Too fat to float, apparently.")))
    print("Too long, ! or ?, quotes, emoji, the gross thing named, a name, two capital words or a body joke are each refused")
    assert any("repeat" in p for p in problems(line("Dead. Even the enemies looked away out of some respect."),
                                                known=["Dead. Even the enemies looked away out of respect."]))
    assert problems(line("Dead. Nobody will miss you."), known=["Dead. Even the enemies looked away out of respect."]) == []
    print("A near-copy of a known line is a repeat; a line that only shares a word isn't")
    assert any("Gauntlet" in p for p in problems(line("Right between the eyes.", topic="directDeposit", line_id="rw_directDeposit_001")))
    assert problems(line("Right between the eyes.", topic="directDeposit", flag=True, line_id="rw_directDeposit_001")) == []
    assert any("Gauntlet" in p for p in problems(line("The smell will be in the pool for weeks.")))
    assert problems(line("The water is calm now.", flag=True)) == []
    print("A splat event or a smell word needs the Gauntlet flag; a flag where none is needed is fine")
    assert any("event" in p for p in problems(line("Fine.", topic="ceiling")))
    assert any("outcome" in p for p in problems(line("Dead and dirty.", topic="diedDirty", outcome="win", flag=True,
                                                      line_id="rw_diedDirty_001")))
    assert any("id" in p for p in problems(line("Calm water now."), taken={"rw_drowned_001"}))
    assert any("id" in p for p in problems(line("Calm water now.", line_id="drowned_9")))
    print("An unknown event, an outcome the event can't have, a taken id or a badly formed id are each refused")
    assert bridge.needs_gauntlet("Flushed. Try again.", False) and not bridge.needs_gauntlet("Dead.", False)
    assert bridge.needs_gauntlet("Dead.", True)
    assert rw.describe(line("x", topic="directDeposit", outcome="win", flag=True)) == "Direct Deposit, on a win, not in Gauntlet"
    assert rw.describe(line("x", topic="", outcome="loss")) == "General, on a loss"
    assert rw.describe(line("x", topic="drowned", outcome="")) == "Lifeguard Off Duty, on a win or a loss"
    print("The card's description names the event, the outcome and Gauntlet")


def plan_tests():
    have = [(k["topic"], k["outcome"]) for k in rw.kept_lines()]
    assert rw.plan(5, have) == [("drowned", "win"), ("drowned", "loss"), ("longestStreak", "win"), ("fullCoverage", "loss"),
                                ("flaps", "win")], rw.plan(5, have)
    print("A batch covers the events with the fewest lines first, and within one the outcome it has least of")
    assert all(o == "loss" for t, o in rw.plan(40, []) if t == "diedDirty")
    print("Died Dirty only gets loss lines")
    assert rw.next_id("drowned", {"rw_drowned_001", "rw_drowned_002"}) == "rw_drowned_003"
    assert rw.next_id("", set()) == "rw_general_001"
    print("Ids are new and numbered per event")


def save_line(root, l, decision=None, note=""):
    d = root / "roast_lines" / l["id"]
    d.mkdir(parents=True)
    (d / "manifest.json").write_text(json.dumps({"kind": rw.KIND, "agent": rw.AGENT, "name": l["text"], "line": l}), encoding="utf-8")
    if decision:
        (d / "decision.json").write_text(json.dumps({"decision": decision, "note": note}), encoding="utf-8")


def batch_tests(tmp):
    common.SUBMISSIONS = tmp / "submissions"
    rw.APPROVED = tmp / "approved" / "roast_lines.json"
    game = tmp / "roasts.json"
    kept = [line(f"Kept line number {k} about {t or 'nothing'}.", topic=t, outcome="win", flag=rw.EVENTS[t][2],
                 line_id=f"{t or 'gen'}_{k:02}") for t in rw.EVENTS if t != "drowned" for k in range(2)]
    kept = [dict(k, outcome="loss") if k["topic"] == "diedDirty" else k for k in kept]
    game.write_text(json.dumps({"lines": kept}), encoding="utf-8")
    rw.GAME_ROASTS = game
    before = hashlib.sha256(game.read_bytes()).hexdigest()

    assert rw.state() == {"waiting": 0, "approved": 0, "next": rw.FIRST}, rw.state()
    print("Before any line is made, the next batch is the 5-line test")
    save_line(common.SUBMISSIONS, line("Rejected about flaps.", topic="flaps", line_id="rw_flaps_001"), "reject", "too wordy")
    save_line(common.SUBMISSIONS, line("Approved about kills.", topic="kills", outcome="win", line_id="rw_kills_001"), "approve")
    assert rw.state() == {"waiting": 0, "approved": 1, "next": rw.PER_RUN}, rw.state()

    calls = []

    def fake_ask_json(agent, messages, required, **kw):
        assert agent == "roast-writer", agent
        calls.append((required, messages))
        if required == ["lines"]:
            if sum(r == ["lines"] for r, _ in calls) == 1:
                return {"lines": [{"text": "The lifeguard has stopped taking your calls.", "outcome": "win"},
                                  {"text": "They sank with the poop.", "outcome": "win"},
                                  {"text": "You stayed in the water for a very long time and nobody at all came to help.", "outcome": "win"},
                                  {"text": "Kept line number 0 about kills.", "outcome": "win"},
                                  *[{"text": f"Glug number {k}!", "outcome": "loss"} for k in range(4)]]}
            return {"lines": [{"text": "The pool has asked you to leave.", "outcome": "loss"},
                              {"text": "Even the water wanted you out.", "outcome": "loss"}]}
        numbered = [x for x in messages[-1]["content"].splitlines() if re.match(r"^\d+\. ", x)]
        return {"scores": [{"n": k + 1, "fits": 5, "voice": 5, "funny": 9 if "leave" in x else 3, "fresh": 5}
                           for k, x in enumerate(numbered)]}

    real = common.ask_json
    common.ask_json = fake_ask_json
    said = []
    try:
        folders = rw.make_batch(2, {"id": "card-14", "name": "[Roast Writer] 250 new roast lines"}, "run-1", said.append)
    finally:
        common.ask_json = real
    writes = [m for r, m in calls if r == ["lines"]]
    assert len(writes) == 2, len(writes)
    assert "4 for a win" in writes[0][-1]["content"] and "4 for a loss" in writes[0][-1]["content"], writes[0][-1]["content"]
    assert "for a loss" in writes[1][-1]["content"] and "for a win" not in writes[1][-1]["content"], writes[1][-1]["content"]
    print("Every line needed gets 4 candidates, and an outcome with none left after the checks gets one more try")
    assert "too wordy" in writes[0][-1]["content"] and "Rejected about flaps." in writes[0][-1]["content"]
    assert "Kept line number 0 about kills." in writes[0][-1]["content"] and "Approved about kills." in writes[0][-1]["content"]
    print("The prompt holds the kept lines, the approved lines, and each rejected line with David's note")
    assert writes[0][-1]["content"].startswith("From the Bottom Busters game design document (GDD), Section 21")
    assert "### 21.2 Roast lines" in writes[0][-1]["content"] and "### 21.1 Characters" not in writes[0][-1]["content"]
    print("Every write starts with the GDD's Content guide opening and Section 21.2, before anything else")
    made = [json.loads((f / "manifest.json").read_text(encoding="utf-8")) for f in folders]
    assert [m["line"]["text"] for m in made] == ["The lifeguard has stopped taking your calls.", "The pool has asked you to leave."], made
    assert [m["line"]["id"] for m in made] == ["rw_drowned_001", "rw_drowned_002"]
    assert [m["line"]["outcome"] for m in made] == ["win", "loss"]
    print("The best line for each outcome goes up; the poop line, the long one, the repeat and the ! ones never do")
    m = made[0]
    assert m["kind"] == "roast line" and m["agent"] == "Roast Writer" and m["card"] == "card-14" and m["run"] == "run-1"
    assert m["label"] == m["line"]["text"] and m["description"] == "Lifeguard Off Duty, on a win", m
    assert m["line"]["placeholder"] is False and m["line"]["noGauntlet"] is False
    assert all(f.parent == common.SUBMISSIONS / "roast_lines" for f in folders)
    print("Each line is its own submission folder, with the whole line as its card label")
    assert any("poop" in s or "never named" in s for s in said), said
    assert hashlib.sha256(game.read_bytes()).hexdigest() == before
    print("The game's roast file is read, never written")
    assert rw.state() == {"waiting": 2, "approved": 1, "next": 0}, rw.state()
    print("While David hasn't decided the last card, no new batch starts")

    (folders[0] / "decision.json").write_text(json.dumps({"decision": "approve", "note": ""}), encoding="utf-8")
    (folders[1] / "decision.json").write_text(json.dumps({"decision": "reject", "note": "flat"}), encoding="utf-8")
    assert rw.store_approved() == 2
    stored = json.loads(rw.APPROVED.read_text(encoding="utf-8"))["lines"]
    assert [s["id"] for s in stored] == ["rw_drowned_001", "rw_kills_001"], stored
    assert set(stored[0]) == {"id", "text", "topic", "outcome", "noGauntlet", "placeholder"}, stored[0]
    print("Approved lines collect outside the game, in the game's own line format")


def review_tests(tmp):
    """The Critic's GDD check inside a batch: lines it fails are dropped, and its reasons go into that event's next try."""
    writes, checked = [], []
    first = ["The deep end has filed a formal complaint.", "Sunk. The pool would like a word."]

    def fake_ask_json(agent, messages, required, **kw):
        if required == ["lines"]:
            writes.append(messages[-1]["content"])
            texts = first if len(writes) == 1 else ["Down you went. The lifeguard took notes."]
            return {"lines": [{"text": t, "outcome": "loss"} for t in texts]}
        numbered = [x for x in messages[-1]["content"].splitlines() if re.match(r"^\d+\. ", x)]
        return {"scores": [{"n": k + 1, "fits": 5, "voice": 5, "funny": 5, "fresh": 5} for k in range(len(numbered))]}

    def review(lines, describe):
        checked.append([(l["text"], describe(l)) for l in lines])
        return [{"verdict": "fail", "problem": "a grievance is the kept lines' joke, not a new one"} if "complaint" in l["text"]
                else {"verdict": "fail", "problem": "a flat verdict with no turn"} if "Sunk" in l["text"]
                else {"verdict": "pass", "problem": ""} for l in lines]

    real = common.ask_json
    common.ask_json = fake_ask_json
    said = []
    try:
        folders = rw.make_batch(1, {"id": "card-14", "name": "[Roast Writer] 250 new roast lines"}, "run-2", said.append, review=review)
    finally:
        common.ask_json = real
    assert len(checked) == 2 and [t for t, _ in checked[0]] == first, checked
    assert checked[0][0][1] == "Lifeguard Off Duty, on a loss", checked[0][0]
    print("Every line that passed the Bridge goes to the Critic's GDD check, with its event and outcome")
    assert "a flat verdict with no turn" in writes[1] and "Sunk. The pool would like a word." in writes[1], writes[1]
    print("A line the Critic sent back is dropped, and its GDD reason reaches that event's next try")
    made = [json.loads((f / "manifest.json").read_text(encoding="utf-8"))["line"]["text"] for f in folders]
    assert made == ["Down you went. The lifeguard took notes."], made
    assert any("sent back" in s and "complaint" in s for s in said) and any("0 of 2" in s for s in said), said
    print("Only a line that passed the GDD check goes up, and the run log says what the Critic sent back")


class Board:
    def __init__(self):
        self.moves, self.comments, self.tasks = [], [], []

    def move(self, card, list_name):
        self.moves.append(list_name)
        card["list"] = list_name

    def comment(self, card, text):
        self.comments.append(text)

    def open_task(self, card, agent, title, brief):
        self.tasks.append([agent, title, None])
        return len(self.tasks) - 1

    def close_task(self, task_id, status, text):
        self.tasks[task_id][2] = status


def orchestrator_tests(tmp):
    common.RUNS = tmp / "runs"
    statuses = []
    orchestrator.set_status = statuses.append
    orchestrator.report_costs = lambda board, run, card: None
    card = {"id": "card-14", "name": "[Roast Writer] 250 new roast lines", "list": pb.BACKLOG, "agent": "roast-writer"}
    assert orchestrator.MAKERS["Roast Writer"]["id"] == "roast-writer"

    rw.state = lambda: {"waiting": 3, "approved": 10, "next": 0}
    board = Board()
    assert orchestrator.run_roasts(board, dict(card), common.Run("r-wait")) == 0
    assert board.moves == [] and board.tasks == []
    print("While David is deciding the last card, the run leaves the card alone")

    made = []
    rw.state = lambda: {"waiting": 0, "approved": 10, "next": 25}
    handed = []
    rw.make_batch = lambda n, c, run_id, say=print, review=None: handed.append(review) or made.append(n) or [Path("a"), Path("b")]
    board = Board()
    assert orchestrator.run_roasts(board, dict(card), common.Run("r-go")) == 0
    assert made == [25] and board.moves == [pb.LEASED, pb.BACKLOG], board.moves
    assert handed == [critic.check_gdd_lines], handed
    print("The Orchestrator hands the batch the Critic's GDD check")
    assert board.tasks == [["roast-writer", "25 new roast lines", "done"]], board.tasks
    assert any("Paperclip inbox" in c for c in board.comments), board.comments
    print("A batch leases the card, closes its task, and puts the card back in the queue for the next batch")

    def stops(n, c, run_id, say=print, review=None):
        raise common.CrewStop("MindRouter is down")
    rw.make_batch = stops
    board = Board()
    assert orchestrator.run_roasts(board, dict(card), common.Run("r-stop")) == 1
    assert board.tasks[0][2] == "cancelled" and board.moves[-1] == pb.BACKLOG, (board.tasks, board.moves)
    print("A stopped batch cancels its task and puts the card back with the reason")

    rw.state = lambda: {"waiting": 0, "approved": 250, "next": 0}
    board = Board()
    assert orchestrator.run_roasts(board, dict(card), common.Run("r-done")) == 0
    assert board.moves == [pb.DONE] and any("250" in c for c in board.comments), (board.moves, board.comments)
    assert not any("\\" in c for c in board.comments), board.comments   # Paperclip stores "\r" in a path as a line break
    print("With 250 approved, the card is done, and its note names the file with forward slashes")


def main():
    check_tests()
    plan_tests()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        batch_tests(tmp)
        review_tests(tmp)
        rw.GAME_ROASTS = REAL_GAME_ROASTS
        orchestrator_tests(tmp)
    print("all passed")


if __name__ == "__main__":
    main()
