"""The Roast Writer: new roast lines for the Bottom Busters end card. C:\\cluster\\ROAST_WRITER_DESIGN.md, approved by DAVID on
2026-11-04 ("build it now").

Content only (DAVID: "this is a content generation pipeline only. i only care about new high qualit roast lines"). It reads
the game's roast file for the 40 lines David kept and never writes it. Each batch:
  1. plan: which events and outcomes need lines, fewest first
  2. write: qwen3:30b writes 4 candidates for every line needed, one call per event
  3. checks: the Bridge drops any line that breaks the voice's rules; an outcome left with none gets one more try
  4. pick: a separate qwen3:30b call scores the survivors, and the best line for each outcome goes up
Each line is its own submission folder, so the Paperclip approvals put the batch on one card in David's inbox. Approved lines
collect in C:\\cluster\\approved\\roasts\\roast_lines.json in the game's own line format, for David to add himself.
"""
import json
import re
from collections import Counter
from pathlib import Path

import bridge
import common
import gdd
from common import CrewStop

GAME_ROASTS = Path(r"C:\bbust\BBUST\Assets\Resources\Roasts\roasts.json")   # read only
APPROVED = Path(r"C:\cluster\approved\roasts\roast_lines.json")
FOLDER = "roast_lines"          # under common.SUBMISSIONS
KIND = "roast line"
AGENT = "Roast Writer"
TOTAL = 250                     # the crew design: 250 lines, 25 a batch, stopping after the first 5
FIRST = 5
PER_RUN = 25
CANDIDATES = 4                  # written for every line that goes up
RECENT_APPROVED = 20            # approved lines shown in the prompt beside the 40 kept
RECENT_REJECTED = 40

# The 11 events the kept lines use: id -> (on the card, happens when, always out of Gauntlet, outcomes it can have).
# "" is a general line. "" as an outcome means a win or a loss.
EVENTS = {
    "": ("General", "any round, when no event line fits", False, ("win", "loss")),
    "flaps": ("Methane Released", "the player flapped 5 or more times (the characters fly by farting)", False, ("win", "loss", "")),
    "kills": ("Enemies Defeated", "the player defeated at least one enemy", False, ("win", "loss", "")),
    "drowned": ("Lifeguard Off Duty", "the player drowned at least one enemy", False, ("win", "loss", "")),
    "bombsOnTarget": ("Bombs On Target", "the player's poo splats hit enemies", True, ("win", "loss", "")),
    "directDeposit": ("Direct Deposit", "the player's poo splats hit enemies on the head", True, ("win", "loss", "")),
    "inOneSitting": ("In One Sitting", "the player hit 3 or more enemies in a row without missing", True, ("win", "loss", "")),
    "longestStreak": ("Longest Streak Of Poo", "the player dropped 10 or more splats in the round", True, ("win", "loss", "")),
    "received": ("Received", "the player got splatted by others", True, ("win", "loss", "")),
    "fullCoverage": ("Full Coverage", "every enemy in the level got splatted at least once", True, ("win", "loss", "")),
    "diedDirty": ("Died Dirty", "the player lost after being splatted 3 or more times", True, ("loss",)),
}
OUTCOME_WORDS = {"win": "on a win", "loss": "on a loss", "": "on a win or a loss"}

VOICE = """You write roast lines for Bottom Busters, a comedy arcade game. The players fly by farting and splat each other \
with poo. At the end of each round a deadpan narrator reads one short line about what the player just did.

The voice:
- Short. One to three short sentences, 15 words at most.
- A flat verdict, then a turn. Example: "Dead. Even the enemies looked away out of respect."
- A deadpan, formal narrator treating something gross like an official matter: a grievance filed, a museum basement, \
medical questions.
- Never name the gross thing. Say "it", a smell, a plumber, a bad curry. Never "poo", "poop" or "fart".
- Backhanded praise on a win, meaner on a loss.
- Threes work: "Efficient. Brutal. Faintly upsetting."
- Periods only. No exclamation marks, no question marks, no quotation marks, no pop culture, no brands, no real people. \
At most one word in capitals, for stress.
- Always about "you", the player, and the exact thing that happened. No names, and nothing about the player's body, race, \
age or looks, so it fits any character.
- American English.
Don't explain the joke. Don't lean on a pun alone. Don't copy a line you're shown, or its shape."""

JUDGE = """You judge new roast lines for Bottom Busters against the lines David kept. Be hard to please: most lines aren't \
funny. Score each numbered line from 0 to 10 on four things:
"fits": it's about this event and this outcome
"voice": it sounds like the kept lines: deadpan and formal, a flat verdict then a turn, the gross thing never named
"funny": it would make a player laugh out loud
"fresh": its joke and its shape differ from the kept lines and from the other numbered lines
Answer with only one JSON object: {"scores": [{"n": 1, "fits": 0, "voice": 0, "funny": 0, "fresh": 0}]}, one entry for \
every numbered line."""


def _read(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def kept_lines():
    """The lines in the game today, read from its roast file (never written)."""
    lines = (_read(GAME_ROASTS, {}) or {}).get("lines") or []
    return [{"id": l.get("id", ""), "text": l["text"], "topic": l.get("topic") or "", "outcome": l.get("outcome") or "",
             "noGauntlet": bool(l.get("noGauntlet")), "placeholder": bool(l.get("placeholder"))}
            for l in lines if isinstance(l, dict) and l.get("text") and not l.get("placeholder")]


def lines():
    """(folder, manifest, decision or None) for every line the Roast Writer has put up."""
    found = []
    for m in sorted((common.SUBMISSIONS / FOLDER).glob("*/manifest.json")):
        man = _read(m)
        if isinstance(man, dict) and man.get("kind") == KIND and isinstance(man.get("line"), dict):
            found.append((m.parent, man, _read(m.with_name("decision.json"))))
    return found


def state():
    """waiting: lines David hasn't decided. approved: lines he approved. next: how many the next batch makes, 0 while he's
    deciding the last card or once TOTAL are approved."""
    made = lines()
    waiting = sum(1 for _, _, d in made if not d)
    approved = sum(1 for _, _, d in made if d and d.get("decision") == "approve")
    if waiting or approved >= TOTAL:
        nxt = 0
    elif not made:
        nxt = FIRST
    else:
        nxt = min(PER_RUN, TOTAL - approved)
    return {"waiting": waiting, "approved": approved, "next": nxt}


def plan(n, have):
    """n (event, outcome) slots, each for the event with the fewest lines so far, and within it the outcome it has least
    of. have: (event, outcome) of every line kept, approved or waiting."""
    by_event = Counter(t for t, _ in have)
    by_outcome = Counter(have)
    order = list(EVENTS)
    slots = []
    for _ in range(n):
        topic = min(order, key=lambda t: (by_event[t], order.index(t)))
        outcomes = EVENTS[topic][3]
        outcome = min(outcomes, key=lambda o: (by_outcome[(topic, o)], outcomes.index(o)))
        slots.append((topic, outcome))
        by_event[topic] += 1
        by_outcome[(topic, outcome)] += 1
    return slots


def next_id(topic, taken):
    k = 1
    while f"rw_{topic or 'general'}_{k:03}" in taken:
        k += 1
    return f"rw_{topic or 'general'}_{k:03}"


def describe(line):
    """The card item's description: "Direct Deposit, on a win, not in Gauntlet"."""
    return f"{EVENTS[line['topic']][0]}, {OUTCOME_WORDS[line['outcome']]}" + (", not in Gauntlet" if line.get("noGauntlet") else "")


def _outcome(word):
    word = (word or "").strip().lower()
    return word if word in ("win", "loss") else ""


def _clean(text):
    return re.sub(r"\s+", " ", str(text or "")).strip().strip('"“”').strip()


def _tag(l):
    return f"{EVENTS.get(l['topic'], ('?',))[0]}, {OUTCOME_WORDS.get(l['outcome'], '')}"


def write(topic, outcomes, kept, approved, rejected, sent_back=()):
    """Raw candidates for one event: CANDIDATES for every outcome in outcomes. sent_back: (line, the GDD rule it broke) from
    the Critic's check of this event's last try. Returns [{"text", "outcome"}]."""
    label, happens = EVENTS[topic][:2]
    need = Counter(outcomes)
    asks = ", ".join(f"{CANDIDATES * need[o]} for {OUTCOME_WORDS[o][3:]}" for o in ("win", "loss", "") if need[o])
    parts = [gdd.prompt_block("roast-writer"), "",
             f"The event: {label}. It happens when {happens}." if topic else "General lines: they play when no event line fits.",
             "", "Lines David kept, the style to match:"] + [f"- {l['text']} ({_tag(l)})" for l in kept]
    if approved:
        parts += ["", "New lines David approved:"] + [f"- {l['text']} ({_tag(l)})" for l in approved]
    if rejected:
        parts += ["", "New lines David rejected, with his note. Learn from the notes:"]
        parts += [f"- {l['text']} ({_tag(l)}). David's note: {note}" for l, note in rejected]
    if sent_back:
        parts += ["", "Your last lines for this event that the Critic sent back, with the GDD rule each one broke. Don't repeat it:"]
        parts += [f"- {text}. Broke: {why}" for text, why in sent_back]
    parts += ["", f"Write {sum(CANDIDATES * need[o] for o in need)} new lines for this event: {asks}. Each one different.",
              'Answer with only one JSON object: {"lines": [{"text": "...", "outcome": "win" or "loss" or "either"}]}']
    messages = [{"role": "system", "content": VOICE}, {"role": "user", "content": "\n".join(parts)}]
    d = common.ask_json("roast-writer", messages, ["lines"], max_tokens=max(800, 80 * CANDIDATES * len(outcomes) + 300))
    return [{"text": _clean(c.get("text")), "outcome": _outcome(c.get("outcome"))}
            for c in d["lines"] if isinstance(c, dict) and c.get("text")]


def pick(topic, survivors, outcomes, kept):
    """The best survivor for each outcome needed, scored by a separate call. A line too like one already picked is skipped."""
    if not survivors:
        return []
    label = EVENTS[topic][0]
    parts = [f"The event: {label}." if topic else "General lines.", "", "Lines David kept:"]
    parts += [f"- {l['text']} ({_tag(l)})" for l in kept]
    parts += ["", "New lines to score:"] + [f"{k + 1}. ({OUTCOME_WORDS[s['outcome']]}) {s['text']}" for k, s in enumerate(survivors)]
    messages = [{"role": "system", "content": JUDGE}, {"role": "user", "content": "\n".join(parts)}]
    d = common.ask_json("roast-writer", messages, ["scores"], max_tokens=max(600, 40 * len(survivors) + 300))
    total = {}
    for s in d["scores"]:
        try:
            # Funny counts double: high-quality lines are the whole point (DAVID: "i only care about new high qualit roast lines").
            total[int(s["n"]) - 1] = sum(float(s.get(k) or 0) for k in ("fits", "voice", "fresh")) + 2 * float(s.get("funny") or 0)
        except (KeyError, TypeError, ValueError):
            continue
    ranked = sorted(range(len(survivors)), key=lambda k: -total.get(k, 0))
    chosen = []
    for outcome in outcomes:
        for k in ranked:
            s = survivors[k]
            if s["outcome"] == outcome and s not in chosen and not any(bridge.similar_lines(c["text"], s["text"]) for c in chosen):
                chosen.append(dict(s, score=total.get(k, 0)))
                break
    return chosen


def make_batch(n, card, run_id, say=print, review=None):
    """Writes, checks and picks n lines, and puts each in its own submission folder. Returns the folders.
    review: the Critic's GDD check, handed over by the Orchestrator (critic.check_gdd_lines). Lines that pass the Bridge go
    through it; a line it fails is dropped, and its reason goes into this event's next try."""
    kept, made = kept_lines(), lines()
    approved = [m["line"] for _, m, d in made if d and d.get("decision") == "approve"]
    rejected = [(m["line"], (d.get("note") or "").strip() or "no note")
                for _, m, d in made if d and d.get("decision") == "reject"][-RECENT_REJECTED:]
    have = [(l["topic"], l["outcome"]) for l in kept] + \
           [(m["line"]["topic"], m["line"]["outcome"]) for _, m, d in made if not d or d.get("decision") == "approve"]
    known = [l["text"] for l in kept] + [m["line"]["text"] for _, m, _ in made]
    taken = {l["id"] for l in kept} | {m["line"]["id"] for _, m, _ in made}

    groups = {}
    for topic, outcome in plan(n, have):
        groups.setdefault(topic, []).append(outcome)
    chosen = []
    for topic, outcomes in groups.items():
        survivors, ask, sent_back = [], list(outcomes), []
        for attempt in range(2):
            passed = []
            for c in write(topic, ask, kept, approved[-RECENT_APPROVED:], rejected, sent_back):
                l = {"id": next_id(topic, taken), "text": c["text"], "topic": topic, "outcome": c["outcome"],
                     "noGauntlet": bridge.needs_gauntlet(c["text"], EVENTS[topic][2]), "placeholder": False}
                problems = bridge.check_roast_line(l, EVENTS, known + [s["text"] for s in survivors + passed + chosen], taken)
                if problems:
                    say(f"roast-writer: dropped \"{l['text']}\": {'; '.join(problems)}")
                else:
                    passed.append(l)
            sent_back = []
            if review and passed:
                for l, v in zip(passed, review(passed, describe)):
                    if v["verdict"] == "pass":
                        survivors.append(l)
                        if v.get("dropped"):
                            say(f"critic: kept \"{l['text']}\": its finding was dropped, {v['dropped']['dropped']}")
                    else:
                        sent_back.append((l["text"], v["problem"]))
                        say(f"critic: sent back \"{l['text']}\" against the GDD: {v['problem']}")
                say(f"critic: {len(passed) - len(sent_back)} of {len(passed)} {EVENTS[topic][0]} lines passed the GDD check")
            else:
                survivors += passed
            ask = [o for o in outcomes if not any(s["outcome"] == o for s in survivors)]
            if not ask:
                break
        for o in ask:
            say(f"roast-writer: no {EVENTS[topic][0]} line {OUTCOME_WORDS[o]} passed the checks, so that one is left out")
        chosen += pick(topic, survivors, outcomes, kept)
    if not chosen:
        raise CrewStop("no roast line passed the checks")

    folders = []
    root = common.SUBMISSIONS / FOLDER
    for c in chosen:
        l = {k: c[k] for k in ("text", "topic", "outcome", "noGauntlet", "placeholder")}
        l = {"id": next_id(l["topic"], taken), **l}
        problems = bridge.check_roast_line(l, EVENTS, known, taken)
        if problems:   # the picked lines were checked already; this only catches two picks too alike
            say(f"roast-writer: left out \"{l['text']}\": {'; '.join(problems)}")
            continue
        taken.add(l["id"])
        known.append(l["text"])
        folder = root / l["id"]
        folder.mkdir(parents=True, exist_ok=True)
        manifest = {"kind": KIND, "agent": AGENT, "name": l["text"], "label": l["text"], "description": describe(l),
                    "card": card["id"], "card_name": card["name"], "run": run_id, "score": c.get("score"), "line": l}
        tmp = folder / "manifest.tmp"
        tmp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        tmp.replace(folder / "manifest.json")   # the approvals pass only sees a whole manifest
        folders.append(folder)
        say(f"roast-writer: {l['id']} ({describe(l)}): {l['text']}")
    return folders


def store_approved():
    """Every approved line, in the game's own line format, in APPROVED. Returns how many."""
    approved = sorted((m["line"] for _, m, d in lines() if d and d.get("decision") == "approve"), key=lambda l: l["id"])
    out = {"lines": [{k: l[k] for k in ("id", "text", "topic", "outcome", "noGauntlet", "placeholder")} for l in approved]}
    text = json.dumps(out, indent=2)
    if (APPROVED.read_text(encoding="utf-8") if APPROVED.exists() else None) != text:
        APPROVED.parent.mkdir(parents=True, exist_ok=True)
        tmp = APPROVED.with_suffix(".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(APPROVED)
    return len(approved)
