"""The Level Architect: the idea list, the recipe and its rules, and making a background. Spends nothing.
usage: python test_level_architect.py
"""
import json
import tempfile
from pathlib import Path

import common
import level_architect as la


def idea(theme, style="flat pixel art"):
    return {"theme": theme, "style": style}


def post(root, n, theme, decision=None, note=""):
    d = root / f"idea_{n:03}"
    d.mkdir(parents=True)
    (d / "manifest.json").write_text(json.dumps({"kind": "background idea", "theme": theme, "style": "s", "name": theme}), encoding="utf-8")
    if decision:
        (d / "decision.json").write_text(json.dumps({"decision": decision, "note": note}), encoding="utf-8")


def ideas_tests(tmp):
    scenes = tmp / "scenes"
    for name in ("forestB3", "moonB1", "sky2", "kitchen1", "parisC"):
        (scenes / name).mkdir(parents=True)
    la.SCENES, la.IDEAS = scenes, tmp / "ideas"
    la.BACKGROUNDS, la.APPROVED = tmp / "backgrounds", tmp / "approved"   # never the real ones: the first real background
    # (idea_001, run 20261107-164801) made the real folder count that idea as used
    places =["glass desert", "salt flats", "frozen lake", "coral reef", "lava fields", "whale graveyard", "paper city",
              "cloud harbor", "kite festival", "lantern bridge"]
    good = [idea(f"moon over the {p}" if k < 5 else f"sky above the {p}") for k, p in enumerate(places)]
    good += [idea("sunken jade temple"), idea("neon fungus caverns")]
    assert la.check_ideas(good) == [], la.check_ideas(good)
    assert any("forest at night" in p for p in la.check_ideas(good + [idea("forest at night")]))
    print("An idea that's just one of the 99 at another time of day is a repeat")
    assert any("twice" in p for p in la.check_ideas(good + [idea("sunken jade temple")]))
    print("Two ideas with one theme are a repeat")
    for first, again in [("floating tea party islands", "floating tea party islands in a gravity storm"),
                         ("floating tea party islands", "tea party islands in a thunderstorm"),
                         ("jellyfish abyss", "jellyfish abyss with sunken city ruins"),
                         ("solar flare desert", "solar flare canyon under twin moons"),
                         ("sky circus under a silver moon", "sky circus with floating trapeze"),
                         ("moonlit crater sky", "moonlit crater sky with drifting constellations")]:
        assert any(f"'{again}'" in p and "twice" in p for p in la.check_ideas([idea(first), idea(again)])), (first, again)
    print("The same place with new weather, a new sky or a new detail is a repeat")
    different = [idea("sky cathedral with moon spires"), idea("sky orchard with glowing moon fruits"),
                 idea("sky of drifting origami birds"), idea("sky of floating moon shards"), idea("neon jellyfish swamp"),
                 idea("jellyfish abyss"), idea("giant clockwork garden in bloom"), idea("mechanical orchard of ticking blossoms")]
    assert la.check_ideas(different) == [], la.check_ideas(different)
    print("Places that only share a word or two aren't repeats")
    few = [idea(f"rusty harbor of {p}") for p in places]
    assert any("moon or sky" in p for p in la.check_ideas(few, moon=10)) and la.check_ideas(few) == []
    assert la.check_ideas(good, moon=10) == []
    nine = good[:9] + [idea("rusty harbor of glass")]
    assert any("moon or sky" in p for p in la.check_ideas(nine, moon=10)) and la.check_ideas(nine, moon=10, spare=90) == []
    print("A batch asked for moon or sky ideas fails without them, unless the batches still to come can make up the rest")
    assert any("style" in p for p in la.check_ideas(good + [{"theme": "ice caves", "style": ""}]))
    print("Every idea needs a style")

    for k in range(95):
        post(la.IDEAS, k + 1, f"approved theme {k}", "approve")
    for k in range(3):
        post(la.IDEAS, 96 + k, f"waiting theme {k}")
    post(la.IDEAS, 99, "rejected theme", "reject")
    asked = []
    real = la.write_ideas

    def fake(count, moon=0, spare=0):
        asked.append((count, moon))
        return [idea(f"{'moon' if k < moon else 'new'} theme {len(asked)} {k}") for k in range(count)]
    la.write_ideas = fake
    try:
        assert la.top_up_ideas() == 2 and asked == [(2, 2)], asked
        print("Topping up posts only what it takes to reach 100 approved and waiting")
        empty = tmp / "empty_ideas"
        la.IDEAS, asked[:] = empty, []
        assert la.top_up_ideas() == 100 and asked == [(10, 10)] + [(10, 0)] * 9, asked
        assert len(list(empty.glob("idea_*/manifest.json"))) == 100
        print("An empty list is written 10 at a time, the moon and sky ideas first, each batch posted as it passes")
        la.IDEAS, asked[:] = tmp / "short_ideas", []

        def short(count, moon=0, spare=0):   # one moon idea short in the first batch
            asked.append((count, moon))
            return [idea(f"{'moon' if k < moon - (len(asked) == 1) else 'new'} theme {len(asked)} {k}") for k in range(count)]
        la.write_ideas = short
        assert la.top_up_ideas() == 100 and asked[:2] == [(10, 10), (10, 1)] and asked[2] == (10, 0), asked[:3]
        print("A batch one moon idea short passes, and the next batch is asked for the one still missing")
        la.write_ideas = fake
        la.IDEAS, asked[:] = tmp / "half_ideas", []

        def breaks(count, moon=0, spare=0):
            if len(asked) == 3:   # the fourth batch fails its checks twice
                raise common.MalformedOutput("the idea list failed its checks twice")
            return fake(count, moon)
        la.write_ideas = breaks
        try:
            la.top_up_ideas()
            raise AssertionError("a failed batch should stop the top-up")
        except common.MalformedOutput:
            pass
        assert len(list(la.IDEAS.glob("idea_*/manifest.json"))) == 30
        print("A batch that fails stops the top-up, and the batches before it stay posted")
    finally:
        la.write_ideas = real
        la.IDEAS = tmp / "ideas"

    real_ask = common.ask_json
    try:
        answer = {"ideas": [idea("approved theme 3 at noon"), idea("tin can volcano"), idea("ribbon glacier")]}
        common.ask_json = lambda agent, messages, required, **kw: json.loads(json.dumps(answer))
        kept = la.write_ideas(3, spare=50)
        assert [i["theme"] for i in kept] == ["tin can volcano", "ribbon glacier"], kept
        print("After two tries, a batch drops only its repeats and keeps the new ideas")
        answer = {"ideas": [idea("approved theme 3 at noon"), idea("approved theme 4")]}
        try:
            la.write_ideas(2, spare=50)
            raise AssertionError("a batch with nothing new should stop")
        except common.MalformedOutput:
            pass
        print("A batch with nothing new in it stops the top-up")
    finally:
        common.ask_json = real_ask

    first = la.next_idea()
    assert first["theme"] == "approved theme 0"
    common_used = la.IDEAS.parent / "backgrounds" / "used_one"
    common_used.mkdir(parents=True)
    (common_used / "manifest.json").write_text(json.dumps({"kind": "background", "idea": first["id"]}), encoding="utf-8")
    la.BACKGROUNDS = la.IDEAS.parent / "backgrounds"
    assert la.next_idea()["theme"] == "approved theme 1"
    print("The next idea is the lowest-numbered approved one not used yet")
    edited = la.IDEAS / "idea_002" / "decision.json"
    edited.write_text(json.dumps({"decision": "approve", "note": "a lighthouse on a giant turtle"}), encoding="utf-8")
    assert la.next_idea()["theme"] == "a lighthouse on a giant turtle"
    print("David's note on an approval replaces the idea's wording")


GOOD = {
    "theme": "lantern bridge over a sleeping river", "style": "flat pixel art, thick outline", "ground_type": "grass",
    "palette": [[20, 18, 50], [70, 50, 120], [130, 90, 180], [240, 170, 70], [250, 230, 170], [40, 120, 150]],
    "layers": [
        {"kind": "sky", "speed": 0.05, "rows": [[20, 18, 50], [70, 50, 120], [240, 170, 70]]},
        {"kind": "objects", "speed": 0.2, "ground_row": 260, "ground_color": [70, 50, 120],
         "objects": [{"description": "a far pagoda roof", "count": 4, "height": [40, 90]}]},
        {"kind": "haze", "speed": 0.3, "color": [130, 90, 180], "center_row": 240, "width_rows": 40, "strength": 0.4},
        {"kind": "objects", "speed": 0.6, "ground_row": 300, "ground_color": [20, 18, 50],
         "objects": [{"description": "a paper lantern on a post", "count": 6, "height": [60, 140]}]},
    ],
}


def broken(**change):
    r = json.loads(json.dumps(GOOD))
    for k, v in change.items():
        if k.startswith("layer") and k[5:6].isdigit():
            idx, field = k[5:].split("_", 1)
            r["layers"][int(idx)][field] = v
        else:
            r[k] = v
    return r


def recipe_tests(tmp):
    la.SCENES = tmp / "scenes"
    (la.SCENES / "forestB1").mkdir(parents=True)
    assert la.check_recipe(GOOD) == [], la.check_recipe(GOOD)
    print("A good recipe passes")
    cases = {
        "green": broken(palette=GOOD["palette"] + [[0, 255, 0]]),
        "forestB1": broken(theme="forestB1"),
        "sky first": broken(layers=GOOD["layers"][1:2] + GOOD["layers"][:1] + GOOD["layers"][2:]),
        "speed": broken(layer3_speed=0.1),
        "haze": broken(layers=GOOD["layers"] + [dict(GOOD["layers"][2])] * 2),
        "height": broken(layer1_objects=[{"description": "a tower", "count": 2, "height": [100, 300]}]),
    }
    for word, r in cases.items():
        problems = la.check_recipe(r)
        assert problems, f"{word} should fail"
        print(f"Caught: {problems[0]}")
    replies = [broken(palette=GOOD["palette"] + [[0, 255, 0]]), dict(GOOD, theme="whatever", style="whatever")]
    seen = []
    real = common.ask_json
    common.ask_json = lambda agent, messages, required, **kw: seen.append(messages) or json.loads(json.dumps(replies[len(seen) - 1]))
    try:
        r = la.recipe({"id": "idea_001", "theme": "lantern bridge over a sleeping river", "style": "flat pixel art, thick outline"}, None)
    finally:
        common.ask_json = real
    assert len(seen) == 2 and r["theme"] == "lantern bridge over a sleeping river" and r["style"] == "flat pixel art, thick outline"
    assert r["idea"] == "idea_001"
    print("A bad recipe gets one fix prompt, and the idea's theme and style are kept")
    assert '"kind": "sky"' in la.RECIPE_SYSTEM and '"kind": "objects"' in la.RECIPE_SYSTEM
    typed = json.loads(json.dumps(GOOD))
    for l in typed["layers"]:
        l["type"] = l.pop("kind")
    seen.clear()
    common.ask_json = lambda agent, messages, required, **kw: seen.append(messages) or json.loads(json.dumps(typed))
    try:
        r = la.recipe({"id": "idea_001", "theme": "lantern bridge over a sleeping river", "style": "flat"}, None)
    finally:
        common.ask_json = real
    assert len(seen) == 1 and [l["kind"] for l in r["layers"]] == [l["kind"] for l in GOOD["layers"]], r["layers"]
    print('The prompt names each layer\'s "kind", and a layer the model labels "type" is read as its kind (run 20261107-155047)')
    assert common.RUN_CAPS["level-architect"] == 30000


def make_tests(tmp):
    import bridge
    import comfy
    import objects
    from test_objects import mushroom
    la.IDEAS, la.BACKGROUNDS, la.APPROVED = tmp / "ideas", tmp / "backgrounds", tmp / "approved"
    la.SCENES = tmp / "scenes"
    la.SCENES.mkdir()
    bridge.BACKGROUND_ROOTS = [la.BACKGROUNDS, la.APPROVED]
    common.WORK = tmp / "work"
    objects.LIBRARY = tmp / "library"
    calls = []
    real = (common.ask_json, comfy.up, comfy.paint, comfy.start)
    common.ask_json = lambda agent, messages, required, **kw: calls.append(agent) or json.loads(json.dumps(GOOD))
    comfy.paint = lambda prompt, seed, w, h: mushroom()
    try:
        comfy.up = lambda: True
        try:
            la.make({"id": "t1", "brief": "x"}, None, [], None, 1)
            raise AssertionError("no approved idea should wait on David")
        except common.NeedsDavid:
            assert calls == []
        print("With no approved idea waiting, the card waits on David before any model call")
        post(la.IDEAS, 1, "lantern bridge over a sleeping river", "approve")
        # ComfyUI down: the Level Architect starts it. One that never answers stops the run before any recipe tokens.
        t, launches = [0], []
        fake = {"launch": lambda args, **kw: launches.append(args), "sleep": lambda s: t.__setitem__(0, t[0] + s),
                "clock": lambda: t[0]}
        answers = [False, False, True]
        comfy.up = lambda: answers.pop(0)
        assert comfy.start(wait=60, **fake) is True and len(launches) == 1 and launches[0][-2:] == ["launch", "--background"]
        comfy.up, t[0] = (lambda: True), 0
        assert comfy.start(**fake) is False and len(launches) == 1
        comfy.up = lambda: False
        try:
            comfy.start(wait=20, **fake)
            raise AssertionError("a ComfyUI that never answers should stop")
        except common.CrewStop as e:
            assert "didn't answer" in str(e) and len(launches) == 2
        print("comfy.start launches ComfyUI only when it's down, waits for it, and stops if it never answers")
        started = []

        def never_answers():
            started.append(1)
            raise common.CrewStop("ComfyUI was launched but didn't answer at http://127.0.0.1:8188 within 300 seconds")
        comfy.start = never_answers
        try:
            la.make({"id": "t1", "brief": "x"}, None, [], None, 1)
            raise AssertionError("ComfyUI that never answers should stop")
        except common.CrewStop as e:
            assert "ComfyUI" in str(e) and calls == [] and started == [1]
        print("test_starts_comfyui_when_down: started first; one that never answers stops before any recipe tokens")
        comfy.start = lambda: False
        comfy.up = lambda: True
        assert la.how_many() == 1
        folder, r = la.make({"id": "t1", "brief": "x"}, None, [], None, 1)
        assert bridge.check_background(folder) == [], bridge.check_background(folder)
        m = json.loads((folder / "manifest.json").read_text())
        assert m["kind"] == "background" and m["idea"] == "idea_001" and "drift.gif" in m["previews"]
        print("make builds a background that passes every Bridge check")
        published = la.publish(folder)
        assert published.parent == la.BACKGROUNDS and (published / "00.png").exists() and not folder.exists()
        post(la.IDEAS, 2, "glass moon harbor", "approve")
        assert la.how_many() == 1, la.how_many()
        for k in range(3, 14):
            post(la.IDEAS, k, f"theme number {k}", "approve")
        assert la.how_many() == 10, la.how_many()
        print("The first run makes one; after it, up to 10 per run, never more than the approved ideas waiting")
        (published / "decision.json").write_text(json.dumps({"decision": "approve"}), encoding="utf-8")
        assert la.store_approved() == [published.name] and (la.APPROVED / published.name / "00.png").exists()
        assert la.store_approved() == []
        print("An approved background is stored outside the game once, and skipped after that")
    finally:
        common.ask_json, comfy.up, comfy.paint, comfy.start = real
    for k in range(98):
        d = la.BACKGROUNDS / f"made_{k}"
        d.mkdir(parents=True)
        (d / "manifest.json").write_text(json.dumps({"kind": "background", "idea": f"idea_{900 + k}"}), encoding="utf-8")
    for k in range(20):
        post(la.IDEAS, 200 + k, f"spare theme {k}", "approve")
    assert la.how_many() == 1, la.how_many()
    print("test_count_stops_at_100: with 99 made, the next run makes 1")


def hole_tests():
    """BACKGROUNDS_METHOD.md rule 3: a small enclosed gap inside an object's box is filled with object color; a bigger one is
    real background showing through, and stays."""
    import numpy as np
    from PIL import Image
    a = np.zeros((324, 576, 4), np.uint8)
    a[200:300, 100:160] = (90, 70, 110, 255)   # an object standing on the ground
    a[300:, :] = (60, 40, 70, 255)             # the ground
    a[290:293, 120:124] = 0                    # 12 pixels at its foot, closed in by the ground: a hole
    a[220:240, 130:150] = 0                    # 400 pixels: a window the background shows through
    box = {"layer": "02.png", "x": 95, "top": 195, "width": 70, "height": 110}
    out = np.array(la.fill_holes(Image.fromarray(a, "RGBA"), [box]))
    assert (out[290:293, 120:124, 3] == 255).all() and (out[290:293, 120:124, :3] == (90, 70, 110)).all()
    assert (out[220:240, 130:150, 3] == 0).all()
    print("A gap of 12 pixels at an object's foot is filled with its color; a 400-pixel window stays see-through")
    wrapped = np.roll(a, 500, axis=1)
    out = np.array(la.fill_holes(Image.fromarray(wrapped, "RGBA"), [dict(box, x=(95 + 500) % 576)]))
    assert (np.roll(out, -500, axis=1)[290:293, 120:124, 3] == 255).all()
    print("An object that wraps across the layer's edge is filled the same way")


def main():
    hole_tests()
    with tempfile.TemporaryDirectory() as tmp:
        ideas_tests(Path(tmp))
    with tempfile.TemporaryDirectory() as tmp:
        make_tests(Path(tmp))
    with tempfile.TemporaryDirectory() as tmp:
        recipe_tests(Path(tmp))
    print("all passed")


if __name__ == "__main__":
    main()
