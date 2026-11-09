"""Critic: an adversarial look at the crew's work, in two checks. No agent calls its own reviewer: the Orchestrator hands the
work over.

1. The GDD check (check_gdd, check_gdd_lines), on the cluster's writer model. Every design, before any art is made, and every
   roast line, is checked against the same part of the GDD's Content guide the maker read. A fail goes back to the maker with
   the GDD rule it broke, and costs it a cheek: this is the consistency check loop (Assignment #4). A finding sends work back
   only when it survives judge(): its rule is quoted from the GDD, it doesn't hedge ("may", "in spirit"), the words it blames
   are really in the work, and a second call that sees that one finding alone agrees the words break the rule. Run
   20261107-155047 showed why: the Critic failed "Just the smell" on a rule that allows "a smell", and stopped three makers.
2. The picture review (review, review_background, review_wardrobe), on the cluster's vision model, after the Bridge. It sees only
   the pictures and the Bridge's measurements. Its verdict goes to David as a note beside the work: it hasn't been tested on art
   with known answers, so it doesn't send work back.
"""
import base64
import io
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

from PIL import Image

import common
import gdd

GDD_SYSTEM = """You are the Critic on the Bottom Busters crew. Before new work goes any further, you check it against the game's design document, the GDD. This is the part of the GDD the work must follow:

{guide}

Check the work against every rule in that part. Fail it only for a clear break: words in the work that a rule written above forbids. For each problem, copy the rule word for word from the text above, and copy the exact words from the work that break it.
Never fail work for what it may, might or could lead to, for what it implies or hints at, or for the spirit of a rule. Something a rule allows is never a break.{seen}
Pass work that follows every rule, even if you'd have done it differently. A rule that isn't written above isn't a rule."""
DESIGN_SEEN = """
You're reading a design as text, before any art is made. Judge only what the text says, never how you guess the art will look: how it looks is checked on the picture later."""
GDD_ANSWER = """
Answer with only one JSON object with these fields:
"verdict": "pass" or "fail"
"problems": a list of {"rule": the one sentence of the GDD it breaks, copied word for word from the text above, "words": the exact words from the work that break it, "why": how those words break the rule, in one short sentence}, empty on a pass
"note_for_maker": one instruction for fixing it, or "" on a pass"""
GDD_LINES_ANSWER = """
Answer with only one JSON object: {"lines": [{"n": 1, "verdict": "pass" or "fail", "problems": [{"rule": "the one sentence of the GDD it breaks, copied word for word from the text above", "words": "the exact words from the line that break it", "why": "how those words break the rule"}]}]}, one entry for every numbered line, with every rule the line breaks in its problems, and problems empty on a pass."""
SECOND_LOOK = """You check one finding against the design document (GDD) of Bottom Busters, a comedy arcade game. A reviewer failed some work on a rule from this part of the GDD:

{guide}

You get the work, the rule and the words it was failed for. Read the whole rule first: many rules say what they allow as well as what they forbid. The words break the rule only when they are something the rule forbids. Words the rule allows, or words the rule isn't about, don't break it.
Answer with only one JSON object, in this order: {"forbids": what the rule forbids, in its own words, "allows": what the rule allows, in its own words, or "", "breaks": true or false, "reason": one short sentence}"""
# A design can't break a rule by leaving something out of its text: the Critic failed a top hat on "the description does not
# indicate that the hat leans left", which the code that draws it decides.
ABSENCE = re.compile(r"\b(?:does not|doesn't|do not|don't|fails to) (?:indicate|say|mention|specify|state|show|describe|include)|"
                     r"\bno mention\b|\bnot (?:specified|stated|mentioned|indicated|described)\b", re.I)
# A finding that hedges isn't a break: plain code drops it before anyone reads it (run 20261107-155047 failed a character on
# "may create a caricature ... in spirit, though not in letter" and a hat on "may not fit properly").
HEDGE = re.compile(r"\b(may|might|possibly|potentially|likely|perhaps|seems?|appears? to|in spirit|not explicitly|not in letter|"
                   r"borders? on|leans? (?:into|on|toward)|impl(?:y|ies|ied|ying)|indirectly|by implication|by association|"
                   r"suggests?|hints? at|could be (?:seen|read|taken|viewed|interpreted|considered)|comes? across as|"
                   r"risks?|risking)\b", re.I)
# GDD rules about how the finished art looks on screen. A design is text, so the GDD check can't judge these: they're the
# Bridge's measurements and the picture review's, after the art is made. A design check that fails on one is dropped (the
# Critic failed a top hat and a propeller beanie on "look like it belongs" from their text alone).
PICTURE_RULES = [
    "Everything new has to read at game size and sit beside what's already in the game.",
    "It has to look like it belongs with the four already in the game.",
    "A hat's bottom edge is its brim, and it sits on the head.",
    "Every item has to sit right on every character.",
    "An item that doesn't read as what it is at game size, or reads as a blob.",
    "Off-style art.",
    "A hat that floats above the head, or shades that miss the eyes.",
    "Any visible seam or vertical line while a layer moves.",
    "An object split across layers.",
    "Holes inside objects.",
    "Key color left behind.",
    # DAVID, 2026-11-08: Derrick's face is fine, though the Critic failed the same words ("wide-set eyes, thick bushy brows")
    # three runs in a row. Whether a face looks exaggerated shows on the picture, not in the words.
    "Every face gets the same cartoon treatment, with no exaggerated features.",
]


# The Bridge holds the GDD's "the gross thing is never named" in plain code (bridge.ROAST_BANNED), before a line reaches the
# Critic. The model reads the rule's allowed words ("it", "a smell") as names: in four live checks it failed "Just the smell"
# and "carry it further" on this rule, with two separate looks agreeing. So a finding on it stands only for a banned word.
GROSS_RULE = ("the gross thing is never named", "never poop or fart")
# A design's context, never shown in the game ("The game shows no ethnicity information"): the Critic failed Maurice for
# "naming the group" on the words of his set's name.
CONTEXT_KEYS = ("set",)


def _gross_rule_misread(raw):
    """A finding on the never-named rule that blames no banned word: the rule allows what it blames."""
    import bridge
    rule = _plain(raw.get("rule"))
    return any(g in rule for g in GROSS_RULE) and not any(w in bridge.ROAST_BANNED for w in bridge.roast_words(str(raw.get("words") or "")))


# GDD sentences that describe the game as it is, not what new work must do. The Critic failed the approved haunted-mansion
# background for not being one of "the game's terrain themes", and for not being gross-out.
NOT_RULES = [
    "Bottom Busters is a comedy arcade game.",
    "A character's health is two cheeks, and lives are white underwear icons.",
    "The humor is gross-out and physical.",
    "Poo piles up and dirties bodies, cheeks and hats, and the base coat never washes off.",
    'Other humor-first visuals include cheek "health" and the chef animals in the bonus rounds.',
    "A character is about 100 pixels tall in play.",
    "The game has four today: the Santa hat, the turkey hat, black shades and silver aviators.",
    "The game's terrain themes are blue stone, green sludge, pale bone, ice, charred ember and red crimson, with the red lava world last.",
    "The Studio Director liked the violets of the first test, a giant mushroom forest at dusk.",
]


def _listed(rule, sentences):
    r = _plain(rule)
    return any(p in r or SequenceMatcher(None, r, p).ratio() >= 0.85 for p in map(_plain, sentences))


def _picture_rule(rule):
    """Is this quoted rule one about how the art looks, judged on the picture after it's made?"""
    return _listed(rule, PICTURE_RULES)


def _plain(text):
    """Text compared for a quote: no markdown or quote marks of any kind, no end punctuation, one space, lower case."""
    text = re.sub(r"[*`\"'“”‘’]", "", str(text or ""))
    return re.sub(r"\s+", " ", text).strip().strip(".:;, -").lower()


def _sentences(guide_text):
    """Every bullet and sentence of the GDD text, plain, for matching a quote copied with small slips."""
    out = []
    for line in guide_text.splitlines():
        line = line.strip().lstrip("-#|").strip()
        out += [_plain(s) for s in re.split(r"(?<=[.!?])\s+", line) if len(_plain(s)) >= 8] + ([_plain(line)] if line else [])
    return out


def cited(problem, guide_text):
    """A problem as one string, when the rule it quotes is in the GDD text; None when the Critic invented the rule. Plain code
    holds this line: the model reads the GDD, but only a rule the GDD really has can send work back. A quote counts when it's
    in the GDD word for word, or nearly the whole of one GDD sentence or bullet."""
    if not isinstance(problem, dict):
        return None
    rule, why = _plain(problem.get("rule")), str(problem.get("why") or "").strip()
    if len(rule) < 8:
        return None
    if rule not in _plain(guide_text) and not any(SequenceMatcher(None, rule, s).ratio() >= 0.85 for s in _sentences(guide_text)):
        return None
    quote = focus(problem.get("rule"), why)
    return f'{why} (GDD: "{quote}")' if why else f'GDD: "{quote}"'


def focus(rule, why):
    """The one sentence of a quoted rule the finding is about, when the Critic copied a whole paragraph: the sentence that
    shares the most words with its why. A rule of one or two sentences, like most GDD bullets, is kept whole."""
    parts = [s.strip() for s in re.split(r"(?<=[.!?])\s+", str(rule or "").replace("**", "").strip()) if s.strip()]
    if len(parts) <= 2:
        return str(rule or "").strip()
    said = set(re.findall(r"[a-z]{4,}", str(why).lower()))
    return max(parts, key=lambda s: len(set(re.findall(r"[a-z]{4,}", s.lower())) & said))


def _in_work(words, work_text):
    """Are the words the Critic quotes really in the work? Word for word, or nearly all of their words."""
    w = _plain(words)
    if len(w) < 2:
        return False
    if w in _plain(work_text):
        return True
    mine = [x for x in re.findall(r"[a-z0-9]+", w) if len(x) >= 3]
    theirs = set(re.findall(r"[a-z0-9]+", _plain(work_text)))
    return bool(mine) and sum(x in theirs for x in mine) >= 0.8 * len(mine)


def _second_look(guide_text, work_text, raw):
    """A separate call that sees one finding alone, without the Critic's argument for it (shown the argument, the model agreed
    with it): do these words break that rule? True when they do."""
    messages = [{"role": "system", "content": SECOND_LOOK.replace("{guide}", guide_text)},
                {"role": "user", "content": f"The work: {work_text}\nThe rule: \"{str(raw.get('rule')).strip()}\"\n"
                                            f"The words it was failed for: \"{str(raw.get('words')).strip()}\"\n"
                                            f"Do those words break that rule?"}]
    try:
        v = common.ask_json("critic", messages, ["forbids", "allows", "breaks", "reason"], max_tokens=400, tries=3)
    except common.MalformedOutput:   # no answer confirms nothing: run 20261107-163826 lost a hat a cheek to one
        return False, "the second look gave no readable answer, so nothing confirmed the finding"
    return v.get("breaks") in (True, "true", "True", "yes"), str(v.get("reason") or "").strip()


def judge(raw, guide_text, work_text, quote_from=None, design=False):
    """One finding the Critic wrote, through plain code and then a second look. Returns (the problem as one string, None) when it
    stands, or (None, why it was dropped). Plain code drops a finding whose rule isn't in the GDD, that judges a design's text
    on a rule about the finished picture, that hedges, or that quotes words the work doesn't have (quote_from: where the words
    must be, when that's narrower than the work, such as a roast line without its event's name); the second look drops one
    whose words don't clearly break its rule."""
    if not isinstance(raw, dict):
        return None, "not a finding"
    problem = cited(raw, guide_text)
    if not problem:
        return None, "its rule isn't in the GDD"
    if _listed(focus(raw.get("rule"), raw.get("why")), NOT_RULES):
        return None, "it quotes a sentence that describes the game today, not a rule for new work"
    if design and _picture_rule(focus(raw.get("rule"), raw.get("why"))):
        return None, "its rule is about how the finished art looks, which is checked on the picture after it's made"
    hedge = HEDGE.search(str(raw.get("why") or ""))
    if hedge:
        return None, f'a maybe, not a break ("{hedge.group(0)}")'
    if design and ABSENCE.search(str(raw.get("why") or "")):
        return None, "it blames the design for something its text leaves out, which isn't a break"
    if _gross_rule_misread(raw):
        return None, "it blames words the rule allows: only a banned word names the gross thing, and the Bridge checks those"
    if not _in_work(raw.get("words"), work_text if quote_from is None else quote_from):
        return None, "the words it quotes aren't in the work"
    for _ in range(2):   # two separate looks must both find the break: one look alone agreed with a wrong fail now and then
        breaks, reason = _second_look(guide_text, work_text, raw)
        if not breaks:
            return None, f"the second look found no break: {reason}"
    return problem, None


def as_text(work, pad=""):
    """A design as plain "field: value" lines, with no JSON quote marks: the Critic copied JSON from a design into its own
    answer unescaped ("words": "speed": 0.3, ...), which broke its reply every time on one recipe."""
    out = []
    for k, v in work.items():
        if isinstance(v, dict):
            out += [f"{pad}{k}:", as_text(v, pad + "  ")]
        elif isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
            out.append(f"{pad}{k}:")
            for n, x in enumerate(v, 1):
                out.append(f"{pad}  {n}. " + "; ".join(f"{a} {', '.join(map(str, b)) if isinstance(b, list) else b}" for a, b in x.items()))
        elif isinstance(v, list):
            out.append(f"{pad}{k}: {', '.join(map(str, v))}")
        else:
            out.append(f"{pad}{k}: {v}")
    return "\n".join(out)


def check_gdd(agent, work):
    """Does this design follow the agent's part of the GDD? Returns the verdict, the problems left standing (each quoting the
    GDD rule it breaks), a note for the maker, the GDD sections it was checked against, and every finding dropped, with why.
    A fail with no problem left standing is a pass."""
    g = gdd.guide(agent)
    work_text = as_text(work)
    messages = [{"role": "system", "content": GDD_SYSTEM.replace("{guide}", g["text"]).replace("{seen}", DESIGN_SEEN) + GDD_ANSWER},
                {"role": "user", "content": "The design to check:\n" + work_text}]
    # Three tries: a broken answer from the Critic would cost the maker a cheek (1 of 6 live checks of the real recipes).
    v = common.ask_json("critic", messages, ["verdict", "problems", "note_for_maker"], max_tokens=1500, tries=3)
    raw = v.get("problems") if isinstance(v.get("problems"), list) else []
    said_fail = str(v.get("verdict")).strip().lower() != "pass"
    own_words = as_text({k: x for k, x in work.items() if k not in CONTEXT_KEYS})
    problems, dropped = [], []
    for r in raw if said_fail else []:
        problem, why_dropped = judge(r, g["text"], work_text, quote_from=own_words, design=True)
        if problem:
            problems.append(problem)
        else:
            dropped.append({"finding": r, "dropped": why_dropped})
    verdict = "fail" if problems else "pass"
    return {"verdict": verdict, "problems": problems,
            "note_for_maker": str(v.get("note_for_maker") or "") if verdict == "fail" else "",
            "gdd": f"{Path(g['source']).name}, Sections {' and '.join(g['sections'])}", "dropped": dropped}


def check_gdd_lines(lines, describe):
    """The GDD check for a batch of roast lines: one call for the batch, then each fail through judge(). lines: dicts with
    "text"; describe(line) says its event and outcome. Returns one {"verdict", "problem"} per line, in order, with any finding
    dropped. A line the Critic gave no answer for fails, so nothing reaches David unchecked."""
    if not lines:
        return []
    g = gdd.guide("roast-writer")
    numbered = "\n".join(f"{k + 1}. ({describe(l)}) {l['text']}" for k, l in enumerate(lines))
    messages = [{"role": "system", "content": GDD_SYSTEM.replace("{guide}", g["text"]).replace("{seen}", "") + GDD_LINES_ANSWER},
                {"role": "user", "content": "The roast lines to check, each with the event and outcome it plays on:\n" + numbered}]
    # Room for every line's problems with their quoted rules: at 80 tokens a line, the answer for 11 lines was cut off mid-JSON
    # twice and stopped the Roast Writer (run 20261107-163826).
    d = common.ask_json("critic", messages, ["lines"], max_tokens=max(1000, 250 * len(lines) + 300), tries=3)
    answers = {}
    for a in d["lines"] if isinstance(d["lines"], list) else []:
        try:
            answers[int(a["n"]) - 1] = a
        except (KeyError, TypeError, ValueError):
            continue
    out = []
    for k, line in enumerate(lines):
        a = answers.get(k)
        if a is None:
            out.append({"verdict": "fail", "problem": "the Critic gave no answer for it"})
            continue
        if str(a.get("verdict")).strip().lower() == "pass":
            out.append({"verdict": "pass", "problem": ""})
            continue
        # Every finding, so a real break isn't lost when the Critic also quotes the wrong rule (a line with "that famous
        # plumber in the red hat" passed when its one finding quoted the never-named rule instead of "No pop culture.").
        raw = a.get("problems") if isinstance(a.get("problems"), list) else [a]
        problems, dropped = [], []
        for r in raw:
            problem, why_dropped = judge(r, g["text"], f"({describe(line)}) {line['text']}", quote_from=line["text"])
            if problem:
                problems.append(problem)
                break   # one break is enough to send the line back
            dropped.append({"finding": r, "dropped": why_dropped})
        if problems:
            out.append({"verdict": "fail", "problem": problems[0]})
        else:
            out.append({"verdict": "pass", "problem": "", "dropped": dropped[0] if dropped else None})
    return out

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


BACKGROUND_QUESTIONS = {
    "unfilled": "Is any object only partly colored in, with blank, white or see-through patches inside its outline?",
    "split": "Is any object cut apart or incomplete, such as a cap with no stem under it?",
    "floating": "Is any object floating above the ground instead of standing on it?",
    "specks": "Are there stray specks or dots of color scattered around the edges of the objects?",
}


def review_background(folder, facts):
    """The four questions from the vision test of 2026-11-04, in one call. Only a note beside the background: the 7B model
    can't be the checker (BACKGROUNDS_METHOD.md rule 9), so this never sends work back."""
    folder = Path(folder)
    whole = Image.open(folder / "preview_1_whole.png")
    whole = whole.resize((whole.width * 2, whole.height * 2), Image.NEAREST)
    ask = " ".join(f'"{k}": {q}' for k, q in BACKGROUND_QUESTIONS.items())
    messages = [{"role": "system", "content": "You check 2D game background art for defects. Answer with only one JSON object of "
                                              "true or false values for the keys unfilled, split, floating and specks."},
                {"role": "user", "content": [{"type": "text", "text": ask}, {"type": "image_url", "image_url": {"url": _data_url(whole)}}]}]
    d = common.extract_json(common.ask("critic", messages, model=common.VISION_MODEL, max_tokens=80)) or {}
    answers = {k: d.get(k) in (True, "true", "yes") for k in BACKGROUND_QUESTIONS}
    return {"verdict": "fail" if any(answers.values()) else "pass", "answers": answers, "facts": facts}


def review_wardrobe(folder, concept, facts):
    r"""C:\cluster\WARDROBE_STYLIST_DESIGN.md step 5: does the item read as its idea, and does it sit right? One call on one
    picture (the close-up beside the sheet). Only a note beside the item: it never sends work back."""
    folder = Path(folder)
    close, row = Image.open(folder / "closeup.png"), Image.open(folder / "sheet.png")
    row = row.resize((round(row.width * 300 / row.height), 300))
    close = close.resize((round(close.width * 300 / close.height), 300), Image.NEAREST)
    both = Image.new("RGB", (close.width + row.width + 20, 300), (236, 233, 224))
    both.paste(close.convert("RGB"), (0, 0))
    both.paste(row.convert("RGB"), (close.width + 20, 0))
    where = "on top of each head" if concept.get("kind") == "hat" else "over the eyes of each character"
    ask = (f'Left: one item, close up. Right: the same item on every character. "reads": does the item look like '
           f'{concept.get("name")}? "sits": is it {where}? "note": what you see, in one short sentence.')
    messages = [{"role": "system", "content": "You check pixel-art hats and glasses for a game. Answer with only one JSON object "
                                              "with true or false for reads and sits, and a short note."},
                {"role": "user", "content": [{"type": "text", "text": ask}, {"type": "image_url", "image_url": {"url": _data_url(both)}}]}]
    d = common.extract_json(common.ask("critic", messages, model=common.VISION_MODEL, max_tokens=120)) or {}
    answers = {k: d.get(k) in (True, "true", "yes") for k in ("reads", "sits")}
    problems = ([] if answers["reads"] else [f"doesn't read as {concept.get('name')}"]) + ([] if answers["sits"] else ["doesn't sit right"])
    return {"verdict": "pass" if not problems else "fail", "what_i_see": str(d.get("note") or "")[:300], "problems": problems,
            "note_for_artist": "; ".join(problems), "answers": answers, "facts": facts}
