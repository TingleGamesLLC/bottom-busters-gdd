"""The LLM agents. Each has one narrow job, one prompt and one JSON schema.

Every output goes Generate -> Check -> Funny Gate -> Commit. A failed check sends it back
for a rewrite with the reason attached. After MAX_TRIES failures, code builds a plain line
from the ledger, or, for the agents that build the premise, the premise is thrown out.

Prompts are built from the tone guide, the cast sheets, the ledger and the JSON format
only. There are no story examples anywhere."""
from __future__ import annotations

import json
import re

from . import cast
from .funny import FunnyGate
from .llm import LLMUnavailable, english_only

C = cast.CAST
MAX_TRIES = cast.MAX_TRIES


class PremiseFailed(Exception):
    pass


BASE_SYSTEM = (
    cast.TONE_GUIDE + "\n\n" + cast.RAILS + "\n\n"
    "The player is never named. Talking TO the player, say 'you'. Talking ABOUT the player, say 'they'.\n"
    "Return only JSON that matches the schema."
)


# ====================================================================== schema helpers

def S(maxlen: int, minlen: int = 1) -> dict:
    return {"type": "string", "minLength": minlen, "maxLength": maxlen}

def ENUM(values) -> dict:
    return {"type": "string", "enum": list(values)}

def OBJ(props: dict, required=None) -> dict:
    return {"type": "object", "properties": props, "required": required or list(props), "additionalProperties": False}

def ARR(items: dict, mn: int, mx: int) -> dict:
    return {"type": "array", "items": items, "minItems": mn, "maxItems": mx}

BOOL = {"type": "boolean"}


# ====================================================================== text helpers

_STOP = {"that", "this", "with", "from", "they", "them", "their", "there", "were", "what", "when", "where", "which",
         "have", "just", "about", "into", "your", "you're", "then", "than", "been", "after", "before", "over",
         "once", "only", "some", "every", "very", "said", "says", "told", "heard", "also", "because", "while"}

def norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9$ ]", " ", str(s).lower())).strip()

def has_phrase(text: str, phrase: str) -> bool:
    p = norm(phrase)
    return bool(p) and f" {p} " in f" {norm(text)} "

def content_words(s: str) -> set[str]:
    return {w for w in norm(s).split() if len(w) > 3 and w not in _STOP}

def stems(s: str) -> set[str]:
    return {w[:5] for w in content_words(s)}

def overlaps(a: str, b: str, n: int = 1) -> bool:
    return len(stems(a) & stems(b)) >= n

def detail_in(text: str, detail: str) -> bool:
    """Is this exact small detail (a time, an amount, an object) in the text?"""
    nd, nt = norm(detail), f" {norm(text)} "
    if not nd:
        return False
    if f" {nd} " in nt:
        return True
    toks = nd.split()
    nums = [t for t in toks if any(ch.isdigit() for ch in t)]
    if nums:
        return all(f" {t} " in nt for t in nums)
    words = [t for t in toks if len(t) > 3 and t not in _STOP]
    if not words:
        return False
    return sum(f" {w} " in nt for w in words) >= max(1, round(len(words) * 0.6))

def place_in(text: str, place: str) -> bool:
    """Does the text name this place? The full name, or most of its distinctive words."""
    if has_phrase(text, place):
        return True
    words = [w for w in content_words(place) if w not in {"house", "shop", "tavern", "theater", "dock", "docks", "shed"}]
    if not words:
        return False
    nt = f" {norm(text)} "
    return sum(f" {w} " in nt for w in words) >= max(1, round(len(words) * 0.6))

def has_key(text: str, key: str, kind: str) -> bool:
    """Is a tell's key in the text? kind is 'detail', 'place' or 'name'."""
    if kind == "detail":
        return detail_in(text, key)
    if kind == "place":
        return place_in(text, key)
    return re.search(rf"\b{re.escape(key)}\b", text, re.I) is not None

def has_marker(text: str, key: str) -> bool:
    t = text.lower()
    return any(m in t for m in C[key]["markers"])

def strings_ok(obj) -> str | None:
    """Return a reason if any string is not plain English."""
    if isinstance(obj, dict):
        for v in obj.values():
            r = strings_ok(v)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = strings_ok(v)
            if r:
                return r
    elif isinstance(obj, str):
        if not english_only(obj):
            return "Use plain English only."
    return None

_NAMES = sorted({c["name"] for c in C.values()} | {c["short"] for c in C.values()}, key=len, reverse=True)
_SPEAKER_PREFIX = re.compile(r"^\s*(?:" + "|".join(re.escape(n) for n in _NAMES) + r")\s*:\s*")

def tidy(obj):
    """Strip quote marks and speaker names the model sometimes wraps spoken lines in."""
    if isinstance(obj, dict):
        return {k: tidy(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [tidy(v) for v in obj]
    if isinstance(obj, str):
        s = obj.strip()
        s = _SPEAKER_PREFIX.sub("", s)
        while len(s) > 1 and s[0] in "\"'“" and s[-1] in "\"'”" and s.count(s[0]) <= 2:
            s = s[1:-1].strip()
        for q in "\"“”":   # a lone quote mark at either end
            if s.count(q) == 1 and (s.startswith(q) or s.endswith(q)):
                s = s.strip(q).strip()
        return s
    return obj


_DAYS = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
_ALWAYS_OK = _DAYS | {"i", "i'm", "i'd", "i'll", "i've", "ok", "okay", "oh", "mr", "mrs", "ms", "miss", "sir",
                      "ma'am", "god", "lord", "heavens", "hey", "whoa", "wow", "yes", "no", "and", "the",
                      "daily", "whisper", "am", "pm", "town", "dear", "darling", "pal", "buddy", "folks"}

def unknown_names(line: str, known: set[str]) -> list[str]:
    """Capitalized words in the middle of a sentence that aren't a person or place in this town."""
    out = []
    prev_end = ""
    for m in re.finditer(r"[A-Za-z][A-Za-z'\-]*", line):
        w = m.group(0)
        before = line[:m.start()].rstrip()
        initial = (not before) or before[-1] in ".!?:\"“—(-"
        if w[0].isupper() and not w.isupper() and not initial:
            base = w.lower().rstrip("'-")
            if base.endswith("'s"):
                base = base[:-2]
            if base not in known and base not in _ALWAYS_OK:
                out.append(w)
    return out


_NOTE_FIELDS = {"note", "reason", "about"}   # a judge's own notes; nobody reads them in the game

def cut_off(obj, schema, path: str = "") -> str | None:
    """A string that hit its schema's length limit was cut off mid-sentence by the grammar."""
    if isinstance(obj, dict) and schema.get("type") == "object":
        for k, v in obj.items():
            r = cut_off(v, schema.get("properties", {}).get(k, {}), k)
            if r:
                return r
    elif isinstance(obj, list) and schema.get("type") == "array":
        for v in obj:
            r = cut_off(v, schema.get("items", {}), path)
            if r:
                return r
    elif isinstance(obj, str) and schema.get("maxLength") and "enum" not in schema and path not in _NOTE_FIELDS:
        if len(obj) >= schema["maxLength"]:
            return f'"{path}" ran over the length limit ({schema["maxLength"]} characters) and got cut off. Keep it shorter.'
    return None


# Catchphrases that belong to one person. Nobody else says them.
SIGNATURE = {"toby": [], "mildred": ["you know what else"], "bev": ["nearly died", "can't even"],
             "ozzie": ["trust me", "i would never"], "gary": []}

PLUG = re.compile(r"(\$|\bcents?\b|\bspecials?\b|tell your friends|half off|two for (one|a)|buy one|on sale|discount|"
                  r"\bdollars?\b|\bbucks\b|\bnickel\b|\bdime\b|\bpennies\b|\bprices?\b|\bdeal\b)", re.I)

def catch_hint(key: str) -> str:
    """Catchphrases are optional: forcing one into every line made nonsense."""
    c = C[key]
    return f" You can use {c['say']} if it fits naturally; never force it." if c["say"] else ""

def borrowed(line: str, key: str) -> str | None:
    t = line.lower().replace("’", "'")
    if key == "toby" and PLUG.search(t):
        return "Toby never plugs his lemonade: no prices, specials, deals or 'tell your friends'."
    for other, phrases in SIGNATURE.items():
        if other != key:
            for p in phrases:
                if p in t:
                    own = f"Use only {C[key]['short']}'s own fingerprint." if key in C else "Leave it out."
                    return f'"{p}" is {C[other]["short"]}\'s catchphrase. {own}'
    return None

def scrub(text: str, key: str | None) -> str:
    """Take other people's catchphrases out of a rumor before handing it to a speaker, so the
    speaker retells the story without borrowing anyone's fingerprint."""
    parts = re.split(r"(?<=[.!?])\s+", text)
    keep = [p for p in parts if not borrowed(p, key or "")]
    if keep:
        return " ".join(keep)
    out = text
    for other, phrases in SIGNATURE.items():
        if other != key:
            for p in phrases:
                out = re.sub(rf"(,?\s*(and\s+)?(i\s+)?){re.escape(p).replace(chr(39), '.?')}\w*", "", out, flags=re.I)
    return re.sub(r"\s{2,}", " ", out).strip()


# ====================================================================== the loop

def run(server, agent: str, system: str, user: str, schema: dict, check, fallback=None, *,
        mode: str = "creative", max_tokens: int = 400, label: str = "",
        gate: FunnyGate | None = None, visible=None, critic_context: str = "", who=None) -> tuple[dict, str]:
    """Generate -> Check -> Funny Gate -> Commit.

    Returns (result, source): "model", "model (critic kept)" when every try passed the checks but
    not the Comedy Critic (the best-scoring one is used), or "code" for a plain line built from
    the ledger. With no fallback, failing every try throws out the premise."""
    notes = ""
    best = None
    last = ""
    for attempt in range(1, MAX_TRIES + 1):
        try:
            obj, stats = server.call(agent, system, user + notes, schema, mode=mode, max_tokens=max_tokens)
        except LLMUnavailable as e:
            server.record({"agent": agent, "label": label, "attempt": attempt, "ok": False, "note": f"model unavailable: {e}",
                           "source": "-", "ms": 0, "tokens_per_sec": 0, "json_ok": False})
            last = f"the model is unavailable ({e})"
            break
        reason = None
        lines = []
        if obj is None:
            reason = "That was not valid JSON."
        else:
            obj = tidy(obj)
            reason = strings_ok(obj) or cut_off(obj, schema) or check(obj)
            if reason is None and gate is not None and visible is not None:
                lines = [l for l in visible(obj) if l]
                reason = gate.code_check(lines)
        server.record({**stats, "label": label, "attempt": attempt, "ok": reason is None,
                       "note": reason or "pass", "source": "model", "output": obj})
        if reason is None and gate is not None and lines:
            ok, cnotes, verdicts = gate.critic(server, lines, critic_context or f"Speaker: {label}", label)
            if not ok:
                score = min((v["score"] for v in verdicts), default=0)
                if best is None or score > best[0]:
                    best = (score, obj, lines)
                reason = "The Comedy Critic sent it back: " + cnotes
        if reason is None:
            if gate is not None and lines:
                gate.commit(lines, label, who)
            return obj, "model"
        last = reason
        notes = f"\n\nYOUR LAST ANSWER WAS SENT BACK: {reason} Write it again and fix that."
    if best is not None:
        gate.commit(best[2], label, who)
        server.record({"agent": agent, "label": label, "attempt": "-", "ok": True,
                       "note": f"kept the line the Critic scored best ({best[0]}/5)", "source": "model (critic kept)",
                       "ms": 0, "tokens_per_sec": 0, "json_ok": True, "output": best[1]})
        return best[1], "model (critic kept)"
    if fallback is None:
        raise PremiseFailed(f"{agent} ({label}) failed {MAX_TRIES} times: {last}")
    result = fallback() if callable(fallback) else fallback
    if gate is not None and visible is not None:
        gate.commit([l for l in visible(result) if l], label, who)
    server.record({"agent": agent, "label": label, "attempt": "-", "ok": True, "note": "built a plain line from the ledger",
                   "source": "code", "ms": 0, "tokens_per_sec": 0, "json_ok": True, "output": result})
    return result, "code"


# ====================================================================== sheets

def sheet(key: str, roles: dict | None = None) -> str:
    c = C[key]
    s = (f"{c['name']}, {c['type']}. Voice: {c['voice']}. What they do to a rumor: {c['does']}. "
         f"Fingerprint: {c['fingerprint']}. Look: {c['look']}.")
    if roles and key in roles and roles[key].get("job"):
        r = roles[key]
        s += f" This game: {r['job']}" + (f", at {r['place']}" if r.get("place") else "") + "."
    return s

def relations_text(key: str, roles: dict) -> str:
    r = roles[key]
    out = []
    if r.get("friend"):
        out.append(f"good friends with {C[r['friend']]['short']}")
    if r.get("owes") and r["owes"] != "nobody":
        out.append(f"owes {C[r['owes']]['short']} ({r['owes_what']})")
    if r.get("cant_stand"):
        out.append(f"can't stand {C[r['cant_stand']]['short']}")
    return ", ".join(out) or "you know everyone on the street"

def dna_text(dna: dict) -> str:
    out = []
    for k in ["subject", "act", "scale", "place", "time"]:
        out.append(f'  {k}: "{dna[k]}"')
    out.append("  extras: " + (json.dumps(dna["extras"]) if dna["extras"] else "[] (none yet)"))
    return "\n".join(out)

def critic_ctx(keys, roles: dict | None, what: str) -> str:
    keys = [keys] if isinstance(keys, str) else list(keys)
    who = "\n".join(f"- {sheet(k, roles)}" for k in keys)
    return f"WHAT THESE LINES ARE: {what}\nWHO SAYS THEM:\n{who}"


# ====================================================================== night shift: the premise

def casting_director(server) -> tuple[dict, str]:
    """Casting Director: this game's job, workplace, friend, debt, grudge and secret for each actor."""
    per = {}
    for k in cast.KEYS:
        others = [o for o in cast.KEYS if o != k]
        per[k] = OBJ({
            "job": S(50, 3),
            "building": ENUM(cast.KIT_ORDER),
            "friend": ENUM(others),
            "owes": ENUM(others + ["nobody"]),
            "owes_what": S(70, 2),
            "cant_stand": ENUM(others),
            "secret": S(160, 10),
        })
    schema = OBJ({"roles": OBJ(per)})
    actors = "\n".join(f"- {k}: {C[k]['name']}, {C[k]['type']}. Voice: {C[k]['voice']}. Look: {C[k]['look']}." for k in cast.KEYS)
    kit = ", ".join(b.replace("_", " ") + f" ({b})" for b in cast.KIT_ORDER)
    user = f"""THE FIVE ACTORS. Like a theater troupe, they play new roles every game.
{actors}

THE STREET: five buildings, one person each: {kit}. Every building goes to exactly one person.

Cast this game's roles. For each actor:
- job: their job this game, 1 to 4 words, like a name tag would say. A real small-town job (what they do all day) that makes sense in their building, not a joke about their type or look.
- building: where they work or live, from the list. Each building is used exactly once.
- friend: who they're friends with.
- owes: who they owe something to, or "nobody". owes_what: what they owe, a few words, or "nothing".
- cant_stand: who they can't stand. Not their friend.
- secret: one small, harmless, embarrassing secret they'd hate to get out. It has nothing to do with the player."""

    def check(o):
        roles = o["roles"]
        b = [roles[k]["building"] for k in cast.KEYS]
        if sorted(b) != sorted(cast.KIT_ORDER):
            dup = sorted({x for x in b if b.count(x) > 1})
            return f"Each building goes to exactly one person. These were used twice: {', '.join(dup)}."
        for k in cast.KEYS:
            if roles[k]["friend"] == roles[k]["cant_stand"]:
                return f"{C[k]['short']} can't be friends with the person they can't stand."
        jobs = [norm(roles[k]["job"]) for k in cast.KEYS]
        if len(set(jobs)) < 5:
            return "Give everyone a different job."
        for k in cast.KEYS:
            if len(roles[k]["job"].split()) > 4:
                return f'{C[k]["short"]}\'s job "{roles[k]["job"]}" is a sentence. Give a job title, 1 to 4 words.'
        return None

    return run(server, "casting_director", BASE_SYSTEM + "\nYou are the Casting Director.", user, schema, check,
               None, max_tokens=900, label="this game's roles")


def town_architect(server, roles: dict) -> tuple[dict, str]:
    """Town Architect: names the five places on the street and picks the shop's rooftop prop."""
    by_building = {roles[k]["building"]: k for k in cast.KEYS}
    schema = OBJ({
        "street": S(40, 3),
        "places": OBJ({b: OBJ({"name": S(40, 3), "works_or_lives": ENUM(["works", "lives"])}) for b in cast.KIT_ORDER}),
        "roof_prop": ENUM(cast.ROOF_PROPS),
    })
    lines = "\n".join(f"- {b} (a {b.replace('_', ' ')}): {C[by_building[b]]['name']}, {roles[by_building[b]]['job']}"
                      for b in cast.KIT_ORDER)
    user = f"""THE BUILDINGS on the street, and who is in each one this game:
{lines}

Lay out the town:
- street: the name of the street.
- places: a name for each building, 2 to 5 words, the way its sign or the neighbors would say it: a real business name for a workplace, or whose house it is for a home. Specific, with a little wit. Say whether the person works or lives there.
- roof_prop: the giant prop on the shop's roof, from the list. It should fit what the shop sells."""

    def check(o):
        names = [norm(o["places"][b]["name"]) for b in cast.KIT_ORDER]
        if len(set(names)) < 5:
            return "Every place needs a different name."
        for b in cast.KIT_ORDER:
            name = o["places"][b]["name"]
            if len(name.split()) > 6:
                return f'"{name}" is too long. 2 to 5 words.'
            for k in cast.KEYS:
                if k != by_building[b] and re.search(rf"\b{C[k]['short']}\b", name, re.I):
                    return f'"{name}" names {C[k]["short"]}, but {C[by_building[b]]["short"]} is the one there.'
        return None

    obj, src = run(server, "town_architect", BASE_SYSTEM + "\nYou are the Town Architect.", user, schema, check,
                   None, max_tokens=500, label="the street")
    for b in cast.KIT_ORDER:
        obj["places"][b]["who"] = by_building[b]
    return obj, src


_CRIME = re.compile(r"\b(steal\w*|stole\w*|theft|thie\w*|rob|robb\w*|burgl\w*|assault\w*|vandal\w*|arson|"
                    r"fraud\w*|smuggl\w*|kidnap\w*|break(s|ing)? in|broke into|shoplift\w*|pickpocket\w*|embezzl\w*|"
                    r"brib\w*|forg(e|ed|ery)|counterfeit\w*|poison\w*|trespass\w*|arrest\w*|crime\w*|illegal\w*)\b", re.I)

def history_seeder(server, roles: dict, town: dict, carryover: list[str]) -> tuple[dict, str]:
    """History Seeder: 5 to 10 small, boring true events from the last two days."""
    who_enum = ["you"] + cast.KEYS
    event = OBJ({
        "who": ENUM(who_enum),
        "what": S(110, 5),
        "how_much": S(70, 1),
        "where": ENUM(cast.KIT_ORDER),
        "when": ENUM(cast.SLOTS),
        "with": ARR(ENUM(who_enum), 0, 2),
        "detail": S(80, 2),
        "text": S(260, 10),
        "from_last_time": BOOL,
    })
    schema = OBJ({"events": ARR(event, cast.EVENTS_MIN, cast.EVENTS_MAX)})
    people = "\n".join(f"- {k}: {C[k]['name']}, {roles[k]['job']}, at {roles[k]['place']}" for k in cast.KEYS)
    places = "\n".join(f"- {b}: {town['places'][b]['name']} ({town['places'][b]['who']} {town['places'][b]['works_or_lives']} there)"
                       for b in cast.KIT_ORDER)
    last = ""
    if carryover:
        last = ("\nWHAT THE PLAYER REALLY DID LAST TIME (it happened, so it's true). Retell at least one of these as an event "
                "in this town, and mark it from_last_time:\n" + "\n".join(f"- {a}" for a in carryover) + "\n")
    user = f"""THE PEOPLE (and "you", the player, who lives in town):
{people}

THE PLACES:
{places}

WHEN: {", ".join(cast.SLOTS)}.
{last}
Write 6 to 8 small, boring, true events from Tuesday and Wednesday. Ordinary town life: errands, chores, small mix-ups.
- At least {cast.EVENTS_ABOUT_YOU} involve the player ("you" as who, or in with), and at least two of those happen by Wednesday morning.
- The player is never guilty of anything, and nothing is a crime.
- Mix in events about the other people too.

For each event:
- who: who did it.
- what: what they did, a short past-tense phrase with no name in front of it (it follows the person's name), and no place or time in it.
- how_much: how much or how many, and how often.
- where, when: from the lists.
- with: who else was there, 0 to 2 (never the same as who).
- detail: one tiny, exact detail only someone who was there would know, 2 to 6 words: an exact time, amount, color or object.
- text: one plain sentence that says all of it, including the detail. Call the player "you".
- from_last_time: true only for an event that retells something the player really did last time."""

    def check(o):
        ev = o["events"]
        about_you = [e for e in ev if e["who"] == "you" or "you" in e["with"]]
        if len(about_you) < cast.EVENTS_ABOUT_YOU:
            return f"At least {cast.EVENTS_ABOUT_YOU} events must involve the player."
        if sum(1 for e in about_you if cast.SLOTS.index(e["when"]) <= 3) < 2:
            return "At least two of the player's events must happen by Wednesday morning."
        for i, e in enumerate(ev, 1):
            if e["who"] in e["with"] or len(set(e["with"])) != len(e["with"]):
                return f"Event {i}: 'with' lists who else was there, never the same person twice or the person in 'who'."
            m = _CRIME.search(e["what"] + " " + e["text"] + " " + e["how_much"])
            if m:
                return f'Event {i}: "{m.group(0)}" sounds like a crime. These are small, boring, legal events.'
            pname = town["places"][e["where"]]["name"]
            if place_in(e["what"], pname):
                return f"Event {i}: 'what' leaves out the place ({pname}); that goes in 'where'."
            first = norm(e["what"]).split()[:1]
            if first and (first[0] in {"you", "they", "he", "she"} or first[0] in {c["short"].lower() for c in C.values()}):
                return f"Event {i}: 'what' starts with no name or pronoun; it follows the person's name."
        if carryover and not any(e["from_last_time"] for e in ev):
            return "Retell at least one thing the player really did last time, and mark it from_last_time."
        return None

    return run(server, "history_seeder", BASE_SYSTEM + "\nYou are the History Seeder. You write what really happened.",
               user, schema, check, None, max_tokens=1600, label="true events")


SPIN_CHANGE = {
    "toby": 'adds ONE plug for what he sells to "extras" (a price or a special)',
    "bev": 'adds ONE emotional, theatrical detail to "extras"',
    "gary": 'makes "scale" bigger: more of it, more often, more people',
    "mildred": 'merges the other true event, "{merge}", into "act"',
    "ozzie": 'swaps the name on purpose and makes it about the player: new_value is "the player"',
}

TWIST_TEXT = {
    "none": ("No twist. The source tells it because of their relationships (a grudge, a debt, a friendship) or an honest "
             "misunderstanding. Not a stunt."),
    "victim_stunt": ("The twist: the person the rumor makes look wronged started it themselves, as a stunt for their own gain "
                     "(attention, customers, sympathy). The why must say what they gain."),
}

def spin(server, kernel: dict, dna: dict, candidates: list[str], twist: str, roles: dict, merge_text: str) -> tuple[dict, str]:
    """Spin Agent: who starts the rumor, why, and its first version."""
    schema = OBJ({"source": ENUM(candidates), "why": S(180, 10), "new_value": S(120, 2), "new_version": S(260, 20)})
    who = "\n".join(f"- {k}: {sheet(k, roles)} {relations_text(k, roles).capitalize()}. Their one change: "
                    + SPIN_CHANGE[k].format(merge=merge_text) + "." for k in candidates)
    about = "the player (say \"they\")" if dna["subject"] == "the player" else dna["subject"]
    user = f"""THE TRUE EVENT: {kernel['text']}
The exact detail only people who were there know: "{kernel['detail']}". Keep it OUT of the rumor.

Story fields right now:
{dna_text(dna)}

WHO COULD START THIS RUMOR (they were there):
{who}

{TWIST_TEXT[twist]}

THE RULE: exactly one change, in the source's style. Every other field stays true.
A rumor is juicy: the change makes whoever it's about look worse or more ridiculous.

Write:
- source: who starts it.
- why: one sentence on why they start it.
- new_value: their one change, a few words.
- new_version: what they say out loud the first time they tell it. One or two short sentences, under 40 words, in their voice, with their fingerprint. It's about {about}, unless Ozzie makes it about the player."""

    def check(o):
        k = o["source"]
        field = C[k]["field"]
        if not has_marker(o["new_version"], k):
            return f"{C[k]['short']} always uses their fingerprint in new_version: {C[k]['fingerprint']}."
        if detail_in(o["new_version"], kernel["detail"]):
            return f'Keep the exact detail "{kernel["detail"]}" out of the rumor.'
        if field == "act":
            if not overlaps(o["new_value"], merge_text):
                return f'Mildred merges in the other true event: "{merge_text}". Put it in new_value.'
        elif field == "scale":
            if norm(o["new_value"]) == norm(dna["scale"]):
                return 'new_value must make "scale" bigger.'
        if not overlaps(o["new_version"], dna["act"] + " " + (o["new_value"] if field == "act" else "")):
            return "Keep what happened in new_version."
        return None

    obj, src = run(server, "spin", BASE_SYSTEM + "\nYou are the Spin Agent. You turn a boring true event into the first version of a rumor.",
                   user, schema, check, None, max_tokens=420, label="who starts it")
    if C[obj["source"]]["field"] == "subject":
        obj["new_value"] = "the player"
    return obj, src


MUTATION_HELP = {
    "merge": 'Merge the other true event going around town, "{merge}", into the "act" field. The new act blames {subject} for both.',
    "exaggerate": 'Make the "scale" field bigger: more of it, more often, more people.',
    "add_detail:toby": 'Add ONE new detail to "extras", and it must be a plug for what Toby sells as {job} (a price or a special).',
    "add_detail:bev": 'Add ONE new emotional, theatrical detail to "extras": something that supposedly happened because of it.',
    "swap_name_on_purpose": ('Swap the name on purpose. The rumor is about {subject}; Ozzie makes it about the player instead. '
                             'new_value is "the player". He tells it about the player ("they").'),
}

def mutate(server, key: str, prev_key: str, prev_line: str, dna: dict, roles: dict, heard: str, telling: str,
           merge_text: str, detail: str) -> tuple[dict, str]:
    """Mutation Agent: exactly one change in the teller's style."""
    c = C[key]
    field = c["field"]
    nv = ENUM(["the player"]) if field == "subject" else S(120, 2)
    schema = OBJ({"new_value": nv, "new_version": S(260, 20)})
    help_key = f"add_detail:{key}" if c["mutation"] == "add_detail" else c["mutation"]
    help_text = MUTATION_HELP[help_key].format(merge=merge_text, subject=dna["subject"], job=roles[key]["job"])
    about = "the player (say \"they\")" if (dna["subject"] == "the player" or field == "subject") else dna["subject"]
    user = f"""THE RUMOR SO FAR, as {C[prev_key]['name']} told it to {c['name']} ({heard}):
"{scrub(prev_line, key)}"

Story fields right now:
{dna_text(dna)}

THE SPEAKER: {sheet(key, roles)}
WHO THEY'RE TELLING, AND WHERE: {telling}

THE RULE: exactly one change per mouth. {c['short']} changes ONLY the "{field}" field. {help_text}
Every other field stays the same. The change makes it juicier: whoever it's about looks worse or more ridiculous.

Write:
- new_value: the new value of "{field}"{'. Just the ONE new detail, in a few words. Do not repeat the old extras.' if field == 'extras' else '.'}
- new_version: what {c['short']} says out loud when passing it on. One or two short sentences, under 40 words, in their voice. It MUST include {c['say']}. Keep the rest of the story in it too (what happened, how much and how often, where). It's about {about}."""

    def check(o):
        nv_ = o["new_value"].strip()
        if field == "extras":
            low = nv_.lower()
            for e in dna["extras"]:
                el = e.lower()
                if low == el or el in low or low in el or overlaps(low, el, 3):
                    return "new_value must be ONE NEW detail, not a repeat of the old extras."
        elif field != "subject" and norm(nv_) == norm(dna[field]):
            return f'new_value must change "{field}".'
        if field == "act" and not overlaps(nv_, merge_text):
            return f'Merge in the other true event: "{merge_text}".'
        if not has_marker(o["new_version"], key):
            return f"Use {c['short']}'s fingerprint in new_version: {c['fingerprint']}."
        b = borrowed(o["new_version"], key)
        if b:
            return b
        if has_marker(prev_line, "gary") and field != "scale" and not has_marker(o["new_version"], "gary"):
            return f'Keep how much and how often in new_version ("{dna["scale"]}"), in words like "every day".'
        if detail and detail_in(o["new_version"], detail):
            return f'Leave out "{detail}". Nobody in the chain knows that detail.'
        return None

    def fallback():
        return {"new_value": plain_change(key, dna, roles, merge_text), "new_version": ""}

    obj, src = run(server, "mutation", BASE_SYSTEM + "\nYou are the Mutation Agent. You pass a rumor on with exactly one change, in the teller's style.",
                   user, schema, check, fallback, max_tokens=360, label=f"{C[prev_key]['short']} -> {c['short']}")
    return obj, src


def plain_change(key: str, dna: dict, roles: dict, merge_text: str) -> str:
    """Code builds a plain one-field change from the ledger when the Mutation Agent keeps failing."""
    m = C[key]["mutation"]
    if m == "exaggerate":
        return f"{dna['scale']}, every single day"
    if m == "merge":
        return f"{dna['act']}, and also {merge_text}"
    if m == "swap_name_on_purpose":
        return "the player"
    if key == "toby":
        return f"{roles['toby']['place']} has a special on this week"
    return "someone fainted when they heard"


def consistency(server, key: str, before: dict, after: dict, line: str) -> tuple[dict, str]:
    """Consistency Agent, LLM half: does the spoken line change anything besides the one allowed field?"""
    c = C[key]
    schema = OBJ({
        "line_matches_story": BOOL,
        "other_field_changed": BOOL,
        "verdict": ENUM(["pass", "fail"]),
        "note": S(160),
    })
    user = f"""A rumor just passed from one person to the next. The rule is one change per mouth.
Flavor, jokes, attitude and saying the same thing in other words are all fine.

Allowed change: the "{c['field']}" field ({c['mutation']}).

Story fields BEFORE:
{dna_text(before)}

Story fields AFTER:
{dna_text(after)}

What {c['short']} said: "{line}"

- line_matches_story: does what they said fit the AFTER fields? It doesn't have to mention every field.
- other_field_changed: does what they said change a DIFFERENT field than "{c['field']}"? For example a different day, a different place, or a different person.
verdict is "pass" when line_matches_story is true and other_field_changed is false. Otherwise "fail". note: one short sentence."""

    def check(o):
        expect = "pass" if (o["line_matches_story"] and not o["other_field_changed"]) else "fail"
        if o["verdict"] != expect:
            return "verdict must follow the two answers."
        return None

    return run(server, "consistency", BASE_SYSTEM + "\nYou are the Consistency Agent. You check rumors against the ledger.",
               user, schema, check, {"line_matches_story": True, "other_field_changed": False, "verdict": "pass",
                                      "note": "the check couldn't decide, so code passed it"},
               mode="judge", max_tokens=200, label=f"check {c['short']}")


def code_check(before: dict, after: dict, field: str) -> str | None:
    """Consistency Agent, code half: exactly one field differs, and it's the allowed one."""
    changed = [k for k in before if before[k] != after[k]]
    if changed != [field]:
        return f"changed {changed}, allowed only {field}"
    if field == "extras" and after["extras"][:-1] != before["extras"]:
        return "extras must only append one item"
    return None


def red_herring(server, spec: dict, roles: dict, places: list[str]) -> tuple[dict, str]:
    """Red Herring Agent: writes one lie, its alibi and the tell that lets a sharp player catch it.

    spec: liar, kind ('self' | 'cover_teller' | 'alibi'), truth, why_hint, options, real_where,
    real_when, tell_key (what the tell must contain, word for word), tell_what."""
    k = spec["liar"]
    c = C[k]
    other_places = [p for p in places if p != spec["real_where"]]
    if spec["kind"] == "alibi":
        schema = OBJ({"claimed_where": ENUM(other_places), "lie": S(220, 10), "alibi": S(200, 10),
                      "why": S(160, 10), "tell": S(220, 10)})
        write = f"""- claimed_where: where they claim {C[spec['covering_for']]['short']} was with them at that time.
- lie: one sentence: the false alibi they give their friend.
- alibi: what they say, in their voice, oddly specific, about where they both were {spec['real_when']}.
- why: why they lie.
- tell: the slip that gives them away, in their own words, first person: {spec['tell_what']}. It must include "{spec['tell_key']}" word for word."""
    else:
        opts = spec["options"]
        schema = OBJ({"claimed_source": ENUM(opts), "claimed_where": ENUM(other_places + ["somewhere they can't remember"]),
                      "claimed_when": ENUM(cast.SLOTS), "lie": S(220, 10), "alibi": S(200, 10),
                      "why": S(160, 10), "tell": S(220, 10)})
        names = ", ".join(("someone they can't remember" if o == "someone_i_cant_remember" else f"{o} ({C[o]['short']})") for o in opts)
        write = f"""- claimed_source: who they SAY told them this rumor. One of: {names}.
- claimed_where, claimed_when: where and when they say that happened.
- lie: one sentence: who they claim told them this rumor, and where.
- alibi: an oddly specific alibi in their voice for {spec['real_when']}, putting them anywhere but {spec['real_where']}.
- why: why they lie.
- tell: the slip that gives them away, in their own words, first person: {spec['tell_what']}. It must include "{spec['tell_key']}" word for word."""
    user = f"""THE LIAR: {sheet(k, roles)}
THE RUMOR: "{spec['rumor']}"
THE TRUTH THEY'RE HIDING: {spec['truth']}
WHY THEY LIE: {spec['why_hint']}
PLACES IN TOWN: {", ".join(places)}

Write their lie, so a sharp player can catch it:
{write}"""

    def check(o):
        if not has_key(o["tell"], spec["tell_key"], spec["tell_kind"]):
            return f'The tell must include "{spec["tell_key"]}" word for word.'
        if place_in(o["alibi"], spec["real_where"]) or place_in(o["lie"], spec["real_where"]):
            return f"The lie and the alibi must put them somewhere other than {spec['real_where']}."
        if spec["kind"] == "cover_teller":
            t = C[spec["covering_for"]]["short"]
            if re.search(rf"\b{t}\b", o["lie"] + " " + o["alibi"], re.I):
                return f"The lie hides that {t} told them. Don't mention {t} in the lie or the alibi."
        if spec["kind"] == "self" and any(p in o["lie"].lower() for p in ("i started", "made it up", "it was me")):
            return "The lie must not admit anything."
        return None

    def fallback():
        if spec["tell_kind"] == "detail":
            tell = f"It was {spec['tell_key']}, wasn't it? Or so I'd imagine."
        elif spec["tell_kind"] == "name":
            tell = f"{spec['tell_key']} did drop by {spec['real_where']}, {spec['real_when']}, now that I think of it."
        else:
            tell = f"I was at {spec['tell_key']}, {spec['real_when']}, now that I think of it."
        lie = {"claimed_where": other_places[0], "why": spec["why_hint"], "tell": tell}
        if spec["kind"] == "alibi":
            lie["lie"] = f"{c['short']} says {C[spec['covering_for']]['short']} was with them at {other_places[0]}, {spec['real_when']}."
            lie["alibi"] = f"We were at {other_places[0]} all {spec['real_when']}. Both of us. {c['phrase']}"
        else:
            src = spec["options"][0]
            name = "someone they can't remember" if src == "someone_i_cant_remember" else C[src]["short"]
            lie.update({"claimed_source": src, "claimed_when": spec["real_when"],
                        "lie": f"{c['short']} says {name} told them, at {other_places[0]}.",
                        "alibi": f"I was at {other_places[0]} all {spec['real_when']}. {c['phrase']}"})
        return lie

    obj, src = run(server, "red_herring", BASE_SYSTEM + "\nYou are the Red Herring Agent. You write lies that a sharp player can catch.",
                   user, schema, check, fallback, max_tokens=520, label=f"{c['short']}'s lie")
    return obj, src


def evidence_writer(server, kernel: dict, place: str) -> tuple[dict, str]:
    """Evidence: what the player is holding that proves the true event."""
    schema = OBJ({"kind": ENUM(list(cast.EVIDENCE)), "title": S(50, 3), "lines": ARR(S(60, 2), 2, 5)})
    kinds = "\n".join(f"- {k}: {v}" for k, v in cast.EVIDENCE.items())
    day = kernel["when"].split()[0]
    user = f"""THE TRUE EVENT: {kernel['text']}
Where: {place}. When: {kernel['when']}. The exact detail: "{kernel['detail']}".

The player is holding one piece of evidence that proves what really happened. Pick its kind:
{kinds}

Write it the way the real thing would read, written by whoever really would have written it (a shop, a ticket booth, someone who was there). Plain and factual, short lines.
- title: what it is, a few words.
- lines: 2 to 5 short lines of its text. They must include the exact detail "{kernel['detail']}", the day ({day}) and where it happened."""

    def check(o):
        text = " ".join([o["title"]] + o["lines"])
        if not detail_in(text, kernel["detail"]):
            return f'Include the exact detail "{kernel["detail"]}".'
        if day.lower() not in text.lower():
            return f"Include the day, {day}."
        if not place_in(text, place):
            return f"Include where it happened: {place}."
        return None

    def fallback():
        return {"kind": "note", "title": f"A note from {place}",
                "lines": [kernel["what"], kernel["how_much"], kernel["detail"], f"{place}, {kernel['when']}"]}

    return run(server, "evidence", BASE_SYSTEM + "\nYou write the evidence the player holds.", user, schema, check,
               fallback, max_tokens=260, label="your evidence")


# ====================================================================== night shift: the lines

GIVEAWAY_SELF = ["it was me", "i started", "started it", "started the rumor", "started this", "i made it up", "made it up",
                 "my idea", "i invented", "i spread", "i spun", "a stunt", "publicity", "i'm the one who"]
GIVEAWAY_ANY = ["covering for", "i lied", "i was lying", "i'm lying"]

def giveaway(line: str, secret: dict | None) -> str | None:
    """A liar who hasn't been cracked never confesses on their own."""
    if not secret:
        return None
    t = line.lower().replace("’", "'")
    if secret["kind"] == "truth_person":
        from .hunts import CONFESS
        if any(p in t for p in CONFESS + list(secret.get("guard", []))):
            return "Don't give your secret away. Nobody has caught you, so act innocent and stay in character."
        return None
    if any(p in t for p in GIVEAWAY_ANY):
        return "Don't give your secret away. You haven't been caught, so keep your story and stay in character."
    if secret["kind"] == "self":
        if any(p in t for p in GIVEAWAY_SELF):
            return "Don't give your secret away. You haven't been caught, so keep your story and stay in character."
        first = C[secret["first_listener"]]["short"].lower()
        if re.search(rf"\bi (told|said it to) {first}\b", t):
            return "Don't give your secret away. You haven't been caught, so keep your story and stay in character."
    if secret["kind"] == "cover_teller":
        t_short = C[secret["covering_for"]]["short"].lower()
        if re.search(rf"\b{t_short}\b", t) and re.search(r"\b(told me|heard it from|said it to me|got it from|told it to me)\b", t):
            return "Don't give your secret away. You haven't been caught, so keep your story and stay in character."
    return None

def mentions_source(line: str) -> bool:
    return bool(re.search(r"\b(told me|heard it from|heard from|got it from|said it to me|who told)\b", line.lower()))


def clue_writer(server, key: str, ctx: dict, gate: FunnyGate, roles: dict, known: set[str]) -> tuple[dict, str]:
    """Clue Writer: the first thing each person says when you walk up, fingerprint planted."""
    c = C[key]
    schema = OBJ({"line": S(240, 10), "face": ENUM(cast.OPEN_FACES), "anim": ENUM(cast.OPEN_ANIMS)})
    user = f"""THE SPEAKER: {sheet(key, roles)}
{ctx['belief_text']}
{ctx['secret_text']}

The player (the one the rumor is about) walks up to {c['short']} at {roles[key]['place']} on {cast.GAME_DAY} morning.
Write what {c['short']} says first: one to three short sentences, in their voice, telling the player {ctx['what_to_tell']} to their face.{catch_hint(key)} Retell it in their own words; never use anyone else's catchphrase. Do NOT say who told them, or where or when they heard it.
Don't make anything up: no new people, places, times or details beyond what's written above, and don't claim to have seen it unless it says they did."""
    known_facts = f"{ctx['belief_text']}\n{ctx['secret_text']}"

    def check(o):
        g = giveaway(o["line"], ctx.get("secret"))
        if g:
            return g
        if mentions_source(o["line"]):
            return "Don't say who told them or where they heard it yet."
        b = borrowed(o["line"], key)
        if b:
            return b
        bad = unknown_names(o["line"], known)
        if bad:
            return f"Only name people and places in this town. Leave out {', '.join(bad)}."
        v, _ = consistency_line(server, key, [], known_facts, o["line"])
        if v.get("contradicts"):
            return f"That makes something up: {v.get('note', '')} Stick to what's written above."
        return None

    def fallback():
        return {"line": f"{c['phrase']} {ctx['plain']}".strip(), "face": "talking", "anim": c["anims"][0]}

    return run(server, "clue_writer", BASE_SYSTEM + "\nYou are the Clue Writer. You write the first thing each person says.",
               user, schema, check, fallback, label=f"{c['short']}'s first words", gate=gate,
               visible=lambda o: [o["line"]], critic_context=critic_ctx(key, roles, "what this person says first when the player walks up"),
               who=key)


def messenger(server, key: str, version: str, act: str, roles: dict, gate: FunnyGate, known: set[str], plain: str) -> tuple[dict, str]:
    """Messenger: delivers the morning hook in character."""
    c = C[key]
    schema = OBJ({"line": S(260, 20), "face": ENUM(cast.OPEN_FACES), "anim": ENUM(cast.OPEN_ANIMS)})
    user = f"""THE MESSENGER: {sheet(key, roles)}
WHAT THEY BELIEVE: "{scrub(version, key)}"

{cast.GAME_DAY} morning. {c['short']} comes up to the player outside the player's door and tells them the rumor, about THEM, to their face.
Start with "I heard you". One to three sentences in their voice, with {c['say']}. Keep the key parts of what they believe."""

    def check(o):
        t = o["line"].lower()
        if "i heard you" not in t:
            return 'Start with "I heard you".'
        if not overlaps(o["line"], act):
            return "Keep the key parts of the rumor: what they did."
        if not has_marker(o["line"], key):
            return f"Use {c['short']}'s fingerprint: {c['fingerprint']}."
        b = borrowed(o["line"], key)
        if b:
            return b
        bad = unknown_names(o["line"], known)
        if bad:
            return f"Only name people and places in this town. Leave out {', '.join(bad)}."
        return None

    return run(server, "messenger", BASE_SYSTEM + "\nYou are the Messenger. You deliver the morning hook in character.",
               user, schema, check, lambda: {"line": plain, "face": "shocked", "anim": c["anims"][0]},
               label=f"{c['short']}'s hook", gate=gate, visible=lambda o: [o["line"]],
               critic_context=critic_ctx(key, roles, "the morning hook: telling the player a rumor about them, to their face"), who=key)


def town_crier(server, version: str, callbacks: list[str], gate: FunnyGate, plain: dict, known: set[str]) -> tuple[dict, str]:
    """Town Crier: the morning paper, THE DAILY WHISPER."""
    schema = OBJ({"headline": S(50, 8), "subhead": S(170, 10), "caption": S(150, 10)})
    user = f"""Write the front page of THE DAILY WHISPER, the town gossip paper, for {cast.GAME_DAY}.
The hottest rumor in town, about a local resident (never named): "{scrub(version, None)}"
Funny details going around, for callbacks: {json.dumps(callbacks)}
- headline: a punchy tabloid headline, 2 to 6 words, in sentence case (capitalize only the first word and names).
- subhead: one deadpan sentence or two short fragments, under 20 words.
- caption: the caption under the paper's artist's impression of the suspect, one deadpan sentence, under 15 words.
Only name people and places from the rumor. Never give the resident a name, and never call them "the player"."""

    def check(o):
        if len(o["headline"].split()) > 7:
            return "headline must be 2 to 6 words."
        for part in ("headline", "subhead", "caption"):
            if re.search(r"\bplayers?\b", o[part], re.I):
                return f'{part}: never say "player". Say "a local resident" or "you know who".'
            bad = unknown_names(o[part], known)
            if bad:
                return f"{part}: only name people and places from the rumor. Leave out {', '.join(bad)}."
        return None

    return run(server, "town_crier", BASE_SYSTEM + "\nYou are the Town Crier.", user, schema, check, lambda: dict(plain),
               label="front page", gate=gate, visible=lambda o: [o["headline"], o["subhead"], o["caption"]],
               critic_context="WHAT THESE LINES ARE: the town gossip paper's headline, subhead and photo caption.")


def gossip_barks(server, key: str, belief: str, roles: dict, gate: FunnyGate, known: set[str], plain: list[str]) -> tuple[list, str]:
    """Gossip Barks: one-liners a person calls out as you pass in town, from what they believe."""
    c = C[key]
    schema = OBJ({"barks": ARR(S(140, 4), 2, 2)})
    user = f"""THE SPEAKER: {sheet(key, roles)}
WHAT THEY BELIEVE this morning: {belief}

Write two barks: short one-liners {c['short']} calls out as the player (the one the rumor is about) walks past.
In their voice, from what they believe.{catch_hint(key)} Never anyone else's catchphrase.
Under 15 words each, and different from each other. Never say who told them. Don't make up new facts."""

    def check(o):
        for b in o["barks"]:
            if mentions_source(b):
                return "Barks never say who told them."
            bw = borrowed(b, key)
            if bw:
                return bw
            bad = unknown_names(b, known)
            if bad:
                return f"Only name people and places in this town. Leave out {', '.join(bad)}."
        v, _ = consistency_line(server, key, [], f"WHAT THEY BELIEVE: {belief}", " / ".join(o["barks"]))
        if v.get("contradicts"):
            return f"That makes something up: {v.get('note', '')} Stick to what they believe."
        return None

    obj, src = run(server, "gossip_barks", BASE_SYSTEM + "\nYou are the Gossip Barks writer.", user, schema, check,
                   lambda: {"barks": list(plain)}, label=f"{c['short']}'s barks", gate=gate, visible=lambda o: o["barks"],
                   critic_context=critic_ctx(key, roles, "barks: one-liners called out as the player walks past"), who=key)
    return obj["barks"], src


def overheard(server, facts: list[dict], gate: FunnyGate, known: set[str], detail: str) -> tuple[dict, str]:
    """Gossip Barks, overheard lines: what an unnamed passerby says about something they saw.
    The Director uses these to give a stuck player a push."""
    ids = [f["id"] for f in facts]
    schema = OBJ({"lines": ARR(OBJ({"id": ENUM(ids), "line": S(200, 10)}), len(ids), len(ids))})
    listed = "\n".join(f"- {f['id']}: {f['saw']}" for f in facts)
    user = f"""Townsfolk gossip in the street. Each of these is something a passerby really saw:
{listed}

For each one, write the line the player overhears a nameless passerby say to another passerby about it: one or two sentences, deadpan, natural gossip, in the third person.
Each line must name the people in it and the place or the day. Don't guess what anyone said; just what was seen."""

    def check(o):
        got = [x["id"] for x in o["lines"]]
        if sorted(got) != sorted(ids):
            return "Write exactly one line for each id."
        for x in o["lines"]:
            f = next(f for f in facts if f["id"] == x["id"])
            for n in f["names"]:
                if not re.search(rf"\b{n}\b", x["line"], re.I):
                    return f"Line {x['id']} must name {n}."
            if not (place_in(x["line"], f["place"]) or f["when"].split()[0].lower() in x["line"].lower()):
                return f"Line {x['id']} must say the place ({f['place']}) or the day."
            if detail_in(x["line"], detail):
                return f'Line {x["id"]}: the passerby doesn\'t know "{detail}". Leave it out.'
            bad = unknown_names(x["line"], known)
            if bad:
                return f"Only name people and places in this town. Leave out {', '.join(bad)}."
        return None

    def fallback():
        return {"lines": [{"id": f["id"], "line": f["plain"]} for f in facts]}

    return run(server, "gossip_barks", BASE_SYSTEM + "\nYou are the Gossip Barks writer.", user, schema, check, fallback,
               label="overheard lines", gate=gate, visible=lambda o: [x["line"] for x in o["lines"]],
               critic_context="WHAT THESE LINES ARE: gossip the player overhears from nameless passersby in the street.",
               max_tokens=110 * len(ids) + 60)


def escalation(server, version: str, gate: FunnyGate, plain: dict, known: set[str]) -> tuple[dict, str]:
    """Escalation Agent: what the town does at each heat tier, using only what's already drawn."""
    tier = OBJ({"assets": ARR(ENUM(cast.TOWN_ASSETS), 1, 2), "line": S(260, 10)})
    schema = OBJ({"whispers": tier, "talk": tier, "scandal": tier})
    user = f"""THE RUMOR about the player: "{scrub(version, None)}"
The town can only use these, already drawn: wanted_poster (posters go up on the buildings), guard (the town guard follows the player), stocks (the player spends the night in the stocks while townsfolk throw pies).

Decide what the town does at each heat tier, and write one deadpan sentence, under 30 words, telling the player what's happening:
- whispers: enough people believe it that the town acts. Must use wanted_poster.
- talk: Talk of the Town. Must use guard.
- scandal: Scandal, at 6 PM. Must use stocks.
Tie each line to the rumor."""

    def check(o):
        need = {"whispers": "wanted_poster", "talk": "guard", "scandal": "stocks"}
        for t, a in need.items():
            if a not in o[t]["assets"]:
                return f"{t} must use {a}."
            bad = unknown_names(o[t]["line"], known)
            if bad:
                return f"Only name people and places in this town. Leave out {', '.join(bad)}."
        return None

    return run(server, "escalation", BASE_SYSTEM + "\nYou are the Escalation Agent.", user, schema, check,
               lambda: json.loads(json.dumps(plain)), label="what the town does", gate=gate,
               visible=lambda o: [o[t]["line"] for t in ("whispers", "talk", "scandal")],
               critic_context="WHAT THESE LINES ARE: what the whole town does about a rumor as it heats up, told to the player.")


# ====================================================================== daytime

INTENTS = ["ask_who_told", "ask_about", "show_evidence", "call_out", "look_around", "talk"]
LOOK_WORDS = re.compile(r"\b(look around|looks around|looking around|search|snoop|poke around|rummage|have a look|take a look around|"
                        r"look for clues|examine the|inspect the|look behind|look in|look under|check the)\b")
CALL_OUT_WORDS = re.compile(r"\b(liar|lying|lied|contradict\w*|doesn't add up|don't add up|caught you|but you said|you just said|"
                            r"you started|you were there|you knew|covering for|you made it up|admit it|you said .* but)\b")

def plain_intent(text: str, pocket: list[str]) -> dict:
    t = text.lower()
    if CALL_OUT_WORDS.search(t):
        return {"intent": "call_out", "evidence": "none", "about": "a contradiction"}
    if re.search(r"\b(who told|where did you hear|who said|heard it from|who did you hear|where'd you hear)\b", t):
        return {"intent": "ask_who_told", "evidence": "none", "about": "who told them"}
    if LOOK_WORDS.search(t):
        return {"intent": "look_around", "evidence": "none", "about": "searching the place"}
    for k in pocket:
        if any(w in t for w in k.split("_")) and re.search(r"\b(look|show|see|read|here|this)\b", t):
            return {"intent": "show_evidence", "evidence": k, "about": "evidence"}
    if CALL_OUT_WORDS.search(t):
        return {"intent": "call_out", "evidence": "none", "about": "a contradiction"}
    if "?" in t:
        return {"intent": "ask_about", "evidence": "none", "about": "a question"}
    return {"intent": "talk", "evidence": "none", "about": "small talk"}


def intent_reader(server, text: str, key: str, pocket: list[dict], last_line: str) -> tuple[dict, str]:
    """Intent Reader: what the player means by what they typed. Plain code decides what it does."""
    c = C[key]
    ids = [p["kind"] for p in pocket]
    schema = OBJ({"intent": ENUM(INTENTS), "evidence": ENUM(["none"] + ids), "about": S(80, 1)})
    pocket_t = "; ".join(f"{p['title']} (id: {p['kind']})" for p in pocket) or "nothing"
    user = f"""In a detective game, the player is talking to {c['name']}. The player's pocket holds: {pocket_t}.
{c['short']} just said: "{last_line}"

THE PLAYER TYPED: "{text}"

What is the player doing?
- ask_who_told: asks who told them the rumor, or where or when they heard it.
- ask_about: asks about a time, a place, a person or what happened, but not who told them.
- show_evidence: shows, holds up, reads out or describes something in their pocket.
- call_out: says they're lying or contradicting themselves, or points out that two things don't add up. This wins over everything else: a line that accuses them is call_out even if it also shows evidence or asks a question.
- look_around: the player looks around, searches or examines the place they're standing in (not asking {c['short']} a question).
- talk: anything else.
evidence: the pocket item they show or describe, or "none".
about: a few words on what the line is about."""

    def check(o):
        if o["intent"] == "show_evidence" and o["evidence"] == "none" and ids:
            return None   # they mean evidence they don't have; code handles it
        return None

    return run(server, "intent_reader", BASE_SYSTEM + "\nYou are the Intent Reader. You read what the player means.",
               user, schema, check, lambda: plain_intent(text, ids), mode="judge", max_tokens=80,
               label=f"read: {text[:30]}")


def names_ok(line: str, source: str) -> bool:
    t = line.lower()
    if source in C:
        return re.search(rf"\b{C[source]['short'].lower()}\b", t) is not None
    if source == "townsfolk":
        return any(w in t for w in ("everyone", "everybody", "street", "people", "around", "town", "folks", "whole"))
    if source == "someone_i_cant_remember":
        return any(w in t for w in ("remember", "someone", "somebody", "stranger", "who knows", "don't know who", "forget", "forgot"))
    if source == "myself":
        return any(w in t for w in ("it was me", "i started", "myself", "i made", "i did", "my idea", "i said it first",
                                    "nobody told me", "no one told me", "i saw", "i read", "with my own eyes"))
    return True

def source_label(source: str) -> str:
    if source in C:
        return C[source]["short"]
    return {"townsfolk": "everyone in the street", "someone_i_cant_remember": "someone they can't remember",
            "myself": "themselves"}.get(source, source)


def consistency_line(server, key: str, said: list[str], facts: str, line: str) -> tuple[dict, str]:
    """Consistency Agent, daytime: no one contradicts their own story."""
    c = C[key]
    schema = OBJ({"contradicts": BOOL, "note": S(160)})
    said_t = "\n".join(f'- "{s}"' for s in said[-8:])
    user = f"""{c['name']} is in a conversation. Their facts:
{facts}

What they've already said to the player:
{said_t}

THE NEW LINE: "{line}"

contradicts: true if EITHER
- the new line clearly can't be true together with something they already said or with their facts (a different person, place, day or amount for the same thing), OR
- the new line makes up a new fact about the rumor or about what happened that isn't in their facts: a new object, person, place, time, or something they claim to have seen or done.
These are fine and are NOT made up: jokes, attitude, opinions, figures of speech, repeating themselves, exaggerating a number or how often (bigger, more people, every day), and lying or pretending exactly the way their facts say they do (a liar telling their lie, someone acting like they just heard it, someone keeping a secret).
Where they are right now is not where the rumor happened; talking about where they are now is fine.
note: one short sentence naming what's wrong."""
    return run(server, "consistency", BASE_SYSTEM + "\nYou are the Consistency Agent. No character contradicts their own story.",
               user, schema, lambda o: None, {"contradicts": False, "note": "the check couldn't decide, so code passed it"},
               mode="judge", max_tokens=120, label=f"check {c['short']}'s line")


def npc_actor(server, key: str, ctx: dict, gate: FunnyGate, roles: dict) -> tuple[dict, str]:
    """NPC Actor: plays a character live, from what they know, believe and are hiding."""
    c = C[key]
    allowed = ctx["allowed_source"]
    guard = ctx["guard"]   # not cracked yet: no telltale faces or moves, no confessing
    schema = OBJ({
        "line": S(260, 4),
        "face": ENUM(cast.OPEN_FACES if guard else cast.FACES),
        "anim": ENUM(cast.OPEN_ANIMS if guard else cast.ANIMS),
        "names_source": ENUM(["none", allowed]),
    })
    said = "\n".join(f'- "{s}"' for s in ctx["said"][-6:]) or "- (nothing yet)"
    convo = "\n".join(f"{'Player' if h['who'] == 'player' else c['short']}: {h['text']}" for h in ctx["history"]) or "(just started)"
    user = f"""YOU ARE: {sheet(key, roles)}
WHERE: {roles[key]['place']}, {cast.GAME_DAY}, {ctx['clock']}.
YOUR PEOPLE: {relations_text(key, roles)}.
{ctx['facts']}
THIS MORNING'S PAPER: {ctx['paper']}

WHAT YOU'VE ALREADY SAID TO THE PLAYER (never contradict it):
{said}

CONVERSATION (most relevant turns):
{convo}

NOW: {ctx['instruction']}

Reply as {c['short']}, in the first person, talking to the player as "you". One to three short sentences, in your voice.{catch_hint(key)} Only name people and places in this town. Never make up facts that aren't written above.
names_source: "{allowed}" only if this line tells the player who told you ({source_label(allowed)}). Otherwise "none".
face and anim: pick what fits the line."""

    must = ctx.get("must_name")
    slip = ctx.get("slip")

    def check(o):
        line = o["line"]
        if must and o["names_source"] != must:
            return f'This line must tell the player who told you: {source_label(must)}. Set names_source to "{must}".'
        if o["names_source"] != "none" and not names_ok(line, o["names_source"]):
            return f"If names_source is set, the line must actually name {source_label(o['names_source'])}."
        if slip and not has_key(line, slip["key"], slip["kind"]):
            return f'Let your tell slip in this line, by accident: it must include "{slip["key"]}".'
        if guard:
            g = giveaway(line, ctx.get("secret"))
            if g:
                return g
        b = borrowed(line, key)
        if b:
            return b
        for bad in ctx.get("forbidden", []):
            if bad and detail_in(line, bad):
                return f'You don\'t know "{bad}". Leave it out.'
        bad = unknown_names(line, ctx["known"])
        if bad:
            return f"Only name people and places in this town. Leave out {', '.join(bad)}."
        if ctx["said"]:
            v, _ = consistency_line(server, key, ctx["said"], ctx["facts"], line)
            if v.get("contradicts"):
                return f"That contradicts what you already said: {v.get('note', '')}"
        return None

    return run(server, "npc_actor", BASE_SYSTEM + f"\nYou are the NPC Actor. You play {c['name']} in a live conversation. Stay in character.",
               user, schema, check, ctx["fallback"], label=f"{c['short']}: {ctx['label']}", max_tokens=300,
               gate=gate, visible=lambda o: [o["line"]],
               critic_context=critic_ctx(key, roles, f"a live line in conversation with the player ({ctx['label']})"), who=key)


def code_judge(lie: dict | None, accusation: str) -> dict:
    """Plain code, used only when the Gotcha Judge can't decide: does the call-out point at the tell?"""
    if lie and has_key(accusation, lie["tell_key"], lie["tell_kind"]):
        return {"verdict": "caught", "reason": "Plain code: the call-out points at the tell."}
    return {"verdict": "not_caught", "reason": "Plain code: the call-out doesn't point at the tell."}


def gotcha_judge(server, key: str, lie: dict | None, said: list[str], witnesses: list[str], evidence: str,
                 accusation: str) -> tuple[dict, str]:
    """Gotcha Judge: is the player's call-out right? It runs for every call-out, liar or not,
    so how long the answer takes never gives a liar away."""
    c = C[key]
    schema = OBJ({"verdict": ENUM(["caught", "not_caught"]), "reason": S(180)})
    said_t = "\n".join(f'- "{s}"' for s in said) or "- (nothing)"
    wit_t = "\n".join(f"- {w}" for w in witnesses) or "- (nothing)"
    if lie:
        about = f"""{c['name']} is lying. The lie: {lie['lie']} Their alibi: {lie.get('alibi', '')}
Why: {lie['why']}
Their tell: {lie['tell']}"""
    else:
        about = f"{c['name']} has told the truth all day: everything they said is what they really heard and saw."
    user = f"""{about}

Everything {c['short']} has said to the player:
{said_t}

What other people told the player, word for word:
{wit_t}

Evidence the player holds: {evidence}

THE PLAYER SAYS: "{accusation}"

Has the player caught {c['short']}? "caught" means the player points to two things {c['short']} said that can't both be true, or to something {c['short']} said that clashes with what someone else said or with the evidence. Vague accusations, guesses with no reason, or pointing at the wrong thing are "not_caught".
reason: one short sentence."""

    return run(server, "gotcha_judge", BASE_SYSTEM + "\nYou are the Gotcha Judge. You are fair and strict.",
               user, schema, lambda o: None, code_judge(lie, accusation), mode="judge", max_tokens=200,
               label=f"judge {c['short']}")


# ====================================================================== payoff

def reward_menu(server, culprit: str, truth: str, final: str, callbacks: list[str], roles: dict, gate: FunnyGate) -> tuple[dict, str]:
    """Reward Menu Agent: three comeuppances, catalog props and animations only."""
    c = C[culprit]
    option = OBJ({
        "title": S(40, 3),
        "description": S(200, 10),
        "props": ARR(ENUM(cast.PROPS), 1, 3),
        "anim": ENUM(cast.ANIMS),
    })
    schema = OBJ({"options": ARR(option, 3, 3)})
    user = f"""THE CULPRIT: {sheet(culprit, roles)}
THE TRUTH: "{truth}"
WHAT THE RUMOR BECAME: "{final}"
FUNNY DETAILS FROM THE CHAIN, for callbacks: {json.dumps(callbacks)}

Write exactly three comeuppances for {c['short']}, for the player to pick from. Slapstick, never cruel, specific to this rumor.
One of the three must be the player starting a rumor about {c['short']}.
Use only props from the catalog list in the schema. Each title is 2 to 5 words. Each description is one or two sentences, said to the player ("you")."""

    def check(o):
        titles = [norm(x["title"]) for x in o["options"]]
        if len(set(titles)) < 3:
            return "The three titles must be different."
        for x in o["options"]:
            if len(set(x["props"])) != len(x["props"]):
                return f'"{x["title"]}" lists the same prop twice.'
        if not any("rumor" in (x["title"] + x["description"]).lower() for x in o["options"]):
            return f"One option must be the player starting a rumor about {c['short']}."
        return None

    def fallback():
        act = final.rstrip(".")
        return {"options": [
            {"title": "Pie to the face", "description": f"You deliver one custard pie, slowly, directly to {c['short']}'s face.",
             "props": ["custard_pie"], "anim": "cower"},
            {"title": "The Liar's Hat", "description": f"{c['short']} wears the Liar's Hat for three days, and everyone asks about it.",
             "props": ["liars_hat"], "anim": "grovel"},
            {"title": f"A rumor about {c['short']}", "description": f"You tell the whole street a rumor about {c['short']}, and it spreads by dinner.",
             "props": ["megaphone"], "anim": "whisper_behind_hand"},
        ]}

    return run(server, "reward_menu", BASE_SYSTEM + "\nYou are the Reward Menu Agent.", user, schema, check, fallback,
               label="three comeuppances", max_tokens=650, gate=gate,
               visible=lambda o: [x["title"] + ". " + x["description"] for x in o["options"]],
               critic_context=critic_ctx(culprit, roles, f"three comeuppances the player can pick for {c['short']}, who started the rumor"))


def scene_director(server, culprit: str, choice: dict, roles: dict, gate: FunnyGate) -> tuple[dict, str]:
    """Scene Director: shoots the comeuppance from a fixed menu of comedy shots."""
    c = C[culprit]
    beat = OBJ({"shot": ENUM(cast.SHOTS), "text": S(170, 8)})
    schema = OBJ({"beats": ARR(beat, 3, 4), "caption": S(40, 6)})
    user = f"""The player chose this comeuppance for {c['name']}:
"{choice['title']}: {choice['description']}"
Props: {choice['props']}. {c['short']}'s reaction: {choice['anim']}.

Write it as 3 or 4 short beats, each one sentence, each with one camera shot. Deadpan, slapstick, never cruel.
End with a short freeze-frame caption that names {c['short']}."""

    def check(o):
        if c["short"].lower() not in o["caption"].lower():
            return f"The caption should name {c['short']}."
        return None

    def fallback():
        return {"beats": [{"shot": "wide", "text": f"The whole street stops to watch {c['short']}."},
                          {"shot": "slow_push_in", "text": f"{choice['title']}."},
                          {"shot": "freeze_frame", "text": choice["description"]}],
                "caption": f"Yep. That's {c['short']}."}

    return run(server, "scene_director", BASE_SYSTEM + "\nYou are the Scene Director.", user, schema, check, fallback,
               label="comeuppance scene", max_tokens=520, gate=gate,
               visible=lambda o: [b["text"] for b in o["beats"]] + [o["caption"]],
               critic_context=critic_ctx(culprit, roles, "the comeuppance scene, beat by beat, and its freeze-frame caption"))
