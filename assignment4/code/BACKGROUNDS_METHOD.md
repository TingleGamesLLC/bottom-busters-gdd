# How new parallax backgrounds are made

DAVID, 2026-11-04: "we're building methodology here, so these are methods that you should be learning and never forgetting
for all future renditions." Every round, every agent and every session that makes background art follows this file. A
lesson learned the hard way gets added here the same day.

## What a background is

- 100 new, unique parallax backgrounds, made by us. No craftpix and no bought art (DAVID, 2026-11-03).
- The game's shape for one: a solid sky layer, then see-through layers from far to near, each 576 by 324. Every layer loops
  sideways, because it drifts at its own speed and wraps (`Backdrop3D.cs`).
- PixelLab is for character sprites only. Background art is painted with ComfyUI (Flux schnell) on the dev PC.

## The system (DAVID, 2026-11-04)

Simple systems, one job per layer, stacked back to front. Never paint a whole scene and cut it apart.

- **Color layer:** the sky color, a gradient made by code. Solid, and it loops by itself.
- **Haze layer:** a soft see-through band of color made by code. It loops by itself.
- **Object layer:** one kind of object per layer (distant mushroom shapes, a row of big mushrooms, foreground grass). ComfyUI
  paints one object at a time, which cuts out cleanly; code places the objects along the strip, wrapping across the ends,
  so every object is whole and the layer loops by construction.
- **A background is a recipe:** a palette, and the list of layers in order with their drift speeds. 100 backgrounds are 100
  recipes drawn from a growing library of objects, colors and hazes.

**No visible seams, ever, on any layer while it moves (DAVID, 2026-11-04).** The vertical lines in the craftpix originals are
flaws: never copy them, and never copy anything else that's poorly made just because the originals do it.

## Rules learned so far

0. **Loop by construction, never by repair.** Repainting a band at the wrap point left vertical lines (tests of 2026-11-04).
   Color and haze layers are made to loop by code, and object layers wrap their objects across the edge.
1. **Every object stays whole on one layer.** A mushroom's cap and stem are one object. Never split a layer by depth bands or
   anything else that ignores objects. (Test of 2026-11-04: a depth split put a cap and its stem on different layers.)
2. **Cut out with a key color the scene never uses.** Paint every non-sky layer on a flat key color that isn't in the theme's
   palette, and keep that color out of the prompt's subject. Keying a color the art also uses deletes parts of the art.
   (Test of 2026-11-04: magenta keying ate the pink and violet parts of the mushrooms.)
3. **No holes inside objects.** Any see-through spot inside an object's outline is a defect: fill it if it's object color,
   keep it only if it's real background showing through.
4. **The sky layer is only sky.** Say so plainly in the prompt (no ground, trees, hills or objects), and check it.
5. **Loops with no visible seam.** See rule 0. (Replaced: repainting a band at the wrap point, even blended, still showed
   lines.)
8. **A color cut-out fails behind haze.** Flux won't paint a flat key color behind hazy or distant scenery; it fades the key
   into the scene (round 3, 2026-11-04). Haze is its own code-made layer, and objects are painted one at a time.
6. **Check every layer on its own, at full size, before David sees anything.** The whole picture can look fine while a layer is
   broken. A layer that fails a check is fixed or repainted, never shown. Small defects are defects, not "leftovers".
7. **David's taste so far:** he likes the violets of the first test (giant mushroom forest at dusk).

9. **The 7B vision model can't be the checker.** Tested 2026-11-04 on six layers with known answers, four yes/no questions
   each: it got the overall pass or fail right on 5 of 6, but only ever said yes to "is anything floating". It never caught
   half-painted objects, a cap split from its stem, or specks, and it passed the version with floating stems and specks. Plain-
   code checks carry the gate; the vision model's answer is a note beside the work, and David's approval decides.

## The checks every layer passes before it's shown

| Check | Pass |
|---|---|
| Holes inside objects | No see-through pixels of object color inside any object's outline |
| Key color left behind | No visible key-colored pixels or fringe on the layer |
| Sky only | The sky layer has no ground or objects |
| Wraps cleanly | The layer's left and right edges match when placed side by side |
| No lines while moving | Frames rendered across one full loop of every layer show no vertical line or column jump anywhere |
| Objects whole | No object is cut off by a layer boundary or split across layers |

## Where it's shown

On the dashboard's Characters tab, as a submission in `C:\cluster\submissions\backgrounds\<id>` with still previews, and as a
moving GIF on a claude.ai page David can open on his phone.
