"""The Wardrobe Stylist: 40 new hats and shades. C:\\cluster\\WARDROBE_STYLIST_DESIGN.md, approved by DAVID on 2026-11-04
("Design approved. Build it now.").

Content only. Each item is drawn the way C:\\bbust\\draw_wearables.py draws the 4 in the game (DAVID, 2026-11-04: no PixelLab,
the same method): a label map of flat shapes on a 32-wide design grid, the outline worked out from it, scaled up with hard
edges, and a color mask for a hat. The cluster writes an item as a recipe of those shapes; this file draws it with
draw_wearables.py's own functions, so a new item matches the 4 exactly. It reads the game's sprites and C:\\bbust\\wearables,
and never writes them. Approved items wait in C:\\cluster\\approved\\wardrobe.
"""
import json
import re
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import common
import gdd
from common import MalformedOutput

BBUST = Path(r"C:\bbust")
if str(BBUST) not in sys.path:
    sys.path.append(str(BBUST))
import draw_wearables as dw      # noqa: E402  the method itself
import mock_wearables as mw      # noqa: E402  where an item sits on a character
import wearable_anchors as wa    # noqa: E402  the hat line and the eyes, found on each skin

GAME_ITEMS = BBUST / "wearables"                 # the 4 in the game and their catalog: read only
APPROVED = Path(r"C:\cluster\approved\wardrobe")
IDEAS, ITEMS = "wardrobe_ideas", "wardrobe"      # under common.SUBMISSIONS
KIND, IDEA_KIND, AGENT = "wardrobe item", "wardrobe idea", "Wardrobe Stylist"
TOTAL, FIRST, PER_RUN = 40, 2, 5                  # the crew design: 5 a run, stopping after the first 2
SPLIT = {"hat": 30, "shades": 10}
BOX = {"hat": (dw.HAT_W, dw.HAT_H, dw.HAT_SCALE), "shades": (dw.SHADES_W, dw.SHADES_H, dw.SHADES_SCALE)}
GRID = {kind: (w / s, h / s) for kind, (w, h, s) in BOX.items()}   # the design grid each box is drawn from
SHAPES = ("poly", "ellipse", "rect", "line")
GENERIC = {"hat", "shades", "glasses", "the", "a", "of"}


def _region(rid, name, color, colorable):
    return {"id": rid, "name": name, "color": list(color), "colorable": colorable}


# The 4 items in the game, written as recipes: draw_wearables.py's own shapes, numbers and colors.
EXAMPLES = {
    "santa_hat": {"name": "Santa Hat", "kind": "hat",
                  "regions": [_region(1, "HAT", (200, 30, 36), True), _region(2, "TRIM", (246, 246, 240), True),
                              _region(3, "POM", (246, 246, 240), True)],
                  "shapes": [{"shape": "poly", "points": [[4, 23], [28, 23], [26, 16], [22, 9], [17, 4], [12, 2], [8, 3]], "region": 1},
                             {"shape": "poly", "points": [[8, 3], [12, 2], [14, 4], [11, 7], [8, 11], [6, 15], [3, 15], [4, 9]], "region": 1},
                             {"shape": "rect", "box": [3, 21, 28, 28], "region": 2},
                             {"shape": "ellipse", "box": [0, 21, 7, 28], "region": 2},
                             {"shape": "ellipse", "box": [24, 21, 31, 28], "region": 2},
                             {"shape": "ellipse", "box": [0, 13, 7, 20], "region": 3}]},
    "turkey_hat": {"name": "Turkey Hat", "kind": "hat",
                   "regions": [_region(1, "BIRD", (196, 120, 48), True), _region(2, "STICKS", (222, 156, 78), True),
                               _region(3, "GARNISH", (70, 150, 60), True), _region(4, "BONE", (244, 236, 214), False)],
                   "shapes": [{"shape": "line", "points": [[7, 11], [5, 3]], "width": 3, "region": 4},
                              {"shape": "line", "points": [[25, 11], [27, 3]], "width": 3, "region": 4},
                              {"shape": "ellipse", "box": [1, 0, 6, 5], "region": 4},
                              {"shape": "ellipse", "box": [5, 0, 10, 5], "region": 4},
                              {"shape": "ellipse", "box": [22, 0, 27, 5], "region": 4},
                              {"shape": "ellipse", "box": [26, 0, 31, 5], "region": 4},
                              {"shape": "poly", "points": [[4, 20], [12, 19], [11, 13], [9, 8], [6, 8], [4, 12]], "region": 2},
                              {"shape": "poly", "points": [[28, 20], [20, 19], [21, 13], [23, 8], [26, 8], [28, 12]], "region": 2},
                              {"shape": "ellipse", "box": [2, 12, 30, 34], "region": 1},
                              {"shape": "rect", "box": [0, 29, 31, 29], "region": 0},
                              {"shape": "ellipse", "box": [0, 22, 7, 29], "region": 3},
                              {"shape": "ellipse", "box": [25, 22, 31, 29], "region": 3}]},
    "black_shades": {"name": "Black Shades", "kind": "shades",
                     "regions": [_region(5, "FRAMES", (26, 26, 30), False), _region(6, "BRIDGE", (26, 26, 30), False)],
                     "shapes": [{"shape": "ellipse", "box": [0, 0, 11, 8], "region": 5},
                                {"shape": "rect", "box": [0, 0, 11, 4], "region": 5},
                                {"shape": "ellipse", "box": [12, 0, 23, 8], "region": 5},
                                {"shape": "rect", "box": [12, 0, 23, 4], "region": 5},
                                {"shape": "rect", "box": [10, 1, 13, 2], "region": 6}]},
    "silver_aviators": {"name": "Silver Aviators", "kind": "shades", "outline": list(dw.SILVER),
                        "regions": [_region(7, "WIRE", dw.SILVER, False), _region(8, "LENS", (62, 74, 84), False)],
                        "shapes": [{"shape": "poly", "points": [[0, 0], [10, 0], [10, 4], [8, 7], [5, 8], [2, 7], [0, 4]], "region": 8},
                                   {"shape": "poly", "points": [[23, 0], [13, 0], [13, 4], [15, 7], [18, 8], [21, 7], [23, 4]], "region": 8},
                                   {"shape": "rect", "box": [10, 0, 13, 0], "region": 7},
                                   {"shape": "rect", "box": [10, 2, 13, 2], "region": 7}]},
}

RECIPE_SYSTEM = """You draw one hat or one pair of shades for Bottom Busters, a comedy pixel-art game, as a recipe of flat \
shapes. Code draws the recipe: every shape fills its region, a thick dark outline is added wherever a region meets empty \
space or another region, and the result is scaled up with hard pixel edges. No shading, no gradients, no text.

The grid:
- A hat is drawn on a grid 32 wide (x 0 to 32) and 30 tall (y 0 to 30), y going down. Its bottom edge (y about 28 to 30) \
is the brim, which sits on the head, so the hat must reach the bottom. Every character faces right, so anything that leans, \
flops or hangs goes to the left, the back of the head.
- Shades are drawn on a grid 24 wide and 9 tall: two lenses, one centered near x 5.5 and one near x 17.5, with a bridge \
between them around x 10 to 13. Each lens sits on an eye.

The recipe is one JSON object:
"name": the item's name
"kind": "hat" or "shades"
"regions": a list of {"id": a number, "name": a capitalized word, "color": [red, green, blue], "colorable": true or false}. \
A hat has 1 to 3 colorable regions, numbered 1, 2 and 3: the parts a player can recolor. Fixed parts are numbered 4 and up. \
Shades have no colorable regions; number their regions 5 and up.
"shapes": a list, drawn in order, later shapes over earlier ones. Each is one of:
  {"shape": "poly", "points": [[x, y], [x, y], [x, y], ...], "region": id}
  {"shape": "ellipse", "box": [left, top, right, bottom], "region": id}
  {"shape": "rect", "box": [left, top, right, bottom], "region": id}
  {"shape": "line", "points": [[x, y], [x, y]], "width": 1 to 6, "region": id}
  Region 0 erases.
"outline": leave it out for the usual dark outline, or give [red, green, blue] (the silver aviators' wire is silver).
Make the item read at a glance: one strong outline you'd know anywhere, big simple parts, every part at least 3 grid units \
across. Answer with only the JSON object."""


def _read(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(path, data):
    tmp = Path(path).with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def game_items():
    return (_read(GAME_ITEMS / "catalog.json", {}) or {}).get("items", [])


# ── drawing ────────────────────────────────────────────────────────────────────────────────────────────────────────────
def draw(recipe):
    """(art, mask or None, label map) at art resolution, by draw_wearables.py's own functions."""
    w, h, scale = BOX[recipe["kind"]]
    dw.DRAW_SCALE = scale
    m = dw.new_map(w, h)
    for s in recipe["shapes"]:
        region = int(s["region"])
        if s["shape"] == "poly":
            dw.poly(m, [tuple(p) for p in s["points"]], region)
        elif s["shape"] == "ellipse":
            dw.ellipse(m, list(s["box"]), region)
        elif s["shape"] == "rect":
            dw.rect(m, list(s["box"]), region)
        else:
            dw.line(m, [tuple(p) for p in s["points"]], region, s.get("width", 1))
    colors = {int(g["id"]): tuple(int(c) for c in g["color"]) for g in recipe["regions"]}
    colorable = {int(g["id"]) for g in recipe["regions"] if g.get("colorable")}
    outline = tuple(recipe["outline"]) if recipe.get("outline") else dw.OUTLINE
    art, mask = dw.render(m, colors, colorable, outline)
    return art, (mask if recipe["kind"] == "hat" else None), m


def full_size(img):
    """Art resolution to the characters' resolution, hard edges kept (draw_wearables.up)."""
    return dw.up(img)


_marks = {}


def _skin(skin):
    if skin not in _marks:
        body = Image.open(Path(wa.SKIN_DIR) / f"{skin}.png").convert("RGBA")
        try:
            a = wa.anchors(body)
            e = wa.eyes(body, a)
        except Exception:
            a, e = None, None
        _marks[skin] = (body, a, e)
    return _marks[skin]


def sheet(item, kind):
    """The item on every character at game size, placed by mock_wearables.py's rules, and a close-up. Returns (sheet,
    close-up, fit): fit says per character whether the hat line, or both eyes, were found and the item placed."""
    cw, ch = int(mw.CELL_W * mw.SHOW), int(mw.CELL_H * mw.SHOW)
    out = Image.new("RGBA", (cw * len(wa.SKINS), 40 + ch), (236, 233, 224, 255))
    d = ImageDraw.Draw(out)
    font = ImageFont.truetype(mw.FONT, 22)
    fit = {}
    for c, skin in enumerate(wa.SKINS):
        body, a, e = _skin(skin)
        canvas = mw.assembled(skin)
        try:
            if kind == "hat":
                mw.place_hat(canvas, body, a, item)
            else:
                mw.place_shades(canvas, e, item)
            fit[skin] = True
        except Exception:
            fit[skin] = False
        d.text((c * cw + cw / 2, 20), skin + ("" if fit[skin] else " (not placed)"), font=font, fill=(34, 30, 28, 255), anchor="mm")
        hx = a["head_x"] if a else body.width / 2
        top = (a["top"] if a else 0) + mw.PAD - 380
        cell = Image.new("RGBA", (mw.CELL_W, mw.CELL_H), (196, 196, 196, 255))
        cell.alpha_composite(canvas.crop((round(hx - mw.CELL_W / 2), top, round(hx + mw.CELL_W / 2), top + mw.CELL_H)))
        out.alpha_composite(cell.resize((cw, ch), Image.LANCZOS), (c * cw, 40))
    return out.convert("RGB"), fit


def closeup(art):
    """The item at art resolution, 12 times bigger, on the sheet's gray."""
    big = art.resize((art.width * 12, art.height * 12), Image.NEAREST)
    out = Image.new("RGBA", (big.width + 48, big.height + 48), (196, 196, 196, 255))
    out.alpha_composite(big, (24, 24))
    return out.convert("RGB")


def draw_files(folder):
    """The item's art, mask, sheet and close-up, drawn from the recipe in its folder; the manifest says which files."""
    folder = Path(folder)
    m, r = _read(folder / "manifest.json"), _read(folder / "recipe.json")
    art, mask, _ = draw(r)
    files = [f"{m['item']}.png"]
    full_size(art).save(folder / files[0])
    if mask is not None:
        files.append(f"{m['item']}_mask.png")
        full_size(mask).save(folder / files[1])
    whole, fit = sheet(full_size(art), r["kind"])
    whole.save(folder / "sheet.png")
    closeup(art).save(folder / "closeup.png")
    m.update(files=files + ["recipe.json"], previews=["closeup.png", "sheet.png"], fit=fit)
    _write(folder / "manifest.json", m)
    return m


# ── the idea list ──────────────────────────────────────────────────────────────────────────────────────────────────────
def _words(name):
    return {w for w in re.findall(r"[a-z0-9']+", name.lower()) if w not in GENERIC}


def check_ideas(ideas, full=True):
    """Plain-code checks on the idea list: fields, kinds, color areas, no repeats, none of the 4 in the game. full: the
    whole list, so the 30 hats and 10 shades are checked too."""
    problems, seen = [], {}
    game = {i["name"]: _words(i["name"]) for i in game_items()}
    for i in ideas:
        name = (i.get("name") or "").strip()
        if not name:
            problems.append("an idea has no name")
            continue
        if "." in name:
            problems.append(f"{name}: no periods in a name")
        kind, areas = i.get("kind"), i.get("areas") or []
        if kind not in SPLIT:
            problems.append(f"{name}: kind is {kind!r}, not hat or shades")
        elif kind == "hat" and not 1 <= len(areas) <= 3:
            problems.append(f"{name}: a hat needs 1 to 3 color areas")
        elif kind == "shades" and areas:
            problems.append(f"{name}: shades take no color areas")
        if not (i.get("looks") or "").strip():
            problems.append(f"{name}: no description of what it looks like")
        for other, words in game.items():
            if name.lower() == other.lower() or _words(name) == words:
                problems.append(f"{name}: the game already has {other}")
        if name.lower() in seen:
            problems.append(f"{name}: listed twice")
        seen[name.lower()] = i
    if full:
        for kind, n in SPLIT.items():
            have = sum(1 for i in ideas if i.get("kind") == kind)
            if have != n:
                problems.append(f"{have} {kind} ideas, not {n}")
    return problems


def post_ideas(ideas, card=None):
    """Each idea as its own submission, so the Paperclip approvals put them on a card in David's inbox."""
    problems = check_ideas(ideas)
    if problems:
        raise ValueError("; ".join(problems))
    folders = []
    for n, i in enumerate(ideas, 1):
        folder = common.SUBMISSIONS / IDEAS / f"idea_{n:02}"
        folder.mkdir(parents=True, exist_ok=False)
        areas = f", color areas: {', '.join(i['areas'])}" if i["areas"] else ""
        _write(folder / "manifest.json", {"kind": IDEA_KIND, "agent": "Claude (researched list)", "card": card,
                                           "name": f"{i['name']}. {i['looks']}",
                                           "description": f"{i['kind'].capitalize()} idea{areas}", "idea": i})
        folders.append(folder)
    return folders


def _decided(kind_dir, kind):
    found = []
    for p in sorted((common.SUBMISSIONS / kind_dir).glob("*/manifest.json")):
        m = _read(p)
        if isinstance(m, dict) and m.get("kind") == kind:
            found.append((p.parent, m, _read(p.with_name("decision.json"))))
    return found


def ideas():
    return _decided(IDEAS, IDEA_KIND)


def items():
    return _decided(ITEMS, KIND)


def _ideas_waiting():
    used = {m.get("idea") for _, m, _ in items()}
    return [(f, m) for f, m, d in ideas() if d and d.get("decision") == "approve" and f.name not in used]


def state():
    """approved and waiting items, approved ideas not drawn yet, and how many the next run draws: 0 while David is deciding
    the last items or once TOTAL are approved; FIRST (the test) before any item; else PER_RUN, never past the ideas."""
    made = items()
    approved = sum(1 for _, _, d in made if d and d.get("decision") == "approve")
    waiting = sum(1 for _, _, d in made if not d)
    left = len(_ideas_waiting())
    nxt = 0 if waiting or approved >= TOTAL else min(PER_RUN if made else FIRST, TOTAL - approved, left)
    return {"approved": approved, "waiting": waiting, "ideas_waiting": left, "next": nxt}


def tasks(n):
    return [{"id": f"t{k + 1}", "brief": f"{m['idea']['name']}: {m['idea']['looks']}", "idea": f.name}
            for k, (f, m) in enumerate(_ideas_waiting()[:n])]


def redo_task(card):
    """A redo card from the Foreman: the same idea, with David's note."""
    found = re.search(r"\(([^()]+)\) from ", card["desc"])
    note = re.search(r"^David's note: (.+)$", card["desc"], re.M)
    m = _read(common.SUBMISSIONS / ITEMS / found.group(1) / "manifest.json") if found else None
    if not m or not note:
        raise common.CrewStop(f"the redo card {card['name']} doesn't name an item that's there")
    return {"id": "t1", "brief": f"Redraw {m['name']}", "idea": m["idea"], "note": note.group(1).strip()}


# ── one item ───────────────────────────────────────────────────────────────────────────────────────────────────────────
def recipe(idea, notes=None):
    """The cluster's recipe for one idea."""
    examples = "\n".join(f"Example: {key}\n{json.dumps(r)}" for key, r in EXAMPLES.items())
    user = [gdd.prompt_block("wardrobe-stylist"), "", f"The item: {idea['name']}, {idea['kind']}. What it looks like: {idea['looks']}"]
    if idea.get("areas"):
        user.append(f"Its color areas, regions 1 to {len(idea['areas'])}: {', '.join(idea['areas'])}.")
    user.append(f"\nThe 4 items in the game, as recipes:\n{examples}")
    if notes:
        user.append(f"\nFix this from last time: {notes}")
    messages = [{"role": "system", "content": RECIPE_SYSTEM}, {"role": "user", "content": "\n".join(user)}]
    return common.ask_json("wardrobe-stylist", messages, ["regions", "shapes"], max_tokens=3000)


def _slug(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "item"


def _fresh_id(name):
    taken = {i["id"] for i in game_items()} | {f.name for f, _, _ in items()} | \
            ({p.name for p in APPROVED.iterdir()} if APPROVED.exists() else set())
    base, k = _slug(name), 2
    item = base
    while item in taken:
        item, k = f"{base}_{k}", k + 1
    return item


def seat_hat(r, most=8):
    """A hat moved down its grid, one unit at a time, until its drawing reaches the bottom of its box: the GDD's "A hat's bottom
    edge is its brim, and it sits on the head." Plain code, so a brim drawn a little high doesn't cost a cheek (run
    20261107-163826: the Cowboy Hat's brim stopped at y 28 of 30.7, and the Bridge sent it back as floating)."""
    import bridge
    import numpy as np
    if r.get("kind") != "hat":
        return r
    for _ in range(most):
        art, _, _ = draw(r)
        if int((np.asarray(art)[-2:, :, 3] > 0).sum()) >= bridge.WARDROBE_BRIM_PIXELS:
            return r
        for s in r["shapes"]:
            if "points" in s:
                s["points"] = [[p[0], p[1] + 1] for p in s["points"]]
            if "box" in s:
                b = s["box"]
                s["box"] = [b[0], b[1] + 1, b[2], b[3] + 1]
    return r


def design(task, slot, taken, notes, seed):
    """The recipe for an approved idea, written with the GDD's Section 21.3 at the top of the prompt, and one the Bridge can
    draw. The Orchestrator has the Critic check it against the GDD before build() draws it. slot, taken and seed are unused:
    every maker gets the same arguments."""
    import bridge
    idea_folder = common.SUBMISSIONS / IDEAS / task["idea"]
    idea = (_read(idea_folder / "manifest.json") or {}).get("idea")
    if not idea:
        raise common.CrewStop(f"the idea {task['idea']} isn't there")
    r = recipe(idea, notes or task.get("note"))
    r.update(name=idea["name"], kind=idea["kind"])
    problems = bridge.check_wardrobe_recipe(r)
    if not problems:
        r = seat_hat(r)
    if problems:
        raise MalformedOutput(f"the recipe for {idea['name']} can't be drawn: {'; '.join(problems)}")
    return {"recipe": r, "looks": idea.get("looks", ""), "idea": task["idea"]}


def for_review(d):
    """What the Critic's GDD check reads: the item, the idea it was drawn from, its parts and colors, and its outline."""
    r = d["recipe"]
    return {"name": r["name"], "kind": r["kind"], "idea": d["looks"], "outline": r.get("outline") or "the usual dark outline",
            "regions": [{"name": g.get("name"), "color": g.get("color"), "players_recolor_it": bool(g.get("colorable"))}
                        for g in r.get("regions") or [] if isinstance(g, dict)],
            "shapes": len(r.get("shapes") or [])}


def make(task, slot, taken, notes, seed):
    """One item, with no GDD check between the recipe and the drawing. Returns its folder and concept."""
    return build(task, slot, design(task, slot, taken, notes, seed), seed)


def build(task, slot, d, seed):
    """The item drawn from a recipe that passed the GDD check. Returns its folder and concept."""
    r = d["recipe"]
    idea = {"name": r["name"]}
    folder = common.WORK / f"wardrobe_{task['id']}"
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    _write(folder / "recipe.json", r)
    colorable = [g["name"] for g in sorted(r["regions"], key=lambda g: g["id"]) if g.get("colorable")]
    description = "Shades" if r["kind"] == "shades" else \
        f"Hat, {len(colorable)} color area" + ("" if len(colorable) == 1 else "s")
    _write(folder / "manifest.json", {"kind": KIND, "agent": AGENT, "name": idea["name"], "description": description,
                                      "item": _fresh_id(idea["name"]), "item_kind": r["kind"], "idea": task["idea"],
                                      "regions": colorable})
    draw_files(folder)
    return folder, {"name": idea["name"], "kind": r["kind"], "idea": task["idea"]}


def publish(folder):
    """Work that passed goes where the Paperclip approvals pick it up, in one move."""
    folder = Path(folder)
    m = _read(folder / "manifest.json")
    dst = common.SUBMISSIONS / ITEMS / m["item"]
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(folder), str(dst))
    return dst


def result(task, folder, concept, manifest, verdict, facts):
    """The run record's line for one item."""
    return {"task": task["id"], "name": concept["name"], "skin": Path(folder).name, "look": concept["kind"], "skin_tone": "",
            "critic_saw": verdict.get("what_i_see"), "folder": Path(folder).name, "difference_from_roster": facts.get("difference")}


def store_approved():
    """Every approved item, once, in APPROVED/<id>: the art, a hat's mask, the recipe, the sheet and its catalog entry in
    the game's own format. Returns how many items are approved."""
    approved = [(f, m) for f, m, d in items() if d and d.get("decision") == "approve"]
    for folder, m in approved:
        dst = APPROVED / folder.name
        if dst.exists():
            continue
        tmp = APPROVED / f".{folder.name}.tmp"
        if tmp.exists():
            shutil.rmtree(tmp)
        tmp.mkdir(parents=True)
        for f in m.get("files", []) + ["sheet.png"]:
            if (folder / f).exists():
                shutil.copyfile(folder / f, tmp / f)
        _write(tmp / "catalog_entry.json", {
            "id": folder.name, "kind": m["item_kind"], "name": m["name"], "art": folder.name,
            "mask": f"{folder.name}_mask" if m["item_kind"] == "hat" else "", "regions": m.get("regions", []),
            "source": "", "steamItemDef": 0, "season": ""})
        tmp.rename(dst)
    return len(approved)
