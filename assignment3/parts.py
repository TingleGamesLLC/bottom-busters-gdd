"""Separates a body sprite into its skin, hair and face, whatever the skin tone.

Everything is measured against the body's own skin, read off its torso, so a very dark character sorts the same way as a
pale one. Boxes come from the template's pixel grid. The other nine originals sit a cell or two off it, which still lands
inside these boxes.
"""
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, r"C:\bbust\CoverArt\tools")
import flail  # noqa: E402

TEMPLATE = "player"
SIZE = 1024
FACE_ROWS, FACE_CELLS = (15, 25), (38, 52)
TORSO_ROWS, TORSO_CELLS = (32, 46), (38, 54)
EYES_END_ROW = 20          # the upper face box, where eyes go, ends on this row; the mouth is below it
HEAD_END_ROW = 29          # hair and beards stop here
EYE_SEPARATION = (50, 100)  # pixels between two eyes, center to center; the originals run 67 to 81
EYE_LEVEL = 10             # how far apart two eyes can sit up and down, in pixels
EYE_REACH = 30             # how far an eye's box can reach from the shape it was found by, in pixels, across
EYE_REACH_Y = 22           # and up and down
PALE = 200                 # every channel above this is the white of an eye
MOUTH_REACH = 60           # how far from the middle of the eyes a mouth can reach, in pixels
MIN_BLOB = 20              # pixels; smaller than this is a speck
NEUTRAL = (128, 128, 128)  # what a measured view shows where the part isn't, so skin tone can't count as a difference
HEAD_BOX = (300, 0, 780, 350)


def _box(cells, rows):
    g = flail.Body(TEMPLATE)
    x0, _, y0, _ = g.cell_rect(cells[0], rows[0])
    _, x1, _, y1 = g.cell_rect(cells[1], rows[1])
    return x0, x1, y0, y1


FACE_BOX = _box(FACE_CELLS, FACE_ROWS)
TORSO_BOX = _box(TORSO_CELLS, TORSO_ROWS)
EYES_END = _box(FACE_CELLS, (EYES_END_ROW, EYES_END_ROW))[3]
HEAD_END = _box(FACE_CELLS, (HEAD_END_ROW, HEAD_END_ROW))[3]


def lum(rgb):
    return 0.3 * rgb[..., 0] + 0.59 * rgb[..., 1] + 0.11 * rgb[..., 2]


def skin_like(img, skin, low=0.62, high=1.25, spread=0.2):
    """Pixels that are the skin or a shade of it: every channel the same multiple of the skin, within reason."""
    ratio = img[..., :3].astype(float) / np.maximum(np.asarray(skin, float), 1)
    return (ratio.min(axis=-1) >= low) & (ratio.max(axis=-1) <= high) & (ratio.max(axis=-1) - ratio.min(axis=-1) <= spread)


def of(body):
    """skin: the torso's median color. hair and face: bool masks at 1024, everything on the head that isn't skin."""
    x0, x1, y0, y1 = TORSO_BOX
    torso = body[y0:y1, x0:x1]
    skin = np.median(torso[torso[..., 3] > 128][:, :3], axis=0)
    not_skin = (body[..., 3] > 128) & ~skin_like(body, skin)
    in_face = np.zeros(body.shape[:2], bool)
    fx0, fx1, fy0, fy1 = FACE_BOX
    in_face[fy0:fy1, fx0:fx1] = True
    in_head = np.zeros(body.shape[:2], bool)
    in_head[:HEAD_END] = True
    return {"skin": skin, "hair": not_skin & in_head & ~in_face, "face": not_skin & in_face}


def head_skin_share(body, p):
    """How much of the face box is the torso's own skin, near enough. A head on another tone scores about zero."""
    x0, x1, y0, y1 = FACE_BOX
    box = body[y0:y1, x0:x1]
    solid = box[..., 3] > 128
    return float((skin_like(box, p["skin"], low=0.85, high=1.15) & solid).sum() / max(solid.sum(), 1))


def _blobs(mask):
    """Connected shapes as (area, center x, center y, labels array, label), biggest first."""
    labels, n = ndimage.label(mask, structure=np.ones((3, 3)))
    found = []
    for k in range(1, n + 1):
        ys, xs = np.nonzero(labels == k)
        if len(xs) >= MIN_BLOB:
            found.append((len(xs), float(xs.mean()), float(ys.mean()), k))
    return labels, sorted(found, reverse=True)


def _level_pair(blobs):
    """The two biggest shapes that sit level and an eye's distance apart, left one first, or None."""
    pairs = [(a, b) for i, a in enumerate(blobs) for b in blobs[i + 1:]
             if abs(a[2] - b[2]) <= EYE_LEVEL and EYE_SEPARATION[0] <= abs(a[1] - b[1]) <= EYE_SEPARATION[1]]
    if not pairs:
        return None
    return sorted(max(pairs, key=lambda ab: min(ab[0][0], ab[1][0])), key=lambda b: b[1])


def _eye_box(labels, blob, dark, whites):
    """The box round the whole eye: the shape and whatever dark or white pixels it touches, a white and its pupil. In the upper
    face box's own pixels, held to EYE_REACH around the shape so a brow or the edge of the head can't stretch it."""
    ys, xs = np.nonzero(labels == blob[3])
    joined, _ = ndimage.label(dark | whites, structure=np.ones((3, 3)))
    whole_y, whole_x = np.nonzero(joined == joined[ys[0], xs[0]])
    cx, cy = xs.mean(), ys.mean()
    return (int(max(whole_x.min(), cx - EYE_REACH)), int(min(whole_x.max(), cx + EYE_REACH)),
            int(max(whole_y.min(), cy - EYE_REACH_Y)), int(min(whole_y.max(), cy + EYE_REACH_Y)))


def face_positions(body, p):
    """eyes: the two whites of the eyes when there are any, else two dark shapes, in either case level and an eye's distance
    apart. mouth: the largest shape in the lower face box near the middle of the eyes. Boxes go with them for splat_faces,
    which paints over each one. Anything it can't find comes back empty, and the Bridge sends that back."""
    x0, x1, y0, y1 = FACE_BOX
    empty = {"eyes": [], "mouth": [], "eye_boxes": [], "mouth_box": []}
    rgb = body[..., :3].astype(float)
    dark = (p["face"] & (lum(rgb) < lum(np.asarray(p["skin"], float)) * 0.5))[y0:EYES_END, x0:x1]
    whites = (p["face"] & (rgb.min(axis=-1) > PALE))[y0:EYES_END, x0:x1]
    labels, blobs = _blobs(whites)
    pair = _level_pair(blobs)
    if pair is None:
        labels, blobs = _blobs(dark)
        pair = _level_pair(blobs)
    if pair is None:
        return empty
    boxes = []
    for blob in pair:
        bx0, bx1, by0, by1 = _eye_box(labels, blob, dark, whites)
        boxes.append([bx0 + x0, bx1 + x0, by0 + y0, by1 + y0])
    eyes = [[round((b[0] + b[1]) / 2), round((b[2] + b[3]) / 2)] for b in boxes]

    mid = (eyes[0][0] + eyes[1][0]) / 2
    lower = p["face"].copy()
    lower[:EYES_END] = False
    lower[y1:] = False
    lower[:, :int(mid - MOUTH_REACH)] = False
    lower[:, int(mid + MOUTH_REACH):] = False
    labels, blobs = _blobs(lower)
    if not blobs:
        return dict(empty, eyes=eyes, eye_boxes=boxes)
    _, cx, cy, k = blobs[0]
    ys, xs = np.nonzero(labels == k)
    cx, cy = round(cx), round(cy)
    mouth_box = [int(max(xs.min(), cx - MOUTH_REACH)), int(min(xs.max(), cx + MOUTH_REACH)), int(max(ys.min(), cy - 20)), int(min(ys.max(), cy + 20))]
    return {"eyes": eyes, "mouth": [cx, cy], "eye_boxes": boxes, "mouth_box": mouth_box}


def _view(body, mask, box, size):
    """Only this part's pixels, on a neutral gray, shrunk to about game size."""
    img = np.zeros(body.shape[:2] + (3,), np.uint8)
    img[...] = NEUTRAL
    img[mask] = body[..., :3][mask]
    return np.array(Image.fromarray(img).crop(box).resize(size, Image.LANCZOS)).astype(float)


def measure(body):
    """What two characters get compared on: the skin color, and the hair and the face each seen alone."""
    p = of(body)
    fx0, fx1, fy0, fy1 = FACE_BOX
    return {"skin": p["skin"], "hair": _view(body, p["hair"], HEAD_BOX, (36, 26)),
            "face": _view(body, p["face"], (fx0, fy0, fx1, fy1), (18, 13))}


def differences(a, b):
    """Skin, hair and face distances between two measures. Each is a mean color difference, 0 to 255."""
    return {part: float(np.abs(a[part] - b[part]).mean()) for part in ("skin", "hair", "face")}
