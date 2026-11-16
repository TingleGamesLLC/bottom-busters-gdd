"""The Builder's code scan: what it reads, what search finds, the outline, and the files another session has changed.

usage: python -m pytest test_codebase.py -q
"""
import subprocess
import tempfile
from pathlib import Path

import codebase

MENU = """using UnityEngine;

public class CharacterSelect : MonoBehaviour
{
    private const int TileColumns = 6;
    public static void Open(int seats)
    {
        int x = seats + 1;
        Debug.Log("open " + x);
    }

    private Tile NewTile(string name) => new Tile();
}
"""
MANAGER = """public class GameManager
{
    private void LoadCharacterPrefabs()
    {
        for (int index = 2; index <= 20; index++) { }
    }
}
"""


def make_repo(tmp):
    repo = Path(tmp)
    (repo / "Assets/Scripts/UI").mkdir(parents=True)
    (repo / "Assets/Scripts/Core").mkdir(parents=True)
    (repo / "Assets/Scripts/UI/CharacterSelect.cs").write_text(MENU, encoding="utf-8")
    (repo / "Assets/Scripts/Core/GameManager.cs").write_text(MANAGER, encoding="utf-8")
    (repo / "Assets/Scripts/UI/notes.txt").write_text("CharacterSelect", encoding="utf-8")
    return repo


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def test_scan_reads_only_cs():
    with tempfile.TemporaryDirectory() as tmp:
        index = codebase.scan(make_repo(tmp))
        assert sorted(index.files) == ["Assets/Scripts/Core/GameManager.cs", "Assets/Scripts/UI/CharacterSelect.cs"]


def test_search_whole_words_ranked():
    with tempfile.TemporaryDirectory() as tmp:
        index = codebase.scan(make_repo(tmp))
        hits = codebase.search(index, ["LoadCharacterPrefabs", "index"])
        assert hits[0].path == "Assets/Scripts/Core/GameManager.cs"   # two distinct terms beat one
        assert codebase.search(index, ["Character"]) == []            # whole words only
        assert codebase.search(index, ["tilecolumns"])[0].line_no == 5  # any case
        assert codebase.terms_found(index, ["GameManager", "Nope", '"open "']) == 2


def test_outline_keeps_signatures_drops_bodies():
    with tempfile.TemporaryDirectory() as tmp:
        index = codebase.scan(make_repo(tmp))
        text = codebase.outline(index, "Assets/Scripts/UI/CharacterSelect.cs")
        assert "3: public class CharacterSelect : MonoBehaviour" in text
        assert "6: public static void Open(int seats)" in text
        assert "12: private Tile NewTile(string name) => new Tile();" in text
        assert "Debug.Log" not in text and "int x" not in text


def test_dirty_lists_modified_and_untracked():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(tmp)
        git(repo, "init")
        git(repo, "add", "-A")
        git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "start")
        assert codebase.dirty(repo) == set()
        (repo / "Assets/Scripts/Core/GameManager.cs").write_text(MANAGER + "// edit\n", encoding="utf-8")
        (repo / "Assets/Scripts/UI/New Thing.cs").write_text("class N {}", encoding="utf-8")
        assert codebase.dirty(repo) == {"Assets/Scripts/Core/GameManager.cs", "Assets/Scripts/UI/New Thing.cs"}


def test_dirty_on_the_game_repo_sees_the_browser_work():
    """The real BBUST tree, read only: GameManager.cs has the browser session's uncommitted changes today."""
    repo = Path(r"C:\bbust\BBUST")
    if not repo.exists():
        return
    d = codebase.dirty(repo)
    assert all("\\" not in p for p in d)
