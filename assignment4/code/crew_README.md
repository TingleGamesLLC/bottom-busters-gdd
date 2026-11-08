# Bottom Busters Agent Crew

Assignment #3, Multi-Agent AI for Game Development (ELVTR). David St. Onge, Tingle Games LLC.

## What this crew produces, and what game it's for

The game is **Bottom Busters**, a comedy arcade game for Steam and itch.io, built in Unity 6.3. Players are chubby men in white briefs who fly by farting and pop each other's cheeks.

This crew produces **new playable characters**, **new animated backgrounds**, **new roast lines** and **new hats and shades**. Players told me the ten current characters are hard to tell apart, so each new one has to read at game size, about 100 pixels tall. One character is 30 files in the formats the game already loads: a body sprite, 12 death-flail frames, a splat pair, and their Unity import settings. One background is a set of 576x324 parallax layers that loop with no seam, made by the method in `BACKGROUNDS_METHOD.md`. One roast line is a short line the narrator reads on the end card, tied to what the player just did and written in the voice of the 40 lines I kept. Roast lines are content only: approved lines wait in a file outside the game. One hat or pair of shades is drawn from flat shapes the way the 4 in the game were (`draw_wearables.py`), with a color mask for a hat; approved items wait outside the game too.

The crew works from my Paperclip board, which replaced Trello. Paperclip runs on my dev PC, every agent's heartbeat is off, and each card is assigned to one agent. The board's priority order is my priority list. Each maker takes its own top card, and the makers run alongside each other.

## The agents

| Agent | Kind | Job | Hands off |
|---|---|---|---|
| Orchestrator | qwen3:30b-instruct on the local cluster | Takes the next card, splits it into tasks, leases it to one maker, moves it across the board, runs the pipeline | Task briefs (JSON) |
| Character Artist | qwen3:30b-instruct for the concept, PixelLab for the art | Designs a look nobody could mistake for the roster, paints the hair and beard, and pulls them onto the body's own pixel grid | A submission folder and manifest |
| Level Architect | qwen3:30b-instruct for the recipe, Flux schnell in ComfyUI on the dev PC for each object | Builds a background from an idea I approved: a sky and haze made in code, and object layers painted one whole object at a time | A submission folder with the layers, previews and a moving loop |
| Roast Writer | qwen3:30b-instruct on the local cluster, one call to write and a separate one to pick | Writes 4 candidates for every line needed, keeps the ones that pass the Bridge, and puts the best on an approval card. My reject notes go into its next batch | Roast lines, each in its own submission folder |
| Wardrobe Stylist | qwen3:30b-instruct on the local cluster | Turns an idea I approved into a recipe of flat shapes; plain code draws it with `draw_wearables.py`'s own drawing and puts it on every character | An item's art, mask, recipe and a sheet of it on every character |
| Bridge | A script, no AI | Checks the files before anything looks at them. Characters: sizes, silhouette, palette, frame count, unique Unity ids, and a measured difference from every roster character. Backgrounds: one solid sky, clean loops with no seam or vertical line while moving, no leftover key color or specks, whole objects, and a measured difference from the other backgrounds. Roast lines: 15 words at most, periods only, the gross thing never named, no names or body jokes, the Gauntlet flag where it's needed, and no repeats. Hats and shades: the recipe draws, flat fills with an outline all round, color areas big enough to color, a hat reaching the head, a lens on each eye, a place on every character, and a measured difference from every other item | Pass, or a fix prompt back to the maker |
| Critic | qwen3:30b-instruct for the GDD check, qwen2.5vl:7b vision model for the picture review, on the local cluster | The GDD check: every design, before any art is made, and every roast line is checked against the same part of the GDD the maker read. A fail goes back to the maker with the GDD rule it broke, quoted word for word, and costs it a cheek. The picture review looks at the work at game size; its answer is a note beside the work, not a gate | A verdict (JSON) |
| Technical Writer | qwen3:30b-instruct on the local cluster | Writes the run summary, keeps the crew's memory short, closes finished cards, keeps the diagram current | Summary, log, memory |
| Foreman | Plain code, every hour | Puts stalled cards back in the queue, closes tasks a dead run left open, unblocks cards whose blocker finished, and raises failed runs, my notes and my rejections with me, once each. No feature work | Tasks for me in Paperclip |

## How they work together

See `crew.mmd`. The same diagram:

```mermaid
MERMAID_DIAGRAM
```

- **Every maker reads the GDD before it writes (Assignment #4).** The Bottom Busters GDD's Section 21, the Content guide, has an opening every agent reads and one part per maker: 21.1 Characters, 21.2 Roast lines, 21.3 Hats and shades, 21.4 Backgrounds. `gdd.py` reads it from the game's repo, and each maker's generating prompt opens with the opening and its own part, word for word. A missing GDD stops the run.
- **The consistency check loop.** A maker's design (a character concept, a background recipe, a hat or shades recipe) goes to the Critic's GDD check before anything is built from it, and each roast line that passes the Bridge goes through it before the pick. Each problem the Critic raises has to quote the GDD rule it breaks and the words in the work that break it. Plain code drops a problem whose rule isn't in the GDD, that hedges ("may", "in spirit"), that blames words the work doesn't have, that quotes a sentence describing the game rather than a rule, that judges a design's text on how the finished picture will look, or that fails a roast line for words the never-named rule allows. What's left goes to a second look: two separate calls that see only the rule and the blamed words, never the Critic's argument, and both have to find a break. A fail goes back to the maker with the rule, and two fails stop the task. Every dropped finding is kept with the reason it was dropped. Run 20261107-155047 is why: the first version stopped three makers on findings like "Just the smell" breaking a rule that allows "a smell". Every design, verdict and send-back is a file in the run's `messages` folder, and every prompt and reply is in the run's `prompts.jsonl`.
- **Handoffs are files with a declared shape.** Agents never call each other. Every handoff is a JSON message in the run's `messages` folder, so any step can be read or re-run alone. `sample_run/messages` has a real run's.
- **One writer for shared state.** Only the Orchestrator writes `run.json`, under a lock.
- **Malformed output is caught and fixed.** A model reply that isn't the JSON asked for gets one fix prompt. Files that fail the Bridge go back to the maker with instructions.
- **Two cheeks per agent, like the characters in the game.** A send-back pops one, two pops stop the task and the run says why, and a finished job refills them. Each agent has a token cap per run and its own key, so its usage is counted separately.
- **Memory stays short.** The Technical Writer keeps one line per run and folds old lines together, so a run starts from a short summary instead of everything that came before.
- **A person is the last gate.** The crew stops at Your Playtest. I approve or reject each submission on an approval card in my Paperclip inbox, I play the build, and nothing is committed without my say-so. The shipped game contains no AI from this crew, only the files it made.

## What keeps the art consistent

Only the hair, beard and skin tone change. The body, eyes, nose and mouth stay the template's own pixels, so hats, shades, cheeks and the uzi still line up. Death art isn't drawn by a model: the flail frames are the template's frames wearing the new head, and the splat pair comes from `splat_faces.py`, the tools that made the original ten.

## Running it

```
python orchestrator.py                         one run: each maker takes its own top card, side by side; skipped if the game is running
python orchestrator.py --now                   one run even if the game is running
python orchestrator.py --maker level-architect one maker only
python orchestrator.py --dry                   says which card each maker would take, and does nothing else
python test_sendback.py                        the send-back and stop paths, using no model time
```

It needs my local setup, so it won't run elsewhere as is: the model cluster behind MindRouter, PixelLab, ComfyUI with Flux schnell on the dev PC, the Bottom Busters project, and Paperclip on the dev PC. `sample_run/` holds a complete real run so the output can be read without any of that. API keys aren't in this repository.

Windows scheduled tasks: `Paperclip` starts Paperclip when I log in, `BBUST Foreman` runs the Foreman every hour, and `BBUST Crew` can run the crew every 30 minutes. `BBUST Crew` is registered and turned off.

## The sample run

Run `20261030-211259`, on 2026-10-30, took the card "[Character Artist] First batch of new playable characters" and made two characters. Nothing was sent back in that run. `test_sendback.py` covers those paths.

| Character | Look | Skin tone |
|---|---|---|
| Puffball (player11) | Fluffy white poof in a perfect sphere | Pale |
| Fuzzball (player12) | Stiff electric blue spikes | Tan |

Each folder in `sample_run/characters` has `preview_lineup.png`, the new character beside the whole roster at game size, plus close-ups, flail frames and the splat. Tokens used, all on the local cluster: Orchestrator 345, Character Artist 1,062, Critic 2,307, Technical Writer 504.

## Files

| File | What it is |
|---|---|
| `orchestrator.py` | The Orchestrator, and the file you run |
| `character_artist.py` | The Character Artist |
| `level_architect.py` | The Level Architect: its idea list, recipe and background |
| `layers.py` | Background layers made in code (sky, haze, ground lines), the loop and the previews |
| `objects.py` | Background objects: painted whole on a key color, cut out, shrunk onto the palette, kept in a library |
| `roast_writer.py` | The Roast Writer: the plan, the writing and picking, and the approved lines |
| `wardrobe_stylist.py` | The Wardrobe Stylist: the 4 items as recipes, drawing, the sheet, the idea list, and the approved items |
| `BACKGROUNDS_METHOD.md` | The background method and its rules |
| `gdd.py` | Reads the GDD's Content guide for each maker and the Critic |
| `bridge.py` | The Bridge |
| `critic.py` | The Critic: the GDD check and the picture review |
| `technical_writer.py` | The Technical Writer |
| `foreman.py` | The Foreman |
| `common.py` | The cluster call, cheeks, run state and handoff messages |
| `paperclip_board.py` | The Paperclip board |
| `paperclip_setup.py` | One-time setup of the company and agents in Paperclip |
| `board.py`, `trello_setup.py` | The old Trello board, kept for the record |
| `pixellab.py` | The PixelLab calls and balance |
| `comfy.py` | The ComfyUI call, for background objects |
| `install_character.py` | Puts an approved character into the Unity project, only when I say so |
| `test_sendback.py` | Tests the send-back and stop paths, the GDD check's included |
| `test_gdd.py` | Tests that each maker reads only its own part of the GDD, that its prompts open with it, and that the Critic's problems must quote a real GDD rule |
| `test_roast_writer.py` | Tests the roast line checks, a batch on a stand-in model, and its run |
| `test_wardrobe_stylist.py` | Tests that the 4 items draw the same from recipes, the checks, the ideas, one item on a stand-in model, and its run |
| `roster.json` | The ten current looks, for the concept step |
| `crew.mmd` | The Mermaid diagram |
