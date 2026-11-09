"""The Bottom Busters company in Paperclip. It replaced the Trello board on 2026-11-03 (DAVID: "help me migrate to running
paperclip for this instead"). Paperclip runs on the dev PC at http://127.0.0.1:3100 in local trusted mode, so calls from this PC
need no key. paperclip.json holds the company, agent and issue ids that paperclip_setup.py made.

Trello's lists map onto an issue's status and assignee:
  Backlog        todo
  In Progress    in_progress
  Review         in_review, assigned to an agent or no one
  Your Playtest  in_review, assigned to David
  Done           done

The crew works a card when it's assigned to one of its makers; the [Prefix] in a title is only a label.
Paperclip has no hand-set order. The crew takes the highest priority first, then the lowest issue number. The cards were
imported in David's Trello order, so the numbers keep it.

DAVID, 2026-11-03: "all agents will need hearbeats turned off". Every agent is made with its timer off and with waking on
assignment or demand off, so Paperclip never starts a run by itself.
"""
import json
import mimetypes
import re
import urllib.error
import uuid
from datetime import datetime, timezone
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
IDS_FILE = HERE / "paperclip.json"
URL = "http://127.0.0.1:3100"

BACKLOG, LEASED, REVIEW, PLAYTEST, DONE = "Backlog", "In Progress", "Review", "Your Playtest", "Done"
STATUS = {BACKLOG: "todo", LEASED: "in_progress", REVIEW: "in_review", PLAYTEST: "in_review", DONE: "done"}
PRIORITY = {"critical": 0, "high": 1, "medium": 2, "low": 3}

# Card prefixes and the agent that owns them. [You] and [Waiting] go to David. The rest stay unassigned.
PREFIX_AGENT = {"Character Artist": "character-artist", "Level Architect": "level-architect", "Wardrobe Stylist": "wardrobe-stylist",
                "Roast Writer": "roast-writer", "Builder": "builder"}
DAVID_PREFIXES = ("You", "Waiting")
# The project each maker's cards go in (paperclip.json holds the project ids).
AGENT_PROJECT = {"character-artist": "characters", "level-architect": "backgrounds", "roast-writer": "roasts",
                 "wardrobe-stylist": "wardrobe", "builder": "game"}
HEARTBEAT_OFF = {"heartbeat": {"enabled": False, "intervalSec": 0, "wakeOnDemand": False}}


def call(method, path, body=None):
    req = urllib.request.Request(URL + path, method=method, headers={"Content-Type": "application/json"},
                                 data=None if body is None else json.dumps(body).encode())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Paperclip answered HTTP {e.code} on {method} {path}: {e.read().decode('utf-8', 'replace')[:300]}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"could not reach Paperclip at {URL}: {e.reason}. Start it with start_paperclip.cmd") from None


def load_ids():
    return json.loads(IDS_FILE.read_text(encoding="utf-8")) if IDS_FILE.exists() else {}


def save_ids(ids):
    tmp = IDS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(ids, indent=2), encoding="utf-8")
    tmp.replace(IDS_FILE)


def prefix_of(title):
    m = re.match(r"\[(.+?)\]", title)
    return m.group(1) if m else ""


def owner_of(title, ids):
    """The assignee a card's prefix gives it: an agent, David, or no one."""
    prefix = prefix_of(title)
    if prefix in DAVID_PREFIXES:
        return {"assigneeAgentId": None, "assigneeUserId": ids["board_user"]}
    agent = ids["agents"].get(PREFIX_AGENT.get(prefix, ""))
    return {"assigneeAgentId": agent, "assigneeUserId": None}


class PaperclipBoard:
    def __init__(self):
        self.ids = load_ids()
        if not self.ids.get("company_id"):
            raise RuntimeError(f"no Paperclip company in {IDS_FILE.name}; run paperclip_setup.py first")
        self.company = self.ids["company_id"]
        self.david = self.ids["board_user"]
        # Submissions made before the move name their Trello card, so each issue also answers to its card's old id.
        self.trello_id = {issue: card for card, issue in self.ids.get("imported", {}).items()}
        self.agent_key = {v: k for k, v in self.ids["agents"].items()}

    def issues(self, status):
        """Every issue with this status, tasks under cards included."""
        rows = call("GET", f"/api/companies/{self.company}/issues?status={status}")
        return rows["items"] if isinstance(rows, dict) else rows

    def _issues(self, status):
        # Per-task issues sit under their card and aren't cards themselves.
        return [r for r in self.issues(status) if not r.get("parentId")]

    def issue(self, issue_id):
        return call("GET", f"/api/issues/{issue_id}")

    def update(self, issue_id, body):
        call("PATCH", f"/api/issues/{issue_id}", body)

    def new_card(self, title, text, agent):
        """A new card in the queue for one of the makers, in that maker's project. Returns its id."""
        body = {"title": title, "description": text, "status": "todo", "priority": "medium", "assigneeAgentId": self.ids["agents"][agent]}
        project = self.ids.get("projects", {}).get(AGENT_PROJECT.get(agent))
        if project:
            body.update(projectId=project, goalId=self.ids.get("goal_id"))
        return call("POST", f"/api/companies/{self.company}/issues", body)["id"]

    def ask_david(self, title, text, parent=None):
        """A high-priority issue assigned to David, at the top of his list, with a question card on it (gap analysis X3).
        Returns its id. If the card can't be made, the question still stands as the issue's text."""
        body = {"title": title, "description": text, "status": "todo", "priority": "high", "assigneeUserId": self.david}
        if parent:
            body["parentId"] = parent
        issue_id = call("POST", f"/api/companies/{self.company}/issues", body)["id"]
        try:
            call("POST", f"/api/issues/{issue_id}/interactions", question_card(title, text))
        except RuntimeError:
            pass
        return issue_id

    def answered_questions(self):
        """(question issue, David's answer) for each open question of David's whose card he has answered."""
        found = []
        for status in ("todo", "in_progress", "blocked"):
            for r in self.issues(status):
                if r.get("assigneeUserId") != self.david:
                    continue
                cards = call("GET", f"/api/issues/{r['id']}/interactions")
                answer = answer_of(cards["items"] if isinstance(cards, dict) else cards)
                if answer:
                    found.append((r, answer))
        return found

    def cards(self, list_name):
        rows = self._issues(STATUS[list_name])
        if list_name == PLAYTEST:
            rows = [r for r in rows if r.get("assigneeUserId") == self.david]
        elif list_name == REVIEW:
            rows = [r for r in rows if r.get("assigneeUserId") != self.david]
        rows.sort(key=lambda r: (PRIORITY.get(r.get("priority"), 9), r.get("issueNumber") or 0))
        return [{"id": r["id"], "name": r["title"], "desc": r.get("description") or "", "url": r.get("identifier"), "list": list_name,
                 "trello_id": self.trello_id.get(r["id"]), "agent": self.agent_key.get(r.get("assigneeAgentId"))} for r in rows]

    def move(self, card, list_name):
        body = {"status": STATUS[list_name]}
        if list_name == PLAYTEST:
            body.update({"assigneeAgentId": None, "assigneeUserId": self.david})
        elif card.get("agent"):
            body.update({"assigneeAgentId": self.ids["agents"][card["agent"]], "assigneeUserId": None})
        else:
            body.update(owner_of(card["name"], self.ids))
        call("PATCH", f"/api/issues/{card['id']}", body)
        card["list"] = list_name

    def comment(self, card, text):
        call("POST", f"/api/issues/{card['id']}/comments", {"body": text[:16000]})

    def archive(self, card):
        """Done is Paperclip's last state, and done issues stay on the record. Nothing more to do."""

    # Paperclip's own records: one issue per task for the agent doing it, and what each agent spent.

    def open_task(self, card, agent, title, brief):
        body = {"title": title, "description": brief, "status": "in_progress", "parentId": card["id"],
                "assigneeAgentId": self.ids["agents"][agent]}
        return call("POST", f"/api/companies/{self.company}/issues", body)["id"]

    def close_task(self, task_id, status, text):
        call("PATCH", f"/api/issues/{task_id}", {"status": status, "comment": text[:16000]})

    def task_comment(self, task_id, text):
        call("POST", f"/api/issues/{task_id}/comments", {"body": text[:16000]})

    def report_cost(self, agent, provider, model, input_tokens, output_tokens, cents, billing, card=None, key=None):
        """billing is "fixed" for the local cluster (our own machines) and "credits" for PixelLab. The key stops a retry
        from counting twice."""
        try:
            call("POST", f"/api/companies/{self.company}/cost-events",
                 {"agentId": self.ids["agents"][agent], "provider": provider, "model": model, "billingType": billing,
                  "inputTokens": int(input_tokens), "outputTokens": int(output_tokens), "costCents": round(cents, 4),
                  "issueId": card["id"] if card else None, "idempotencyKey": key,
                  "occurredAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")})
        except RuntimeError as e:
            if "Idempotency key already used" not in str(e):
                raise


    # Review cards (approvals in Paperclip, 2026-11-04; approvals.py): a "[You] Approve: ..." issue for David with one
    # request_item_verdicts card on it, the previews uploaded as attachments.

    def new_review(self, title, parent):
        body = {"title": title, "status": "todo", "priority": "high", "assigneeUserId": self.david,
                "description": "Approve or reject each one on the card below. Your calls reach the crew within a minute."}
        if parent:
            body["parentId"] = parent
        return call("POST", f"/api/companies/{self.company}/issues", body)

    def upload(self, issue_id, path):
        return upload(self.company, issue_id, path)

    def post_verdicts(self, issue_id, payload):
        return call("POST", f"/api/issues/{issue_id}/interactions",
                    {"kind": "request_item_verdicts", "continuationPolicy": "none", "payload": payload})

    def verdict_card(self, issue_id, card_id):
        cards = call("GET", f"/api/issues/{issue_id}/interactions")
        cards = cards["items"] if isinstance(cards, dict) else cards
        return next((c for c in cards if c.get("id") == card_id), None)


def upload(company, issue_id, path):
    """One file onto an issue, as Paperclip's attachment form takes it (field "file"). Returns the attachment."""
    path = Path(path)
    ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    boundary = uuid.uuid4().hex
    head = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\n"
            f"Content-Type: {ctype}\r\n\r\n").encode()
    req = urllib.request.Request(f"{URL}/api/companies/{company}/issues/{issue_id}/attachments", method="POST",
                                 data=head + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode(),
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Paperclip answered HTTP {e.code} on uploading {path.name}: "
                           f"{e.read().decode('utf-8', 'replace')[:300]}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"could not reach Paperclip at {URL}: {e.reason}. Start it with start_paperclip.cmd") from None


def open_board():
    return PaperclipBoard()


# ── question cards (gap analysis X3): Paperclip's built-in card, answered in the question's thread ─────────────────────
DONE_ANSWER = "Done, I've handled it"


def question_card(title, text):
    """The card for one question: Done, or an answer in David's own words. Answering wakes no agent (every heartbeat is
    off); the Foreman reads the answer on its next check."""
    return {"kind": "ask_user_questions", "continuationPolicy": "none", "title": "The crew needs you",
            "payload": {"version": 1, "submitLabel": "Send",
                        "questions": [{"id": "answer", "prompt": re.sub(r"^\[[^\]]+\]\s*", "", title)[:4000] or title[:4000],
                                       "helpText": text[:4000], "selectionMode": "single", "required": True,
                                       "options": [{"id": "done", "label": DONE_ANSWER},
                                                   {"id": "note", "label": "Answer in my own words", "freeText": True}]}]}}


def answer_of(interactions):
    """David's answer on a question card: his own words, or DONE_ANSWER. None while no card is answered."""
    for i in interactions:
        if i.get("kind") != "ask_user_questions" or i.get("status") != "answered":
            continue
        for a in (i.get("result") or {}).get("answers", []):
            if (a.get("otherText") or "").strip():
                return a["otherText"].strip()
            if "done" in (a.get("optionIds") or []):
                return DONE_ANSWER
    return None


# ── the Crew tab's view of Paperclip (gap analysis G13: one source of truth for agent status) ─────────────────────────
COLUMNS = {"todo": "Backlog", "blocked": "Backlog", "in_progress": "In progress", "done": "Done"}   # the dashboard's names
RANK = {"working": 0, "waiting": 1, "queued": 2, "queued behind a card": 3}


def crew_view(ids, agents, rows, blockers):
    """Each agent's state and card, and the cards per column, from Paperclip's own rows.
    agents: Paperclip's agent rows. rows: every issue. blockers: {issue id: the issues blocking it}.
    working: a run Paperclip started, or a card or task in progress. waiting: blocked by a question to David, or in review
    (his playtest counts by the card's [Prefix]). queued: to do, or blocked only by other cards (a card ready to take shown first). Paused and errored agents
    show that instead. The first card in priority order is the one shown."""
    key_of = {v: k for k, v in ids["agents"].items()}
    david = ids["board_user"]
    found = {}
    for r in sorted(rows, key=lambda r: (PRIORITY.get(r.get("priority"), 9), r.get("issueNumber") or 0)):
        key = key_of.get(r.get("assigneeAgentId")) or (PREFIX_AGENT.get(prefix_of(r["title"]))
                                                         if r.get("assigneeUserId") == david else None)
        if not key:
            continue
        if r["status"] == "in_progress":
            state = "working"
        elif r["status"] == "in_review" or (r["status"] == "blocked" and
                                             any(b.get("assigneeUserId") == david and b.get("status") not in ("done", "cancelled")
                                                 for b in blockers.get(r["id"], []))):
            state = "waiting"
        elif r["status"] in ("todo", "blocked"):
            state = "queued" if r["status"] == "todo" else "queued behind a card"
        else:
            continue
        if key not in found or RANK[state] < RANK[found[key][0]]:
            found[key] = (state, f"{r.get('identifier')} {r['title']}")
    view = {}
    for a in agents:
        key = key_of.get(a["id"])
        if not key:
            continue
        state, card = found.get(key, ("idle", None))
        state = "queued" if state == "queued behind a card" else state
        if a.get("status") == "running":
            state = "working"
        elif a.get("status") in ("paused", "error"):
            state = "paused" if a["status"] == "paused" else "stopped"
        view[key] = {"status": state, "card": card}
    cards = []
    for r in rows:
        if r.get("parentId") or r["status"] == "cancelled":
            continue
        column = COLUMNS.get(r["status"]) or ("Your playtest" if r.get("assigneeUserId") == david else "Review")
        cards.append({"column": column, "name": f"{r.get('identifier')} {r['title']}"})
    return {"agents": view, "cards": cards}


def read_crew_view(board=None):
    """crew_view on the live board, for the PC helper to send to the dashboard."""
    board = board or open_board()
    rows = [r for s in ("todo", "in_progress", "in_review", "blocked", "done", "cancelled") for r in board.issues(s)]
    blockers = {r["id"]: board.issue(r["id"]).get("blockedBy") or [] for r in rows if r["status"] == "blocked"}
    agents = call("GET", f"/api/companies/{board.company}/agents")
    return crew_view(board.ids, agents["items"] if isinstance(agents, dict) else agents, rows, blockers)
