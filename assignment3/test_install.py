"""The install tool against a temp copy of the parts of the project it touches. Never writes to the real project.

usage: python test_install.py
"""
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

import bridge
import common
import install_character as ic
import parts
import test_bridge


def tree_state(root):
    state = {}
    for where, _, names in os.walk(root):
        for n in names:
            path = os.path.join(where, n)
            state[path] = Path(path).read_bytes()
    return state


def changed_lines(a, b):
    return [(x, y) for x, y in zip(a.splitlines(), b.splitlines()) if x != y]


def refused(folder):
    try:
        ic.install(folder)
    except SystemExit as e:
        return str(e)
    raise AssertionError(f"{folder} should have been refused")


def main():
    real_assets, real_flail = ic.ASSETS, ic.FLAIL_PY
    real_state = {p: Path(p).stat().st_mtime_ns for p in (real_flail, real_assets / "Resources" / "Wearables" / "fit.json")}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        common.SUBMISSIONS = tmp / "submissions"
        (common.SUBMISSIONS / "characters").mkdir(parents=True)

        assets = tmp / "Assets"
        for rel in ("Resources/Prefabs/playerPrefab.prefab", "Resources/Prefabs/playerPrefab.prefab.meta", "Resources/Prefabs/aiPrefab.prefab",
                    "Resources/Prefabs/aiPrefab.prefab.meta", "Resources/Wearables/fit.json", "Resources/Wearables/catalog.json", "Sprites/Characters/player.png"):
            (assets / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(real_assets / rel, assets / rel)
        ic.ASSETS, ic.PREFABS = assets, assets / "Resources" / "Prefabs"
        ic.FIT, ic.NAMES = assets / "Resources" / "Wearables" / "fit.json", assets / "Resources" / "CharacterNames.json"
        ic.TEMPLATE_SPRITE = assets / "Sprites" / "Characters" / "player.png"
        ic.FLAIL_PY = tmp / "flail.py"
        shutil.copyfile(real_flail, ic.FLAIL_PY)

        folder = test_bridge.good_character(tmp / "work", slot=11, first_name="Darnell")
        m = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        m["face"] = {"eyes": [[505, 215], [575, 213]], "mouth": [540, 275]}
        (folder / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
        before = tree_state(tmp / "Assets")
        flail_before = ic.FLAIL_PY.read_text(encoding="utf-8")

        # Undecided or rejected: nothing moves.
        assert "isn't approved" in refused(folder)
        (folder / "decision.json").write_text('{"decision": "reject"}', encoding="utf-8")
        assert "isn't approved" in refused(folder)
        assert tree_state(tmp / "Assets") == before and ic.FLAIL_PY.read_text(encoding="utf-8") == flail_before
        print("Undecided and rejected work is refused, and nothing changes")

        ic.install(folder, dry=True)
        assert tree_state(tmp / "Assets") == before and ic.FLAIL_PY.read_text(encoding="utf-8") == flail_before
        print("A dry run changes nothing")

        (folder / "decision.json").write_text('{"decision": "approve"}', encoding="utf-8")
        ic.install(folder)

        for rel in m["files"]:
            assert (assets / rel).read_bytes() == (folder / rel).read_bytes(), rel
        for tag, count in (("idle", 3), ("flap", 8), ("flail", 12)):
            sub = {"idle": "CharacterIdle", "flap": "FartFlap", "flail": "DeathFlail"}[tag]
            assert len(list((assets / "Resources" / sub).glob(f"player11_{tag}_*.png"))) == count, tag
        print("All the files are copied, idle and flap included")

        for source, name in (("playerPrefab", "player11Prefab"), ("aiPrefab", "ai11Prefab")):
            old = (ic.PREFABS / f"{source}.prefab").read_text(encoding="utf-8")
            new = (ic.PREFABS / f"{name}.prefab").read_text(encoding="utf-8")
            differ = changed_lines(old, new)
            fields = {re.match(r"\s*(\w+):", y).group(1) for _, y in differ}
            assert len(old.splitlines()) == len(new.splitlines()) and {"m_Name", "m_Sprite"} <= fields <= {"m_Name", "m_Sprite", "oldSize"}, differ
            guid = re.search(r"\nguid: (\S+)", (ic.PREFABS / f"{name}.prefab.meta").read_text(encoding="utf-8")).group(1)
            assert guid != re.search(r"\nguid: (\S+)", (ic.PREFABS / f"{source}.prefab.meta").read_text(encoding="utf-8")).group(1)
        print("Two prefabs, with only the name, the sprite and the size changed")

        fit = json.loads(ic.FIT.read_text(encoding="utf-8"))
        places = {(p["skin"], p["item"]): p for p in fit["places"]}
        template = bridge._rgba(ic.TEMPLATE_SPRITE)
        where = parts.face_positions(template, parts.of(template))
        tx, ty, tdist = ic.eye_place(where["eyes"])
        x, y, dist = ic.eye_place(m["face"]["eyes"])
        for item in ("black_shades", "silver_aviators"):
            old, new = places[("player", item)], places[("player11", item)]
            assert abs(new["cx"] - old["cx"] - (x - tx)) < 0.02 and abs(new["cy"] - old["cy"] - (y - ty)) < 0.02, (old, new)
            assert abs(new["scale"] - old["scale"] * dist / tdist) < 1e-4, (old, new)
        lift = ic.top_row(ic.TEMPLATE_SPRITE) - ic.top_row(folder / "Sprites" / "Characters" / "player11.png")
        assert lift > 0 and places[("player11", "santa_hat")]["cy"] == max(0.0, places[("player", "santa_hat")]["cy"] - lift)
        assert b"\r\n" in ic.FIT.read_bytes(), "fit.json keeps its line endings"
        print("Shades sit on the new eyes, and hats ride up on the taller hair")

        assert json.loads(ic.NAMES.read_text(encoding="utf-8"))["names"] == {"player11": "Darnell"}
        flail_after = ic.FLAIL_PY.read_text(encoding="utf-8")
        assert flail_after.count('"player11":') == 1
        namespace = {}
        table = re.search(r"^CHARACTERS = \{\n(?:.*\n)*?\}\n", flail_after, re.M).group(0)
        exec(table, namespace)
        assert namespace["CHARACTERS"]["player11"] == namespace["CHARACTERS"]["player"] and len(namespace["CHARACTERS"]) == 11
        print("The first name and the flail row are in, once each")

        # A second install refuses, with nothing overwritten.
        after = tree_state(tmp / "Assets")
        assert "already exists" in refused(folder)
        assert tree_state(tmp / "Assets") == after and ic.FLAIL_PY.read_text(encoding="utf-8") == flail_after
        print("A second install refuses, and nothing is overwritten")

        # A half-installed slot refuses before writing anything.
        other = test_bridge.good_character(tmp / "work", slot=12, first_name="Marcus", hair_rgb=(40, 200, 220))
        m2 = json.loads((other / "manifest.json").read_text(encoding="utf-8"))
        (other / "decision.json").write_text('{"decision": "approve"}', encoding="utf-8")
        (ic.PREFABS / "ai12Prefab.prefab").write_text("already here", encoding="utf-8")
        state = tree_state(tmp / "Assets")
        assert "already exists" in refused(other)
        assert tree_state(tmp / "Assets") == state
        (ic.PREFABS / "ai12Prefab.prefab").unlink()
        ic.install(other)
        assert json.loads(ic.NAMES.read_text(encoding="utf-8"))["names"] == {"player11": "Darnell", "player12": "Marcus"}
        assert ic.FLAIL_PY.read_text(encoding="utf-8").count('"player12":') == 1
        assert m2["skin"] == "player12"
        print("A half-installed slot refuses first, and a second character installs beside the first")

        # The original ten's names go in once approved, and never overwrite a different name.
        names = tmp / "names"
        names.mkdir()
        (names / "manifest.json").write_text(json.dumps({"kind": "names", "name": "First names", "names": {"player": "Gary", "player2": "Doug"}}), encoding="utf-8")
        assert "isn't approved" in refused(names)
        (names / "decision.json").write_text('{"decision": "approve"}', encoding="utf-8")
        ic.install(names)
        assert json.loads(ic.NAMES.read_text(encoding="utf-8"))["names"]["player2"] == "Doug"
        (names / "manifest.json").write_text(json.dumps({"kind": "names", "name": "First names", "names": {"player2": "Other"}}), encoding="utf-8")
        assert "already has other names" in refused(names)
        print("The original ten's names go in once approved, and a different name is refused")

    ic.ASSETS, ic.FLAIL_PY = real_assets, real_flail
    for path, stamp in real_state.items():
        assert Path(path).stat().st_mtime_ns == stamp, f"{path} changed"
    print("The real project wasn't touched")
    print("all passed")


if __name__ == "__main__":
    main()
