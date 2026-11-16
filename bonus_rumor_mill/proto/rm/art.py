"""Pixel art for the terminal.

Every picture is a grid of colors drawn with half-block characters, so one
terminal cell shows two stacked pixels. Portraits are hand-drawn once and
share one set of face stamps (talking, shocked, smug, lying, busted, crying),
the same idea as the GDD's six face textures.
"""
from __future__ import annotations

import math
import random

from rich.style import Style
from rich.text import Text

# ---------------------------------------------------------------- palette
PAL = {
    "k": "#2B1B2E",  # outline
    "s": "#F2C29B",  # skin
    "S": "#D49A72",  # skin shadow
    "w": "#FFF8F5",  # white
    "W": "#DCD3DD",  # light gray
    "n": "#1C1222",  # eyes, darkest
    "r": "#E0464E",  # red
    "R": "#A42F3A",  # dark red
    "h": "#7A4A2A",  # brown
    "H": "#4E2C17",  # dark brown
    "p": "#FF7AA8",  # pink
    "P": "#D9488A",  # deep pink
    "m": "#F2A541",  # amber
    "M": "#B8741C",  # dark amber
    "v": "#B99CEB",  # lavender
    "V": "#8466C2",  # deep lavender
    "c": "#6FE3B8",  # mint
    "C": "#3FA88A",  # teal
    "b": "#5B8DEF",  # blue
    "B": "#2F4C8F",  # navy
    "g": "#9AA0AE",  # gray
    "G": "#5A6072",  # slate
    "y": "#FFD24A",  # gold
    "Y": "#C99A1E",  # dark gold
    "o": "#E8489E",  # boa magenta
    "O": "#B02C7A",  # boa shade
    "l": "#2A2440",  # sunglasses lens
    "L": "#6A5F9A",  # lens shine
    "q": "#8FD3FF",  # tears, sweat
    "e": "#F59A9A",  # blush
}

# Interface colors
UI = {
    "bg": "#221A33",        # night blue
    "panel": "#2D2443",
    "panel2": "#3A2F55",
    "ink": "#F7E9F1",       # off-white
    "dim": "#A99BBF",
    "rumor": "#FF7AA8",     # pink: rumors, lies
    "heat": "#F2A541",      # amber: time, heat
    "truth": "#6FE3B8",     # mint: truth, evidence
    "player": "#7CC8FF",    # sky blue: you
    "danger": "#FF5A5F",
    "paper": "#EFE6DA",
    "paper_ink": "#2B2230",
}

def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

def rgb_hex(c) -> str:
    return "#%02X%02X%02X" % tuple(max(0, min(255, int(round(v)))) for v in c)

def mix(a: str, b: str, t: float) -> str:
    ca, cb = hex_rgb(a), hex_rgb(b)
    return rgb_hex([ca[i] + (cb[i] - ca[i]) * t for i in range(3)])

# ---------------------------------------------------------------- canvas
class Canvas:
    """A pixel grid. None means transparent."""

    def __init__(self, w: int, h: int, fill: str | None = None):
        self.w, self.h = w, h + (h % 2)
        self.px: list[list[str | None]] = [[fill] * self.w for _ in range(self.h)]

    def set(self, x: int, y: int, c: str | None):
        if 0 <= x < self.w and 0 <= y < self.h and c is not None:
            self.px[y][x] = c

    def get(self, x: int, y: int):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.px[y][x]
        return None

    def rect(self, x, y, w, h, c):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.set(xx, yy, c)

    def blend(self, x, y, c, a):
        cur = self.get(x, y)
        if cur is None:
            return
        self.set(x, y, mix(cur, c, a))

    def blit(self, other: "Canvas", ox: int, oy: int, scale: int = 1):
        for y in range(other.h):
            for x in range(other.w):
                c = other.px[y][x]
                if c is None:
                    continue
                for dy in range(scale):
                    for dx in range(scale):
                        self.set(ox + x * scale + dx, oy + y * scale + dy, c)

    def to_text(self, bg: str = UI["bg"]) -> Text:
        """Two pixel rows per text row, using the upper half block."""
        text = Text(no_wrap=True, overflow="crop")
        cache: dict = {}
        for y in range(0, self.h, 2):
            run_style, run_len = None, 0
            for x in range(self.w):
                top = self.px[y][x] or bg
                bot = self.px[y + 1][x] or bg
                key = (top, bot)
                st = cache.get(key)
                if st is None:
                    st = cache[key] = Style(color=top, bgcolor=bot)
                if st is run_style:
                    run_len += 1
                else:
                    if run_style is not None:
                        text.append("▀" * run_len, run_style)
                    run_style, run_len = st, 1
            if run_style is not None:
                text.append("▀" * run_len, run_style)
            if y + 2 < self.h:
                text.append("\n")
        return text


# ---------------------------------------------------------------- portraits
# Each portrait is 22 x 26 pixels. Rows are written as LEFT halves (11 px)
# and mirrored, then a few asymmetric pixels are overridden. All five share
# one head shape, so one set of face stamps fits everyone:
#   eyes: (8,9)-(8,10) and (13,9)-(13,10); brows row 8; mouth x9..12, rows 13-14.

HEAD = {
    7:  ".....kkkkkk",
    8:  ".....ksssss",
    9:  "....kssssss",
    10: "....kssssss",
    11: "....ksssssS",
    12: ".....ksssss",
    13: ".....ksssss",
    14: ".....ksssss",
    15: "......kssss",
    16: ".......kkkk",
    17: ".......kSSS",
}

def _mirror(half: str) -> str:
    return half + half[::-1]

def _build(rows: dict[int, str], overrides: list[tuple[int, int, str]] = ()) -> list[str]:
    grid = []
    for y in range(26):
        half = rows.get(y, HEAD.get(y, "..........."))
        assert len(half) == 11, (y, half, len(half))
        grid.append(list(_mirror(half)))
    for x, y, c in overrides:
        grid[y][x] = c
    return ["".join(r) for r in grid]

SPRITES: dict[str, list[str]] = {}

# Gary Gusto, the Exaggerator: tall striped hat, handlebar mustache, barrel chest.
SPRITES["gary"] = _build({
    0:  "........kkk",
    1:  ".......krwr",
    2:  ".......krwr",
    3:  ".......krwr",
    4:  ".......krwr",
    5:  ".......kRRR",
    6:  "....kkkkkkk",
    7:  ".....kHHHHH",
    10: ".h..kssssss",
    11: "..h.ksssssS",
    12: "..hhhhhhhhh",
    18: "....kkkwwrr",
    19: "..kkwwwwBrr",
    20: ".kwwwwwwBww",
    21: "kwwwwwwwBww",
    22: "kwwwwwwwBww",
    23: "kwwwwwwwBww",
    24: "kwwwwwwwBww",
    25: "kwwwwwwwBww",
}, [(10, 12, "H"), (11, 12, "H"), (1, 9, "h"), (20, 9, "h")])

# Toby Crumb, the Salesman: paper hat, apron dusted white, huge grin.
SPRITES["toby"] = _build({
    1:  ".....kkkkkk",
    2:  "....kwwwwww",
    3:  "...kwwwWwww",
    4:  "...kwwwwwww",
    5:  "....kwwwwwW",
    6:  ".....kWWWWW",
    7:  ".....kkkkkk",
    8:  ".....kHssss",
    18: "...kkkkmmww",
    19: "..kmmmmmwww",
    20: ".kmmmmmwwww",
    21: ".kmmmmmwwww",
    22: "kmmmmmmwwww",
    23: "kmmmmmmwwww",
    24: "kmmmmmwwwww",
    25: "kmmmmmwwwww",
}, [
    # white dust on the apron
    (14, 21, "W"), (12, 23, "W"), (15, 24, "W"), (13, 19, "W"),
    (16, 8, "H"),
])

# Mildred Ashby, the Busybody: curlers, bathrobe, binoculars.
SPRITES["mildred"] = _build({
    4:  "......kgggg",
    5:  ".....kgggWg",
    6:  "....kgWgggg",
    7:  "....kgggggW",
    8:  "....kgsssss",
    9:  "....kgsssss",
    18: "...kkvvvvSS",
    19: "..kvvvvvvvS",
    20: ".kvvvvvvvvv",
    21: ".kvvvvvkGGk",
    22: "kvvvvvkGnGG",
    23: "kvVvvvkGGkV",
    24: "kvVvvvvkkVv",
    25: "kvVvvvvvVvv",
}, [
    # three fat curlers across the top: mint, pink, mint
    (4, 3, "k"), (5, 3, "c"), (6, 3, "c"), (7, 3, "c"), (8, 3, "k"),
    (4, 4, "k"), (5, 4, "C"), (6, 4, "C"), (7, 4, "C"), (8, 4, "k"),
    (9, 2, "k"), (10, 2, "p"), (11, 2, "p"), (12, 2, "k"),
    (9, 3, "k"), (10, 3, "P"), (11, 3, "P"), (12, 3, "k"),
    (13, 3, "k"), (14, 3, "c"), (15, 3, "c"), (16, 3, "c"), (17, 3, "k"),
    (13, 4, "k"), (14, 4, "C"), (15, 4, "C"), (16, 4, "C"), (17, 4, "k"),
])

# Bev Fairweather, the Drama Queen: enormous sun hat, giant sunglasses, boa.
SPRITES["bev"] = _build({
    1:  "........kkk",
    2:  "......kkyyy",
    3:  ".....kyyyyy",
    4:  ".....kyyYyy",
    5:  ".....kppppp",
    6:  ".kkkkyyyyyy",
    7:  "kyyyyyyyyyy",
    8:  ".kkkkksssss",
    17: "......oOSSS",
    18: "...koooOoPP",
    19: "..kOoooooPP",
    20: ".kPPOooOPPP",
    21: ".kPPPPPPPPP",
    22: "kPPPPPPPPPP",
    23: "kPPPPPPPPPP",
    24: "kPPPPPPPPPP",
    25: "kPPPPPPPPPP",
}, [(4, 12, "e"), (17, 12, "e")])

BEV_GLASSES = [  # drawn over the eyes after the face stamp
    (5, 9, "k"), (6, 9, "l"), (7, 9, "L"), (8, 9, "l"), (9, 9, "l"), (10, 9, "k"),
    (11, 9, "k"), (12, 9, "l"), (13, 9, "L"), (14, 9, "l"), (15, 9, "l"), (16, 9, "k"),
    (6, 10, "k"), (7, 10, "l"), (8, 10, "l"), (9, 10, "k"),
    (12, 10, "k"), (13, 10, "l"), (14, 10, "l"), (15, 10, "k"),
]

# Ozzie Fink, the Liar: slicked hair, pencil mustache, pinstripes, a deck of cards.
SPRITES["ozzie"] = _build({
    5:  "......kkkkk",
    6:  ".....knnnnn",
    7:  "....knnnGnn",
    8:  "....knsssss",
    12: ".....ksssnn",
    18: "...kkkkGGwr",
    19: "..kGgGgGGwr",
    20: ".kGgGgGgGwr",
    21: ".kGgGgGgGGr",
    22: "kGgGgGgGgGG",
    23: "kGgGgGgGgGG",
    24: "kGgGgGgGgGG",
    25: "kGgGgGgGgGG",
}, [
    (12, 7, "G"),
    # a fanned deck of cards, lower right
    (16, 21, "k"), (17, 21, "k"), (18, 21, "k"),
    (15, 22, "k"), (16, 22, "w"), (17, 22, "w"), (18, 22, "w"), (19, 22, "k"),
    (15, 23, "k"), (16, 23, "w"), (17, 23, "r"), (18, 23, "w"), (19, 23, "k"),
    (15, 24, "k"), (16, 24, "w"), (17, 24, "w"), (18, 24, "w"), (19, 24, "k"),
    (14, 24, "s"), (14, 25, "s"), (13, 25, "s"),
])

# ---------------------------------------------------------------- faces
FACES = ["talking", "shocked", "smug", "lying", "busted", "crying"]

EYES = [(8, 9), (13, 9)]
MOUTH = (9, 13)

MOUTHS = {
    "talk_open":  ["nnnn", ".RR."],
    "talk_shut":  [".nn.", "...."],
    "shocked":    [".nn.", ".nn."],
    "smug":       ["...n", "nnn."],
    "lying":      [".n.n", "n.n."],
    "busted":     ["wwww", "nnnn"],
    "crying":     [".nn.", "n..n"],
    "rest":       ["....", ".nn."],
}

def stamp_face(grid: list[list[str]], face: str, mouth_open: bool = True, blink: bool = False):
    def put(x, y, c):
        if c != ".":
            grid[y][x] = c

    (lx, ey), (rx, _) = EYES
    if blink or face == "crying":
        for ex in (lx, rx):
            put(ex, ey + 1, "n")
    elif face == "shocked" or face == "busted":
        for ex in (lx, rx):
            put(ex, ey, "w"); put(ex, ey + 1, "n")
            put(ex - 1, ey - 1, "H"); put(ex, ey - 2 if ey >= 2 else ey - 1, ".")
        put(lx - 1, ey - 1, "H"); put(rx + 1, ey - 1, "H")
    elif face == "smug":
        for ex in (lx, rx):
            put(ex, ey, "S"); put(ex, ey + 1, "n")
        put(lx - 1, ey - 1, "H"); put(lx, ey - 1, "H")
        put(rx, ey - 1, "H"); put(rx + 1, ey - 1, "H")
    elif face == "lying":
        for ex in (lx, rx):
            put(ex, ey, "w"); put(ex, ey + 1, "w")
            put(ex + 1, ey, "n"); put(ex + 1, ey + 1, "n")
    else:  # talking, rest
        for ex in (lx, rx):
            put(ex, ey, "n"); put(ex, ey + 1, "n")

    if face in ("lying", "busted"):
        put(rx + 3, ey - 1, "q"); put(rx + 3, ey, "q")
    if face == "busted":
        put(lx - 3, ey, "q")
    if face == "crying":
        for ex in (lx, rx):
            put(ex, ey + 2, "q"); put(ex, ey + 3, "q")

    if face == "talking":
        key = "talk_open" if mouth_open else "talk_shut"
    elif face in MOUTHS:
        key = face
    else:
        key = "rest"
    mx, my = MOUTH
    for dy, row in enumerate(MOUTHS[key]):
        for dx, c in enumerate(row):
            put(mx + dx, my + dy, c)


def portrait(name: str, face: str = "rest", mouth_open: bool = True, blink: bool = False,
             spotlight: str | None = None, pad: int = 4) -> Canvas:
    """A portrait with a soft spotlight behind the character."""
    rows = [list(r) for r in SPRITES[name]]
    stamp_face(rows, face, mouth_open, blink)
    if name == "bev":
        for x, y, c in BEV_GLASSES:
            rows[y][x] = c
    w, h = 22 + pad * 2, 26 + pad
    cv = Canvas(w, h)
    if spotlight:
        cx, cy = w / 2, h * 0.55
        r = w * 0.55
        for y in range(cv.h):
            for x in range(w):
                d = math.hypot((x - cx) / r, (y - cy) / (r * 1.05))
                t = max(0.0, min(1.0, 1.0 - d))
                cv.px[y][x] = mix(UI["panel"], spotlight, 0.55 * t * t)
    for y, row in enumerate(rows):
        for x, c in enumerate(row):
            if c != ".":
                cv.set(x + pad, y + pad, PAL[c])
    return cv


# ---------------------------------------------------------------- small icons
ICONS = {
    "custard_pie": [
        "........",
        "..wwww..",
        ".wwwwww.",
        "yyyyyyyy",
        "mMmMmMmM",
        ".MMMMMM.",
        "........",
        "........",
    ],
    "fish": [
        "........",
        "...bbb..",
        "bbbbbbb.",
        ".bnbbbbb",
        "bbbbbbb.",
        "...bbb..",
        "........",
        "........",
    ],
    "rubber_chicken": [
        "..rr....",
        ".yyyy...",
        ".ynyym..",
        "..yyyy..",
        "..yyyyy.",
        "...yyy..",
        "...m.m..",
        "........",
    ],
    "receipt": [
        ".wwwwww.",
        ".wnnnnw.",
        ".wwwwww.",
        ".wnnnww.",
        ".wwwwww.",
        ".wnnwnw.",
        ".wwwwww.",
        ".w.w.w..",
    ],
    "ticket_stub": [
        "........",
        "rrrrrrrr",
        "rwnnwnwr",
        "rwwwwwwr",
        "rwnwnnwr",
        "rrrrrrrr",
        "........",
        "........",
    ],
    "note": [
        "yyyyyyy.",
        "ywwwwwy.",
        "ynnnnwy.",
        "ywwwwwy.",
        "ynnnwwy.",
        "ywwwwwy.",
        "yyyyyyy.",
        "........",
    ],
    "liars_hat": [
        "..pppp..",
        "..wwww..",
        "..pppp..",
        "..wwww..",
        "..pppp..",
        "pppppppp",
        "........",
        "........",
    ],
    "bucket_of_water": [
        "........",
        ".gggggg.",
        ".gqqqqg.",
        ".gggggg.",
        ".gggggg.",
        "..gggg..",
        "..GGGG..",
        "........",
    ],
    "megaphone": [
        "......y.",
        "....yyy.",
        "..yyyyy.",
        "nnyyyyy.",
        "..yyyyy.",
        "....yyy.",
        "......y.",
        "........",
    ],
    "baguette": [
        "......mm",
        ".....mMm",
        "....mMm.",
        "...mMm..",
        "..mMm...",
        ".mMm....",
        "mmm.....",
        "........",
    ],
    # giant props for the shop's roof
    "teapot": [
        "...yy...",
        "..bbbb..",
        ".bbbbbbb",
        "bbbbbbbb",
        "bbbbbbb.",
        "bbbbbbb.",
        ".BBBBB..",
        "........",
    ],
    "boot": [
        "..hhh...",
        "..hhh...",
        "..hhh...",
        "..hhh...",
        "..hhhhh.",
        ".hhhhhhh",
        ".HHHHHHH",
        "........",
    ],
    "key": [
        ".yyy....",
        "y...y...",
        "y...yyyy",
        "y...y.y.",
        ".yyy..y.",
        "........",
        "........",
        "........",
    ],
    "cheese": [
        "........",
        "......yy",
        "....yyyy",
        "..yyYyyy",
        "yyyyyyYy",
        "yYyyyyyy",
        "YYYYYYYY",
        "........",
    ],
    "anvil": [
        "........",
        "GGGGGGG.",
        ".GGGGGGG",
        "...GGG..",
        "...GGG..",
        "..GGGGG.",
        ".ggggggg",
        "........",
    ],
    "scissors": [
        "g.....g.",
        ".g...g..",
        "..g.g...",
        "...g....",
        "..r.r...",
        ".r...r..",
        ".r...r..",
        "..r.r...",
    ],
    "clock": [
        "..kkkk..",
        ".kwwwwk.",
        "kwwnwwwk",
        "kwwnwwwk",
        "kwwnnnwk",
        "kwwwwwwk",
        ".kwwwwk.",
        "..kkkk..",
    ],
    "top_hat": [
        "..nnnn..",
        "..nnnn..",
        "..nnnn..",
        "..rrrr..",
        "..nnnn..",
        "nnnnnnnn",
        "........",
        "........",
    ],
    "candle": [
        "...y....",
        "..yYy...",
        "...k....",
        "..www...",
        "..www...",
        "..wWw...",
        "..www...",
        ".WWWWW..",
    ],
    "book": [
        "........",
        ".rrrrrr.",
        ".rwwwwr.",
        ".rrrrrr.",
        ".rrrrrr.",
        ".rRRRRr.",
        ".rrrrrr.",
        "........",
    ],
    "bell": [
        "...y....",
        "..yyy...",
        ".yyyyy..",
        ".yyyyy..",
        ".yyyyy..",
        "yyyyyyy.",
        "...Y....",
        "........",
    ],
    # a speech bubble for the title screen ("w" is swapped for a cast color)
    "bubble": [
        ".wwwwww.",
        "wwwwwwww",
        "wnwnwnww",
        "wwwwwwww",
        ".wwwwww.",
        "..ww....",
        ".w......",
        "........",
    ],
}

def icon(name: str, recolor: dict | None = None) -> Canvas | None:
    rows = ICONS.get(name)
    if not rows:
        return None
    cv = Canvas(8, 8)
    for y, row in enumerate(rows):
        for x, c in enumerate(row):
            if c != ".":
                cv.set(x, y, (recolor or {}).get(c) or PAL[c])
    return cv


# ---------------------------------------------------------------- pixel font
FONT = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01110", "10001", "10000", "10000", "10000", "10001", "01110"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01110", "10001", "10000", "10111", "10001", "10001", "01111"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "J": ["00111", "00010", "00010", "00010", "10010", "10010", "01100"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "10101", "01010"],
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
    "!": ["00100", "00100", "00100", "00100", "00100", "00000", "00100"],
    "?": ["01110", "10001", "00001", "00110", "00100", "00000", "00100"],
    ".": ["00000", "00000", "00000", "00000", "00000", "00000", "00100"],
    "'": ["00100", "00100", "01000", "00000", "00000", "00000", "00000"],
    ",": ["00000", "00000", "00000", "00000", "00000", "00100", "01000"],
    "-": ["00000", "00000", "00000", "01110", "00000", "00000", "00000"],
    ":": ["00000", "00100", "00000", "00000", "00000", "00100", "00000"],
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00110", "01000", "10000", "11111"],
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "4": ["10010", "10010", "10010", "11111", "00010", "00010", "00010"],
    "5": ["11111", "10000", "11110", "00001", "00001", "10001", "01110"],
    "6": ["01110", "10000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00001", "01110"],
    " ": ["000", "000", "000", "000", "000", "000", "000"],
}

def word_canvas(text: str, top: str, bottom: str, scale: int = 1, shadow: str | None = None) -> Canvas:
    """Pixel-font text with a vertical gradient."""
    text = text.upper()
    glyphs = [FONT.get(ch, FONT["?"]) for ch in text]
    width = sum(len(g[0]) + 1 for g in glyphs) - 1
    sh = scale if shadow else 0
    cv = Canvas(width * scale + sh + 1, 7 * scale + sh)
    x0 = 0
    for g in glyphs:
        gw = len(g[0])
        for gy, row in enumerate(g):
            for gx, bit in enumerate(row):
                if bit != "1":
                    continue
                col = mix(top, bottom, gy / 6)
                bw = scale + (1 if scale > 1 else 0)  # faux bold
                for dy in range(scale):
                    for dx in range(bw):
                        if shadow:
                            cv.set((x0 + gx) * scale + dx + sh, gy * scale + dy + sh, shadow)
                for dy in range(scale):
                    for dx in range(bw):
                        cv.set((x0 + gx) * scale + dx, gy * scale + dy, col)
        x0 += gw + 1
    return cv


# ---------------------------------------------------------------- the town
# The building kit, left to right on the street (cast.KIT_ORDER).
KIT_ORDER = ["shop", "house", "dock_shed", "theater", "tavern"]

def town(w: int, h: int, t: float, night: bool = False, heat: float = 0.0,
         selected: int | None = None, posters: int = 0, guard: bool = False, roof_prop: str | None = None) -> Canvas:
    """The diorama street. t is time in seconds, for twinkles and water."""
    cv = Canvas(w, h)
    h = cv.h
    ground_y = h - 7
    # sky
    if night:
        top, bot = "#120E2A", "#3B2A5E"
    else:
        top, bot = "#8FD0FF", "#FFE0EE"
        if heat > 0.0:
            warm = min(1.0, heat)
            top = mix(top, "#FF9A6B", warm * 0.55)
            bot = mix(bot, "#FF6B6B", warm * 0.45)
    for y in range(ground_y):
        c = mix(top, bot, y / max(1, ground_y - 1))
        for x in range(w):
            cv.px[y][x] = c
    rnd = random.Random(11)
    if night:
        for _ in range(w // 3):
            sx, sy = rnd.randrange(w), rnd.randrange(max(1, ground_y - 12))
            tw = 0.5 + 0.5 * math.sin(t * 2.3 + sx * 1.7)
            cv.set(sx, sy, mix("#3B2A5E", "#FFF6D8", 0.35 + 0.65 * tw))
        mx, my = int(w * 0.5) + 4, 5  # above the docks, the lowest roof
        for y in range(-7, 8):
            for x in range(-7, 8):
                d = math.hypot(x, y)
                if d <= 3.6:
                    shade_ = "#FFF2C4" if (x, y) not in ((1, -1), (-1, 1), (2, 1)) else "#E8D9A8"
                    cv.set(mx + x, my + y, shade_)
                elif d <= 7:
                    cv.blend(mx + x, my + y, "#FFF2C4", 0.18 * (1 - (d - 3.6) / 3.4))
    else:
        # clouds drift slowly
        for i, (cx0, cy, cw) in enumerate([(8, 4, 9), (45, 2, 12), (80, 5, 8)]):
            cx = int((cx0 + t * (1.2 + i * 0.4)) % (w + 20)) - 10
            for x in range(cw):
                cv.set(cx + x, cy, "#FFFFFF")
                if 1 < x < cw - 2:
                    cv.set(cx + x, cy - 1, "#FFFFFF")
    # hills
    for x in range(w):
        hy = int(ground_y - 5 - 3 * math.sin(x / 9.0) - 2 * math.sin(x / 4.3 + 1))
        for y in range(hy, ground_y):
            cv.set(x, y, "#2A3B4F" if night else "#9BD8A8")
    # street
    for y in range(ground_y, h):
        for x in range(w):
            base = "#3A3348" if night else "#C9B8A6"
            if (x + (y % 2) * 2) % 5 == 0:
                base = mix(base, "#000000", 0.12)
            cv.px[y][x] = base
    slot_w = w // len(KIT_ORDER)
    for i, kit in enumerate(KIT_ORDER):
        x0 = i * slot_w + 2
        bw = slot_w - 4
        _building(cv, kit, x0, bw, ground_y, t, night, highlighted=(selected == i), roof_prop=roof_prop)
        if posters > i:
            px = x0 + bw - 5
            cv.rect(px, ground_y - 6, 3, 4, "#FFF6E0")
            cv.set(px + 1, ground_y - 5, "#2B1B2E")
            cv.set(px + 1, ground_y - 3, "#E0464E")
    if selected is not None:
        x0 = selected * slot_w + slot_w // 2
        bob = int(round(math.sin(t * 5) * 1))
        ay = 1 + bob
        for dy, half in enumerate([3, 2, 1, 0]):
            for dx in range(-half, half + 1):
                cv.set(x0 + dx, ay + dy, "#FFD24A" if not night else "#FFF2C4")
    if guard and selected is not None:
        gx = selected * slot_w + slot_w // 2 + 6
        gy = ground_y + 1
        cv.rect(gx, gy - 6, 3, 2, "#5A6072")
        cv.rect(gx, gy - 4, 3, 1, "#F2C29B")
        cv.rect(gx, gy - 3, 3, 3, "#2F4C8F")
        cv.set(gx + 3, gy - 3, "#FFD24A")
    return cv


def _building(cv: Canvas, kit: str, x0: int, bw: int, gy: int, t: float, night: bool, highlighted: bool,
              roof_prop: str | None = None):
    lit = "#FFD98A"
    dark_win = "#3D5A80"
    win = lit if night else dark_win
    def shade(c):
        return mix(c, "#141026", 0.45) if night else c
    if kit == "shop":
        wall, trim = shade("#FFB3CF"), shade("#D9488A")
        top = gy - 13
        cv.rect(x0, top, bw, 13, wall)
        for x in range(bw):  # striped awning
            for y in range(3):
                cv.set(x0 + x, top + 4 + y, shade("#FFFFFF") if (x // 2) % 2 == 0 else trim)
        cv.rect(x0 + 2, top + 8, bw - 8, 4, win)
        cv.rect(x0 + bw - 5, top + 7, 3, 6, shade("#8A4B2A"))
        cv.rect(x0, top - 1, bw, 1, trim)
        # the giant prop on the roof, picked by the Town Architect from the catalog
        prop = icon(roof_prop) if roof_prop else None
        if prop:
            if night:
                for y in range(prop.h):
                    for x in range(prop.w):
                        if prop.px[y][x]:
                            prop.px[y][x] = shade(prop.px[y][x])
            cv.blit(prop, x0 + bw // 2 - 4, top - 9)
    elif kit == "house":
        wall, roof = shade("#C9B6F0"), shade("#6C4FA8")
        top = gy - 11
        cv.rect(x0 + 1, top, bw - 2, 11, wall)
        for i in range(7):
            cv.rect(x0 + i, top - 1 - i, bw - i * 2, 1, roof)
        cv.rect(x0 + 3, top + 3, 4, 4, win)
        cv.rect(x0 + bw - 7, top + 3, 4, 4, win)
        cv.set(x0 + 4, top + 4, "#5A6072")  # binoculars glint
        cv.set(x0 + 5, top + 4, "#FFFFFF" if int(t * 2) % 4 == 0 else "#5A6072")
        cv.rect(x0 + bw // 2 - 1, top + 6, 3, 5, shade("#8A4B2A"))
        for x in range(0, bw, 2):  # picket fence
            cv.rect(x0 + x, gy - 3, 1, 3, shade("#FFFFFF"))
        cv.rect(x0, gy - 2, bw, 1, shade("#FFFFFF"))
    elif kit == "dock_shed":
        water = "#1E3A66" if night else "#4FA3E0"
        for y in range(gy - 4, gy + 7):
            for x in range(bw):
                wave = math.sin((x + t * 4) / 2.5 + y) > 0.8
                cv.set(x0 + x, y, mix(water, "#FFFFFF", 0.35) if wave else water)
        cv.rect(x0, gy - 5, bw, 2, shade("#8A5A33"))
        for x in range(1, bw, 4):
            cv.rect(x0 + x, gy - 3, 1, 5, shade("#6B4426"))
        cv.rect(x0 + 2, gy - 12, 9, 7, shade("#A9744A"))
        for i in range(4):
            cv.rect(x0 + 1 + i, gy - 13 - i, 11 - i * 2, 1, shade("#5A3A22"))
        cv.rect(x0 + 4, gy - 10, 3, 2, win)
        # fishing rod and line, bobbing
        rx = x0 + bw - 6
        for i in range(7):
            cv.set(rx - i // 2 + 3, gy - 6 - i, shade("#5A3A22"))
        by = gy + 1 + int(round(math.sin(t * 3)))
        for y in range(gy - 12, by):
            cv.set(rx + 4, y, "#E8E8E8" if not night else "#8888AA")
        cv.set(rx + 4, by, "#E0464E")
    elif kit == "theater":
        wall = shade("#7A2E4A")
        top = gy - 15
        cv.rect(x0, top, bw, 15, wall)
        cv.rect(x0 + 2, top + 4, bw - 4, 11, shade("#2B1B2E"))
        for y in range(top + 4, gy):
            for x in range(x0 + 2, x0 + bw - 2):
                fold = (x - x0) % 3 == 0
                if x < x0 + bw // 2 - 1 or x > x0 + bw // 2 + 1:
                    cv.set(x, y, shade("#B8283C" if fold else "#E0464E"))
        for x in range(x0, x0 + bw, 2):  # marquee lights
            on = (x // 2 + int(t * 4)) % 3 != 0
            cv.set(x, top, "#FFD24A" if on else shade("#7A5A1E"))
            cv.set(x, top + 2, "#FFD24A" if not on else shade("#7A5A1E"))
        cv.rect(x0, top + 1, bw, 1, shade("#FFD24A"))
    elif kit == "tavern":
        wall, beam = shade("#E8D3A9"), shade("#5A3A22")
        top = gy - 13
        cv.rect(x0, top, bw, 13, wall)
        for x in range(x0, x0 + bw, 5):
            cv.rect(x, top, 1, 13, beam)
        cv.rect(x0, top + 6, bw, 1, beam)
        for i in range(4):
            cv.rect(x0 - 1 + i, top - 1 - i, bw + 2 - i * 2, 1, shade("#7A3B2A"))
        cv.rect(x0 + 2, top + 2, 4, 3, win)
        cv.rect(x0 + bw - 7, top + 2, 4, 3, win)
        cv.rect(x0 + bw // 2 - 2, top + 8, 4, 5, beam)
        # hanging tankard sign, swaying
        sx = x0 + bw // 2 + int(round(math.sin(t * 2)))
        cv.set(sx, top - 6, beam)
        cv.rect(sx - 1, top - 5, 3, 3, shade("#F2A541"))
        cv.set(sx + 2, top - 4, shade("#F2A541"))
        cv.rect(sx - 1, top - 5, 3, 1, "#FFFFFF" if not night else "#CCCCDD")
    if highlighted:
        # a soft glow on the street in front of the selected building
        for x in range(x0 - 1, x0 + bw + 1):
            for y in range(gy, gy + 3):
                cv.blend(x, y, "#FFD24A", 0.35 if y == gy else 0.18)


# ---------------------------------------------------------------- stocks (losing)
def stocks_scene(w: int, h: int, t: float) -> Canvas:
    cv = Canvas(w, h, UI["panel"])
    h = cv.h
    for y in range(h - 6, h):
        for x in range(w):
            cv.set(x, y, "#5A4636")
    cx = w // 2
    cv.rect(cx - 12, h - 18, 24, 4, "#8A5A33")
    cv.rect(cx - 10, h - 14, 2, 8, "#6B4426")
    cv.rect(cx + 8, h - 14, 2, 8, "#6B4426")
    cv.rect(cx - 2, h - 24, 5, 6, "#F2C29B")  # head
    cv.set(cx - 1, h - 22, "#1C1222"); cv.set(cx + 1, h - 22, "#1C1222")
    cv.rect(cx - 1, h - 20, 3, 1, "#1C1222")
    cv.set(cx - 7, h - 17, "#F2C29B"); cv.set(cx + 7, h - 17, "#F2C29B")
    pie = icon("custard_pie")   # the town throws pies
    rnd = random.Random(3)
    for i in range(5):
        phase = (t * 0.7 + i * 0.37) % 1.0
        sx = -10 + (cx + 6 + 10) * phase if i % 2 == 0 else w + 2 - (w - cx + 6) * phase
        sy = h - 30 - 18 * math.sin(math.pi * phase) + rnd.randint(-2, 2)
        cv.blit(pie, int(sx), int(sy))
    return cv
