"""The daily page on the Today tab, from Paperclip (gap analysis X4): what's waiting on David, and the day's work grouped by
card. Stand-in Paperclip rows, activity and Foreman log; touches nothing.
usage: python test_daily_page.py
"""
from datetime import datetime, timezone

import daily_page as dp

IDS = {"board_user": "david", "agents": {"character-artist": "a-art", "critic": "a-critic", "level-architect": "a-level"}}


def row(n, title, status, agent=None, user=None, parent=None):
    return {"id": f"i{n}", "identifier": f"BOT-{n}", "issueNumber": n, "title": title, "status": status, "priority": "medium",
            "assigneeAgentId": agent, "assigneeUserId": user, "parentId": parent}


def utc(h, m):
    """A UTC timestamp that is h:m local time today."""
    local = datetime.now().astimezone().replace(hour=h, minute=m, second=0, microsecond=0)
    return local.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


ROWS = [
    row(33, "[Character Artist] First set: the other 8 characters", "in_review", user="david"),
    row(60, "player13: make one character", "done", "a-art", parent="i33"),
    row(61, "Review player13", "done", "a-critic", parent="i33"),
    row(6, "[Level Architect] 100 new animated backgrounds", "in_progress", "a-level"),
    row(31, "[Foreman] You rejected Fuzzball (player12) with no note", "todo", user="david", parent="i33"),
    row(70, "[Foreman] PixelLab has 2 generations left", "todo", user="david"),
    row(1, "[You] Confirm the new character count and token estimate", "todo", user="david"),
    row(17, "[You] Scoring definitions", "todo", user="david"),
    row(2, "[You] Pick the layout concepts for levels 100-200", "blocked", user="david"),
    row(22, "[Waiting] Steam App ID", "blocked", user="david"),
]
DESCRIPTIONS = {"i31": "Fuzzball (player12) was rejected with no note. What should change? Reject it again with a note.",
                "i70": "PixelLab has 2 generations and $0.00 left."}


def act(h, m, action, issue, **details):
    return {"createdAt": utc(h, m), "action": action, "entityType": "issue", "entityId": issue, "details": details}


def main():
    box = dp.inbox(IDS, ROWS, DESCRIPTIONS, {"i2": [row(6, "[Level Architect] 100 new animated backgrounds", "in_progress")], "i22": []},
                   question_ids={"i31", "i70"}, reject_makers={"i31": "Character Artist"})
    q = {x["id"]: x for x in box["questions"]}
    assert q["BOT-31"]["text"] == "You rejected Fuzzball (player12) with no note. What should change?", q["BOT-31"]
    assert q["BOT-31"]["under"] == "A question from the Foreman, on BOT-31. Your answer goes back to the Character Artist as its note."
    assert q["BOT-31"]["url"] == "http://127.0.0.1:3100/BOT/issues/BOT-31"
    assert q["BOT-70"]["text"] == "PixelLab has 2 generations left." and q["BOT-70"]["under"] == "A question from the Foreman, on BOT-70."
    print("A question card: its question, who asked, and where the answer goes")
    own = box["own"]
    assert own["open"] == 2 and own["first"] == {"id": "BOT-1", "title": "Confirm the new character count and token estimate"}, own
    assert own["waiting"] == ["BOT-2 on 100 new animated backgrounds", "BOT-22, Steam App ID"], own["waiting"]
    assert own["url"] == "http://127.0.0.1:3100/BOT/inbox/mine"
    print("David's own cards: how many are open, the first one, and the ones waiting on something else")
    review = dp.inbox(IDS, ROWS + [row(80, "[You] Approve: 3 backgrounds from Claude", "todo", user="david")], DESCRIPTIONS,
                      {"i2": [], "i22": []}, question_ids={"i31", "i70"}, reject_makers={}, review_ids={"i80"})
    assert review["own"]["open"] == 2 and all(x["id"] != "BOT-80" for x in review["questions"]), review
    print("An approval card is neither a question nor one of David's own cards")

    activity = [
        act(9, 2, "issue.comment_added", "i33", bodySnippet="Leased to character-artist by the Orchestrator, run 20261104-090200. Plan: player13"),
        act(9, 15, "issue.comment_added", "i60", bodySnippet="The Bridge sent it back: flail frame 5 is missing"),
        act(9, 20, "issue.comment_added", "i60", bodySnippet="Made Tariq (player13). Hair: short twists."),
        act(9, 21, "issue.comment_added", "i61", bodySnippet="pass. Short black twists, clear face."),
        act(9, 22, "issue.updated", "i60", changes={"status": {"from": "in_progress", "to": "done"}}),
        act(10, 48, "issue.updated", "i33", changes={"status": {"from": "in_progress", "to": "in_review"}}),
        act(11, 12, "issue.comment_added", "i6", bodySnippet="Leased to level-architect by the Orchestrator, run x. Plan: idea_012"),
        act(11, 3, "issue.comment_added", "i31", bodySnippet="Foreman: David answered on the question card: make the poof smaller"),
        act(11, 30, "issue.blockers_updated", "i6"),
        act(11, 31, "issue.comment_added", "i70", bodySnippet="Foreman: this cleared on its own check."),
        {"createdAt": "2020-01-01T10:00:00Z", "action": "issue.comment_added", "entityType": "issue", "entityId": "i6",
         "details": {"bodySnippet": "an old day"}},
    ]
    checks = [f"{datetime.now():%Y-%m-%d} 10:00:04  check done: fixed 0, raised 0",
              f"{datetime.now():%Y-%m-%d} 11:00:04  check done: fixed 1, raised 0",
              f"{datetime.now():%Y-%m-%d} 11:00:04    fixed: BOT-14: unblocked",
              "2020-01-01 10:00:04  check done: fixed 3, raised 0"]
    groups = dp.work(IDS, ROWS, activity, checks)
    assert [g["heading"] for g in groups] == ["Level Architect: 100 new animated backgrounds",
                                              "Character Artist: First set: the other 8 characters", "Crew upkeep"], [g["heading"] for g in groups]
    print("One group per card, the card with the newest entry first, crew upkeep last")
    la, ca, up = groups
    assert la["id"] == "BOT-6" and la["where"] == ["In progress", ""] and la["entries"] == [
        {"time": "11:12", "text": "Leased to **Level Architect** by the **Orchestrator**, run x. Plan: idea_012"}], la
    assert ca["where"] == ["Waiting for your approval", "you"], ca["where"]
    assert [e["time"] for e in ca["entries"]] == ["9:02", "9:15", "9:20", "9:21", "10:48", "11:03"], ca["entries"]
    assert ca["entries"][1]["text"] == "**Character Artist**: The Bridge sent it back: flail frame 5 is missing", ca["entries"][1]
    assert ca["entries"][3]["text"] == "**Critic**: pass. Short black twists, clear face."
    assert ca["entries"][4]["text"] == "Now waiting for your approval"
    assert ca["entries"][5]["text"] == "**Foreman**: David answered on the question card: make the poof smaller"
    print("Each line says who did it, a task's line goes under its card, a question under the card it's about")
    assert all("an old day" not in e["text"] for g in groups for e in g["entries"])
    assert not any("blockers" in e["text"] for g in groups for e in g["entries"])
    print("Only today's entries, and Paperclip's own housekeeping is left out")
    assert up["id"] is None and up["where"] is None and up["entries"] == [
        {"time": "11:00", "text": "**Foreman** fixed: BOT-14: unblocked"},
        {"time": "11:00", "text": "**Foreman** checked 2 times today."},
        {"time": "11:31", "text": "**Foreman**: this cleared on its own check."}], up["entries"]
    quiet = dp.work(IDS, ROWS, [], checks[:1])
    assert quiet == [{"heading": "Crew upkeep", "id": None, "where": None,
                      "entries": [{"time": "10:00", "text": "**Foreman** checked 1 time today, nothing to fix."}]}], quiet
    print("Crew upkeep: what the Foreman fixed or raised, and how often it checked")
    print("all passed")


if __name__ == "__main__":
    main()
