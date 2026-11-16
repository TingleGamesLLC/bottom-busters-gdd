# Rumor Mill — Agent Pipelines (DRAFT, 2026-11-10; status updated 2026-11-15)

## Where this stands (2026-11-15)

**The generative pipelines below were built (prototype v2, 2026-11-13), and their content failed.**
- Pipelines 1 to 4 generated the town, the true events, the rumor, the chain, the liars and the quest.
- The hunts were solvable, but David judged six rounds of generated rumors terrible: about 60 rumors on Qwen3.5-4B, and one round also on qwen3:30b-instruct.
- `GAP_ANALYSIS.md` has the full analysis. In short, the hardest jobs (inventing premises, being funny) landed on the weakest part, a 4B model with no examples.

**The new direction: approved hunts, played by the AI.**
- `GAP_ANALYSIS.md` section 6 offered doing for stories what Pillar 4 does for art: make them once, and have the AI play them.
- A strong model (Claude) wrote rumors, David picked, and he approved six hunts: the rumor, the chain, the truth and the proof (`proto\results\rumor_gold_2026-11-13.md`, game copy `proto\rm\hunts.py`).
- The Milestone 1 prototype plays those six (David, 2026-11-15).
- The agents now act on a fixed premise instead of inventing one. `proto\REBUILD_PLAN.md` (v3) has the build details and every complication found.

**Each pipeline in the prototype now:**

| Pipeline | In the prototype |
|---|---|
| 1. Genesis | Replaced. The town is fixed: Main Street with the Lemonade Stand (Toby), Post Office (Mildred), Dock (Gary), Theater (Ozzie) and Coffee Shop (Bev). |
| 2. Rumor Birth | Replaced. The approved hunt is the premise. |
| 3. Rumor Spread | The chain is fixed, word for word, and still logged hop by hop in the mutation log. Heat, the Escalation Agent (LLM), and belief becoming reality all run. Rumors dying off isn't in the prototype, which lasts one day. |
| 4. Quest Builder | Messenger: replaced by David's sentence, word for word. Chain Walker: quest steps for the DM view. Clue Writer: replaced by each person's approved version plus their catchphrase. Red Herring: replaced by the hunt's lie (the starter says they saw it themselves). Solvability Check: replaced, because each hunt was checked and approved by hand. |
| 4b. Proof (new) | The player types "look around" at a place to search it. The proof is fixed per hunt and found only where it is. |
| 5. Interrogation | Runs, and it's now the main job of the AI. The Intent Reader (LLM, new) reads what the player means; it now has a `look_around` intent. The NPC Actor (LLM) plays each person live. The Consistency Agent (LLM) checks every line against what that person already said, and now also tries to send back made-up facts. The Gotcha Judge (LLM) runs on every call-out, but code decides the verdict: a liar cracks only if the player holds the proof. The Dialogue Pruner (code) runs. |
| 6. Payoff | The confession is a fixed line plus David's approved truth, word for word (code). The Reward Menu Agent and Scene Director (LLM) write the comeuppance. |
| 7. Town Life | Barks: each person's approved version plus their catchphrase (code). Town Crier (LLM): the paper, now checked for made-up names. Morning rumor: David's sentence. |
| 8. Director | Code. It gives an idle player an overheard line (LLM-written) about a hop of the chain. |
| 9. Funny Gate | Runs on every line the model writes. |

**Design complications that bear on these pipelines:**
- **Generated inputs poison everything after them.** When the premise is weak, every later agent builds on it, so fixing the premise fixed more than any later agent could.
- **The 4B is a poor judge.** As a fact checker it sends back good lines and lets some made-up ones through. The judges (Consistency, Gotcha, Comedy Critic) can't be fully trusted on quality, so code decides wherever it can, like the proof rule for call-outs.
- **Cast traits leak into content.** Toby's plug got inside the rumor itself; he no longer plugs (David). Forced catchphrases made nonsense, so they're optional now. Mildred's "merge two rumors" invites made-up add-ons.
- **Retelling fixed facts goes wrong.** Asked to retell an approved truth, the model garbled it, so fixed facts are shown word for word instead.
- **Waiting kills the game.** Model calls at night left the player on a still screen for about a minute. Anything that doesn't need the model shouldn't call it.

**The path back to generation (not started).** Have the agents generate new hunts as good as the six, which are the bar. How to scale isn't decided. The GDD's plan (6.2) is to fine-tune the 4B on hunts a strong model writes and David picks.

---

> **Superseded in parts by `RUMOR_MILL_GDD.md` (2026-11-10).** The cast is now a fixed 12-actor repertory (`CAST.md`), so the Casting Director replaces the Cast Generator. All art comes from a fixed catalog. Every agent runs on one built-in model, Qwen3.5-4B. GDD section 4.4 is the current agent list.

Goal: humans write only the bounds and the feel. Everything else (town, people, rumors, quests, jokes, payoffs) is generated in-game and feeds itself, while staying extremely fun and funny.

---

## The two rules that make it work

1. **LLMs write the words. Code keeps the score.** Counting, graph paths, thresholds, dice rolls, timers and saving are all plain code. LLMs only do language and comedic choices, and they always return JSON. That keeps it cheap, reliable, and it never "forgets" (the Class 10 lesson).
2. **Every generated line goes Generate -> Check -> Commit.** Same as the class Consistency Agent: nothing reaches the player until it passes the ledger check and the Funny Gate.

---

## What humans author (the bounds)

A `bounds/` folder. This is the whole design of the game.

| File | What it sets |
|---|---|
| `tone_bible.md` | What funny means here: slapstick, never cruel. Specific, not generic (a named shop, not "a bakery"). Escalation, callbacks, deadpan townsfolk, rule of three. Plus what's banned. |
| `rails.json` | Hard content limits: cartoon violence only (beat-ups are slapstick, nobody really gets hurt), no real people, PG-13. |
| `world_rules.json` | Setting, era, town size (e.g. 12–20 NPCs, 4–6 districts, 8–12 businesses). |
| `mechanics.json` | Mutation types, distortion personalities, belief threshold (5), prune after N ticks, escalation tiers, chain length range (3–6 hops), twist deck weights. |

---

## The master loop

```
player does something
   -> TRUTH LEDGER gets a new kernel (a small true event)
   -> [2 Rumor Birth]   spin the kernel into a rumor
   -> [3 Rumor Spread]  hop, mutate, log, heat up, world reacts
   -> [4 Quest Builder] rumor reaches the player; the chain becomes the quest
   -> [5 Interrogation] player climbs the chain, catches liars
   -> [6 Payoff]        comeuppance + revenge rumor + status effects
   -> those results are NEW kernels in the truth ledger -> loop again

[7 Town Life]  the town gossips on its own the whole time
[8 Director]   the actual DM: watches pacing over everything
[9 Funny Gate] checks every line before the player sees it
```

---

## Pipelines

### 1. Genesis — build the town (once per new game)

| # | Agent | LLM or code | Output |
|---|---|---|---|
| 1 | Town Architect | LLM | Town name, districts, businesses. Each business owned by someone, a little absurd. |
| 2 | Cast Generator | LLM | NPCs: name, job, quirk, distortion personality (from the mechanics list), a secret, a sample voice line. |
| 3 | Social Graph Builder | code | Who talks to whom, with trust levels. Guarantees rumor chains can run 3–6 hops. |
| 4 | History Seeder | LLM | 5–10 small, boring true events (kernels) into the truth ledger. |
| 5 | Funny Gate | LLM critic | Rejects boring NPCs ("Bob, a normal farmer") and samey casts. |
| 6 | Save | code | `state/world.json`, `state/npcs.json`, `state/truth.json`. |

### 2. Rumor Birth — turn a boring truth into a rumor (each in-game day)

| # | Agent | LLM or code | Output |
|---|---|---|---|
| 1 | Kernel Picker | code | Picks a true event. The player's own actions are weighted highest (slide 3). |
| 2 | Twist Dealer | code | Draws from the twist deck: normal, it was you, an animal, the victim did it as a stunt, the rumor is true. No back-to-back repeats. |
| 3 | Spin Agent | LLM | First rumor version + who starts it + why (jealous, bored, misheard, marketing, parrot). |
| 4 | Consistency Agent | LLM + code | Confirms it traces to a real kernel. Logs the origin. |

### 3. Rumor Spread — the telephone game itself (every tick)

| # | Agent | LLM or code | Output |
|---|---|---|---|
| 1 | Router | code | Picks the next listener on the social graph by trust and closeness. |
| 2 | Mutation Agent | LLM | Applies exactly ONE mutation from the list, in the speaker's personality. Returns `{new_version, mutation_type, field_changed}`. |
| 3 | Consistency Agent | LLM + code | Only one field changed? Speaker not contradicting their own belief ledger? `heard_from` recorded? If not, redo. |
| 4 | Heat Meter | code | Rumor heat rises per hop and per believer. |
| 5 | Escalation Agent | LLM | When heat crosses a tier, the world reacts (guards, wanted poster, an angry mob with churro pitchforks). The tiers are bounds; what happens is generated. |
| 6 | Belief -> Reality | code | Believers >= threshold: world_state changes to match. |
| 7 | Pruner | code | Rumors nobody repeats for N ticks die. `relevance_score` set at birth (slide 4). |

### 4. Quest Builder — Rumor Hunt (when a rumor about the player reaches them)

Key idea: **the quest is the mutation log played backwards.** It isn't invented, it's read off real data, so it's always solvable.

| # | Agent | LLM or code | Output |
|---|---|---|---|
| 1 | Messenger Agent | LLM | An NPC delivers the hook in character ("I heard you married a goat"). The hand-written quest starters are its examples. |
| 2 | Chain Walker | code | Turns the logged chain into quest steps, one per hop. |
| 3 | Clue Writer | LLM | What each NPC says when questioned. Plants fingerprints (Gary's "every day"). |
| 4 | Red Herring Agent | LLM | 0–2 NPCs lie to cover a friend. Writes the lie + a tell, stored in their ledger so the lie stays consistent. |
| 5 | Solvability Check | code | Confirms the player can reach the origin from the clues. If not, adds a clue. |

### 5. Interrogation — live conversation

| # | Agent | LLM or code | Output |
|---|---|---|---|
| 1 | NPC Actor | LLM | Plays the NPC from: belief ledger, personality, secret, planned lie (if any), feelings about the player. |
| 2 | Consistency Agent | LLM + code | "Never inside one mouth." Blocks the NPC from contradicting their own ledger, except their planned lie. |
| 3 | Gotcha Judge | LLM | When the player calls out a contradiction, decides if it's legit. If so, the NPC cracks and gives up who told them. |
| 4 | Dialogue Pruner | code | Slide 4 `prune_dialogue_tree`. |

### 6. Payoff — the comeuppance

| # | Agent | LLM or code | Output |
|---|---|---|---|
| 1 | Reward Menu Agent | LLM | 3 revenge options fitted to THIS culprit and THIS rumor (goat rumor -> the culprit has to marry the goat). |
| 2 | Callback Picker | code | Pulls 2–3 funny details from the chain log. |
| 3 | Scene Director | LLM | Writes the comeuppance scene using those callbacks. |
| 4 | Consequences | code | Status effects (Liar's Hat, 3 days), relationship changes (snitch). All written to the ledger. |
| 5 | Revenge Rumor | player + Spin Agent | The player's revenge rumor goes straight into Pipeline 3. Loop closed. |

### 7. Town Life — the world talks without you

| Agent | LLM or code | Output |
|---|---|---|
| Gossip Barks | cheap LLM | One-liners as you walk by, about hot rumors and status effects ("Nice hat, liar."). |
| Town Crier | LLM | The day's headline = the hottest rumor version. |
| Morning Rumor | code + Messenger | Every morning someone tells you a new rumor about yourself. That's the daily quest. |

### 8. The Director — the actual Dungeon Master

Mostly code, with an LLM for flavor. Watches everything and controls pacing.

- Player bored (no active hunt, idle) -> push a rumor about them.
- Player swamped (3+ hunts) -> hold new ones, let some die.
- Chain length grows as the player gets better.
- About every 3 quests gets a twist; keeps the twist deck varied.
- At session end, the Legend Keeper saves the best rumors as folklore for the next game.

### 9. Funny Gate — checks every line before the player sees it

- **Comedy Critic (LLM):** Scores against the tone bible: funny, specific, on-tone, safe. Below the bar -> rewrite with notes.
- **Joke Ledger (code):** Tracks used jokes, props, punchlines and names. Bans repeats (no three goat jokes in a row).
- **Callback Bank (code):** Saves good details for later callbacks, the cheapest reliable laugh.
- **Rails Filter:** Hard content limits.

---

## Comedy built in by structure (not hoping the model is funny)

- **The gap is the joke.** Boring truth vs. wild final rumor. The chain replay shows it.
- **Escalation** is a code-driven heat tier.
- **Callbacks** come out of the log automatically.
- **Specificity** is enforced by the tone bible and the critic.
- **Deadpan contrast:** townsfolk react calmly to absurd things.
- **Rule of three:** the reward menu is always 3 options; escalation has 3 tiers.

---

## New ledger pieces these pipelines need

```json
{
  "truth":   { "k3": "<a small true event the History Seeder wrote>" },
  "npcs": {
    "gary": {
      "personality": "exaggerator",
      "talks_to": { "mira": 0.8, "toby": 0.4 },
      "beliefs": { "r7": { "version": "<Gary's version of the rumor>", "heard_from": "mira", "lie": null } },
      "status": [ { "effect": "liars_hat", "days_left": 3 } ]
    }
  },
  "rumors": {
    "r7": { "kernel": "k3", "chain": [], "heat": 4, "believers": 3, "last_repeated": 12, "relevance_score": 0.7 }
  },
  "quests":      {},
  "joke_ledger": [],
  "callbacks":   [],
  "director":    { "twist_history": [], "active_hunts": 1 }
}
```

All saved to `state/` after every update (slide 2).

---

## Model

One model built into the game runs every agent: Qwen3.5-4B (DAVID, 2026-11-10). The earlier cheap/strong split is dropped. See `MODEL_CHOICE.md` and GDD 6.2.
