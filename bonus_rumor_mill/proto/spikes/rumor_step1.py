"""THROWAWAY TEST (2026-11-13), not part of the game.

Step 1 only: can the small model write ONE good morning rumor of a given shape, when that is its only job?
One town, then 10 calls, one rumor each, first try only, no retries and no judge. David reads the results.

    python spikes/rumor_step1.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rm import cast  # noqa: E402
from rm.agents import BASE_SYSTEM, OBJ, S  # noqa: E402
from rm.llm import Server  # noqa: E402
from rumor_backwards import RULES, SHAPE_KEYS, SHAPES, make_town  # noqa: E402

C = cast.CAST


def main():
    srv = Server()
    if not srv.start():
        print(srv.error)
        return
    roles, town = make_town(srv)
    people = "\n".join(f"- {C[k]['name']}: {roles[k]['job']}, at {roles[k]['place']}." for k in cast.KEYS)
    schema = OBJ({"rumor": S(160, 5)})
    rows = []
    for i in range(10):
        shape = SHAPE_KEYS[i % len(SHAPE_KEYS)]
        user = f"""THE TOWN:
{people}

{RULES}

THE KIND OF RUMOR: {SHAPES[shape]}

Write the rumor as one short sentence said to the player's face, starting with "You". One thing the player supposedly did. Nothing else."""
        obj, stats = srv.call("rumor_step1", BASE_SYSTEM + "\nYou write the one rumor the player hears on Thursday morning.",
                              user, schema, max_tokens=120)
        text = obj["rumor"] if obj else "(no valid answer)"
        rows.append((shape, text, stats["ms"]))
        print(f"{i + 1}. {shape}: {text}", flush=True)
    srv.stop()
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    stamp = time.strftime("%Y-%m-%d_%H%M")
    md = [f"# Rumor test, step 1 only: one morning rumor per call, {time.strftime('%Y-%m-%d %H:%M')}", "",
          "Throwaway test. Qwen3.5-4B. One town; each call gets only the town, the rumor rules and a shape, and writes "
          "one sentence. First try only, no retries, no judge.", "",
          f"Town: {town['street']}. " + "; ".join(f"{C[k]['short']}, {roles[k]['job']} at {roles[k]['place']}" for k in cast.KEYS) + ".", ""]
    for i, (shape, text, ms) in enumerate(rows, 1):
        md.append(f"{i}. **{shape.replace('_', ' ')}:** {text} ({ms / 1000:.1f}s)")
    path = out / f"rumor_step1_{stamp}.md"
    path.write_text("\n".join(md) + "\n", encoding="utf-8")
    print("Report:", path)


if __name__ == "__main__":
    main()
