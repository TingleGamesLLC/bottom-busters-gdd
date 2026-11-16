# Rumor Mill

Tingle Games · Game Design Document

Multi-Agent AI for Game Development, ELVTR. Class 10 project: an AI virtual Dungeon Master built on AI narrative systems. David, Tingle Games LLC (Austin, TX). November 2026. Engine: Unreal Engine 5.8 (planned). Platform: Windows PC.

## 1. Executive Summary

Rumor Mill is a comedy detective game built on the childhood game Telephone. Every morning someone in town walks up and tells you a rumor about yourself, one the AI made up overnight. You say "Oh yeah? I'll get to the bottom of this," and you go find out who started it. You climb the rumor back from mouth to mouth, catch liars contradicting themselves, and find the source before the rumor gets so big the town guard comes for you. Your reward is a comeuppance: a pie to the face, a fish slap, a giant "Liar's Hat," or the sweetest one, starting a rumor about them.

The Dungeon Master is a crew of AI agents. They write the town, the rumors, the quests, the clues, the lies and the payoffs while you play. The core idea flips this class's lesson. Class 10 teaches how to stop an AI story from drifting and contradicting itself. In Rumor Mill, drift is the game: the AI distorts every rumor on purpose, but a truth ledger and a mutation log track every change, so any rumor can always be traced back to what really happened.

- **Pillar 1. Every rumor is traceable.** The AI distorts on purpose but never forgets. That makes every hunt solvable.
- **Pillar 2. The gap is the joke.** The distance between a boring truth and the wild rumor it turns into is the comedy.
- **Pillar 3. Comeuppance, not cruelty.** Slapstick payoffs, cartoon violence only, never punching down.
- **Pillar 4. Fixed art, endless stories.** All art is made once during development. The AI only recombines it, so no art is generated while anyone plays.

Target players: people who like detective and social-deduction games, comedy games and cozy small-town games, and anyone who has played Telephone.

## 2. Game Mechanics

### 2.1 The core loop (one day)

- **1. Morning: the hook.** A townsperson delivers a rumor about you, in character. The Town Crier's front page shows the headline version.
- **2. Day: the hunt.** Question people, eavesdrop on gossip clusters, look around places for proof and take photos as evidence. Every person you question tells you their version and who they heard it from. Each conversation costs an hour of the day.
- **3. The crack.** Catch someone contradicting themselves, or call out their lie while holding proof you found, and they crack and give up who told them or what really happened. Each person's distortion style is a fingerprint: hear "every day" and you know Gary the Exaggerator passed it on.
- **4. Evening: the confrontation.** Reach the person who started it and pick one of three comeuppances made for that culprit and that rumor.
- **5. Night: the town gossips.** While you sleep, rumors spread one hop at a time and heat rises. Your own actions today become the true events that tomorrow's rumors are spun from.

### 2.2 A game is one week

A game runs seven in-game days, Monday to Sunday. Rumors that aren't solved keep spreading overnight, so an ignored rumor gets worse. You start with a Reputation of 5.

- **Rumor heat.** Every rumor has three heat tiers: Whispers (wanted posters go up), Talk of the Town (a guard starts following you) and Scandal (you're arrested).
- **Busting a rumor:** Reputation +1. The whole chain plays back as a replay.
- **A rumor hits Scandal:** you spend the night in the stocks while townsfolk throw pies. Reputation -2.

### 2.3 Win and loss

| Result | When |
|---|---|
| Win the week | You reach Sunday's Town Fair with Reputation above 0. The fair holds a parade with a float for every rumor you busted. |
| Lose the week | Your Reputation hits 0. The town runs you out of town on a cart, and the end card replays the rumor that ruined you. |
| Win a rumor | You find the true source before it reaches Scandal. |
| Lose a rumor | It reaches Scandal first. |

Score for the week: rumors busted, liars cracked, and the Biggest Gap (the busted rumor that drifted furthest from the truth).

### 2.4 Rules that make rumors work

- **One change per mouth.** Each time a rumor is passed on, exactly one thing about it changes, in the style of the person telling it.
- **Drift between mouths, never inside one mouth.** A rumor can change when it's passed on, but no character can contradict their own earlier story. A planned lie is the one exception, and it's recorded too.
- **Every rumor starts from something true.** Usually something you really did.
- **Belief becomes reality.** If five people believe a rumor, the town acts on it. A statue of the rumor's version of you goes up in the square.
- **Rumors die.** One nobody repeats for three nights fades away.
- **Evidence can't change.** Photos, receipts and sticky notes stay true. Showing one to someone snaps their belief back to the truth.
- **Twists.** Some rumors were started by you (at the tavern last night), by a parrot, or by the victim as a stunt. Some are true, and then you have to shut everyone up instead.

## 3. The Cast

Twelve characters are made once and reused every game. Like a repertory theater troupe, the same actors get new roles each week (last week Gary was the blacksmith; this week he's the mayor), so players come to know them. Each one is built around one way of distorting a rumor. The player builds their own character from a parts kit. Full sheets are in CAST.md.

| Character | Type | What they do to a rumor | Fingerprint |
|---|---|---|---|
| Gary Gusto | The Exaggerator | Bigger, more often, more people | "every day," "hundreds" |
| Toby Crumb | The Salesman | Adds one vivid detail | a cheery voice, never a plug |
| Nana Pearl | The Mishearer | Swaps a word for a sound-alike | sound-alike swaps |
| Dez Halloway | The Conspiracy Theorist | Swaps the motive for a secret plot | "they don't want you to know" |
| Bev Fairweather | The Drama Queen | Adds an emotional detail | "and I nearly DIED" |
| Pip Nettle | The Literal Kid | Takes figures of speech literally | "my mom said" |
| Reggie Fumbleton | The Tavern Regular | Swaps names by accident | calls everyone "Gerald" |
| Mildred Ashby | The Busybody | Merges two rumors | "AND you know what ELSE" |
| Ozzie Fink | The Liar | Swaps the name on purpose | oddly specific alibis |
| Sgt. Brick Hammond | The Shrinker | Shrinks it to avoid paperwork | "possibly a squirrel" |
| Prof. Wendell Dimm | The Forgetful One | Drops a detail | "thingamajig" |
| Captain Squawk | The Parrot | Keeps only the last few words | fragments plus a squawk |

Pip and Captain Squawk are never the targets of slapstick. If they started a rumor, the payoff is gentle. Captain Squawk isn't humanoid, so he doesn't use the shared skeleton; his wing flap and head bob are keyframed by Blender script.

## 4. AI Architecture

### 4.1 How the Class 10 systems are used

| Class 10 system | What it does in Rumor Mill |
|---|---|
| The Facts Ledger (a JSON source of truth, saved to disk after every update) | Becomes two layers: one truth ledger of what really happened, and a belief ledger for each character holding their version and who told them. |
| The Narrative Consistency Agent (stops contradictions) | Gets a new job. It allows exactly one change per hop and records it in a mutation log, and it still blocks any character from contradicting their own story. |
| Remembering player actions (Player Action, Consistency Agent, Update Ledger, Narrative Agents) | The player's actions become the true events that rumors are spun from. Whatever you do today can come back as tomorrow's rumor. |
| Pruning (cut low-relevance branches, score set at generation) | Rumors that nobody repeats fade away, dialogue trees are pruned, and each rumor's relevance score is set when it's born (recency, number of believers, keyword match to the ledger). |

### 4.2 The ledger

```json
{
  "truth":  { "k3": "<a small true event the History Seeder wrote>" },
  "npcs": {
    "gary": {
      "personality": "exaggerator",
      "talks_to": { "mildred": 0.8, "ozzie": 0.6 },
      "beliefs": { "r7": { "version": "<Gary's version of the rumor>", "heard_from": "mildred", "lie": null } },
      "status": [ { "effect": "liars_hat", "days_left": 3 } ]
    }
  },
  "rumors": {
    "r7": { "kernel": "k3", "heat": 2, "believers": 4, "relevance_score": 0.7,
            "chain": [ { "npc": "toby", "version": "...", "mutation": "add_detail" } ] }
  }
}
```

The ledger is saved to disk after every update.

### 4.3 The Dungeon Master loop

Your action becomes a true event in the truth ledger. The night shift spins it into a rumor and spreads it, one logged change per hop. When a rumor about you reaches you, its chain becomes your quest. You climb the chain, crack the liars and pick a comeuppance. The comeuppance (a Liar's Hat, a revenge rumor) becomes a new true event, and the loop starts again. The Director watches pacing over all of it, and the Funny Gate checks every line before you see it.

### 4.4 The agents

LLM agents write words and make comedy choices. Plain code keeps the score: counting, graph paths, thresholds, dice rolls, timers and saving. Every agent returns JSON, every output is checked before it's used, and a failed check sends it back for a rewrite. All LLM agents run on one model built into the game, Qwen3.5-4B (section 6.2).

| Agent | LLM or code | Its job | What it produces (format) |
|---|---|---|---|
| Town Architect | LLM | Lays out a new town from the building kit and names the businesses | town.json: kit piece IDs, business names, rooftop prop IDs |
| Casting Director | LLM | Gives the 12 actors this week's roles, relationships and secrets | cast_roles.json |
| History Seeder | LLM | Writes 5 to 10 small, boring true events to start the week | truth ledger entries (JSON) |
| Social Graph Builder | code | Decides who talks to whom and how much they trust each other, so chains run 3 to 6 hops | graph.json |
| Kernel Picker | code | Picks the true event to spin, weighting the player's own actions highest | kernel ID |
| Twist Dealer | code | Draws a twist from a weighted deck, with no back-to-back repeats | twist tag |
| Spin Agent | LLM | Writes a rumor's first version, who starts it and why | rumor entry (JSON) |
| Router | code | Picks the next listener along the social graph | character ID |
| Mutation Agent | LLM | Makes exactly one change in the teller's style | {new_version, mutation_type, field_changed} |
| Consistency Agent | LLM + code | Enforces one change per hop and no contradicting your own story, records who told whom, writes the mutation log | pass/fail + log entry (JSON) |
| Escalation Agent | LLM | Decides what the town does at each heat tier, using only catalog assets | event (JSON with asset IDs) |
| Messenger | LLM | Delivers the morning hook in character | line + animation tag + face tag (JSON) |
| Chain Walker | code | Turns a rumor's chain into quest steps | quest.json |
| Clue Writer | LLM | Writes what each person says when questioned, with fingerprints planted | clue lines (JSON) |
| Red Herring Agent | LLM | Has 0 to 2 people lie to cover a friend, each lie with a tell | lie entries in belief ledgers (JSON) |
| Solvability Check | code | Proves the source can be reached from the clues, and adds a clue if not | pass / fix |
| NPC Actor | LLM | Plays a character in live conversation from their ledger, personality and secret | line + animation tag + face tag (JSON) |
| Gotcha Judge | LLM | Decides whether the player's "you contradicted yourself" is right | verdict (JSON) |
| Reward Menu Agent | LLM | Writes three comeuppances for this culprit and rumor, using only catalog props and animations | 3 options (JSON) |
| Scene Director | LLM | Shoots the comeuppance from a fixed menu of comedy camera shots | shot list (JSON) |
| Town Crier | LLM | Writes the morning paper's headline, "THE DAILY WHISPER" | headline + subhead (JSON) |
| Gossip Barks | LLM | Writes one-liners people say as you walk by ("Nice hat, liar.") | bark list (JSON) |
| Director | code | Controls pacing: no rumors while you're busy, a push when you're idle, a twist about every third quest | schedule (JSON) |
| Comedy Critic | LLM | Scores lines against the tone guide and sends weak ones back with notes | score + notes (JSON) |
| Joke Ledger, Callback Bank, Pruner | code | Ban repeated jokes, save funny details for callbacks, let dead rumors fade | ledger fields |

### 4.5 What humans write: the bounds

The designer writes only the bounds and the feel. The agents generate everything else.

- **Tone guide.** What funny means here: slapstick, never cruel. Specific, not generic (a named shop, not "a bakery"). Escalation, callbacks, deadpan townsfolk, the rule of three.
- **Content rails.** Cartoon violence only, PG-13, no real people, kids and animals are never slapstick targets.
- **Game numbers.** Heat tiers, how many believers make a rumor real, how many nights a rumor lasts, chain length, twist deck weights.
- **The catalog.** Every character, prop, animation, face, effect and camera shot by ID. Agents can only pick from it.
## 5. Visual Design (Unreal Engine 5.8)

**Art direction.** A tilt-shift diorama with a clay and toon look: the town looks like a miniature on a table, seen from above at an angle. At that size characters read by silhouette and color, so small flaws in AI-made models don't show. One master toon material with a palette makes every asset match.

**Fixed art, endless stories.** All art is made once:
- the 12-actor cast
- a parts kit for townsfolk and the player (body types, heads, hats, accessories)
- a library of 50 to 100 comedy props
- six face textures (talking, shocked, smug, lying, busted, crying)
- a gesture library on one shared skeleton
- a modular building kit

The AI recombines these. Any prop on the hat socket can be the Liar's Hat. The same prop at 20 times its size sits on a shop roof. The player's own model in gold is the statue the town puts up.

**Seeing rumors.**
- Speech bubbles show the changed words struck out and replaced.
- Rumor Vision shows glowing threads between everyone who passed a rumor on.
- A conspiracy corkboard in your house builds itself as you investigate: photos, red string, and a card for each version.

**Comedy on screen.**
- A cartoon fight cloud with fists and a rubber chicken poking out (no fight animations needed).
- Pies and fish slaps with physics.
- A freeze frame with a caption at the big reveal: "Yep. That's Gary."
- The full chain replayed as a camera flight from mouth to mouth.

## 6. Technical Strategy

### 6.1 Art production, one time

Characters are made with the Meshy pipeline already used for Bottom Busters' first 3D character: a front, side and back drawing, then a 3D model, a game-ready version and an auto-rig, about 49 credits each. Blender scripts add parts and attach points. The 12 cast members come to about 585 credits, spent once. Props and kit parts use cheaper Meshy models or free local generation. Gameplay is written in C++.

### 6.2 Runtime AI: Qwen3.5-4B, built into the game

The AI model ships inside the game and runs on the player's own PC. There is no server and no account to sign in to. It costs Tingle Games nothing per player, and the game works offline. The only thing it generates is text and choices. Every agent in section 4.4 runs on this one model, each with its own prompt and JSON schema.

**The model: Qwen3.5-4B.** It has an Apache 2.0 license (official model card), so it can ship inside a commercial game. It's strong at following instructions and tool calling, small enough to share the graphics card with Unreal, and supported by the main fine-tuning tool. It's the only model the game uses.

**Why a small model is enough.** Every agent has one narrow job and returns a few lines of JSON. Plain code does all the counting and scorekeeping. The Funny Gate sends weak lines back for a rewrite, and if a line keeps failing, code builds a plain one from the ledger.

**Expected workload** (estimated from this design; Milestone 1 measures it):

| Phase | Model work per in-game day |
|---|---|
| Night batch | About 40 short calls (spreading, consistency checks, clues, barks, the morning paper), writing about 6,000 tokens |
| Daytime | About 40 conversation turns, each writing about 80 to 130 tokens and reading 2,000 to 3,000 tokens of context |
| Total | About 11,000 tokens written per day, about 80,000 per week |

**How it's set up**
- **Thinking mode off** for every agent. It's on by default and would waste time on short JSON jobs.
- **Text only.** The model also handles images; that part is left out.
- **Small context window, about 8,000 tokens.** Prompts are about 2,000 to 3,000 tokens, and a small window saves memory and speed.
- **Shipped compressed to 4-bit** (GGUF Q4_K_M), estimated at about 2.5 GB.
- **Low-priority thread.** The game's frame rate comes first.

**Settings**

| Agents | Settings | Source |
|---|---|---|
| Creative lines: NPC Actor, Spin, Mutation, barks, Town Crier | temperature 0.7, top_p 0.8, top_k 20, min_p 0, presence penalty 1.5 | Model card, non-thinking preset |
| Judges: Consistency Agent, Gotcha Judge, Comedy Critic scoring | Lower temperature, starting around 0.2 to 0.3 | Tuned in Milestone 1 |

The model card warns that a higher presence penalty can make other languages slip in, so it stays at 1.5 or lower, and the checker rejects any line with non-English characters.

**Reliable JSON**
- **Constrained decoding.** llama.cpp forces every output to match the agent's JSON schema, so the JSON is always valid. The grammar is generated from the schema, never written by hand.
- **Game-level check.** Valid JSON can still name a prop that isn't in the catalog. Every output is checked (IDs exist, one change per hop, no self-contradiction) and retried. After a few failures, code builds a plain line from the ledger.

**Trained in Rumor Mill's voice (development time)**
- **1.** A bigger open model on the development cluster writes thousands of example lines inside the bounds: tone guide, cast sheets, JSON formats.
- **2.** The Comedy Critic and I keep the best ones.
- **3.** Qwen3.5-4B is fine-tuned on them with Unsloth, using bf16 LoRA (about 10 GB of video memory, which fits the development PC's 16 GB card). The 4-bit QLoRA method is skipped because Qwen3.5 loses more quality that way. Starting settings: rank 16, 2 epochs, learning rate 2e-4.
- **4.** The result is merged and compressed to 4-bit for shipping.

This matches published NPC research: a fine-tuned small model with a fixed persona plus a swappable memory, which here are the cast sheets and belief ledgers.

**The Unreal plugin, verified before anything is built on it.** The model runs through llama.cpp inside Unreal. Candidates found on 2026-11-10:

| Plugin | What's known |
|---|---|
| Llama-Unreal | Open source, wraps llama.cpp |
| Volley Studios Local Multimodal LLM | Built for UE 5.8, runs the model on a lower-priority thread |
| Runtime Local LLM | Sold on Fab, updated regularly to keep up with llama.cpp |
| GenAI Llama | Sold on Fab, listed for UE 5.1 to 5.7, pinned to a llama.cpp build from April 2026, so 5.8 support needs checking |

The plugin chosen must pass every check:
- Runs in UE 5.8.
- Its llama.cpp build runs Qwen3.5, which uses a new architecture.
- Supports output constrained to a JSON schema.
- Can turn thinking mode off.
- Loads the model text-only.
- Can be called from C++.
- Its license allows shipping in a commercial game.
- Measured video memory and speed are acceptable while the diorama renders.

**The night batch.** Most of the work runs in the night phase between days: spreading rumors, building quests, writing barks. It starts in the background during the day, so the night scene stays short. Daytime only needs live calls for conversation, and lines appear typewriter-style with babble voices, so the model only has to write faster than people read.

**Minimum PC spec.** Milestone 1 measures the real model work per in-game day. That number, plus measured speed and memory, sets the minimum graphics card. Shipping a local model this way has been done before: the PC game AI People runs fully offline on a local model.

### 6.3 Constraints

- **No art is generated while playing.** Every asset is made once, and agents can only use what's in the catalog. This is the biggest constraint, and it's deliberate: it keeps the cost per player at zero for art.
- **Hallucination.** Every agent output is checked against a JSON schema and the ledger. Failures get rewritten, and after a few failed tries code builds a plain line from the ledger instead.
- **Waiting on the AI.** Live conversation is the only place a player waits on a model. Everything else runs in the night batch.
- **One person.** The 12-actor cast is the art ceiling. Everyone else comes from the parts kit.
- **Not tested yet.** Importing the Meshy characters into Unreal and running Qwen3.5-4B through an Unreal plugin have not been done yet on any project. Both get checked before any work that depends on them.

### 6.4 Scope and milestones

Milestone 1 is the class deliverable. The rest of this document is the full game it grows into.

**Milestone 1: the AI DM in text (class deliverable).** A playable text hunt on the ledgers and five characters, running on Qwen3.5-4B on the player's PC. This proves the Class 10 systems before any art.

- **Six approved hunts.** Each game plays one of six hunts I approved. The rumor, the chain of who told whom, the truth and the proof are fixed, so every hunt is solvable and reads the way I want.
- **What the AI does.** It plays every person live in typed conversation (NPC Actor), reads what the player means (Intent Reader), rules on call-outs (Gotcha Judge), checks every line against what that person already said (Consistency Agent), and writes the morning paper, what the town does as the rumor heats up, and the comeuppance.
- **How you play.** Ask each person who told them until you reach the one who started it. Look around places to find the proof. Call out a liar while holding it, or show it to someone who got it wrong by mistake. Then the whole chain plays back as text.
- **Next.** Having the agents generate new hunts that are as good as the six.

**After Milestone 1:**

- **Milestone 2: the Unreal diorama.** It starts with the plugin check (section 6.2) and training the chosen model in Rumor Mill's voice. Then: one street, the 12 cast members, the catalog, speech bubbles and the conversation screen.
- **Milestone 3: the full week.** Heat tiers, the Reputation meter, comeuppances with the fight cloud and pies, the conspiracy corkboard and the Sunday Town Fair.
- **Later:** a party mode with real players as links in the chain, a Rumor Museum, and legends that carry over between games.

## 7. References

Model facts are from the official model card. Plugin, speed and fine-tuning details are from guides and forum posts as of 2026-11-10, and get confirmed in Milestones 1 and 2.

- Qwen3.5-4B model card: https://huggingface.co/Qwen/Qwen3.5-4B
- Running and fine-tuning Qwen3.5 (Unsloth): https://unsloth.ai/docs/models/qwen3.5
- Fine-tuning Qwen3.5 with Unsloth (guide): https://feedbagel.com/post/guide-to-fine-tuning-qwen35-large-language-models-with-unsloth
- Qwen 3 4B memory and speed: https://willitrunai.com/models/qwen-3-4b
- Constrained decoding: https://www.aidancooper.co.uk/constrained-decoding/
- JSON mode and grammars for local models: https://localaimaster.com/blog/json-mode-grammars-guide
- Fixed-persona small models for NPC dialogue: https://arxiv.org/pdf/2511.10277
- AI People, fully offline with a local model: https://www.goodai.com/ai-people-now-with-local-llm/
- Volley Studios Local Multimodal LLM (UE 5.8): https://forums.unrealengine.com/t/volley-studios-local-multimodal-llm/2746330
- Runtime Local LLM: https://forums.unrealengine.com/t/runtime-local-llm-llama-cpp/2718296
- GenAI Llama: https://forums.unrealengine.com/t/muddy-terrain-games-genai-llama-local-llm-model-in-game-runtime-gpt-oss-llama-cpp-hugging-face/2718525
- Llama-Unreal: https://github.com/getnamo/Llama-Unreal
