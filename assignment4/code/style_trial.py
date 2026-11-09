"""[David's go] Does one style hold across separately painted objects? Four objects, one style sentence, one palette, side by
side, for David on the dashboard's Characters tab. Paints with ComfyUI on this PC (free).
usage: python style_trial.py
"""
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

import layers
import objects

OUT = Path(r"C:\cluster\submissions\backgrounds\style_trial")
STYLE = "16-bit pixel art game sprite with flat colors, a thick dark outline and two-tone shading"
PALETTE = np.array([(24, 18, 52), (60, 40, 110), (120, 80, 170), (190, 160, 225), (30, 170, 160), (240, 160, 60),
                    (250, 220, 140), (200, 90, 120)], float)
THINGS = ["a giant mushroom with a domed cap", "a twisted dead tree", "a small stone shrine", "a tall crystal spire"]


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    sprites = [objects.shrink(objects.paint_whole(STYLE, thing, 8800 + k * 101), 200, PALETTE) for k, thing in enumerate(THINGS)]
    gap = 16   # spaced by each object's own width, so none is cut at the edge or overlaps its neighbor
    sheet = Image.new("RGBA", (max(layers.GW, sum(s.width for s in sprites) + gap * (len(sprites) + 1)), layers.GH), (40, 40, 40, 255))
    x = gap
    for sprite in sprites:
        sheet.alpha_composite(sprite, (x, 300 - sprite.height))
        x += sprite.width + gap
    sheet.convert("RGB").save(OUT / "preview_1_side_by_side.png")
    (OUT / "manifest.json").write_text(json.dumps({"kind": "background", "agent": "Level Architect (style trial)",
        "name": f"STYLE TRIAL: four objects painted separately in one style ({STYLE})",
        "previews": ["preview_1_side_by_side.png"], "files": []}, indent=2), encoding="utf-8")
    print("done:", OUT)


if __name__ == "__main__":
    main()
