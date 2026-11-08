"""The parts of a background made by code, and how layers are stacked, moved and previewed.

One job per layer (DAVID, 2026-11-04; C:\\cluster\\crew\\BACKGROUNDS_METHOD.md). Color and haze layers are the same across
the width, so they loop by themselves; ground lines are whole sine waves over the width, and objects crossing an end are drawn
across the other end too, so every layer loops by construction, never by repair.
"""
import math
import random

import numpy as np
from PIL import Image, ImageDraw

GW, GH = 576, 324          # the game's layer size
GIF_STEP, GIF_MS = 8, 60    # the moving loop: every 8th position, 60 ms a frame


def sky(colors, seed=0, stars=45):
    """A vertical gradient through the given colors, top to bottom, and fixed small stars in the top 45%."""
    stops = np.array(colors, float)
    pos = np.linspace(0, GH - 1, len(stops))
    rows = np.stack([np.interp(np.arange(GH), pos, stops[:, c]) for c in range(3)], axis=1)
    img = np.repeat(rows[:, None, :], GW, axis=1).astype(np.uint8)
    rng = random.Random(seed)
    for _ in range(stars):
        x, y = rng.randrange(GW), rng.randrange(int(GH * 0.45))
        img[y, x] = (235, 230, 255)
    return Image.fromarray(np.dstack([img, np.full((GH, GW), 255, np.uint8)]), "RGBA")


def haze(color, center_row, width_rows, strength):
    """A see-through band of one color, strongest at center_row, the same across the width."""
    y = np.arange(GH)[:, None]
    alpha = strength * np.exp(-((y - center_row) / float(width_rows)) ** 2)
    img = np.zeros((GH, GW, 4), np.uint8)
    img[..., :3] = color
    img[..., 3] = np.broadcast_to((alpha * 255).astype(np.uint8), (GH, GW))
    return Image.fromarray(img, "RGBA")


def periodic_line(base, amps, seed):
    """A ground or hill line of whole sine waves over the width, so its two ends meet."""
    rng = random.Random(seed)
    x = np.arange(GW)
    y = np.full(GW, float(base))
    for k, a in enumerate(amps, start=1):
        y += a * np.sin(2 * math.pi * k * x / GW + rng.uniform(0, 2 * math.pi))
    return np.round(y).astype(int)


def ground(layer, line, color):
    """Solid ground below the line."""
    a = np.array(layer)
    for x in range(GW):
        a[max(0, line[x]):, x, :3] = color
        a[max(0, line[x]):, x, 3] = 255
    return Image.fromarray(a, "RGBA")


def place_wrapped(layer, sprite, x, base_y):
    """Stand the sprite on base_y with its left edge at x. Any part past an end is drawn across the other end."""
    top = base_y - sprite.height
    for dx in (-GW, 0, GW):
        left = x + dx
        if left + sprite.width <= 0 or left >= GW:
            continue
        canvas = Image.new("RGBA", (GW, GH))
        canvas.paste(sprite, (left, top), sprite)
        layer.alpha_composite(canvas)
    return layer


def frame(layers, speeds, t):
    """The stack at time t, each layer moved left by its speed times t and wrapped."""
    out = Image.new("RGBA", (GW, GH))
    for name, im in layers.items():
        shift = int(round(t * speeds[name])) % GW
        out.alpha_composite(Image.fromarray(np.roll(np.array(im.convert("RGBA")), -shift, axis=1)))
    return out.convert("RGB")


def checker(size, cell=12):
    bg = Image.new("RGB", size, (200, 200, 200))
    d = ImageDraw.Draw(bg)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if (x // cell + y // cell) % 2:
                d.rectangle([x, y, x + cell - 1, y + cell - 1], fill=(235, 235, 235))
    return bg


def previews(layers, speeds, out_dir):
    """The pictures David reviews: the whole, each layer on a checkerboard, the loop point, four moments of drift, and the
    moving loop. Returns their file names."""
    names = []
    frame(layers, speeds, 0).save(out_dir / "preview_1_whole.png"); names.append("preview_1_whole.png")
    cols = 3
    rows = (len(layers) + cols - 1) // cols
    sheet = Image.new("RGB", (GW * cols + 8 * (cols - 1), GH * rows + 8 * (rows - 1)), (40, 40, 40))
    for k, im in enumerate(layers.values()):
        tile = checker((GW, GH))
        tile.paste(im, (0, 0), im.convert("RGBA"))
        sheet.paste(tile, ((k % cols) * (GW + 8), (k // cols) * (GH + 8)))
    sheet.save(out_dir / "preview_2_layers.png"); names.append("preview_2_layers.png")
    whole = frame(layers, speeds, 0)
    loop = Image.new("RGB", (GW * 2, GH))
    loop.paste(whole, (0, 0)); loop.paste(whole, (GW, 0))
    loop.save(out_dir / "preview_3_loop_check.png"); names.append("preview_3_loop_check.png")
    fastest = max(speeds.values())
    for k in range(4):
        frame(layers, speeds, (k + 1) * GW / 5 / fastest).save(out_dir / f"preview_4_drift_{k + 1}.png")
        names.append(f"preview_4_drift_{k + 1}.png")
    gif = [frame(layers, speeds, t / fastest) for t in range(0, GW, GIF_STEP)]
    gif[0].save(out_dir / "drift.gif", save_all=True, append_images=gif[1:], duration=GIF_MS, loop=0)
    names.append("drift.gif")
    return names
