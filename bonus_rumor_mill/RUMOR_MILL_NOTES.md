# Rumor Mill — Notes and Plan

Started 2026-11-10. Class assignment: build an AI virtual Dungeon Master using the Class 10 AI narrative systems.

Rumor Mill = an AI DM game built on the childhood game Telephone.

## 0. Status — start here (updated 2026-11-14, end of session)

**The current spec is `RUMOR_MILL_GDD.md` (PDF: `RUMOR_MILL_GDD.pdf`).** Where this notes file and the GDD differ, the GDD wins. David shows the GDD to his instructor the week of 2026-11-16.

**Where things stand (2026-11-15): the prototype plays David's six approved hunts**
- David approved six rumors, then a chain, truth and proof for each (`proto\results\rumor_gold_2026-11-13.md`). The game's copy is `proto\rm\hunts.py`. Each game plays one of the six.
- What changed in the game: the night no longer generates the town, events or rumor; the town is the five people the six need (Lemonade Stand, Post Office, Dock, Theater, Coffee Shop). The morning hook is David's sentence word for word. The model still writes first words, the paper, barks, overheard lines, the escalation, all live conversation and the comeuppance.
- New in the day: type "look around" at a place to find the proof. Liars are caught by calling them out while holding the proof. In hunts 3 and 4 nobody lied, so showing the starter the proof solves it.
- Tested 2026-11-15: all six play to the bust with a stub model; hunts 1, 3, 4, 5 and 7 play to the bust on Qwen3.5-4B; the game screens run headless. `model_test.py` has not been updated for the six.
- Fixes after the first test (David said go, 2026-11-15): when someone cracks, the game shows David's approved truth word for word (the model no longer retells it); the paper is checked for made-up names; a stricter fact check on live lines, first words and barks; catchphrases are optional; Toby never plugs (cast sheet and GDD updated, PDF rebuilt). The 4B is a poor fact checker: it sends back many good lines, so most first words and barks fell back to each person's approved version plus their catchphrase, and it still let some inventions through.
- The night took about a minute with nothing to do (David, 2026-11-15). Now first words and barks are each person's approved version plus their catchphrase, with no model, and the night screen shows a step count. The model writes only the paper, the overheard lines and the town's reactions at night, and the night takes about 9 seconds.
- **Next: David plays it** (`proto\play.cmd`).

**Earlier (2026-11-14): the rumors were the problem, and we built a gold set**
- **The hunt runs, but the rumors are bad.** David judged six rounds of rumor tests terrible. All six ran on Qwen3.5-4B. One also ran on qwen3:30b-instruct on David's cluster, for comparison only; the game still ships one model.
  - Reports: `proto\results\`.
  - Throwaway test scripts: `proto\spikes\`.
  - Why it failed and what to do: `GAP_ANALYSIS.md`.
- **What a rumor must be:** `RUMOR_RULES.md`, still a DRAFT.
- **The ceiling test:** Claude wrote 10 rumors by hand under those rules (`proto\results\rumor_ceiling_2026-11-13.md`). David liked 1 to 3, with 1 the absolute best. So good rumors can exist under the rules, and the 4B can't write them on its own.
- **Now: building a gold set of rumors at David's bar,** in `proto\results\rumor_gold_2026-11-13.md`. Read its header first.
  - Six are kept: numbers 1 to 5 and 7.
  - Nine have been rejected. The file lists them.
- **Waiting on David:** what's wrong with the rejected ones? Claude's guess, which he hasn't answered yet:
  - The kept ones are soft or lonely secrets that involve someone in town: Mildred hands you the letters, you're proposing to Bev, it's the cat at Gary's dock.
  - Most rejected ones are odd hobbies you supposedly do alone: waltzing, opera, ballet, singing to tomatoes, mirror pep talks.
- **Next:** get his answer, write more gold rumors, then "scale from there" (David). How to scale isn't decided yet. The GDD's plan (6.2) is to fine-tune the 4B on rumors a strong model writes and David picks.

**Earlier (2026-11-13)**
- **The rebuild is built.** David approved all of `proto\REBUILD_PLAN.md` ("proceed with the entire rebuild now"). The AI generates every hunt, conversation is typed only, the game uses one model, and the example story is gone from the code and art (`gold.py` deleted). The plan's top section lists the choices made while building.
- **Next: David plays it** (`proto\play.cmd`, or `play dm` for the DM view).
- Gemma is out (David, 2026-11-13). Qwen3.5-4B is the one model, and `model_test.py` runs only Qwen.
- Earlier on 2026-11-13: the spoiler fixes, the example story removed from every document, the GDD PDF rebuilt, and the old model test results deleted.

**Decisions (DAVID, 2026-11-13, during the rumor work)**
- **Good example rumors are OK to build.** Claude asked whether training the 4B on hand-picked rumors breaks the no-examples rule. David's words: "no i just need more good examples like that. are you good to build 7 more to make 10 total? then we can scale from there?"

**Decisions (DAVID, 2026-11-13)**
- The AI generates everything in a hunt: town, cast roles, true events, the chain, the liars, the twist and the evidence. Nothing in the story is hand-written. There's no fallback story and no story examples in prompts.
- Conversation is typed only, with no buttons. A new Intent Reader agent reads what the player means.
- No spoilers anywhere:
  - The player sees only what they witness.
  - Nobody is labeled ahead of time.
  - No mechanic hands over the answer. For example, evidence never cracks anyone.
- The game ships with one model, Qwen3.5-4B. Players never choose a model or see its name.
- The five Milestone 1 actors keep their type and fingerprint. Their jobs, places, relationships and secrets are generated each game.
- The player twists ("you started it," "it's true") wait until the player's real actions go into the ledger. Milestone 1 uses no twist or the victim's stunt.

**Decisions (DAVID, 2026-11-10)**
- Rumor Hunt quest (someone tells you a rumor about yourself, and you trace it back to whoever started it) is David's idea and the core loop.
- Everything in a hunt is generated by the agents. Any example story in these notes was an example only, never a spec (DAVID, 2026-11-13).
- No Meshy credits spent while the game runs or when a new level is made. All art is made once during development; the AI only recombines it from a fixed catalog.
- Visual game in Unreal (UE 5.8).
- The GDD says Tingle Games at the top (David, Tingle Games LLC).
- The AI model ships inside the game and runs on the player's own PC. No server, no "bring your own key." David's cluster is for development only; nobody else can use it.
- Model: Qwen3.5-4B, backup Gemma 4 E4B. Plan approved in full ("i like everything above and all aspects"), including verifying the Unreal plugins. Details: `MODEL_CHOICE.md` and GDD 6.2.
- Milestone 1 (the AI DM in text, plus the model test) is the class deliverable. The GDD still covers the full game.

**Files**
| File | What it is |
|---|---|
| `RUMOR_MILL_GDD.md` / `.pdf` | The GDD for the instructor. Current spec. |
| `CAST.md` | The 12-actor repertory cast, full sheets |
| `MODEL_CHOICE.md` | Model pick, settings, fine-tuning, plugin research, sources |
| `AGENT_PIPELINES.md` | Early pipeline brainstorm (GDD 4.4 is the current agent list) |
| `VISUAL_UNREAL_IDEAS.md` | Visual ideas, v2 (pregenerated art only) |
| `RUMOR_RULES.md` | What a rumor is and how one's built. DRAFT. |
| `GAP_ANALYSIS.md` | Why the rumor tests failed, and what to do about it |
| `proto\results\rumor_gold_2026-11-13.md` | The gold rumors David kept, and the ones he rejected |
| `slides\` | Class 10 slides (copies of `C:\gdd\class10*.png`) |
| `proto\` | Milestone 1 prototype, rebuilt 2026-11-13: the AI DM in text, a Python terminal game with pixel art, through llama.cpp. Read `proto\README.md`. Play with `proto\play.cmd`. Model test: `proto\model_test.py`. Plan: `proto\REBUILD_PLAN.md`. |

**Still open**
- David's answer on why the rejected gold rumors miss.
- How to scale the gold set.
- `RUMOR_RULES.md` is a DRAFT. Change it only when David says go. The ceiling test turned up three things it doesn't cover yet:
  - Anyone named in the story, or anyone who knows the truth, can't come later in the chain.
  - Ozzie's later name swap didn't work in any rumor. That rule needs rethinking.
  - The tone guide (`TONE_GUIDE` in `proto\rm\cast.py`) goes into every prompt. It asks for slapstick and absurd, which works against "believable" (`GAP_ANALYSIS.md` 2.2).
- What the missed Class 10 loop slide showed (ask the instructor or a classmate).
- David plays the rebuilt game.

---

## 1. What Class 10 taught (slides in `slides\`)

**class10.png — Tracking Plot Threads**
- Biggest risk of AI-written stories is hallucination: characters forget facts or contradict earlier events.
- Fix: a Narrative Consistency Agent whose only job is tracking plot threads and stopping contradictions before the player sees them.

**class10a.png — The "Facts" Ledger**
- A JSON object is the master ledger, the single source of truth.
- Every narrative agent reads it before generating dialogue.
- Persist to disk after every update: `json.dump(ledger, open('state/facts.json', 'w'), indent=2)`. A ledger not written to disk is lost on restart.
- Works for any genre, only the keys change. Their example even has `"rumor_spread": true`.

**class10b.png — Remembering Player Actions**
- Loop: Player Action -> Consistency Agent -> Update JSON Ledger -> Narrative Agents.
- The Consistency Agent updates the ledger after every player message, so the world never forgets crimes or alliances.
- This feedback loop is what separates a narrative engine from a chatbot.

**class10c.png — The Importance of Pruning**
- Endless dialogue overflows the context window. A pruning script cuts old, low-value branches.
- `prune_dialogue_tree(tree, max_depth=3, max_branches=4)` keeps the top branches by `relevance_score`.
- `relevance_score` is set when a branch is generated (recency + keyword match against the ledger), not when it's pruned.

**Missing slide — the full loop (NOT SEEN, reconstruction only, confirm with instructor or a classmate)**
1. Player acts.
2. Consistency Agent pulls the new facts out of the action.
3. Ledger updated and saved to disk.
4. Narrative Agents read the ledger and write a response.
5. Consistency Agent checks that response against the ledger; rewrites it if it contradicts anything.
6. Old branches pruned.
7. Player sees the response and acts again. Each turn's output feeds the next turn.

---

## 2. The big idea: Rumor Mill flips the lesson

The class teaches you to stop drift. In Rumor Mill, drift IS the game, but every bit of it is tracked.

- **Two kinds of ledgers.** One TRUTH ledger (what really happened). One BELIEF ledger per NPC (their version).
- **The Consistency Agent's new job.** It stops preventing every change and starts recording each one. Every time a rumor passes from one NPC to the next, it logs exactly what changed (the mutation log). The AI distorts on purpose, but nothing is ever lost, and any rumor can be traced back to the truth.
- **The rule:** "Drift is allowed between mouths, never inside one mouth." A rumor can change when it's passed on, but Baker Tom can't contradict his own earlier story. That's the slide 1 problem, solved inside the game.

```json
"rumors": { "r1": { "truth": "Kael burned the market", "chain": [
  {"npc": "Mira",       "version": "Kael burned the market",          "changed": null},
  {"npc": "Baker Tom",  "version": "A guild thief burned the market", "changed": "name -> vague"},
  {"npc": "Sgt. Harlo", "version": "Lord Voss paid to burn it",       "changed": "blame shifted"}]}}
```

Pitch line for the instructor: the truth ledger + mutation log shows we understood the consistency lesson and then turned it into the core mechanic.

---

## 3. Brainstorm — core mechanics

- **Personality decides the distortion.** Exaggerators make it bigger, forgetful NPCs drop details, drama lovers add details, liars change it on purpose, kids take everything literally, drunks swap names.
- **Fixed list of mutation types:** exaggerate, shrink, swap the name, swap the place, swap the motive, drop a detail, add a detail, merge with another rumor. Each one logged, so it's trackable and gradeable.
- **Rumor DNA.** Each rumor has who / what / where / why / how big. Each hop changes one of those. Show the rumor's family tree.
- **Belief becomes reality.** Once enough NPCs believe something (say 5), the world changes to match. If the guards believe Voss did it, they arrest Voss.
- **Rumors collide.** Two rumors in the same tavern merge into a third.
- **Pruning becomes forgetting.** A rumor nobody repeats for N turns dies. Popular rumors score higher. Ties to slide 4.
- **Trust on social links.** NPCs believe a rumor based on how much they trust the teller.
- **Social graph.** Rumors travel between people who actually talk to each other; slower across districts.
- **Evidence can't change.** A letter or wax seal stays the same no matter who carries it. NPCs who see it snap back to the truth.
- **Truth is slow.** A player can launch a correction, but it spreads slower than the lie.

## 4. Brainstorm — player roles

- **Source:** Start a rumor and try to make it reach the king saying exactly what you want after 5 mouths.
- **Detective:** Hear the final garbled version and work back up the chain to the truth. The truth ledger is the answer key.
- **Link in the chain:** You hear it and decide what to pass on; your edits get logged like anyone's.
- **Victim:** Your real actions from the ledger (`crimes_committed`) turn into gossip about you and get distorted. "Stole the crown jewels" becomes "killed the king." Your reputation is made of rumors.
- **Unreliable DM:** The narrator telling you the story is one of the links in the chain too.

## 5. Brainstorm — multiplayer and party

- **Real telephone:** Real players take turns, the AI DM distorts between each one, final reveal shows the whole chain.
- **Hidden saboteur:** One player is secretly the liar. The DM knows who from the ledger.
- **Slow online play:** A rumor travels through real players over several days.
- **Voice mode:** Players speak the rumor, speech-to-text mishears it ("Lord Voss" -> "Lord Moss"), different text-to-speech voice per NPC.
- **Translation chain:** The rumor passes through languages and comes back changed.

## 6. Brainstorm — agent roles (multi-agent DM)

- **Mutation Agent:** Only distorts, and only by the rules. Keeps changes funny, not random noise.
- **Chronicler:** The Consistency Agent as an in-world character who knows the truth.
- **Judge Agent:** Decides whether a changed rumor is still the same rumor or a new one with its own ID.
- **Town Crier:** Announces today's headline version.

## 7. Brainstorm — settings (only the ledger keys change)

- Fantasy village
- Middle school hallway
- Cold War spy chain with intercepted messages
- Viral social media, shares instead of mouths
- Haunted town: the ghost gets stronger the more people believe in it
- Pirate map: the directions change as they're retold, and the treasure actually moves

## 8. Brainstorm — payoff and scoring

- **Chain replay:** Every version side by side with the changes highlighted. The big laugh at the end of Telephone.
- **Truth meter:** How far each version has drifted from the truth.
- **Two modes:** Accuracy (stay close to truth) and Chaos (how wild it gets).
- **Legends that carry over:** Last game's rumors become next game's town folklore.
- **Achievements:** "Reached the king unchanged." "Started a war over a sandwich."

---

## 9. NEW: Rumor Hunt — "Who said that?!" (David's idea, 2026-11-10)

**The hook:** An NPC walks up and tells you a rumor about yourself. You: "Oh yeah? I'll get to the bottom of this." You trace the rumor back to whoever started it. Reward: you get to beat them up, or something funny.

**How it runs on the Class 10 systems**
- Every NPC's belief ledger stores who they heard it from (`heard_from`). Questioning someone points you one step up the chain.
- Versions get closer to the original as you climb, so you can tell you're going the right way.
- **Mutation styles are fingerprints.** The exaggerator always adds "every day." Hear "every day" and you know Gary the Exaggerator touched it.
- **Kernel of truth.** Every rumor about you starts from something real in the truth ledger.
- NPCs can lie to cover for a friend, but the Consistency Agent keeps each NPC's lies consistent with their own belief ledger, so you can catch them contradicting themselves.

**Funny rewards**
- Slap fight with a fish, a baguette, or a rubber chicken.
- Custard pie duel in the town square.
- Public apology in the square, written by the AI in the NPC's voice, with maximum groveling.
- They wear the Liar's Hat for 3 days, and every NPC comments on it.
- Their face goes on the town gossip board: "WANTED FOR LYING."
- Noogie / wedgie / getting dunked in the fountain.
- They become your snitch and feed you future rumors.
- **Best one for the system:** your reward is getting to start a rumor about THEM, and you watch it spread through the mill. That closes the loop.

**Funny twists on who started it**
- It was you, drunk at the tavern last night. Reward: you beat yourself up.
- A parrot that repeats everything. Or the mayor's dog. Or a 6-year-old.
- The victim, as a marketing stunt.
- The rumor is TRUE. You really did it earlier (it's in the ledger). Now flip it: chase downstream and shut everyone up.
- The rumor mutated so far it's now about someone else, and they're hunting YOU.

**Pressure and escalation**
- **Escalation timer:** The longer you take, the worse the rumor gets. Guards show up and a wanted poster goes up.
- **Counter-rumor:** The rumor-starter fights back by spreading "you've been harassing innocent people."
- **Word on the street:** Every morning someone tells you a new rumor about yourself. That's your daily quest.
- **Reputation made of fiction:** You get famous for things you never did. Some of it helps (people fear the version of you in the rumor).

**More rumors about you (quest starters)**
- "I heard you're secretly three kids in a trench coat."
- "I heard you married a goat."
- "I heard you got banned from the bakery for licking the bread."
- "I heard you're scared of ducks."
- "I heard you know why the mayor's mustache is fake."

---

## 10. Build plan (early draft — superseded by GDD section 6.4)

Smallest version that shows the full Class 10 loop working:

1. Truth ledger + belief ledgers in JSON, saved to `state/` after every update.
2. 5 NPCs, each with a name, a distortion personality, and who they talk to.
3. Mutation Agent: passes a rumor one hop and changes one field by that NPC's personality.
4. Consistency Agent: logs every change in the mutation log, and blocks an NPC from contradicting their own earlier story.
5. One Rumor Hunt quest, generated by the agents: question NPCs, climb the chain, find the starter, pick a funny reward.
6. Chain replay screen at the end.
7. Pruning: rumors nobody repeats for N turns die off; `relevance_score` set at generation time.

## 11. Agent pipelines (fully generative design)

See `AGENT_PIPELINES.md`. Humans write only the bounds and the feel; the game generates and feeds everything else.

## 12. Visual game in Unreal

See `VISUAL_UNREAL_IDEAS.md`. Builds on the Meshy + Blender pipeline proven in `C:\unrealbbust`.

## 13. Cast and GDD

- `CAST.md` — the 12-actor repertory cast, full sheets.
- `RUMOR_MILL_GDD.md` / `RUMOR_MILL_GDD.pdf` — the GDD for the instructor (2026-11-10).

## 14. Model choice

See `MODEL_CHOICE.md`: Qwen3.5-4B built into the game, Gemma 4 E4B as backup. GDD 6.2 has the full plan.

## Open questions

- What did the missed loop slide actually show? (Ask instructor or a classmate.)
- ~~What does the instructor want turned in?~~ Answered: Milestone 1 is the deliverable (DAVID, 2026-11-10).
- ~~Text-only, or a visual game?~~ Answered: visual, in Unreal; Milestone 1 is the text version of the AI DM.
