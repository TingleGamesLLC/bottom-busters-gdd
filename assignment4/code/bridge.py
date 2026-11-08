"""Bridge: a script, not an agent. Checks a maker's files before anything looks at them or anything builds them.

Malformed output goes back to its maker with a fix prompt (class notes: detect malformed content, prompt self-correction,
validate before compile). Returns a list of problems, each written as an instruction to the maker. An empty list passes.
A check that can't run counts as a fail.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

import common
import parts

ASSETS = Path(r"C:\bbust\BBUST\Assets")
SPRITES = ASSETS / "Sprites" / "Characters"
GAME_MANAGER = ASSETS / "Scripts" / "Core" / "GameManager.cs"
NAMES_FILE = ASSETS / "Resources" / "CharacterNames.json"
LIMITS = Path(__file__).resolve().with_name("limits.json")
ROSTER = ["player"] + [f"player{i}" for i in range(2, 11)]
TEMPLATE = "player"

BODY_ROW = 400           # below this row the body must be the template's silhouette
BRIEFS_ROW = 500         # the briefs start below this row
HEAD_BOX = parts.HEAD_BOX
MAX_HAIR_COLORS = 12
MIN_HEAD_SKIN = 0.10     # share of the face box that must be the torso's skin; the originals run 0.18 to 0.52
BASELINE_OVERLAP = 0.75  # the originals sit a cell or two off the template; their closest fit to it runs 0.77 to 0.93
BASELINE_BRIEFS = 0.15   # and their briefs are within this share of the template's size
SKIN_LIMIT = 10.0        # how far a new skin must be from the original ten's, which are within 2.7 of each other
ANIMATIONS = (("DeathFlail", "flail", 12), ("CharacterIdle", "idle", 3), ("FartFlap", "flap", 8))


def _rgba(path):
    return np.array(Image.open(path).convert("RGBA"))


def _load(path, default=None):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def distance(head_a, head_b):
    """Mean color difference of two whole heads shrunk to about game size, on the game's sky."""
    def small(a):
        im = Image.fromarray(a).crop(HEAD_BOX)
        bg = Image.new("RGBA", im.size, (150, 200, 240, 255))
        bg.alpha_composite(im)
        return np.array(bg.convert("RGB").resize((36, 26), Image.LANCZOS)).astype(float)
    return float(np.abs(small(head_a) - small(head_b)).mean())


def submissions(decision=None):
    """(folder, manifest) for every character submission; with decision, only those David gave that decision."""
    found = []
    for path in sorted(common.SUBMISSIONS.glob("characters/*/manifest.json")):
        said = (_load(path.with_name("decision.json"), {}) or {}).get("decision")
        if decision is None or said == decision:
            found.append((path.parent, json.loads(path.read_text(encoding="utf-8"))))
    return found


def _is_rejected(folder):
    return (_load(Path(folder) / "decision.json", {}) or {}).get("decision") == "reject"


def character_list(skip=None):
    """Every character a new one has to differ from: the game's own, then the submissions David approved."""
    found = {p.stem: p for p in sorted(SPRITES.glob("player*.png")) if re.fullmatch(r"player\d*", p.stem)}
    for folder, m in submissions("approve"):
        if m.get("kind") == "character" and Path(folder) != skip and m["skin"] not in found:
            found[m["skin"]] = Path(folder) / "Sprites" / "Characters" / f"{m['skin']}.png"
    return found


_measures = {}


def _measure(path):
    key = (str(path), Path(path).stat().st_mtime_ns)
    if key not in _measures:
        _measures[key] = parts.measure(_rgba(path))
    return _measures[key]


def nearest(body, skip=None, skin=None):
    """How close this body comes to everyone on the list, part by part: {part: (distance, who)}."""
    mine = parts.measure(body)
    closest = {}
    for name, path in character_list(skip).items():
        if name == skin:
            continue
        for part, d in parts.differences(mine, _measure(path)).items():
            if part not in closest or d < closest[part][0]:
                closest[part] = (d, name)
    return closest


def start_limits():
    """From the roster's own closest pairs. The five closest for hair are the ones players said were hard to tell apart, so
    the limit is the next pair up. The closest pair for face wears the same face, so the limit sits just under the next."""
    measures = {n: parts.measure(_rgba(SPRITES / f"{n}.png")) for n in ROSTER}
    pairs = [parts.differences(measures[a], measures[b]) for i, a in enumerate(ROSTER) for b in ROSTER[i + 1:]]
    hair, face = sorted(p["hair"] for p in pairs), sorted(p["face"] for p in pairs)
    return {"hair": round(hair[5], 1), "face": round(face[1] * 0.9, 1), "skin": SKIN_LIMIT}


def limits():
    if not LIMITS.exists():
        LIMITS.write_text(json.dumps(start_limits(), indent=1), encoding="utf-8")
    return json.loads(LIMITS.read_text(encoding="utf-8"))


def set_limits():
    """Rewrites limits.json from what David approved. An approved character closer than the limit proves that much closeness
    is fine with him, so the limit comes down to it. It never rises past where the roster started it."""
    new = start_limits()
    for folder, m in submissions("approve"):
        if m.get("kind") != "character":
            continue
        closest = nearest(_rgba(Path(folder) / "Sprites" / "Characters" / f"{m['skin']}.png"), Path(folder), m["skin"])
        for part in ("hair", "face"):
            if part in closest:
                new[part] = min(new[part], round(closest[part][0], 1))
    LIMITS.write_text(json.dumps(new, indent=1), encoding="utf-8")
    return new


def game_slot_limit():
    """The highest playerN the game looks for, read from its own loop so this can't drift from the code."""
    found = re.findall(r"index\s*<=\s*(\d+)", GAME_MANAGER.read_text(encoding="utf-8"))
    if not found:
        raise ValueError("no 'index <=' loop in GameManager.cs")
    return min(int(v) for v in found)


def taken_names(skip=None):
    """First names already on the list, lower case: the game's, and every submission David hasn't rejected."""
    names = {str(v).lower() for v in (_load(NAMES_FILE, {}) or {}).get("names", {}).values()}
    for folder, m in submissions():
        if Path(folder) == skip or _is_rejected(folder):
            continue
        if m.get("first_name"):
            names.add(str(m["first_name"]).lower())
        names |= {str(v).lower() for v in (m.get("names") or {}).values()}
    return names


def _png_problem(png):
    try:
        with Image.open(png) as im:
            size = im.size
            im.verify()
    except Exception:
        return f"Write {png.name} again: it can't be read as a PNG."
    return None if size == (1024, 1024) else f"Make {png.name} 1024x1024."


def _meta_rect(meta):
    return tuple(re.search(rf"\n        {f}: (\S+)", meta).group(1) for f in ("x", "y", "width", "height"))


def _briefs(img):
    """The white of the briefs: pale in every channel, and far below the head."""
    rgb = img[..., :3].astype(int)
    pale = (img[..., 3] > 128) & (rgb.min(axis=2) > 190) & (np.abs(rgb[..., 0] - rgb[..., 2]) < 30)
    pale[:BRIEFS_ROW] = False
    return pale


def _frame_problems(folder, skin):
    problems = []
    for subfolder, tag, count in ANIMATIONS:
        rects = set()
        for k in range(count):
            png = folder / "Resources" / subfolder / f"{skin}_{tag}_{k:02}.png"
            meta = png.with_suffix(".png.meta")
            if not png.exists() or not meta.exists():
                problems.append(f"Write {png.name} and its .meta.")
                continue
            problem = _png_problem(png)
            if problem:
                problems.append(problem)
            rects.add(_meta_rect(meta.read_text(encoding="utf-8")))
        if len(rects) > 1:
            problems.append(f"Use one sprite rect for all {count} {tag} frames, or the body jumps during the animation.")
    for suffix in ("splat", "splatchar"):
        png = folder / "Resources" / "DeathSplat" / f"{skin}_{suffix}.png"
        if not png.exists() or not png.with_suffix(".png.meta").exists():
            problems.append(f"Write {png.name} and its .meta.")
        else:
            problem = _png_problem(png)
            if problem:
                problems.append(problem)
    return problems


def _guid_problems(folder):
    """Every meta needs its own guid, or Unity sees two files as one asset."""
    problems, guids = [], {}
    for meta in folder.rglob("*.meta"):
        found = re.search(r"\nguid: (\S+)", meta.read_text(encoding="utf-8"))
        if not found:
            problems.append(f"Write {meta.name} again: it has no guid.")
        elif found.group(1) in guids:
            problems.append(f"Give {meta.name} its own guid: {guids[found.group(1)]} has the same one.")
        else:
            guids[found.group(1)] = meta.name
    return problems


def _body_problems(body, template, baseline):
    """The chubby body, the white briefs and the skin all belong to one person."""
    problems = []
    p = parts.of(body)
    if parts.head_skin_share(body, p) < MIN_HEAD_SKIN:
        problems.append("Make the head's skin match the body's: the face box shows almost none of the torso's skin tone.")
    mine, theirs = body[BODY_ROW:, :, 3] > 0, template[BODY_ROW:, :, 3] > 0
    if baseline:
        if (mine & theirs).sum() / max((mine | theirs).sum(), 1) < BASELINE_OVERLAP:
            problems.append("Keep the body's silhouette: pixels below the neck changed shape.")
        if abs(int(_briefs(body).sum()) / int(_briefs(template).sum()) - 1) > BASELINE_BRIEFS:
            problems.append("Keep the white briefs: they're a different size from the template's.")
        return problems
    # The body below the neck is shared by every character; hats, cheeks and the uzi depend on it.
    if np.any(mine != theirs):
        problems.append("Keep the body's silhouette: pixels below the neck changed shape.")
    briefs = _briefs(template)
    if np.any(body[briefs] != template[briefs]):
        problems.append("Keep the white briefs: they must match the template's pixels exactly.")
    return problems


def _difference_problems(folder, m, body, template):
    """Skin, hair and face each have to be new on their own, so a new skin tone alone can't pass."""
    problems = []
    x0, y0, x1, y1 = HEAD_BOX
    outside = (template[y0:y1, x0:x1, 3] < 128) & (body[y0:y1, x0:x1, 3] > 128)
    hair_colors = {tuple(c) for c in body[y0:y1, x0:x1, :3][outside]}
    if len(hair_colors) > MAX_HAIR_COLORS:
        problems.append(f"Use fewer colors in the hair: {len(hair_colors)} found, {MAX_HAIR_COLORS} at most.")

    limit = limits()
    closest = nearest(body, folder, m["skin"])
    for part, words in (("hair", "the hair"), ("face", "the face")):
        d, who = closest[part]
        if d < limit[part]:
            problems.append(f"Make {words} look less like {who}'s: difference {d:.1f}, needs at least {limit[part]}.")
    originals = [_measure(SPRITES / f"{n}.png")["skin"] for n in ROSTER]
    skin = parts.of(body)["skin"]
    if min(float(np.abs(skin - o).mean()) for o in originals) < limit["skin"]:
        problems.append("Use a new skin tone: this one is the original ten's.")
    return problems


def _name_problems(folder, m):
    first = str(m.get("first_name") or "").strip()
    if not first:
        return ["Give this character a first name: every new character needs one, in the manifest's first_name."]
    if first.lower() in taken_names(folder):
        return [f"Pick another first name: {first} is already on the list."]
    return []


def _fit_problems(m):
    """The splat and shades land on these numbers. The slot only has to be a number: DAVID, 2026-11-03, characters are all
    generated first, so one can sit past the last slot the game loads today."""
    problems = []
    if not isinstance(m.get("slot"), int):
        problems.append(f"Give the character a numbered slot: '{m.get('slot')}' isn't one.")
    face = m.get("face") or {}
    if len(face.get("eyes") or []) != 2 or len(face.get("mouth") or []) != 2:
        problems.append("Record both eye positions and the mouth position in the manifest's face: the splat and shades land on them.")
    return problems


def _check_character(folder, baseline):
    problems = []
    manifest_path = folder / "manifest.json"
    if not manifest_path.exists():
        return ["Write manifest.json: there is none in the submission."]
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    for field in ("kind", "name", "slot", "skin", "files", "previews", "concept"):
        if field not in m:
            problems.append(f"Add '{field}' to manifest.json.")
    if problems:
        return problems
    skin = m["skin"]
    if not re.fullmatch(r"player\d*" if baseline else r"player\d+", skin):
        problems.append(f"Name the skin playerN: '{skin}' won't be found by the game's roster scan.")
    for rel in list(m["files"]) + list(m["previews"]):
        if not (folder / rel).exists():
            problems.append(f"Write {rel}: the manifest lists it but it isn't there.")
    if not baseline:
        problems += _name_problems(folder, m) + _fit_problems(m)
    problems += _frame_problems(folder, skin) + _guid_problems(folder)

    body_path = folder / "Sprites" / "Characters" / f"{skin}.png"
    if not body_path.exists() or not body_path.with_suffix(".png.meta").exists():
        return problems + [f"Write the body sprite and its .meta: {body_path.name} is missing."]
    body = _rgba(body_path)
    template = _rgba(SPRITES / f"{TEMPLATE}.png")
    if body.shape != template.shape:
        return problems + [f"Make the body {template.shape[1]}x{template.shape[0]}: it is {body.shape[1]}x{body.shape[0]}."]
    problems += _body_problems(body, template, baseline)
    if not baseline:
        problems += _difference_problems(folder, m, body, template)
    return problems


def check_character(folder, baseline=False):
    """One character's files. baseline skips the name, new-face and difference checks, for the original ten."""
    try:
        return _check_character(Path(folder), baseline)
    except Exception as e:
        return [f"Write the submission again: the check couldn't run on it ({type(e).__name__}: {e})."]


def check_chunk_plan(tasks, chunk, rule):
    """The Orchestrator's drafted plan against the agent's rulebook: the right number of tasks, each one different."""
    try:
        wanted = chunk["units"]
        if wanted > max(rule.get("chunk_size", wanted), rule.get("first_stop", wanted)):
            return [f"Plan a smaller chunk: {wanted} units is more than this agent's rulebook allows."]
        problems = []
        if len(tasks) != wanted:
            problems.append(f"Plan exactly {wanted} tasks: this plan has {len(tasks)}.")
        briefs = [str(t.get("brief") or "").strip().lower() for t in tasks]
        if not all(briefs):
            problems.append("Give every task a brief.")
        if len(set(briefs)) != len(briefs):
            problems.append("Make every task's brief different: two of them ask for the same thing.")
        return problems
    except Exception as e:
        return [f"Write the plan again: the check couldn't run on it ({type(e).__name__}: {e})."]


def character_facts(folder):
    """The numbers the run report, the daily page and the Critic get."""
    folder = Path(folder)
    m = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    body = _rgba(folder / "Sprites" / "Characters" / f"{m['skin']}.png")
    closest = nearest(body, folder, m["skin"])
    whole = {n: distance(body, _rgba(p)) for n, p in character_list(folder).items() if n != m["skin"]}
    who = min(whole, key=whole.get)

    def size(where, listed):
        return sum((Path(where) / rel).stat().st_size for rel in listed if (Path(where) / rel).exists())

    mine = size(folder, m["files"])
    others = sum(size(f, o.get("files", [])) for f, o in submissions() if Path(f) != folder and not _is_rejected(f))
    return {"nearest_roster": who, "difference_from_nearest": round(whole[who], 1),
            "hair_distance": round(closest["hair"][0], 1), "nearest_hair": closest["hair"][1],
            "face_distance": round(closest["face"][0], 1), "nearest_face": closest["face"][1],
            "skin_distance": round(closest["skin"][0], 1), "nearest_skin": closest["skin"][1],
            "size_mb": round(mine / 1e6, 2), "running_total_mb": round((mine + others) / 1e6, 2)}


facts = character_facts


if __name__ == "__main__":
    # Prints how far apart the roster is from itself, the numbers the limits start from, or checks one folder.
    if len(sys.argv) > 1:
        print(check_character(sys.argv[1]) or "pass", character_facts(sys.argv[1]))
    else:
        print("limits:", limits())
        print("game loads up to slot", game_slot_limit())


# ── backgrounds (C:\cluster\crew\BACKGROUNDS_METHOD.md) ────────────────────────────────────────────────────────────
BACKGROUND_ROOTS = [Path(r"C:\cluster\submissions\backgrounds"), Path(r"C:\cluster\approved\backgrounds")]
BACKGROUND_LIMIT = 20.0      # mean color difference, at a small size, from every other background
LINE_LIMIT = 0.6             # a column jumping sharply over this share of the height reads as a vertical line
LAYER_SIZE = (576, 324)
HOLE_MAX = 25                # an enclosed see-through spot this many pixels or fewer, inside an object's box, is a hole


def _line_score(rgb):
    lum = rgb.astype(float) @ np.array([0.30, 0.59, 0.11])
    return (np.abs(np.diff(lum, axis=1)) > 40).mean(axis=0)


def _over_gray(rgba):
    out = np.full(rgba.shape[:2] + (3,), 128.0)
    a = rgba[..., 3:4] / 255.0
    return out * (1 - a) + rgba[..., :3] * a


def _small(path):
    return np.array(Image.open(path).convert("RGB").resize((144, 81), Image.LANCZOS)).astype(float)


def _others(folder):
    for root in BACKGROUND_ROOTS:
        for p in sorted(root.glob("*/preview_1_whole.png")) if root.exists() else []:
            if p.parent.resolve() != Path(folder).resolve():
                yield p.parent.name, p


def _check_background(folder):
    from objects import is_key
    from scipy import ndimage
    folder = Path(folder)
    m = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    files = list(m.get("files") or [])
    if not files or files[0] != "00.png":
        return ["List the layers in files, starting with 00.png, the sky."]
    speeds = [l.get("speed", 0) for l in json.loads((folder / "recipe.json").read_text(encoding="utf-8"))["layers"]]
    problems, stack = [], []
    for name in files:
        a = np.array(Image.open(folder / name).convert("RGBA"))
        if (a.shape[1], a.shape[0]) != LAYER_SIZE:
            problems.append(f"Make {name} {LAYER_SIZE[0]}x{LAYER_SIZE[1]}: it is {a.shape[1]}x{a.shape[0]}.")
            continue
        stack.append((name, a))
        if np.abs(a[:, :2].astype(float) - a[:, -2:][:, ::-1]).mean() >= 30:
            problems.append(f"Make {name} wrap: its left and right edges don't meet.")
        if _line_score(_over_gray(np.roll(a, a.shape[1] // 2, axis=1))).max() >= LINE_LIMIT:
            problems.append(f"Take the vertical line out of {name}: it shows while the layer moves.")
        if name == "00.png":
            if (a[..., 3] < 255).any():
                problems.append("Make the sky, 00.png, solid: it has see-through pixels.")
            continue
        alpha = a[..., 3] > 0
        if int((is_key(a[..., :3].astype(float)) & alpha).sum()) > 3:
            problems.append(f"Take the green out of {name}: key color was left on it.")
        lab, n = ndimage.label(a[..., 3] >= 128)
        if n and min(ndimage.sum(a[..., 3] >= 128, lab, range(1, n + 1))) < 4:
            problems.append(f"Remove the loose specks on {name}.")
    by_name = dict(stack)
    for p in m.get("placements") or []:
        a = by_name.get(p["layer"])
        if a is None:
            continue
        box = np.roll(a[..., 3] > 0, -p["x"], axis=1)[max(0, p["top"]):p["top"] + p["height"], :p["width"]]
        holes = ndimage.binary_fill_holes(box) & ~box
        lab, n = ndimage.label(holes)
        if n and any(s <= HOLE_MAX for s in ndimage.sum(holes, lab, range(1, n + 1))):
            problems.append(f"Fill the hole inside the object at x {p['x']} on {p['layer']}.")
        if p["lowest_row"] < p["ground_row"]:
            problems.append(f"Stand the object at x {p['x']} on {p['layer']} on its ground: it floats.")
    if stack and len(speeds) == len(stack) and not problems:
        moving = [s for s in speeds if s > 0]
        period = LAYER_SIZE[0] / min(moving) if moving else LAYER_SIZE[0]
        for t in np.linspace(0, period, 240, endpoint=False):
            out = np.zeros(stack[0][1].shape[:2] + (3,))
            for (name, a), s in zip(stack, speeds):
                r = np.roll(a, -int(round(t * s)) % a.shape[1], axis=1).astype(float)
                k = r[..., 3:4] / 255.0
                out = out * (1 - k) + r[..., :3] * k
            if _line_score(out).max() >= LINE_LIMIT:
                problems.append(f"Take out the vertical line that shows while the layers move (at t {t:.0f}).")
                break
    preview = folder / "preview_1_whole.png"
    if preview.exists():
        mine = _small(preview)
        for name, p in _others(folder):
            d = float(np.abs(mine - _small(p)).mean())
            if d < BACKGROUND_LIMIT:
                problems.append(f"Make it more different from {name}: difference {d:.1f}, needs at least {BACKGROUND_LIMIT}.")
                break
    return problems


def check_background(folder):
    """Every check in BACKGROUNDS_METHOD.md, each failure an instruction. A check that can't run is a fail."""
    try:
        return _check_background(folder)
    except Exception as e:
        return [f"Build the background again: the check couldn't run on it ({type(e).__name__}: {e})."]


def background_facts(folder):
    folder = Path(folder)
    m = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    mine = _small(folder / "preview_1_whole.png")
    nearest, diff = None, None
    for name, p in _others(folder):
        d = float(np.abs(mine - _small(p)).mean())
        if diff is None or d < diff:
            nearest, diff = name, d
    size = sum((folder / f).stat().st_size for f in m["files"] if (folder / f).exists())
    return {"nearest_background": nearest, "difference": None if diff is None else round(diff, 1), "layers": len(m["files"]),
            "size_mb": round(size / 1e6, 2)}


# ---------- Roast lines (C:\cluster\ROAST_WRITER_DESIGN.md, section 5) ----------
# The rules come from the 40 lines David kept: every one of them passes these checks.

ROAST_MAX_WORDS = 15            # the longest kept line is 14
ROAST_ID = re.compile(r"^rw_[A-Za-z]+_\d{3}$")
ROAST_CHARS = re.compile(r"^[A-Za-z0-9 .,'’;:-]+$")   # periods only: no ! ? quotes or emoji
# The gross thing is never named.
ROAST_BANNED = {"poo", "poos", "poop", "poops", "pooped", "pooping", "poopy", "fart", "farts", "farted", "farting", "farty",
                "crap", "crapped", "crapping", "shit", "shits", "shat", "turd", "turds", "dung", "feces", "faeces", "diarrhea",
                "diarrhoea", "pee", "peed", "piss", "pissed", "bowel", "bowels", "stool", "stools", "excrement", "manure"}
# Nothing about a character's body, race or background: every line has to fit any character.
ROAST_BODY = {"fat", "fatty", "fatso", "chubby", "obese", "tubby", "pudgy", "belly", "bellies", "gut", "black", "white",
              "brown", "asian", "latino", "hispanic", "mexican", "african", "indian", "chinese", "jewish", "muslim", "arab",
              "irish", "italian", "russian", "gay", "old", "bald"}
# Poo, toilets and smell: a line with one of these is kept out of Gauntlet (as "Flushed", "cleanup crew", "bad curry",
# "plumber" and "smell" are in the kept lines).
ROAST_SMELL = {"smell", "smells", "smelled", "smelly", "stink", "stinks", "stank", "stinky", "stench", "reek", "reeks",
               "reeked", "odor", "odors", "whiff", "fumes", "toilet", "toilets", "porcelain", "flush", "flushed", "flushing",
               "plumber", "plumbers", "plumbing", "sewer", "sewers", "sewage", "bowl", "cleanup", "curry", "filthy", "filth",
               "caked", "splat", "splats", "splatted", "splatter", "mess", "messy", "stain", "stains", "stained", "wipe",
               "wipes", "wiped", "bathroom", "restroom", "loo", "latrine", "outhouse", "plunger", "septic", "deposit"}
ROAST_STOP = {"the", "a", "an", "of", "to", "and", "in", "on", "at", "it", "is", "that", "this", "you", "your", "was", "for",
              "with", "as", "be", "are", "by", "but", "not", "so", "up", "out", "no", "one", "all", "very", "more", "than",
              "some", "has", "have", "had", "will", "just"}
ROAST_REPEAT = 0.5              # share of content words two lines share before one is a repeat of the other


def roast_words(text):
    return re.findall(r"[a-z0-9']+", text.lower().replace("’", "'"))


def similar_lines(a, b):
    """True when b is a copy or near-copy of a: half or more of their content words are shared."""
    wa = {w for w in roast_words(a) if w not in ROAST_STOP}
    wb = {w for w in roast_words(b) if w not in ROAST_STOP}
    if not wa or not wb:
        return roast_words(a) == roast_words(b)
    return len(wa & wb) / len(wa | wb) >= ROAST_REPEAT


def needs_gauntlet(text, always):
    """A line kept out of Gauntlet: every line of a splat event, and any line about poo, toilets or smell."""
    return bool(always) or any(w in ROAST_SMELL for w in roast_words(text))


def check_roast_line(line, events, known, taken):
    """The Bridge's checks on one roast line. events: id -> (on the card, happens when, always out of Gauntlet, outcomes).
    known: texts it must not repeat. taken: ids already used. Returns the problems, empty if it passes."""
    problems = []
    text = line.get("text")
    if not isinstance(text, str) or not text.strip():
        return ["the line has no text"]
    for field in ("id", "topic", "outcome", "noGauntlet", "placeholder"):
        if field not in line:
            problems.append(f"the line has no {field}")
    topic, outcome = line.get("topic"), line.get("outcome")
    if topic not in events:
        problems.append(f"the event {topic!r} isn't one the Roast Writer writes for")
    elif outcome not in events[topic][3]:
        problems.append(f"the event {topic!r} can't have the outcome {outcome!r}")
    if not ROAST_ID.match(line.get("id") or ""):
        problems.append(f"the id {line.get('id')!r} isn't rw_<event>_<number>")
    elif line["id"] in taken:
        problems.append(f"the id {line['id']} is already used, and replays store ids")
    words = text.split()
    if len(words) > ROAST_MAX_WORDS:
        problems.append(f"{len(words)} words, more than {ROAST_MAX_WORDS}")
    if not text.endswith(".") or not ROAST_CHARS.match(text):
        problems.append("it has to end in a period, with no ! ? quotes or emoji")
    if sum(1 for w in re.findall(r"[A-Za-z]+", text) if len(w) > 1 and w.isupper()) > 1:
        problems.append("more than one word in capitals")
    found = [w for w in roast_words(text) if w in ROAST_BANNED]
    if found:
        problems.append(f"the gross thing is never named ({', '.join(found)})")
    found = [w for w in roast_words(text) if w in ROAST_BODY]
    if found:
        problems.append(f"nothing about a character's body, race or background ({', '.join(found)})")
    for sentence in re.split(r"(?<=[.;:])\s+", text):
        names = [w for w in sentence.split()[1:] if w[:1].isupper() and not w.strip(".,;:'’").isupper()]
        if names:
            problems.append(f"no names: it has to fit any character ({', '.join(names)})")
            break
    if topic in events and not line.get("noGauntlet") and needs_gauntlet(text, events[topic][2]):
        problems.append("it's about poo, toilets or smell, so it needs the Gauntlet flag")
    if any(similar_lines(k, text) for k in known):
        problems.append("a repeat of a line that's already there")
    return problems


# ---------- Wardrobe items (C:\cluster\WARDROBE_STYLIST_DESIGN.md, section 5) ----------
# The rules come from the 4 items in the game: every one of them passes these checks.

WARDROBE_MIN_AREA = 6          # fill pixels a hat's color area needs to show its color, at art resolution
WARDROBE_MIN_PIXELS = {"hat": 60, "shades": 20}
WARDROBE_BRIM_PIXELS = 4       # a hat touches the head: this many pixels in its bottom two rows
WARDROBE_LENS_GAP = (5, 11)    # art pixels between the two lens centers (8 on the 4 in the game: 12 on the design grid)
WARDROBE_DIFF = 10.0           # percent of pixels that must differ from every other item of the same kind


def _number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float("inf")


def _rgb(v):
    return isinstance(v, list) and len(v) == 3 and all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 255 for c in v)


def check_wardrobe_recipe(r):
    """Whether a recipe can be drawn and follows the method's rules. Returns the problems, empty if it passes."""
    import wardrobe_stylist as ws
    if not isinstance(r, dict):
        return ["the recipe isn't a JSON object"]
    kind = r.get("kind")
    if kind not in ws.BOX:
        return [f"kind is {kind!r}, not hat or shades"]
    problems = []
    name = r.get("name")
    if not isinstance(name, str) or not name.strip() or len(name) > 40 or "." in name:
        problems.append("the name has to be 1 to 40 characters with no periods")
    regions = r.get("regions")
    if not isinstance(regions, list) or not regions:
        return problems + ["no regions"]
    ids = set()
    for g in regions:
        if not isinstance(g, dict) or not isinstance(g.get("id"), int) or isinstance(g.get("id"), bool) or not 1 <= g["id"] <= 30:
            problems.append(f"a region's id isn't a number from 1 to 30: {g!r}"[:200])
            continue
        if g["id"] in ids:
            problems.append(f"region {g['id']} is defined twice")
        ids.add(g["id"])
        if not isinstance(g.get("name"), str) or not g["name"].strip():
            problems.append(f"region {g['id']} has no name")
        if not _rgb(g.get("color")):
            problems.append(f"region {g['id']}'s color isn't [red, green, blue] from 0 to 255")
    colorable = {g["id"] for g in regions if isinstance(g, dict) and g.get("colorable") and isinstance(g.get("id"), int)}
    if kind == "hat" and (not colorable or not colorable <= {1, 2, 3}):
        problems.append("a hat has 1 to 3 color areas, numbered 1, 2 and 3")
    if kind == "shades" and colorable:
        problems.append("shades take no color areas")
    if r.get("outline") is not None and not _rgb(r["outline"]):
        problems.append("the outline color isn't [red, green, blue]")
    shapes = r.get("shapes")
    if not isinstance(shapes, list) or not shapes:
        return problems + ["no shapes"]
    gw, gh = ws.GRID[kind]
    for k, s in enumerate(shapes, 1):
        if not isinstance(s, dict) or s.get("shape") not in ws.SHAPES:
            problems.append(f"shape {k} isn't one of {', '.join(ws.SHAPES)}")
            continue
        if s.get("region") != 0 and s.get("region") not in ids:
            problems.append(f"shape {k} fills region {s.get('region')!r}, which isn't defined")
        if s["shape"] in ("poly", "line"):
            pts = s.get("points")
            least = 3 if s["shape"] == "poly" else 2
            if not (isinstance(pts, list) and len(pts) >= least
                    and all(isinstance(p, list) and len(p) == 2 and all(_number(v) for v in p) for p in pts)):
                problems.append(f"shape {k} needs at least {least} [x, y] points")
                continue
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            if s["shape"] == "line" and not (isinstance(s.get("width"), int) and 1 <= s["width"] <= 6):
                problems.append(f"shape {k} is a line with a width that isn't 1 to 6")
        else:
            box = s.get("box")
            if not (isinstance(box, list) and len(box) == 4 and all(_number(v) for v in box)):
                problems.append(f"shape {k} needs a box [left, top, right, bottom]")
                continue
            if box[0] > box[2] or box[1] > box[3]:
                problems.append(f"shape {k}'s box is drawn backwards")
                continue
            xs, ys = [box[0], box[2]], [box[1], box[3]]
        if min(xs) < -4 or max(xs) > gw + 4 or min(ys) < -4 or max(ys) > gh + 4:
            problems.append(f"shape {k} goes off the {round(gw)} by {round(gh)} grid")
    return problems


def check_wardrobe_art(r):
    """The drawn item, at art resolution: every region shows, color areas big enough to color, flat fills, outlined, a
    hat touching the head, shades with a lens on each eye. Only for a recipe that passed check_wardrobe_recipe."""
    import wardrobe_stylist as ws
    art, mask, labels = ws.draw(r)
    a = np.asarray(art)
    lab = np.asarray(labels)
    opaque = a[:, :, 3] > 0
    problems = []
    outline = tuple(r["outline"]) if r.get("outline") else (22, 18, 18)
    is_outline = opaque & np.all(a[:, :, :3] == outline, axis=2)
    for g in r["regions"]:
        here = lab == g["id"]
        if not here.any():
            problems.append(f"region {g['id']} ({g['name']}) has no pixels: later shapes cover it or it's off the box")
        elif r["kind"] == "hat" and g.get("colorable") and int((here & ~is_outline).sum()) < WARDROBE_MIN_AREA:
            problems.append(f"the color area {g['name']} is too small to see its color")
    if int(opaque.sum()) < WARDROBE_MIN_PIXELS[r["kind"]]:
        problems.append(f"only {int(opaque.sum())} pixels: too small to read")
    colors = {tuple(c) for c in a[opaque][:, :3].tolist()}
    if len(colors) > len(r["regions"]) + 1:
        problems.append("more colors than its regions and outline: fills have to be flat")
    padded = np.pad(opaque, 1)
    edge = opaque & ~(padded[:-2, 1:-1] & padded[2:, 1:-1] & padded[1:-1, :-2] & padded[1:-1, 2:])
    if not np.all(is_outline[edge]):
        problems.append("the outline doesn't go all the way round")
    if r["kind"] == "hat" and int(opaque[-2:].sum()) < WARDROBE_BRIM_PIXELS:
        problems.append("the hat doesn't reach the bottom of its box, so it would float above the head")
    if r["kind"] == "shades":
        w = opaque.shape[1]
        centers = []
        for x0, x1 in ((0, w // 2), (w // 2, w)):
            xs = np.nonzero(opaque[:, x0:x1])[1]
            centers.append(xs.mean() + x0 if len(xs) else None)
        if None in centers:
            problems.append("shades need a lens on each side, one for each eye")
        elif not WARDROBE_LENS_GAP[0] <= centers[1] - centers[0] <= WARDROBE_LENS_GAP[1]:
            problems.append(f"the lens centers are {centers[1] - centers[0]:.1f} pixels apart; the eyes need about 8")
    return problems


def wardrobe_difference(a, b):
    """Percent of pixels that differ between two items of one kind at art resolution: drawn in one and not the other, or
    drawn in both in clearly different colors."""
    a, b = np.asarray(a).astype(int), np.asarray(b).astype(int)
    oa, ob = a[:, :, 3] > 0, b[:, :, 3] > 0
    far = np.abs(a[:, :, :3] - b[:, :, :3]).sum(axis=2) > 60
    return round(100.0 * float(((oa != ob) | (oa & ob & far)).sum()) / max(1, int((oa | ob).sum())), 1)


def _wardrobe_others(folder):
    """(name, recipe) of every other item: the 4 in the game and the Wardrobe Stylist's own."""
    import wardrobe_stylist as ws
    others = [(r["name"], r) for r in ws.EXAMPLES.values()]
    for f, m, _ in ws.items():
        if Path(f).resolve() != Path(folder).resolve():
            r = _load(f / "recipe.json")
            if r:
                others.append((m["name"], r))
    return others


def wardrobe_names(folder):
    """Names a new item can't take: the game's, and every other item's except one David rejected, whose redo keeps its name
    (run 20261107-164801: the Top Hat's redo, from David's note "its upside down", was sent back as "the name Top Hat is taken"
    by the Top Hat he'd rejected, and lost both cheeks)."""
    import wardrobe_stylist as ws
    names = {i["name"].lower() for i in ws.game_items()} | {r["name"].lower() for r in ws.EXAMPLES.values()}
    for f, m, d in ws.items():
        if Path(f).resolve() != Path(folder).resolve() and not (d and d.get("decision") == "reject"):
            names.add(str(m.get("name", "")).lower())
    return names


def wardrobe_facts(folder):
    """The nearest other item of the same kind and how different it is, and the files' size."""
    import wardrobe_stylist as ws
    folder = Path(folder)
    r = _load(folder / "recipe.json")
    art = ws.draw(r)[0]
    nearest, diff = None, None
    for name, other in _wardrobe_others(folder):
        if other["kind"] == r["kind"]:
            d = wardrobe_difference(art, ws.draw(other)[0])
            if diff is None or d < diff:
                nearest, diff = name, d
    m = _load(folder / "manifest.json") or {}
    size = sum((folder / f).stat().st_size for f in m.get("files", []) + m.get("previews", []) if (folder / f).exists())
    return {"nearest_item": nearest, "difference": diff, "size_kb": round(size / 1024)}


def check_wardrobe_item(folder):
    """Every check on one item's folder: the recipe, the art drawn from it, the files matching it, a place on every
    character, a name nobody else has, and a measured difference from every other item."""
    import wardrobe_stylist as ws
    folder = Path(folder)
    m, r = _load(folder / "manifest.json"), _load(folder / "recipe.json")
    if not m or not r:
        return ["the manifest or the recipe is missing"]
    problems = check_wardrobe_recipe(r)
    if problems:
        return problems
    problems = check_wardrobe_art(r)
    art, mask, _ = ws.draw(r)
    for f, want in ((f"{m['item']}.png", art), (f"{m['item']}_mask.png", mask)):
        if want is None:
            continue
        try:
            same = np.array_equal(np.asarray(Image.open(folder / f).convert("RGBA")),
                                  np.asarray(ws.full_size(want).convert("RGBA")))
        except OSError:
            same = False
        if not same:
            problems.append(f"{f} doesn't match its recipe")
    for f in m.get("previews", []):
        if not (folder / f).is_file():
            problems.append(f"the preview {f} is missing")
    missed = [skin for skin, ok in (m.get("fit") or {}).items() if not ok]
    if missed or not m.get("fit"):
        problems.append(f"it couldn't be placed on {', '.join(missed) or 'any character'}")
    if r["name"].lower() in wardrobe_names(folder):
        problems.append(f"the name {r['name']} is taken")
    facts = wardrobe_facts(folder)
    if facts["difference"] is not None and facts["difference"] < WARDROBE_DIFF:
        problems.append(f"too like {facts['nearest_item']}: only {facts['difference']}% different")
    return problems
