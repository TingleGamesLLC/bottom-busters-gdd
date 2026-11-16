"""The Builder (Assignment #5), tested with a stand-in model, a small fake game in a temp git repo and a fake build: no
cluster time, no Claude, nothing near the real game. One test reads the real GDD's headings.

usage: python -m pytest test_builder.py -q
"""
import json
import subprocess
import tempfile
from pathlib import Path

import pytest

import builder
import codebase
import common
import gdd

MINI_GDD = """# Mini game

## 0. What changed

- Everything changed. This section is never read for features.

## 1. Overview

- The main menu has a big PLAY button that starts a run.

## 5. Game modes

| Mode | Summary |
|---|---|
| **Endless** (planned) | Levels keep coming with no end until the lives are gone. |
| **Old Mode** | Retired: the old mode was taken out of the game. |

## 7. Characters

- Every character will show its first name under its tile on Character Select (planned, Studio Director, 2026-11-01).

## 20. Risks and open questions

- Nobody knows. Never read.
"""

MENU = """using UnityEngine;

public class MainMenu : MonoBehaviour
{
    public void BuildPlayButton()
    {
        var label = "PLAY";
    }
}
"""
SELECT = """using UnityEngine;

public class CharacterSelect : MonoBehaviour
{
    private void BuildTiles()
    {
        int tiles = 10;
    }
}
"""


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def game(tmp_path, monkeypatch):
    repo = tmp_path / "game"
    (repo / "Assets/Scripts/UI").mkdir(parents=True)
    (repo / "Assets/Scripts/UI/MainMenu.cs").write_text(MENU, encoding="utf-8")
    (repo / "Assets/Scripts/UI/CharacterSelect.cs").write_text(SELECT, encoding="utf-8")
    git(repo, "init")
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "start")
    doc = tmp_path / "GDD.md"
    doc.write_text(MINI_GDD, encoding="utf-8")
    subs = tmp_path / "submissions"
    (subs / "characters" / "player21_t1").mkdir(parents=True)
    work = tmp_path / "work"
    monkeypatch.setattr(common, "RUNS", tmp_path / "runs")
    return {"repo": repo, "gdd": doc, "subs": subs, "work": work, "tmp": tmp_path}


FEATURES = {
    "1": [{"feature": "PLAY button on the main menu", "quote": "The main menu has a big PLAY button", "status": "built",
           "visible": True, "content": "none", "evidence": ["MainMenu", "BuildPlayButton", '"PLAY"']}],
    "5": [{"feature": "Endless mode", "quote": "Levels keep coming with no end until the lives are gone.", "status": "planned",
           "visible": True, "content": "none", "evidence": ["EndlessMode", "isEndless"]},
          {"feature": "Old mode", "quote": "Retired: the old mode was taken out of the game.", "status": "retired",
           "visible": True, "content": "none", "evidence": ["OldMode"]},
          {"feature": "Made up", "quote": "This sentence is not in the section at all.", "status": "planned",
           "visible": True, "content": "none", "evidence": ["Nothing"]}],
    "7": [{"feature": "First names on Character Select",
           "quote": "Every character will show its first name under its tile on Character Select", "status": "built",
           "visible": True, "content": "characters", "evidence": ["CharacterNames", "FirstName"]}],
}


class FakeModel:
    """Answers the two reading prompts like the cluster would. A feature counts as built once a marker line for it is in
    the code, and its code quote is that line."""
    MARKERS = {"Endless mode": "public static bool isEndless = true;", "First names on Character Select":
               'public static string FirstName(int skin) => "Larry";'}
    TARGETS = {"Endless mode": ([], "Assets/Scripts/Core/EndlessMode.cs", 200),
               "First names on Character Select": (["Assets/Scripts/UI/CharacterSelect.cs"],
                                                   "Assets/Scripts/UI/CharacterNames.cs", 40)}

    def __init__(self, repo, features=FEATURES):
        self.repo, self.features, self.calls = repo, features, []

    def __call__(self, agent, messages, required, **kw):
        system, user = messages[0]["content"], messages[-1]["content"]
        self.calls.append(system[:20])
        if system == builder.REQ_SYSTEM:
            number = user.split("GDD Section ", 1)[1].split(",", 1)[0]
            return {"features": self.features.get(number, [])}
        feature = user.split("Feature: ", 1)[1].split("\n", 1)[0]
        marker = self.MARKERS.get(feature)
        code = "\n".join(p.read_text(encoding="utf-8") for p in (self.repo / "Assets/Scripts").rglob("*.cs"))
        if marker and marker in code:
            return {"built": True, "code_quote": marker, "targets": [], "new_file": "", "lines": 0, "why": "it's there"}
        targets, new, lines = self.TARGETS.get(feature, ([], "", 0))
        return {"built": False, "code_quote": "", "targets": targets, "new_file": new, "lines": lines, "why": "not there"}


def writer_for(repo, log):
    """A writer that closes whichever gap it is asked about by creating the marker class."""
    def write(messages):
        log.append(messages)
        user = messages[1]["content"]
        if "First names" in user:
            return ("=== NEW FILE: Assets/Scripts/UI/CharacterNames.cs\npublic static class CharacterNames\n{\n"
                    '    public static string FirstName(int skin) => "Larry";\n}\n'
                    "=== EDIT: Assets/Scripts/UI/CharacterSelect.cs\n<<<<<<< FIND\n        int tiles = 10;\n=======\n"
                    "        int tiles = 10;\n        CharacterNames.ToString();\n>>>>>>> REPLACE\n=== END\n")
        return ("=== NEW FILE: Assets/Scripts/Core/EndlessMode.cs\npublic static class EndlessMode\n{\n"
                "    public static bool isEndless = true;\n}\n=== END\n")
    return write


def ok_build(repo, log):
    return True, []


def run(game, model, writers, **kw):
    return builder.run(repo=game["repo"], gdd_path=game["gdd"], ask=model, writers=writers, build=kw.pop("build", ok_build),
                       submissions=game["subs"], work=game["work"], workers=1, **kw)


def mini_reqs(game, model):
    secs = gdd.sections(game["gdd"])
    return builder.requirements(secs, ["MainMenu"], model, game["work"] / "req.json", workers=1)


# --- requirements -------------------------------------------------------------------------------------------------

def test_sections_split_21_parts():
    numbers = [s.number for s in gdd.sections()]
    assert {"21.1", "21.2", "21.3", "21.4", "16", "5"} <= set(numbers)


def test_invented_quote_dropped(game):
    reqs, dropped = mini_reqs(game, FakeModel(game["repo"]))
    assert "Made up" not in [r.feature for r in reqs]
    assert any(d["feature"] == "Made up" and "word for word" in d["why"] for d in dropped)


def test_table_row_quote_kept_and_paragraph_found(game):
    reqs, _ = mini_reqs(game, FakeModel(game["repo"]))
    endless = next(r for r in reqs if r.feature == "Endless mode")
    assert endless.paragraph.startswith("| **Endless** (planned)")


def test_sections_0_and_20_skipped(game):
    model = FakeModel(game["repo"])
    mini_reqs(game, model)
    asked = [m for m in model.calls]
    assert len(asked) == 3   # sections 1, 5 and 7


def test_cache_reused_when_gdd_unchanged(game):
    model = FakeModel(game["repo"])
    first, _ = mini_reqs(game, model)
    again, _ = mini_reqs(game, model)
    assert len(model.calls) == 3 and [r.id for r in first] == [r.id for r in again]


# --- the gap pass -------------------------------------------------------------------------------------------------

def test_built_with_evidence_found_needs_no_second_look(game):
    model = FakeModel(game["repo"])
    reqs, _ = mini_reqs(game, model)
    gaps, present = builder.find_gaps(reqs, codebase.scan(game["repo"]), model, None, workers=1)
    assert any(p["feature"] == "PLAY button on the main menu" and "evidence" in p["how"] for p in present)
    assert len(model.calls) == 3 + 2   # second looks only for Endless and First names


def test_retired_and_on_hold_never_gaps(game):
    reqs, _ = mini_reqs(game, FakeModel(game["repo"]))
    gaps, _ = builder.find_gaps(reqs, codebase.scan(game["repo"]), FakeModel(game["repo"]), None, workers=1)
    assert "Old mode" not in [g.req.feature for g in gaps]
    assert sorted(g.req.feature for g in gaps) == ["Endless mode", "First names on Character Select"]


def test_built_without_real_code_quote_is_gap(game):
    reqs, _ = mini_reqs(game, FakeModel(game["repo"]))
    liar = lambda *a, **k: {"built": True, "code_quote": "public static class Nowhere {}", "targets": [], "new_file": "",
                            "lines": 0, "why": "trust me"}
    gaps, _ = builder.find_gaps(reqs, codebase.scan(game["repo"]), liar, None, workers=1)
    assert any(g.req.feature == "Endless mode" and "isn't in the code" in g.why for g in gaps)


def test_built_with_real_quote_is_not_gap(game):
    (game["repo"] / "Assets/Scripts/UI/CharacterNames.cs").write_text(
        'public static class CharacterNames\n{\n    public static string FirstName(int skin) => "Larry";\n}\n')
    reqs, _ = mini_reqs(game, FakeModel(game["repo"]))
    gaps, present = builder.find_gaps(reqs, codebase.scan(game["repo"]), FakeModel(game["repo"]), None, workers=1)
    assert "First names on Character Select" not in [g.req.feature for g in gaps]
    assert any(p["feature"].startswith("First names") and "second look quoted" in p["how"] for p in present)


def test_targets_outside_scripts_dropped(game):
    reqs, _ = mini_reqs(game, FakeModel(game["repo"]))
    odd = lambda *a, **k: {"built": False, "code_quote": "", "lines": 10, "why": "x",
                           "targets": ["Assets/Scripts/UI/MainMenu.cs", "Assets/Editor/HeadlessBuild.cs", "../evil.cs"],
                           "new_file": "Assets/Resources/Thing.cs"}
    gaps, _ = builder.find_gaps(reqs, codebase.scan(game["repo"]), odd, None, workers=1)
    assert all(g.targets == ["Assets/Scripts/UI/MainMenu.cs"] and g.new_file == "" for g in gaps)


def test_second_look_cached(game):
    model = FakeModel(game["repo"])
    reqs, _ = mini_reqs(game, model)
    cache = game["work"] / "looks.json"
    index = codebase.scan(game["repo"])
    builder.find_gaps(reqs, index, model, cache, workers=1)
    builder.find_gaps(reqs, index, model, cache, workers=1)
    assert len(model.calls) == 3 + 2


# --- priority_score() ---------------------------------------------------------------------------------------------

def req(**kw):
    base = dict(id="7-1", section="7", feature="f", quote="q q q q q", paragraph="", status="planned", visible=False,
                content="none", evidence=["X"])
    base.update(kw)
    return builder.Requirement(**base)


def gap(r=None, targets=("Assets/Scripts/UI/A.cs",), new="", lines=50):
    return builder.Gap(r or req(), list(targets), new, [], "", lines)


def test_dirty_target_skipped_with_reason():
    score, b = builder.priority_score(gap(), {"Assets/Scripts/UI/A.cs"}, {}, set())
    assert score is None and "uncommitted" in b["skipped"]


def test_failed_requirement_skipped():
    score, b = builder.priority_score(gap(), set(), {}, {"7-1"})
    assert score is None and "stopped twice" in b["skipped"]


def test_waiting_submissions_raise_score():
    named = "- More playable characters (planned, 2026-10-21)."
    low, _ = builder.priority_score(gap(req(content="characters", paragraph=named)), set(), {"characters": 0}, set())
    high, b = builder.priority_score(gap(req(content="characters", paragraph=named)), set(), {"characters": 31}, set())
    unnamed, _ = builder.priority_score(gap(req(content="characters", paragraph="- Endless (planned).")), set(),
                                        {"characters": 31}, set())
    assert high - low == 3 and b["unblocks"] == "31 characters waiting" and unnamed == low


def test_ruling_detected_from_paragraph():
    with_ruling = req(paragraph="- 80 new characters, for 90 in all (Studio Director, 2026-11-07).")
    dated_only = req(paragraph="- Arms flap on every fart (2026-10-31).")
    a, b = builder.priority_score(gap(with_ruling), set(), {}, set())
    c, _ = builder.priority_score(gap(dated_only), set(), {}, set())
    assert a - c == 2 and b["ruling"].startswith("Studio Director")


def test_small_change_outranks_large():
    small, _ = builder.priority_score(gap(lines=60), set(), {}, set())
    medium, _ = builder.priority_score(gap(targets=("a", "b"), lines=200), set(), {}, set())
    large, _ = builder.priority_score(gap(targets=("a", "b"), lines=900), set(), {}, set())
    unknown, _ = builder.priority_score(gap(lines=0), set(), {}, set())
    assert (small, medium, large, unknown) == (2, 1, 0, 0)


def test_ties_keep_gdd_order():
    first, second = gap(req(id="5-1")), gap(req(id="7-1"))
    ranked = builder.rank([first, second], set(), {}, set())
    assert [g.req.id for _, _, g in ranked] == ["5-1", "7-1"]
    skipped_first = builder.rank([first, second], {"Assets/Scripts/UI/A.cs"}, {}, set())
    assert all(s is None for s, _, _ in skipped_first)


# --- the write step -----------------------------------------------------------------------------------------------

def test_parse_change_blocks():
    c = builder.parse_change("<think>hm</think>Sure.\n=== NEW FILE: Assets/Scripts/UI/N.cs\n```csharp\nclass N {}\n```\n"
                             "=== EDIT: Assets/Scripts/UI/M.cs\n<<<<<<< FIND\na\n=======\nb\n>>>>>>> REPLACE\n"
                             "<<<<<<< FIND\nc\n=======\nd\n>>>>>>> REPLACE\n=== END\n")
    assert c.new_files == {"Assets/Scripts/UI/N.cs": "class N {}\n"}
    assert [(e.find, e.replace) for e in c.edits] == [("a\n", "b\n"), ("c\n", "d\n")]
    with pytest.raises(common.MalformedOutput):
        builder.parse_change("I can't do that.")


def edit(path, find, replace):
    return builder.Change({}, [builder.Edit(path, find, replace)])


def test_find_must_occur_once(game):
    p = game["repo"] / "Assets/Scripts/UI/MainMenu.cs"
    with pytest.raises(builder.Refused):
        builder.apply(edit("Assets/Scripts/UI/MainMenu.cs", "nothing like this\n", "x\n"), game["repo"], set())
    with pytest.raises(builder.Refused):
        builder.apply(edit("Assets/Scripts/UI/MainMenu.cs", "{", "x"), game["repo"], set())   # twice
    assert p.read_text(encoding="utf-8") == MENU


def test_indentation_tolerant_find(game):
    backup = builder.apply(edit("Assets/Scripts/UI/MainMenu.cs", 'var label = "PLAY";\n', '        var label = "GO";\n'),
                           game["repo"], set())
    assert '        var label = "GO";\n' in (game["repo"] / "Assets/Scripts/UI/MainMenu.cs").read_text(encoding="utf-8")
    builder.restore(backup, game["repo"])
    assert (game["repo"] / "Assets/Scripts/UI/MainMenu.cs").read_text(encoding="utf-8") == MENU


def test_crlf_file_edit(game):
    p = game["repo"] / "Assets/Scripts/UI/MainMenu.cs"
    p.write_bytes(MENU.replace("\n", "\r\n").encode("utf-8"))
    builder.apply(edit("Assets/Scripts/UI/MainMenu.cs", '        var label = "PLAY";\n', '        var label = "GO";\n'),
                  game["repo"], set())
    assert b'var label = "GO";\r\n' in p.read_bytes() and b"\n\n" not in p.read_bytes().replace(b"\r\n", b"")


def test_dirty_path_refused(game):
    with pytest.raises(builder.Refused, match="uncommitted"):
        builder.apply(edit("Assets/Scripts/UI/MainMenu.cs", 'var label = "PLAY";', "x"), game["repo"],
                      {"Assets/Scripts/UI/MainMenu.cs"})
    # its own file from earlier in the run is fine
    builder.apply(edit("Assets/Scripts/UI/MainMenu.cs", 'var label = "PLAY";', 'var label = "GO";'), game["repo"],
                  {"Assets/Scripts/UI/MainMenu.cs"}, mine=["Assets/Scripts/UI/MainMenu.cs"])


def test_path_outside_scripts_refused(game):
    for path in ("Assets/Editor/X.cs", "Assets/Scripts/../X.cs", "Assets/Scripts/UI/X.txt"):
        with pytest.raises(builder.Refused):
            builder.apply(builder.Change({path: "class X {}"}, []), game["repo"], set())
    assert not (game["repo"] / "Assets/Editor").exists()


def test_new_file_must_not_exist(game):
    with pytest.raises(builder.Refused, match="already exists"):
        builder.apply(builder.Change({"Assets/Scripts/UI/MainMenu.cs": "class X {}"}, []), game["repo"], set())


def test_nothing_written_when_any_part_refused(game):
    change = builder.Change({"Assets/Scripts/UI/Good.cs": "class Good {}"},
                            [builder.Edit("Assets/Scripts/UI/MainMenu.cs", "not there", "x")])
    with pytest.raises(builder.Refused):
        builder.apply(change, game["repo"], set())
    assert not (game["repo"] / "Assets/Scripts/UI/Good.cs").exists()


def first_names_gap(game):
    model = FakeModel(game["repo"])
    reqs, _ = mini_reqs(game, model)
    gaps, _ = builder.find_gaps(reqs, codebase.scan(game["repo"]), model, None, workers=1)
    return next(g for g in gaps if g.req.feature.startswith("First names"))


def test_failed_build_gets_fix_prompt(game):
    seen = []
    builds = iter([(False, ["Assets/Scripts/UI/CharacterNames.cs(3,1): error CS1002: ; expected"]), (True, [])])
    name, backup, _ = builder.build_feature(first_names_gap(game), codebase.scan(game["repo"]), game["repo"], set(), [],
                                            game["tmp"], [("cluster", writer_for(game["repo"], seen))],
                                            lambda repo, log: next(builds), lambda t: None)
    assert name == "cluster" and len(seen) == 2
    assert "error CS1002" in seen[1][-1]["content"] and seen[1][-2]["role"] == "assistant"
    assert (game["repo"] / "Assets/Scripts/UI/CharacterNames.cs").exists()


def test_two_failures_hand_over_to_next_writer(game):
    cluster, claude = [], []
    builds = iter([(False, ["error CS0103: x"]), (False, ["error CS0103: x"]), (True, [])])
    name, _, _ = builder.build_feature(first_names_gap(game), codebase.scan(game["repo"]), game["repo"], set(), [],
                                       game["tmp"], [("qwen3:30b-instruct", writer_for(game["repo"], cluster)),
                                                     ("claude-code", writer_for(game["repo"], claude))],
                                       lambda repo, log: next(builds), lambda t: None)
    assert name == "claude-code" and len(cluster) == 2 and len(claude) == 1
    assert len(claude[0]) == 2   # Claude starts from the clean prompt, not the cluster's failures


def test_all_writers_fail_restore_and_record(game):
    model = FakeModel(game["repo"])
    fail = lambda repo, log: (False, ["error CS0246: The type or namespace name 'Nope' could not be found"])
    state = run(game, model, [("cluster", writer_for(game["repo"], [])), ("claude", writer_for(game["repo"], []))],
                build=fail, only="7-1")
    assert state["status"].startswith("stopped:") and "put back" in state["status"]
    assert (game["repo"] / "Assets/Scripts/UI/CharacterSelect.cs").read_text(encoding="utf-8") == SELECT
    assert not (game["repo"] / "Assets/Scripts/UI/CharacterNames.cs").exists()
    assert json.loads((game["work"] / "builder_failed.json").read_text()) == ["7-1"]


def test_unity_running_stops(game, monkeypatch):
    monkeypatch.setattr(builder, "unity_running", lambda repo: True)
    with pytest.raises(common.CrewStop, match="Unity has"):
        builder.build_check(game["repo"], game["tmp"] / "b.log")


# --- the loop -----------------------------------------------------------------------------------------------------

def test_loop_rescans_after_each_write_and_stops_when_met(game):
    model, seen = FakeModel(game["repo"]), []
    state = run(game, model, [("cluster", writer_for(game["repo"], seen))], max_features=5)
    built = state["builder"]["built"]
    assert [b["id"] for b in built] == ["7-1", "5-1"]          # first names first: 31-style waiting work + ruling
    assert all(b["closed"] for b in built)                      # each one confirmed closed by the rescan
    assert [p["gaps"] for p in state["builder"]["passes"]] == [2, 1, 0]
    assert state["status"] == "every requirement met"


def test_dry_writes_nothing(game):
    before = codebase.scan(game["repo"]).files
    state = run(game, FakeModel(game["repo"]), [("cluster", writer_for(game["repo"], []))], dry=True)
    assert state["status"] == "waiting on David" and state["builder"]["pick"]["id"] == "7-1"
    assert codebase.scan(game["repo"]).files == before and codebase.dirty(game["repo"]) == set()


def test_max_features_stops_loop(game):
    state = run(game, FakeModel(game["repo"]), [("cluster", writer_for(game["repo"], []))], max_features=1)
    assert [b["id"] for b in state["builder"]["built"]] == ["7-1"]
    assert state["status"] == "built 1 feature(s), its limit for this run"
    assert state["builder"]["built"][0]["closed"] is True


def test_resume_only_builds_approved(game):
    dry = run(game, FakeModel(game["repo"]), [("cluster", writer_for(game["repo"], []))], dry=True)
    state = run(game, FakeModel(game["repo"]), [("cluster", writer_for(game["repo"], []))], run_id=dry["id"], only="5-1")
    assert state["id"] == dry["id"] and [b["id"] for b in state["builder"]["built"]] == ["5-1"]
    assert len(state["builder"]["passes"]) == 3   # the dry pass, the build pass, the rescan
    runs = common.RUNS / dry["id"]
    assert (runs / "change_1" / "change.diff").read_text().count("EndlessMode") >= 1


def test_only_refuses_a_skipped_gap(game):
    (game["repo"] / "Assets/Scripts/UI/CharacterSelect.cs").write_text(SELECT + "// someone else's edit\n")
    state = run(game, FakeModel(game["repo"]), [("cluster", writer_for(game["repo"], []))], only="7-1")
    assert "uncommitted" in state["status"] and state["builder"]["built"] == []


def test_declaration_is_not_proof(game):
    """A class declaration line is in the code, but it proves nothing: the gap stands."""
    (game["repo"] / "Assets/Scripts/UI/CharacterNames.cs").write_text("public static class CharacterNames\n{\n}\n")
    reqs, _ = mini_reqs(game, FakeModel(game["repo"]))
    decl = lambda *a, **k: {"built": True, "code_quote": "public static class CharacterNames", "targets": [], "new_file": "",
                            "lines": 0, "why": "the class is there"}
    gaps, _ = builder.find_gaps(reqs, codebase.scan(game["repo"]), decl, None, workers=1)
    assert "First names on Character Select" in [g.req.feature for g in gaps]


def test_built_in_the_gdd_is_never_a_gap(game):
    """The GDD calls it built and only class names were found: it's listed as unconfirmed, with no second look, and it
    is never something to build (a second copy of a working feature would be the worst outcome)."""
    feats = {"1": [{"feature": "PLAY button on the main menu", "quote": "The main menu has a big PLAY button",
                    "status": "planned", "visible": True, "content": "none", "evidence": ["MainMenu", "CharacterSelect"]}]}
    model = FakeModel(game["repo"], feats)
    reqs, _ = builder.requirements(gdd.sections(game["gdd"]), [], model, None, workers=1)
    assert reqs[0].status == "built"   # the GDD's words, not the model's "planned"
    gaps, present = builder.find_gaps(reqs, codebase.scan(game["repo"]), model, None, workers=1)
    assert gaps == [] and present[0]["confirmed"] is False and len(model.calls) == 3


def test_status_comes_from_the_gdd_words():
    assert builder.status_of("| **Endless** (planned) | Levels keep coming. |") == "planned"
    assert builder.status_of("**Full game:**\n- The Endless mode (Section 5).") == "planned"
    assert builder.status_of("**Planned later:**\n- Achievements (a list of about 60 has been drafted).") == "planned"
    assert builder.status_of("- The Custom Game screen ships as a teaser today.") == "planned"
    assert builder.status_of("- Every character rolls one of four cheek sets each life (2026-10-18).") == "built"
    assert builder.status_of("- The developer level-skip buttons were taken out of every build.") == "retired"


def test_paragraph_carries_its_label():
    text = "**Full game:**\n- 200 levels.\n- The Endless mode (Section 5).\n\n**Planned later:**\n- Achievements."
    assert builder.paragraph_of(text, "The Endless mode (Section 5).") == "**Full game:**\n- The Endless mode (Section 5)."
    assert builder.paragraph_of(text, "Achievements.").startswith("**Planned later:**")


def test_unity_check_is_per_project():
    r"""Today's real case: the browser session's BuildWeb has C:\bbust\BBUST open; another folder isn't blocked by it."""
    assert builder.unity_running(r"C:\no\such\project") is False


def test_stop_mid_build_puts_the_change_back(game):
    """Unity opening (or anything else stopping the run) during the build never leaves the change in the game."""
    def unity_opened(repo, log):
        raise common.CrewStop("Unity has the project open")
    with pytest.raises(common.CrewStop):
        builder.build_feature(first_names_gap(game), codebase.scan(game["repo"]), game["repo"], set(), [], game["tmp"],
                              [("cluster", writer_for(game["repo"], []))], unity_opened, lambda t: None)
    assert (game["repo"] / "Assets/Scripts/UI/CharacterSelect.cs").read_text(encoding="utf-8") == SELECT
    assert not (game["repo"] / "Assets/Scripts/UI/CharacterNames.cs").exists()


def test_line_numbers_and_file_tags_are_taken_off():
    """The practice run's real failure: qwen copied '1: ' line numbers into FIND and wrapped the new file in <file> tags."""
    c = builder.parse_change("=== NEW FILE: Assets/Scripts/UI/N.cs\n<file>\nusing UnityEngine;\nclass N {}\n</file>\n"
                             "=== EDIT: Assets/Scripts/UI/M.cs\n<<<<<<< FIND\n1: using System;\n2: using UnityEngine;\n=======\n"
                             "1: using System;\n2: using UnityEngine;\n3: using TMPro;\n>>>>>>> REPLACE\n=== END\n")
    assert c.new_files["Assets/Scripts/UI/N.cs"] == "using UnityEngine;\nclass N {}\n"
    assert c.edits[0].find == "using System;\nusing UnityEngine;\n"
    assert c.edits[0].replace == "using System;\nusing UnityEngine;\nusing TMPro;\n"


def test_code_that_starts_with_a_number_is_left_alone():
    assert builder.unnumber(["1: a", "x = 2;"]) == ["1: a", "x = 2;"]


def test_write_prompt_shows_code_without_line_numbers(game):
    text = builder.write_prompt(first_names_gap(game), codebase.scan(game["repo"]))
    assert "        int tiles = 10;" in text and "6:" not in text


def test_only_builds_an_unconfirmed_requirement_david_approved(game):
    """The GDD calls it built, the search can't confirm it, David checks and approves: the agent builds it."""
    feats = dict(FEATURES)
    feats["7"] = [{"feature": "First names on Character Select",
                   "quote": "Every character will show its first name under its tile on Character Select",
                   "status": "built", "visible": True, "content": "characters", "evidence": ["CharacterNames", "FirstName"]}]
    doc = game["gdd"]
    doc.write_text(doc.read_text(encoding="utf-8").replace("(planned, Studio Director", "(Studio Director"), encoding="utf-8")
    state = run(game, FakeModel(game["repo"], feats), [("cluster", writer_for(game["repo"], []))], only="7-1")
    assert [b["id"] for b in state["builder"]["built"]] == ["7-1"]
    assert state["builder"]["pick"]["approved_by_david"].startswith("listed as unconfirmed")
    assert (game["repo"] / "Assets/Scripts/UI/CharacterNames.cs").exists()


def test_approved_feature_is_planned_around_busy_files(game):
    """For a feature David approved, the second look hears which files are off limits (another session's work)."""
    (game["repo"] / "Assets/Scripts/UI/MainMenu.cs").write_text(MENU + "// the browser session's edit\n")
    seen = []
    def look(agent, messages, required, **kw):
        seen.append(messages[-1]["content"])
        return {"built": False, "code_quote": "", "targets": ["Assets/Scripts/UI/CharacterSelect.cs"],
                "new_file": "Assets/Scripts/UI/CharacterNames.cs", "lines": 40, "why": "not there"}
    r = req(id="7-1", feature="First names", quote="first names", status="built")
    a = builder.second_look(codebase.scan(game["repo"]), r, [], look,
                            avoid=codebase.dirty(game["repo"]))
    assert "can't be changed now: Assets/Scripts/UI/MainMenu.cs" in seen[0] and a["targets"]


def test_file_named_by_the_feature_is_shown_first(game):
    """The class the feature names is shown to the second look even when other files match more search words."""
    for k in range(4):   # four files that each match more evidence words than CharacterSelect.cs
        (game["repo"] / f"Assets/Scripts/UI/Busy{k}.cs").write_text(
            f"public class Busy{k} {{ void A() {{ var c = CharacterSelect.x; var s = Strings.y; var b = CharacterBase.z; }} }}\n")
    r = req(feature="Character name display", quote="just a list of characters with first names",
            evidence=["CharacterSelect", "Strings", "CharacterBase"])
    index = codebase.scan(game["repo"])
    text = builder.evidence_text(index, r, codebase.search(index, r.evidence, limit=12))
    assert text.index("--- Assets/Scripts/UI/CharacterSelect.cs") < text.index("--- Assets/Scripts/UI/Busy0.cs")


def test_approved_feature_targets_its_own_class_first_and_overrides_a_past_stop(game):
    """Official run 20261115-161537: the second look aimed the names at the wrong file. For a feature David approved, the
    file that declares the feature's own class goes to the writer first, the GDD section goes with it, and his approval
    overrides the 'failed before' mark."""
    feats = dict(FEATURES)
    feats["7"] = [{"feature": "First names on Character Select",
                   "quote": "Every character will show its first name under its tile on Character Select",
                   "status": "built", "visible": True, "content": "characters", "evidence": ["CharacterSelect", "FirstName"]}]
    doc = game["gdd"]
    doc.write_text(doc.read_text(encoding="utf-8").replace("(planned, Studio Director", "(Studio Director"), encoding="utf-8")
    game["work"].mkdir(parents=True, exist_ok=True)
    (game["work"] / "builder_failed.json").write_text('["7-1"]')
    class WrongFile(FakeModel):
        def __call__(self, agent, messages, required, **kw):
            a = super().__call__(agent, messages, required, **kw)
            if "built" in a and not a["built"]:
                a.update(targets=["Assets/Scripts/UI/MainMenu.cs"], new_file="")
            return a
    seen = []
    state = run(game, WrongFile(game["repo"], feats), [("cluster", writer_for(game["repo"], seen))], only="7-1")
    prompt = seen[0][1]["content"]
    assert prompt.index("--- Assets/Scripts/UI/CharacterSelect.cs") < prompt.index("--- Assets/Scripts/UI/MainMenu.cs")
    assert "The GDD's whole Section 7" in prompt
    assert [b["id"] for b in state["builder"]["built"]] == ["7-1"]
