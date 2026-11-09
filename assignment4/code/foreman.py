"""Foreman: keeps the crew moving. Each check looks for stalled tasks, failed runs and false blockers, fixes what plain rules
can fix, and puts the rest in front of David as a high-priority Paperclip issue assigned to him, once per problem.

DAVID, 2026-11-03: "need a foreman agent who keeps the crew moving, hourly checks for stalled tickets, failed runs, and false
blockers. fixes what it can, escalated the reset. no feature work."

So it never makes content, calls a model, spends PixelLab credits, touches the game project or starts a crew run. Plain code,
no tokens.

    python foreman.py            one check
The "BBUST Foreman" scheduled task runs it every hour with pythonw, so no window opens. Paperclip heartbeats stay off.

What it fixes:
  - A card the crew left in progress or in review with no crew run alive goes back to the queue.
  - A task the crew opened under a card, still open with no crew run alive, is closed as cancelled.
  - A blocked issue whose blocking issues are all finished goes back to todo.
  - A card waiting on David whose work he has all approved is closed, by the Technical Writer's own rule.
  - Paperclip not answering: it starts Paperclip.
  - Pre-flight: an issue it raised about MindRouter, Node A, PixelLab or the BBUST project is closed once that clears.
What it raises with David:
  - A crew run that stopped, crashed, or died without finishing, with its reason.
  - A crew run that's alive but has written nothing for an hour.
  - Pre-flight: MindRouter or Node A not answering, PixelLab without room for a call, or the BBUST project missing.
  - An approval that came with a note, and a rejection with no note.
What it sends back: a rejection with a note becomes a redo card for the maker.
"""
import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import common
import paperclip_board as pb
import pixellab
import roast_writer
import technical_writer
import wardrobe_stylist
from orchestrator import MAKERS

STATE = common.HERE / "foreman_state.json"
LOG = common.HERE / "foreman.log"
START = common.HERE / "start_paperclip.cmd"
QUIET_MINUTES = 60
FINAL = ("waiting on David", "nothing to do")
BBUST = Path(r"C:\bbust\BBUST\Assets")
ART_TOOLS = Path(r"C:\bbust\CoverArt\tools")


def mindrouter_answers():
    """Any HTTP answer counts: a 401 or 404 still means MindRouter is up."""
    try:
        urllib.request.urlopen(common.ROUTER + "/v1/models", timeout=10).close()
        return True
    except urllib.error.HTTPError:
        return True
    except OSError:
        return False


def node_a_answers():
    try:
        socket.create_connection((common.NODE_A, 22), timeout=8).close()
        return True
    except OSError:
        return False


def pixellab_room():
    """None when a call fits, else what's wrong. Reading the balance is free."""
    try:
        left = pixellab.balance()
    except common.CrewStop as e:
        return str(e)
    if left["generations"] < pixellab.GENERATIONS_PER_CALL and left["usd"] <= 0:
        return (f"PixelLab has {left['generations']:g} generations and ${left['usd']:.2f} left, and a call takes "
                f"{pixellab.GENERATIONS_PER_CALL}: the Character Artist can't paint until there's a plan or credits")
    return None


# name: a check returning None when fine, or what's wrong. The Foreman can't fix any of these, so they go to David.
PREFLIGHT = {
    "mindrouter": lambda: None if mindrouter_answers() else f"MindRouter at {common.ROUTER} isn't answering: no agent can think",
    "node-a": lambda: None if node_a_answers() else f"Node A ({common.NODE_A}) isn't answering on SSH: the dashboard can't get crew status",
    "pixellab": pixellab_room,
    "bbust": lambda: None if BBUST.exists() and ART_TOOLS.exists() else f"{BBUST} or {ART_TOOLS} is missing: the Character Artist can't make files",
    "nas-backup": lambda: __import__("backup_paperclip").behind(),
}


def crew_running():
    """True while a crew run's process is alive, from any window or the scheduled task."""
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | ForEach-Object { $_.CommandLine }"],
                         capture_output=True, text=True, timeout=60, creationflags=subprocess.CREATE_NO_WINDOW).stdout
    return "orchestrator.py" in out


def paperclip_up():
    try:
        with urllib.request.urlopen(pb.URL + "/api/health", timeout=10) as r:
            return r.status == 200
    except OSError:
        return False


def start_command():
    """start's first quoted argument is the window title. Unquoted, Windows takes "Paperclip" as the program to run and
    hangs on an error (2026-11-03), so this is one string with the quotes kept."""
    return f'cmd /c start "Paperclip" /min "{START}"'


def make_sure_paperclip_runs(log):
    if paperclip_up():
        return True
    log("Paperclip wasn't answering; starting it with start_paperclip.cmd")
    subprocess.Popen(start_command(), cwd=str(common.HERE), creationflags=subprocess.CREATE_NO_WINDOW)
    for _ in range(24):
        time.sleep(5)
        if paperclip_up():
            log("Paperclip is up")
            return True
    return False


class Check:
    """One pass. Fixes are commented on the issue they touch. Escalations are remembered so each is raised once."""

    def __init__(self, board, state, running):
        self.board, self.state, self.running = board, state, running
        self.state.setdefault("escalated", {})
        self.fixed, self.raised = [], []
        ids = board.ids["agents"]
        self.crew_agents = {ids[m["id"]] for m in MAKERS.values()} | {ids["critic"]}

    def fix(self, issue_id, what, label):
        self.board.comment({"id": issue_id}, f"Foreman: {what}")
        self.fixed.append(f"{label}: {what}")

    def escalate(self, key, title, text, parent=None):
        if key in self.state["escalated"]:
            return
        self.state["escalated"][key] = self.board.ask_david(f"[Foreman] {title}", text, parent)
        self.raised.append(title)

    def redo(self, card, folder, name, note):
        """A rejection with a note goes back to the maker as a card of its own: one character, with David's note as its first
        instruction. The rejected submission records the redo, so its old card can close."""
        key = f"redo:{folder.name}"
        if key in self.state["escalated"]:
            return
        manifest_path = folder / "manifest.json"
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
        maker = m.get("agent") or "Character Artist"
        redo_id = self.board.new_card(f"[{maker}] Redo {name}: {note[:80]}",
                                      f"David rejected {name} ({folder.name}) from {card['name']}.\nDavid's note: {note}",
                                      pb.PREFIX_AGENT.get(maker, "character-artist"))
        self.state["escalated"][key] = redo_id
        m["redone_by"] = redo_id
        manifest_path.write_text(json.dumps(m, indent=2), encoding="utf-8")
        self.fixed.append(f"{name}: rejected with a note, so it's back with the maker as a redo card")

    def stalled_cards(self):
        """The crew moves only its makers' cards. One sitting in progress or in review with no run alive was left by a run
        that ended badly."""
        if self.running:
            return
        for list_name in (pb.LEASED, pb.REVIEW):
            for card in self.board.cards(list_name):
                if card.get("agent") in {m["id"] for m in MAKERS.values()}:
                    self.board.move(card, pb.BACKLOG)
                    self.fix(card["id"], f"no crew run is working on this, but it was left in {list_name}. "
                                         "It's back in the queue for the next run.", card["name"])

    def orphan_tasks(self):
        if self.running:
            return
        for row in self.board.issues("in_progress"):
            if row.get("parentId") and row.get("assigneeAgentId") in self.crew_agents:
                self.board.update(row["id"], {"status": "cancelled",
                                              "comment": "Foreman: the run that opened this task ended without closing it."})
                self.fixed.append(f"{row.get('identifier')}: closed a task its run left open")

    def failed_runs(self):
        seen = self.state.get("seen_runs")
        baseline = seen is None
        seen = set(seen or [])
        for folder in sorted(p for p in common.RUNS.iterdir() if (p / "run.json").exists()):
            if folder.name in seen:
                continue
            d = json.loads((folder / "run.json").read_text(encoding="utf-8"))
            status = d.get("status") or ""
            if status == "running" and self.running:
                quiet = (time.time() - max(p.stat().st_mtime for p in folder.rglob("*"))) / 60
                if quiet >= QUIET_MINUTES and not baseline:
                    self.escalate(f"stuck:{folder.name}", f"Crew run {folder.name} has written nothing for {int(quiet)} minutes",
                                  f"Card: {d.get('card')}\nRun folder: {folder}\nThe Foreman doesn't stop runs. "
                                  "End it by hand if it's hung; the next check puts its card back in the queue.")
                continue
            seen.add(folder.name)
            if baseline or status.startswith(FINAL):
                continue
            if status == "running":
                reason = "ended without finishing: no crew process is alive and its record still says running"
            elif status == "crashed":
                crash = folder / "crash.txt"
                tail = crash.read_text(encoding="utf-8").strip().splitlines()[-1] if crash.exists() else "no crash.txt"
                reason = f"crashed: {tail}"
            else:
                reason = status
            card = next((c for lst in (pb.BACKLOG, pb.LEASED, pb.REVIEW) for c in self.board.cards(lst) if c["name"] == d.get("card")), None)
            self.escalate(f"run:{folder.name}", f"Crew run {folder.name} {reason[:120]}",
                          f"Card: {d.get('card')}\nReason: {reason}\nRun folder: {folder}\n"
                          "Its card is back in the queue (the Orchestrator does that, or the Foreman if the run died).",
                          card["id"] if card else None)
        self.state["seen_runs"] = sorted(seen)
        if baseline:
            self.fixed.append(f"started watching runs; the {len(seen)} earlier runs aren't reported")

    def preflight(self):
        """What a crew run needs, checked before a run fails on it. A problem is raised once; when it clears, its issue is
        closed, so the same problem can be raised again if it comes back."""
        open_now = self.state.setdefault("preflight", {})
        for name, check in PREFLIGHT.items():
            problem = check()
            if problem and name not in open_now:
                open_now[name] = self.board.ask_david(f"[Foreman] {problem[:150]}", problem + "\nThe Foreman closes this once it clears.")
                self.raised.append(problem)
            elif not problem and name in open_now:
                self.board.update(open_now.pop(name), {"status": "done", "comment": "Foreman: this cleared on its own check."})
                self.fixed.append(f"{name}: cleared, so its issue is closed")
        for name in [n for n in open_now if n not in PREFLIGHT]:   # a check that was taken out (ComfyUI, 2026-11-07)
            self.board.update(open_now.pop(name), {"status": "done", "comment": "Foreman: this check isn't needed any more."})
            self.fixed.append(f"{name}: the check was taken out, so its issue is closed")

    def answered_questions(self):
        """Gap analysis X3: David answers the crew's question cards in Paperclip. An answer typed to a no-note rejection is
        his note, so the work goes back to the maker. Any other answer goes on the card. Either way the question closes,
        and the unblock step then frees the card."""
        by_question = {v: k for k, v in self.state["escalated"].items()}
        for q, answer in self.board.answered_questions():
            key, parent = by_question.get(q["id"], ""), q.get("parentId")
            card = self.board.issue(parent) if parent else None
            if key.startswith("reject:") and card and answer != pb.DONE_ANSWER:
                folder = next((p.parent for p in common.SUBMISSIONS.glob(f"*/{key[len('reject:'):]}/manifest.json")), None)
                if folder:
                    name = json.loads((folder / "manifest.json").read_text(encoding="utf-8")).get("name", folder.name).split(". ")[0]
                    self.redo({"id": parent, "name": card["title"]}, folder, name, answer)
            if card and card.get("status") not in ("done", "cancelled"):   # a comment would reopen a finished card
                self.board.comment({"id": parent}, f"David's answer to \"{q['title']}\": {answer}")
            self.board.update(q["id"], {"status": "done", "comment": f"Foreman: David answered on the question card: {answer}"})
            self.fixed.append(f"{q.get('identifier') or q['id']}: David answered, so it's closed")

    def false_blockers(self):
        for row in self.board.issues("blocked"):
            blockers = self.board.issue(row["id"]).get("blockedBy") or []
            if blockers and all(b.get("status") in ("done", "cancelled") for b in blockers):
                self.board.update(row["id"], {"status": "todo", "comment": "Foreman: everything blocking this is finished, so it's back to todo."})
                self.fixed.append(f"{row.get('identifier')}: unblocked")

        for card in self.board.cards(pb.PLAYTEST):
            names = {card["id"], card.get("trello_id")} - {None}
            # A rejected roast line never becomes a redo card: its note goes into the Roast Writer's next batch
            # (ROAST_WRITER_DESIGN.md section 9).
            folders = [p.parent for p in common.SUBMISSIONS.glob("*/*/manifest.json")
                       if json.loads(p.read_text(encoding="utf-8")).get("card") in names
                       and json.loads(p.read_text(encoding="utf-8")).get("kind") != roast_writer.KIND]
            decisions = [p / "decision.json" for p in folders]
            if not folders or not all(d.exists() for d in decisions):
                continue  # really waiting on David
            for folder, path in zip(folders, decisions):
                d = json.loads(path.read_text(encoding="utf-8"))
                name = json.loads((folder / "manifest.json").read_text(encoding="utf-8")).get("name", folder.name).split(". ")[0]
                note = (d.get("note") or "").strip()
                if d.get("decision") == "approve" and note:
                    self.escalate(f"note:{folder.name}", f"Your note on {name} needs a task",
                                  f"You approved {name} ({folder.name}) with this note: \"{note}\"\n"
                                  "The crew doesn't act on notes yet, so this issue holds it until the work is assigned.", card["id"])
                elif d.get("decision") == "reject" and note:
                    self.redo(card, folder, name, note)
                elif d.get("decision") == "reject":
                    self.escalate(f"reject:{folder.name}", f"You rejected {name} with no note",
                                  f"{name} ({folder.name}) was rejected with no note. What should change? Reject it again with "
                                  "a note and the Foreman sends it back to the maker.", card["id"])

        # A Wardrobe Stylist card stays in the queue between runs (WARDROBE_STYLIST_DESIGN.md section 8), so an item David
        # rejected with a note becomes its redo card here, not only at Your Playtest. self.redo makes each one once.
        for p in sorted((common.SUBMISSIONS / wardrobe_stylist.ITEMS).glob("*/manifest.json")):
            m = json.loads(p.read_text(encoding="utf-8"))
            d = json.loads(p.with_name("decision.json").read_text(encoding="utf-8")) if p.with_name("decision.json").exists() else {}
            note = (d.get("note") or "").strip()
            if m.get("kind") == wardrobe_stylist.KIND and d.get("decision") == "reject" and note and not m.get("redone_by"):
                self.redo({"id": m.get("card"), "name": m.get("card_name") or "the Wardrobe Stylist's card"}, p.parent,
                          m.get("name", p.parent.name), note)

        class Log:
            def event(_, agent, text):
                pass
        for name in technical_writer.close_finished(self.board, Log()):
            self.fixed.append(f"{name}: David approved all of its work, so it's closed")


LOCK = common.HERE / "foreman.lock"
LOCK_WAIT = 300   # seconds a check waits for the one before it to finish


def one_at_a_time(path, wait=LOCK_WAIT):
    """An open, locked file while this is the only Foreman check running, else None after waiting `wait` seconds. The hourly
    check and a decisions-only check started by the PC helper never touch the board or the state file at once."""
    import msvcrt
    f = open(path, "a+")
    for _ in range(max(1, wait // 5 + 1)):
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            return f
        except OSError:
            if wait:
                time.sleep(5)
    f.close()
    return None


def steps(check, decisions_only=False):
    """Gap analysis G14: right after David decides on the dashboard, the PC helper runs only the step that acts on it,
    instead of waiting up to an hour for the full check."""
    if decisions_only:
        return [check.false_blockers]
    return [check.preflight, check.stalled_cards, check.orphan_tasks, check.failed_runs, check.answered_questions, check.false_blockers]


def main():
    decisions_only = "--decisions" in sys.argv
    if sys.stdout:   # the scheduled task runs it windowless, with no stdout
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    lines = []

    def log(text):
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {text}"
        lines.append(line)
        print(line, flush=True)

    def write_log():
        with LOG.open("a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    held = one_at_a_time(LOCK)
    if held is None:
        log("another Foreman check was still running after five minutes, so this one didn't run")
        write_log()
        return 1
    try:
        if not make_sure_paperclip_runs(log):
            log("Paperclip still isn't answering after two minutes. Nothing else was checked.")
            return 1
        state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
        check = Check(pb.open_board(), state, crew_running())
        for step in steps(check, decisions_only):
            step()
        tmp = STATE.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
        tmp.replace(STATE)
        log(f"{'decisions check' if decisions_only else 'check'} done{' (a crew run is alive)' if check.running else ''}: "
            f"fixed {len(check.fixed)}, raised {len(check.raised)}")
        for f in check.fixed:
            log(f"  fixed: {f}")
        for r in check.raised:
            log(f"  raised: {r}")
        return 0
    finally:
        held.close()
        write_log()


if __name__ == "__main__":
    sys.exit(main())
