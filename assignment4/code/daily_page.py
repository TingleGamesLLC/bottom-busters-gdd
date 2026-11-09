"""The daily page on the dashboard's Today tab, built from Paperclip (gap analysis X4; the design's section 4). Paperclip only
answers on this PC, so the PC helper reads it here and sends the result to the dashboard every minute.

  - What's waiting on David: each question card the crew put to him, and his own open cards.
  - The day's work: one group per card, the card with the newest entry first, from Paperclip's activity log, plus a
    Crew upkeep group from the Foreman's own log. Times are this PC's local time, 24-hour.
DAVID approved the mockup on 2026-11-04 (dashboard/preview/today_mockup.html); it is the spec.
"""
import json
import re
from datetime import datetime

import common
import paperclip_board as pb

PAPERCLIP_UI = "http://127.0.0.1:3100/BOT"
FOREMAN_LOG = common.HERE / "foreman.log"
FOREMAN_STATE = common.HERE / "foreman_state.json"
NAMES = ["Orchestrator", "Character Artist", "Level Architect", "Roast Writer", "Wardrobe Stylist", "Technical Writer",
         "Critic", "Foreman", "Builder"]
ENTRY_LIMIT = 40   # per card


def _split(title):
    """'[Foreman] You rejected X' -> ('Foreman', 'You rejected X')."""
    m = re.match(r"\[(.+?)\]\s*(.*)", title or "")
    return (m.group(1), m.group(2)) if m else ("", title or "")


def _name(key):
    return key.replace("-", " ").title()


def _first_question(text):
    m = re.search(r"[^.?!]*\?", text or "")
    return m.group(0).strip() if m else ""


def inbox(ids, rows, descriptions, blockers, question_ids, reject_makers, review_ids=frozenset()):
    """What's waiting on David in Paperclip. question_ids: his open issues that carry a question card. reject_makers:
    {question issue id: maker} for the Foreman's no-note rejection questions. review_ids: his approval cards
    (approvals.py); the Today tab counts those as approvals, so they're left out here."""
    david = ids["board_user"]
    mine = sorted((r for r in rows if r.get("assigneeUserId") == david and r["status"] in ("todo", "in_progress", "blocked")
                   and r["id"] not in review_ids), key=lambda r: r.get("issueNumber") or 0)
    questions, open_cards, waiting = [], [], []
    for r in mine:
        who, title = _split(r["title"])
        if r["id"] in question_ids:
            ask = _first_question(descriptions.get(r["id"]))
            under = f"A question from the {who or 'crew'}, on {r['identifier']}."
            if r["id"] in reject_makers:
                under += f" Your answer goes back to the {reject_makers[r['id']]} as its note."
            questions.append({"id": r["identifier"], "text": f"{title}. {ask}" if ask else f"{title}.", "under": under,
                              "url": f"{PAPERCLIP_UI}/issues/{r['identifier']}"})
        elif not r.get("parentId") and r["status"] == "blocked":
            on = (blockers.get(r["id"]) or [None])[0]
            waiting.append(f"{r['identifier']} on {_split(on['title'])[1]}" if on else f"{r['identifier']}, {title}")
        elif not r.get("parentId"):
            open_cards.append({"id": r["identifier"], "title": title})
    return {"questions": questions,
            "own": {"open": len(open_cards), "first": open_cards[0] if open_cards else None, "waiting": waiting,
                    "url": f"{PAPERCLIP_UI}/inbox/mine"}}


def _when(stamp):
    t = datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone()
    return t, f"{t.hour}:{t.minute:02}"


def _bold_names(text, key_names):
    for key, name in key_names.items():
        text = re.sub(rf"\b{re.escape(key)}\b", name, text)
    for name in NAMES:
        text = re.sub(rf"(?<!\*)\b{re.escape(name)}\b(?!\*)", f"**{name}**", text, count=1)
    return text


WHERE = {"todo": ["In the queue", ""], "blocked": ["Blocked", ""], "in_progress": ["In progress", ""],
         "in_review": ["In review", ""], "done": ["Done", "done"], "cancelled": ["Cancelled", ""]}
MOVED = {"todo": "Back in the queue", "blocked": "Blocked", "in_progress": "In progress", "in_review": "In review",
         "done": "Closed", "cancelled": "Cancelled"}


def _where(r, david):
    if r["status"] == "in_review" and r.get("assigneeUserId") == david:
        return ["Waiting for your approval", "you"]
    return WHERE.get(r["status"], [r["status"], ""])


def _line(x, r, card, ids):
    """One readable line for an activity entry, or None for Paperclip's own housekeeping."""
    key_names = {k: _name(k) for k in ids["agents"]}
    agent = key_names.get({v: k for k, v in ids["agents"].items()}.get(r.get("assigneeAgentId")), "")
    d = x.get("details") or {}
    if x["action"] == "issue.comment_added":
        text = (d.get("bodySnippet") or "").strip()
        if not text:
            return None
        if text.startswith("Foreman:"):
            return "**Foreman**:" + text[len("Foreman:"):]
        if r is not card and agent:   # a task's comment: said by the agent doing the task
            return f"**{agent}**: {text}"
        return _bold_names(text, key_names)
    status = ((d.get("changes") or {}).get("status") or {}).get("to")
    if x["action"] == "issue.updated" and status and r is card:
        if status == "in_review" and r.get("assigneeUserId") == ids["board_user"]:
            return "Now waiting for your approval"
        return MOVED.get(status, f"Now {status}")
    if x["action"] == "issue.created" and r is card:
        return "Added to the board"
    return None


def _foreman(lines, today):
    """Crew upkeep from the Foreman's log: what it fixed or raised, and how often it checked."""
    entries, checks, acted, last = [], 0, False, None
    for line in lines:
        m = re.match(r"(\d{4}-\d{2}-\d{2}) (\d{2}):(\d{2}):\d{2}\s+(.*)", line)
        if not m or m.group(1) != today:
            continue
        t, text = (int(m.group(2)), int(m.group(3))), m.group(4).strip()
        if re.match(r"(decisions )?check done", text):
            checks, last = checks + 1, t
        elif text.startswith(("fixed: ", "raised: ")):
            acted = True
            verb, what = text.split(": ", 1)
            entries.append((t, f"**Foreman** {'fixed' if verb == 'fixed' else 'raised with you'}: {what}"))
    if checks:
        entries.append((last, f"**Foreman** checked {checks} time{'s' if checks > 1 else ''} today"
                              f"{'' if acted else ', nothing to fix'}."))
    return entries


def work(ids, rows, activity, foreman_lines):
    """The day's work, one group per card. Entries are today's only, oldest first within a card."""
    index = {r["id"]: r for r in rows}
    david, today = ids["board_user"], datetime.now().astimezone().date()
    groups, upkeep = {}, []
    for x in activity:
        r = index.get(x.get("entityId")) if x.get("entityType") == "issue" else None
        if not r:
            continue
        t, shown = _when(x["createdAt"])
        if t.date() != today:
            continue
        card = index.get(r.get("parentId")) or r
        text = _line(x, r, card, ids)
        if not text:
            continue
        if card["title"].startswith("[Foreman]"):
            upkeep.append(((t.hour, t.minute, t.second), shown, text))
        else:
            groups.setdefault(card["id"], []).append(((t.hour, t.minute, t.second), shown, text))
    for (h, m), text in _foreman(foreman_lines, today.isoformat()):
        upkeep.append(((h, m, -1), f"{h}:{m:02}", text))
    out = []
    for card_id, entries in sorted(groups.items(), key=lambda kv: max(e[0] for e in kv[1]), reverse=True):
        card = index[card_id]
        who, title = _split(card["title"])
        entries = sorted(entries, key=lambda e: e[0])[-ENTRY_LIMIT:]
        out.append({"heading": f"{who}: {title}" if who else title, "id": card.get("identifier"), "where": _where(card, david),
                    "entries": [{"time": shown, "text": text} for _, shown, text in entries]})
    if upkeep:
        out.append({"heading": "Crew upkeep", "id": None, "where": None,
                    "entries": [{"time": shown, "text": text} for _, shown, text in sorted(upkeep, key=lambda e: e[0])]})
    return out


def read(board=None):
    """The daily page from the live board, for the PC helper."""
    board = board or pb.open_board()
    rows = [r for s in ("todo", "in_progress", "in_review", "blocked", "done", "cancelled") for r in board.issues(s)]
    david = board.ids["board_user"]
    open_mine = [r for r in rows if r.get("assigneeUserId") == david and r["status"] in ("todo", "in_progress", "blocked")]
    question_ids, descriptions, review_ids = set(), {}, set()
    for r in open_mine:
        cards = pb.call("GET", f"/api/issues/{r['id']}/interactions")
        cards = cards["items"] if isinstance(cards, dict) else cards
        if any(c.get("kind") == "ask_user_questions" and c.get("status") == "pending" for c in cards):
            question_ids.add(r["id"])
            descriptions[r["id"]] = r.get("description") or ""
        if any(c.get("kind") == "request_item_verdicts" and c.get("status") == "pending" for c in cards):
            review_ids.add(r["id"])
    blockers = {r["id"]: board.issue(r["id"]).get("blockedBy") or [] for r in open_mine if r["status"] == "blocked"}
    escalated = json.loads(FOREMAN_STATE.read_text(encoding="utf-8")).get("escalated", {}) if FOREMAN_STATE.exists() else {}
    reject_makers = {}
    for key, issue_id in escalated.items():
        if key.startswith("reject:"):
            manifest = next(common.SUBMISSIONS.glob(f"*/{key[len('reject:'):]}/manifest.json"), None)
            agent = json.loads(manifest.read_text(encoding="utf-8")).get("agent") if manifest else None
            reject_makers[issue_id] = (agent or "maker").split(" (")[0]
    activity = pb.call("GET", f"/api/companies/{board.company}/activity?limit=1000")
    activity = activity["items"] if isinstance(activity, dict) else activity
    lines = FOREMAN_LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-2000:] if FOREMAN_LOG.exists() else []
    return {"inbox": inbox(board.ids, rows, descriptions, blockers, question_ids, reject_makers, review_ids),
            "work": work(board.ids, rows, activity, lines)}
