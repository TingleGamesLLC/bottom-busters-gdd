"""The fixed Critic on the real model: the work it wrongly failed in run 20261107-155047, and work it must still fail."""
import json
import sys
sys.path.insert(0, r"C:\cluster\crew")
import common, critic, roast_writer
common.PROMPT_LOG = None
R = r"C:\cluster\crew\runs\20261107-155047-"
maurice = json.load(open(R + r"character-artist\messages\0003_character-artist_to_critic_design.json", encoding="utf-8"))["payload"]["design"]
top_hat = json.load(open(R + r"wardrobe-stylist\messages\0002_wardrobe-stylist_to_critic_design.json", encoding="utf-8"))["payload"]["design"]
cases = [
 ("character-artist", "judgment (vs Terry)", maurice),
 ("character-artist", "should pass", {"first_name": "Dwayne", "set": "African American", "skin_tone": "chestnut", "hair": "tall rounded high-top fade (black)", "beard": "short boxed beard", "face": "thick arched brows, wide eyes, a big confident grin", "why_distinct": "No one on the roster has a high-top fade"}),
 ("character-artist", "should fail", {"first_name": "Chief", "set": "Native American/Indigenous", "skin_tone": "copper", "hair": "two long braids under a feather headdress (black)", "beard": "none", "face": "a huge hooked nose and a stern frown", "why_distinct": "The headdress makes him stand out"}),
 ("wardrobe-stylist", "should pass", top_hat),
 ("wardrobe-stylist", "should pass", {"name": "Propeller Beanie", "kind": "hat", "idea": "a round beanie with a little propeller on top", "outline": "the usual dark outline", "regions": [{"name": "Cap", "color": [200, 40, 40], "players_recolor_it": True}, {"name": "Propeller", "color": [240, 200, 40], "players_recolor_it": True}], "shapes": 6}),
 ("wardrobe-stylist", "should fail", {"name": "Nike Cap", "kind": "hat", "idea": "a baseball cap with the Nike swoosh logo, soft shading on the crown", "outline": "none", "regions": [{"name": "Cap", "color": [20, 20, 20], "players_recolor_it": True}, {"name": "Swoosh", "color": [255, 255, 255], "players_recolor_it": False}], "shapes": 9}),
 ("level-architect", "should fail", {"theme": "Bowser's castle from Super Mario", "style": "pixel art", "ground_type": "stone", "palette": [[60, 20, 20], [200, 80, 20]], "layers": [{"kind": "sky", "speed": 0.05, "note": "sky with mountains and a castle painted in"}, {"kind": "objects", "speed": 0.5, "objects": ["Bowser statue", "lava"]}]}),
]
for agent, expect, work in cases:
    v = critic.check_gdd(agent, work)
    print(f"{agent:17} {expect:20} -> {v['verdict']:4} {v['problems']}")
    for d in v["dropped"]:
        print(f"{'':39} dropped: {d['dropped'][:140]}")
lines = [("", "loss", "Dead. Even the enemies looked away out of respect.", "pass"),
         ("longestStreak", "win", "Ten in a row. The level is now a monument.", "pass"),
         ("fullCoverage", "loss", "You left no trace. Just the smell. And the regret.", "pass"),
         ("fullCoverage", "loss", "No survivors. No witnesses. No dignity.", "pass"),
         ("fullCoverage", "loss", "Full coverage. The air itself refused to carry it further.", "pass"),
         ("fullCoverage", "win", "Every target hit. The cleanup crew has been reassigned.", "pass"),
         ("fullCoverage", "win", "Complete. The level has been declared unfit for occupancy.", "pass"),
         ("directDeposit", "win", "You pooped all over them, dude!", "fail"),
         ("kills", "loss", "Nice belly. Shame about the aim.", "fail"),
         ("bombsOnTarget", "win", "Bombs away. Like that famous plumber in the red hat.", "fail")]
batch = [{"text": t, "topic": k, "outcome": o, "noGauntlet": False} for k, o, t, _ in lines]
for (k, o, t, expect), v in zip(lines, critic.check_gdd_lines(batch, roast_writer.describe)):
    print(f"roast line should {expect:4} -> {v['verdict']:4} {t} | {v['problem'][:160]}" +
          (f" | dropped: {v['dropped']['dropped'][:120]}" if v.get("dropped") else ""))
print("critic tokens:", common.usage.tokens)
