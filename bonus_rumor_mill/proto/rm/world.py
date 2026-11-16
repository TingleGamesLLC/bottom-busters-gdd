"""The Dungeon Master loop for one day: the night shift sets up one of the six approved hunts,
the day is the hunt, the evening is the comeuppance. Plain code keeps the score; the agents only
write words and make comedy choices.

Conversation is typed only. The Intent Reader says what the player means, and plain code
decides what that does."""
from __future__ import annotations

import difflib
import random
import time

from . import agents, cast
from .ledger import prune_dialogue, relevance_score
from .night import NightShift, find_text, load_carryover, save_carryover

C = cast.CAST


def clock_text(hour: int) -> str:
    h = hour % 12 or 12
    return f"{h}:00 {'AM' if hour < 12 else 'PM'}"


def word_diff(a: str, b: str) -> list[tuple[str, str]]:
    """[(op, text)] with op in 'same', 'del', 'add'."""
    aw, bw = a.split(), b.split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, aw, bw).get_opcodes():
        if op == "equal":
            out.append(("same", " ".join(aw[i1:i2])))
        if op in ("delete", "replace"):
            out.append(("del", " ".join(aw[i1:i2])))
        if op in ("insert", "replace"):
            out.append(("add", " ".join(bw[j1:j2])))
    return out


def first_sentence(s: str) -> str:
    for p in ".!?":
        if p in s:
            s = s.split(p)[0] + p
    return s


class Game:
    def __init__(self, server, seed: int | None = None):
        self.server = server
        self.rng = random.Random(seed)
        self.ledger = None
        self.p: dict = {}
        self.gate = None
        self.thrown_out: list[str] = []
        self.history: dict[str, list] = {k: [] for k in cast.KEYS}
        self.turns = 0
        self.here: str | None = None
        self.visits: dict[str, int] = {k: 0 for k in cast.KEYS}
        # The player's notebook: only what the player saw and heard, word for word, in order.
        self.notes: list[dict] = []
        self.held: list[str] = []             # ids of the proof the player has found
        self.cracked: set[str] = set()
        self.corrected: set[str] = set()
        self.known_chain: set[str] = set()   # chain members the player has been pointed to (for the Director)
        self.asked_who: dict[str, int] = {k: 0 for k in cast.KEYS}
        self.outcome: str | None = None
        self.last_call = False
        self.reward_options: list | None = None
        self.choice: dict | None = None
        self.scene: dict | None = None
        self.clock = cast.DAY_START
        self.townsfolk = 0
        self.fired: set[str] = set()
        self.pushed: set[str] = set()
        self.idle_hours = 0
        self.pending: list[dict] = []
        self.barks_heard: set[tuple] = set()

    # ------------------------------------------------------------------ night
    def night(self, progress=None, hunt: dict | None = None):
        ns = NightShift(self.server, self.rng, progress)
        self.ledger, self.p, self.gate = ns.run(hunt)
        carry = load_carryover()
        carry["last_hunt"] = self.p["hunt"]["id"]
        save_carryover(carry)

    # ------------------------------------------------------------------ quick access
    @property
    def hunt(self) -> dict:
        return self.p["hunt"]

    @property
    def path(self) -> list[str]:
        return self.p["path"]

    @property
    def chain(self) -> list[dict]:
        return self.p["chain"]

    @property
    def source(self) -> str:
        return self.p["source"]

    @property
    def messenger(self) -> str:
        return self.p["path"][-1]

    @property
    def morning(self) -> dict:
        return self.p["morning"]

    @property
    def roles(self) -> dict:
        return self.p["roles"]

    @property
    def pocket(self) -> list[dict]:
        """What the player has found, for the Intent Reader and the notebook."""
        return [{"kind": f["id"], **f} for f in self.hunt["finds"] if f["id"] in self.held]

    def find(self, fid: str) -> dict:
        return next(f for f in self.hunt["finds"] if f["id"] == fid)

    def pocket_text(self) -> str:
        return "; ".join(find_text(f) for f in self.pocket) or "nothing"

    def place(self, key: str) -> str:
        return self.roles[key]["place"]

    def who_at(self, building: str) -> str:
        return self.p["owner_of"][building]

    def belief(self, key: str) -> dict:
        return self.p["beliefs"][key]

    def lie(self, key: str) -> dict | None:
        return self.p["lies"].get(key)

    # ------------------------------------------------------------------ heat
    def named_believers(self) -> int:
        n = 0
        for k in cast.KEYS:
            b = self.belief(k)
            if b["role"] in ("chain", "bystander") and not b["knows_truth"] and k not in self.corrected:
                n += 1
        return n

    @property
    def believers(self) -> int:
        return self.named_believers() + self.townsfolk

    @property
    def heat(self) -> float:
        """Heat comes from the rumor spreading and how many believe it. It hits Scandal at 6 PM."""
        if self.clock >= cast.DAY_END:
            return 1.0
        frac = (self.clock - cast.DAY_START) / (cast.DAY_END - cast.DAY_START)
        spread = min(1.0, self.believers / (cast.BELIEVER_THRESHOLD * 4))
        return round(min(0.99, 0.5 * frac + 0.5 * spread), 3)

    @property
    def tier(self) -> str:
        h = self.heat
        name = cast.TIERS[0][1]
        for threshold, n in cast.TIERS:
            if h >= threshold:
                name = n
        return name

    @property
    def reputation(self) -> int:
        if self.outcome == "busted":
            return cast.REP_START + 1
        if self.outcome == "scandal":
            return cast.REP_START - 2
        return cast.REP_START

    def _tick_ledger(self):
        def f(d):
            d["meta"]["clock"] = self.clock
            d["meta"]["heat"] = self.heat
            d["meta"]["tier"] = self.tier
            d["meta"]["believers"] = self.believers
            d["rumors"]["r1"]["heat"] = round(self.heat * 3, 2)
            d["rumors"]["r1"]["believers"] = self.believers
        self.ledger.update(f)

    def _hour_passes(self):
        """The rumor spreads: every believer who hasn't seen the truth tells one more person an hour."""
        self.clock += 1
        self.townsfolk += self.named_believers()
        self.idle_hours += 1
        esc = self.morning["escalation"]
        if "whispers" not in self.fired and self.believers >= cast.BELIEVER_THRESHOLD:
            self.fired.add("whispers")   # belief becomes reality: the town acts
            self.pending.append({"kind": "escalation", "tier": "whispers", "text": esc["whispers"]["line"]})
        if "talk" not in self.fired and self.tier == "Talk of the Town":
            self.fired.add("talk")
            self.pending.append({"kind": "escalation", "tier": "talk", "text": esc["talk"]["line"]})
        self._tick_ledger()

    @property
    def posters(self) -> int:
        return 0 if "whispers" not in self.fired else min(5, 1 + int(self.heat * 6))

    @property
    def guard(self) -> bool:
        return "talk" in self.fired

    # ------------------------------------------------------------------ day
    def start_day(self):
        m = self.messenger
        self.notes.append({"npc": m, "clock": self.clock, "where": "outside your door", "you": None,
                           "line": self.morning["hook"]["line"]})
        self.known_chain.add(m)
        self.ledger.update(lambda d: d["npcs"][m]["said_to_player"].append(self.morning["hook"]["line"]))
        self._tick_ledger()

    def _progress(self):
        self.idle_hours = 0

    def director(self) -> dict | None:
        """Director (code): after a few hours without progress, a push: an overheard line with a clue."""
        if self.outcome or self.idle_hours < cast.DIRECTOR_IDLE_HOURS:
            return None
        path = self.path
        fid = None
        for i in range(len(path) - 1, 0, -1):
            if path[i] in self.known_chain and path[i - 1] not in self.known_chain:
                fid = f"hop{i}"
                break
        if fid is None or fid in self.pushed or fid not in self.morning["overheard"]:
            return None
        self.pushed.add(fid)
        self.idle_hours = 0
        line = self.morning["overheard"][fid]
        fact = next(f for f in self.morning["overheard_facts"] if f["id"] == fid)
        self.notes.append({"npc": None, "clock": self.clock, "where": "in the street", "you": None, "line": line})
        return {"kind": "push", "text": line, "fact": fact}

    def hub_events(self) -> list[dict]:
        out = list(self.pending)
        self.pending.clear()
        push = self.director()
        if push:
            out.append(push)
        return out

    def bark(self, key: str) -> str | None:
        """What someone calls out as you pass. Nobody barks once they've seen the truth or cracked."""
        if key in self.corrected or key in self.cracked or self.outcome:
            return None
        barks = self.morning["barks"][key]
        line = barks[(self.clock - cast.DAY_START) % len(barks)]
        if (key, line) not in self.barks_heard:
            self.barks_heard.add((key, line))
            self.notes.append({"npc": key, "clock": self.clock, "where": "as you walked past", "you": None, "line": line})
        return line

    def visit(self, key: str) -> dict:
        """Each conversation costs an hour."""
        self.here = key
        self.turns = 0
        self._hour_passes()
        self.last_call = self.clock >= cast.DAY_END
        self.visits[key] += 1
        self.ledger.update(lambda d: d["player"]["visited"].append({"npc": key, "clock": clock_text(self.clock)}))
        if self.visits[key] == 1:
            reply = dict(self.morning["arrival"][key])
            self._remember(key, None, reply)
            return reply
        return self._act(key, "return", None, "The player is back to talk to you again. Greet them, in character.")

    @property
    def out_of_turns(self) -> bool:
        return self.turns >= cast.TURNS_PER_VISIT

    def leave(self):
        self.here = None
        if self.last_call and self.outcome is None:
            self.outcome = "scandal"
            self.ledger.update(lambda d: d["meta"].__setitem__("outcome", "scandal"))

    # ------------------------------------------------------------------ typed conversation
    def talk(self, key: str, text: str) -> dict:
        self.turns += 1
        pocket = self.pocket
        last = next((h["text"] for h in reversed(self.history[key]) if h["who"] == "npc"), "")
        intent, isrc = agents.intent_reader(self.server, text, key, pocket, last)
        it = intent["intent"]
        if it != "call_out" and agents.CALL_OUT_WORDS.search(text.lower()):
            it = "call_out"   # tie-break: an accusation is a call-out even when it also shows evidence or asks something
            isrc += " + code tie-break"
        elif it not in ("call_out", "look_around") and agents.LOOK_WORDS.search(text.lower()):
            it = "look_around"
            isrc += " + code tie-break"
        self.ledger.update(lambda d: d["player"]["said"].append({"npc": key, "clock": clock_text(self.clock), "text": text,
                                                                  "intent": it, "read_by": isrc}))
        if it == "call_out":
            reply = self._call_out(key, text)
        elif it == "look_around":
            reply = self._look(key, text)
        elif it == "show_evidence" and intent["evidence"] in self.held:
            reply = self._show(key, text, intent["evidence"])
        elif it == "show_evidence" and len(self.held) == 1 and intent["evidence"] == "none":
            reply = self._show(key, text, self.held[0])
        elif it == "ask_who_told":
            reply = self._ask_who(key, text)
        elif it == "ask_about":
            reply = self._ask_about(key, text)
        else:
            extra = ""
            if it == "show_evidence":
                extra = " The player mentions something they aren't holding; they don't have it."
            reply = self._act(key, "talk", text, f'The player says: "{text}". Answer them, in character, from what you know.{extra}')
        reply["intent"] = it
        reply["intent_by"] = isrc
        return reply

    def _look(self, key: str, text: str) -> dict:
        """The player searches the place they're standing in. Proof is found only where it is."""
        b = self.roles[key]["building"]
        place = self.place(key)
        new = [f for f in self.hunt["finds"] if f["where"] == b and f["id"] not in self.held]
        event = None
        if new:
            self.held.extend(f["id"] for f in new)
            self._progress()
            event = "found"
            line = f"You look around the {place}. You find: " + " ".join(
                f"{f['title']}. " + " ".join(f["lines"]) for f in new)
            self.ledger.update(lambda d: d["player"]["evidence"].extend(f["id"] for f in new))
        elif any(f["where"] == b for f in self.hunt["finds"]):
            line = f"You look around the {place} again. Nothing new."
        else:
            line = f"You look around the {place}. Nothing out of the ordinary."
        self.ledger.update(lambda d: d["player"]["actions"].append({"npc": key, "clock": clock_text(self.clock),
                                                                     "did": "looked around", "found": [f["id"] for f in new]}))
        self.notes.append({"npc": key, "clock": self.clock, "where": place, "you": f'You: "{text}"', "line": line,
                           "narr": True})
        return {"line": line, "face": "rest", "anim": "", "narration": True, "event": event, "source": "code"}

    def _ask_who(self, key: str, text: str) -> dict:
        self.asked_who[key] += 1
        b = self.belief(key)
        lie = self.lie(key)
        cracked = key in self.cracked
        if lie and not cracked:
            must = "myself"
            instr = (f'The player asks: "{text}". Tell your lie about who told you: {lie["lie"]} '
                     "Stick to it. Don't admit anything.")
        elif b["role"] == "source" and cracked:
            must = None
            instr = f'The player asks: "{text}". You already confessed the truth: {lie["truth"]} Say so.'
        elif b["role"] == "source":
            must = "myself"
            instr = f'The player asks: "{text}". Tell them the truth as you know it: {self.hunt["claim"]}'
        elif b["role"] == "chain":
            must = b["heard_from"]
            instr = (f'The player asks: "{text}". Tell them the truth: {C[must]["short"]} told you, '
                     f'at {b["heard_where"]}, {b["heard_when"]}.')
            if must not in self.known_chain:
                self.known_chain.add(must)
                self._progress()
        else:
            must = "townsfolk"
            instr = (f'The player asks: "{text}". Tell them the truth: you heard it this morning from everyone in the street, '
                     "and you don't know who started it.")
        return self._act(key, "ask who told", text, instr, must_name=must)

    def _ask_about(self, key: str, text: str) -> dict:
        instr = (f'The player asks: "{text}". Answer from what you know: where you were, what you saw, the people you know '
                 "and what you heard. If you don't know, say so in character.")
        lie = self.lie(key)
        if lie and key not in self.cracked:
            instr += " Stick to your lie."
        return self._act(key, "ask about", text, instr)

    def _show(self, key: str, text: str, fid: str) -> dict:
        f = self.find(fid)
        ev = find_text(f)
        b = self.belief(key)
        lie = self.lie(key)
        H = self.hunt
        self.ledger.update(lambda d: d["player"]["shown"].append({"npc": key, "find": fid, "clock": clock_text(self.clock)}))
        event = None
        if lie and key not in self.cracked:
            # Evidence never cracks anyone: you have to call the lie out.
            instr = (f'The player says: "{text}" and shows you: {ev}. React in character, but keep your story. '
                     "Don't admit anything.")
        elif lie:
            instr = f'The player says: "{text}" and shows you: {ev}. You already confessed. React in character.'
        elif b["role"] == "source" and fid in H.get("solve", []):
            # A starter who got it wrong by mistake sees the proof: that's the hunt solved.
            self.corrected.add(key)
            self._progress()
            self.ledger.update(lambda d: d["npcs"][key].__setitem__("corrected", True))
            reply = self._reveal(key, text, "Oh no. I got it all wrong. Here's what really happened.", "shocked")
            reply["caption"] = f"Yep. {C[key]['short']} started it. By mistake."
            return reply
        elif key == H.get("truth_person"):
            instr = (f'The player says: "{text}" and shows you: {ev}. You get flustered and change the subject. '
                     "Don't admit anything.")
        elif b["role"] == "source":
            instr = (f'The player says: "{text}" and shows you: {ev}. It doesn\'t change what you saw. React in character.')
        else:
            first = key not in self.corrected
            self.corrected.add(key)
            if first:
                self._progress()
                event = "corrected"

            def snap(d):
                bb = d["npcs"][key]["beliefs"]["r1"]
                bb["corrected_by"] = fid
                bb["now_believes"] = "The rumor about the player isn't true."
                d["npcs"][key]["corrected"] = True
            self.ledger.update(snap)
            instr = (f'The player says: "{text}" and shows you: {ev}. Evidence can\'t change. It shows the rumor about the '
                     "player isn't true. You believed it; now you don't. You still don't know who started it. React in character.")
        reply = self._act(key, "show evidence", text, instr)
        reply["event"] = event
        return reply

    def _witness_lines(self, key: str) -> list[str]:
        out = []
        for n in self.notes:
            if n["npc"] != key and not n.get("narr"):
                who = C[n["npc"]]["short"] if n["npc"] else "Overheard in the street"
                out.append(f'{who}: "{n["line"]}"')
        return out[-14:]

    def _call_out(self, key: str, text: str) -> dict:
        self.ledger.update(lambda d: d["player"]["accusations"].append({"npc": key, "text": text, "clock": clock_text(self.clock)}))
        # Every call-out goes through the same steps and the judge, liar or not, so nothing about the
        # answer (its wording or how long it takes) tells the player who is lying.
        lie = self.lie(key)
        catchable = lie is not None and key not in self.cracked
        said = self.ledger.npc(key)["said_to_player"]
        verdict, src = agents.gotcha_judge(self.server, key, lie if catchable else None, said, self._witness_lines(key),
                                           self.pocket_text(), text)
        if catchable and all(f in self.held for f in lie["catch"]):
            verdict = {"verdict": "caught", "reason": "The player holds the proof that catches the lie: "
                       + ", ".join(self.find(f)["title"] for f in lie["catch"]) + f". (Judge said: {verdict['verdict']})"}
            src = "code"
        elif catchable:
            verdict = {"verdict": "not_caught", "reason": "The player doesn't hold the proof that catches the lie yet."
                       f" (Judge said: {verdict['verdict']})"}
            src = "code"
        else:
            verdict = {"verdict": "not_caught", "reason": "Nothing to catch: " + (
                "they already confessed." if key in self.cracked else "they haven't lied.")}
            src = "code"
        self.ledger.update(lambda d: d["player"]["accusations"][-1].update(verdict=verdict["verdict"], reason=verdict["reason"]))
        if verdict["verdict"] == "caught":
            reply = self._crack(key, text)
            reply["judge"] = {**verdict, "source": src}
            return reply
        instr = (f'The player accused you: "{text}". It doesn\'t stick. React in character and keep your story.')
        reply = self._act(key, "call-out that didn't stick", text, instr)
        reply["event"] = "not_caught"
        reply["judge"] = {**verdict, "source": src}
        return reply

    def _crack(self, key: str, text: str) -> dict:
        self.cracked.add(key)
        self._progress()
        self.ledger.update(lambda d: d["npcs"][key].__setitem__("cracked", True))
        reply = self._reveal(key, text, "Fine! You got me. Here's what really happened.", "busted")
        reply["caption"] = f"Yep. That's {C[key]['short']}. They started it."
        return reply

    def _reveal(self, key: str, text: str, said: str, face: str) -> dict:
        """The starter gives up, and the approved truth is shown word for word. The model doesn't
        retell it, so it can't come out wrong."""
        truth = self.hunt["truth"]
        reply = {"line": said, "face": face, "anim": "grovel", "names_source": "none", "source": "code", "slipped": False}
        self._remember(key, text, reply)
        self.notes.append({"npc": key, "clock": self.clock, "where": self.place(key), "you": None,
                           "line": f"What really happened: {truth}", "narr": True})
        reply["event"] = "busted"
        reply["truth"] = truth
        self.outcome = "busted"
        self.ledger.update(lambda d: d["meta"].__setitem__("outcome", "busted"))
        return reply

    # ------------------------------------------------------------------ the NPC Actor's context
    def allowed_source(self, key: str) -> str:
        b = self.belief(key)
        if b["role"] == "source":
            return "myself"
        if b["role"] == "chain":
            return b["heard_from"]
        return "townsfolk"

    def facts(self, key: str) -> str:
        """Everything this person knows, from the ledger, for the NPC Actor and the Consistency Agent."""
        H = self.hunt
        b = self.belief(key)
        n = self.ledger.npc(key)
        lie = self.lie(key)
        cracked = key in self.cracked
        lines = ["WHERE YOU WERE: " + "; ".join(f"{s}: {pl}" for s, pl in n["timeline"].items())]
        idx = self.path.index(key) if key in self.path else None
        if b["role"] == "source":
            told = f'You first told {C[b["told_to"]]["short"]}, at {b["told_where"]}, {b["told_when"]}: "{b["version"]}"'
            if lie and cracked:
                lines.append(f"YOU'VE BEEN CAUGHT and admitted the truth: {lie['truth']}")
            elif lie:
                lines.append(f"THE RUMOR: you started it yourself (your secret). {told}")
                lines.append(f"YOUR LIE (stick to it until you're caught): {lie['lie']}")
            else:
                lines.append(f"WHAT YOU SAW: {H['seen']} {told}")
        elif b["role"] == "chain":
            heard = agents.scrub(self.chain[idx - 1]["version"], key)
            lines.append(f'THE RUMOR: {C[b["heard_from"]]["short"]} told you, at {b["heard_where"]}, {b["heard_when"]}: "{heard}"')
            if b["told_to"]:
                lines.append(f'You passed it on to {C[b["told_to"]]["short"]}, at {b["told_where"]}, {b["told_when"]}: "{b["version"]}"')
            else:
                lines.append(f'This morning you told it to the player, to their face: "{b["version"]}"')
        else:
            lines.append(f'THE RUMOR: you heard it this morning from everyone in the street: "{b["version"]}". '
                         "You don't know who started it.")
            if key == H.get("truth_person"):
                lines.append(f"YOUR SECRET (never admit it, never hint at it; act innocent): {H['truth_secret']}")
        if key in H.get("knows", {}):
            lines.append(f"WHAT YOU KNOW: {H['knows'][key]}")
        if key in self.corrected:
            if b["role"] == "source":
                lines.append(f"You've seen the proof. The truth: {H['truth']} You're embarrassed you got it wrong.")
            else:
                lines.append("You've seen proof that the rumor about the player isn't true. You're a bit embarrassed you believed it.")
        return "\n".join(lines)

    def _plain(self, key: str, label: str, must: str | None, instr: str) -> dict:
        """Part 5: a plain line built by code from the ledger, in the person's voice."""
        c = C[key]
        b = self.belief(key)
        lie = self.lie(key)
        if label == "cracked":
            line = f"Fine! {lie['truth']}"
        elif label == "ask who told":
            if lie and key not in self.cracked:
                line = f"{lie['lie']} {c['phrase']}"
            elif b["role"] == "source" and key in self.cracked:
                line = f"Fine! {lie['truth']}"
            elif b["role"] == "source":
                line = self.hunt["claim"]
            elif must in C:
                line = f"{C[must]['short']} told me, at {b['heard_where']}, {b['heard_when']}."
            else:
                line = f"Everyone in the street was saying it this morning. {c['phrase']}"
        elif label == "show evidence":
            if b["role"] == "source" and key in self.corrected:
                line = f"Oh no. I got it all wrong. {self.hunt['truth']}"
            elif key in self.corrected:
                line = "Huh. So it isn't true. I had it all wrong."
            else:
                line = f"Nice. Doesn't change my story. {c['phrase']}"
        elif label == "call-out that didn't stick":
            line = f"I'm not changing my story. {c['phrase']}"
        elif label in ("ask about", "talk", "return"):
            if lie and key in self.cracked:
                line = f"I already told you. {lie['truth']}"
            elif lie:
                line = f"{lie['lie']} {c['phrase']}"
            elif b["role"] == "source":
                line = self.hunt["claim"]
            elif b["role"] == "chain":
                line = (f"All I know is what {C[b['heard_from']]['short']} told me, at {b['heard_where']}, "
                        f"{b['heard_when']}. {c['phrase']}")
            else:
                line = f"All I know is what everyone was saying in the street this morning. {c['phrase']}"
            if label == "return":
                line = f"Back again? {line}"
        else:
            line = f"{c['phrase']} {agents.scrub(b['version'], key)}"
        return {"line": line.strip(), "face": "talking", "anim": c["anims"][0], "names_source": must or "none"}

    def _act(self, key: str, label: str, text: str | None, instr: str, must_name: str | None = None,
             guard_off: bool = False) -> dict:
        lie = self.lie(key)
        cracked = key in self.cracked
        allowed = must_name or self.allowed_source(key)
        secret = None
        if lie and not cracked:
            secret = {"kind": lie["kind"], "covering_for": lie["covering_for"], "first_listener": lie.get("first_listener")}
        elif key == self.hunt.get("truth_person"):
            secret = {"kind": "truth_person", "guard": self.hunt.get("guard", [])}
        if guard_off:
            secret = None
        hist = prune_dialogue(self.history[key])
        crier = self.morning["crier"]
        ctx = {
            "allowed_source": allowed, "clock": clock_text(self.clock), "facts": self.facts(key),
            "paper": f"{crier['headline']}. {crier['subhead']}",
            "said": self.ledger.npc(key)["said_to_player"],
            "history": [{"who": h["who"], "text": h["text"]} for h in hist],
            "instruction": instr, "label": label, "must_name": must_name, "slip": None,
            "guard": not cracked and not guard_off, "secret": secret, "known": self.p["known"],
            "forbidden": [],
            "fallback": lambda: self._plain(key, label, must_name, instr),
        }
        res, src = agents.npc_actor(self.server, key, ctx, self.gate, self.roles)
        reply = dict(res)
        reply["source"] = src
        reply["slipped"] = False
        self._remember(key, text, reply)
        return reply

    def _remember(self, key, player_text, reply):
        you = f'You: "{player_text}"' if player_text else None
        self.notes.append({"npc": key, "clock": self.clock, "where": self.place(key), "you": you, "line": reply["line"]})
        now = time.time()
        kw = self.ledger.keywords()
        if player_text:
            self.history[key].append({"who": "player", "text": player_text, "t": now,
                                      "relevance_score": relevance_score(player_text, kw)})
        self.history[key].append({"who": "npc", "text": reply["line"], "t": now + 0.001,
                                  "relevance_score": relevance_score(reply["line"], kw)})
        self.ledger.update(lambda d: d["npcs"][key]["said_to_player"].append(reply["line"]))

    # ------------------------------------------------------------------ payoff
    def rewards(self):
        final = self.chain[-1]["version"]
        res, src = agents.reward_menu(self.server, self.source, self.hunt["truth"], final,
                                      self.gate.callbacks[:6], self.roles, self.gate)
        self.reward_options = res["options"]
        return res["options"], src

    def perform(self, idx: int):
        self.choice = self.reward_options[idx]
        res, src = agents.scene_director(self.server, self.source, self.choice, self.roles, self.gate)
        self.scene = res
        culprit = self.source

        def f(d):
            # the comeuppance becomes a new true event, and the loop starts again
            n = len(d["truth"]) + 1
            d["truth"][f"k{n}"] = {"who": "you", "what": f"gave {C[culprit]['short']} a comeuppance: {self.choice['title']}",
                                   "text": f"{cast.GAME_DAY} evening: {self.choice['title']}. {self.choice['description']}",
                                   "from_last_time": True}
            if "liars_hat" in self.choice["props"]:
                d["npcs"][culprit]["status"].append({"effect": "liars_hat", "days_left": 3})
        self.ledger.update(f)
        self.save_actions()
        return res, src

    def save_actions(self):
        """Your actions are saved for later games."""
        acts = []
        snap = self.ledger.snapshot()
        for a in snap["player"]["accusations"]:
            acts.append(f"called out {C[a['npc']]['short']} on {cast.GAME_DAY} at {a['clock']}"
                        + (" and caught them" if a.get("verdict") == "caught" else ", and it didn't stick"))
        for s in snap["player"]["shown"]:
            acts.append(f"showed {self.find(s['find'])['title'].lower()} to {C[s['npc']]['short']} on {cast.GAME_DAY}")
        if self.choice:
            acts.append(f"gave {C[self.source]['short']} a comeuppance on {cast.GAME_DAY} evening: "
                        f"{self.choice['title']} ({self.choice['description']})")
        if self.outcome == "scandal":
            acts.append(f"spent {cast.GAME_DAY} night in the stocks while the town threw pies")
        carry = load_carryover()
        carry["player_actions"] = acts[-6:]
        save_carryover(carry)

    def score(self) -> dict:
        start, final = self.chain[0]["version"], self.chain[-1]["version"]
        gap = 1 - difflib.SequenceMatcher(None, start.split(), final.split()).ratio()
        return {
            "gap": round(gap * 100), "cracked": len(self.cracked), "busted": 1 if self.outcome == "busted" else 0,
            "hours": self.clock - cast.DAY_START, "reputation": self.reputation,
        }

    def replay_rows(self) -> list[dict]:
        rows = [{"npc": None, "sentence": self.hunt["truth"], "diff": None, "line": "", "mutation": "the truth"}]
        prev = None
        for e in self.chain:
            rows.append({"npc": e["npc"], "sentence": e["version"],
                         "diff": None if prev is None else word_diff(prev, e["version"]), "line": "",
                         "mutation": e["mutation"], "written_by": e["written_by"]})
            prev = e["version"]
        return rows
