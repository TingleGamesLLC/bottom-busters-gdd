"""The Bridge on the original ten, and on copies broken on purpose. Spends no model time and writes only to a temp folder.

usage: python test_bridge.py
"""
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

import bridge
import common
import parts

ASSETS = bridge.ASSETS
ROSTER = bridge.ROSTER
FRAME_SETS = [("DeathFlail", "flail", range(12)), ("CharacterIdle", "idle", range(3)), ("FartFlap", "flap", range(8))]
_counter = {"n": 0}


def fixture(skin, tmp, slot=None, first_name=None, concept=None):
    """A submission-shaped folder made from the game's own files for one skin. With slot it's renamed to that slot, each file
    with its own guid, the way the Character Artist writes them."""
    _counter["n"] += 1
    name = f"player{slot}" if slot else skin
    folder = Path(tmp) / f"{name}_{_counter['n']}"

    def bring(source, rel):
        dst = folder / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dst)
        meta = source.with_suffix(".png.meta").read_text(encoding="utf-8")
        meta = re.sub(r"\nguid: \S+", "\nguid: " + hashlib.md5(rel.encode()).hexdigest(), meta)
        dst.with_suffix(".png.meta").write_text(meta, encoding="utf-8", newline="\n")
        return [rel, rel + ".meta"]

    files = bring(ASSETS / "Sprites" / "Characters" / f"{skin}.png", f"Sprites/Characters/{name}.png")
    for sub, tag, frames in FRAME_SETS:
        for k in frames:
            files += bring(ASSETS / "Resources" / sub / f"{skin}_{tag}_{k:02}.png", f"Resources/{sub}/{name}_{tag}_{k:02}.png")
    for suffix in ("splat", "splatchar"):
        files += bring(ASSETS / "Resources" / "DeathSplat" / f"{skin}_{suffix}.png", f"Resources/DeathSplat/{name}_{suffix}.png")
    meta = (folder / "Sprites" / "Characters" / f"{name}.png.meta").read_text(encoding="utf-8")
    rect = {k: int(float(re.search(rf"\n        {k}: (\S+)", meta).group(1))) for k in ("x", "y", "width", "height")}
    manifest = {"kind": "character", "name": f"{first_name or skin} ({name})", "agent": "Character Artist", "slot": slot or 1, "skin": name,
                "concept": concept or {"name": first_name or skin, "hair": "x", "hair_color": "x", "skin_tone": "default"},
                "first_name": first_name or "", "set": "test", "rect": rect, "files": files, "previews": [],
                "face": {"eyes": [[501, 206], [568, 206]], "mouth": [541, 270]}}
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return folder


def body_of(folder):
    m = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    return folder / "Sprites" / "Characters" / f"{m['skin']}.png"


def new_look(body, hair_rgb=(230, 40, 160), shift=0, tone=(0.45, 0.35, 0.3)):
    """A head nobody else has, painted by plain code: a tall crest in one bright color, a new face and a dark skin."""
    g = parts.flail.Body("player")
    out = body.copy()
    skin = parts.of(out)["skin"]

    def paint(i0, i1, j0, j1, rgba):
        x0, _, y0, _ = g.cell_rect(i0, j0)
        _, x1, _, y1 = g.cell_rect(i1, j1)
        out[y0:y1, x0:x1] = rgba

    bare = tuple(int(v) for v in skin) + (255,)
    paint(*parts.FACE_CELLS, *parts.FACE_ROWS, bare)
    paint(28, 62, 2, 14, tuple(hair_rgb) + (255,))
    for i in (41 + shift, 47 + shift):
        paint(i, i + 1, 17, 18, (250, 250, 250, 255))
        paint(i + 2, i + 2, 17, 18, (10, 10, 10, 255))
    paint(40 + shift, 43 + shift, 15, 15, (20, 20, 90, 255))
    paint(46 + shift, 49 + shift, 15, 15, (20, 20, 90, 255))
    paint(42 + shift, 47 + shift, 22, 24, (150, 20, 40, 255))
    keep = parts.skin_like(out, skin)
    out[..., :3][keep] = (out[..., :3][keep] * np.array(tone)).astype(np.uint8)
    return out


def good_character(tmp, slot=11, first_name="Testname", **look):
    """A character that passes everything: the template's files with a new look painted on the body."""
    folder = fixture("player", tmp, slot=slot, first_name=first_name)
    path = body_of(folder)
    Image.fromarray(new_look(bridge._rgba(path), **look)).save(path)
    return folder


def copy_of(folder, tmp):
    _counter["n"] += 1
    other = Path(tmp) / f"copy_{_counter['n']}"
    shutil.copytree(folder, other)
    return other


def edit_manifest(folder, **changes):
    path = folder / "manifest.json"
    m = json.loads(path.read_text(encoding="utf-8"))
    m.update(changes)
    path.write_text(json.dumps(m, indent=1), encoding="utf-8")
    return folder


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        common.SUBMISSIONS = tmp / "submissions"
        (common.SUBMISSIONS / "characters").mkdir(parents=True)
        real_limits = bridge.LIMITS
        bridge.LIMITS = tmp / "limits.json"
        shutil.copyfile(real_limits, bridge.LIMITS)

        # The original ten pass, or the checks are wrong.
        for skin in ROSTER:
            problems = bridge.check_character(fixture(skin, tmp), baseline=True)
            assert problems == [], (skin, problems)
        print("The original ten pass")

        good = good_character(tmp)
        assert bridge.check_character(good) == [], bridge.check_character(good)
        print("A character with a new look passes")

        def broken(*rel):
            other = copy_of(good, tmp)
            for r in rel:
                (other / r).unlink()
            return other

        for tag, rel in (("idle_01", "Resources/CharacterIdle/player11_idle_01.png"), ("flap_07", "Resources/FartFlap/player11_flap_07.png"),
                         ("flail_05", "Resources/DeathFlail/player11_flail_05.png"), ("splat", "Resources/DeathSplat/player11_splat.png")):
            problems = bridge.check_character(broken(rel))
            assert any(tag in p for p in problems), (tag, problems)
        print("Missing frames are named")

        other = copy_of(good, tmp)
        img = bridge._rgba(body_of(other))
        briefs = bridge._briefs(img)
        img[briefs] = (40, 80, 200, 255)
        Image.fromarray(img).save(body_of(other))
        assert any("briefs" in p for p in bridge.check_character(other))
        print("Changed briefs are caught")

        other = copy_of(good, tmp)
        img = bridge._rgba(body_of(other))
        fx0, fx1, fy0, fy1 = parts.FACE_BOX
        p = parts.of(img)
        box = img[fy0:fy1, fx0:fx1]
        was_skin = parts.skin_like(box, p["skin"]) & (box[..., 3] > 128)
        box[..., :3][was_skin] = (box[..., :3][was_skin] * 2.2).clip(0, 255).astype(np.uint8)
        Image.fromarray(img).save(body_of(other))
        problems = bridge.check_character(other)
        assert any("skin" in x for x in problems), problems
        print("A head on a different skin from its body is caught")

        # A new skin tone alone can't pass: same hair and face as the template, only the skin moved.
        other = fixture("player", tmp, slot=11, first_name="Onlytone")
        img = bridge._rgba(body_of(other))
        p = parts.of(img)
        keep = parts.skin_like(img, p["skin"])
        img[..., :3][keep] = (img[..., :3][keep] * np.array((0.43, 0.35, 0.30))).astype(np.uint8)
        Image.fromarray(img).save(body_of(other))
        problems = bridge.check_character(other)
        assert any("hair" in x for x in problems) and any("face" in x for x in problems), problems
        print("A new skin tone alone fails on both hair and face")

        # Nor can an old skin with a new look.
        other = fixture("player", tmp, slot=11, first_name="Oldskin")
        Image.fromarray(new_look(bridge._rgba(body_of(other)), tone=(1, 1, 1))).save(body_of(other))
        assert any("skin tone" in x for x in bridge.check_character(other)), bridge.check_character(other)
        print("The original ten's skin tone is caught")

        assert any("first name" in x for x in bridge.check_character(edit_manifest(copy_of(good, tmp), first_name="")))
        print("A missing first name is caught")

        taken = copy_of(good, tmp)
        shutil.copytree(taken, common.SUBMISSIONS / "characters" / "player12_t1")
        edit_manifest(common.SUBMISSIONS / "characters" / "player12_t1", first_name="Sameguy", skin="player12", slot=12)
        assert any("already" in x for x in bridge.check_character(edit_manifest(copy_of(good, tmp), first_name="sameguy")))
        print("A repeated first name is caught")
        (common.SUBMISSIONS / "characters" / "player12_t1" / "decision.json").write_text('{"decision": "reject"}', encoding="utf-8")
        assert bridge.check_character(edit_manifest(copy_of(good, tmp), first_name="sameguy")) == []
        print("A rejected submission's name is free again")
        shutil.rmtree(common.SUBMISSIONS / "characters" / "player12_t1")

        over = bridge.game_slot_limit() + 1
        assert any("limit" in x for x in bridge.check_character(edit_manifest(copy_of(good, tmp), slot=over)))
        print("A slot past the game's limit is caught")
        assert any("face" in x for x in bridge.check_character(edit_manifest(copy_of(good, tmp), face={"eyes": [], "mouth": []})))
        print("Missing eye and mouth positions are caught")

        other = copy_of(good, tmp)
        a = other / "Resources" / "DeathFlail" / "player11_flail_00.png.meta"
        b = other / "Resources" / "DeathFlail" / "player11_flail_01.png.meta"
        guid = re.search(r"\nguid: (\S+)", a.read_text(encoding="utf-8")).group(1)
        b.write_text(re.sub(r"\nguid: \S+", "\nguid: " + guid, b.read_text(encoding="utf-8")), encoding="utf-8")
        assert any("guid" in x for x in bridge.check_character(other))
        print("A duplicate guid is caught")

        other = copy_of(good, tmp)
        (other / "Resources" / "FartFlap" / "player11_flap_00.png").write_bytes(b"not a png")
        problems = bridge.check_character(other)
        assert problems and any("flap_00" in x for x in problems), problems
        other = copy_of(good, tmp)
        body_of(other).write_bytes(b"not a png")
        problems = bridge.check_character(other)
        assert problems and isinstance(problems, list), problems
        (other / "manifest.json").write_text("{ not json", encoding="utf-8")
        problems = bridge.check_character(other)
        assert problems and "couldn't run" in problems[0], problems
        print("Corrupt files come back as problems, not exceptions")

        # Very dark skin: the parts still sort, and the eyes and mouth are still found.
        deep = new_look(bridge._rgba(ASSETS / "Sprites" / "Characters" / "player.png"), hair_rgb=(10, 10, 10), tone=(0.3, 0.25, 0.2))
        p = parts.of(deep)
        row, col = np.nonzero(bridge._briefs(deep))
        assert not p["hair"][row, col].any() and not p["face"][row, col].any()
        assert p["hair"].sum() > 5000 and p["face"].sum() > 500, (p["hair"].sum(), p["face"].sum())
        where = parts.face_positions(deep, p)
        assert len(where["eyes"]) == 2 and where["mouth"], where
        print("Very dark skin still sorts into hair, face and briefs")

        # The eye finder lands near the splat tables on the bare-faced originals.
        import splat_faces
        for skin in ("player", "player10"):
            body = bridge._rgba(ASSETS / "Sprites" / "Characters" / f"{skin}.png")
            where = parts.face_positions(body, parts.of(body))
            for (x, y), box in zip(where["eyes"], splat_faces.EYES[skin]):
                assert abs(x - (box[0] + box[1]) / 2) < 15 and abs(y - (box[2] + box[3]) / 2) < 15, (skin, where, box)
            assert abs(where["mouth"][0] - splat_faces.MOUTHS[skin][1][0]) < 20, (skin, where)
        print("Eyes and mouths land where the splat tables have them")

        rule = {"chunk_size": 10, "first_stop": 2}
        assert bridge.check_chunk_plan([{"brief": "a"}], {"units": 2}, rule)
        assert bridge.check_chunk_plan([{"brief": "a"}, {"brief": "A "}], {"units": 2}, rule)
        assert bridge.check_chunk_plan([{"brief": "a"}, {"brief": ""}], {"units": 2}, rule)
        assert bridge.check_chunk_plan([{"brief": str(k)} for k in range(11)], {"units": 11}, rule)
        assert bridge.check_chunk_plan(["not a task"], {"units": 1}, rule)
        assert bridge.check_chunk_plan([{"brief": "a"}, {"brief": "b"}], {"units": 2}, rule) == []
        print("Chunk plans are checked")

        facts = bridge.character_facts(good)
        for key in ("nearest_roster", "difference_from_nearest", "hair_distance", "face_distance", "size_mb", "running_total_mb"):
            assert key in facts, facts
        print("Facts:", facts)

        # Limits come down to what David approved, and don't rise past where the roster started them.
        start = bridge.start_limits()
        assert bridge.set_limits() == start
        approved = common.SUBMISSIONS / "characters" / "player11_a"
        shutil.copytree(good, approved)
        (approved / "decision.json").write_text('{"decision": "approve"}', encoding="utf-8")
        close = common.SUBMISSIONS / "characters" / "player12_a"
        shutil.copytree(good, close)
        edit_manifest(close, skin="player12", slot=12, first_name="Other")
        for path in close.rglob("player11*"):
            path.rename(path.with_name(path.name.replace("player11", "player12")))
        (close / "decision.json").write_text('{"decision": "approve"}', encoding="utf-8")
        new = bridge.set_limits()
        assert new["hair"] < start["hair"] and new["face"] < start["face"], (new, start)
        print("Limits come down to what David approved:", new)
    print("all passed")


if __name__ == "__main__":
    main()
