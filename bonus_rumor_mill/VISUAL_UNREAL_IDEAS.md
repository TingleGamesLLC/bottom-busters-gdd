# Rumor Mill — Visual Game in Unreal: Ideas (DRAFT v2, 2026-11-10)

Everything here is brainstorm / proposed. Nothing is approved yet.

v2 replaces v1. DAVID (2026-11-10): no Meshy credits spent while the game runs or when a new level is made. All art is made ahead of time.

---

## 1. The rule: make every asset once, the AI only recombines

- All 3D art is made during development, one time, using the pipeline proven in `C:\unrealbbust` (turnaround -> 3D -> remesh -> auto-rig -> Blender scripts for parts and sockets).
- The only thing generated while you play is the story: text, choices, and which existing assets to use. That can run on a local model.
- **The catalog is a bound.** A `catalog.json` lists every character, part, prop, animation, face, effect, sound and camera shot by ID. Agents can only pick from that list. They can't ask for anything that doesn't exist. The fun comes from how they combine it.

---

## 2. Characters

- **A repertory cast.** About 12 hand-approved characters, made once. Like a theater troupe or sitcom ensemble, the same faces play new roles each game. Last game Gary was the baker; this game he's the mayor. Players start to recognize them ("oh no, Gary's back").
- **Each actor is a comedy type.** Each one is built for a distortion personality: the exaggerator, the forgetful one, the liar, the drama queen, the literal kid, the drunk. The look matches the type.
- **A parts kit for everyone else.** 3–4 body types, 10–15 heads, 30+ hats, hair and accessories on the shared skeleton's sockets. That makes hundreds of different townsfolk from one build.
- **Free color swaps.** The master toon material's palette recolors clothes, hair and skin at no cost.
- **Face textures instead of facial rigs.** One set made once (talking, shocked, smug, lying, busted, crying), used on every character. Same trick as BBUST's batsplat dead face.
- **One gesture library.** Made once on the shared skeleton and tagged by personality and emotion: whisper behind a hand, gasp, wide exaggerator sweep, drunk sway, finger-point, faint. The NPC agent outputs a tag like `anim: gasp` and the game plays it.
- **Babble voices.** Each character gets a set of pitched gibberish syllables made once, played under their text. No voice costs during play, and it's funny.

---

## 3. Props: a fixed comedy prop library, reused in every way possible

- **50–100 props made once.** Custard pie, fish, baguette, rubber chicken, goat, wedding arch, pitchforks, churros, wanted poster, giant hat, crown, bucket...
- **The Reward Menu Agent picks from the library.** Its prompt includes the prop list, so it writes rewards it can actually show.
- **Any prop on any socket.** Any prop on the head socket can be the Liar's Hat. No new asset.
- **Scale is a free joke.** A giant prop on a shop roof is the same prop at 20x. The angry mob's churro pitchforks are churros on a stick.
- **Material swaps make new things.** The player mesh in a pose with a gold material = the statue the town puts up of the rumor's version of you. With a shiny inflated look = the parade balloon. A prop in clay = a museum statuette.

---

## 4. Seeing rumors (no assets needed, mostly effects)

- **Speech bubbles show the mutation.** Changed words struck out and replaced.
- **Belief icons.** A small icon set made once (jail bars, goat, heart, skull...). Thought bubbles combine them with a character's portrait to show what an NPC believes.
- **Rumor fog.** The hotter the town gossip, the more whisper particles in the streets.
- **The parade balloon.** At top heat, the player's own mesh with the balloon material floats over town.

---

## 5. The hunt

- **The Red String Board.** A conspiracy corkboard in your house. Each NPC you question gets a photo pinned up (rendered live in the engine), red string runs between who told whom, and each version is a card. It builds itself from the mutation log.
- **Rumor Vision.** Hold a button to see glowing threads between NPCs who passed the rumor, colored by version.
- **Eavesdropping.** NPCs huddle in gossip clusters. Sneak close to listen. If they spot you, they all stop and stare in silence.
- **Photo evidence.** An in-game camera. Photos can't mutate. Show one to an NPC and their belief snaps back to the truth.
- **Evidence you can turn over.** Inspect items from the prop library, like a receipt.
- **The crack.** Catch an NPC in a contradiction: camera push-in, sweat drops, the "busted" face, and they give up who told them.

---

## 6. Comeuppance and comedy

- **The cartoon fight cloud.** One dust-cloud effect with library props popping out (fists, feet, rubber chicken). No fight animations needed.
- **Physics comedy.** Pies with splat decals, fish slaps with ragdolls, dunking in the fountain. Physics makes every payoff come out a little different for free.
- **The dirt layer.** BBUST's poo dirt layer becomes custard, frosting and fountain water.
- **AI cinematographer.** The Scene Director agent picks from a fixed menu of comedy shots (slow push-in, whip pan, dolly zoom on the reveal, freeze frame with a caption). C++ turns the list into a camera sequence.
- **Freeze frame.** Record scratch, freeze, caption: "Yep. That's Gary."
- **Chain replay as a cinematic.** The camera flies from NPC to NPC as each says their version, with the changed words popping up in 3D text.
- **Rumor parade.** At the end of a big quest, a float for each version rolls through the square: library props stacked on a cart, posed cast members on top.

---

## 7. The town

- **A modular building kit, made once.** Walls, roofs, awnings, doors, signs. The Town Architect agent arranges them into a new layout each game. Unreal's procedural (PCG) tools place them.
- **Businesses from parts.** The agent names the business, the name goes on a sign mesh, and a library prop at large scale goes on the roof.
- **Escalation changes the town.** Heat tiers spread wanted posters, bring out guards, then the mob. Lighting shifts from warm to paranoid red.
- **Wanted posters and newspaper.** A poster template plus a live in-engine portrait of the character in a pose plus the agent's text. Same for the Town Crier's front page ("THE DAILY WHISPER").
- **Belief becomes reality.** When enough people believe something, existing assets show up: the gold statue in the square, the wedding arch with the goat.
- **The Rumor Museum.** Town hall keeps a statuette of the wildest version of every rumor you solved, built from cast meshes + props + the clay material.
- **Day and night.** The morning rumor at dawn, the crier's bell, the tavern at night as rumor central.

---

## 8. Proposed art direction

**Tilt-shift diorama with a clay/toon look.** The town looks like a miniature on a table, seen from above at an angle.
- Characters read by silhouette and color at that size, so small flaws in AI models don't show.
- The one master toon material makes every asset match.
- Clay and miniatures are funny on their own and suit small-town gossip.

---

## 9. One-time art list (what we'd make during development)

| Set | Count | How |
|---|---|---|
| Repertory cast | ~12 | Meshy, proven BBUST chain (~49 credits each) |
| Body types for the parts kit | 3–4 | Meshy, same chain |
| Heads, hats, hair, accessories | 40+ | Meshy, or free locally with TRELLIS.2 in ComfyUI (listed in the BBUST plan as the free fallback) |
| Comedy props | 50–100 | Same as above; simple shapes by Blender script |
| Face textures | ~6 expressions | Image tools, made once |
| Gesture clips | ~20 | Meshy animation library / Blender keyframes on the shared skeleton |
| Building kit | ~30 pieces | Blender scripts or free Fab/Megascans content |
| Effects | fog, fight cloud, splats | Unreal Niagara, no credits |
| Belief icons | ~30 | 2D, made once |
| Babble voice sets | ~12 | Recorded or made once |

---

## 10. Things to check before we count on them

- Importing Meshy/Blender models into UE 5.8 (not done yet on BBUST).
- What UE 5.8's MCP plugin can and can't do.
- Rendering NPC portraits live in the engine for the Red String Board and posters.
