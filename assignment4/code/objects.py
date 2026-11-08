"""One painted object at a time: cut out whole, shrunk to game size on the background's palette, and kept in a library.

ComfyUI paints each object alone on chroma green, which no recipe's palette may use (method rules 2 and 8), so the cut is by
that green only. An object touching the picture's edge was cut off by the painting and is refused (rule 1: objects whole).
"""
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

LIBRARY = Path(r"C:\cluster\crew\library")
MIN_PIXELS = 3000


def is_key(rgb):
    """Chroma green: hue 80 to 155 degrees, saturation over 0.35, value over 0.3."""
    hsv = np.array(Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).convert("HSV")).astype(float)
    hue, sat, val = hsv[..., 0] * 360 / 255, hsv[..., 1] / 255, hsv[..., 2] / 255
    return (hue >= 80) & (hue <= 155) & (sat > 0.35) & (val > 0.3)


def cut(img):
    """The one object, whole: its biggest non-green piece, holes inside it filled, the green tint on its outline gone, cropped.
    None when it touches the picture's edge or is too small to use."""
    rgb = np.array(img.convert("RGB")).astype(float)
    obj = ~is_key(rgb)
    lab, n = ndimage.label(obj)
    if not n:
        return None
    sizes = ndimage.sum(obj, lab, range(1, n + 1))
    obj = ndimage.binary_fill_holes(lab == int(np.argmax(sizes)) + 1)
    tint = rgb[..., 1] - np.maximum(rgb[..., 0], rgb[..., 2])
    outline = obj & ~ndimage.binary_erosion(obj, iterations=2)
    obj = ndimage.binary_fill_holes(obj & ~(outline & (tint > 30)))
    ys, xs = np.nonzero(obj)
    h, w = obj.shape
    if len(ys) < MIN_PIXELS or ys.min() <= 2 or xs.min() <= 2 or ys.max() >= h - 3 or xs.max() >= w - 3:
        return None
    idx = ndimage.distance_transform_edt(~obj, return_distances=False, return_indices=True)
    filled = rgb[idx[0], idx[1]]            # no green under the edges when it's shrunk
    rgba = np.dstack([filled.astype(np.uint8), np.where(obj, 255, 0).astype(np.uint8)])
    return Image.fromarray(rgba, "RGBA").crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))


def to_palette(rgb, palette):
    flat = rgb.reshape(-1, 3).astype(float)
    w = np.array([0.30, 0.59, 0.11]) ** 0.5
    d = (((flat[:, None, :] - palette[None, :, :]) * w) ** 2).sum(-1)
    return palette[d.argmin(1)].reshape(rgb.shape).astype(np.uint8)


def shrink(obj, height, palette):
    """To game size with a hard edge: pinholes inside the outline filled, specks and green tint on the outline removed, pieces
    under 4 pixels dropped, every color mapped onto the background's palette."""
    w = max(1, round(obj.width * height / obj.height))
    a = np.array(obj.resize((w, height), Image.LANCZOS))
    alpha = ndimage.binary_fill_holes(a[..., 3] >= 128)
    rgb = a[..., :3].astype(float)
    outline = alpha & ~ndimage.binary_erosion(alpha)
    lum = rgb @ np.array([0.30, 0.59, 0.11])
    sat = (rgb.max(-1) - rgb.min(-1)) / np.maximum(rgb.max(-1), 1)
    tint = rgb[..., 1] - np.maximum(rgb[..., 0], rgb[..., 2])
    alpha &= ~(outline & ((tint > 12) | ((lum > 190) & (sat < 0.3))))
    lab, n = ndimage.label(alpha)
    if n:
        sizes = ndimage.sum(alpha, lab, range(1, n + 1))
        alpha = np.isin(lab, [k + 1 for k in range(n) if sizes[k] >= 4])
    rgb = to_palette(rgb, np.asarray(palette, float))
    return Image.fromarray(np.dstack([rgb, np.where(alpha, 255, 0).astype(np.uint8)]), "RGBA")


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


class Library:
    """Every object that passed its cut-out: <root>/<id>.png and <id>.json (style, description, approved)."""

    def __init__(self, root=LIBRARY):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _meta(self, path):
        return json.loads(Path(path).with_suffix(".json").read_text(encoding="utf-8"))

    def find(self, style, description):
        for meta in sorted(self.root.glob("*.json")):
            m = json.loads(meta.read_text(encoding="utf-8"))
            if m["style"] == style and m["description"] == description:
                return meta.with_suffix(".png")
        return None

    def add(self, style, description, img):
        base = f"{_slug(style)}--{_slug(description)}"
        n, path = 1, self.root / f"{base}.png"
        while path.exists():
            n += 1
            path = self.root / f"{base}-{n}.png"
        img.save(path)
        path.with_suffix(".json").write_text(json.dumps({"style": style, "description": description, "approved": False}, indent=1),
                                             encoding="utf-8")
        return path

    def approve(self, paths):
        for p in paths:
            m = self._meta(p)
            m["approved"] = True
            Path(p).with_suffix(".json").write_text(json.dumps(m, indent=1), encoding="utf-8")

    def approved(self, path):
        return bool(self._meta(path).get("approved"))


ISOLATED = ("the whole object in frame and centered, isolated on a flat solid bright chroma green background (pure #00FF00), "
            "no ground, no grass, no shadow, no other objects, no text")


def object_prompt(style, description):
    """The recipe's style first, so every object in one background is painted the same way, then the object, then isolation."""
    return f"{style}. {description}. {ISOLATED}."


def paint_whole(style, description, seed, tries=3):
    """Paint one object until it comes out whole. Every try is a new seed."""
    import comfy
    from common import CrewStop
    for k in range(tries):
        got = cut(comfy.paint(object_prompt(style, description), seed + k * 13, 1024, 1024))
        if got is not None:
            return got
    raise CrewStop(f"{description} came out cut off or too small {tries} times")
