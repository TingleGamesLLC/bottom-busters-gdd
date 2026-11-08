"""The game design document, read by every content agent before it writes anything (Assignment #4: the pipeline uses the GDD as
its source, so the output sounds like Bottom Busters and not like generic content).

The source is the GDD in the game's repo. Its Section 21, the Content guide, has an opening every agent reads and one part per
maker. A maker reads the opening and its own part, word for word, at the top of every prompt that generates content. The Critic
reads the same text when it checks that work against the GDD (critic.check_gdd), so the maker and its check work from one source.
"""
import re
from pathlib import Path

import common

SOURCE = Path(r"C:\bbust\BBUST\BOTTOM_BUSTERS_GDD.md")
PARTS = {"character-artist": "21.1", "roast-writer": "21.2", "wardrobe-stylist": "21.3", "level-architect": "21.4"}


def guide(agent):
    """{"source", "sections", "text"}: Section 21's opening and this agent's own part. Stops the run if either is missing,
    because a maker that can't read the GDD mustn't generate anything."""
    part = PARTS.get(agent)
    if not part:
        raise common.CrewStop(f"{agent} has no part in the GDD's Content guide")
    try:
        doc = SOURCE.read_text(encoding="utf-8")
    except OSError as e:
        raise common.CrewStop(f"the GDD isn't readable at {SOURCE}: {e}")
    whole = re.search(r"^## 21\. Content guide\s*$(.*?)(?=^## |\Z)", doc, re.M | re.S)
    if not whole:
        raise common.CrewStop(f"the GDD at {SOURCE} has no Section 21, Content guide")
    body = whole.group(1)
    opening = re.split(r"^### ", body, maxsplit=1, flags=re.M)[0].strip()
    own = re.search(rf"^### {re.escape(part)} .*?(?=^### |\Z)", body, re.M | re.S)
    if not opening or not own:
        raise common.CrewStop(f"the GDD's Content guide is missing its opening or Section {part}")
    return {"source": str(SOURCE), "sections": ["21", part],
            "text": f"## 21. Content guide\n\n{opening}\n\n{own.group(0).strip()}"}


def prompt_block(agent):
    """The guide as the first thing in a maker's prompt."""
    g = guide(agent)
    return (f"From the Bottom Busters game design document (GDD), Section 21, the Content guide: its opening and Section "
            f"{g['sections'][1]}. Read it before you write anything. Everything you make follows it.\n\n{g['text']}\n\n"
            "End of the GDD extract.")
