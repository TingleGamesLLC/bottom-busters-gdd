"""One-time setup: the Bottom Busters company and crew in Paperclip, and David's Trello cards copied over in his order.

    python paperclip_setup.py

Safe to run again: whatever paperclip.json already names is skipped. Trello itself is only read, never changed.
Every agent is made with heartbeats off (DAVID, 2026-11-03), so nothing here starts a run.
"""
import json
import sys

import board as trello
from paperclip_board import HEARTBEAT_OFF, call, load_ids, owner_of, prefix_of, save_ids

CREW = r"C:\cluster\crew"
# Paperclip's process adapter takes the program and its arguments separately; one string as the command fails its check.
PYTHON = r"C:\Users\david\AppData\Local\Programs\Python\Python313\python.exe"
INSIDE = ["-c", "print('This agent runs inside the Orchestrator run, not on its own.')"]

# key, name, role, reports to, what it does, arguments to python. Only the Orchestrator and the Foreman are programs of
# their own today. The Orchestrator's Run button in Paperclip is turned on after setup (timer off, on demand on).
AGENTS = [
    ("orchestrator", "Orchestrator", "ceo", None,
     "Takes the next task in priority order, splits it into parts for one maker, sends the work through the Bridge and the "
     "Critic, and stops for David. qwen3:30b-instruct drafts the plan; plain code decides.", ["orchestrator.py"]),
    ("character-artist", "Character Artist", "designer", "orchestrator",
     "New playable characters: the concept on qwen3:30b-instruct, the head painted by PixelLab, animations and splat from the "
     "game's own tools.", INSIDE),
    ("bridge", "Bridge", "qa", "orchestrator",
     "A script, no AI: checks the files before anything looks at them, and sends problems back to the maker.", INSIDE),
    ("critic", "Critic", "qa", "orchestrator",
     "qwen2.5vl:7b on the local cluster: looks at the line-up at game size for reasons to send it back.", INSIDE),
    ("technical-writer", "Technical Writer", "pm", "orchestrator",
     "qwen3:30b-instruct on the local cluster: writes the run summary, keeps the crew's memory short, closes finished tasks.", INSIDE),
    ("level-architect", "Level Architect", "designer", "orchestrator", "Not built yet: 100 new animated backgrounds.", INSIDE),
    ("roast-writer", "Roast Writer", "general", "orchestrator", "qwen3:30b-instruct on the local cluster: new roast lines for the end card, approved by David on Paperclip cards.", INSIDE),
    ("wardrobe-stylist", "Wardrobe Stylist", "designer", "orchestrator", "qwen3:30b-instruct on the local cluster: new hats and shades drawn as shapes, approved by David on Paperclip cards.", INSIDE),
    ("builder", "Builder", "engineer", "orchestrator",
     "Claude Code, only in sessions David starts: game changes, one approved feature at a time.",
     ["-c", "print('The Builder is Claude Code in a session David starts.')"]),
    ("foreman", "Foreman", "devops", None,
     "Plain code, no AI: keeps the crew moving. Checks for stalled tasks, failed runs and false blockers, fixes what it can, "
     "and raises the rest with David. No feature work.", ["foreman.py"]),
]


def make_company(ids):
    if ids.get("company_id"):
        return
    c = call("POST", "/api/companies", {"name": "Bottom Busters",
                                        "description": "The Bottom Busters agent crew. Tingle Games LLC. David tests everything and says commit."})
    ids["company_id"] = c["id"]
    ids["board_user"] = call("GET", "/api/auth/get-session")["user"]["id"]
    save_ids(ids)
    print("company:", c["name"], c["id"])


def make_agents(ids):
    agents = ids.setdefault("agents", {})
    for key, name, role, boss, does, args in AGENTS:
        if key in agents:
            continue
        a = call("POST", f"/api/companies/{ids['company_id']}/agents", {
            "name": name, "role": role, "title": name, "capabilities": does,
            "reportsTo": agents[boss] if boss else None,
            "adapterType": "process", "adapterConfig": {"command": PYTHON, "args": args, "cwd": CREW, "timeoutSec": 7200},
            "runtimeConfig": HEARTBEAT_OFF})
        heartbeat = (a.get("runtimeConfig") or {}).get("heartbeat") or {}
        if heartbeat.get("enabled") is not False or heartbeat.get("wakeOnDemand") is not False:
            sys.exit(f"stopped: {name} was made, but its heartbeat isn't off: {json.dumps(heartbeat)}")
        agents[key] = a["id"]
        save_ids(ids)
        print("agent:", name, "heartbeat off")


def import_cards(ids):
    """Trello's lists in board order, each list top to bottom, so the issue numbers keep David's order."""
    done = ids.setdefault("imported", {})
    tb = trello.open_board()
    statuses = [(trello.BACKLOG, "todo"), (trello.LEASED, "in_progress"), (trello.REVIEW, "in_review"),
                (trello.PLAYTEST, "in_review"), (trello.DONE, "done")]
    for list_name, status in statuses:
        for card in tb.cards(list_name):
            if card["id"] in done:
                continue
            title = card["name"]
            owner = owner_of(title, ids)
            if list_name == trello.PLAYTEST:
                owner = {"assigneeAgentId": None, "assigneeUserId": ids["board_user"]}
            this_status = "blocked" if prefix_of(title) == "Waiting" else status
            body = {"title": title, "description": (card["desc"] + f"\n\nFrom Trello: {card['url']}").strip(),
                    "status": this_status, "priority": "medium",
                    **{k: v for k, v in owner.items() if v}}
            issue = call("POST", f"/api/companies/{ids['company_id']}/issues", body)
            done[card["id"]] = issue["id"]
            save_ids(ids)
            print(f"{issue.get('identifier')}  {this_status:<12} {title}")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ids = load_ids()
    make_company(ids)
    make_agents(ids)
    if "--agents-only" not in sys.argv:
        import_cards(ids)
    print("done")


if __name__ == "__main__":
    main()
