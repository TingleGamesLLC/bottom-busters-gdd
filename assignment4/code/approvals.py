"""Approvals in Paperclip. DAVID, 2026-11-04: "i dont like how my dashboard leaves dead bodies around after i apporve or
rejcet them. it makes me want to abandon it and switch to using paperclip only", then "yes make it so" to
C:\\cluster\\APPROVALS_IN_PAPERCLIP_PLAN.md.

The PC helper runs sync() every minute:
  1. collect: David's approve / reject calls on the review cards become decision.json in each submission's folder, the same
     file the dashboard wrote before, so the Foreman, the makers and install don't change. A card with everything decided
     is closed, so it leaves his inbox.
  2. post: submissions with no decision and no card go up on a review card, one "[You] Approve: ..." issue assigned to David
     per maker, kind and card, with the previews on the card. review.json in the folder says which card.
"""
import json
import time
from datetime import datetime
from pathlib import Path

import common
import paperclip_board as pb

ITEM_LIMIT = 200                  # Paperclip's most items on one card
MAX_UPLOAD = 10 * 1024 * 1024     # Paperclip's attachment cap
RETRY_AFTER = 900                 # a group whose post failed waits 15 minutes
IMAGE = {".png", ".gif", ".jpg", ".jpeg", ".webp"}
PLURAL = {"character": "characters", "background": "backgrounds", "background idea": "background ideas",
          "roast line": "roast lines"}
REASON_LABEL = "Your note (goes to the agent)"
_failed = {}                      # group title: when its post last failed


def _stamp(ts):
    return datetime.fromtimestamp(ts).astimezone().isoformat(timespec="seconds")   # the PC helper's iso()


def _read(path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def waiting(root):
    """Submissions with neither a decision nor a review card, by id ("<kind dir>/<folder>")."""
    out = []
    for m in sorted(Path(root).glob("*/*/manifest.json")):
        folder = m.parent
        if (folder / "decision.json").exists() or (folder / "review.json").exists():
            continue
        manifest = _read(m)
        if isinstance(manifest, dict):
            out.append({"id": f"{folder.parent.name}/{folder.name}", "folder": folder, "manifest": manifest})
    return out


def maker(manifest):
    """Who made it, as a sentence names them: "Claude", "the Level Architect"."""
    name = (manifest.get("agent") or "").split(" (")[0].strip()
    if not name:
        return "the crew"
    return name if name == "Claude" else f"the {name}"


def parent_of(board, card):
    """The maker's card in Paperclip, when the manifest names one that's there. Old Trello ids go through the import map."""
    if not card:
        return None
    issue_id = board.ids.get("imported", {}).get(card, card)
    try:
        board.issue(issue_id)
    except RuntimeError:
        return None
    return issue_id


def group(subs):
    """One review card per maker, kind and card, at most ITEM_LIMIT items each."""
    groups = {}
    for s in subs:
        m = s["manifest"]
        groups.setdefault((maker(m), m.get("kind") or "submission", m.get("card")), []).append(s)
    out = []
    for (who, kind, card), mine in groups.items():
        for i in range(0, len(mine), ITEM_LIMIT):
            chunk = mine[i:i + ITEM_LIMIT]
            noun = kind if len(chunk) == 1 else PLURAL.get(kind, kind + "s")
            out.append({"title": f"[You] Approve: {len(chunk)} {noun} from {who}", "maker": who, "card": card, "subs": chunk})
    return out


def item(sub, previews):
    """One item on the card. previews: uploaded attachments, or the file name of one that couldn't go up."""
    m = sub["manifest"]
    if m.get("label"):   # a manifest that names its own label shows it whole: a roast line has ". " inside it
        label, rest = m["label"], ""
    else:
        label, _, rest = (m.get("name") or sub["id"]).strip().partition(". ")
    lines = [rest.strip()] if rest.strip() else []
    for p in previews:
        if isinstance(p, dict):
            lines.append(f"![preview]({p['contentPath']})")
        elif Path(p).suffix.lower() in IMAGE:
            lines.append(f"Preview too big to show here: {p}")
        else:
            lines.append(f"Preview can't show here (not a picture): {p}")
    out = {"id": sub["id"][:120], "label": (label.strip() or sub["id"])[:120],
           "description": (m.get("description") or f"{m.get('kind') or 'submission'} from {maker(m)}")[:500]}
    if lines:
        out["previewMarkdown"] = "\n\n".join(lines)[:20000]
    return out


def card_payload(who, items):
    return {"version": 1, "prompt": f"Approve or reject each one. A reject needs a note, and the note goes to {who}.",
            "items": items, "reasonLabel": REASON_LABEL}


def post(board, root, now, say=print):
    """Put waiting submissions on review cards. Returns how many went up. A group that fails is cancelled in Paperclip,
    nothing is marked posted, and it waits RETRY_AFTER before trying again."""
    posted = 0
    for g in group(waiting(root)):
        if now - _failed.get(g["title"], now - RETRY_AFTER - 1) <= RETRY_AFTER:
            continue
        issue = None
        try:
            issue = board.new_review(g["title"], parent_of(board, g["card"]))
            items = []
            for s in g["subs"]:
                previews = []
                for p in s["manifest"].get("previews", []):
                    f = s["folder"] / p
                    if not f.is_file():
                        say(f"approvals: {s['id']}: preview {p} isn't there, so it's left off the card")
                    elif f.suffix.lower() in IMAGE and f.stat().st_size <= MAX_UPLOAD:
                        previews.append(board.upload(issue["id"], f))
                    else:
                        previews.append(f.name)
                items.append(item(s, previews))
            card = board.post_verdicts(issue["id"], card_payload(g["maker"], items))
        except Exception as e:   # any failure, not only Paperclip's: a half-made card left behind would repeat every minute
            _failed[g["title"]] = now
            say(f"approvals: couldn't post \"{g['title']}\": {e}. Trying again in {RETRY_AFTER // 60} minutes.")
            if issue:
                try:
                    board.update(issue["id"], {"status": "cancelled",
                                               "comment": "Claude: couldn't finish posting this; it will be posted again."})
                except RuntimeError:
                    pass
            continue
        _failed.pop(g["title"], None)
        for s in g["subs"]:
            (s["folder"] / "review.json").write_text(json.dumps(
                {"issue": issue["id"], "identifier": issue.get("identifier"), "interaction": card["id"],
                 "posted_at": _stamp(now)}, indent=2), encoding="utf-8")
        posted += len(g["subs"])
        say(f"approvals: {issue.get('identifier')} {g['title']}")
    return posted


def _write_decision(folder, sid, v, now):
    (folder / "decision.json").write_text(json.dumps(
        {"id": sid, "decision": v["verdict"], "note": (v.get("reason") or "").strip(), "at": v.get("resolvedAt") or _stamp(now),
         "written_at": _stamp(now)}, indent=2), encoding="utf-8")


def collect(board, root, now, say=print):
    """David's calls on the review cards, written as decision.json (never over one that's there). Returns how many were
    written. A card with everything decided is closed once. If its issue is cancelled or closed, or the card expired or is
    gone, while items are undecided, those items go up again on a new card on the next post."""
    cards = {}
    for path in sorted(Path(root).glob("*/*/review.json")):
        rec = _read(path)
        if isinstance(rec, dict) and rec.get("issue") and rec.get("interaction"):
            cards.setdefault((rec["issue"], rec["interaction"]), []).append((path.parent, rec))
    written = 0
    for (issue_id, card_id), folders in cards.items():
        if all(rec.get("closed_at") for _, rec in folders):
            continue
        label = folders[0][1].get("identifier") or issue_id
        undecided = [f for f, _ in folders if not (f / "decision.json").exists()]
        try:
            card, issue = board.verdict_card(issue_id, card_id), board.issue(issue_id)
        except RuntimeError as e:
            if "HTTP 404" not in str(e):
                say(f"approvals: couldn't read {label}: {e}")
                continue
            card, issue = None, {"status": "cancelled"}   # deleted in Paperclip: treat it as cancelled
        calls = {i.get("id"): i for i in ((card or {}).get("result") or {}).get("items", [])}
        for f in undecided:
            sid = f"{f.parent.name}/{f.name}"
            v = calls.get(sid)
            if v and v.get("verdict") in ("approve", "reject"):
                _write_decision(f, sid, v, now)
                written += 1
                say(f"approvals: {sid}: {v['verdict']}" + (f" ({v['reason'].strip()})" if (v.get("reason") or "").strip() else ""))
        still = [f for f in undecided if not (f / "decision.json").exists()]
        if still:
            if card is None or card.get("status") in ("cancelled", "expired") or issue.get("status") in ("cancelled", "done"):
                for f in still:
                    (f / "review.json").unlink()
                say(f"approvals: {label} closed with {len(still)} undecided; they go up again on a new card")
                if issue.get("status") not in ("cancelled", "done"):
                    try:
                        board.update(issue_id, {"status": "cancelled",
                                                "comment": "Claude: the undecided ones went up again on a new card."})
                    except RuntimeError:
                        pass
            continue
        calls_made = [(_read(f / "decision.json", {}) or {}).get("decision") for f, _ in folders]
        try:
            if issue.get("status") not in ("cancelled", "done"):
                board.update(issue_id, {"status": "done", "comment": f"All {len(folders)} decided: "
                                        f"{calls_made.count('approve')} approved, {calls_made.count('reject')} rejected."})
        except RuntimeError as e:
            say(f"approvals: couldn't close {label}: {e}")
            continue
        for f, rec in folders:
            (f / "review.json").write_text(json.dumps({**rec, "closed_at": _stamp(now)}, indent=2), encoding="utf-8")
    return written


def sync(board=None, root=None, now=None, say=print):
    """One pass for the PC helper: pass on David's calls, then post what's new. Returns how many calls were passed on."""
    board = board or pb.open_board()
    root = Path(root or common.SUBMISSIONS)
    now = time.time() if now is None else now
    written = collect(board, root, now, say)
    post(board, root, now, say)
    return written
