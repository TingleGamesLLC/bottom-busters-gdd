"""Orchestrator: runs one crew run against the Trello board, top to bottom. This is the file you start.

    python orchestrator.py            one run; skipped if the game is running
    python orchestrator.py --now      one run even if the game is running

It takes the first card it has a maker for, splits it into tasks, leases it to that maker, sends the work through the Bridge
and the Critic, and stops at Your Playtest. David tests and David says commit: nothing here commits, pushes, launches the
game or copies anything into the project.
"""
import base64
import json
import re
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

import board as trello
import bridge
import character_artist
import common
import critic
import pixellab
import technical_writer
from common import CrewStop, MalformedOutput, Run, cheeks_for

# DAVID, 2026-10-30 ("go"): the first batch is 2 characters. The GDD's total of 10 stays a placeholder.
BATCH = 2

# What the board's card prefixes mean. A prefix with no runner is work this crew doesn't do yet.
MAKERS = {"Character Artist": {"id": "character-artist", "make": character_artist.make, "check": bridge.check_character, "publish": character_artist.publish}}
NOT_MAKERS = ("Assignment", "You", "Waiting", "Builder")

PIPELINE = {
    "nodes": [("D", "Studio Director (David)<br/>plays every build, says commit", "person"),
              ("T", "Trello board<br/>Backlog, In Progress, Review, Your Playtest, Done", "store"),
              ("O", "Orchestrator<br/>qwen3:30b on the cluster", "round"),
              ("A", "Character Artist: concept<br/>qwen3:30b on the cluster", "round"),
              ("F", "Character Artist: art<br/>PixelLab, flail.py, idle_game.py, flap_game.py, splat_faces.py", "box"),
              ("B", "Bridge<br/>a script, not AI: checks the files", "box"),
              ("C", "Critic<br/>qwen2.5vl:7b on the cluster", "round"),
              ("W", "Technical Writer<br/>qwen3:30b on the cluster", "round"),
              ("S", "C:\\cluster\\submissions<br/>character files waiting for approval", "store"),
              ("H", "Dashboard<br/>Crew and Characters tabs", "box"),
              ("G", "Bottom Busters<br/>Unity project", "store")],
    "edges": [("T", "O", "next card in David's order"), ("O", "T", "leases and moves the card"),
              ("O", "A", "task brief (JSON)"), ("A", "F", "concept (JSON)"), ("F", "S", "sprite, flail, idle and flap frames, splat, metas"),
              ("S", "B", "submission"), ("B", "A", "fix prompt if malformed"), ("B", "C", "passes the format check"),
              ("C", "O", "verdict (JSON)"), ("O", "S", "the Critic's note, beside the character"), ("O", "W", "run record"), ("W", "T", "summary comment"),
              ("O", "H", "status, cheeks, tokens"), ("S", "H", "shown for approval"), ("H", "D", "Approve or Reject with a note"),
              ("D", "S", "decision.json"), ("D", "G", "tests, says commit")],
    "classes": {"cluster": ["O", "A", "C", "W"], "script": ["F", "B"], "human": ["D"]},
    "styles": {"cluster": "fill:#CFE8F7,stroke:#1F2A44", "script": "fill:#FBFBF8,stroke:#1F2A44", "human": "fill:#F3D9A4,stroke:#1F2A44"},
}

PLAN_SYSTEM = """You are the Orchestrator of a game development agent crew. You split a Trello card into small tasks for one specialist.
Answer with only one JSON object with these fields:
"objective": the card's goal in one sentence
"tasks": a list of objects, each with one field "brief": what this one task must produce, in one sentence. Each brief asks for something clearly different from the others."""


def game_running():
    out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True).stdout.lower()
    return any(name in out for name in ("bbust.exe", "bottom busters", "bottombusters"))


def pick_card(board, run):
    """The first card from the top that has a maker. David's order is the priority; nothing is reordered."""
    for card in board.cards(trello.BACKLOG):
        m = re.match(r"\[(.+?)\]", card["name"])
        prefix = m.group(1) if m else ""
        if prefix in MAKERS:
            return card, MAKERS[prefix]
        if prefix not in NOT_MAKERS:
            run.event("orchestrator", f"no runner yet for: {card['name']}")
    return None, None


def plan(card, batch):
    memory = common.MEMORY.read_text(encoding="utf-8") if common.MEMORY.exists() else "(no earlier runs)"
    messages = [{"role": "system", "content": PLAN_SYSTEM},
                {"role": "user", "content": f"Card: {card['name']}\nDescription: {card['desc']}\nSplit it into exactly {batch} tasks.\n\n"
                                            f"Notes from earlier runs:\n{memory}"}]
    d = common.ask_json("orchestrator", messages, ["objective", "tasks"], max_tokens=800)
    # Plain code decides how much gets made: a longer plan is cut to the batch, and a shorter one is malformed.
    tasks = [t for t in d["tasks"] if isinstance(t, dict) and t.get("brief")][:batch]
    if len(tasks) != batch:
        raise MalformedOutput(f"the plan has {len(tasks)} tasks, not {batch}")
    return d["objective"], [{"id": f"t{k + 1}", "brief": t["brief"]} for k, t in enumerate(tasks)]


def set_status(updates):
    """Status, cheeks and last output on the dashboard's Crew tab: a small atomic rewrite of crew.json on Node A."""
    script = ("import json,sys,os\n"
              f"p='{common.DASHBOARD}/crew.json'\n"
              "d=json.load(open(p))\nu=json.load(sys.stdin)\n"
              "for a in d['agents']:\n"
              "    if a['id'] in u:\n"
              "        c=dict(u[a['id']]); inc=c.pop('units_add',0); a.update(c); a['units_done']=a.get('units_done',0)+inc\n"
              "t=p+'.crewtmp'\njson.dump(d,open(t,'w'),indent=2)\nos.replace(t,p)\n")
    encoded = base64.b64encode(script.encode()).decode()
    c = common.ssh()
    try:
        stdin, out, err = c.exec_command(f"/opt/homebrew/bin/python3.14 -c \"$(echo {encoded} | base64 -d)\"", timeout=20)
        stdin.write(json.dumps(updates))
        stdin.channel.shutdown_write()
        problem = err.read().decode("utf-8", "replace").strip()
        if problem:
            print("dashboard status not updated:", problem[:300], flush=True)
    finally:
        c.close()


def taken_looks():
    looks = []
    for manifest in common.SUBMISSIONS.glob("characters/*/manifest.json"):
        d = json.loads(manifest.read_text(encoding="utf-8")).get("concept") or {}
        if d:
            looks.append(f"{d.get('hair')}, {d.get('hair_color')} hair")
    return looks


def keep_failed(run, folder):
    """The last attempt stays with the run's record, off David's approval screen and holding no slot."""
    failed = run.dir / "failed"
    failed.mkdir(exist_ok=True)
    if (failed / Path(folder).name).exists():
        shutil.rmtree(failed / Path(folder).name)
    shutil.move(str(folder), str(failed / Path(folder).name))


def reset_card(board, card, run, why):
    """A stopped run's card goes back where the next run can pick it up, saying why."""
    board.move(card, trello.BACKLOG)
    board.comment(card, f"Crew run {run.id} stopped: {why}")


def work_task(run, card, maker, task, slot, seed, to_review):
    """One task through maker, Bridge and Critic. A Bridge send-back pops the maker's cheek, and both popped stops the task. The
    Critic's verdict goes with the work to David."""
    agent, cheeks, notes = maker["id"], cheeks_for(maker["id"]), None
    while True:
        run.send("orchestrator", agent, "task", {**task, "slot": slot, "notes": notes})
        try:
            folder, concept = maker["make"](task, slot, taken_looks(), notes, seed)
        except MalformedOutput as e:
            problem = str(e)
            run.event(agent, f"sent back: {problem}")
            if cheeks.pop() <= 0:
                raise CrewStop(f"{agent} lost both cheeks on {task['id']}: {problem}")
            notes, seed = problem, seed + 10
            continue
        run.send(agent, "bridge", "submission", {"task": task["id"], "folder": str(folder), "concept": concept})
        to_review()

        problems = maker["check"](folder)
        if problems:
            notes = " ".join(problems)
            run.send("bridge", agent, "fix_prompt", {"task": task["id"], "problems": problems})
            run.event("bridge", f"sent back {task['id']}: {notes[:200]}")
            if cheeks.pop() <= 0:
                keep_failed(run, folder)
                raise CrewStop(f"{agent} lost both cheeks on {task['id']}: {notes[:300]}")
            seed += 10
            continue
        facts = bridge.facts(folder)
        run.send("bridge", "critic", "passed", {"task": task["id"], "folder": str(folder), "facts": facts})

        verdict = critic.review(folder, concept, facts)
        run.send("critic", "orchestrator", "verdict", {"task": task["id"], **verdict})
        run.event("critic", f"{task['id']} {verdict['verdict']}: {verdict.get('what_i_see')}")
        # The Critic hasn't been tested on art with known answers, so its fail is a note beside the character for David, not a send-back.
        manifest = folder / "manifest.json"
        m = json.loads(manifest.read_text(encoding="utf-8"))
        m.update(card=card["id"], card_name=card["name"], run=run.id, bridge=facts, critic=verdict)
        if verdict["verdict"] != "pass":
            note = verdict.get("note_for_artist") or "; ".join(verdict.get("problems") or []) or "the Critic failed it"
            m["name"] = f"{m['name']}. Critic's note: {note}"
        manifest.write_text(json.dumps(m, indent=2), encoding="utf-8")
        folder = maker["publish"](folder)
        cheeks.refill()
        return {"task": task["id"], "name": concept.get("name"), "skin": m["skin"], "look": f"{concept.get('hair')}, {concept.get('hair_color')}",
                "skin_tone": concept.get("skin_tone"), "critic_saw": verdict.get("what_i_see"), "folder": folder.name, "difference_from_roster": facts["difference_from_nearest"]}


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--now" not in sys.argv and game_running():
        print("skipped: the game is running, and David gets the PC while he plays")
        return 0

    board = trello.open_board()
    run = Run()
    technical_writer.write_diagram(PIPELINE)
    technical_writer.close_finished(board, run)
    card, maker = pick_card(board, run)
    if not card:
        run.state["status"] = "nothing to do"
        run.event("orchestrator", "no card on the board that this crew can work")
        return 0

    agent = maker["id"]
    run.state["card"] = card["name"]
    results, card_moved = [], False
    try:
        run.event("orchestrator", f"PixelLab balance before: {pixellab.balance()}")
        set_status({"orchestrator": {"status": "working"}, agent: {"status": "working", "cheeks": 2}})
        objective, tasks = plan(card, BATCH)
        run.state["objective"], run.state["tasks"] = objective, tasks
        run.event("orchestrator", f"plan for {card['name']}: {len(tasks)} tasks")
        board.move(card, trello.LEASED)
        card_moved = True
        board.comment(card, f"Leased to {agent} by the Orchestrator, run {run.id}. Plan: " + " | ".join(t["brief"] for t in tasks))

        def to_review():
            if card["list"] != trello.REVIEW:
                board.move(card, trello.REVIEW)

        slots = []
        for k, task in enumerate(tasks):
            slot = character_artist.next_slot(slots)
            slots.append(slot)
            set_status({agent: {"status": "working"}, "critic": {"status": "working"}})
            result = work_task(run, card, maker, task, slot, int(run.id[-4:]) * 100 + k * 1000, to_review)
            results.append(result)
            run.event(agent, f"{task['id']} done: {result['name']} ({result['skin']})")

        board.move(card, trello.PLAYTEST)
        run.state["status"] = "waiting on David"
        run.save()
        summary = technical_writer.summarize(run, card, results)
        technical_writer.compact_memory(card, summary)
        board.comment(card, summary + "\n\nWaiting on David: approve or reject each one on the dashboard's Characters tab.")
        done = "; ".join(f"{r['name']} ({r['skin']})" for r in results)
        set_status({"orchestrator": {"status": "idle", "last_output": f"Run {run.id}: leased {card['name']}."},
                    agent: {"status": "waiting", "cheeks": 2, "units_add": len(results), "last_output": f"Run {run.id}: {done}."},
                    "critic": {"status": "idle", "last_output": f"Run {run.id}: reviewed {len(results)} characters."},
                    "technical-writer": {"status": "idle", "last_output": f"Run {run.id}: {summary[:200]}"}})
        print(f"\nDone. {summary}\nRun folder: {run.dir}")
        return 0
    except (CrewStop, MalformedOutput) as e:
        run.state["status"] = f"stopped: {e}"
        run.event("orchestrator", f"stopped: {e}")
        if card_moved:
            reset_card(board, card, run, e)
        set_status({"orchestrator": {"status": "stopped", "last_output": f"Run {run.id} stopped: {str(e)[:200]}"},
                    agent: {"status": "stopped", "cheeks": 0, "last_output": f"Run {run.id} stopped: {str(e)[:200]}"}, "critic": {"status": "idle"}})
        return 1
    except Exception:
        (run.dir / "crash.txt").write_text(traceback.format_exc(), encoding="utf-8")
        run.state["status"] = "crashed"
        run.save()
        raise
    finally:
        run.state["pixellab"] = pixellab.spent()
        run.event("orchestrator", f"PixelLab this run: {pixellab.spent()}")
        (run.dir / "tokens.json").write_text(json.dumps(common.usage.tokens, indent=2), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
