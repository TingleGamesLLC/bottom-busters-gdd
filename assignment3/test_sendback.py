"""The paths a good run never takes: the Bridge sends bad files back, the maker fixes them, and two failures stop the task.

Uses a character built from the game's own files with a new look painted on as the good output, a copy with a file missing as
the bad output, and a stand-in Critic, so it spends no model time and touches neither Trello nor the dashboard.
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
        result = orchestrator.work_task(common.Run("test-fix"), card, m, task, 11, 1, lambda: None)
        assert calls["n"] == 2 and "flail_05" in calls["notes"][1], calls
        print("Bad then good: the maker got the fix prompt and the task finished as", result["skin"])
        published = common.SUBMISSIONS / "characters" / result["folder"]
        assert (published / "manifest.json").exists() and not work.exists()
        print("Only work that passed reaches the approval screen")
        shutil.rmtree(published)
        slot_before = character_artist.next_slot([])

        # Bad twice: both cheeks popped, the run stops and says why.
        m, calls = maker([bad])
        try:
            orchestrator.work_task(common.Run("test-stop"), card, m, task, 11, 1, lambda: None)
            raise AssertionError("two failures should stop the task")
        except common.CrewStop as e:
            assert calls["n"] == 2, calls
            print("Bad twice: stopped after two tries:", str(e)[:90])
        assert not list((common.SUBMISSIONS / "characters").iterdir()), "failed work reached the approval screen"
        assert (common.RUNS / "test-stop" / "failed" / "work" / "manifest.json").exists()
        assert character_artist.next_slot([]) == slot_before
        print("The failed attempt stays with the run, off the approval screen, and holds no slot")

        moved = []

        class Board:
            def move(self, card_, list_name):
                moved.append(("move", list_name))

            def comment(self, card_, text):
                moved.append(("comment", text))

        orchestrator.reset_card(Board(), card, common.Run("test-reset"), "the reason")
        assert moved[0] == ("move", "Backlog") and "the reason" in moved[1][1], moved
        print("A stopped run's card goes back to the Backlog, saying why")

        # The Critic's fail doesn't send work back. It goes to David as a note beside the character.
        critic.review = lambda folder, concept, facts: {"verdict": "fail", "what_i_see": "stand-in", "problems": ["a problem"], "note_for_artist": "the Critic's words"}
        m, calls = maker([good])
        result = orchestrator.work_task(common.Run("test-note"), card, m, task, 11, 1, lambda: None)
        published = json.loads((common.SUBMISSIONS / "characters" / result["folder"] / "manifest.json").read_text(encoding="utf-8"))
        assert calls["n"] == 1 and "the Critic's words" in published["name"] and published["critic"]["verdict"] == "fail", published["name"]
        print("A Critic fail reaches David as a note, without a send-back")
    print("all passed")


if __name__ == "__main__":
    main()
