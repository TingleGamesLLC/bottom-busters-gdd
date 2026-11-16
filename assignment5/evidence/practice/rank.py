"""Practice, read only: the Builder's GDD read, gap pass and ranking on the real GDD and the real game code, with the real
cluster model. Nothing is written to the game; every result goes to this folder."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, r"C:\cluster\crew")
import builder, codebase, common, gdd
here = Path(__file__).parent
common.PROMPT_LOG = here / "prompts.jsonl"
t = time.time()
index = codebase.scan(builder.REPO)
reqs, dropped = builder.requirements(gdd.sections(), builder.class_names(index), cache=here / "req_cache.json")
print(f"GDD read: {len(reqs)} requirements, {len(dropped)} dropped, {time.time() - t:.0f}s", flush=True)
gaps, present = builder.find_gaps(reqs, index, cache=here / "looks_cache.json")
dirty = codebase.dirty(builder.REPO)
waiting = builder.waiting_counts()
ranked = builder.rank(gaps, dirty, waiting, set())
(here / "ranking.json").write_text(json.dumps({"gaps": [b for _, b, _ in ranked], "present": present, "waiting": waiting},
                                              indent=2), encoding="utf-8")
print(f"gap pass: {len(present)} met, {len(gaps)} gaps, {time.time() - t:.0f}s, tokens {common.usage.tokens}")
for s, b, g in ranked[:15]:
    print(s, b["id"], b["feature"], "|", b.get("math") or b.get("skipped"), "|", b["files"])
