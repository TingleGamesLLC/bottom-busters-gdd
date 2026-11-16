"""The night shift: sets up one of the six approved hunts (rm/hunts.py), then the agents write
the morning around it.

The rumor, each person's version up the chain, the truth and the proof come from the hunt,
word for word. The LLM agents write everyone's first words, the morning paper, the barks, the
overheard lines and what the town does as the rumor heats up. Every result goes into the truth
ledger and the belief ledgers, saved after each step."""
from __future__ import annotations

import json
import random
import re

from . import agents, cast, hunts
from .agents import PremiseFailed
from .funny import FunnyGate
from .ledger import STATE_DIR, Ledger, relevance_score

C = cast.CAST
CARRYOVER = STATE_DIR / "carryover.json"


class NightFailed(Exception):
    pass


def load_carryover() -> dict:
    try:
        return json.loads(CARRYOVER.read_text(encoding="utf-8"))
    except Exception:
        return {"last_hunt": None, "player_actions": []}


def save_carryover(data: dict):
    STATE_DIR.mkdir(exist_ok=True)
    CARRYOVER.write_text(json.dumps(data, indent=2), encoding="utf-8")


def find_text(f: dict) -> str:
    return f"{f['title']}: " + " / ".join(f["lines"])


class NightShift:
    def __init__(self, server, rng: random.Random, progress=None):
        self.server = server
        self.rng = rng
        self.carry = load_carryover()
        self.progress = progress or (lambda *a, **k: None)
        self.thrown_out: list[str] = []

    STEPS = 17   # night log entries for a liar hunt (16 for a mistake hunt): the progress count

    def log(self, agent: str, kind: str, result: str, source: str = ""):
        entry = {"agent": agent, "kind": kind, "result": result, "source": source}
        self.L.update(lambda d: d["night_log"].append(entry))
        self.done = getattr(self, "done", 0) + 1
        self.progress({**entry, "n": self.done, "of": self.total})

    def pick(self) -> dict:
        """One of the six, never the same one twice in a row."""
        last = self.carry.get("last_hunt")
        pool = [h for h in hunts.HUNTS if h["id"] != last] or hunts.HUNTS
        return self.rng.choice(pool)

    def run(self, hunt: dict | None = None) -> tuple[Ledger, dict, FunnyGate]:
        hunt = hunt or self.pick()
        self.total = self.STEPS - (0 if hunt["kind"] == "liar" else 1)
        self.L = Ledger(1, self.rng.randrange(1 << 30))
        self.gate = FunnyGate()
        try:
            return self.L, self._premise(hunt), self.gate
        except PremiseFailed as e:
            raise NightFailed(str(e))

    # ------------------------------------------------------------------ the premise
    def _premise(self, H: dict) -> dict:
        S = self.server
        chain_in = H["chain"]
        path = [e["npc"] for e in chain_in]
        source = path[0]
        final = chain_in[-1]["version"]
        liar = H["kind"] == "liar"

        # The town and everyone's roles (fixed for the six)
        town = {"street": hunts.STREET, "roof_prop": hunts.ROOF_PROP,
                "places": {b: dict(v) for b, v in hunts.PLACES.items()}}
        place_of = {b: town["places"][b]["name"] for b in cast.KIT_ORDER}
        owner_of = {b: town["places"][b]["who"] for b in cast.KIT_ORDER}
        friend = {}
        for a, b in H.get("friends", []):
            friend[a], friend[b] = b, a
        roles = {}
        for b in cast.KIT_ORDER:
            k = owner_of[b]
            roles[k] = {"job": hunts.JOBS[k], "building": b, "place": place_of[b], "secret": None,
                        "friend": friend.get(k), "owes": "nobody", "owes_what": "", "cant_stand": None}

        def commit_roles(d):
            d["town"] = town
            d["meta"]["hunt"] = H["id"]
            d["truth"] = {"k1": {"text": H["truth"]}}
            for k in cast.KEYS:
                r = roles[k]
                d["npcs"][k].update({"job": r["job"], "building": r["building"], "place": r["place"],
                                     "relationships": {"friend": r["friend"]}})
        self.L.update(commit_roles)
        self.log("Hunt", "code", f"hunt {H['id']}: {final}", "approved by David")

        known = self._known_words(town, roles, H)
        self.gate.add_facts(town["street"], *place_of.values(), *[roles[k]["job"] for k in cast.KEYS])

        # The chain, word for word, and when and where each hop happened
        hops = []
        for i, h in enumerate(H["hops"]):
            hops.append({"teller": path[i], "listener": path[i + 1], "where": h["where"], "when": h["when"], "witnesses": []})
        chain = []
        for i, e in enumerate(chain_in):
            last = i == len(chain_in) - 1
            chain.append({
                "hop": i + 1, "npc": e["npc"], "heard_from": path[i - 1] if i else None,
                "heard_where": hops[i - 1]["where"] if i else None, "heard_when": hops[i - 1]["when"] if i else None,
                "told_to": None if last else path[i + 1],
                "told_where": "outside your door" if last else hops[i]["where"],
                "told_when": f"{cast.GAME_DAY} morning" if last else hops[i]["when"],
                "version": e["version"], "mutation": e["change"], "field_changed": "-",
                "before": chain_in[i - 1]["version"] if i else "(nothing: started it)", "after": e["version"],
                "consistency": "pass", "written_by": "approved by David", "why": H["truth"] if i == 0 else None,
            })
        rumor = {"kernel": "k1", "started_by": source, "chain": chain, "hops": hops, "heat": 0, "believers": 0,
                 "relevance_score": 1.0}

        def commit_chain(d):
            d["rumors"]["r1"] = rumor
            for e in chain:
                d["mutation_log"].append({k: e[k] for k in ["hop", "npc", "heard_from", "mutation", "before", "after",
                                                              "consistency", "written_by"]})
        self.L.update(commit_chain)
        self.gate.add_facts(H["truth"], H["claim"], H.get("seen", ""), *[e["version"] for e in chain],
                            *[find_text(f) for f in H["finds"]], *H.get("knows", {}).values())
        self.log("Chain", "code", " -> ".join(C[k]["short"] for k in path) + " -> you", "approved by David")

        # Where everyone was (code): at their own place, except for the hops
        timeline = {k: {s: roles[k]["place"] for s in cast.SLOTS} for k in cast.KEYS}
        for h in hops:
            timeline[h["teller"]][h["when"]] = h["where"]
            timeline[h["listener"]][h["when"]] = h["where"]
        saw = {k: [] for k in cast.KEYS}

        # The starter's lie (liar hunts). It's caught only with the proof in hand.
        lies = {}
        if liar:
            lies[source] = {
                "liar": source, "kind": "self", "covering_for": source, "first_listener": path[1],
                "lie": H["claim"], "alibi": "", "why": H["truth"], "truth": H["truth"], "tell": "",
                "tell_key": "", "tell_kind": "detail", "claimed_source": "myself",
                "claimed_where": hops[0]["where"], "claimed_when": hops[0]["when"],
                "real_where": hops[0]["where"], "real_when": hops[0]["when"], "catch": list(H["catch"]),
                "written_by": "approved by David",
            }
            self.log("Red Herring", "code", f"{C[source]['short']} lies: {H['claim']}", "approved by David")

        # What everyone believes (code)
        beliefs = {}
        for i, k in enumerate(path):
            e = chain[i]
            beliefs[k] = {"role": "source" if i == 0 else "chain", "version": e["version"],
                          "heard_from": e["heard_from"], "heard_where": e["heard_where"], "heard_when": e["heard_when"],
                          "told_to": e["told_to"], "told_where": e["told_where"], "told_when": e["told_when"],
                          "about_player": True, "started_it": i == 0, "knows_truth": False, "lie": lies.get(k)}
        for k in cast.KEYS:
            if k not in beliefs:
                beliefs[k] = {"role": "bystander", "version": final, "heard_from": "townsfolk", "heard_where": "in the street",
                              "heard_when": f"{cast.GAME_DAY} morning", "told_to": None, "told_where": None, "told_when": None,
                              "about_player": True, "started_it": False, "knows_truth": k == H.get("truth_person"),
                              "lie": None}

        quest = self._quest(H, path)

        def commit_people(d):
            for k in cast.KEYS:
                n = d["npcs"][k]
                n["timeline"] = timeline[k]
                n["saw"] = saw[k]
                n["beliefs"]["r1"] = beliefs[k]
            d["lies"] = lies
            d["quest"] = quest
            d["finds"] = H["finds"]
        self.L.update(commit_people)

        # First words (code): each person's approved version, with their catchphrase. The model's tries
        # mostly failed the fact check and fell back to this anyway, and they kept the player waiting.
        arrival = {}
        for k in cast.KEYS:
            line = f"{C[k]['phrase']} {agents.scrub(beliefs[k]['version'], k)}".strip()
            arrival[k] = {"line": line, "face": "talking", "anim": C[k]["anims"][0], "source": "approved by David"}
            self.log("First words", "code", f"{C[k]['short']}: {line}", "approved by David")

        # The morning hook: the rumor, word for word, from the last person in the chain
        m = path[-1]
        hook = {"line": final, "face": "talking", "anim": C[m]["anims"][0], "source": "approved by David"}
        self.log("Messenger", "code", f"{C[m]['short']}: {final}", "approved by David")

        # Town Crier, Gossip Barks, overheard lines and the Escalation Agent (LLM)
        plain_paper = {"headline": "LOCAL RESIDENT IN QUESTION", "subhead": final, "caption": "An artist's impression of the suspect."}
        crier, src = agents.town_crier(S, final, self.gate.callbacks[:6], self.gate, plain_paper, known)
        self.gate.bank(crier["headline"])
        self.log("Town Crier", "LLM", f"{crier['headline']}. {crier['subhead']}", src)
        barks = {}
        for k in cast.KEYS:   # (code) their approved version and their catchphrase, for the same reason
            barks[k] = [x for x in (C[k]["phrase"], agents.scrub(beliefs[k]["version"], k)) if x]
            self.log("Gossip Barks", "code", f"{C[k]['short']}: " + " / ".join(barks[k]), "approved by David")
        facts = self._overheard_facts(hops)
        over, src = agents.overheard(S, facts, self.gate, known, "")
        overheard = {x["id"]: x["line"] for x in over["lines"]}
        self.log("Gossip Barks", "LLM", f"{len(overheard)} overheard lines", src)
        plain_esc = {"whispers": {"assets": ["wanted_poster"], "line": "Wanted posters with your face on them go up on every building."},
                     "talk": {"assets": ["guard"], "line": "The town guard starts following you around."},
                     "scandal": {"assets": ["stocks"], "line": "You spend the night in the stocks while the town throws pies."}}
        esc, src = agents.escalation(S, final, self.gate, plain_esc, known)
        self.log("Escalation Agent", "LLM", "; ".join(f"{t}: {esc[t]['line']}" for t in ("whispers", "talk", "scandal")), src)

        morning = {"hook": hook, "crier": crier, "arrival": arrival, "barks": barks,
                   "overheard": overheard, "overheard_facts": facts, "escalation": esc}
        keys = self.L.keywords()

        def commit_morning(d):
            d["morning"] = morning
            d["rumors"]["r1"]["relevance_score"] = relevance_score(final, keys)
        self.L.update(commit_morning)

        return {"hunt": H, "roles": roles, "town": town, "place_of": place_of, "owner_of": owner_of,
                "kernel": {"text": H["truth"], "detail": ""}, "twist": "none", "source": source, "path": path,
                "hops": hops, "chain": chain, "lies": lies, "finds": H["finds"], "quest": quest, "checks": [],
                "beliefs": beliefs, "participants": [], "timeline": timeline, "saw": saw, "morning": morning,
                "known": known}

    # ------------------------------------------------------------------ code steps
    def _known_words(self, town: dict, roles: dict, H: dict) -> set[str]:
        """Proper nouns people in this town can use: the five, the places, the street and the hunt's own names."""
        out = set()
        for c in C.values():
            out |= {w.lower() for w in c["name"].split()}
        texts = [town["street"]] + [town["places"][b]["name"] for b in cast.KIT_ORDER] + [roles[k]["job"] for k in cast.KEYS]
        texts += [H["truth"], H["claim"], H.get("seen", "")] + [e["version"] for e in H["chain"]]
        texts += [find_text(f) for f in H["finds"]]
        for text in texts:
            out |= {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z'\-]*", text.replace("'s", " "))}
        return out

    def _quest(self, H: dict, path: list[str]) -> list[dict]:
        """The hunt as steps, for the DM view."""
        steps = []
        for i in range(len(path) - 1, 0, -1):
            steps.append({"step": len(steps) + 1, "find": path[i - 1], "from": path[i],
                          "how": f"ask {C[path[i]]['short']} who told them"})
        where = ", ".join(f"{f['title']} ({hunts.PLACES[f['where']]['name']})" for f in H["finds"])
        s = C[path[0]]["short"]
        if H["kind"] == "liar":
            how = f"look around to find {where}, then call out {s} while holding it"
        else:
            how = f"look around to find {where}, then show it to {s}"
        steps.append({"step": len(steps) + 1, "find": "the source", "from": path[0], "how": how})
        return steps

    def _clue_ctx(self, k: str, belief: dict, H: dict, final: str, liar: bool) -> dict:
        v = agents.scrub(belief["version"], k)
        ctx = {"secret": None, "secret_text": "", "plain": agents.scrub(belief["version"], k)}
        if belief["role"] == "source" and liar:
            ctx["belief_text"] = f'WHAT THEY\'RE SPREADING: "{v}"'
            ctx["secret_text"] = "SECRET: they started this rumor themselves. They act like they heard it like everyone else."
            ctx["what_to_tell"] = "the rumor, as if they'd just heard it"
            ctx["secret"] = {"kind": "self", "first_listener": belief["told_to"]}
        elif belief["role"] == "source":
            ctx["belief_text"] = f'WHAT THEY SAW and believe: {H["seen"]} So they say: "{v}"'
            ctx["what_to_tell"] = "what they saw, and that they're sure it was the player"
        elif belief["role"] == "chain":
            ctx["belief_text"] = f'WHAT THEY BELIEVE about the player: "{v}"'
            ctx["what_to_tell"] = "their version of the rumor"
        else:
            ctx["belief_text"] = f'WHAT THEY HEARD in the street this morning, and believe: "{agents.scrub(final, k)}"'
            ctx["what_to_tell"] = "the rumor everyone's talking about"
            if k == H.get("truth_person"):
                ctx["belief_text"] = (f'WHAT THEY HEARD in the street this morning: "{agents.scrub(final, k)}". '
                                      "They know the truth, and it's their own secret.")
                ctx["secret_text"] = f"SECRET: {H['truth_secret']} Keep it secret; act innocent."
                ctx["secret"] = {"kind": "truth_person", "guard": H.get("guard", [])}
                ctx["what_to_tell"] = "the rumor everyone's talking about, acting innocent"
        return ctx

    def _overheard_facts(self, hops) -> list[dict]:
        facts = []
        for j, h in enumerate(hops):
            t, l = C[h["teller"]]["short"], C[h["listener"]]["short"]
            facts.append({"id": f"hop{j + 1}", "names": [t, l], "place": h["where"], "when": h["when"],
                          "saw": f"{t} and {l} with their heads together, gossiping, at {h['where']}, {h['when']}",
                          "plain": f"I saw {t} and {l} with their heads together at {h['where']}, {h['when']}."})
        return facts
