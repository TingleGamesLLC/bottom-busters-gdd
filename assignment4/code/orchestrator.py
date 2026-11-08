"""Orchestrator: runs one crew run against the Bottom Busters tasks in Paperclip, by priority. This is the file you start.

    python orchestrator.py            one run; skipped if the game is running
    python orchestrator.py --now      one run even if the game is running
    python orchestrator.py --dry      says which card a run would take, and does nothing else

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
import time
import traceback
from pathlib import Path

import bridge
import character_artist
import common
import critic
import level_architect
import paperclip_board as trello
import pixellab
import roast_writer
import technical_writer
import wardrobe_stylist
from common import CrewStop, MalformedOutput, NeedsDavid, Run, cheeks_for

# DAVID, 2026-11-03: characters come in sets of ten, one set at a time. The first set's 2 were the test, its next run makes
# the other 8, and every set after that is 10 in one run. A card's title says how many ("the other 8 characters").
SET_SIZE = 10


def how_many(card, davids_note, named=None):
    """A redo card is one character. A card naming a set makes what that set still needs, so a run that stopped partway
    picks up where it left off. Otherwise the number in the card's title, or a whole set."""
    if davids_note:
        return 1
    if named:
        return SET_SIZE - character_artist.made_in_set(named)
    found = re.search(r"(\d+) characters", card["name"])
    return int(found.group(1)) if found else SET_SIZE

# What the board's card prefixes mean. A prefix with no runner is work this crew doesn't do yet.
# A maker with "design" and "build" is made in two steps: its design, written from its part of the GDD, goes through the
# Critic's GDD check first, and only a design that passes is built (Assignment #4).
MAKERS = {
    "Character Artist": {"id": "character-artist", "make": character_artist.make, "check": bridge.check_character,
                         "design": character_artist.design, "build": character_artist.build,
                         "for_review": character_artist.for_review,
                         "publish": character_artist.publish, "facts": bridge.facts,
                         "review": lambda folder, concept, facts: critic.review(folder, concept, facts), "count": None,
                         "slots": True, "pixellab": True},
    # C:\cluster\LEVEL_ARCHITECT_DESIGN.md. Its Critic answer is only a note (BACKGROUNDS_METHOD.md rule 9).
    "Level Architect": {"id": "level-architect", "make": level_architect.make, "check": bridge.check_background,
                        "design": level_architect.design, "build": level_architect.build,
                        "for_review": level_architect.for_review,
                        "publish": level_architect.publish, "facts": bridge.background_facts,
                        "review": lambda folder, concept, facts: critic.review_background(folder, facts),
                        "count": level_architect.how_many, "slots": False, "pixellab": False},
    # C:\cluster\ROAST_WRITER_DESIGN.md. A whole batch of lines at once, with its own checks and pick instead of the
    # Orchestrator's plan and the Critic.
    "Roast Writer": {"id": "roast-writer", "batch": lambda board, card, run: run_roasts(board, card, run), "pixellab": False},
    # C:\cluster\WARDROBE_STYLIST_DESIGN.md. Each item goes through the usual steps (recipe, Bridge, Critic); its own run
    # keeps its card in the queue between batches. The Critic's answer is only a note.
    "Wardrobe Stylist": {"id": "wardrobe-stylist", "batch": lambda board, card, run: run_wardrobe(board, card, run),
                         "make": wardrobe_stylist.make, "check": bridge.check_wardrobe_item, "publish": wardrobe_stylist.publish,
                         "design": wardrobe_stylist.design, "build": wardrobe_stylist.build,
                         "for_review": wardrobe_stylist.for_review,
                         "facts": bridge.wardrobe_facts, "review": lambda folder, concept, facts: critic.review_wardrobe(folder, concept, facts),
                         "result": wardrobe_stylist.result, "slots": False, "pixellab": False},
}
NOT_MAKER_AGENTS = ("orchestrator", "builder", "foreman", "bridge", "critic", "technical-writer")

PIPELINE = {
    "nodes": [("D", "Studio Director (David)<br/>plays every build, says commit", "person"),
              ("T", "Paperclip<br/>tasks, agents and costs, on the dev PC", "store"),
              ("O", "Orchestrator<br/>qwen3:30b on the cluster", "round"),
              ("P", "Bottom Busters GDD<br/>Section 21, Content guide", "store"),
              ("A", "Maker: design<br/>Character Artist, Level Architect, Wardrobe Stylist<br/>qwen3:30b on the cluster", "round"),
              ("R", "Roast Writer<br/>qwen3:30b on the cluster: write, then pick", "round"),
              ("K", "Critic: GDD check<br/>qwen3:30b on the cluster", "round"),
              ("F", "Maker: build<br/>PixelLab and the art tools, ComfyUI, draw_wearables.py", "box"),
              ("B", "Bridge<br/>a script, not AI: checks the files", "box"),
              ("C", "Critic: picture review<br/>qwen2.5vl:7b on the cluster", "round"),
              ("W", "Technical Writer<br/>qwen3:30b on the cluster", "round"),
              ("S", "C:\\cluster\\submissions<br/>work waiting for approval", "store"),
              ("H", "Dashboard<br/>Crew and Characters tabs", "box"),
              ("G", "Bottom Busters<br/>Unity project", "store")],
    "edges": [("T", "O", "next task by priority"), ("O", "T", "moves the task, one task per agent, costs"),
              ("O", "A", "task brief (JSON)"), ("P", "A", "the opening and the maker's own part, read before it writes"),
              ("A", "K", "design (JSON)"), ("P", "K", "the same part, to check against"),
              ("K", "A", "send back with the GDD rule broken, costs a cheek"), ("K", "F", "passes the GDD check"),
              ("O", "R", "batch brief"), ("P", "R", "the opening and Section 21.2, read before it writes"),
              ("R", "K", "lines that passed the Bridge's line checks"), ("K", "R", "send back with the GDD rule broken"),
              ("R", "S", "the best line for each event"),
              ("F", "S", "art files and previews"),
              ("S", "B", "submission"), ("B", "A", "fix prompt if malformed"), ("B", "C", "passes the format check"),
              ("C", "O", "verdict (JSON)"), ("O", "S", "the Critic's note, beside the work"), ("O", "W", "run record"), ("W", "T", "summary comment"),
              ("O", "H", "status, cheeks, tokens"), ("S", "H", "shown for approval"), ("H", "D", "Approve or Reject with a note"),
              ("D", "S", "decision.json"), ("D", "G", "tests, says commit")],
    "classes": {"cluster": ["O", "A", "R", "K", "C", "W"], "script": ["F", "B"], "human": ["D"], "gdd": ["P"]},
    "styles": {"cluster": "fill:#CFE8F7,stroke:#1F2A44", "script": "fill:#FBFBF8,stroke:#1F2A44", "human": "fill:#F3D9A4,stroke:#1F2A44",
               "gdd": "fill:#D8F0D2,stroke:#1F2A44"},
}

PLAN_SYSTEM = """You are the Orchestrator of a game development agent crew. You split a Trello card into small tasks for one specialist.
Answer with only one JSON object with these fields:
"objective": the card's goal in one sentence
"tasks": a list of objects, each with one field "brief": what this one task must produce, in one sentence. Each brief asks for something clearly different from the others."""


def game_running():
    out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True).stdout.lower()
    return any(name in out for name in ("bbust.exe", "bottom busters", "bottombusters"))


def pick_card(board, run, only=None):
    """The first card in priority order that's assigned to one of the makers, or to the one maker named. Nothing is reordered."""
    makers = {m["id"]: m for m in MAKERS.values() if only is None or m["id"] == only}
    for card in board.cards(trello.BACKLOG):
        if card.get("agent") in makers:
            return card, makers[card["agent"]]
        if card.get("agent") and card["agent"] not in NOT_MAKER_AGENTS:
            run.event("orchestrator", f"no runner yet for {card['agent']}: {card['name']}")
    return None, None


def plan(card, batch):
    memory = common.MEMORY.read_text(encoding="utf-8") if common.MEMORY.exists() else "(no earlier runs)"
    messages = [{"role": "system", "content": PLAN_SYSTEM},
                {"role": "user", "content": f"Card: {card['name']}\nDescription: {card['desc']}\nSplit it into exactly {batch} tasks.\n\n"
                                            f"Notes from earlier runs:\n{memory}"}]
    d = common.ask_json("orchestrator", messages, ["objective", "tasks"], max_tokens=max(800, 150 * batch))
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


def wait_for_david(board, card, run, question, results):
    """A question only David can answer. It goes to him once as an issue that blocks the card, so no run picks the card up
    again until he closes the question. The Foreman then puts the card back in the queue, and the next run moves on."""
    made = f" {len(results)} made before the question are waiting on the Characters tab." if results else ""
    asked = board.ask_david(f"[Crew] {str(question)[:150]}",
                            f"{question}\n\nCard: {card['name']}\nRun: {run.id}.{made}\nClose this issue once it's answered, "
                            "and the card goes back in the queue.", card["id"])
    board.update(card["id"], {"status": "blocked", "blockedByIssueIds": [asked],
                              "comment": f"Crew run {run.id} needs David: {question}"})
    run.state["status"] = f"waiting on David: {question}"
    run.event("orchestrator", f"asked David, and the card waits: {question}")


def reset_card(board, card, run, why):
    """A stopped run's card goes back where the next run can pick it up, saying why."""
    board.move(card, trello.BACKLOG)
    board.comment(card, f"Crew run {run.id} stopped: {why}")


def work_task(run, board, card, maker, task, slot, seed, to_review, notes=None):
    """One task through maker, Bridge and Critic. A Bridge send-back pops the maker's cheek, and both popped stops the task. The
    Critic's verdict goes with the work to David. In Paperclip the task is an issue under the card, assigned to the maker, and
    the Critic's review is one assigned to the Critic."""
    agent, cheeks = maker["id"], cheeks_for(maker["id"])
    task_issue = board.open_task(card, agent, f"{task['id']}: {task['brief'][:100]}", task["brief"])
    try:
        return _work_task(run, board, card, maker, task, slot, seed, to_review, agent, cheeks, notes, task_issue)
    except Exception as e:
        try:
            board.close_task(task_issue, "cancelled", f"Stopped in run {run.id}: {str(e)[:500]}")
        except RuntimeError as problem:
            run.event("orchestrator", f"task not closed in Paperclip: {problem}")
        raise


def gdd_check(run, board, card, maker, task, design):
    """The Critic checks a design against the maker's part of the GDD, before anything is built from it. The verdict goes back
    to the Orchestrator as a handoff, and into Paperclip as the Critic's task."""
    agent = maker["id"]
    work = maker["for_review"](design)
    run.send(agent, "critic", "design", {"task": task["id"], "design": work})
    issue = board.open_task(card, "critic", f"GDD check: {task['id']}",
                            f"Check {agent}'s design for {task['id']} against its part of the GDD's Content guide.")
    verdict = critic.check_gdd(agent, work)
    run.send("critic", "orchestrator", "gdd_check", {"task": task["id"], **verdict})
    problems = "; ".join(verdict["problems"])
    run.event("critic", f"GDD check on {task['id']} ({verdict['gdd']}): {verdict['verdict']}" + (f": {problems}" if problems else ""))
    for d in verdict.get("dropped") or []:
        f = d["finding"] if isinstance(d.get("finding"), dict) else {}
        run.event("critic", f"GDD check on {task['id']}: a finding was dropped, {d['dropped']}: {str(f.get('why') or f)[:300]}")
    board.close_task(issue, "done", f"{verdict['verdict']} against {verdict['gdd']}." + (f" Problems: {problems}" if problems else ""))
    return verdict


def _work_task(run, board, card, maker, task, slot, seed, to_review, agent, cheeks, notes, task_issue):
    while True:
        run.send("orchestrator", agent, "task", {**task, "slot": slot, "notes": notes})
        gdd_verdict = None
        try:
            if "design" in maker:
                design = maker["design"](task, slot, taken_looks(), notes, seed)
                gdd_verdict = gdd_check(run, board, card, maker, task, design)
                if gdd_verdict["verdict"] != "pass":
                    why = "; ".join(gdd_verdict["problems"]) or "it breaks the GDD"
                    notes = f"The Critic checked it against the GDD and sent it back: {why}. {gdd_verdict['note_for_maker']}".strip()
                    run.send("orchestrator", agent, "gdd_send_back", {"task": task["id"], "notes": notes})
                    board.task_comment(task_issue, f"The Critic sent it back against the GDD: {why}")
                    if cheeks.pop() <= 0:
                        raise CrewStop(f"{agent} lost both cheeks on {task['id']}: the Critic sent it back against the GDD: {why[:300]}")
                    seed += 10
                    continue
                folder, concept = maker["build"](task, slot, design, seed)
            else:
                folder, concept = maker["make"](task, slot, taken_looks(), notes, seed)
        except MalformedOutput as e:
            problem = str(e)
            run.event(agent, f"sent back: {problem}")
            board.task_comment(task_issue, f"Sent back: {problem}")
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
            board.task_comment(task_issue, f"The Bridge sent it back: {notes}")
            if cheeks.pop() <= 0:
                keep_failed(run, folder)
                raise CrewStop(f"{agent} lost both cheeks on {task['id']}: {notes[:300]}")
            seed += 10
            continue
        facts = maker.get("facts", bridge.facts)(folder)
        run.send("bridge", "critic", "passed", {"task": task["id"], "folder": str(folder), "facts": facts})

        review = board.open_task(card, "critic", f"Review {concept.get('name') or task['id']}",
                                 f"The line-up at game size for {task['id']}: {task['brief']}")
        verdict = maker["review"](folder, concept, facts) if "review" in maker else critic.review(folder, concept, facts)
        run.send("critic", "orchestrator", "verdict", {"task": task["id"], **verdict})
        run.event("critic", f"{task['id']} {verdict['verdict']}: {verdict.get('what_i_see')}")
        problems = "; ".join(verdict.get("problems") or [])
        board.close_task(review, "done", f"{verdict['verdict']}. {verdict.get('what_i_see') or ''}" + (f" Problems: {problems}" if problems else ""))
        # The Critic hasn't been tested on art with known answers, so its fail is a note beside the character for David, not a send-back.
        manifest = folder / "manifest.json"
        m = json.loads(manifest.read_text(encoding="utf-8"))
        m.update(card=card["id"], card_name=card["name"], run=run.id, bridge=facts, critic=verdict)
        if gdd_verdict:
            m["gdd_check"] = gdd_verdict
        if verdict["verdict"] != "pass":
            note = verdict.get("note_for_artist") or "; ".join(verdict.get("problems") or []) or "the Critic failed it"
            m["name"] = f"{m['name']}. Critic's note: {note}"
        manifest.write_text(json.dumps(m, indent=2), encoding="utf-8")
        folder = maker["publish"](folder)
        cheeks.refill()
        board.close_task(task_issue, "done", f"Made {concept.get('name') or concept.get('theme')} ({m.get('skin', folder.name)}). "
                                             "Waiting on David on the dashboard's Characters tab.")
        if maker.get("result"):   # a maker that says its own run-record line
            return maker["result"](task, folder, concept, m, verdict, facts)
        if "theme" in concept:   # a background
            return {"task": task["id"], "name": concept["theme"], "skin": folder.name, "look": concept.get("style"),
                    "skin_tone": concept.get("ground_type"), "critic_saw": verdict.get("answers"), "folder": folder.name,
                    "difference_from_roster": facts.get("difference")}
        return {"task": task["id"], "name": concept.get("name"), "skin": m["skin"], "look": f"{concept.get('hair')}, {concept.get('hair_color')}",
                "skin_tone": concept.get("skin_tone"), "critic_saw": verdict.get("what_i_see"), "folder": folder.name, "difference_from_roster": facts["difference_from_nearest"]}


def run_roasts(board, card, run):
    """One Roast Writer batch (C:\\cluster\\ROAST_WRITER_DESIGN.md). The card holds all 250 lines, so it goes back in the
    queue after each batch instead of to Your Playtest, and it waits there until David has decided the last card's lines."""
    agent = "roast-writer"
    run.state["card"] = card["name"]
    roast_writer.store_approved()
    s = roast_writer.state()
    if s["approved"] >= roast_writer.TOTAL:
        # Forward slashes: Paperclip stores "\r" in a Windows path as a line break.
        board.comment(card, f"All {roast_writer.TOTAL} roast lines are approved, in {roast_writer.APPROVED.as_posix()}. "
                            "Closed by the Orchestrator.")
        board.move(card, trello.DONE)
        run.state["status"] = "nothing to do: all roast lines approved"
        run.event(agent, f"all {roast_writer.TOTAL} lines approved; the card is done")
        return 0
    if s["waiting"]:
        run.state["status"] = "nothing to do: waiting on David"
        run.event(agent, f"waiting on David's calls on {s['waiting']} lines before the next batch")
        return 0

    count, card_moved, task = s["next"], False, None
    try:
        set_status({agent: {"status": "working", "cheeks": 2}})
        board.move(card, trello.LEASED)
        card_moved = True
        task = board.open_task(card, agent, f"{count} new roast lines",
                               f"Write, check and pick {count} new roast lines. {s['approved']} of {roast_writer.TOTAL} approved so far.")
        folders = roast_writer.make_batch(count, card, run.id, lambda text: run.event(agent, text), review=critic.check_gdd_lines)
        board.close_task(task, "done", f"Put up {len(folders)} lines for David. They reach his Paperclip inbox within a minute.")
        task = None
        board.move(card, trello.BACKLOG)
        board.comment(card, f"Crew run {run.id}: {len(folders)} new roast lines are on their way to your Paperclip inbox. "
                            f"{s['approved']} of {roast_writer.TOTAL} approved so far.")
        run.state["status"] = "waiting on David"
        run.save()
        set_status({agent: {"status": "waiting", "cheeks": 2, "units_add": len(folders),
                            "last_output": f"Run {run.id}: {len(folders)} roast lines for David."}})
        print(f"\nDone. {len(folders)} roast lines for David.\nRun folder: {run.dir}")
        return 0
    except (CrewStop, MalformedOutput) as e:
        run.state["status"] = f"stopped: {e}"
        run.event("orchestrator", f"stopped: {e}")
        if task is not None:
            board.close_task(task, "cancelled", f"Stopped in run {run.id}: {str(e)[:500]}")
        if card_moved:
            reset_card(board, card, run, e)
        set_status({agent: {"status": "stopped", "cheeks": 0, "last_output": f"Run {run.id} stopped: {str(e)[:200]}"}})
        return 1
    except Exception:
        (run.dir / "crash.txt").write_text(traceback.format_exc(), encoding="utf-8")
        run.state["status"] = "crashed"
        run.save()
        raise
    finally:
        (run.dir / "tokens.json").write_text(json.dumps(common.usage.tokens, indent=2), encoding="utf-8")
        report_costs(board, run, card)


def run_wardrobe(board, card, run):
    """One Wardrobe Stylist run (C:\\cluster\\WARDROBE_STYLIST_DESIGN.md). A redo card goes first: one item, the same idea,
    David's note as its first instruction, and it waits at Your Playtest. Otherwise the next batch from approved ideas, each
    item through the usual steps; the card holds all 40, so it goes back in the queue and waits there until David has
    decided the last batch."""
    agent = "wardrobe-stylist"
    maker = MAKERS["Wardrobe Stylist"]
    wardrobe_stylist.store_approved()
    redo = next((c for c in [card] + board.cards(trello.BACKLOG)
                 if c.get("agent") == agent and "David's note:" in (c.get("desc") or "")), None)
    if redo:
        card = redo
        jobs = [wardrobe_stylist.redo_task(card)]
    else:
        s = wardrobe_stylist.state()
        if s["approved"] >= wardrobe_stylist.TOTAL:
            board.comment(card, f"All {wardrobe_stylist.TOTAL} hats and shades are approved, in "
                                f"{wardrobe_stylist.APPROVED.as_posix()}. Closed by the Orchestrator.")
            board.move(card, trello.DONE)
            run.state["status"] = "nothing to do: all hats and shades approved"
            run.event(agent, f"all {wardrobe_stylist.TOTAL} items approved; the card is done")
            return 0
        if s["waiting"] or not s["next"]:
            why = (f"waiting on David's calls on {s['waiting']} items" if s["waiting"]
                   else "no approved idea is waiting to be drawn")
            run.state["status"] = f"nothing to do: {why}"
            run.event(agent, why)
            return 0
        jobs = wardrobe_stylist.tasks(s["next"])
    run.state["card"], run.state["tasks"] = card["name"], jobs
    results, card_moved = [], False
    try:
        set_status({agent: {"status": "working", "cheeks": 2}})
        board.move(card, trello.LEASED)
        card_moved = True

        def to_review():
            if card["list"] != trello.REVIEW:
                board.move(card, trello.REVIEW)

        for k, task in enumerate(jobs):
            set_status({agent: {"status": "working"}, "critic": {"status": "working"}})
            note = f"David rejected the last one: {task['note']}" if task.get("note") else None
            results.append(work_task(run, board, card, maker, task, None, int(run.id[9:15]) * 100 + k * 1000, to_review, note))
            run.event(agent, f"{task['id']} done: {results[-1]['name']} ({results[-1]['skin']})")
        board.move(card, trello.PLAYTEST if redo else trello.BACKLOG)
        run.state["status"] = "waiting on David"
        run.save()
        summary = technical_writer.summarize(run, card, results)
        technical_writer.compact_memory(card, summary)
        board.comment(card, summary + "\n\nWaiting on David: approve or reject each one on the card in his Paperclip inbox.")
        set_status({agent: {"status": "waiting", "cheeks": 2, "units_add": len(results),
                            "last_output": f"Run {run.id}: " + "; ".join(r["name"] for r in results) + "."},
                    "critic": {"status": "idle"}})
        print(f"\nDone. {summary}\nRun folder: {run.dir}")
        return 0
    except (CrewStop, MalformedOutput) as e:
        run.state["status"] = f"stopped: {e}"
        run.event("orchestrator", f"stopped: {e}")
        if card_moved:
            reset_card(board, card, run, e)
        set_status({agent: {"status": "stopped", "cheeks": 0, "last_output": f"Run {run.id} stopped: {str(e)[:200]}"},
                    "critic": {"status": "idle"}})
        return 1
    except Exception:
        (run.dir / "crash.txt").write_text(traceback.format_exc(), encoding="utf-8")
        run.state["status"] = "crashed"
        run.save()
        raise
    finally:
        (run.dir / "tokens.json").write_text(json.dumps(common.usage.tokens, indent=2), encoding="utf-8")
        report_costs(board, run, card)


def upkeep(board):
    """Crew-wide work that belongs to no maker: the diagram, and closing cards whose work David has all decided. It runs
    once, before any maker starts, so no maker's run carries it and no two runs race on it (DAVID, 2026-11-04: "0
    dependancies should exist in the agent pipeline")."""
    class Log:
        def event(self, agent, text):
            print(f"[{time.strftime('%H:%M:%S')}] {agent}: {text}", flush=True)
    # Each step on its own: a failure here is reported and the makers start anyway. The Foreman closes cards hourly too.
    for step in (lambda: technical_writer.write_diagram(PIPELINE), lambda: technical_writer.close_finished(board, Log())):
        try:
            step()
        except Exception as e:
            print(f"crew upkeep step failed, and the makers start anyway: {type(e).__name__}: {e}", flush=True)


def run_alongside():
    """DAVID, 2026-11-04: the agents run alongside each other. One child run per maker, each on its own top card, at the
    same time; the worst exit code is this run's. --child tells a maker's run that the upkeep is already done."""
    args = [a for a in sys.argv[1:] if a == "--now"]
    children = [subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--maker", m["id"], "--child", *args])
                for m in MAKERS.values()]
    return max(c.wait() for c in children)


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--now" not in sys.argv and game_running():
        print("skipped: the game is running, and David gets the PC while he plays")
        return 0

    only = sys.argv[sys.argv.index("--maker") + 1] if "--maker" in sys.argv else None
    board = trello.open_board()
    if "--dry" in sys.argv:
        # Says which card each maker would take, and does nothing else: no run folder, no model, no PixelLab, no dashboard.
        class Quiet:
            def event(self, agent, text):
                pass
        for m in MAKERS.values():
            if only in (None, m["id"]):
                card, maker = pick_card(board, Quiet(), m["id"])
                print(f"dry run: would take {card['url']} {card['name']} for {maker['id']}" if card else f"dry run: nothing for {m['id']}")
        return 0
    if only is None:
        upkeep(board)
        return run_alongside()
    if "--child" not in sys.argv:   # one maker started by hand
        upkeep(board)
    run = Run(time.strftime("%Y%m%d-%H%M%S") + f"-{only}")
    if only == "level-architect":   # its own approved backgrounds, nobody else's
        level_architect.store_approved()
    card, maker = pick_card(board, run, only)
    if not card:
        run.state["status"] = "nothing to do"
        run.event("orchestrator", "no card on the board that this crew can work")
        return 0
    if maker.get("batch"):
        return maker["batch"](board, card, run)

    agent = maker["id"]
    run.state["card"] = card["name"]
    results, card_moved = [], False
    try:
        if maker.get("pixellab", True):
            run.event("orchestrator", f"PixelLab balance before: {pixellab.balance()}")
            pixellab.check_room()   # before any tokens go on a plan the art can't be paid for
        set_status({"orchestrator": {"status": "working"}, agent: {"status": "working", "cheeks": 2}})
        # A redo card carries David's note: one character, and his note is the maker's first instruction.
        found = re.search(r"^David's note: (.+)$", card["desc"], re.M)
        davids_note = found.group(1).strip() if found else None
        # The set named on the card, so a run never fills one set's places with another's characters.
        named = next((s["name"] for s in character_artist.SETS if f"({s['name']})" in card["name"] + card["desc"]), None)
        count = 1 if davids_note and maker.get("count") else maker["count"]() if maker.get("count") else how_many(card, davids_note, named)
        if count <= 0:
            raise NeedsDavid(f"the {named} set already has its {SET_SIZE} characters, so {card['url']} has nothing left to make")
        objective, tasks = plan(card, count)
        tasks = [dict(t, set=named) for t in tasks] if named else tasks
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
            slot = character_artist.next_slot(slots) if maker.get("slots", True) else None
            slots.append(slot)
            set_status({agent: {"status": "working"}, "critic": {"status": "working"}})
            result = work_task(run, board, card, maker, task, slot, int(run.id[9:15]) * 100 + k * 1000, to_review,
                               f"David rejected the last one: {davids_note}" if davids_note else None)
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
    except NeedsDavid as e:
        wait_for_david(board, card, run, e, results)
        set_status({"orchestrator": {"status": "idle", "last_output": f"Run {run.id}: asked David: {str(e)[:200]}"},
                    agent: {"status": "waiting", "cheeks": 2, "units_add": len(results)}, "critic": {"status": "idle"}})
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
        report_costs(board, run, card)


def report_costs(board, run, card):
    """Each agent's tokens this run, and PixelLab's charge, on Paperclip's Costs page. The local cluster costs nothing."""
    try:
        for (agent, model), (tokens_in, tokens_out) in common.usage.by_model.items():
            board.report_cost(agent, "mindrouter", model, tokens_in, tokens_out, 0, "fixed", card, f"{run.id}:{agent}:{model}")
        # PixelLab bills subscription generations, or dollars once credits are bought. Generations show as the count.
        spent = pixellab.spent()
        if spent.get("generations"):
            board.report_cost("character-artist", "pixellab", "inpaint-pro-flash generations", 0, spent["generations"], 0,
                              "subscription_included", card, f"{run.id}:pixellab-generations")
        if spent.get("usd"):
            board.report_cost("character-artist", "pixellab", "inpaint-pro-flash", 0, 0, spent["usd"] * 100, "credits", card,
                              f"{run.id}:pixellab-usd")
    except RuntimeError as e:
        run.event("orchestrator", f"costs not sent to Paperclip: {e}")


if __name__ == "__main__":
    sys.exit(main())
