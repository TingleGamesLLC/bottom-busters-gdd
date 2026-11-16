"""Practice: the Builder's GDD read on the real GDD, with the real cluster model. Results go to this folder only."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, r"C:\cluster\crew")
import builder, codebase, common, gdd
here = Path(__file__).parent
common.PROMPT_LOG = here / "prompts.jsonl"
t = time.time()
classes = builder.class_names(codebase.scan(builder.REPO))
reqs, dropped = builder.requirements(gdd.sections(), classes, cache=here / "requirements_cache.json")
(here / "requirements.json").write_text(json.dumps([r.__dict__ for r in reqs], indent=2), encoding="utf-8")
(here / "dropped.json").write_text(json.dumps(dropped, indent=2), encoding="utf-8")
by = {}
for r in reqs:
    by[r.status] = by.get(r.status, 0) + 1
print(f"{len(reqs)} requirements, {len(dropped)} dropped, {by}, {time.time() - t:.0f}s, tokens {common.usage.tokens}")
