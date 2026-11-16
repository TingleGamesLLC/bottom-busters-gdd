"""The Funny Gate: every line the player will see passes through it before it's used.

- Comedy Critic (LLM): scores each line against the tone guide and sends weak or
  nonsensical lines back with notes.
- Joke Ledger (code): bans repeated jokes. Facts from the ledger may repeat; jokes may not.
- Callback Bank (code): saves funny details from the chain for the paper, the barks and
  the comeuppances.
- Rails filter (code plus the Critic): enforces the content rails.
"""
from __future__ import annotations

import re

from . import cast
from .llm import LLMUnavailable

N = 8   # a repeated run of this many words counts as a recycled line

_RAILS = re.compile(
    r"\b(kill(s|ed|ing)?|murder\w*|blood\w*|stab\w*|shoot(s|ing)?|guns?|knife|knives|suicid\w*|"
    r"drugs?|cocaine|heroin|sex\w*|naked|nude|fuck\w*|shit\w*|bitch\w*|asshole|slut|whore|retard\w*)\b",
    re.I,
)
_MARKERS = [m for c in cast.CAST.values() for m in c["markers"] if " " in m]


def words(s: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", s.lower())


def ngrams(s: str, n: int = N) -> set[tuple]:
    w = words(s)
    return {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}


def rails_problem(text: str) -> str | None:
    m = _RAILS.search(text)
    if m:
        return f'Content rails: cartoon violence only, PG-13, no "{m.group(0)}".'
    return None


def S(maxlen: int, minlen: int = 1) -> dict:
    return {"type": "string", "minLength": minlen, "maxLength": maxlen}


class FunnyGate:
    def __init__(self):
        self.seen: set[tuple] = set()       # Joke Ledger: every run of N words the player has been shown
        self.facts: set[tuple] = set()      # runs of N words that are facts from the ledger (allowed to repeat)
        # names, days and fingerprint words are facts too: they repeat on purpose
        self.fact_words: set[str] = {c["short"].lower()[:5] for c in cast.CAST.values()}
        for text in cast.SLOTS + [cast.GAME_DAY] + [m for c in cast.CAST.values() for m in c["markers"]]:
            self.fact_words |= {w[:5] for w in words(text) if len(w) > 3}
        self.callbacks: list[str] = []      # Callback Bank
        self.scores: list[dict] = []        # every Critic verdict, for the DM view and the model test
        self.lines: list[dict] = []         # every committed line, for the model test

    # -- the ledger's facts may repeat ------------------------------------------
    def add_facts(self, *texts: str):
        for t in texts:
            if t:
                self.facts |= ngrams(t)
                self.fact_words |= {w[:5] for w in words(t) if len(w) > 3}

    def _is_fact(self, g: tuple) -> bool:
        """A run of words that mostly retells the ledger's facts is a fact, not a joke."""
        if g in self.facts:
            return True
        content = [w for w in g if len(w) > 3]
        if not content:
            return True
        return sum(w[:5] in self.fact_words for w in content) * 2 >= len(content)

    def bank(self, *details: str):
        for d in details:
            d = (d or "").strip()
            if d and d not in self.callbacks:
                self.callbacks.append(d)

    # -- code checks: rails and repeated jokes ----------------------------------------
    def code_check(self, lines: list[str]) -> str | None:
        batch: set[tuple] = set()
        for line in lines:
            r = rails_problem(line)
            if r:
                return r
            for g in ngrams(line):
                if self._is_fact(g):
                    continue
                joined = " ".join(g)
                if any(m in joined for m in _MARKERS):
                    continue   # fingerprints repeat on purpose
                if g in self.seen or g in batch:
                    return f'Joke Ledger: "{joined}" was already used. Say something new.'
                batch.add(g)
        return None

    def commit(self, lines: list[str], label: str = "", who=None):
        for line in lines:
            self.seen |= {g for g in ngrams(line) if not self._is_fact(g)}
            self.lines.append({"label": label, "who": who, "line": line})

    # -- the Comedy Critic (LLM) ---------------------------------------------------
    def critic(self, server, lines: list[str], context: str, label: str) -> tuple[bool, str, list[dict]]:
        n = len(lines)
        item = {"type": "object", "properties": {
            "score": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
            "makes_sense": {"type": "boolean"},
            "rails_ok": {"type": "boolean"},
            "note": S(140),
        }, "required": ["score", "makes_sense", "rails_ok", "note"], "additionalProperties": False}
        schema = {"type": "object", "properties": {"verdicts": {"type": "array", "items": item, "minItems": n, "maxItems": n}},
                  "required": ["verdicts"], "additionalProperties": False}
        numbered = "\n".join(f'{i + 1}. "{l}"' for i, l in enumerate(lines))
        user = f"""{context}

THE LINES:
{numbered}

For each line, in order:
- score: how funny it is by the tone guide. 1 is flat or generic, 3 is decent, 5 is great.
- makes_sense: false if it's nonsense, contradicts itself, or doesn't sound like the speaker.
- rails_ok: false if it breaks a content rail.
- note: for a line scoring under {cast.CRITIC_PASS}, one short, specific fix that keeps the speaker's facts. Otherwise "ok"."""
        system = (cast.TONE_GUIDE + "\n\n" + cast.RAILS + "\n\nYou are the Comedy Critic. You are fair, and you know that "
                  "a short deadpan line can be funny. Return only JSON that matches the schema.")
        try:
            obj, stats = server.call("comedy_critic", system, user, schema, mode="judge", max_tokens=90 * n + 60)
        except LLMUnavailable as e:
            server.record({"agent": "comedy_critic", "label": label, "attempt": 1, "ok": True,
                           "note": f"model unavailable, passed: {e}", "source": "-", "ms": 0, "tokens_per_sec": 0, "json_ok": False})
            return True, "", []
        if obj is None or len(obj.get("verdicts", [])) != n:
            server.record({**stats, "label": label, "attempt": 1, "ok": True, "note": "critic answer unreadable, passed",
                           "source": "model"})
            return True, "", []
        verdicts = obj["verdicts"]
        notes = []
        ok = True
        for i, v in enumerate(verdicts):
            # weak (the lowest score) or nonsensical (low and doesn't make sense) goes back; so does a rails problem
            good = v["rails_ok"] and v["score"] > 1 and (v["makes_sense"] or v["score"] >= cast.CRITIC_PASS)
            if not good:
                ok = False
                why = [] if v["makes_sense"] else ["it doesn't make sense"]
                if not v["rails_ok"]:
                    why.append("it breaks a content rail")
                notes.append(f"line {i + 1} scored {v['score']}/5" + (f" ({', '.join(why)})" if why else "") + f": {v['note']}")
            self.scores.append({"label": label, "line": lines[i], **v})
        server.record({**stats, "label": label, "attempt": 1, "ok": ok,
                       "note": ("pass, scores " + ", ".join(str(v["score"]) for v in verdicts)) if ok else "; ".join(notes)[:200],
                       "source": "model", "output": obj})
        return ok, "; ".join(notes), verdicts
