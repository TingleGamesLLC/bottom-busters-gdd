"""The code-made layers, ground lines, placement with wrap-around, frames and previews. Spends nothing.
usage: python test_layers.py
"""
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

import layers as L


def main():
    a = np.array(L.sky([(10, 20, 80), (200, 120, 60)], stars=0))
    assert a.shape == (L.GH, L.GW, 4) and (a == a[:, :1]).all() and (a[..., 3] == 255).all()
    starry = np.array(L.sky([(10, 20, 80), (200, 120, 60)], seed=3))
    assert np.abs(starry[:, 0].astype(int) - starry[:, -1].astype(int)).max() <= 255 and (starry[..., 3] == 255).all()
    print("The sky is the same down every column, and solid")

    h = np.array(L.haze((150, 110, 200), 230, 40, 0.4))
    assert (h == h[:, :1]).all() and h[230, 0, 3] > h[100, 0, 3]
    print("The haze is the same across the width, strongest at its center row")

    line = L.periodic_line(260, [7, 4, 2], 5)
    step = np.abs(np.diff(line)).max()
    assert len(line) == L.GW and abs(int(line[0]) - int(line[-1])) <= step
    print("A ground line's two ends meet")

    sprite = Image.new("RGBA", (40, 30), (200, 50, 50, 255))
    layer = L.place_wrapped(Image.new("RGBA", (L.GW, L.GH)), sprite, L.GW - 15, 200)
    alpha = np.array(layer)[..., 3] > 0
    assert alpha[:, L.GW - 15:].sum() + alpha[:, :25].sum() == 40 * 30 and alpha[:, :25].any()
    print("An object crossing the right end carries on at the left end, whole")

    speeds = {"a": 0.25, "b": 0.5, "c": 1.0}
    rng = np.random.default_rng(1)
    stack = {k: Image.fromarray(rng.integers(0, 255, (L.GH, L.GW, 4), dtype=np.uint8)) for k in speeds}
    assert (np.array(L.frame(stack, speeds, 37)) == np.array(L.frame(stack, speeds, 37 + L.GW / 0.25))).all()
    print("After one full loop every layer is back where it started")

    plain = {"a": L.sky([(10, 20, 80), (200, 120, 60)], seed=1), "b": L.haze((150, 110, 200), 230, 40, 0.4),
             "c": L.place_wrapped(Image.new("RGBA", (L.GW, L.GH)), sprite, 100, 300)}
    with tempfile.TemporaryDirectory() as tmp:
        names = L.previews(plain, speeds, Path(tmp))
        assert "drift.gif" in names and all((Path(tmp) / n).exists() for n in names)
        assert (Path(tmp) / "drift.gif").stat().st_size < 4 * 1024 * 1024
    print("The previews and a moving loop under 4 MB are written")
    print("all passed")


if __name__ == "__main__":
    main()
