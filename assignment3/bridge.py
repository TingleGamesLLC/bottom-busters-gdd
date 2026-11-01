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
    """The splat and shades land on these numbers, and the game only looks so far up the slots."""
    problems = []
    top = game_slot_limit()
    if not isinstance(m.get("slot"), int) or m["slot"] > top:
        problems.append(f"Use a slot within the game's limit: {m.get('slot')} is past player{top}, the last one the game loads.")
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
