"""Technical Writer: keeps the record, so the next run starts from a short true summary instead of everything that happened.

After a run it writes the run's summary, adds it to CREW_LOG.md and the card, and compacts memory.md (class notes:
prevent context collapse: summarize past actions, archive resolved tasks). It also keeps the Mermaid diagram current, and
closes a card once David has approved all of its work.
"""
import json
import re
import time

import board as trello
import common

LOG = common.HERE / "CREW_LOG.md"
DIAGRAM = common.HERE / "crew.mmd"
MEMORY_LINES = 12


def plain_report(made, sent_back):
    """The report with no model in it: what the draft is checked against, and what goes out if the draft is wrong."""
    looks = "; ".join(f"{m['name']} ({m['skin']}): {m['look']}, {m['skin_tone']} skin" for m in made)
    backs = f"{len(sent_back)} sent back: {' '.join(sent_back)}" if sent_back else "Nothing was sent back."
    return f"Made {len(made)}: {looks}. {backs} Waiting on David to approve or reject each one on the dashboard's Characters tab. Not tested in the game."


def draft_is_true(text, made, sent_back):
    """The cluster's draft is only used if it names everything made and doesn't invent a send-back."""
    if not all(m["name"] in text for m in made):
        return False
    if not sent_back and re.search(r"(?<!nothing )(?<!nothing was )\b(sent back|revision|rejected|redo|redone)\b", text, re.I):
        return False
    return "tested" not in text.lower() or "not tested" in text.lower()


def summarize(run, card, results):
    sent_back = [e["text"] for e in run.state["events"] if "sent back" in e["text"]]
    made = [{k: r[k] for k in ("name", "skin", "look", "skin_tone")} for r in results]
    facts = {"made": made, "sent_back_count": len(sent_back), "sent_back_reasons": sent_back, "waiting_on": "David approves or rejects each on the Characters tab"}
    messages = [{"role": "system", "content": "You write short run reports in plain American English. Use only the facts given, and "
                                              "add nothing. Never claim anything was tested in the game. No headings, no lists."},
                {"role": "user", "content": "Write at most 4 sentences on this crew run: what was made, whether anything was sent back, "
                                            "and what is waiting on David. If sent_back_count is 0, say nothing was sent back.\n\n"
                                            + json.dumps(facts, indent=1)}]
    text = common.ask("technical-writer", messages, max_tokens=500).strip()
    if not draft_is_true(text, made, sent_back):
        run.event("technical-writer", "the cluster's draft didn't match the run, so the plain report went out instead")
        text = plain_report(made, sent_back)
    (run.dir / "SUMMARY.md").write_text(f"# Run {run.id}: {card['name']}\n\n{text}\n", encoding="utf-8")
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"\n## {time.strftime('%Y-%m-%d %H:%M')}, {card['name']}\n\n{text}\n")
    return text


def compact_memory(card, text):
    """One line per run. When it grows past MEMORY_LINES, the older half is folded into one line by the cluster."""
    line = f"- {time.strftime('%Y-%m-%d')} {card['name']}: {text.splitlines()[0][:300]}"
    lines = common.MEMORY.read_text(encoding="utf-8").splitlines() if common.MEMORY.exists() else []
    lines.append(line)
    if len(lines) > MEMORY_LINES:
        old, lines = lines[:len(lines) // 2], lines[len(lines) // 2:]
        messages = [{"role": "user", "content": "Fold these crew run notes into one line of at most 40 words. Keep decisions and "
                                                "what David rejected.\n\n" + "\n".join(old)}]
        lines.insert(0, "- Earlier runs: " + common.ask("technical-writer", messages, max_tokens=200).strip().replace("\n", " "))
    common.MEMORY.write_text("\n".join(lines) + "\n", encoding="utf-8")


def close_finished(board, run):
    """Cards at Your Playtest whose submissions David has all approved go to Done and are archived."""
    closed = []
    for card in board.cards(trello.PLAYTEST):
        manifests = [p for p in common.SUBMISSIONS.glob("*/*/manifest.json")
                     if json.loads(p.read_text(encoding="utf-8")).get("card") == card["id"]]
        decisions = [p.with_name("decision.json") for p in manifests]
        if manifests and all(d.exists() and json.loads(d.read_text(encoding="utf-8")).get("decision") == "approve" for d in decisions):
            board.move(card, trello.DONE)
            board.comment(card, f"All {len(manifests)} submissions approved by David. Closed by the Technical Writer.")
            board.archive(card)
            closed.append(card["name"])
            run.event("technical-writer", f"closed and archived: {card['name']}")
    return closed


def write_diagram(pipeline):
    """crew.mmd, generated from the Orchestrator's own pipeline table so the picture can't drift from the code."""
    lines = ["flowchart TD"]
    for node, label, shape in pipeline["nodes"]:
        open_, close = {"round": ('("', '")'), "box": ('["', '"]'), "store": ('[("', '")]'), "person": ('(["', '"])')}[shape]
        lines.append(f"    {node}{open_}{label}{close}")
    for a, b, label in pipeline["edges"]:
        lines.append(f'    {a} -->|"{label}"| {b}')
    for name, members in pipeline.get("classes", {}).items():
        lines.append(f"    class {','.join(members)} {name}")
    for name, style in pipeline.get("styles", {}).items():
        lines.append(f"    classDef {name} {style}")
    DIAGRAM.write_text("\n".join(lines) + "\n", encoding="utf-8")
