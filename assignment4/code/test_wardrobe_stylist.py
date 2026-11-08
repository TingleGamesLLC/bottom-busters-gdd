"""The Wardrobe Stylist: the 4 items as recipes, the Bridge's checks, the idea list, one item made on a stand-in model, storing
approved items, and its run in the Orchestrator on a stand-in board. Reads the game's sprites and C:\\bbust\\wearables, never
writes them; spends nothing.
usage: python test_wardrobe_stylist.py
"""
import copy
import json
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

import bridge
import common
import orchestrator
import paperclip_board as pb
import wardrobe_stylist as ws

PARTY = {"name": "Test Party Hat", "kind": "hat",
         "regions": [{"id": 1, "name": "CONE", "color": [60, 120, 220], "colorable": True},
                     {"id": 2, "name": "STRIPES", "color": [250, 210, 60], "colorable": True},
                     {"id": 3, "name": "POM", "color": [240, 60, 90], "colorable": True}],
         "shapes": [{"shape": "poly", "points": [[5, 30], [27, 30], [16, 5]], "region": 1},
                    {"shape": "poly", "points": [[8, 24], [24, 24], [22, 19], [10, 19]], "region": 2},
                    {"shape": "ellipse", "box": [12, 0, 20, 8], "region": 3}]}


def same(a, b):
    return a.size == b.size and np.array_equal(np.asarray(a.convert("RGBA")), np.asarray(b.convert("RGBA")))


def method_tests():
    for name, recipe in ws.EXAMPLES.items():
        art, mask, _ = ws.draw(recipe)
        assert same(ws.full_size(art), Image.open(ws.GAME_ITEMS / f"{name}.png")), name
        if recipe["kind"] == "hat":
            assert same(ws.full_size(mask), Image.open(ws.GAME_ITEMS / f"{name}_mask.png")), name
    print("The 4 items in the game, written as recipes, draw pixel for pixel the same as their PNGs")
    for name, recipe in ws.EXAMPLES.items():
        assert bridge.check_wardrobe_recipe(recipe) == [], (name, bridge.check_wardrobe_recipe(recipe))
        assert bridge.check_wardrobe_art(recipe) == [], (name, bridge.check_wardrobe_art(recipe))
    print("The 4 pass every recipe and art check")


def broken(change):
    r = copy.deepcopy(PARTY)
    change(r)
    return bridge.check_wardrobe_recipe(r) or bridge.check_wardrobe_art(r)


def check_tests():
    assert bridge.check_wardrobe_recipe(PARTY) == [] and bridge.check_wardrobe_art(PARTY) == []
    cases = {
        "a shape type nobody draws": lambda r: r["shapes"].append({"shape": "star", "points": [[1, 1]], "region": 1}),
        "a region that isn't defined": lambda r: r["shapes"].append({"shape": "rect", "box": [1, 1, 2, 2], "region": 9}),
        "a color area numbered past 3": lambda r: r["regions"].append({"id": 4, "name": "X", "color": [1, 2, 3], "colorable": True}),
        "a box drawn backwards": lambda r: r["shapes"].append({"shape": "ellipse", "box": [9, 9, 2, 2], "region": 1}),
        "a shape off the grid": lambda r: r["shapes"].append({"shape": "rect", "box": [1, 1, 60, 2], "region": 1}),
        "a color that isn't a color": lambda r: r["regions"][0].update(color="blue"),
        "a name with a period": lambda r: r.update(name="Mr. Hat"),
        "a hat floating above the head": lambda r: [s.update(points=[[x, y - 8] for x, y in s["points"]]) if "points" in s
                                                    else s.update(box=[s["box"][0], s["box"][1] - 8, s["box"][2], s["box"][3] - 8])
                                                    for s in r["shapes"]],
        "a color area too small to see": lambda r: r["shapes"].__setitem__(1, {"shape": "rect", "box": [16, 15, 16, 15], "region": 2}),
        "a region with no pixels": lambda r: r["regions"].append({"id": 5, "name": "GHOST", "color": [9, 9, 9], "colorable": False}),
    }
    for what, change in cases.items():
        assert broken(change), what
    shades = copy.deepcopy(ws.EXAMPLES["black_shades"])
    shades["regions"].append({"id": 1, "name": "LENS", "color": [1, 1, 1], "colorable": True})
    assert bridge.check_wardrobe_recipe(shades), "shades with a color area"
    one = copy.deepcopy(ws.EXAMPLES["black_shades"])
    one["shapes"] = [s for s in one["shapes"] if s.get("box", [0])[0] < 10]
    assert any("lens" in p for p in bridge.check_wardrobe_art(one)), bridge.check_wardrobe_art(one)
    print("Unknown shapes, undefined regions, bad color areas, backwards boxes, shapes off the grid, bad colors, a period "
          "in the name, a floating hat, a color area too small, an empty region, colored shades and one-lens shades are "
          "each refused")


def idea_tests():
    ideas = json.loads((common.WORK / "wardrobe_ideas_40.json").read_text(encoding="utf-8"))
    assert ws.check_ideas(ideas) == [], ws.check_ideas(ideas)
    assert sum(i["kind"] == "hat" for i in ideas) == 30 and sum(i["kind"] == "shades" for i in ideas) == 10
    print("The 40 ideas pass: 30 hats and 10 shades, no repeats, none of the 4 in the game")
    assert any("Santa" in p for p in ws.check_ideas(ideas[:-1] + [{"name": "Santa Hat", "kind": "hat", "areas": ["A"],
                                                                     "looks": "x"}]))
    assert any("twice" in p for p in ws.check_ideas(ideas[:-1] + [dict(ideas[0])]))
    assert any("color areas" in p for p in ws.check_ideas([{"name": "Bare Hat", "kind": "hat", "areas": [], "looks": "x"}], full=False))
    assert any("color areas" in p for p in ws.check_ideas([{"name": "Pink Shades", "kind": "shades", "areas": ["L"], "looks": "x"}], full=False))
    print("An idea already in the game, one listed twice, a hat with no color areas or shades with some are refused")


def post_idea(root, n, name, kind="hat", decision="approve"):
    d = root / ws.IDEAS / f"idea_{n:02}"
    d.mkdir(parents=True)
    idea = {"name": name, "kind": kind, "areas": ["CONE", "STRIPES", "POM"] if kind == "hat" else [], "looks": "a test"}
    (d / "manifest.json").write_text(json.dumps({"kind": ws.IDEA_KIND, "name": f"{name}. a test", "idea": idea}), encoding="utf-8")
    if decision:
        (d / "decision.json").write_text(json.dumps({"decision": decision, "note": ""}), encoding="utf-8")


def make_tests(tmp):
    common.SUBMISSIONS, common.WORK = tmp / "submissions", tmp / "work"
    common.WORK.mkdir(parents=True)
    ws.APPROVED = tmp / "approved"
    assert ws.state() == {"approved": 0, "waiting": 0, "ideas_waiting": 0, "next": 0}, ws.state()
    post_idea(common.SUBMISSIONS, 1, "Test Party Hat")
    post_idea(common.SUBMISSIONS, 2, "Test Cone")
    post_idea(common.SUBMISSIONS, 3, "Not Yet", decision=None)
    post_idea(common.SUBMISSIONS, 4, "Said No", decision="reject")
    assert ws.state() == {"approved": 0, "waiting": 0, "ideas_waiting": 2, "next": 2}, ws.state()
    tasks = ws.tasks(2)
    assert [t["idea"] for t in tasks] == ["idea_01", "idea_02"] and "Test Party Hat" in tasks[0]["brief"], tasks
    print("The first run draws the 2-item test, from approved ideas only")

    asked = []

    def fake(agent, messages, required, **kw):
        asked.append((agent, messages))
        return copy.deepcopy(PARTY)
    real = common.ask_json
    common.ask_json = fake
    try:
        folder, concept = ws.make(tasks[0], None, [], "David's note: make the pom bigger", 1)
    finally:
        common.ask_json = real
    assert asked[0][0] == "wardrobe-stylist"
    prompt = asked[0][1][-1]["content"]
    assert "Test Party Hat" in prompt and "make the pom bigger" in prompt and "santa_hat" in prompt.lower().replace(" ", "_")
    print("The prompt holds the idea, David's note and the 4 items' own recipes")
    m = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert m["kind"] == ws.KIND and m["agent"] == ws.AGENT and m["idea"] == "idea_01" and m["name"] == "Test Party Hat"
    assert m["description"] == "Hat, 3 color areas", m["description"]
    for f in m["previews"] + m["files"]:
        assert (folder / f).is_file(), f
    assert all(m["fit"].values()) and len(m["fit"]) == 10, m["fit"]
    assert Image.open(folder / m["files"][0]).size == (256, 245)
    print("An item's folder has its art, mask, recipe, the sheet on all 10 characters and a close-up")
    assert bridge.check_wardrobe_item(folder) == [], bridge.check_wardrobe_item(folder)
    facts = bridge.wardrobe_facts(folder)
    assert facts["nearest_item"] and facts["difference"] > 0, facts
    print("The Bridge passes it and measures it against the 4 in the game")
    Image.new("RGBA", (256, 245)).save(folder / m["files"][0])
    assert any("doesn't match its recipe" in p for p in bridge.check_wardrobe_item(folder))
    print("Art that doesn't match its recipe is refused")
    ws.draw_files(folder)   # draws the art from its recipe again
    dst = ws.publish(folder)
    assert dst.parent == common.SUBMISSIONS / ws.ITEMS and not folder.exists()
    assert ws.state()["waiting"] == 1 and ws.state()["next"] == 0
    print("Published items wait on David, and no new batch starts until he decides them")

    (dst / "decision.json").write_text(json.dumps({"decision": "approve", "note": ""}), encoding="utf-8")
    assert ws.state() == {"approved": 1, "waiting": 0, "ideas_waiting": 1, "next": 1}, ws.state()
    assert ws.store_approved() == 1
    stored = ws.APPROVED / dst.name
    entry = json.loads((stored / "catalog_entry.json").read_text(encoding="utf-8"))
    assert entry == {"id": dst.name, "kind": "hat", "name": "Test Party Hat", "art": dst.name, "mask": dst.name + "_mask",
                     "regions": ["CONE", "STRIPES", "POM"], "source": "", "steamItemDef": 0, "season": ""}, entry
    assert (stored / f"{dst.name}.png").is_file() and (stored / f"{dst.name}_mask.png").is_file() and (stored / "recipe.json").is_file()
    print("An approved item goes outside the game with its art, mask, recipe and a catalog entry in the game's format")

    redo = {"id": "redo-1", "name": "[Wardrobe Stylist] Redo Test Party Hat: pom bigger",
            "desc": f"David rejected Test Party Hat ({dst.name}) from [Wardrobe Stylist] 40 new hats and shades.\n"
                    "David's note: pom bigger", "agent": "wardrobe-stylist"}
    t = ws.redo_task(redo)
    assert t["idea"] == "idea_01" and t["note"] == "pom bigger", t
    print("A redo card redraws the same idea with David's note")


class Board:
    def __init__(self, cards=()):
        self.moves, self.comments, self.list = [], [], list(cards)

    def cards(self, list_name):
        return [c for c in self.list if c["list"] == list_name]

    def move(self, card, list_name):
        self.moves.append((card["id"], list_name))
        card["list"] = list_name

    def comment(self, card, text):
        self.comments.append(text)


def orchestrator_tests(tmp):
    common.RUNS = tmp / "runs"
    orchestrator.set_status = lambda u: None
    orchestrator.report_costs = lambda board, run, card: None
    assert orchestrator.MAKERS["Wardrobe Stylist"]["id"] == "wardrobe-stylist"
    card = {"id": "bot-7", "name": "[Wardrobe Stylist] 40 new hats and shades", "list": pb.BACKLOG, "agent": "wardrobe-stylist",
            "desc": ""}
    worked = []
    orchestrator.work_task = lambda run, board, c, maker, task, slot, seed, to_review, notes=None: \
        worked.append((c["id"], task["idea"], notes)) or {"task": task["id"], "name": "n", "skin": "s", "look": "hat", "skin_tone": ""}
    orchestrator.technical_writer.summarize = lambda run, c, results: "summary"
    orchestrator.technical_writer.compact_memory = lambda c, s: None
    ws.store_approved = lambda: 0

    ws.state = lambda: {"approved": 3, "waiting": 2, "ideas_waiting": 9, "next": 0}
    board = Board([dict(card)])
    assert orchestrator.run_wardrobe(board, dict(card), common.Run("20261104-120000-w-wait")) == 0 and board.moves == [] and worked == []
    print("While David is deciding the last items, the run leaves the card alone")

    ws.state = lambda: {"approved": 3, "waiting": 0, "ideas_waiting": 9, "next": 5}
    ws.tasks = lambda n: [{"id": f"t{k + 1}", "brief": "b", "idea": f"idea_{k:02}"} for k in range(n)]
    board = Board([dict(card)])
    assert orchestrator.run_wardrobe(board, dict(card), common.Run("20261104-120000-w-go")) == 0
    assert len(worked) == 5 and [l for _, l in board.moves] == [pb.LEASED, pb.BACKLOG], board.moves
    print("A batch draws 5 items through the usual steps and puts the card back in the queue")

    worked.clear()
    redo = {"id": "redo-1", "name": "[Wardrobe Stylist] Redo X: pom bigger", "list": pb.BACKLOG, "agent": "wardrobe-stylist",
            "desc": "David rejected X (test_party_hat) from c.\nDavid's note: pom bigger"}
    ws.redo_task = lambda c: {"id": "t1", "brief": "Redraw X", "idea": "idea_01", "note": "pom bigger"}
    board = Board([dict(card), redo])
    assert orchestrator.run_wardrobe(board, dict(card), common.Run("20261104-120000-w-redo")) == 0
    assert worked == [("redo-1", "idea_01", "David rejected the last one: pom bigger")], worked
    assert board.moves[-1] == ("redo-1", pb.PLAYTEST), board.moves
    print("A redo card goes first: the same idea with David's note, then it waits at Your Playtest")

    ws.state = lambda: {"approved": 40, "waiting": 0, "ideas_waiting": 0, "next": 0}
    board = Board([dict(card)])
    assert orchestrator.run_wardrobe(board, dict(card), common.Run("20261104-120000-w-done")) == 0
    assert board.moves == [("bot-7", pb.DONE)] and not any("\\" in c for c in board.comments), (board.moves, board.comments)
    print("With 40 approved, the card is done")


def seat_tests():
    """A hat drawn a little high is moved down to sit on the head, before the Bridge sees it (run 20261107-163826)."""
    import copy
    import bridge
    high = {"name": "Test Cap", "kind": "hat", "regions": [{"id": 1, "name": "CAP", "color": [139, 100, 65], "colorable": True}],
            "shapes": [{"shape": "ellipse", "box": [4, 14, 28, 26], "region": 1}]}
    assert "the hat doesn't reach the bottom of its box, so it would float above the head" in bridge.check_wardrobe_art(high)
    seated = ws.seat_hat(copy.deepcopy(high))
    assert not any("float" in p for p in bridge.check_wardrobe_art(seated)), bridge.check_wardrobe_art(seated)
    assert seated["shapes"][0]["box"][1] > 14 and seated["shapes"][0]["box"][3] - seated["shapes"][0]["box"][1] == 12
    print(f"A hat ending at y 26 is moved down to y {seated['shapes'][0]['box'][3]}, the same size, and sits on the head")
    shades = {"kind": "shades", "shapes": [{"shape": "rect", "box": [0, 0, 3, 3], "region": 1}]}
    assert ws.seat_hat(copy.deepcopy(shades)) == shades
    print("Shades are left where they are")


def name_tests(tmp):
    """A name David rejected is free for its redo; a name waiting or approved isn't (run 20261107-164801: Top Hat)."""
    import bridge
    common.SUBMISSIONS = tmp / "submissions"
    for folder, name, decision in (("top_hat", "Top Hat", "reject"), ("cone", "Test Cone", None), ("bow", "Test Bow", "approve")):
        d = common.SUBMISSIONS / ws.ITEMS / folder
        d.mkdir(parents=True)
        (d / "manifest.json").write_text(json.dumps({"kind": ws.KIND, "name": name, "idea": "idea_x"}), encoding="utf-8")
        if decision:
            (d / "decision.json").write_text(json.dumps({"decision": decision}), encoding="utf-8")
    names = bridge.wardrobe_names(common.SUBMISSIONS / ws.ITEMS / "top_hat_2")
    assert "top hat" not in names and "test cone" in names and "test bow" in names and "santa hat" in names.union(
        {r["name"].lower() for r in ws.EXAMPLES.values()}), names
    print("A rejected Top Hat leaves its name free for its redo; a waiting or approved item keeps its name")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        name_tests(Path(tmp))
    seat_tests()
    method_tests()
    check_tests()
    idea_tests()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        make_tests(tmp)
        orchestrator_tests(tmp)
    print("all passed")


if __name__ == "__main__":
    main()
