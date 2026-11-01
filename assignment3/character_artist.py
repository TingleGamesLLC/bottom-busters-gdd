"""Character Artist: one new playable character, from a concept to files the game can load.

DAVID, 2026-10-31: "same chubby body and white briefs, change skin tone, faces and hair." The new characters come in sets of
ten, one set at a time (sets.json), and every character gets a first name.

Two steps, as in the class notes (concept agent, then asset agent):
1. Concept. The cluster's writer model proposes a first name and a look that can be told apart from the roster.
2. Asset. PixelLab paints the hair, beard and face onto a bald, blank-faced copy of the template body, on the body's own pixel
   grid, and keeps every pixel outside the mask. The body stays the template's pixels, which is what keeps hats, cheeks and
   the uzi lined up, as with the original ten. Plain code then measures where the eyes and mouth landed.

The animations aren't drawn by a model. The 12 flail frames are the template's own frames wearing the new head, the idle and
flap frames come from idle_game.py and flap_game.py, and the splat pair comes from splat_faces.py, the tools that made the
original ten. Those tools only work on skin as light as the template's, so they run on the light body and the frames move to
the character's tone afterward.
"""
import io
import json
import re
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

import bridge
import common
import parts
import pixellab

sys.path.insert(0, r"C:\bbust\CoverArt\tools")
import flail  # noqa: E402
import flap_game  # noqa: E402
import idle_game  # noqa: E402
import splat_faces  # noqa: E402

ASSETS = Path(r"C:\bbust\BBUST\Assets")
SPRITES = ASSETS / "Sprites" / "Characters"
FLAIL_DIR = ASSETS / "Resources" / "DeathFlail"
PREFABS = ASSETS / "Resources" / "Prefabs"
ROSTER = json.loads((Path(__file__).with_name("roster.json")).read_text(encoding="utf-8"))
SETS = json.loads((Path(__file__).with_name("sets.json")).read_text(encoding="utf-8"))
SET_SIZE = 10
ORIGINALS = ["player"] + [f"player{i}" for i in range(2, 11)]

TEMPLATE = "player"
GRID = 88                     # PixelLab paints on the sprite's own grid, this many cells a side
MIN_HAIR_CELLS = 100          # fewer than this doesn't read at game size
MARK = (255, 0, 255, 255)     # painted on the hair for a second pass through the art tools; see toned_frames
OUTLINE = (12, 8, 8, 255)
WHITE = (245, 245, 245, 255)
SKIN_FLOOR = 30.0
OUTLINE_LUM = 60              # darker than this on the template is its outline
HEAD_RIGHT_LIMIT = 60         # no cell of the head on the face's rows is this far right

# Skin tones by what the template's base skin becomes. The hue of every skin shade moves with it.
SKIN_BASE = (239, 194, 158)
TONES = {"default": SKIN_BASE, "pale": (250, 222, 203), "tan": (214, 163, 118), "olive": (190, 152, 104),
         "brown": (150, 101, 70), "deep": (104, 68, 48), "sunburn": (244, 148, 118),
         "ivory": (247, 212, 176), "sand": (224, 180, 132), "honey": (226, 178, 130), "golden": (205, 155, 105),
         "caramel": (178, 126, 84), "copper": (186, 120, 82), "bronze": (160, 110, 72), "chestnut": (128, 84, 58),
         "espresso": (84, 56, 42)}

# The plain-code side of DAVID's line, "comically stereotypical but not offensive". He approves every name; these catch what
# should never reach him: a name that's just the group, or a joke instead of a name, or art that leans on a caricature.
GROUP_WORDS = ("african", "american", "black", "asian", "chinese", "japanese", "korean", "oriental", "islander", "polynesian", "hawaiian",
               "samoan", "hispanic", "latino", "latina", "mexican", "indian", "hindu", "arab", "arabic", "muslim", "persian", "native",
               "indigenous", "tribal", "ethnic", "white")
JOKE_NAMES = ("chief", "sensei", "amigo", "taco", "burrito", "guru", "sheikh", "homeboy", "homie", "brave", "squaw", "kung", "ninja", "samurai")
BANNED_LOOKS = ("headdress", "feather", "face paint", "war paint", "turban", "sombrero", "slanted", "buck teeth", "buck-teeth",
                "(big|huge|thick|full|fat|wide) lips", "(wide|flat|broad|big|huge|giant|hooked|long|pointy) nose",
                "hat", "glasses", "mask", "green hair")

CONCEPT_FIELDS = ["first_name", "hair", "hair_color", "beard", "beard_desc", "face", "skin_tone", "why_distinct"]
CONCEPT_SYSTEM = """You design new playable characters for Bottom Busters, a comedy arcade game where chubby men in white briefs fly by farting.
Every character has the same chubby body and the same white briefs. Only the skin tone, face and hair change. At game size a character is about 100 pixels tall, so players tell them apart by the shape and color of the hair first and the face second.
This character is one of a set of ten. The game shows no ethnicity information, just a large list of characters with first names.
The first name: a real first name you'd really hear, one word, comically stereotypical for this set, the most classic name you can think of. It's funny for being so typical, and it's never offensive. No jokes about accents or the group, no nicknames, no titles, and no words that name the group.
The face: the same cartoon treatment as every other character in the game, with no exaggerated features. Two eyes with whites and dark pupils, eyebrows, a nose and a mouth. Make it this character's own with the shape of the brows, the size of the eyes, and the expression. Don't describe the size or shape of the nose or lips.
The hair: bold silhouettes. Never green hair. No hats, glasses, masks or held objects. No real people, no characters from other games or shows, and no ethnic or religious caricature.
Answer with only one JSON object with these fields:
"first_name": the first name
"hair": a visual description of the hair shape, under 15 words
"hair_color": one plain color word
"beard": true or false
"beard_desc": a visual description of the beard under 10 words, or "" if none
"face": a visual description of the brows, eyes and expression, under 15 words
"skin_tone": one of the skin tones listed for this set
"why_distinct": one sentence on how this differs from the roster"""


def check_first_name(first):
    """A real-looking first name, or MalformedOutput saying what to change."""
    first = str(first or "").strip()
    if not re.fullmatch(r"[^\W\d_]+(['-][^\W\d_]+)?", first) or not 2 <= len(first) <= 14:
        raise common.MalformedOutput(f"'{first}' isn't a first name: it has to be one real name, one word, under 15 letters")
    if first.lower() in GROUP_WORDS or first.lower() in JOKE_NAMES:
        raise common.MalformedOutput(f"'{first}' isn't a name you'd really hear: use a real first name, never a word for the group or a joke")
    return first.capitalize() if first.islower() else first


def check_concept(data, the_set):
    """Plain code holds the rules the model can't be trusted with. Returns the concept, cleaned up."""
    data["first_name"] = check_first_name(data.get("first_name"))
    if data["first_name"].lower() in bridge.taken_names():
        raise common.MalformedOutput(f"the first name {data['first_name']} is already on the list: pick another")
    data["beard"] = data.get("beard") in (True, "true", "True", "yes")
    if "green" in str(data.get("hair_color")).lower():
        raise common.MalformedOutput("green hair is against the rules: the art step keys out a green background")
    words = " ".join(str(data.get(k)) for k in ("hair", "hair_color", "beard_desc", "face")).lower()
    for banned in BANNED_LOOKS:
        found = re.search(rf"\b{banned}\b", words)
        if found:
            raise common.MalformedOutput(f"'{found.group(0)}' is against the rules for this look: describe only hair and a plain cartoon face")
    data["set"] = the_set["name"]
    data["name"] = data["first_name"]
    return data


def current_set(task):
    """The set this task belongs to: the one it names, else the first in David's order with room left."""
    if task.get("set"):
        named = [s for s in SETS if s["name"] == task["set"]]
        if not named:
            raise common.NeedsDavid(f"the task names a set that isn't in sets.json: {task['set']}")
        return named[0]
    for candidate in SETS:
        made = [f for f, m in bridge.submissions() if m.get("set") == candidate["name"] and not bridge._is_rejected(f)]
        if len(made) < SET_SIZE:
            return candidate
    raise common.NeedsDavid("all eight sets are full: there's no set left for a new character")


def concept(brief, taken, notes, the_set, slot=0):
    roster = "\n".join(f"- {r}" for r in ROSTER + taken)
    names = ", ".join(sorted(bridge.taken_names())) or "none yet"
    text = (f"The roster today:\n{roster}\n\nFirst names already taken: {names}\n\nThis character's set: {the_set['name']}.\n"
            f"Skin tones for this set: {', '.join(the_set['tones'])}.\nHair for this set: {the_set['hair_notes']}\n\n"
            f"Your task: {brief}\nDesign one character nobody could mistake for any of those.")
    if notes:
        text += f"\nThe last attempt was sent back: {notes}\nChange the design to fix that."
    data = common.ask_json("character-artist", [{"role": "system", "content": CONCEPT_SYSTEM}, {"role": "user", "content": text}],
                           CONCEPT_FIELDS, max_tokens=800)
    data = check_concept(data, the_set)
    if data.get("skin_tone") not in the_set["tones"]:
        data["skin_tone"] = the_set["tones"][slot % len(the_set["tones"])]
    return data


# ── the head, in cells of the sprite's own pixel grid ─────────────────────────────────────────────────────────
class Head:
    """Where things are on the template, in grid cells. Measured from player.png on its fitted grid."""

    def __init__(self):
        self.g = flail.Body(TEMPLATE)
        self.t = np.array(Image.open(SPRITES / f"{TEMPLATE}.png").convert("RGBA"))
        self.cells = flail.sample_cells(self.g, self.t)
        self.ny, self.nx = self.cells.shape[:2]
        jj, ii = np.mgrid[0:self.ny, 0:self.nx]
        self.jj, self.ii = jj, ii
        # The template's own hair, cleared before anything else: the top of the head and the chunk on its left side.
        self.old_hair = ((jj <= 14) & (ii >= 33) & (ii <= 56)) | ((jj >= 15) & (jj <= 18) & (ii >= 36) & (ii <= 39))
        self.old_hair[(jj == 16) & (ii == 39)] = False   # the cheek side of the face starts here
        self.old_hair[(jj >= 17) & (ii == 39)] = False
        # The bald skull that hair sits on, and the side of the face where the old hair was.
        ellipse = ((ii - 45.2) / 7.6) ** 2 + ((jj - 15.5) / 8.2) ** 2 <= 1
        self.skull = ellipse & (jj <= 14)
        self.side_fill = self.old_hair & (jj >= 15)
        # Where hair may go: above the brow, and down both sides to the shoulders.
        self.hair_zone = ((jj <= 14) | ((jj <= 24) & ((ii <= 37) | (ii >= 53)))) & (ii >= 26) & (ii <= 64) & (jj >= 2)
        # Where a beard may go: the jaw and the top of the chest, around the mouth.
        beard = (jj >= 21) & (jj <= 29) & (ii >= 38) & (ii <= 52)
        mouth = (jj <= 24) & (ii >= 43) & (ii <= 49)
        self.beard_zone = beard & ~mouth
        self.mouth_box = [self.rect(43, 21)[0], self.rect(49, 24)[1] - 1, self.rect(43, 21)[2], self.rect(49, 24)[3] - 1]
        # The face: brows, eyes, nose and mouth. It's cleared to bare skin and painted new for every character. The head's right
        # outline runs through parts' box, so on each row the face stops short of it and the outline stays.
        self.face = np.zeros_like(self.old_hair)
        self.face_box = (jj >= parts.FACE_ROWS[0]) & (jj <= parts.FACE_ROWS[1]) & (ii >= parts.FACE_CELLS[0]) & (ii <= parts.FACE_CELLS[1])
        for j in range(parts.FACE_ROWS[0], parts.FACE_ROWS[1] + 1):
            row = self.cells[j, :HEAD_RIGHT_LIMIT]
            edge = np.nonzero((row[..., 3] > 128) & (lum(row[..., :3].astype(float)) < OUTLINE_LUM))[0].max()
            while lum(row[edge, :3].astype(float)) < OUTLINE_LUM:
                edge -= 1
            self.face[j, parts.FACE_CELLS[0]:min(parts.FACE_CELLS[1], edge) + 1] = True

    def rect(self, i, j):
        return self.g.cell_rect(i, j)

    def paint_cells(self, img, mask, colors):
        """Paint each masked cell's color onto a 1024 image. colors is a (ny, nx, 4) array or one value for every cell."""
        for j, i in zip(*np.nonzero(mask)):
            x0, x1, y0, y1 = self.rect(i, j)
            img[y0:y1, x0:x1] = colors[j, i] if isinstance(colors, np.ndarray) else colors


def bald_template(h):
    """The template with its hair and face gone, a plain skull and bare skin where the face was."""
    img = h.t.copy()
    base = tuple(int(v) for v in SKIN_BASE) + (255,)
    h.paint_cells(img, h.old_hair, (0, 0, 0, 0))
    h.paint_cells(img, h.skull | h.side_fill | h.face, base)
    return img


def outline_cells(solid, keep_dark):
    """Transparent cells touching a solid cell: the one-cell dark outline every sprite has, skipped where hair is already dark."""
    ring = ndimage.binary_dilation(solid, structure=ndimage.generate_binary_structure(2, 1)) & ~solid
    return ring & ~keep_dark


def paint_head(h, concept_data, seed, tone, tries=2):
    """Ask PixelLab for the head. Every call is charged, so a head with two eyes, a mouth and enough hair to read is kept straight
    away. If neither try gets there, the better one goes on and the Bridge has its say. Returns (cell colors, hair, face and bare
    skin cell masks)."""
    best, best_score = None, None
    for k in range(tries):
        painted = _paint_once(h, concept_data, seed + k, tone)
        body = Layer(h, *painted).wear(h.t)
        where = parts.face_positions(body, parts.of(body))
        score = (len(where["eyes"]) == 2 and len(where["mouth"]) == 2, int(painted[1].sum()))
        if best is None or score > best_score:
            best, best_score = painted, score
        if score[0] and score[1] >= MIN_HAIR_CELLS:
            break
    return best


def painted_skin(h, out, tone):
    """The skin PixelLab painted: the commonest warm color on the face. It gets the character's tone to work from, but nothing
    can assume it kept to it."""
    cells = out[h.face & (out[..., 3] > 128)][:, :3].astype(float)
    warm = cells[(cells[:, 0] > cells[:, 1]) & (cells[:, 1] > cells[:, 2]) & (lum(cells) > 45)] if len(cells) else cells
    if not len(warm):
        return np.array(TONES[tone], float)
    bins, inverse, counts = np.unique((warm // 24).astype(int), axis=0, return_inverse=True, return_counts=True)
    return np.median(warm[inverse.ravel() == counts.argmax()], axis=0)


def same_skin(rgb, skin):
    """A shade of this skin. SKIN_FLOOR keeps a tiny channel, like the blue in dark brown, from swinging the ratio."""
    ratio = (rgb + SKIN_FLOOR) / (skin + SKIN_FLOOR)
    return ratio.min() >= 0.6 and ratio.max() <= 1.45 and ratio.max() - ratio.min() <= 0.35


def to_template_skin(rgb, skin):
    """The same shade on the template's skin, so the head moves to the character's tone exactly as the body does."""
    return np.clip((rgb + SKIN_FLOOR) / (skin + SKIN_FLOOR) * (np.array(SKIN_BASE, float) + SKIN_FLOOR) - SKIN_FLOOR, 0, 255)


def _png(cells):
    buf = io.BytesIO()
    Image.fromarray(cells).save(buf, "PNG")
    return buf.getvalue()


def _paint_once(h, concept_data, seed, tone):
    has_beard = bool(concept_data.get("beard"))
    # The whole box goes to PixelLab, outline cells included. A cell left out shows the template through the painting.
    zone = h.hair_zone | h.face_box | (h.beard_zone if has_beard else np.zeros_like(h.hair_zone))

    # The bald, blank-faced body on its own grid, in the character's tone, so the painting has the real skin next to it.
    body = np.zeros((GRID, GRID, 4), np.uint8)
    cells = flail.sample_cells(h.g, recolor(bald_template(h), tone))
    cells[..., 3] = np.where(cells[..., 3] >= 128, 255, 0)
    body[:h.ny, :h.nx] = cells
    mask = np.zeros((GRID, GRID, 4), np.uint8)
    mask[..., 3] = 255
    mask[:h.ny, :h.nx, :3][zone] = 255

    beard_text = f", {concept_data['beard_desc']}" if has_beard and concept_data.get("beard_desc") else ""
    description = (f"Pixel art game character, front view, a chubby man's head with big {concept_data['hair_color']} hair, {concept_data['hair']}{beard_text}. "
                   f"Simple cartoon face with the same skin color as his body: {concept_data.get('face', '')}. Two eyes with white whites and "
                   f"dark pupils, eyebrows, a nose and a mouth. Thick dark outline. No hat, no glasses.")
    painted, _ = pixellab.inpaint(_png(body), _png(mask), description, seed)
    out = np.array(Image.open(io.BytesIO(painted)).convert("RGBA"))
    if out.shape[:2] != (GRID, GRID):
        raise common.MalformedOutput(f"PixelLab sent back {out.shape[1]}x{out.shape[0]}, not {GRID}x{GRID}")
    out = out[:h.ny, :h.nx]

    # The painting is already on the body's own grid: one color per cell.
    colors = np.zeros((h.ny, h.nx, 4), np.uint8)
    hair = np.zeros((h.ny, h.nx), bool)
    face = np.zeros((h.ny, h.nx), bool)
    bare = np.zeros((h.ny, h.nx), bool)
    skin = painted_skin(h, out, tone)

    for j, i in zip(*np.nonzero(zone)):
        if out[j, i, 3] < 128:
            continue  # background
        rgb = out[j, i, :3].astype(float)
        if same_skin(rgb, skin):
            colors[j, i] = tuple(int(v) for v in to_template_skin(rgb, skin)) + (255,)
            bare[j, i] = True
            continue
        colors[j, i] = tuple(int(v) for v in rgb) + (255,)
        if h.face_box[j, i] and not (has_beard and h.beard_zone[j, i]):
            face[j, i] = True
        else:
            hair[j, i] = True

    # Only what is attached to the head counts; stray specks go, small holes close.
    head_seed = h.skull | (h.beard_zone & (h.jj <= 25))
    lab, _ = ndimage.label(hair | bare | face | head_seed)
    keep_labels = set(np.unique(lab[head_seed])) - {0}
    hair &= np.isin(lab, list(keep_labels))
    bare &= np.isin(lab, list(keep_labels))
    holes = ndimage.binary_fill_holes(hair | h.skull) & ~hair & ~bare & ~h.skull & h.hair_zone
    if holes.any():
        idx = ndimage.distance_transform_edt(~hair, return_distances=False, return_indices=True)
        for j, i in zip(*np.nonzero(holes)):
            colors[j, i] = colors[idx[0][j, i], idx[1][j, i]]
        hair |= holes
    whites = face & (colors[..., :3].min(axis=-1) > parts.PALE)
    colors = _quantize(_quantize(_quantize(colors, hair), face, n=6), bare, n=4)
    colors[whites] = WHITE   # the eye finder and the eye both want these to stay white through the palette
    return colors, hair, face, bare


def _quantize(colors, hair, n=8):
    """A small palette, as the sprites have; near-black all becomes the outline color."""
    if not hair.any():
        return colors
    px = colors[hair][:, :3]
    pal_img = Image.fromarray(px.reshape(-1, 1, 3).astype(np.uint8)).quantize(colors=n, method=Image.MEDIANCUT)
    out = np.array(pal_img.convert("RGB")).reshape(-1, 3)
    lum = 0.3 * out[:, 0] + 0.59 * out[:, 1] + 0.11 * out[:, 2]
    out[lum < 45] = (12, 8, 8)
    result = colors.copy()
    result[hair] = np.concatenate([out, np.full((len(out), 1), 255, np.uint8)], axis=1)
    return result


def lum(rgb):
    return 0.3 * rgb[..., 0] + 0.59 * rgb[..., 1] + 0.11 * rgb[..., 2]


def recolor(img, tone, protect=None, chest=None):
    """Move the skin to another tone by scaling every skin shade. Briefs, eye whites and the outline don't move.
    chest is (first row, last row) on the splat body, whose pale highlight lines would otherwise stay light."""
    if tone == "default":
        return img
    r, g, b = (img[..., k].astype(float) for k in range(3))
    is_skin = (img[..., 3] > 0) & (r - b > 18) & (r >= g) & (lum(img[..., :3].astype(float)) > 50)
    if chest is not None:
        is_skin[chest[0]:chest[1]] |= (img[chest[0]:chest[1], :, 3] > 0) & (lum(img[chest[0]:chest[1], :, :3].astype(float)) > 50)
    if protect is not None:
        is_skin &= ~protect
    factor = np.array(TONES[tone], float) / np.array(SKIN_BASE, float)
    out = img.copy()
    out[..., :3][is_skin] = np.clip(img[..., :3][is_skin] * factor, 0, 255).astype(np.uint8)
    return out


class Layer:
    """The new head as a layer that goes on the body and on every flail frame."""

    def __init__(self, h, colors, hair, face, bare):
        self.h = h
        self.clear = np.zeros((1024, 1024), bool)
        for j, i in zip(*np.nonzero(h.old_hair)):
            x0, x1, y0, y1 = h.rect(i, j)
            self.clear[y0:y1, x0:x1] = True
        paint = np.zeros((1024, 1024, 4), np.uint8)
        h.paint_cells(paint, h.skull | h.side_fill | h.face, tuple(int(v) for v in SKIN_BASE) + (255,))
        # The outline goes around the new head only, never over the body the template already outlined.
        head = hair | bare | h.skull | h.side_fill
        body = (h.cells[..., 3] > 128) & ~h.old_hair
        ring = outline_cells(head, np.zeros_like(head)) & ~body
        h.paint_cells(paint, bare, colors)
        h.paint_cells(paint, hair, colors)
        h.paint_cells(paint, face, colors)
        h.paint_cells(paint, ring, OUTLINE)
        self.paint = paint
        self.hair_px = np.zeros((1024, 1024), bool)
        for j, i in zip(*np.nonzero(hair | ring)):
            x0, x1, y0, y1 = h.rect(i, j)
            self.hair_px[y0:y1, x0:x1] = True
        # What keeps its painted color when the skin moves: the hair, and the eyes, brows and mouth on the face.
        self.keep_px = self.hair_px.copy()
        for j, i in zip(*np.nonzero(face)):
            x0, x1, y0, y1 = h.rect(i, j)
            self.keep_px[y0:y1, x0:x1] = True

    def wear(self, img):
        out = img.copy()
        out[self.clear] = 0
        on = self.paint[..., 3] > 0
        out[on] = self.paint[on]
        return out


# ── the files the game loads ────────────────────────────────────────────────────────────────────────────────
def next_slot(taken_slots):
    used = {int(m.group(1)) for p in PREFABS.glob("player*Prefab.prefab") if (m := re.fullmatch(r"player(\d+)Prefab", p.stem))}
    used |= {1} | set(taken_slots)
    for manifest in common.SUBMISSIONS.glob("characters/*/manifest.json"):
        m = json.loads(manifest.read_text(encoding="utf-8"))
        decision = manifest.with_name("decision.json")
        rejected = decision.exists() and json.loads(decision.read_text(encoding="utf-8")).get("decision") == "reject"
        if m.get("slot") and not rejected:
            used.add(m["slot"])
    slot = 2
    while slot in used:
        slot += 1
    limit_check(slot)
    return slot


def limit_check(slot):
    top = bridge.game_slot_limit()
    if slot > top:
        raise common.NeedsDavid(f"player{slot} is past player{top}, the last one the game loads. The Builder's job, slots past "
                                f"player{top} and the name list, has to go in before this character can be made.")


def write_body_meta(name, body, path):
    """player.png.meta with this image's own ids, and a rect that holds the new hair. The pivot stays on the same texture
    pixel as the template's, so the prefab's cheeks and colliders line up unchanged."""
    meta = (SPRITES / f"{TEMPLATE}.png.meta").read_text(encoding="utf-8")
    rect = {k: float(re.search(rf"\n        {k}: ([-\d.]+)", meta).group(1)) for k in ("x", "y", "width", "height")}
    px, py = rect["x"] + rect["width"] / 2, rect["y"] + rect["height"] / 2
    ys, xs = np.nonzero(body[..., 3])
    rx, rw = int(rect["x"]), int(rect["width"])   # the sides and feet stay where they were
    ry = int(rect["y"])
    top = 1024 - (int(ys.min()) - 2)
    rh = max(int(rect["height"]), top - ry)
    if xs.min() < rx or xs.max() >= rx + rw:
        rx, rw = int(xs.min()) - 2, int(xs.max() - xs.min()) + 5
    old_name = re.search(r"\n      name: (\S+)", meta).group(1)
    old_id = re.search(r"\n      internalID: (\S+)", meta).group(1)
    new_name = f"{name}_0"
    meta = meta.replace(old_name, new_name).replace(old_id, flail_internal_id(new_name))
    meta = re.sub(r"\nguid: \S+", "\nguid: " + flail.stable_id(f"Sprites/Characters/{name}"), meta)
    meta = re.sub(r"\n        x: \S+", f"\n        x: {rx}", meta)
    meta = re.sub(r"\n        y: \S+", f"\n        y: {ry}", meta)
    meta = re.sub(r"\n        width: \S+", f"\n        width: {rw}", meta)
    meta = re.sub(r"\n        height: \S+", f"\n        height: {rh}", meta)
    meta = re.sub(r"\n      alignment: \S+", "\n      alignment: 9", meta)
    meta = re.sub(r"\n      pivot: \{[^}]*\}", "\n      pivot: {x: %.6f, y: %.6f}" % ((px - rx) / rw, (py - ry) / rh), meta)
    meta = re.sub(r"\n      spriteID: \S+", "\n      spriteID: " + flail.stable_id(new_name + "/spriteID"), meta)
    path.write_text(meta, encoding="utf-8", newline="\n")
    return {"x": rx, "y": ry, "width": rw, "height": rh}


def flail_internal_id(text):
    return str(int.from_bytes(__import__("hashlib").md5(text.encode()).digest()[:8], "little", signed=True))


def make_flail(name, layer, tone, out):
    """The template's 12 frames wearing the new head, written with flail.py's own exporter."""
    frames = []
    for k in range(flail.FRAMES):
        frame = np.array(Image.open(FLAIL_DIR / f"{TEMPLATE}_flail_{k:02}.png").convert("RGBA"))
        frames.append(recolor(layer.wear(frame), tone, layer.keep_px))
    # The exporter reads the skin's pivot from its .meta; the template's rect gives the pivot this skin keeps.
    pivot_dir = out / "_pivot"
    pivot_dir.mkdir(exist_ok=True)
    shutil.copyfile(SPRITES / f"{TEMPLATE}.png.meta", pivot_dir / f"{name}.png.meta")
    flail.SPRITES, flail.GAME_OUT = str(pivot_dir), str(out / "Resources" / "DeathFlail")
    flail.export_game(name, frames)
    shutil.rmtree(pivot_dir)
    return frames


def tool_folder(name, img, out):
    """idle_game and flap_game read a skin's png and .meta from flail.SPRITES. They get the light body, and the template's
    .meta, whose rect gives the pivot this skin keeps."""
    folder = out / "_tools"
    folder.mkdir(exist_ok=True)
    Image.fromarray(img).save(folder / f"{name}.png")
    shutil.copyfile(SPRITES / f"{TEMPLATE}.png.meta", folder / f"{name}.png.meta")
    flail.SPRITES = str(folder)
    flail.CHARACTERS[name] = flail.CHARACTERS[TEMPLATE]   # a new sprite sits on the template's grid, so this is its row
    return folder


def toned_frames(name, layer, tone, out, build):
    """A tool's frames on the light body, moved to the tone. A second pass on a body with its hair and face paint marked MARK
    shows which pixels of each frame those are, wherever the tool moved them, so they keep their color."""
    light = layer.wear(layer.h.t)
    tool_folder(name, light, out)
    frames = build()
    marked = light.copy()
    marked[layer.keep_px] = MARK
    tool_folder(name, marked, out)
    marks = build()
    return [recolor(f, tone, (m[..., :3] == MARK[:3]).all(axis=-1)) for f, m in zip(frames, marks)]


def make_idle(name, layer, tone, out):
    """idle_game.py's three breath poses, written with its own exporter."""
    frames = toned_frames(name, layer, tone, out, lambda: idle_game.build_skin(name))
    flap_game.GAME_RESOURCES = str(out / "Resources")
    flap_game.export_game(name, frames, "CharacterIdle", "idle")
    return frames


def make_flap(name, layer, tone, out):
    """flap_game.py's eight frames from the approved player frames, written with its own exporter."""
    approved = [np.array(Image.open(Path(flap_game.APPROVED) / f"{n:02}.png").convert("RGBA")) for n in range(flap_game.FRAMES)]
    base = np.array(Image.open(flap_game.H.BASE).convert("RGBA"))
    player_base = flap_game.H.palette(base)["S"]
    rest_waist = flap_game.waist_row(approved[0])
    offsets = [(flap_game.H.head_offset(c, base)[1], flap_game.waist_row(c) - rest_waist) for c in approved]
    frames = toned_frames(name, layer, tone, out, lambda: flap_game.build_skin(name, approved, player_base, offsets))
    flap_game.GAME_RESOURCES = str(out / "Resources")
    flap_game.export_game(name, frames)
    return frames


def make_splat(name, light_body, layer, tone, out, where):
    """splat_faces.py's own steps on this character's own eyes and mouth, with the skin moved to its tone at the end."""
    sf = splat_faces
    sf.EYES[name] = tuple(tuple(b) for b in where["eye_boxes"])
    sf.MOUTHS[name] = (tuple(where["mouth_box"]), tuple(where["mouth"]), None)
    sf.GAME_OUT = str(out / "Resources" / "DeathSplat")
    splatchar, splat, base = sf.load(sf.SPLATCHAR), sf.load(sf.SPLAT), sf.load(sf.SPLATBASE)
    marks, x_color = sf.x_marks(splatchar)
    frown = sf.frown_of(splatchar)

    original_head_x = sf.HEAD_X
    sf.HEAD_X = (260, 800)   # big hair stays whole; above the cut there's only head and hair on this sprite
    try:
        head, dx, dy, mids = sf.head_of(name, light_body, frown)
    finally:
        sf.HEAD_X = original_head_x
    head = sf.shift(head, dx, dy)
    for side, (mx, my) in zip("LR", mids):
        sf.stamp(head, marks[side], mx + dx, my + dy, tuple(x_color) + (255,))
    hair = (sf.shift(layer.hair_px[..., None].astype(np.uint8), dx, dy)[..., 0] > 0) & (head[..., 3] > 0)   # never the splat's own chest under it

    old_head = np.zeros(splatchar.shape[:2], bool)
    old_head[:sf.HEAD_CUT_Y, sf.HEAD_X[0]:sf.HEAD_X[1]] = splatchar[:sf.HEAD_CUT_Y, sf.HEAD_X[0]:sf.HEAD_X[1], 3] > 0
    body = splatchar.copy()
    body[old_head] = 0
    body = sf.fill_neck_gap(sf.over(body, head))
    body = recolor(body, tone, hair, chest=(sf.HEAD_CUT_Y, 590))

    is_body = splatchar[..., 3] > 0
    brown = splat.copy()
    brown[is_body] = 0
    fill = base.copy()
    fill[~old_head] = 0
    fill[..., :3] = np.median(splat[~is_body & (splat[..., 3] > 200)][:, :3], axis=0).astype(np.uint8)
    flying = sf.over(sf.over(fill, brown), body)
    sf.export_game(name, body, flying)
    return body, flying


def previews(folder, name, body, animations, splat_body):
    sky = (150, 200, 240, 255)

    def on_sky(img, size=None, box=None):
        im = Image.fromarray(img)
        if box:
            im = im.crop(box)
        bg = Image.new("RGBA", im.size, sky)
        bg.alpha_composite(im)
        return bg.resize(size, Image.LANCZOS) if size else bg

    on_sky(body).convert("RGB").save(folder / "preview_body.png")
    on_sky(body, box=(250, 0, 790, 480)).convert("RGB").save(folder / "preview_head.png")
    on_sky(splat_body).convert("RGB").save(folder / "preview_splat.png")

    # One strip per animation, in rows so each frame stays readable on the dashboard's 600 by 200 thumbnails.
    for tag, (frames, columns) in animations.items():
        cell = 200
        rows = (len(frames) + columns - 1) // columns
        sheet = Image.new("RGBA", (cell * columns, cell * rows), sky)
        for k, fr in enumerate(frames):
            sheet.alpha_composite(on_sky(fr, (cell, cell)), ((k % columns) * cell, (k // columns) * cell))
        sheet.convert("RGB").save(folder / f"preview_strip_{tag}.png")

    # The line-up at game size: the new character beside the whole roster, as a player sees them.
    tall = 98
    names = [TEMPLATE] + [f"player{i}" for i in range(2, 11)]
    w = tall * 11
    sheet = Image.new("RGBA", (w, tall + 8), sky)
    x = 0
    for n in names:
        im = Image.open(SPRITES / f"{n}.png").convert("RGBA").crop((230, 0, 750, 980)).resize((52, tall), Image.LANCZOS)
        sheet.alpha_composite(im, (x + 22, 4))
        x += tall
    im = Image.fromarray(body).crop((230, 0, 750, 980)).resize((52, tall), Image.LANCZOS)
    sheet.alpha_composite(im, (x + 22, 4))
    sheet.convert("RGB").save(folder / "preview_lineup.png")


def fresh_folder(path):
    """Where this work goes. A folder David has decided on stays as his record, so new work goes beside it. One he hasn't is
    this same task's last attempt, and gets replaced."""
    candidate, n = path, 2
    while (candidate / "decision.json").exists():
        candidate, n = path.with_name(f"{path.name}_{n}"), n + 1
    if candidate.exists():
        shutil.rmtree(candidate)
    return candidate


def make(task, slot, taken, notes, seed):
    """One attempt at one character. Returns the submission folder and the concept."""
    limit_check(slot)
    name = f"player{slot}"
    # It's built out of David's sight. It only reaches the approval screen once the Bridge and the Critic pass it; see publish.
    folder = common.WORK / f"{name}_{task['id']}"
    if folder.exists():
        shutil.rmtree(folder)
    the_set = current_set(task)
    data = concept(task["brief"], taken, notes, the_set, slot)
    before = pixellab.spent()
    (folder / "Sprites" / "Characters").mkdir(parents=True)

    h = Head()
    layer = Layer(h, *paint_head(h, data, seed, data["skin_tone"]))
    light = layer.wear(h.t)
    where = parts.face_positions(light, parts.of(light))
    if len(where["eyes"]) != 2 or len(where["mouth"]) != 2:
        shutil.rmtree(folder)
        raise common.MalformedOutput("PixelLab didn't paint two clear eyes and a mouth: describe a plainer face with big eyes")
    if data["beard"]:
        # A beard joins up with the mouth, and the splat shouldn't bare a square of skin in it. The mouth stays where the beard leaves room.
        where["mouth_box"] = list(h.mouth_box)
        where["mouth"] = [(h.mouth_box[0] + h.mouth_box[1]) // 2, (h.mouth_box[2] + h.mouth_box[3]) // 2]
    tone = data["skin_tone"]
    body = recolor(light, tone, layer.keep_px)

    Image.fromarray(body).save(folder / "Sprites" / "Characters" / f"{name}.png")
    rect = write_body_meta(name, body, folder / "Sprites" / "Characters" / f"{name}.png.meta")
    flail_frames = make_flail(name, layer, tone, folder)
    idle_frames = make_idle(name, layer, tone, folder)
    flap_frames = make_flap(name, layer, tone, folder)
    splat_body, _ = make_splat(name, light, layer, tone, folder, where)
    shutil.rmtree(folder / "_tools")
    previews(folder, name, body, {"flail": (flail_frames, 6), "idle": (idle_frames, 3), "flap": (flap_frames, 4)}, splat_body)
    for folder_meta in ("DeathFlail.meta", "DeathSplat.meta", "CharacterIdle.meta", "FartFlap.meta"):   # the exporters write these; the project already has them
        (folder / "Resources" / folder_meta).unlink(missing_ok=True)

    files = sorted(str(p.relative_to(folder)).replace("\\", "/") for p in folder.rglob("*")
                   if p.is_file() and not p.name.startswith("preview_"))
    manifest = {"kind": "character", "name": f"{data['first_name']} ({name})", "agent": "Character Artist", "slot": slot, "skin": name,
                "first_name": data["first_name"], "set": the_set["name"], "face": where,
                "concept": data, "seed": seed, "rect": rect, "files": files,
                "pixellab": {k: round(v - before[k], 4) for k, v in pixellab.spent().items()},
                "previews": ["preview_lineup.png", "preview_body.png", "preview_head.png", "preview_splat.png",
                             "preview_strip_flail.png", "preview_strip_idle.png", "preview_strip_flap.png"]}
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return folder, data


def publish(folder):
    """Work that passed goes where David can see it."""
    dst = fresh_folder(common.SUBMISSIONS / "characters" / Path(folder).name)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(folder), str(dst))
    return dst


NAMES_SYSTEM = """You give first names to the ten original characters of Bottom Busters, a comedy arcade game where chubby men in white briefs fly by farting.
Each name is a real first name you'd really hear, one word, and comically typical of an ordinary middle-aged American guy with that look. It's funny for being so typical, and it's never offensive. No nicknames and no titles. All ten are different.
Answer with only one JSON object with one field:
"names": an object with the keys player, player2, player3, player4, player5, player6, player7, player8, player9, player10, each holding that character's first name"""


def names_sheet(names, path):
    """The ten with their names under them, sized for the dashboard's 600 by 200 thumbnail."""
    sheet = Image.new("RGBA", (600, 200), (150, 200, 240, 255))
    draw = ImageDraw.Draw(sheet)
    for k, skin in enumerate(ORIGINALS):
        im = Image.open(SPRITES / f"{skin}.png").convert("RGBA").crop((230, 0, 750, 700)).resize((60, 81), Image.LANCZOS)
        x, y = (k % 5) * 120, (k // 5) * 100
        sheet.alpha_composite(im, (x + 30, y + 1))
        draw.text((x + 60, y + 90), names[skin], fill=(20, 20, 40, 255), anchor="mm")
    sheet.convert("RGB").save(path)


def make_original_names():
    """A submission with first names for the original ten, for David to approve like any other work."""
    looks = "\n".join(f"- {skin}: {look}" for skin, look in zip(ORIGINALS, ROSTER))
    data = common.ask_json("character-artist", [{"role": "system", "content": NAMES_SYSTEM},
                                                {"role": "user", "content": f"The ten, and how each one looks:\n{looks}"}], ["names"], max_tokens=500)
    names = data["names"] if isinstance(data["names"], dict) else {}
    missing = [skin for skin in ORIGINALS if not names.get(skin)]
    if missing:
        raise common.MalformedOutput(f"the names are missing {missing}")
    names = {skin: check_first_name(names[skin]) for skin in ORIGINALS}
    if len({v.lower() for v in names.values()}) != len(names):
        raise common.MalformedOutput("two of the original ten got the same first name")
    folder = fresh_folder(common.SUBMISSIONS / "characters" / "names_original")
    folder.mkdir(parents=True)
    names_sheet(names, folder / "preview_names.png")
    listed = ", ".join(f"{v} ({k})" for k, v in names.items())
    manifest = {"kind": "names", "name": f"First names for the original ten: {listed}", "agent": "Character Artist", "names": names,
                "files": [], "previews": ["preview_names.png"]}
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return folder


if __name__ == "__main__":
    # The first chunk's other job, run on David's word: python character_artist.py --names
    if "--names" in sys.argv:
        print(make_original_names())
