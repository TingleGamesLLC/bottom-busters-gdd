"""Cutting one painted object out whole, shrinking it to game size, and the object library. Spends nothing.
usage: python test_objects.py
"""
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

import objects

GREEN = (0, 255, 0)
PALETTE = np.array([(20, 18, 50), (120, 80, 170), (30, 170, 160), (240, 160, 60), (200, 190, 230)], float)


def mushroom(at=(512, 512), size=1024, dot=False):
    img = Image.new("RGB", (size, size), GREEN)
    d = ImageDraw.Draw(img)
    x, y = at
    d.rectangle([x - 40, y - 60, x + 40, y + 260], fill=(200, 190, 230), outline=(20, 18, 50), width=6)
    d.ellipse([x - 220, y - 220, x + 220, y + 20], fill=(30, 170, 160), outline=(20, 18, 50), width=8)
    if dot:
        d.ellipse([x - 12, y - 120, x + 12, y - 96], fill=GREEN)
    return img


def main():
    cut = objects.cut(mushroom())
    a = np.array(cut)
    alpha = a[..., 3] > 0
    assert cut is not None and not (objects.is_key(a[..., :3].astype(float)) & alpha).any()
    assert not (ndimage.binary_fill_holes(alpha) & ~alpha).any()
    print("A whole object is cut out with no green and no holes")

    assert objects.cut(mushroom(at=(512, 900))) is None
    print("An object cut off by the picture's edge is refused")

    dotted = np.array(objects.cut(mushroom(dot=True)))
    assert not (ndimage.binary_fill_holes(dotted[..., 3] > 0) & ~(dotted[..., 3] > 0)).any()
    print("A green speck painted inside an object is filled")

    small = np.array(objects.shrink(cut, 40, PALETTE))
    alpha = small[..., 3] > 0
    lab, n = ndimage.label(alpha)
    assert small.shape[0] == 40 and min(ndimage.sum(alpha, lab, range(1, n + 1))) >= 4
    assert not (objects.is_key(small[..., :3].astype(float)) & alpha).any()
    colors = {tuple(c) for c in small[..., :3][alpha]}
    assert colors <= {tuple(int(v) for v in p) for p in PALETTE}, colors
    print("Shrunk to 40 px: no loose specks, no green, every color from the palette")

    with tempfile.TemporaryDirectory() as tmp:
        lib = objects.Library(Path(tmp))
        path = lib.add("flat cartoon", "a teal mushroom", cut)
        assert lib.find("flat cartoon", "a teal mushroom") == path and lib.find("flat cartoon", "a red mushroom") is None
        lib.approve([path])
        assert lib.approved(path)
    print("The library finds an object by style and description, and records approval")
    import comfy
    import common
    real = comfy.paint
    comfy.paint = lambda prompt, seed, w, h: mushroom(at=(512, 900))
    try:
        objects.paint_whole("flat cartoon", "a teal mushroom", 1)
        raise AssertionError("an object cut off three times should stop")
    except common.CrewStop as e:
        assert "a teal mushroom" in str(e) and "3" in str(e), e
    finally:
        comfy.paint = real
    assert objects.object_prompt("flat cartoon", "a teal mushroom").startswith("flat cartoon")
    print("An object cut off on every try stops the background and names the object")
    print("all passed")


if __name__ == "__main__":
    main()
