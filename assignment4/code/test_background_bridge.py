"""The Bridge's background checks and the Critic's note, on stand-in backgrounds built by layers.py. Spends nothing.
usage: python test_background_bridge.py
"""
import json
import shutil
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import bridge
import common
import critic
import layers as L

SPEEDS = [0.05, 0.3, 0.6, 1.0]


def stand_in(folder, seed=1, hue=(30, 170, 160), sky=((20, 18, 50), (240, 170, 70))):
    """A good background: sky, haze, and two object layers with whole objects standing on their ground."""
    folder.mkdir(parents=True)
    stack = [L.sky(list(sky), seed=seed), L.haze((130, 90, 180), 240, 40, 0.4)]
    placements = []
    for k, (ground_row, size) in enumerate(((270, 60), (305, 110))):
        layer = Image.new("RGBA", (L.GW, L.GH))
        line = L.periodic_line(ground_row, [3, 2], seed + k)
        for n in range(4):
            sprite = Image.new("RGBA", (size // 2, size))
            d = ImageDraw.Draw(sprite)
            d.ellipse([0, 0, size // 2 - 1, size // 2], fill=hue + (255,))
            d.rectangle([size // 6, size // 3, size // 3, size - 1], fill=(200, 190, 230, 255))
            x = n * L.GW // 4 + 20 * k + seed * 7
            base = int(line[x % L.GW]) + 6
            L.place_wrapped(layer, sprite, x, base)
            placements.append({"layer": f"{k + 2:02}.png", "x": x, "top": base - size, "width": size // 2, "height": size,
                               "lowest_row": base - 1, "ground_row": int(line[(x + size // 4) % L.GW])})
        stack.append(L.ground(layer, line, (40, 30, 80)))
    files = []
    for k, im in enumerate(stack):
        im.save(folder / f"{k:02}.png")
        files.append(f"{k:02}.png")
    (folder / "recipe.json").write_text(json.dumps({"layers": [{"speed": s} for s in SPEEDS]}), encoding="utf-8")
    names = L.previews({f: im for f, im in zip(files, stack)}, dict(zip(files, SPEEDS)), folder)
    (folder / "manifest.json").write_text(json.dumps({"kind": "background", "files": files, "previews": names,
                                                      "placements": placements}), encoding="utf-8")
    return folder


def broken(good, tmp, name, edit):
    bad = tmp / name
    shutil.copytree(good, bad)
    edit(bad)
    return bad


def paint(folder, layer, fn):
    a = np.array(Image.open(folder / layer).convert("RGBA"))
    fn(a)
    Image.fromarray(a).save(folder / layer)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        bridge.BACKGROUND_ROOTS = [tmp / "others"]
        stand_in(tmp / "others" / "earlier", seed=9, hue=(220, 80, 60), sky=((150, 210, 240), (250, 250, 220)))
        good = stand_in(tmp / "good")
        assert bridge.check_background(good) == [], bridge.check_background(good)
        print("A good stand-in background passes")

        def line(a):
            a[:, 200] = (10, 10, 10, 255)
        def green(a):
            a[300:305, 100:105] = (0, 255, 0, 255)
        first = [q for q in json.loads((good / "manifest.json").read_text())["placements"] if q["layer"] == "03.png"][0]

        def hole(a):
            y, x = first["top"] + first["height"] // 5, (first["x"] + first["width"] // 2) % L.GW
            assert a[y, x, 3] > 0
            a[y:y + 2, x:x + 2, 3] = 0
        def see_through(a):
            a[10, 10, 3] = 0
        cases = {
            "vertical line": broken(good, tmp, "line", lambda f: paint(f, "03.png", line)),
            "green": broken(good, tmp, "green", lambda f: paint(f, "03.png", green)),
            "hole": broken(good, tmp, "hole", lambda f: paint(f, "03.png", hole)),
            "sky": broken(good, tmp, "sky", lambda f: paint(f, "00.png", see_through)),
            "floating": broken(good, tmp, "floating", lambda f: (f / "manifest.json").write_text(json.dumps(dict(
                json.loads((f / "manifest.json").read_text()), placements=[{"layer": "03.png", "x": 50, "top": 100, "width": 40,
                "height": 100, "lowest_row": 199, "ground_row": 305}])), encoding="utf-8")),
        }
        for word, folder in cases.items():
            problems = bridge.check_background(folder)
            assert problems, f"{word} should fail"
            print(f"Caught ({word}): {problems[0]}")
        bridge.BACKGROUND_ROOTS = [tmp / "others", tmp / "twin"]
        shutil.copytree(good, tmp / "twin" / "copy")
        assert any("different" in p for p in bridge.check_background(good)), bridge.check_background(good)
        print("A copy of another background is caught")
        facts = bridge.background_facts(good)
        assert set(facts) >= {"nearest_background", "difference", "layers", "size_mb"} and facts["layers"] == 4

        real = common.ask
        common.ask = lambda agent, messages, model=None, max_tokens=None: '{"unfilled": false, "split": false, "floating": true, "specks": false}'
        try:
            note = critic.review_background(good, facts)
        finally:
            common.ask = real
        assert note["verdict"] == "fail" and note["answers"]["floating"] is True
        print("The Critic's four answers come back as a note, any yes a fail")
    print("all passed")


if __name__ == "__main__":
    main()
