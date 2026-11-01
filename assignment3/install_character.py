"""Puts an approved character into the Unity project. Refuses anything David hasn't approved on the dashboard.

Copies the submission's sprite, flail, idle and flap frames and splat pair, makes the player and AI prefab pair, adds the skin
to the hats-and-shades fit file, its row to flail.py's CHARACTERS, and its first name to CharacterNames.json. A prefab differs
from playerPrefab only in its name, its sprite and its size (checked against player10Prefab on 2026-10-30), so it's written
as text, the same way flail.py writes metas. Nothing is committed: David tests in the game and says commit.

The names submission for the original ten goes through here too, and only touches CharacterNames.json.

usage: python install_character.py C:\\cluster\\submissions\\characters\\player11_t1 [--dry-run]
"""
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

import parts

ASSETS = Path(r"C:\bbust\BBUST\Assets")
PREFABS = ASSETS / "Resources" / "Prefabs"
FIT = ASSETS / "Resources" / "Wearables" / "fit.json"
NAMES = ASSETS / "Resources" / "CharacterNames.json"
TEMPLATE_SPRITE = ASSETS / "Sprites" / "Characters" / "player.png"
FLAIL_PY = Path(r"C:\bbust\CoverArt\tools\flail.py")


def guid_for(text):
    return hashlib.md5(text.encode()).hexdigest()


def top_row(path):
    return int(np.nonzero(np.array(Image.open(path).convert("RGBA"))[..., 3])[0].min())


def make_prefab(source, name, sprite_id, sprite_guid, size, dry):
    text = (PREFABS / f"{source}.prefab").read_text(encoding="utf-8")
    text, n1 = re.subn(rf"m_Name: {source}\b", f"m_Name: {name}", text)
    text, n2 = re.subn(r"m_Sprite: \{fileID: -?\d+, guid: \w+, type: 3\}", f"m_Sprite: {{fileID: {sprite_id}, guid: {sprite_guid}, type: 3}}", text, count=1)
    text, n3 = re.subn(r"oldSize: \{x: [\d.]+, y: [\d.]+\}", f"oldSize: {{x: {size[0]:g}, y: {size[1]:g}}}", text, count=1)
    if (n1, n2, n3) != (1, 1, 1):
        raise SystemExit(f"{source}.prefab isn't shaped as expected: {n1} names, {n2} sprites, {n3} sizes")
    meta = re.sub(r"\nguid: \S+", "\nguid: " + guid_for(f"Resources/Prefabs/{name}"), (PREFABS / f"{source}.prefab.meta").read_text(encoding="utf-8"))
    print(f"{'would write' if dry else 'writing'} {name}.prefab")
    if not dry:
        (PREFABS / f"{name}.prefab").write_text(text, encoding="utf-8", newline="\n")
        (PREFABS / f"{name}.prefab.meta").write_text(meta, encoding="utf-8", newline="\n")


def eye_place(eyes):
    """The middle of two eyes, and the distance between them."""
    (lx, ly), (rx, ry) = eyes
    return (lx + rx) / 2, (ly + ry) / 2, rx - lx


def add_fit(skin, body_path, face, dry):
    """The template's own places, moved to this face. Hats ride up by however much taller the hair is. Shades sit on this
    character's own eyes and scale to their distance, as mock_wearables.py does for the original ten."""
    fit = json.loads(FIT.read_text(encoding="utf-8"))
    if any(p["skin"] == skin for p in fit["places"]):
        print(f"{skin} is already in fit.json")
        return
    catalog = json.loads((FIT.with_name("catalog.json")).read_text(encoding="utf-8"))
    kinds = {i["id"]: i["kind"] for i in catalog["items"]}
    lift = top_row(TEMPLATE_SPRITE) - top_row(body_path)
    template = np.array(Image.open(TEMPLATE_SPRITE).convert("RGBA"))
    tx, ty, tdist = eye_place(parts.face_positions(template, parts.of(template))["eyes"])
    x, y, dist = eye_place(face["eyes"])
    added = []
    for p in fit["places"]:
        if p["skin"] == "player":
            q = dict(p, skin=skin)
            if kinds.get(p["item"]) == "hat":
                q["cy"] = max(0.0, p["cy"] - lift)
            elif kinds.get(p["item"]) == "shades":
                q["cx"], q["cy"] = round(p["cx"] + x - tx, 2), round(p["cy"] + y - ty, 2)
                q["scale"] = round(p["scale"] * dist / tdist, 5)
            added.append(q)
    print(f"{'would add' if dry else 'adding'} {len(added)} fit places for {skin}; hats lifted {lift} px, shades moved {x - tx:+.0f},{y - ty:+.0f} px")
    if not dry:
        fit["places"].extend(added)
        FIT.write_text(json.dumps(fit, indent=1), encoding="utf-8", newline="\r\n")


def add_flail_row(skin, dry):
    """flail.py's table holds every skin's grid. A new sprite sits on the template's grid, so its row is the template's."""
    text = FLAIL_PY.read_text(encoding="utf-8")
    if re.search(rf'^\s*"{skin}":', text, re.M):
        print(f"{skin} is already in flail.py")
        return
    row = re.search(r'^    "player":\s*(\(.*\)),$', text, re.M)
    table = re.search(r"^CHARACTERS = \{\n(?:.*\n)*?\}\n", text, re.M)
    if not row or not table:
        raise SystemExit("flail.py's CHARACTERS table isn't shaped as expected")
    print(f"{'would add' if dry else 'adding'} {skin}'s row to flail.py")
    if not dry:
        end = table.end() - 2
        FLAIL_PY.write_text(f'{text[:end]}    "{skin}": {row.group(1)},\n{text[end:]}', encoding="utf-8", newline="\n")


def add_names(names, dry):
    """CharacterNames.json is what the game reads for the name list. Names already in it stay as they are."""
    data = json.loads(NAMES.read_text(encoding="utf-8")) if NAMES.exists() else {"names": {}}
    taken = {k: v for k, v in names.items() if k in data["names"] and data["names"][k] != v}
    if taken:
        raise SystemExit(f"CharacterNames.json already has other names for {sorted(taken)}; nothing was overwritten")
    print(f"{'would add' if dry else 'adding'} first names: {names}")
    if not dry:
        data["names"].update(names)
        NAMES.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8", newline="\n")


def install(folder, dry=False):
    folder = Path(folder)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    decision_path = folder / "decision.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8")) if decision_path.exists() else {}
    if decision.get("decision") != "approve" and not dry:
        raise SystemExit(f"{manifest['name']} isn't approved on the dashboard yet (decision: {decision.get('decision')})")
    if manifest["kind"] == "names":
        add_names(manifest["names"], dry)
        return

    skin, slot = manifest["skin"], manifest["slot"]
    # Everything is checked before anything is written, so a refusal leaves the project untouched.
    for dst in [ASSETS / rel for rel in manifest["files"]] + [PREFABS / f"player{slot}Prefab.prefab", PREFABS / f"ai{slot}Prefab.prefab"]:
        if dst.exists():
            raise SystemExit(f"{dst} already exists; nothing was overwritten")
    for rel in manifest["files"]:
        if not dry:
            dst = ASSETS / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(folder / rel, dst)
    print(f"{'would copy' if dry else 'copied'} {len(manifest['files'])} files")

    meta = (folder / "Sprites" / "Characters" / f"{skin}.png.meta").read_text(encoding="utf-8")
    sprite_guid = re.search(r"\nguid: (\S+)", meta).group(1)
    sprite_id = re.search(r"\n      internalID: (\S+)", meta).group(1)
    size = (manifest["rect"]["width"] / 100, manifest["rect"]["height"] / 100)
    make_prefab("playerPrefab", f"player{slot}Prefab", sprite_id, sprite_guid, size, dry)
    make_prefab("aiPrefab", f"ai{slot}Prefab", sprite_id, sprite_guid, size, dry)
    add_fit(skin, folder / "Sprites" / "Characters" / f"{skin}.png", manifest["face"], dry)
    add_flail_row(skin, dry)
    add_names({skin: manifest["first_name"]}, dry)


def main():
    install(sys.argv[1], "--dry-run" in sys.argv)


if __name__ == "__main__":
    main()
