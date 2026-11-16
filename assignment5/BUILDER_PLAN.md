# Builder Agent (Assignment #5) Implementation Plan

> Claude builds this in one session, task by task, with no subagents (BBUST rule: no agent fleets). `DAVID:` marks his
> rulings; everything else here is Proposed until he approves it.

**Goal:** a script version of the crew's Builder that reads the Bottom Busters GDD, scans the game's C# code, finds
GDD features that aren't built, ranks them with `priority_score()`, writes the code for the top one, rebuilds the game,
and rescans until nothing is left or its run limit is reached.

**Architecture:** one new crew agent in `C:\cluster\crew`, built on the crew's own pieces: `common.ask_json` on the
unused `crew-builder` MindRouter key, the run folder with `prompts.jsonl`, two cheeks, and `CrewStop`. The model reads
and writes; plain code checks every claim it makes against the real GDD and the real code (the Assignment #4 rule: a
quote that isn't there word for word is dropped). The game's own headless build is the compile check.

**Tech stack:** Python 3 and pytest (as the rest of the crew), qwen3:30b-instruct through MindRouter, Unity 6.3
batchmode builds per `C:\bbust\BBUST\docs\build.md`.

**Spec:** Assignment #5 (below); GDD Section 16, the Builder row ("Reads this GDD and the project's coding rules and
implements one approved feature at a time in C#, then runs the existing build-and-verify loop"); `BBUST_CREW_DESIGN.md`
Section 7, Builder.

**Deadline:** tonight, 2026-11-15, 10:59 PM Central (11:59 PM ET).

Assignment #5 asks for: `priority_score()` that orders the work; a gap pass comparing the scanned code with the GDD's
features; a code-writing step; a loop that rescans after each write and stops when every requirement is met. Hand-in:
the source, at least one working feature in the game made by the agent, and a README saying what it built, why it
picked that feature, and what had to be changed by hand before it went in.

## What I confirmed before planning (2026-11-15)

- Nothing built covers this. The crew makes content only (characters, roast lines, hats, backgrounds). The Builder
  exists only on paper: `BBUST_CREW_DESIGN.md` Section 7 defines it as Claude Code in a session David starts.
- Reusable as is: `common.py` (`ask`, `ask_json`, `Run`, `Cheeks`, `CrewStop`, per-agent keys and token caps) and
  `gdd.py` (reads `C:\bbust\BBUST\BOTTOM_BUSTERS_GDD.md`, today only Section 21).
- The `crew-builder` key exists on Node A and has never been used. Cluster models: qwen3:30b-instruct, qwen3:8b,
  qwen2.5:14b-instruct, qwen2.5vl:7b. There is no code-specific model.
- The game's code: 171 C# files, about 56,500 lines, in `Assets/Scripts/` (UI 54 files, Replay 24, Powerups 24,
  Core 22, Characters 16, Effects 10, Level 8, Audio 8, Services 5).
- **The Builder's first job is not done.** `GameManager.LoadCharacterPrefabs` loads `player2` to `player20` only;
  `MenuVisualizer` has two hard-coded lists of ten (`Art`, `SplatSkins`); the first names (Larry, Doug...) appear
  nowhere in the code; 31 character submissions are waiting in `C:\cluster\submissions\characters`, numbered up to
  `player30`. No character is approved or installed yet.
- **The browser build:** `HeadlessBuild.BuildWeb` was added today (DAVID, 2026-11-15, in its comment: "the itch demo as
  a browser game"). The "Browser Bottom Busters" Claude session is working in the same tree right now: 22 code files
  modified and not committed, `GameManager.cs`, `MainMenuController.cs` and `MenuWheel.cs` among them, and new touch
  controls last saved at 2:27 PM. `CharacterSelect.cs` and `MenuVisualizer.cs` are clean.
- The two GDD copies differ by one line (Section 6.3, powerup odds); the `C:\gdd` copy is the newer one.
- Unity's Editor is not open. The 0.9.3 builds took about 35 seconds each.
- Paperclip isn't running; nothing in this plan needs it.

## Decisions for David before Task 1

DAVID, 2026-11-15: no GDD changes for this ("we are ignoring that note its not relevant"), and Endless and Custom
Game stay goals ("im not changing those goals yet").

DAVID, 2026-11-15 ("go with your recommendations"):
1. **The write step:** qwen3:30b-instruct on the `crew-builder` key writes first; if its code fails the build twice,
   Claude Code (headless, `claude -p`) takes over that feature.
2. **The game folder:** the agent works in `C:\bbust\BBUST`, and the "Browser Bottom Busters" session is asked to pause
   for the official run only. The guards below still apply.
3. **No run on the game until everything is built and tested** ("im not comfortable with you kicking off the
   automations yet until i know you built everything correctly"). Testing comes first: unit tests with a fake model
   and a fake codebase, then a practice run with the real models on a scratch project outside the game. Then one
   official run on the game, with one stop for David's yes on the pick. The hand-in shows that one run.

## Global constraints

- BBUST: David tests and David says commit. The agent never commits, pushes or launches the game.
- The agent never edits a file `git status` shows as modified (another session's work), writes only under
  `Assets/Scripts/`, deletes nothing, and never renames or moves anything under `Resources` or a scene.
- One feature per run on the real game (GDD Section 16: "one approved feature at a time"), and only after David
  approves the pick from a dry run.
- A build is done only when the log says `HeadlessBuild: Succeeded`. The Editor must be closed: if `Unity.exe` is
  running, the run stops and says so. Unity is reopened after a headless build.
- Every claim from the model is checked by plain code: a GDD quote must be in its section word for word, a code quote
  must be in the named file, an edit's `find` text must occur exactly once.
- The GDD goes to the model one section at a time (the cluster's context size isn't confirmed, and the whole GDD is
  about 13,000 tokens). Sections 0 (the change list) and 20 (risks and open questions) are skipped: they aren't
  features.
- No `/code-review` on BBUST. Verification is a clean build and a read of the diff; then David plays it.

## Review focus

1. **The model invents a GDD quote** for a requirement: plain code drops the requirement and logs why (Task 2 test).
2. **The model says a feature is built,** quoting code that isn't in the file: the quote is dropped and the gap stands
   (Task 3 test).
3. **An edit whose `find` text appears zero or two-plus times:** refused, costs a cheek, nothing written (Task 5 test).
4. **A target file that's modified in git, or outside `Assets/Scripts/`:** the gap is skipped with the reason, never
   written (Task 4 and Task 5 tests).
5. **The build fails twice, or Unity is open:** the run restores only the files it wrote or changed this run, from
   its own backup, and stops with the compiler errors (Task 5 test, with a fake build).

---

## Files

- Create `C:\cluster\crew\codebase.py`: scanning and searching the game's code, and which files are modified in git.
- Create `C:\cluster\crew\builder.py`: requirements, gap pass, `priority_score()`, the write step, the loop, the CLI.
- Create `C:\cluster\crew\test_codebase.py` and `test_builder.py`.
- Modify `C:\cluster\crew\gdd.py`: add `sections()`.
- Modify `C:\cluster\crew\common.py`: `RUN_CAPS["builder"] = 300000`.
- Create the hand-in `C:\gdd\assignment5\`: `README.md`, `code\` (copies), `official_run\` (the run folder).

## Task 1: Code scan

**Produces** (in `codebase.py`):
- `scan(root: Path) -> Index`: every `.cs` file under `root`, `Index.files: dict[str, str]` from path relative to the
  repo (`Assets/Scripts/UI/CharacterSelect.cs`) to its text.
- `search(index: Index, terms: list[str], limit: int = 20) -> list[Hit]`: case-insensitive whole-word search,
  `Hit(path, line_no, line)`, ranked by how many terms a file matches.
- `outline(index: Index, path: str) -> str`: the file's class, method and field signatures only, for prompts.
- `dirty(repo: Path) -> set[str]`: paths from `git status --porcelain` (modified, added, untracked), relative to the repo.

Tests (`test_codebase.py`, a temp folder with three small `.cs` files and a temp git repo):
`test_scan_reads_only_cs`, `test_search_whole_words_ranked`, `test_outline_keeps_signatures_drops_bodies`,
`test_dirty_lists_modified_and_untracked`.

## Task 2: Requirements from the GDD

**Produces:**
- `gdd.sections(path: Path = SOURCE) -> list[Section]`: `Section(number, title, text)` for every `##` and `###`
  heading; Section 21's parts come out as 21.1 to 21.4.
- `builder.requirements(sections, ask=common.ask_json) -> list[Requirement]`, with
  `Requirement(id, section, feature, quote, paragraph, status, visible, content, evidence)`; `paragraph` is the
  section's paragraph or bullet that holds the quote, filled in by plain code:
  - `status`: one of `built`, `planned`, `retired`, `on_hold`, read from the section's own words.
  - `visible`: would a player see it.
  - `content`: `characters`, `backgrounds`, `wardrobe`, `roast_lines` or `none`: which crew output it would let into
    the game.
  - `evidence`: 3 to 6 identifiers or string literals that would exist in the code if the feature were built.
- One model call per section, asking for one JSON object `{"features": [...]}`. Plain code keeps a feature only if
  its `quote` is in that section word for word; dropped ones go in the run's `dropped.json` with the reason.
- Cached in `work/builder_requirements.json` by the GDD file's SHA-256, so rescans in the loop don't re-read the GDD.

Tests (fake `ask`): `test_sections_split_21_parts`, `test_invented_quote_dropped`,
`test_cache_reused_when_gdd_unchanged`, `test_sections_0_and_20_skipped`.

## Task 3: The gap pass

**Produces:** `builder.find_gaps(reqs, index, ask=common.ask_json) -> list[Gap]`, with
`Gap(req, targets: list[str], hits: list[Hit], why: str)`.

- Requirements marked `retired` or `on_hold` are not gaps.
- For every other requirement, `codebase.search(index, req.evidence)`. Then the second look: the model gets the
  requirement, its quote and the top hits' lines, and answers `{"built": bool, "code_quote": str, "targets": [paths]}`.
  - `built` holds only if `code_quote` is in one of the hit files word for word; otherwise it's a gap.
  - For a gap, `targets` are the files the change would touch. Plain code keeps only real paths under
    `Assets/Scripts/`, plus at most one new file path the model names.
- Second-look answers are cached by (requirement id, SHA-256 of the hit files), so a rescan re-asks only where a
  file changed.

Tests: `test_built_without_real_code_quote_is_gap`, `test_built_with_real_quote_is_not_gap`,
`test_retired_and_on_hold_never_gaps`, `test_targets_outside_scripts_dropped`, `test_second_look_cached`.

## Task 4: `priority_score()`

**Produces:** `builder.priority_score(gap, dirty: set[str], waiting: dict[str, int], failed: set[str])
-> tuple[int | None, dict]`. `None` means skipped; the dict is the breakdown that the run log and the README quote.

```
skipped (None) when: any target is in `dirty`  -> "skipped: <file> has uncommitted changes"
                     the requirement id is in `failed` (stopped twice in an earlier run)
score = 3 * unblocks   (waiting[gap.req.content] > 0: crew output is waiting in C:\cluster\submissions)
      + 2 * ruling     (the quote's paragraph carries "Studio Director" or "DAVID" with a date)
      + 2 * visible
      + size           (1 target file: 2; 2 or 3: 1; 4 or more: 0)
ties: GDD order
```

`waiting` is counted by plain code from the folders in `C:\cluster\submissions`. `failed` is read from
`work/builder_failed.json`.

Tests: `test_dirty_target_skipped_with_reason`, `test_failed_requirement_skipped`,
`test_waiting_submissions_raise_score`, `test_ruling_detected_from_paragraph`, `test_small_change_outranks_large`,
`test_ties_keep_gdd_order`.

## Task 5: The write step

**Produces:**
- `builder.write_feature(gap, index, ask=common.ask_json) -> Change`, `Change(new_files: dict[str, str],
  edits: list[Edit])`, `Edit(path, find, replace)`. The prompt holds: the requirement and its GDD quote; the target
  files' outlines and the lines around the hits; the traps from BBUST's `CLAUDE.md` that apply to UI and characters
  (`UIKit.FindMenuCanvas`, zeroing `sizeDelta` on stretched transforms, `FullRect`, recording anything drawn during play
  for replays, never renaming under `Resources`); and "new code in a new file, the smallest hookup in the existing one."
- `builder.apply(change, repo, dirty) -> Backup`: refuses (a cheek, nothing written) a path that's dirty, outside
  `Assets/Scripts/`, an existing file passed as new, or a `find` that doesn't occur exactly once. It writes a backup of
  every file it touches first.
- `builder.build_check(repo) -> tuple[bool, list[str]]`: stops if `Unity.exe` is running; runs
  `HeadlessBuild.Build` as in `docs/build.md`; true only on `HeadlessBuild: Succeeded`; otherwise the `error CS` lines.
- On a failed build, the errors go back to the model as a fix prompt (a cheek). Two cheeks gone:
  `builder.restore(backup)` puts back exactly what this run changed, the requirement goes in `builder_failed.json`, and
  the run stops with the errors.

Tests (fake `ask`, fake build): `test_find_must_occur_once`, `test_dirty_path_refused`,
`test_path_outside_scripts_refused`, `test_new_file_must_not_exist`, `test_failed_build_gets_fix_prompt`,
`test_two_failures_restore_and_record`, `test_unity_running_stops`.

## Task 6: The loop and the CLI

**Produces:** `builder.run(max_features: int = 1, dry: bool = False, only: str | None = None) -> dict`:
scan → requirements → gaps → scores → pick the top → write → build → rescan. Stops when no gap has a score, when
`max_features` are done, or on a stop. Each pass writes `ranking.json` (every gap, its score and breakdown) into the
run folder.

```
python builder.py --dry            the ranking and the pick, nothing written (for David's approval)
python builder.py --only <req id>  build exactly the requirement David approved
python builder.py --max N          up to N features, rescanning after each
```

Tests: `test_loop_rescans_after_each_write_and_stops_when_met` (a temp codebase with two gaps and a fake model that
writes the files that close them: two passes, then "every requirement met"), `test_dry_writes_nothing`,
`test_max_features_stops_loop`.

Check: `python -m pytest test_codebase.py test_builder.py -q` passes, and the older crew tests still pass.

## Task 7: The run on the game

1. `python builder.py --dry`. Show David the top of `ranking.json` with each breakdown. **He approves the pick.**
2. `python builder.py --only <id>`. The agent writes, builds, and rescans to confirm the gap closed.
3. Read the diff. If the feature names characters, check the names against the tile art (`player2Prefab` wears
   `player3`'s art). Anything wrong is fixed by hand and listed for the README.
4. Build all four versions per `docs/build.md` (`HeadlessBuild.Build`, `HeadlessBuild.BuildItch`); reopen Unity.
   The browser build is the browser session's, and its next `BuildWeb` carries the feature.
5. **David plays the full copy in `C:\bbust\full\`.** His word decides whether it's accepted.

My expectation, not a promise: the agent skips the slots past `player20` (`GameManager.cs` has the browser session's
uncommitted changes) and picks first names on Character Select (GDD 21.1: a ruling dated 2026-11-01, visible today
with the original ten, 31 characters waiting, one clean file plus a new one). The score decides, and the README
quotes it.

## Task 8: The hand-in

- `C:\gdd\assignment5\README.md`: what the agent built; why it picked it (the breakdown from `ranking.json`, and what
  it skipped and why); what was changed by hand before it went in (the diff between the agent's output and what David
  accepted); how to run it.
- `C:\gdd\assignment5\code\`: copies of `builder.py`, `codebase.py`, `gdd.py`, `common.py` and the tests.
  `official_run\`: the run folder (`run.json`, `prompts.jsonl`, `ranking.json`, `dropped.json`).
- BBUST `SESSION_LOG.md` handoff and the `HOURS.md` row.
- Commits and pushes (`C:\gdd`, `C:\cluster`, BBUST) only at David's word.
