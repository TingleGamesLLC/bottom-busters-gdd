"""The Crew tab's view of Paperclip (gap analysis G13): each agent's state and card, and the cards per column, read from
stand-in Paperclip rows. Touches neither Paperclip nor the dashboard.
usage: python test_paperclip_view.py
"""
import paperclip_board as pb

IDS = {"board_user": "david", "agents": {"character-artist": "a-art", "level-architect": "a-level", "critic": "a-critic",
                                         "roast-writer": "a-roast", "builder": "a-build", "foreman": "a-fore", "orchestrator": "a-orch"}}


def row(n, title, status, agent=None, user=None, parent=None, priority="medium"):
    return {"id": f"i{n}", "identifier": f"BOT-{n}", "issueNumber": n, "title": title, "status": status, "priority": priority,
            "assigneeAgentId": agent, "assigneeUserId": user, "parentId": parent}


def main():
    agents = [{"id": a, "status": "idle"} for a in IDS["agents"].values()]
    agents[[a["id"] for a in agents].index("a-build")]["status"] = "paused"
    agents[[a["id"] for a in agents].index("a-orch")]["status"] = "running"
    rows = [
        row(33, "[Character Artist] First set", "todo", "a-art"),
        row(38, "[Character Artist] Set 2", "blocked", "a-art"),
        row(6, "[Level Architect] 100 backgrounds", "blocked", "a-level"),
        row(50, "[Foreman] Approve an idea", "todo", user="david", priority="high"),
        row(51, "critic task", "in_progress", "a-critic", parent="i33"),
        row(29, "[Roast Writer] First batch", "in_review", user="david"),
        row(30, "[Character Artist] in review", "in_review", "a-art"),
        row(31, "old", "done", "a-art"),
        row(32, "dropped", "cancelled", "a-art"),
    ]
    blockers = {"i38": [row(33, "", "todo", "a-art")], "i6": [row(50, "", "todo", user="david")]}
    view = pb.crew_view(IDS, agents, rows, blockers)
    a = view["agents"]

    assert a["critic"] == {"status": "working", "card": "BOT-51 critic task"}, a["critic"]
    assert a["orchestrator"]["status"] == "working", a["orchestrator"]
    print("A task in progress, or a run Paperclip started, is working")
    assert a["level-architect"] == {"status": "waiting", "card": "BOT-6 [Level Architect] 100 backgrounds"}, a["level-architect"]
    assert a["roast-writer"] == {"status": "waiting", "card": "BOT-29 [Roast Writer] First batch"}, a["roast-writer"]
    print("Blocked by a question to David, or in his playtest by its title, is waiting on him")
    assert a["character-artist"] == {"status": "waiting", "card": "BOT-30 [Character Artist] in review"}, a["character-artist"]
    rows_no_review = [r for r in rows if r["id"] != "i30"]
    assert pb.crew_view(IDS, agents, rows_no_review, blockers)["agents"]["character-artist"] == \
        {"status": "queued", "card": "BOT-33 [Character Artist] First set"}
    print("Waiting beats queued; a card blocked only by another card is queued, not waiting")
    chained = rows_no_review + [row(3, "[Character Artist] Levels after", "blocked", "a-art")]
    assert pb.crew_view(IDS, agents, chained, {**blockers, "i3": [row(33, "", "todo", "a-art")]})["agents"]["character-artist"]["card"] \
        == "BOT-33 [Character Artist] First set"
    print("Among queued cards, one ready to take shows before a lower-numbered one waiting on another card")
    assert a["builder"]["status"] == "paused" and a["foreman"] == {"status": "idle", "card": None}, (a["builder"], a["foreman"])
    print("Paused in Paperclip shows paused; nothing to do is idle")

    columns = {}
    for c in view["cards"]:
        columns[c["column"]] = columns.get(c["column"], 0) + 1
    assert columns == {"Backlog": 4, "Your playtest": 1, "Review": 1, "Done": 1}, columns
    print("Cards per column: top-level cards only, blocked counts as Backlog, cancelled isn't shown")

    def card(status, option, text=None):
        return {"kind": "ask_user_questions", "status": status,
                "result": {"answers": [{"questionId": "answer", "optionIds": [option], "otherText": text}]} if status == "answered" else None}
    assert pb.answer_of([card("answered", "note", "  use the lighthouse  ")]) == "use the lighthouse"
    assert pb.answer_of([card("answered", "done")]) == pb.DONE_ANSWER
    assert pb.answer_of([card("pending", "note")]) is None and pb.answer_of([]) is None
    assert pb.answer_of([{"kind": "request_confirmation", "status": "answered", "result": {}}]) is None
    print("A question card's answer is David's own words, or Done; an unanswered card has none")
    q = pb.question_card("[Foreman] Approve an idea", "No approved idea is waiting.")
    assert q["kind"] == "ask_user_questions" and q["continuationPolicy"] == "none", q
    assert [o["id"] for o in q["payload"]["questions"][0]["options"]] == ["done", "note"]
    assert q["payload"]["questions"][0]["prompt"] == "Approve an idea" and "No approved idea" in q["payload"]["questions"][0]["helpText"]
    print("Every question gets a card with Done and Answer in my own words, and answering it wakes no agent")
    print("all passed")


if __name__ == "__main__":
    main()
