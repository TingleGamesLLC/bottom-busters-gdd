"""THROWAWAY TEST (2026-11-13), not part of the game.

Twist a real act, aimed at a player with a life. Qwen makes one town, the player's life and 10 ordinary things the
player really did on Wednesday. Then each act gets the SAME twist prompt on two models: Qwen3.5-4B (the game's model)
and qwen3:30b-instruct on the dev cluster (comparison only; the game still ships one model). First try only, no checks,
no judge. David reads the results side by side.

    python spikes/rumor_twist.py
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, r"C:\cluster")

import ask_cluster  # noqa: E402
from rm import cast  # noqa: E402
from rm.agents import ARR, BASE_SYSTEM, ENUM, OBJ, S  # noqa: E402
from rm.llm import CREATIVE, Server  # noqa: E402
from rumor_backwards import RULES, make_town  # noqa: E402

C = cast.CAST
BIG = "qwen3:30b-instruct"
SYSTEM = BASE_SYSTEM + "\nYou write the one rumor the player hears on Thursday morning."


def town_text(roles):
    return "\n".join(f"- {C[k]['name']}: {roles[k]['job']}, at {roles[k]['place']}." for k in cast.KEYS)


def player_life(srv, roles, names):
    schema = OBJ({"job": S(60, 3), "works_at": S(60, 3), "known_for": S(140, 5), "touchy_about": S(140, 5),
                  "friend": ENUM(names), "cant_stand": ENUM(names)})
    user = f"""THE TOWN:
{town_text(roles)}

The player lives in this town. Give them a life the whole town knows about:
- job: what they do for a living
- works_at: where they do it, a short name
- known_for: the thing they're proud of and known for around town
- touchy_about: the thing they're sensitive about and would hate people to talk about
- friend: their one friend in town
- cant_stand: the one person they can't stand
Ordinary small-town life. PG."""
    obj, _ = srv.call("player_life", BASE_SYSTEM + "\nYou give the player a life in this town.", user, schema, max_tokens=300)
    return obj


def real_acts(srv, roles, life, names, places):
    wed = [s for s in cast.SLOTS if s.startswith("Wednesday")]
    item = OBJ({"what": S(140, 5), "place": ENUM(places), "time": ENUM(wed), "who": ENUM(names)})
    schema = OBJ({"acts": ARR(item, 10, 10)})
    user = f"""THE TOWN:
{town_text(roles)}

THE PLAYER: {life['job']} at {life['works_at']}. Known for: {life['known_for']}. Touchy about: {life['touchy_about']}.
Friends with {life['friend']}, can't stand {life['cant_stand']}.

On Wednesday the player really did 10 ordinary things around town. For each one:
- what: what the player did, a short past-tense phrase starting with a verb, no name in front
- place, time: from the lists
- who: the one townsperson who was there
They are true, ordinary things a person does in a day, and they fit the player's life. None is embarrassing on its own."""
    obj, _ = srv.call("real_acts", BASE_SYSTEM + "\nYou write what the player really did on Wednesday.", user, schema,
                      max_tokens=1200)
    return obj["acts"] if obj else []


def twist_prompt(roles, life, act):
    return f"""THE TOWN:
{town_text(roles)}

THE PLAYER: {life['job']} at {life['works_at']}. Known for: {life['known_for']}. Touchy about: {life['touchy_about']}.
Friends with {life['friend']}, can't stand {life['cant_stand']}.

WHAT THE PLAYER REALLY DID: on {act['time']}, at {act['place']}, with {act['who']} there, the player {act['what'].rstrip('.')}.

{RULES}

By Thursday morning this has turned into a rumor about the player. Somebody twisted what really happened so it hits the
player's life: what they're known for or what they're touchy about. Write the rumor as one short sentence said to the
player's face, starting with "You". It must clearly come from what really happened.

Answer in JSON: {{"rumor": "..."}}"""


def ask_big(user):
    t0 = time.time()
    try:
        d = ask_cluster.call("/v1/chat/completions", {
            "model": BIG, "max_tokens": 200,
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
            "temperature": CREATIVE["temperature"], "top_p": CREATIVE["top_p"]}, timeout=180)
        text = d["choices"][0]["message"]["content"].strip()
    except SystemExit as e:
        return f"(cluster error: {e})", time.time() - t0
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            return json.loads(m.group(0))["rumor"], time.time() - t0
        except (ValueError, KeyError, TypeError):
            pass
    return text, time.time() - t0


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    srv = Server()
    if not srv.start():
        print(srv.error)
        return
    roles, town = make_town(srv)
    names = [C[k]["short"] for k in cast.KEYS]
    places = [town["places"][b]["name"] for b in cast.KIT_ORDER]
    life = player_life(srv, roles, names)
    if not life:
        print("no player life came back")
        srv.stop()
        return
    acts = real_acts(srv, roles, life, names, places)
    print("Player:", life, flush=True)
    rows = []
    for i, act in enumerate(acts, 1):
        user = twist_prompt(roles, life, act)
        obj, stats = srv.call("rumor_twist", SYSTEM, user, OBJ({"rumor": S(200, 5)}), max_tokens=150)
        small = obj["rumor"] if obj else "(no valid answer)"
        big, big_s = ask_big(user)
        rows.append({"act": act, "qwen4b": small, "qwen4b_s": stats["ms"] / 1000, "big": big, "big_s": big_s})
        print(f"{i}. REAL: {act['what']} ({act['place']}, {act['time']}, {act['who']})\n   4B:  {small}\n   30B: {big}", flush=True)
    srv.stop()

    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    stamp = time.strftime("%Y-%m-%d_%H%M")
    (out / f"rumor_twist_{stamp}.json").write_text(json.dumps({"life": life, "town": town, "rows": rows}, indent=2), encoding="utf-8")
    md = [f"# Rumor test: twist a real act, aimed at a player with a life ({time.strftime('%Y-%m-%d %H:%M')})", "",
          "Throwaway test. Qwen3.5-4B made the town, the player's life and the 10 real acts. Each act then got the same "
          f"twist prompt on Qwen3.5-4B and on {BIG} (cluster, comparison only). First try only, no checks, no judge.", "",
          f"Town: {town['street']}. " + "; ".join(f"{C[k]['short']}, {roles[k]['job']} at {roles[k]['place']}" for k in cast.KEYS) + ".", "",
          f"**The player:** {life['job']} at {life['works_at']}. Known for: {life['known_for']}. Touchy about: "
          f"{life['touchy_about']}. Friends with {life['friend']}, can't stand {life['cant_stand']}.", ""]
    for i, r in enumerate(rows, 1):
        a = r["act"]
        md += [f"{i}. **Really did:** {a['what']} ({a['place']}, {a['time']}, {a['who']} there)",
               f"   - **Qwen 4B:** {r['qwen4b']} ({r['qwen4b_s']:.1f}s)",
               f"   - **Cluster 30B:** {r['big']} ({r['big_s']:.1f}s)", ""]
    path = out / f"rumor_twist_{stamp}.md"
    path.write_text("\n".join(md), encoding="utf-8")
    print("Report:", path)


if __name__ == "__main__":
    main()
