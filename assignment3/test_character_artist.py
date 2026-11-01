"""The Character Artist with a stand-in for PixelLab and for the cluster. Runs the real art tools, writes only to a temp folder.

usage: python test_character_artist.py
"""
import io
import json
import os
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

import bridge
import character_artist as ca
import common
import flail
import parts


def tree_state(root):
    """Every file under the project's Assets, with its size and time. Any change shows up as a different dict."""
    state = {}
    for where, _, names in os.walk(root):
        for n in names:
            st = os.stat(os.path.join(where, n))
            state[os.path.join(where, n)] = (st.st_size, st.st_mtime_ns)
    return state


PAINT = {"skin": None, "hair": (38, 52, (235, 60, 150))}


def stand_in_paint(image_png, mask_png, description, seed, **_):
    """Paints what PixelLab is asked for, on the same grid: a crest of hair, and a face with two eyes, brows, a nose and a mouth.
    Real PixelLab can pick its own skin color, so PAINT["skin"] paints the face in one. Every pixel outside the mask stays."""
    h = ca.Head()
    out = np.array(Image.open(io.BytesIO(image_png)).convert("RGBA"))
    PAINT["image"], PAINT["description"] = out.copy(), description
    PAINT["mask"] = np.array(Image.open(io.BytesIO(mask_png)).convert("RGBA"))
    ca.pixellab._spent["calls"] += 1

    def paint(i0, i1, j0, j1, rgb):
        out[j0:j1 + 1, i0:i1 + 1] = tuple(rgb) + (255,)

    if PAINT["skin"]:
        for j, i in zip(*np.nonzero(h.face)):
            paint(i, i, j, j, PAINT["skin"])
    paint(PAINT["hair"][0], PAINT["hair"][1], 4, 14, PAINT["hair"][2])
    for i in (40, 47):
        paint(i, i + 1, 17, 19, (250, 250, 250))
        paint(i + 2, i + 2, 17, 19, (10, 10, 10))
    paint(39, 43, 15, 15, (30, 20, 20))
    paint(46, 50, 15, 15, (30, 20, 20))
    paint(45, 45, 20, 21, (150, 90, 60))
    paint(41, 49, 23, 25, (150, 20, 40))
    buf = io.BytesIO()
    Image.fromarray(out).save(buf, "PNG")
    return buf.getvalue(), {"generations": 1}


def stand_in_ask(reply, seen=None):
    def ask_json(agent, messages, required, **_):
        if seen is not None:
            seen.append(messages)
        return dict(reply)
    return ask_json


REPLY = {"first_name": "Darnell", "hair": "tall crest", "hair_color": "pink", "beard": False, "beard_desc": "", "face": "wide eyes, thin brows, small smile",
         "skin_tone": "deep", "why_distinct": "secret reasoning"}


def must_be_malformed(reply, the_set):
    try:
        ca.check_concept(dict(reply), the_set)
    except common.MalformedOutput as e:
        return str(e)
    raise AssertionError(f"this should have been sent back: {reply}")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        common.SUBMISSIONS = tmp / "submissions"
        common.WORK = tmp / "work"
        (common.SUBMISSIONS / "characters").mkdir(parents=True)
        ca.pixellab.inpaint = stand_in_paint
        seen = []
        common.ask_json = stand_in_ask(REPLY, seen)

        # The sets are the design's, in its order, and every tone reads as new against the original ten.
        assert [s["name"] for s in ca.SETS] == ["African American", "East Asian", "Southeast Asian", "Pacific Islander", "Hispanic", "Indian",
                                                "Middle Eastern/North African", "Native American/Indigenous"]
        for s in ca.SETS:
            assert s["tones"] and s["hair_notes"]
            for tone in s["tones"]:
                assert np.abs(np.array(ca.TONES[tone], float) - np.array(ca.SKIN_BASE, float)).mean() >= bridge.limits()["skin"], tone
        print("Eight sets in order, and every tone is new")

        before = tree_state(bridge.ASSETS)
        limit = bridge.game_slot_limit()
        folder, concept = ca.make({"id": "t1", "brief": "the first one"}, limit - 9, [], None, 1)
        skin = f"player{limit - 9}"
        assert tree_state(bridge.ASSETS) == before, "the art step changed something in the project"
        print("Nothing under the project's Assets changed")

        # What PixelLab is given: the real grid, the body in the character's tone, and a clean mask.
        assert PAINT["image"].shape == (88, 88, 4) and PAINT["mask"].shape == (88, 88, 4)
        assert set(np.unique(PAINT["mask"][..., :3])) == {0, 255}, "the mask has to be pure black and white"
        h = ca.Head()
        assert (PAINT["mask"][:h.ny, :h.nx, 0][h.face_box] == 255).all(), "part of the face box was left out"
        assert (PAINT["mask"][:h.ny, :h.nx, 0][h.jj >= 40] == 0).all(), "the body has to stay out of the mask"
        torso = PAINT["image"][36:46, 40:52, :3].astype(float)
        assert np.abs(np.median(torso.reshape(-1, 3), axis=0) - np.array(ca.TONES["deep"], float)).mean() < 12, "the body should show the character's tone"
        assert "pink" in PAINT["description"] and "secret reasoning" not in PAINT["description"]
        print("PixelLab gets the 88 by 88 body in the character's tone, with a clean mask of only the head")

        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        assert concept["first_name"] == "Darnell" and manifest["first_name"] == "Darnell", manifest
        assert manifest["set"] == ca.SETS[0]["name"], manifest["set"]
        assert skin in flail.CHARACTERS
        assert manifest["face"]["eyes"] and manifest["face"]["mouth"], manifest["face"]
        assert manifest["pixellab"]["calls"] == 1, manifest["pixellab"]
        problems = bridge.check_character(folder)
        assert problems == [], problems
        print("The Bridge passes it, on one PixelLab call:", bridge.character_facts(folder))
        for rel in manifest["previews"]:
            assert (folder / rel).exists(), rel
        assert not list(folder.rglob("_tools")) and not list(folder.rglob("_pivot"))
        assert not list((folder / "Resources").glob("*.meta")), "folder metas stay out of the submission"
        assert not list((common.SUBMISSIONS / "characters").iterdir()), "nothing reaches the approval screen until it's published"
        print("All 3 animations, the splat and the previews are there, with no leftovers, and it's still off the approval screen")

        # The briefs and the body are the template's, the hair kept its color, and the skin moved to the tone.
        body = bridge._rgba(folder / "Sprites" / "Characters" / f"{skin}.png")
        template = bridge._rgba(bridge.SPRITES / "player.png")
        briefs = bridge._briefs(template)
        assert np.array_equal(body[briefs], template[briefs])
        assert np.abs(parts.of(body)["skin"] - np.array(ca.TONES["deep"], float)).mean() < 12, parts.of(body)["skin"]
        for sub, tag, count in (("CharacterIdle", "idle", 3), ("FartFlap", "flap", 8), ("DeathFlail", "flail", 12)):
            for k in range(count):
                frame = bridge._rgba(folder / "Resources" / sub / f"{skin}_{tag}_{k:02}.png")
                p = parts.of(frame)
                assert np.abs(p["skin"] - np.array(ca.TONES["deep"], float)).mean() < 16, (tag, k, p["skin"])
                pink = (frame[..., 0] > 200) & (frame[..., 1] < 110) & (frame[..., 2] > 100) & (frame[..., 3] > 128)
                assert pink.sum() > 5000, (tag, k, int(pink.sum()))
        print("Every animation frame has the deep skin and the hair's own color")

        # Things seen by eye on a stand-in: light skin left on the ear, the head's right outline erased, the old mouth on the splat.
        head = body[:parts.HEAD_END]
        assert (parts.skin_like(head, ca.SKIN_BASE, low=0.85, high=1.15) & (head[..., 3] > 128)).sum() < 200, "light skin left on a dark head"
        for j in range(parts.FACE_ROWS[0], parts.FACE_ROWS[1] + 1):
            outline = np.nonzero((h.cells[j, :ca.HEAD_RIGHT_LIMIT, 3] > 128) & (parts.lum(h.cells[j, :ca.HEAD_RIGHT_LIMIT, :3].astype(float)) < ca.OUTLINE_LUM))[0].max()
            x0, x1, y0, y1 = h.rect(int(outline), j)
            cell = body[y0:y1, x0:x1]
            assert cell[..., 3].mean() > 128 and parts.lum(cell[..., :3].astype(float)).mean() < ca.OUTLINE_LUM, ("outline gone", j)
        splat = bridge._rgba(folder / "Resources" / "DeathSplat" / f"{skin}_splatchar.png")
        mouth_red = (splat[..., 0] > 120) & (splat[..., 1] < 50) & (splat[..., 2] < 70) & (splat[..., 3] > 128)
        assert mouth_red[:parts.HEAD_END + 70].sum() < 2500, ("the live mouth shows on the splat", int(mouth_red[:parts.HEAD_END + 70].sum()))
        print("No light skin on the head, the outline stays, and the live mouth is gone from the splat")

        folder = ca.publish(folder)
        assert folder == common.SUBMISSIONS / "characters" / f"{skin}_t1" and (folder / "manifest.json").exists()
        assert not list(common.WORK.iterdir())
        print("Publishing moves it from the work folder to the approval screen")

        # PixelLab can pick its own skin. The head still has to match the body, on any tone.
        for k, (painted_color, tone, first) in enumerate((((249, 102, 56), "chestnut", "Andre"), ((115, 45, 15), "deep", "Jamal"), ((232, 190, 160), "espresso", "Reggie"))):
            PAINT["skin"] = painted_color
            common.ask_json = stand_in_ask(dict(REPLY, first_name=first, skin_tone=tone))
            painted, _ = ca.make({"id": f"s{k}", "brief": "x"}, limit - 8 + k, [], None, 20 + k)
            problems = bridge.check_character(painted)
            assert problems == [], (painted_color, problems)
            made = bridge._rgba(painted / "Sprites" / "Characters" / f"player{limit - 8 + k}.png")
            p = parts.of(made)
            assert parts.head_skin_share(made, p) > 0.35, (painted_color, parts.head_skin_share(made, p))
            assert not (made[:parts.HEAD_END, :, :3] == np.array(painted_color)).all(axis=-1).any(), ("the painted skin color is still on the head", painted_color)
            where = json.loads((painted / "manifest.json").read_text(encoding="utf-8"))["face"]
            assert len(where["eyes"]) == 2 and where["mouth"], where
        PAINT["skin"] = None
        print("Whatever skin PixelLab paints, the head matches the body")

        # Big black hair stays hair.
        PAINT["hair"] = (30, 60, (10, 10, 10))
        common.ask_json = stand_in_ask(dict(REPLY, first_name="Bighair", hair_color="black"))
        painted, _ = ca.make({"id": "b1", "brief": "x"}, limit - 2, [], None, 30)
        made = bridge._rgba(painted / "Sprites" / "Characters" / f"player{limit - 2}.png")
        dark = (parts.lum(made[..., :3].astype(float)) < 40) & (made[..., 3] > 128)
        assert dark[:parts.FACE_BOX[2]].sum() > 30000, int(dark[:parts.FACE_BOX[2]].sum())
        PAINT["hair"] = (38, 52, (235, 60, 150))
        print("Big black hair stays hair")

        # A beard keeps the mouth where the beard leaves room.
        common.ask_json = stand_in_ask(dict(REPLY, first_name="Beardname", beard=True, beard_desc="full beard"))
        bearded, _ = ca.make({"id": "t7", "brief": "x"}, limit - 7, [], None, 7)
        face = json.loads((bearded / "manifest.json").read_text(encoding="utf-8"))["face"]
        assert face["mouth_box"] == h.mouth_box, face
        common.ask_json = stand_in_ask(REPLY, seen)
        print("A beard keeps the mouth where the beard leaves room")

        # The rules reach the model. The maker's reasoning stays with the maker.
        system = seen[0][0]["content"].lower()
        for rule in ("real first name", "no jokes about accents or the group", "same cartoon treatment", "no exaggerated features", "same chubby body", "white briefs"):
            assert rule in system, rule
        print("The prompt carries David's rules")

        # What gets sent back without bothering anyone.
        first = ca.SETS[0]
        assert "Indian" not in must_be_malformed(dict(REPLY, first_name="Taco"), first)
        must_be_malformed(dict(REPLY, first_name="African"), first)
        must_be_malformed(dict(REPLY, first_name="Mexican"), first)
        must_be_malformed(dict(REPLY, first_name="Two Words"), first)
        must_be_malformed(dict(REPLY, first_name=""), first)
        must_be_malformed(dict(REPLY, hair="tall crest with a feather"), first)
        must_be_malformed(dict(REPLY, face="wears glasses"), first)
        must_be_malformed(dict(REPLY, face="arched brows, wide nose, thin smile"), first)
        must_be_malformed(dict(REPLY, face="small eyes, big lips"), first)
        must_be_malformed(dict(REPLY, hair_color="green"), first)
        assert must_be_malformed(dict(REPLY), first).startswith("the first name Darnell")   # already on the list
        print("Names and looks against the rules go back to the maker")
        assert ca.check_first_name("Jean-Luc") == "Jean-Luc" and ca.check_first_name("José") == "José" and ca.check_first_name("darnell") == "Darnell"

        # A tone from outside the set is replaced from the set.
        common.ask_json = stand_in_ask(dict(REPLY, first_name="Marcus", skin_tone="sunburn"))
        assert ca.concept("x", [], None, first, 3)["skin_tone"] in first["tones"]
        print("A tone from outside the set is replaced from the set")

        # Past the game's limit, it's David's call: the Builder's job goes first.
        for ask in (lambda: ca.make({"id": "t9", "brief": "x"}, limit + 1, [], None, 1), lambda: ca.limit_check(limit + 1)):
            try:
                ask()
                raise AssertionError("past the limit should stop")
            except common.NeedsDavid as e:
                assert "Builder" in str(e), e
        print("A slot past the game's limit asks David, naming the Builder's job")

        # A folder David decided on stays. A rejected first name is free again.
        common.ask_json = stand_in_ask(dict(REPLY, first_name="Marcus"))
        (folder / "decision.json").write_text('{"decision": "reject"}', encoding="utf-8")
        again = ca.publish(ca.make({"id": "t1", "brief": "the first one"}, limit - 9, [], None, 2)[0])
        assert again != folder and (folder / "decision.json").exists() and again.name.endswith("_2"), again
        print("A folder David decided on is kept, and the new attempt goes beside it")

        # An undecided folder is the same task's last attempt, and is replaced.
        common.ask_json = stand_in_ask(dict(REPLY, first_name="Tyrone"))
        third = ca.publish(ca.make({"id": "t1", "brief": "the first one"}, limit - 9, [], None, 3)[0])
        assert third == again
        print("An undecided attempt is replaced")

        # A head with no eyes tries once more, then it's a send-back, with nothing left behind.
        calls = {"n": 0}

        def no_eyes(image_png, mask_png, description, seed, **_):
            calls["n"] += 1
            return image_png, {}

        ca.pixellab.inpaint = no_eyes
        common.ask_json = stand_in_ask(dict(REPLY, first_name="Terrell"))
        try:
            ca.make({"id": "t5", "brief": "x"}, limit - 5, [], None, 4)
            raise AssertionError("no eyes should send it back")
        except common.MalformedOutput as e:
            assert "eyes" in str(e) and calls["n"] == 2, (e, calls)
        assert not list(common.WORK.glob(f"player{limit - 5}*")) and not list((common.SUBMISSIONS / "characters").glob(f"player{limit - 5}*"))
        print("No eyes from PixelLab tries once more, then goes back to the maker, with nothing left behind")

        # Out of credits partway through stops the run, and nothing reaches the approval screen.
        def broke(*a, **kw):
            raise common.CrewStop("PixelLab is out of credits and generations")

        ca.pixellab.inpaint = broke
        try:
            ca.make({"id": "t6", "brief": "x"}, limit - 6, [], None, 5)
            raise AssertionError("out of credits should stop")
        except common.CrewStop as e:
            assert "credits" in str(e), e
        assert not list((common.SUBMISSIONS / "characters").glob(f"player{limit - 6}*"))
        print("Out of credits stops the run, with nothing on the approval screen")
        ca.pixellab.inpaint = stand_in_paint

        # The ten full sets move on to the next one.
        for k in range(ca.SET_SIZE):
            d = common.SUBMISSIONS / "characters" / f"fill{k}"
            d.mkdir()
            (d / "manifest.json").write_text(json.dumps({"kind": "character", "set": ca.SETS[0]["name"], "skin": f"x{k}"}), encoding="utf-8")
        assert ca.current_set({"brief": "x"})["name"] == ca.SETS[1]["name"]
        assert ca.current_set({"brief": "x", "set": "Hispanic"})["name"] == "Hispanic"
        print("A full set moves on to the next one")

        # First names for the original ten.
        all_names = {skin: f"Name{chr(97 + k)}" for k, skin in enumerate(ca.ORIGINALS)}
        all_names = {k: v.replace("Name", "Gar") for k, v in all_names.items()}
        common.ask_json = stand_in_ask({"names": all_names})
        names_folder = ca.make_original_names()
        m = json.loads((names_folder / "manifest.json").read_text(encoding="utf-8"))
        assert m["kind"] == "names" and m["names"] == all_names and (names_folder / "preview_names.png").exists()
        assert all_names["player2"] in m["name"]
        assert all_names["player2"].lower() in bridge.taken_names()
        for bad in ({"names": dict(all_names, player3="")}, {"names": dict(all_names, player3=all_names["player"])}, {"names": "nope"}):
            common.ask_json = stand_in_ask(bad)
            try:
                ca.make_original_names()
                raise AssertionError(f"should send back: {bad}")
            except common.MalformedOutput:
                pass
        print("First names for the original ten come in as one submission")
    print("all passed")


if __name__ == "__main__":
    main()
