"""THROWAWAY TEST (2026-11-13), not part of the game.

Can the small model write rumors backwards, by RUMOR_RULES.md? For each rumor: a fresh town,
code sets up the chain and the root, the model writes the morning version first and undoes
each person's change back to the truth, a judge checks it, and each person's spoken line is
written. Results go to results/rumor_spike_<stamp>.md for David to read.

    python spikes/rumor_backwards.py           10 rumors
    python spikes/rumor_backwards.py --n 3
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rm import agents, cast  # noqa: E402
from rm.agents import (ARR, BASE_SYSTEM, BOOL, ENUM, OBJ, S, PremiseFailed, borrowed, cut_off,  # noqa: E402
                       has_marker, norm, overlaps, place_in, run, sheet, strings_ok, tidy)
from rm.llm import Server  # noqa: E402

C = cast.CAST

RULES = """WHAT A RUMOR IS. Every version about the player must be all five:
1. It stings: it would change how the town sees the player. People would whisper it, and the player would want it cleared.
2. It's believable: someone in town could picture it happening. Wrong, exaggerated or unfair is fine. Impossible or nonsense is not.
3. It's one claim: one thing the player supposedly did, said in one breath. Never two stories.
4. It's petty or embarrassing, not a serious crime: PG-13, nothing violent, nothing sexual.
5. It's about the player."""

CHANGE = {
    "gary": "makes it one step bigger: more often, more of it, or more people. Never impossible.",
    "toby": "adds one detail that fits the claim and makes it worse for the player. His sales pitch goes in how he says it, never in the claim.",
    "bev": "adds who was hurt, shocked or embarrassed by it. Believable.",
    "mildred": "adds what it led to: one consequence of the same story. Never a second, separate story.",
    "ozzie": "swaps the other person in the story for a different townsperson, on purpose.",
}

# Rumor shapes (approved for this test 2026-11-13): code picks the kind of claim, the model fills in this town's specifics.
SHAPES = {
    "secret_habit": "a secret habit: something small and a little silly the player supposedly does in private, that they'd hate the town to know.",
    "fear": "a fear: something ordinary and harmless the player is supposedly scared of.",
    "banned": "banned: the player was supposedly told to leave one of the places and not come back.",
    "crush": "a crush: the player supposedly has a crush on one townsperson (the other person in the story).",
    "debt": "a debt: the player supposedly owes one townsperson money and keeps dodging them (the other person in the story).",
    "cheating": "cheating: the player supposedly cheated at a game, a contest or a bet.",
}
SHAPE_KEYS = list(SHAPES)
NEEDS_OTHER = {"crush", "debt"}


def make_town(srv):
    for _ in range(3):
        try:
            obj, _ = agents.casting_director(srv)
            roles = {k: dict(obj["roles"][k]) for k in cast.KEYS}
            town, _ = agents.town_architect(srv, roles)
            for k in cast.KEYS:
                roles[k]["place"] = town["places"][roles[k]["building"]]["name"]
            return roles, town
        except PremiseFailed:
            continue
    raise RuntimeError("couldn't make a town")


def setup(rng: random.Random, roles: dict, want_root: str, shape: str) -> dict:
    """Code sets up the hunt before any words: the chain, the root, who really did it."""
    L = rng.choice([3, 4, 4, 5])
    chain = rng.sample(cast.KEYS, L)
    culprit = chain[0]
    root, real, how = want_root, None, None
    if root == "wrong_person":
        outside = [k for k in cast.KEYS if k not in chain]
        if not outside:
            chain = chain[:4]
            outside = [k for k in cast.KEYS if k not in chain]
        friend = roles[culprit]["friend"]
        if friend in outside:
            real, how = friend, f"on purpose, to cover for their friend {C[friend]['short']}"
        else:
            real = rng.choice(outside)
            how = "on purpose" if culprit == "ozzie" else f"by mistake: they mixed the player up with {C[real]['short']}"
    return {"chain": chain, "culprit": culprit, "root": root, "real": real, "how": how, "shape": shape}


def sentence(v: dict) -> str:
    s = f"You {v['act']}, {v['scale']}, at {v['place']}, {v['time']}"
    if v["other"] != "none":
        s += f", with {v['other']} there"
    for x in v["extras"]:
        s += f"; {x.rstrip('.')}"
    return s + "."


def write_rumor(srv, roles, town, plan) -> tuple[dict | None, list[dict], list[str]]:
    chain, culprit = plan["chain"], plan["culprit"]
    names = [C[k]["short"] for k in cast.KEYS]
    places = [town["places"][b]["name"] for b in cast.KIT_ORDER]
    need_other = "ozzie" in chain[1:] or plan["shape"] in NEEDS_OTHER
    morning = OBJ({"act": S(180, 5), "scale": S(120, 1), "place": ENUM(places), "time": ENUM(cast.SLOTS),
                   "other": ENUM(names if need_other else names + ["none"])})
    undo = {}
    for k in reversed(chain[1:]):   # backwards: the messenger first
        if k == "gary":
            undo[k] = OBJ({"before": S(120, 1)})        # his "after" is the morning scale; code fills it in
        elif k == "ozzie":
            undo[k] = OBJ({"before": ENUM(names)})      # his "after" is the morning's other person; code fills it in
        else:
            undo[k] = OBJ({"added": S(180, 3)})
    who = [C[plan["real"]]["short"]] if plan["real"] else ["nobody"]
    schema = OBJ({"morning": morning, "undo": OBJ(undo),
                  "root": OBJ({"who": ENUM(who), "what_really_happened": S(300, 10), "detail": S(140, 2), "motive": S(300, 10)})})
    people = "\n".join(f"- {C[k]['name']}: {roles[k]['job']}, at {roles[k]['place']}. Friends with {C[roles[k]['friend']]['short']}, "
                       f"can't stand {C[roles[k]['cant_stand']]['short']}." for k in cast.KEYS)
    m = chain[-1]
    if plan["root"] == "wrong_person":
        started = (f"{C[plan['real']]['short']} really did something small and a little embarrassing on Tuesday or Wednesday. "
                   f"{C[culprit]['short']} put the player's name on it, {plan['how']}. {C[culprit]['short']}'s first version is "
                   f"exactly what {C[plan['real']]['short']} did, with the player's name instead.")
    else:
        started = (f"Nothing happened. {C[culprit]['short']} made the whole thing up about the player. The reason comes from who "
                   f"they are: a grudge, a debt, covering for themselves, or a stunt.")
    later = "\n".join(f"- {C[k]['short']} ({C[k]['type']}): {CHANGE[k]}" for k in chain[1:])
    user = f"""THE TOWN, this game's roles:
{people}
PLACES: {", ".join(places)}
WHEN: {", ".join(cast.SLOTS)}

{RULES}

THE KIND OF RUMOR: {SHAPES[plan['shape']]} Every version is this kind of claim.

THE CHAIN, in the order it was passed: {" -> ".join(C[k]['short'] for k in chain)}. {C[m]['short']} tells it to the player's face on Thursday morning.

HOW IT STARTED: {started}

EACH LATER PERSON CHANGES EXACTLY ONE THING when they pass it on. Each change makes it worse for the player and keeps it one believable claim:
{later}

WRITE IT BACKWARDS:
1. morning: the rumor as {C[m]['short']} believes it on Thursday morning, in parts.
   - act: what the player supposedly did, a short past-tense phrase with no name in front ("You" goes in front of it), and no place or time in it. Leave out the details later people added; those go in undo.
   - scale: how much or how often.
   - place, time: from the lists.
   - other: the one other townsperson in the story (who it happened to, or who saw it){'' if need_other else ', or "none"'}.
2. undo: starting with {C[m]['short']} and working back up the chain, what each person changed. For a detail someone added, write just that detail. For Gary, the smaller scale it had before he made it bigger. For Ozzie, the other person who was really in the story before he swapped the name.
3. root: who really did it, what really happened (one plain sentence), one exact small detail that proves the real story (an exact time, amount or object), and why {C[culprit]['short']} made it about the player."""

    def check(o):
        mo, un = o["morning"], o["undo"]
        first = norm(mo["act"]).split()[:1]
        if first and first[0] in {"you", "they", "he", "she"} | {c["short"].lower() for c in C.values()}:
            return "act has no name or pronoun in front of it."
        if "gary" in un and norm(un["gary"]["before"]) == norm(mo["scale"]):
            return "Gary has to make the scale bigger, so the scale before him is smaller."
        if "ozzie" in un and un["ozzie"]["before"] == mo["other"]:
            return "Ozzie swapped the other person, so before him it was someone different."
        added = [un[k]["added"] for k in un if "added" in un[k]]
        if len({norm(a) for a in added}) != len(added):
            return "Each added detail is different."
        if plan["real"]:
            act_s = agents.stems(mo["act"])
            if len(act_s & agents.stems(o["root"]["what_really_happened"])) < max(1, (len(act_s) + 1) // 2):
                return "What really happened is the same act as the rumor, done by the real person. Use the same words for the act."
        return None

    tries = []
    notes = ""
    best = None
    for attempt in range(1, 4):
        obj, stats = srv.call("rumor_writer", BASE_SYSTEM + "\nYou are the Rumor Writer. You write rumors backwards, from the version the player hears to the truth.",
                              user + notes, schema, max_tokens=900)
        reason = None
        if obj is None:
            reason = "That was not valid JSON."
        else:
            obj = tidy(obj)
            act = obj["morning"]["act"].strip()
            for lead in ("you ", "You ", "they ", "They "):   # code drops a leading "you"; "You" is added in front anyway
                if act.startswith(lead):
                    act = act[len(lead):]
            obj["morning"]["act"] = act
            reason = strings_ok(obj) or cut_off(obj, schema) or check(obj)
        versions = derive(obj, plan) if reason is None else None
        verdict = None
        if reason is None:
            verdict = judge(srv, versions, obj, plan)
            if not verdict["pass"]:
                reason = "The judge sent it back: " + verdict["why"]
        tries.append({"attempt": attempt, "ok": reason is None, "note": reason or "pass", "ms": stats["ms"]})
        if obj is not None and versions is not None:
            best = (obj, versions, verdict)
        if reason is None:
            return best, tries, []
        notes = f"\n\nYOUR LAST ANSWER WAS SENT BACK: {reason} Write it again and fix that."
    return best, tries, ["failed all 3 tries"]


def derive(o: dict, plan: dict) -> list[dict]:
    """Code builds every version from the morning parts and the undo steps. Top = the culprit's first version."""
    mo, un = o["morning"], o["undo"]
    v = {"act": mo["act"], "scale": un["gary"]["before"] if "gary" in un else mo["scale"], "place": mo["place"],
         "time": mo["time"], "other": un["ozzie"]["before"] if "ozzie" in un else mo["other"], "extras": []}
    out = [{"who": plan["chain"][0], "change": "made it about you" if plan["root"] == "wrong_person" else "made it up",
            "v": dict(v, extras=[])}]
    for k in plan["chain"][1:]:
        v = dict(v, extras=list(v["extras"]))
        if k == "gary":
            v["scale"] = mo["scale"]
            change = f"made it bigger: \"{un['gary']['before']}\" became \"{mo['scale']}\""
        elif k == "ozzie":
            v["other"] = mo["other"]
            change = f"swapped {un['ozzie']['before']} for {mo['other']}"
        else:
            v["extras"].append(un[k]["added"])
            change = f"added: {un[k]['added']}"
        out.append({"who": k, "change": change, "v": v})
    return out


def judge(srv, versions, o, plan) -> dict:
    n = len(versions)
    item = OBJ({"one_claim": BOOL, "stings": BOOL, "believable": BOOL, "petty_not_crime": BOOL, "note": S(160)})
    schema = OBJ({"versions": ARR(item, n, n), "each_step_worse": BOOL, "root_fits": BOOL, "note": S(200)})
    listed = "\n".join(f"{i + 1}. As {C[x['who']]['short']} told it: {sentence(x['v'])}" for i, x in enumerate(versions))
    root = o["root"]
    user = f"""{RULES}

A rumor about the player, every version from the first to the one the player hears:
{listed}

What really happened: {root['what_really_happened']} ({"made up by " + C[plan['culprit']]['short'] if plan['root'] == 'made_up' else "really done by " + root['who']}). Why it became about the player: {root['motive']}

For each version: one_claim, stings, believable, petty_not_crime (all true or false), and a short note.
each_step_worse: does each version make it a little worse for the player than the one before?
root_fits: does the first version really come from what really happened (the same act with the player's name on it, or a clear invention)?
note: one short sentence. Be strict: the player should hear a rumor someone would really whisper."""
    obj, _ = srv.call("rumor_judge", BASE_SYSTEM + "\nYou are the Rumor Judge. You are strict and fair.", user, schema,
                      mode="judge", max_tokens=110 * n + 160)
    if obj is None:
        return {"pass": True, "why": "judge unreadable", "raw": None}
    bad = []
    for i, v in enumerate(obj["versions"]):
        miss = [k for k in ("one_claim", "stings", "believable", "petty_not_crime") if not v[k]]
        if miss:
            bad.append(f"version {i + 1} fails {', '.join(miss)} ({v['note']})")
    if not obj["each_step_worse"]:
        bad.append("not every step makes it worse")
    if not obj["root_fits"]:
        bad.append("the first version doesn't come from what really happened")
    return {"pass": not bad, "why": "; ".join(bad) or "pass", "raw": obj}


def spoken(srv, key, v, to, is_last) -> str:
    c = C[key]
    to_text = "to the player's face (say \"you\")" if is_last else f"to {C[to]['short']} (talk about the player as \"they\")"
    schema = OBJ({"line": S(260, 10)})
    user = f"""THE SPEAKER: {sheet(key)}
WHAT THEY'RE PASSING ON: {sentence(v)}
Write what {c['short']} says {to_text}: one or two short sentences, in their voice, with {c['say']}. Keep every part of the story.{' Any sales pitch goes around the story, not in it.' if key == 'toby' else ''}"""

    def check(o):
        if not has_marker(o["line"], key):
            return f"Use {c['short']}'s fingerprint: {c['fingerprint']}."
        return borrowed(o["line"], key)

    obj, src = run(srv, "line_writer", BASE_SYSTEM + "\nYou write how one person says something out loud.", user, schema, check,
                   {"line": f"{c['phrase']} {sentence(v)}"}, label=f"{c['short']}'s line")
    return obj["line"] + (" (plain line built by code)" if src == "code" else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10)
    args = ap.parse_args()
    srv = Server()
    if not srv.start():
        print(srv.error)
        return
    rng = random.Random(7)
    results = []
    t_all = time.time()
    for i in range(args.n):
        t0 = time.time()
        roles, town = make_town(srv)
        plan = setup(rng, roles, "wrong_person" if i % 2 == 0 else "made_up", SHAPE_KEYS[i % len(SHAPE_KEYS)])
        best, tries, fail = write_rumor(srv, roles, town, plan)
        lines = []
        if best:
            obj, versions, verdict = best
            for j, x in enumerate(versions):
                last = j == len(versions) - 1
                to = None if last else versions[j + 1]["who"]
                lines.append(spoken(srv, x["who"], x["v"], to, last))
        results.append({"i": i + 1, "plan": plan, "town": town, "roles": {k: roles[k]["job"] for k in cast.KEYS},
                        "best": best, "tries": tries, "lines": lines, "seconds": round(time.time() - t0, 1)})
        status = "passed" if tries and tries[-1]["ok"] else "FAILED"
        print(f"rumor {i + 1}: {plan['shape']}, {plan['root']}, {len(plan['chain'])} people, judge {status} after {len(tries)} tries, "
              f"{time.time() - t0:.0f}s", flush=True)
    srv.stop()
    path = report(results, time.time() - t_all)
    print("Report:", path)


def report(results, total) -> Path:
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    stamp = time.strftime("%Y-%m-%d_%H%M")
    (out / f"rumor_spike_{stamp}.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    first = sum(1 for r in results if r["tries"] and r["tries"][0]["ok"])
    passed = sum(1 for r in results if r["tries"] and r["tries"][-1]["ok"])
    md = [f"# Rumor test: built backwards, with shapes, {time.strftime('%Y-%m-%d %H:%M')}", "",
          "Throwaway test, not the game. Qwen3.5-4B. Each rumor gets a fresh town. Code picks the shape, the chain and the root; the model "
          "writes the morning version first and undoes each person's change back to the truth; a judge checks it against "
          "RUMOR_RULES.md.", "",
          f"- Rumors: {len(results)}. Passed the judge on the first try: {first}. Passed within 3 tries: {passed}.",
          f"- Total time: {total / 60:.1f} minutes, about {total / max(1, len(results)):.0f} seconds per rumor (town included).", ""]
    for r in results:
        p = r["plan"]
        status = "passed" if r["tries"] and r["tries"][-1]["ok"] else "failed the judge all 3 tries (last try shown)"
        kind = "Wrong person" if p["root"] == "wrong_person" else "Made up"
        md += [f"## Rumor {r['i']}: {p['shape'].replace('_', ' ')}, {kind.lower()}, {len(p['chain'])} people. Judge: {status}, try {len(r['tries'])}", ""]
        md.append(f"Town: {r['town']['street']}. " + "; ".join(
            f"{C[k]['short']}, {r['roles'][k]}" for k in cast.KEYS) + ".")
        md.append("")
        if not r["best"]:
            md += ["No usable rumor came back.", ""]
            continue
        obj, versions, verdict = r["best"]
        m = versions[-1]
        md.append(f"**What you hear Thursday morning, from {C[m['who']]['short']}:** \"{r['lines'][-1]}\"")
        md.append("")
        md.append("**Back up the chain:**")
        for j in range(len(versions) - 1, -1, -1):
            x = versions[j]
            who = C[x["who"]]["short"]
            role = "started it" if j == 0 else x["change"]
            md.append(f"- **{who}** ({role}): {sentence(x['v'])}")
            md.append(f"  - How {who} said it: \"{r['lines'][j]}\"")
        root = obj["root"]
        md.append("")
        md.append(f"**What really happened:** {root['what_really_happened']} Proof: {root['detail']}.")
        md.append(f"**Why {C[p['culprit']]['short']} made it about you:** {root['motive']}")
        if verdict:
            md.append(f"**Judge:** {verdict['why']}")
        md += [f"Tries: " + " | ".join(f"{t['attempt']}: {t['note'][:140]}" for t in r["tries"]), ""]
    path = out / f"rumor_spike_{stamp}.md"
    path.write_text("\n".join(md), encoding="utf-8")
    return path


if __name__ == "__main__":
    main()
