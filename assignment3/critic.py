"""Critic: an adversarial look at only what the player will see. Runs after the Bridge, on the cluster's vision model.

It looks for what's wrong with the picture. It never sees the maker's concept or reasoning, only the pictures and the Bridge's
measurements, and no agent calls its own reviewer: the Orchestrator hands the work over. Its verdict goes to David as a note beside
the character. It hasn't been tested on art with known answers, so it doesn't send work back.
"""
import base64
import io
from pathlib import Path

from PIL import Image

import common

FIELDS = ["what_i_see", "tell_apart", "problems", "verdict", "note_for_artist"]
SYSTEM = """You are the toughest playtester on Bottom Busters, a comedy arcade game. You judge new character art by what a player would see. Your job is to find what is wrong, not to be nice.
Send it back if: the hair looks detached from the head, the head has holes or square patches of the wrong color, the face doesn't have two clear eyes and a mouth, the face looks exaggerated or drawn in a different style from the others, the hair is hard to read at small size, or a player could confuse this character with one already in the roster.
Answer with only one JSON object with these fields:
"what_i_see": what the new character's hair, beard and face look like, under 15 words
"tell_apart": true if a player could pick this character out of the line-up at a glance, otherwise false
"problems": a list of short strings, empty if none
"verdict": "pass" or "fail"
"note_for_artist": one instruction for fixing it, or "" on a pass"""


def _data_url(img):
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def review(folder, concept, facts):
    folder = Path(folder)
    lineup = Image.open(folder / "preview_lineup.png")
    lineup = lineup.resize((lineup.width * 2, lineup.height * 2), Image.NEAREST)  # the model reads tiny images poorly
    head = Image.open(folder / "preview_head.png").resize((400, 356), Image.LANCZOS)
    text = (f"First image: the line-up at game size. The new character is the last one on the right. "
            f"Second image: the new character's head up close.\n"
            f"Measured difference from its closest roster character ({facts['nearest_roster']}): {facts['difference_from_nearest']}.")
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": [{"type": "text", "text": text},
                                             {"type": "image_url", "image_url": {"url": _data_url(lineup)}},
                                             {"type": "image_url", "image_url": {"url": _data_url(head)}}]}]
    verdict = common.ask_json("critic", messages, FIELDS, model=common.VISION_MODEL, max_tokens=500)
    verdict["verdict"] = "pass" if str(verdict.get("verdict")).lower() == "pass" else "fail"
    return verdict
