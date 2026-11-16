"""THROWAWAY TEST (2026-11-13), not part of the game.

Step 1, second try: each shape is a few short questions the model answers in separate slots, and code puts the
answers into one sentence. One town, 10 rumors, first try only, no retries and no judge. David reads the results.

    python spikes/rumor_step2.py
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rm import cast  # noqa: E402
from rm.agents import BASE_SYSTEM, ENUM, OBJ, S, unknown_names  # noqa: E402
from rm.llm import Server  # noqa: E402
from rumor_backwards import RULES, SHAPE_KEYS, SHAPES, make_town  # noqa: E402

C = cast.CAST
ACT = "a short past-tense phrase starting with a verb, nothing violent, no stealing"

# Per shape: the questions (slot -> question). "person" slots are filled from the town's names.
QUESTIONS = {
    "secret_habit": {"habit": "the small, silly thing the player supposedly does in private, a short present-tense phrase "
                              "starting with a verb, nothing anyone is hurt by, no stealing",
                     "when": "when or how often they supposedly do it, a short phrase",
                     "witness": "the townsperson who supposedly caught them at it"},
    "fear": {"thing": "an ordinary, harmless thing the player is supposedly scared of, a short noun phrase",
             "reaction": f"what the player supposedly did when they saw it, {ACT}",
             "witness": "the townsperson who supposedly saw it"},
    "banned": {"owner": "the townsperson who supposedly banned the player from their place",
               "reason": f"the petty, embarrassing thing the player supposedly did there, {ACT}"},
    "crush": {"on": "the townsperson the player supposedly has a crush on",
              "giveaway": f"what the player supposedly did that gave the crush away, {ACT}"},
    "debt": {"to": "the townsperson the player supposedly owes",
             "amount": "how much, a small amount of money",
             "dodge": "how the player supposedly keeps dodging them, a short present-tense phrase starting with a verb"},
    "cheating": {"game": "the game, contest or bet the player supposedly cheated at, a short noun phrase",
                 "against": "the townsperson they supposedly cheated against",
                 "how": f"how they supposedly cheated, {ACT}"},
}
PERSON = {"witness", "owner", "on", "to", "against"}


LEADS = ("you ", "they ", "he ", "she ", "the player ", "secretly ")
SOFT_START = {"every", "each", "whenever", "when", "once", "twice", "always", "at", "on", "in", "the", "a", "an",
              "after", "before", "during", "late", "early", "all", "most", "only", "right", "by"}
STEALING = re.compile(r"\b(steal|steals|stealing|stole|stolen|theft|thief|thieves|swiped?|swiping|shoplift\w*|"
                      r"rob|robs|robbed|robbing|robbery|snatch\w*|pilfer\w*|nicked|pocketed)\b", re.I)
MAX_USES = 2


def ph(s: str) -> str:
    """Code tidies a slot answer so it fits the sentence: no leading pronoun, no doubled words, "your" not "their"."""
    s = s.strip().rstrip(".!").strip()
    changed = True
    while changed:
        changed = False
        for lead in LEADS:
            if s.lower().startswith(lead):
                s, changed = s[len(lead):], True
    s = re.sub(r"\btheir\b", "your", s)
    s = re.sub(r"\bthemselves\b", "yourself", s)
    s = re.sub(r"\bthe player's\b", "your", s, flags=re.I)
    first = s.split(" ", 1)[0].lower() if s else ""
    if first in SOFT_START:
        s = s[0].lower() + s[1:]
    return s


def known_words(town: dict, roles: dict) -> set[str]:
    """Proper nouns this town can use: the five, the places, the street, the jobs."""
    out = set()
    for c in C.values():
        out |= {w.lower() for w in c["name"].split()}
    for text in [town["street"]] + [town["places"][b]["name"] for b in cast.KIT_ORDER] + [roles[k]["job"] for k in cast.KEYS]:
        out |= {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z'\-]*", text.replace("'s", " "))}
    return out


def code_check(obj: dict, text: str, known: set[str], uses: dict) -> str | None:
    for k, v in obj.items():
        if k not in PERSON and STEALING.search(v):
            return f'"{v}" is stealing. No stealing.'
    bad = unknown_names(text, known)
    if bad:
        return f"{', '.join(bad)} isn't anyone in this town. Only use people from THE TOWN."
    for k, v in obj.items():
        if k in PERSON and uses.get(v, 0) >= MAX_USES:
            return f"{v} has been in too many rumors already. Pick someone else."
    return None


def sentence(shape: str, a: dict, roles: dict, by_name: dict) -> str:
    if shape == "secret_habit":
        return f"You secretly {ph(a['habit'])} {ph(a['when'])}, and {a['witness']} caught you."
    if shape == "fear":
        return f"You're so scared of {ph(a['thing'])} that you {ph(a['reaction'])}, and {a['witness']} saw it."
    if shape == "banned":
        return f"{a['owner']} banned you from {roles[by_name[a['owner']]]['place']} after you {ph(a['reason'])}."
    if shape == "crush":
        return f"You have a crush on {a['on']}, and you {ph(a['giveaway'])}."
    if shape == "debt":
        return f"You owe {a['to']} {ph(a['amount'])} and you {ph(a['dodge'])}."
    return f"You cheated {a['against']} at {ph(a['game'])}: you {ph(a['how'])}."


def main():
    srv = Server()
    if not srv.start():
        print(srv.error)
        return
    roles, town = make_town(srv)
    names = [C[k]["short"] for k in cast.KEYS]
    by_name = {C[k]["short"]: k for k in cast.KEYS}
    people = "\n".join(f"- {C[k]['name']}: {roles[k]['job']}, at {roles[k]['place']}." for k in cast.KEYS)
    known = known_words(town, roles)
    uses: dict[str, int] = {}
    rows = []
    for i in range(10):
        shape = SHAPE_KEYS[i % len(SHAPE_KEYS)]
        qs = QUESTIONS[shape]
        asks = "\n".join(f"- {k}: {q}" for k, q in qs.items())
        user = f"""THE TOWN:
{people}

{RULES}

THE KIND OF RUMOR: {SHAPES[shape]}

Answer each question in its own slot, as short as you can:
{asks}"""
        notes, sent_back, ms = "", None, 0
        for attempt in (1, 2):   # one retry when a code check sends it back
            free = names if attempt == 1 else [n for n in names if uses.get(n, 0) < MAX_USES]
            schema = OBJ({k: ENUM(free) if k in PERSON else S(100, 2) for k in qs})
            obj, stats = srv.call("rumor_step2", BASE_SYSTEM + "\nYou fill in the parts of the one rumor the player hears on Thursday morning.",
                                  user + notes, schema, max_tokens=150)
            ms += stats["ms"]
            if obj is None:
                text, reason = "(no valid answer)", "not valid JSON"
            else:
                text = sentence(shape, obj, roles, by_name)
                reason = code_check(obj, text, known, uses)
            if reason is None or attempt == 2:
                break
            sent_back = reason
            notes = f"\n\nYOUR LAST ANSWER WAS SENT BACK: {reason} Answer again and fix that."
        if obj:
            for k, v in obj.items():
                if k in PERSON:
                    uses[v] = uses.get(v, 0) + 1
        rows.append((shape, obj, text, ms, sent_back, reason))
        print(f"{i + 1}. {shape}: {text}   sent back: {sent_back}   still fails: {reason}", flush=True)
    srv.stop()
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    stamp = time.strftime("%Y-%m-%d_%H%M")
    md = [f"# Rumor test, step 1 with questions: {time.strftime('%Y-%m-%d %H:%M')}", "",
          "Throwaway test. Qwen3.5-4B. One town; each shape is a few short questions the model answers in slots, and code "
          "puts the answers into one sentence. Code checks for stealing, names not in the town and a person used more "
          "than twice, and sends a failure back once. No judge.", "",
          f"Town: {town['street']}. " + "; ".join(f"{C[k]['short']}, {roles[k]['job']} at {roles[k]['place']}" for k in cast.KEYS) + ".", ""]
    for i, (shape, obj, text, ms, sent_back, still) in enumerate(rows, 1):
        md.append(f"{i}. **{shape.replace('_', ' ')}:** {text} ({ms / 1000:.1f}s)")
        if obj:
            md.append("   - Slots: " + "; ".join(f"{k}: {v}" for k, v in obj.items()))
        if sent_back:
            md.append(f"   - Sent back once: {sent_back}")
        if still:
            md.append(f"   - Still fails a check: {still}")
    path = out / f"rumor_step2_{stamp}.md"
    path.write_text("\n".join(md) + "\n", encoding="utf-8")
    print("Report:", path)


if __name__ == "__main__":
    main()
