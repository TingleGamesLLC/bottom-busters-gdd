"""Level Architect: new parallax backgrounds for Bottom Busters, made on David's machines with no Claude.

C:\\cluster\\LEVEL_ARCHITECT_DESIGN.md is the design and C:\\cluster\\crew\\BACKGROUNDS_METHOD.md the art's rulebook. First, once,
an idea list: 100 one-line ideas (a theme and a style each) that David approves, rejects or rewrites on the dashboard. Then
each background turns the next approved idea into a recipe, ComfyUI paints its objects one at a time, and plain code builds
and checks every layer. Nothing goes into the game.
"""
import json
import re
from pathlib import Path

import common
import gdd

SCENES = Path(r"C:\bbust\BBUST\Assets\Resources\Backdrop\Scenes")   # the 99 existing backgrounds
IDEAS = Path(r"C:\cluster\submissions\background_ideas")
BACKGROUNDS = Path(r"C:\cluster\submissions\backgrounds")
APPROVED = Path(r"C:\cluster\approved\backgrounds")
TOTAL = 100
MOON_OR_SKY = 10      # all-water levels only use moon and sky backgrounds (design, section 3; 10 is Claude's call)
IDEA_BATCH = 10       # ideas per cluster answer
FILLER = {"a", "an", "the", "at", "of", "in", "on", "by", "with", "and", "over", "under", "from"}
TIMES = {"night", "day", "dusk", "dawn", "evening", "sunset", "sunrise", "morning", "noon", "midnight", "twilight"}

IDEAS_SYSTEM = """You plan backgrounds for Bottom Busters, a comedy arcade game where chubby men in white briefs fly by farting.
Each background is a side-scrolling parallax scene: a sky, maybe a haze, and two to four layers of objects drifting at different speeds.
Write new background ideas, each a theme and a visual style. Every theme is a different place, and none is just one of the game's existing backgrounds at another time of day.
Styles vary from idea to idea: pixel art, flat vector, painterly, ink, papercut, low-poly, and so on, always readable behind fast arcade action.
Answer with only one JSON object: {"ideas": [{"theme": "under 10 words", "style": "under 15 words"}, ...]}"""


# ── the idea list ────────────────────────────────────────────────────────────────────────────────────────────────
def _words(text):
    return [w for w in re.findall(r"[a-z]+", text.lower())]


def scene_bases():
    """The 99 scene names as plain words: forestB3 is "forest", apoc1_Pale is "apoc"."""
    bases = set()
    for p in SCENES.iterdir() if SCENES.exists() else []:
        name = re.sub(r"\d+", "", p.name.lower()).split("_")[0]
        bases.add(re.sub(r"[bc]$", "", name) if len(name) > 3 else name)
    return bases


def _core(theme):
    return " ".join(w for w in _words(theme) if w not in FILLER and w not in TIMES)


def _ideas(decided=None):
    """(folder, manifest, decision) for every posted idea, in number order."""
    found = []
    for m in sorted(IDEAS.glob("idea_*/manifest.json")) if IDEAS.exists() else []:
        d = m.with_name("decision.json")
        found.append((m.parent, json.loads(m.read_text(encoding="utf-8")),
                      json.loads(d.read_text(encoding="utf-8")) if d.exists() else None))
    return found


def _live():
    """Ideas approved or still waiting on David."""
    return [(f, m, d) for f, m, d in _ideas() if not d or d.get("decision") == "approve"]


LINKS = {"in", "under", "with", "over", "above", "beneath", "below", "on", "at", "during", "through", "across", "inside",
         "around", "amid", "among", "near", "beyond", "into", "between", "along", "within", "atop"}


def _place(theme):
    """The place an idea names: its words before the first linking word ('floating tea party islands' in '... in a gravity
    storm'), or all its words when that's a single word ('moon over the glass desert')."""
    words = [w for w in _words(theme) if w not in TIMES]
    head = []
    for w in words:
        if w in LINKS:
            break
        if w not in FILLER:
            head.append(w)
    return set(head) if len(head) >= 2 else {w for w in words if w not in FILLER and w not in LINKS}


def _same_place(a, b):
    """One place again: the same words, one place inside the other, or at least half their words shared (two or more)."""
    small, big = sorted((a, b), key=len)
    shared = len(a & b)
    return bool(small) and (a == b or (len(small) >= 2 and small <= big) or (shared >= 2 and shared / len(a | b) >= 0.5))


def _moon_or_sky(theme):
    return bool({"moon", "sky", "skies"} & set(_words(theme)))


def check_ideas(ideas, moon=0, spare=0):
    """A batch's problems: a missing style, a repeat of the 99 or of the list, and fewer moon or sky ideas than asked for,
    beyond what the `spare` ideas in later batches can still make up."""
    problems = []
    bases = scene_bases()
    seen = [(m.get("theme", ""), _place(m.get("theme", ""))) for _, m, _ in _live()]
    for i in ideas:
        theme, style = str(i.get("theme") or "").strip(), str(i.get("style") or "").strip()
        if not theme or not style:
            problems.append(f"Give every idea a theme and a style: '{theme or style}' is missing one.")
            continue
        core, place = _core(theme), _place(theme)
        if core in bases:
            problems.append(f"Replace '{theme}': it's just {core}, one of the game's 99 backgrounds already.")
        other = next((t for t, p in seen if _same_place(place, p)), None)
        if other is not None:
            problems.append(f"Replace '{theme}': it's the same place as '{other}', so the place is in the list twice. "
                            f"Write a new place, not new weather, a new sky or a new detail.")
        seen.append((theme, place))
    moon_sky = sum(1 for i in ideas if _moon_or_sky(str(i.get("theme") or "")))
    if moon_sky + spare < moon:
        problems.append(f"Make at least {moon} of these ideas moon or sky scenes, with the word moon or sky in the theme "
                        f"(all-water levels only use those): there are {moon_sky}.")
    return problems


def write_ideas(count, moon=0, spare=0):
    taken = ", ".join(sorted(scene_bases()))
    live = "; ".join(m.get("theme", "") for _, m, _ in _live()) or "none yet"
    must = f"\nAt least {moon} of them must be moon or sky scenes, with the word moon or sky in the theme." if moon else ""
    messages = [{"role": "system", "content": IDEAS_SYSTEM},
                {"role": "user", "content": f"{gdd.prompt_block('level-architect')}\n\n"
                                            f"Write {count} new ideas.{must}\nThe game's existing backgrounds: {taken}.\n"
                                            f"Ideas already on the list: {live}."}]
    for _ in range(2):
        d = common.ask_json("level-architect", messages, ["ideas"], max_tokens=60 * count + 300)
        ideas = [i for i in d["ideas"] if isinstance(i, dict)][:count] if isinstance(d["ideas"], list) else []
        problems = check_ideas(ideas, moon, spare) + ([f"Write exactly {count} ideas: there are {len(ideas)}."] if len(ideas) != count else [])
        if not problems:
            return ideas
        messages += [{"role": "assistant", "content": json.dumps(d)[:6000]},
                     {"role": "user", "content": "Fix these and answer with the whole list again: " + " ".join(problems[:12])}]
    # Still failing after two tries: keep the ideas that pass on their own and drop the repeats; the next batch asks for
    # the ones dropped. Stops when nothing new is left, or the moon and sky ideas can't be made up later.
    kept = []
    for i in ideas:
        if not check_ideas(kept + [i]):
            kept.append(i)
    if not kept or check_ideas(kept, moon, spare + count - len(kept)):
        raise common.MalformedOutput(f"the idea list failed its checks twice: {' '.join(problems[:3])}")
    return kept


def post_ideas(ideas):
    numbers = [int(f.name.split("_")[1]) for f, _, _ in _ideas()]
    n = max(numbers, default=0)
    for i in ideas:
        n += 1
        folder = IDEAS / f"idea_{n:03}"
        folder.mkdir(parents=True)
        (folder / "manifest.json").write_text(json.dumps({
            "kind": "background idea", "agent": "Level Architect", "name": f"{i['theme']}, {i['style']}",
            "theme": i["theme"], "style": i["style"], "previews": [], "files": []}, indent=2), encoding="utf-8")


def top_up_ideas():
    """Post only as many new ideas as it takes for approved plus waiting to reach 100. Returns how many were posted.
    Written IDEA_BATCH at a time (100 in one answer repeated themes), the moon and sky ideas first, each batch posted as it
    passes; a batch short of moon or sky ideas passes while later batches can make up the rest, and the next is asked for
    them. A batch that fails its checks twice stops the top-up and the batches before it stay posted."""
    posted = 0
    while (missing := TOTAL - len(_live())) > 0:
        count = min(IDEA_BATCH, missing)
        moon = min(count, max(0, MOON_OR_SKY - sum(1 for _, m, _ in _live() if _moon_or_sky(m.get("theme", "")))))
        new = write_ideas(count, moon, spare=missing - count)
        post_ideas(new)
        posted += len(new)
    return posted


def used_ideas():
    used = set()
    for m in BACKGROUNDS.glob("*/manifest.json") if BACKGROUNDS.exists() else []:
        idea = json.loads(m.read_text(encoding="utf-8")).get("idea")
        if idea:
            used.add(idea)
    return used


def next_idea():
    """The lowest-numbered approved idea no background has used. David's note on the approval replaces its wording."""
    used = used_ideas()
    for folder, m, d in _ideas():
        if d and d.get("decision") == "approve" and folder.name not in used:
            note = (d.get("note") or "").strip()
            return {"id": folder.name, "theme": note or m["theme"], "style": "" if note else m["style"]}
    return None


# ── the recipe ───────────────────────────────────────────────────────────────────────────────────────────────────
RECIPE_FIELDS = ["theme", "style", "palette", "layers", "ground_type"]
RECIPE_SYSTEM = """You design one side-scrolling parallax background for Bottom Busters, a comedy arcade game. The screen is 576 by 324 pixels.
The background is "layers", a list of layers, back to front. Every layer has a "kind" and a "speed", and each kind has one job:
- "kind": "sky": the first layer, and the only sky: a vertical color gradient, where "rows" is a list of 2 to 6 colors from top to bottom.
- "kind": "haze": a see-through band of one color: "color", "center_row" (0 to 323), "width_rows" (5 to 120), "strength" (0.1 to 0.8). At most two.
- "kind": "objects": one kind of thing per layer, standing on a ground line: "ground_row" (180 to 320), "ground_color", and "objects", a list of
  {"description": one object, plainly, "count": how many along the width, "height": [min, max] pixels, between 12 and 230}.
Two to four objects layers. Farther layers are smaller and slower; every layer's "speed" is at least the one before it, from about 0.05 for the sky to 1.0 for the nearest.
One layer of each kind, as an example of the fields:
{"kind": "sky", "rows": [[20, 16, 48], [72, 40, 96], [150, 90, 140]], "speed": 0.05}
{"kind": "haze", "color": [120, 70, 130], "center_row": 200, "width_rows": 60, "strength": 0.4, "speed": 0.1}
{"kind": "objects", "ground_row": 250, "ground_color": [60, 40, 70], "objects": [{"description": "a leaning dead tree", "count": 4, "height": [90, 160]}], "speed": 0.3}
"palette": 4 to 24 colors as [r, g, b], used by every layer. Never pure or bright green: green is cut away from painted objects.
"ground_type": one word, such as grass, snow, sand, stone, water or metal.
Answer with only one JSON object with the fields theme, style, palette, layers, ground_type."""


def taken_themes():
    """The 99 existing scene names, and every recipe's theme already submitted or approved, in lower case."""
    taken = {p.name.lower() for p in SCENES.iterdir()} if SCENES.exists() else set()
    for root in (BACKGROUNDS, APPROVED):
        for m in root.glob("*/recipe.json") if root.exists() else []:
            taken.add(str(json.loads(m.read_text(encoding="utf-8")).get("theme", "")).lower())
    return taken


def _color(c):
    return isinstance(c, (list, tuple)) and len(c) == 3 and all(isinstance(v, (int, float)) and 0 <= v <= 255 for v in c)


def check_recipe(r):
    """Fix instructions for the recipe, empty when it follows the layer system and the method's rules."""
    import numpy as np
    import objects
    missing = [f for f in RECIPE_FIELDS if f not in r]
    if missing:
        return [f"Add the fields {missing}."]
    problems = []
    if str(r["theme"]).strip().lower() in taken_themes():
        problems.append(f"Use a new theme: {r['theme']} is taken.")
    palette = r["palette"] if isinstance(r["palette"], list) else []
    if not 4 <= len(palette) <= 24 or not all(_color(c) for c in palette):
        problems.append("Give a palette of 4 to 24 colors, each [r, g, b] from 0 to 255.")
    elif objects.is_key(np.array([palette], float)).any():
        problems.append("Take bright green out of the palette: it's cut away from painted objects.")
    layers = r["layers"] if isinstance(r["layers"], list) else []
    kinds = [l.get("kind") for l in layers if isinstance(l, dict)]
    if not 4 <= len(layers) <= 7:
        problems.append(f"Use 4 to 7 layers: there are {len(layers)}.")
    if kinds[:1] != ["sky"] or kinds.count("sky") != 1:
        problems.append("Make the sky the first layer, and the only sky.")
    if kinds.count("haze") > 2:
        problems.append("Use at most two haze layers.")
    if not 2 <= kinds.count("objects") <= 4:
        problems.append("Use two to four objects layers.")
    speeds = [l.get("speed") for l in layers if isinstance(l, dict)]
    if not all(isinstance(s, (int, float)) for s in speeds) or any(b < a for a, b in zip(speeds, speeds[1:])):
        problems.append("Make every layer's speed at least the one before it, far to near.")
    for k, l in enumerate(layers):
        if not isinstance(l, dict):
            continue
        if l.get("kind") == "sky" and not (isinstance(l.get("rows"), list) and 2 <= len(l["rows"]) <= 6 and all(_color(c) for c in l["rows"])):
            problems.append("Give the sky 2 to 6 colors in rows, top to bottom.")
        if l.get("kind") == "haze" and not (_color(l.get("color")) and 0 <= l.get("center_row", -1) < 324
                                             and 5 <= l.get("width_rows", 0) <= 120 and 0.1 <= l.get("strength", 0) <= 0.8):
            problems.append(f"Fix haze layer {k}: color, center_row 0 to 323, width_rows 5 to 120, strength 0.1 to 0.8.")
        if l.get("kind") == "objects":
            if not (_color(l.get("ground_color")) and 180 <= l.get("ground_row", 0) <= 320):
                problems.append(f"Fix objects layer {k}: ground_color, and ground_row from 180 to 320.")
            things = l.get("objects") if isinstance(l.get("objects"), list) else []
            if not things:
                problems.append(f"Give objects layer {k} at least one object.")
            for o in things:
                h = o.get("height") if isinstance(o, dict) else None
                if not (isinstance(o, dict) and str(o.get("description") or "").strip() and 1 <= o.get("count", 0) <= 40
                        and isinstance(h, list) and len(h) == 2 and 12 <= h[0] <= h[1] <= 230):
                    problems.append(f"Fix an object on layer {k}: a description, a count from 1 to 40, and a height [min, max] from 12 to 230.")
    return problems


def recipe(idea, notes):
    """The approved idea as a recipe. The idea's theme and style are kept whatever the model writes."""
    text = f"{gdd.prompt_block('level-architect')}\n\nTheme: {idea['theme']}\nStyle: {idea['style'] or 'pick one that suits the theme'}"
    if notes:
        text += f"\nThe last attempt was sent back: {notes}"
    messages = [{"role": "system", "content": RECIPE_SYSTEM}, {"role": "user", "content": text}]
    for _ in range(2):
        r = common.ask_json("level-architect", messages, RECIPE_FIELDS, max_tokens=1800)
        r["theme"] = idea["theme"]
        r["style"] = idea["style"] or r.get("style") or ""
        r["idea"] = idea.get("id")
        for l in r.get("layers") if isinstance(r.get("layers"), list) else []:
            if isinstance(l, dict) and "kind" not in l and l.get("type") in ("sky", "haze", "objects"):
                l["kind"] = l.pop("type")   # run 20261107-155047: the model wrote "type" for "kind" on every try
        problems = check_recipe(r)
        if not problems:
            return r
        messages += [{"role": "assistant", "content": json.dumps(r)[:6000]},
                     {"role": "user", "content": "Fix these and answer with the whole recipe again: " + " ".join(problems)}]
    raise common.MalformedOutput(f"the recipe failed its checks twice: {' '.join(problems[:3])}")


# ── making a background ──────────────────────────────────────────────────────────────────────────────────────────
def _fresh(path):
    """A folder David decided on stays as his record, so new work goes beside it; an undecided one is replaced."""
    import shutil
    candidate, n = path, 2
    while (candidate / "decision.json").exists():
        candidate, n = path.with_name(f"{path.name}_{n}"), n + 1
    if candidate.exists():
        shutil.rmtree(candidate)
    return candidate


def _object_layer(k, spec, style, palette, seed, lib, placements, used):
    import random
    import layers
    import numpy as np
    import objects
    from PIL import Image
    rng = random.Random(seed + k)
    first = len(placements)   # this layer's placements start here
    layer = Image.new("RGBA", (layers.GW, layers.GH))
    line = layers.periodic_line(spec["ground_row"], [4, 2], seed + k)
    jobs = [(o, n) for o in spec["objects"] for n in range(o["count"])]
    for j, (o, n) in enumerate(jobs):
        path = lib.find(style, o["description"])
        if path is None:
            path = lib.add(style, o["description"], objects.paint_whole(style, o["description"], seed + 97 * k + 7 * j))
        used.add(str(path))
        h = rng.randint(o["height"][0], o["height"][1])
        sprite = objects.shrink(Image.open(path).convert("RGBA"), h, palette)
        if rng.random() < 0.5:
            sprite = sprite.transpose(Image.FLIP_LEFT_RIGHT)
        center = int((j + rng.uniform(0.2, 0.8)) * layers.GW / len(jobs)) % layers.GW
        base = int(line[center]) + max(4, h // 20)
        left = center - sprite.width // 2
        layers.place_wrapped(layer, sprite, left, base)
        placements.append({"layer": f"{k:02}.png", "x": left % layers.GW, "top": base - sprite.height, "width": sprite.width,
                           "height": sprite.height, "lowest_row": base - 1, "ground_row": int(line[center])})
    ground = tuple(int(v) for v in objects.to_palette(np.array([[spec["ground_color"]]], float), palette)[0, 0])
    return fill_holes(layers.ground(layer, line, ground), placements[first:])


def fill_holes(layer, boxes):
    """BACKGROUNDS_METHOD.md rule 3: a see-through spot enclosed inside an object's box, no bigger than the Bridge's hole limit,
    is filled with the nearest object color. Run 20261107-163827 lost both cheeks to them: 2 to 25 pixel gaps between the grass
    at an object's foot and the ground, which closes them in. Bigger gaps are real background showing through, and stay."""
    import bridge
    import numpy as np
    from PIL import Image
    from scipy import ndimage
    a = np.array(layer)
    for p in boxes:
        r = np.roll(a, -p["x"], axis=1)
        top, bottom = max(0, p["top"]), p["top"] + p["height"]
        box = r[top:bottom, :p["width"]]
        solid = box[..., 3] > 0
        holes = ndimage.binary_fill_holes(solid) & ~solid
        lab, n = ndimage.label(holes)
        if not n:
            continue
        sizes = ndimage.sum(holes, lab, range(1, n + 1))
        small = np.isin(lab, [k + 1 for k, s in enumerate(sizes) if s <= bridge.HOLE_MAX])
        if not small.any():
            continue
        _, (iy, ix) = ndimage.distance_transform_edt(~solid, return_indices=True)
        box[small] = box[iy[small], ix[small]]
        box[small, 3] = 255
        r[top:bottom, :p["width"]] = box
        a = np.roll(r, p["x"], axis=1)
    return Image.fromarray(a, "RGBA")


def design(task, slot, taken, notes, seed):
    """The recipe for the next approved idea, written with the GDD's Section 21.4 at the top of the prompt. The Orchestrator has
    the Critic check it against the GDD before build() paints anything. slot and taken are unused: they're the Character
    Artist's, and the Orchestrator hands every maker the same arguments."""
    import comfy
    comfy.start()   # launched and waited for when it isn't running
    idea = next_idea()
    if idea is None:
        raise common.NeedsDavid("no approved background idea is waiting: approve some on the Characters tab")
    return recipe(idea, notes)


def for_review(r):
    """What the Critic's GDD check reads: the recipe without its numbers, layer by layer, back to front."""
    layers_ = []
    for l in r.get("layers") or []:
        if not isinstance(l, dict):
            continue
        entry = {"kind": l.get("kind"), "speed": l.get("speed")}
        if l.get("kind") == "objects":
            entry["objects"] = [o.get("description") for o in l.get("objects") or [] if isinstance(o, dict)]
        layers_.append(entry)
    return {"theme": r.get("theme"), "style": r.get("style"), "ground_type": r.get("ground_type"),
            "palette": r.get("palette"), "layers": layers_}


def make(task, slot, taken, notes, seed):
    """One background, with no GDD check between the recipe and the painting. Returns its folder and recipe."""
    return build(task, slot, design(task, slot, taken, notes, seed), seed)


def build(task, slot, r, seed):
    """A background painted from a recipe that passed the GDD check. Returns its folder and recipe."""
    import shutil
    import layers
    import numpy as np
    import objects
    idea = {"id": r["idea"]}
    folder = common.WORK / f"background_{task['id']}"
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    palette = np.array(r["palette"], float)
    lib = objects.Library(objects.LIBRARY)
    stack, speeds, placements, used = {}, {}, [], set()
    for k, spec in enumerate(r["layers"]):
        name = f"{k:02}.png"
        if spec["kind"] == "sky":
            im = layers.sky([tuple(c) for c in spec["rows"]], seed=seed)
        elif spec["kind"] == "haze":
            im = layers.haze(tuple(spec["color"]), spec["center_row"], spec["width_rows"], spec["strength"])
        else:
            im = _object_layer(k, spec, r["style"], palette, seed, lib, placements, used)
        im.save(folder / name)
        stack[name], speeds[name] = im, spec["speed"]
    (folder / "recipe.json").write_text(json.dumps(r, indent=2), encoding="utf-8")
    previews = layers.previews(stack, speeds, folder)
    (folder / "manifest.json").write_text(json.dumps({
        "kind": "background", "agent": "Level Architect", "name": f"{r['theme']} ({r['style']})", "idea": idea["id"],
        "theme": r["theme"], "ground_type": r["ground_type"], "files": list(stack), "previews": previews,
        "placements": placements, "objects": sorted(used)}, indent=2), encoding="utf-8")
    return folder, r


def publish(folder):
    """Work that passed goes where David can see it."""
    import shutil
    dst = _fresh(BACKGROUNDS / Path(folder).name)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(folder), str(dst))
    return dst


def _backgrounds():
    """(folder, manifest, decision) for every background made from an idea."""
    found = []
    for m in sorted(BACKGROUNDS.glob("*/manifest.json")) if BACKGROUNDS.exists() else []:
        man = json.loads(m.read_text(encoding="utf-8"))
        if man.get("kind") == "background" and man.get("idea"):
            d = m.with_name("decision.json")
            found.append((m.parent, man, json.loads(d.read_text(encoding="utf-8")) if d.exists() else None))
    return found


def how_many():
    """One while no background has been made: the test run (DAVID, 2026-11-04). After it, up to 10 a run, never past 100,
    and never more than the approved ideas waiting."""
    made = _backgrounds()
    if not made:
        return 1
    counted = sum(1 for _, m, d in made if not d or d.get("decision") != "reject" or m.get("redone_by"))
    used = used_ideas()
    waiting = sum(1 for f, _, d in _ideas() if d and d.get("decision") == "approve" and f.name not in used)
    return max(0, min(10, TOTAL - counted, waiting))


def store_approved():
    r"""Every approved background's layers and recipe go to C:\cluster\approved\backgrounds, outside the game, once; its
    objects are marked approved in the library."""
    import shutil
    import objects
    stored = []
    for folder, m, d in _backgrounds():
        if not d or d.get("decision") != "approve" or (APPROVED / folder.name).exists():
            continue
        dst = APPROVED / folder.name
        dst.mkdir(parents=True)
        for f in m["files"] + ["recipe.json", "manifest.json", "preview_1_whole.png"]:
            if (folder / f).exists():
                shutil.copyfile(folder / f, dst / f)
        objects.Library(objects.LIBRARY).approve([Path(p) for p in m.get("objects", []) if Path(p).exists()])
        stored.append(folder.name)
    return stored
