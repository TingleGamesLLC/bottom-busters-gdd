"""The paths a good run never takes: the Bridge sends bad files back, the maker fixes them, and two failures stop the task.

Uses a character built from the game's own files with a new look painted on as the good output, a copy with a file missing as
the bad output, and a stand-in Critic, so it spends no model time and touches neither Paperclip nor the dashboard.
usage: python test_sendback.py
"""
import json
import shutil
import tempfile
from pathlib import Path

import bridge
import character_artist
import common
import critic
import orchestrator
import test_bridge


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        common.RUNS = tmp / "runs"
        common.SUBMISSIONS = tmp / "submissions"
        (common.SUBMISSIONS / "characters").mkdir(parents=True)
        work = tmp / "work"
        bad = tmp / "bad"
        good = test_bridge.good_character(tmp / "made")
        shutil.copytree(good, bad)
        (bad / "Resources" / "DeathFlail" / "player11_flail_05.png").unlink()

        problems = bridge.check_character(bad)
        assert any("flail_05" in p for p in problems), problems
        print("Bridge catches a missing flail frame:", problems[0])
        assert bridge.check_character(good) == [], bridge.check_character(good)
        print("Bridge passes a good character")

        critic.review = lambda folder, concept, facts: {"verdict": "pass", "what_i_see": "stand-in", "problems": [], "note_for_artist": ""}
        card = {"id": "test", "name": "test card", "desc": "", "list": "Review"}
        records = []

        class Tasks:
            """A stand-in Paperclip: records each task opened, commented on and closed."""
            def open_task(self, card_, agent, title, brief):
                records.append(("open", agent))
                return f"{agent}-{len(records)}"

            def close_task(self, task_id, status, text):
                records.append(("close", task_id.rsplit("-", 1)[0], status))

            def task_comment(self, task_id, text):
                records.append(("comment", task_id.rsplit("-", 1)[0], text))

        tasks = Tasks()
        task = {"id": "t1", "brief": "test"}
        concept = {"name": "test", "hair": "x", "hair_color": "x", "skin_tone": "default"}

        def maker(order):
            calls = {"n": 0, "notes": []}

            def make(task_, slot, taken, notes, seed):
                calls["notes"].append(notes)
                source = order[min(calls["n"], len(order) - 1)]
                calls["n"] += 1
                if work.exists():
                    shutil.rmtree(work)
                shutil.copytree(source, work)
                return work, concept
            return {"id": "character-artist", "make": make, "check": bridge.check_character, "publish": character_artist.publish}, calls

        # Bad, then good: one fix prompt, then it passes, and the fix prompt reached the maker.
        m, calls = maker([bad, good])
        result = orchestrator.work_task(common.Run("test-fix"), tasks, card, m, task, 11, 1, lambda: None)
        assert calls["n"] == 2 and "flail_05" in calls["notes"][1], calls
        print("Bad then good: the maker got the fix prompt and the task finished as", result["skin"])
        assert records[0] == ("open", "character-artist") and records[-1] == ("close", "character-artist", "done"), records
        assert any(r[0] == "comment" and "flail_05" in r[2] for r in records), records
        assert ("open", "critic") in records and ("close", "critic", "done") in records, records
        print("Paperclip got the maker's task with the Bridge's send-back on it, and the Critic's review, both closed")
        records.clear()
        published = common.SUBMISSIONS / "characters" / result["folder"]
        assert (published / "manifest.json").exists() and not work.exists()
        print("Only work that passed reaches the approval screen")
        shutil.rmtree(published)
        slot_before = character_artist.next_slot([])

        # Bad twice: both cheeks popped, the run stops and says why.
        m, calls = maker([bad])
        try:
            orchestrator.work_task(common.Run("test-stop"), tasks, card, m, task, 11, 1, lambda: None)
            raise AssertionError("two failures should stop the task")
        except common.CrewStop as e:
            assert calls["n"] == 2, calls
            print("Bad twice: stopped after two tries:", str(e)[:90])
        assert records[-1] == ("close", "character-artist", "cancelled"), records
        print("The stopped task is closed as cancelled in Paperclip, saying why")
        assert not list((common.SUBMISSIONS / "characters").iterdir()), "failed work reached the approval screen"
        assert (common.RUNS / "test-stop" / "failed" / "work" / "manifest.json").exists()
        assert character_artist.next_slot([]) == slot_before
        print("The failed attempt stays with the run, off the approval screen, and holds no slot")

        # The GDD check: a design the Critic fails against the GDD goes back with the rule it broke, before any art is built.
        verdicts = []

        def fake_check(agent, work_):
            v = verdicts.pop(0)
            return {"verdict": v, "problems": [] if v == "pass" else ["green hair breaks Section 21.1"],
                    "note_for_maker": "" if v == "pass" else "Pick another hair color.", "gdd": "BOTTOM_BUSTERS_GDD.md, Sections 21 and 21.1"}
        critic.check_gdd = fake_check

        def two_step():
            calls = {"design": [], "build": 0}

            def design(task_, slot, taken, notes, seed):
                calls["design"].append(notes)
                return dict(concept)

            def build(task_, slot, d, seed):
                calls["build"] += 1
                if work.exists():
                    shutil.rmtree(work)
                shutil.copytree(good, work)
                return work, d
            return {"id": "character-artist", "design": design, "build": build, "for_review": lambda d: d,
                    "check": bridge.check_character, "publish": character_artist.publish}, calls

        records.clear()
        verdicts[:] = ["fail", "pass"]
        m, calls = two_step()
        gdd_run = common.Run("test-gdd")
        result = orchestrator.work_task(gdd_run, tasks, card, m, task, 11, 1, lambda: None)
        assert len(calls["design"]) == 2 and calls["build"] == 1, calls
        assert "green hair breaks Section 21.1" in calls["design"][1] and "Pick another hair color." in calls["design"][1], calls
        print("GDD fail, then pass: the design went back with the GDD rule it broke, and only the passing design was built")
        sent = sorted(p.name for p in gdd_run.messages.iterdir())
        assert sum("_character-artist_to_critic_design" in n for n in sent) == 2, sent
        assert sum("_critic_to_orchestrator_gdd_check" in n for n in sent) == 2, sent
        assert sum("_orchestrator_to_character-artist_gdd_send_back" in n for n in sent) == 1, sent
        print("Every design, verdict and send-back is a handoff file in the run's messages folder")
        assert any(r[0] == "comment" and "against the GDD" in r[2] for r in records), records
        assert records.count(("open", "critic")) == 3, records   # two GDD checks, then the picture review
        published = common.SUBMISSIONS / "characters" / result["folder"]
        assert json.loads((published / "manifest.json").read_text(encoding="utf-8"))["gdd_check"]["verdict"] == "pass"
        print("Paperclip shows each GDD check as the Critic's task, and the manifest carries the passing verdict")
        shutil.rmtree(published)

        verdicts[:] = ["fail", "fail"]
        m, calls = two_step()
        try:
            orchestrator.work_task(common.Run("test-gdd-stop"), tasks, card, m, task, 11, 1, lambda: None)
            raise AssertionError("two GDD fails should stop the task")
        except common.CrewStop as e:
            assert calls["build"] == 0 and "lost both cheeks" in str(e) and "against the GDD: green hair" in str(e), (calls, e)
            print("GDD fail twice: both cheeks popped, nothing was built, and the run says why:", str(e)[:70])
        assert not list((common.SUBMISSIONS / "characters").iterdir())

        moved = []

        class Board:
            def move(self, card_, list_name):
                moved.append(("move", list_name))

            def comment(self, card_, text):
                moved.append(("comment", text))

        orchestrator.reset_card(Board(), card, common.Run("test-reset"), "the reason")
        assert moved[0] == ("move", "Backlog") and "the reason" in moved[1][1], moved
        print("A stopped run's card goes back to the Backlog, saying why")

        # A question only David can answer: asked once, and the card waits on it instead of going back in the queue.
        asked, updates = [], []

        class Waiting:
            def ask_david(self, title, text, parent=None):
                asked.append((title, parent))
                return "question-1"

            def update(self, issue_id, body):
                updates.append((issue_id, body))

        waiting_run = common.Run("test-wait")
        orchestrator.wait_for_david(Waiting(), card, waiting_run, common.NeedsDavid("player21 is past player20"), [{"name": "x"}])
        assert len(asked) == 1 and asked[0][1] == "test" and "player21" in asked[0][0], asked
        assert updates == [("test", {"status": "blocked", "blockedByIssueIds": ["question-1"],
                                     "comment": "Crew run test-wait needs David: player21 is past player20"})], updates
        assert waiting_run.state["status"].startswith("waiting on David"), waiting_run.state["status"]
        print("A question for David is asked once and blocks the card, instead of a stop that repeats")

        # How many a set card makes: what the set still needs, so a run that stopped partway picks up where it left off.
        def made(name, the_set, decision=None, redone=False):
            d = common.SUBMISSIONS / "characters" / name
            d.mkdir(parents=True)
            m = {"kind": "character", "set": the_set, "name": name}
            if redone:
                m["redone_by"] = "redo-card"
            (d / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
            if decision:
                (d / "decision.json").write_text(json.dumps({"decision": decision}), encoding="utf-8")
        set_card = {"name": "[Character Artist] First set: the other 8 characters", "desc": "", "url": "BOT-33"}
        assert orchestrator.how_many(set_card, None, "Test set") == 10
        made("a", "Test set", "approve")
        made("b", "Test set")
        made("c", "Test set", "reject")
        made("d", "Test set", "reject", redone=True)
        made("e", "Other set", "approve")
        assert orchestrator.how_many(set_card, None, "Test set") == 7, orchestrator.how_many(set_card, None, "Test set")
        assert orchestrator.how_many(set_card, "a note", "Test set") == 1
        print("A set card makes what its set still needs: a rejection with no note is remade, one sent back as a redo isn't counted twice")
        for name in "abcde":
            shutil.rmtree(common.SUBMISSIONS / "characters" / name)

        # Alongside: one child run per maker, the worst exit code wins.
        started = []

        class Child:
            def __init__(self, args):
                self.args = args
                started.append(args)

            def wait(self):
                return 1 if "level-architect" in self.args else 0
        real_popen = orchestrator.subprocess.Popen
        orchestrator.subprocess.Popen = Child
        try:
            code = orchestrator.run_alongside()
        finally:
            orchestrator.subprocess.Popen = real_popen
        assert sorted(a[a.index("--maker") + 1] for a in started) == ["character-artist", "level-architect", "roast-writer",
                                                                      "wardrobe-stylist"] \
            and code == 1, (started, code)
        assert all("--child" in a for a in started), started
        print("Every maker gets its own child run at the same time, and the worst exit code is the run's")

        # No maker's run carries crew-wide work (DAVID, 2026-11-04: "0 dependancies should exist in the agent pipeline").
        upkept, stored = [], []
        tw, la = orchestrator.technical_writer, orchestrator.level_architect
        real = (tw.close_finished, tw.write_diagram, orchestrator.trello.open_board, orchestrator.game_running,
                orchestrator.pick_card, la.store_approved, orchestrator.run_alongside, list(orchestrator.sys.argv))
        try:
            tw.close_finished = lambda board, log: upkept.append("close")
            tw.write_diagram = lambda pipeline: upkept.append("diagram")
            orchestrator.trello.open_board = lambda: object()
            orchestrator.game_running = lambda: False
            orchestrator.pick_card = lambda board, run, only=None: (None, None)
            la.store_approved = lambda: stored.append(1)
            orchestrator.run_alongside = lambda: upkept.append("makers") or 0
            orchestrator.sys.argv[:] = ["orchestrator.py"]
            assert orchestrator.main() == 0 and upkept == ["diagram", "close", "makers"], upkept
            for m in ("character-artist", "level-architect", "roast-writer", "wardrobe-stylist"):
                upkept.clear()
                orchestrator.sys.argv[:] = ["orchestrator.py", "--maker", m, "--child"]
                assert orchestrator.main() == 0 and upkept == [], (m, upkept)
            assert stored == [1], stored
            upkept.clear()
            orchestrator.sys.argv[:] = ["orchestrator.py", "--maker", "roast-writer"]
            orchestrator.main()
            assert upkept == ["diagram", "close"], upkept

            def broken(board, log):
                raise RuntimeError("Paperclip answered HTTP 500")
            tw.close_finished = broken
            upkept.clear()
            orchestrator.sys.argv[:] = ["orchestrator.py"]
            assert orchestrator.main() == 0 and upkept == ["diagram", "makers"], upkept
        finally:
            (tw.close_finished, tw.write_diagram, orchestrator.trello.open_board, orchestrator.game_running,
             orchestrator.pick_card, la.store_approved, orchestrator.run_alongside, argv) = real
            orchestrator.sys.argv[:] = argv
        print("Closing finished cards and the diagram run once before the makers start, never inside one maker's run; "
              "the Level Architect's run stores only its own backgrounds")

        class Two:
            def cards(self, list_name):
                return [{"id": "c", "name": "[Character Artist] x", "agent": "character-artist", "desc": ""},
                        {"id": "l", "name": "[Level Architect] y", "agent": "level-architect", "desc": ""}]

        class Quiet:
            def event(self, agent, text):
                pass
        assert orchestrator.pick_card(Two(), Quiet(), "level-architect")[0]["id"] == "l"
        assert orchestrator.pick_card(Two(), Quiet())[0]["id"] == "c"
        print("A maker's child run takes only that maker's cards")

        # The Critic's fail doesn't send work back. It goes to David as a note beside the character.
        critic.review = lambda folder, concept, facts: {"verdict": "fail", "what_i_see": "stand-in", "problems": ["a problem"], "note_for_artist": "the Critic's words"}
        m, calls = maker([good])
        result = orchestrator.work_task(common.Run("test-note"), tasks, card, m, task, 11, 1, lambda: None)
        published = json.loads((common.SUBMISSIONS / "characters" / result["folder"] / "manifest.json").read_text(encoding="utf-8"))
        assert calls["n"] == 1 and "the Critic's words" in published["name"] and published["critic"]["verdict"] == "fail", published["name"]
        print("A Critic fail reaches David as a note, without a send-back")
    print("all passed")


if __name__ == "__main__":
    main()
