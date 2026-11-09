"""The GDD reader: each maker gets Section 21's opening and its own part, nothing else, and a missing GDD stops the run.

Reads the real GDD, so a change to its Content guide that breaks a maker's part shows here first.
usage: python test_gdd.py
"""
import tempfile
from pathlib import Path

import common
import gdd

HEADS = {"character-artist": "### 21.1 Characters", "roast-writer": "### 21.2 Roast lines",
         "wardrobe-stylist": "### 21.3 Hats and shades", "level-architect": "### 21.4 Backgrounds"}


def makers_read_it():
    """Every prompt a maker writes content from opens with its own part of the GDD. A stand-in model records the prompts."""
    import character_artist
    import level_architect
    import roast_writer
    import wardrobe_stylist
    seen = []

    def fake_ask_json(agent, messages, required, **kw):
        seen.append((agent, "\n".join(m["content"] for m in messages if m["role"] == "user")))
        if "first_name" in required:
            return {"first_name": "Testname", "hair": "a tall flat-top", "hair_color": "black", "beard": False, "beard_desc": "",
                    "face": "arched brows, wide eyes, a grin", "skin_tone": "brown", "why_distinct": "a flat-top"}
        if required == ["ideas"]:
            return {"ideas": []}
        if required == ["lines"]:
            return {"lines": []}
        return {k: [] for k in required}
    real = common.ask_json
    common.ask_json = fake_ask_json
    real_subs = common.SUBMISSIONS
    try:
        # An empty submissions folder: the real one holds the set's characters, and their hair styles are taken (2026-11-08).
        with tempfile.TemporaryDirectory() as subs:
            common.SUBMISSIONS = Path(subs)
            character_artist.concept("a new character", [], None, character_artist.SETS[0], 11)
        common.SUBMISSIONS = real_subs
        for call in (lambda: level_architect.recipe({"id": "idea_x", "theme": "a test", "style": "flat"}, None),
                     lambda: level_architect.write_ideas(1),
                     lambda: wardrobe_stylist.recipe({"name": "Test Hat", "kind": "hat", "looks": "a hat", "areas": ["Band"]}),
                     lambda: roast_writer.write("drowned", ["win"], [], [], [])):
            try:
                call()
            except (common.MalformedOutput, common.CrewStop, KeyError, TypeError):
                pass   # the stand-in's empty answers fail the makers' own checks; the prompts are what's tested
    finally:
        common.ask_json = real
        common.SUBMISSIONS = real_subs
    for agent in ("character-artist", "level-architect", "wardrobe-stylist", "roast-writer"):
        prompts = [p for a, p in seen if a == agent]
        assert prompts, agent
        for p in prompts:
            assert p.startswith("From the Bottom Busters game design document (GDD), Section 21"), (agent, p[:80])
            assert HEADS[agent] in p and not any(h in p for a, h in HEADS.items() if a != agent), agent
        print(f"{agent}: all {len(prompts)} of its generating prompts open with the GDD's opening and its own part")


def judge_tests():
    """A finding sends work back only when plain code and a second look both let it stand. Findings from run 20261107-155047."""
    import critic
    roast = gdd.guide("roast-writer")["text"]
    chars = gdd.guide("character-artist")["text"]
    gross = "The gross thing is never named. It's 'it,' a smell, a plumber, a bad curry, never 'poop' or 'fart.'"
    second = []

    def fake_ask_json(agent, messages, required, **kw):
        second.append(messages[-1]["content"])
        return {"breaks": answer[0], "reason": "stand-in"}
    real, answer = common.ask_json, [False]
    common.ask_json = fake_ask_json
    try:
        p, why = critic.judge({"rule": "No hats, glasses, masks or held objects. Players pick hats and shades at Character Select.",
                               "words": "full, neatly trimmed beard",
                               "why": "it may create a caricature, violating the 'no caricature' rule in spirit, though not in letter"},
                              chars, '{"beard_desc": "full, neatly trimmed beard"}')
        assert p is None and why.startswith("a maybe") and not second, (p, why)
        print("A hedged finding ('may', 'in spirit') is dropped by plain code, before any model call:", why)
        p, why = critic.judge({"rule": gross, "words": "poo", "why": "names the gross thing"}, roast,
                              "(Longest Streak Of Poo, on a win) Ten in a row. The level is now a monument.",
                              quote_from="Ten in a row. The level is now a monument.")
        assert p is None and why == "the words it quotes aren't in the work" and not second, (p, why)
        print("A finding that blames words the line doesn't have (here, the event's name) is dropped:", why)
        for words in ("Just the smell", "carry it further"):
            p, why = critic.judge({"rule": gross, "words": words, "why": "names the gross thing"}, roast,
                                  "You left no trace. Just the smell. Even the air refused to carry it further.")
            assert p is None and why.startswith("it blames words the rule allows") and not second, (p, why)
        print("A finding on the never-named rule that blames no banned word ('the smell', 'it') is dropped by plain code")
        p, why = critic.judge({"rule": "No pop culture.", "words": "No dignity", "why": "a pop culture trope"}, roast,
                              "No survivors. No witnesses. No dignity.")
        assert p is None and why.startswith("the second look found no break") and len(second) == 1, (p, why)
        assert '"No dignity"' in second[0] and "Do those words break that rule?" in second[0], second
        assert "trope" not in second[0], "the second look must not see the Critic's argument"
        print("A finding plain code can't rule out goes to a second look, which can overrule it:", why)
        second.clear()
        maurice = {"first_name": "Maurice", "set": "African American", "hair": "a round afro"}
        common.ask_json = lambda agent, messages, required, **kw: (
            {"verdict": "fail", "note_for_maker": "x", "problems": [{"rule": "No jokes about accents or the group, no nicknames or "
             "titles, and no word that names the group.", "words": "African American", "why": "it names the group"}]})
        v = critic.check_gdd("character-artist", maurice)
        assert v["verdict"] == "pass" and v["dropped"][0]["dropped"] == "the words it quotes aren't in the work", v
        common.ask_json = fake_ask_json
        print("A design isn't failed for the words of its set's name, which the game never shows")
        hats = gdd.guide("wardrobe-stylist")["text"]
        p, why = critic.judge({"rule": "It has to look like it belongs with the four already in the game.", "words": "Top Hat",
                               "why": "a formal top hat contrasts with the playful hats"}, hats, '{"name": "Top Hat"}', design=True)
        assert p is None and "checked on the picture" in why and not second, (p, why)
        missing = [r for r in critic.PICTURE_RULES + critic.NOT_RULES
                   if not any(critic.cited({"rule": r, "why": "x"}, gdd.guide(a)["text"]) for a in HEADS)]
        assert not missing, missing
        bg = gdd.guide("level-architect")["text"]
        p, why = critic.judge({"rule": "The game's terrain themes are blue stone, green sludge, pale bone, ice, charred ember and red "
                               "crimson, with the red lava world last.", "words": "haunted mansion",
                               "why": "a haunted mansion isn't one of the terrain themes"}, bg, '{"theme": "haunted mansion"}', design=True)
        assert p is None and "describes the game today" in why and not second, (p, why)
        print("A finding that quotes a sentence describing the game today (the terrain themes) is dropped: it isn't a rule")
        print("A design's text can't fail on a rule about how the finished art looks; each such rule is still in the GDD")
        p, why = critic.judge({"rule": "Every face gets the same cartoon treatment, with no exaggerated features.", "words": "bushy eyebrows",
                               "why": "bushy eyebrows could be seen as exaggerated"}, chars, '{"face": "bushy eyebrows"}')
        assert p is None and why.startswith("a maybe"), (p, why)
        opening = gdd.guide("level-architect")["text"].split("**The game, for every agent.**")[1].split("\n\n")[0].strip()
        assert critic.focus(opening, "copies a castle from another game, violating the rule against copying characters from "
                                     "other games or shows") == "Nothing is copied from real people, brands, logos, or characters from other games or shows."
        print("A finding quoting a whole paragraph is read as its one sentence, so it's checked against the right rule")
        answer[0] = True
        p, why = critic.judge({"rule": gross, "words": "poop", "why": "it says poop"}, roast, "You left poop everywhere.")
        assert why is None and p == f'it says poop (GDD: "{gross}")', (p, why)
        print("A finding the second look agrees with sends the work back, quoting the GDD rule:", p[:60])
    finally:
        common.ask_json = real


def main():
    for agent, head in HEADS.items():
        g = gdd.guide(agent)
        assert g["sections"] == ["21", gdd.PARTS[agent]], g["sections"]
        assert "**The game, for every agent.**" in g["text"], agent
        assert head in g["text"], (agent, head)
        others = [h for a, h in HEADS.items() if a != agent]
        assert not any(h in g["text"] for h in others), (agent, [h for h in others if h in g["text"]])
        assert "## 20." not in g["text"], agent
        print(f"{agent} reads the opening and {head[4:]}, and no other maker's part ({len(g['text'].split())} words)")

    assert "Larry" in gdd.guide("character-artist")["text"]
    assert "Dead. Even the enemies looked away out of respect." in gdd.guide("roast-writer")["text"]
    assert "silver aviators" in gdd.guide("wardrobe-stylist")["text"]
    assert "576 by 324" in gdd.guide("level-architect")["text"]
    print("Each part carries its own rules: the roster, the kept lines, the four wearables, the layer size")

    block = gdd.prompt_block("roast-writer")
    assert block.startswith("From the Bottom Busters game design document (GDD), Section 21") and "Section 21.2" in block
    print("The prompt block names the GDD and the sections it quotes")

    makers_read_it()

    import critic
    text = gdd.guide("wardrobe-stylist")["text"]
    assert critic.cited({"rule": "Real logos, brands or team names.", "why": "a swoosh"}, text) == \
        'a swoosh (GDD: "Real logos, brands or team names.")'
    assert critic.cited({"rule": "**A hat that floats above the head**, or shades that miss the eyes", "why": "x"}, text)
    assert critic.cited({"rule": "A hat that floats over the head, or shades that miss the eyes.", "why": "x"}, text)
    roast = gdd.guide("roast-writer")["text"]
    assert critic.cited({"rule": "The gross thing is never named. It's 'it,' a smell, a plumber, a bad curry, never 'poop' or 'fart.'",
                         "why": "pooped"}, roast)
    print("A quote counts with its quote marks swapped, its markdown, or a one-word slip")
    assert critic.cited({"rule": "No mechanical parts on any hat.", "why": "a propeller"}, text) is None
    assert critic.cited({"rule": "Hats must never have moving parts or propellers.", "why": "a propeller"}, text) is None
    assert critic.cited({"rule": "", "why": "x"}, text) is None and critic.cited("Real logos", text) is None
    print("The Critic's problem stands only when the rule it quotes is in the GDD; an invented rule is dropped")
    judge_tests()

    real = gdd.SOURCE
    with tempfile.TemporaryDirectory() as tmp:
        for text, why in ((None, "isn't readable"), ("# A GDD\n\n## 20. Risks\n", "no Section 21"),
                          ("## 21. Content guide\n\nOpening.\n\n### 21.1 Characters\n\nRules.\n", "missing its opening or Section 21.2")):
            gdd.SOURCE = Path(tmp) / "gdd.md"
            if text is not None:
                gdd.SOURCE.write_text(text, encoding="utf-8")
            try:
                gdd.guide("roast-writer")
                raise AssertionError(f"should stop: {why}")
            except common.CrewStop as e:
                assert why in str(e), e
                print(f"A GDD that {why.split(' or ')[0]} stops the run: {str(e)[:80]}")
        gdd.SOURCE = real
    try:
        gdd.guide("foreman")
        raise AssertionError("an agent with no part should stop")
    except common.CrewStop:
        print("An agent with no part in the Content guide stops")
    print("all passed")


if __name__ == "__main__":
    main()
