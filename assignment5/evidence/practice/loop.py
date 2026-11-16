"""Practice: the whole Builder loop with the real models, on the practice Unity project, compile-only builds."""
import sys
from pathlib import Path
sys.path.insert(0, r"C:\cluster\crew")
import builder, common
here = Path(__file__).parent
common.RUNS = here / "runs"
state = builder.run(repo=here / "game", gdd_path=here / "PRACTICE_GDD.md", max_features=5,
                    build=lambda repo, log: builder.build_check(repo, log, method=None),
                    submissions=here / "submissions", work=here / "work")
print(state["status"], state["builder"]["built"], state.get("tokens"))
