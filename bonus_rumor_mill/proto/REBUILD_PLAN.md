# Rumor Mill prototype: rebuild plan (v3, 2026-11-15)

## v3 (2026-11-15): built around David's six approved hunts

**Where it stands.** The prototype no longer generates hunts. Each game plays one of six hunts David approved, in `rm/hunts.py`, never the same one twice in a row. The rumor, each person's version up the chain, the truth and the proof are fixed, word for word as approved. The model plays every person live in typed conversation and writes the morning paper, the overheard lines, what the town does as the rumor heats up, and the comeuppance. For the prototype, this replaces the 11-13 rule that the AI generates every hunt (David, 2026-11-15).

### How we got here

1. **v2 was built on 11-13** (below): the AI generated every hunt, and you played by typing.
2. **The generated rumors failed.** David judged six rounds of rumor tests terrible: about 60 rumors on Qwen3.5-4B, and one round also on the cluster's qwen3:30b-instruct. Every fix solved what it targeted, and the content stayed bad. `GAP_ANALYSIS.md` has the full analysis.
3. **The ceiling test.** Claude wrote 10 rumors by hand under `RUMOR_RULES.md`. David liked 3, so good rumors can exist under the rules. The 4B can't write them on its own.
4. **The gold rounds.** Claude wrote more. David kept 3 more and rejected 9.
5. **The six.** David approved the six as plain one-line rumors. Then he approved a new truth for 7, and a chain, truth and proof for each hunt (`proto\results\rumor_gold_2026-11-13.md`).
6. **David's call:** build the game around these six for now, as the prototype.

### Design complications found along the way

**The rumors**
- **The 4B can't write rumors at David's bar.** It lands between funny-wild and believable, and it fixates on the oddest detail it's given.
- **The tone guide fights the rumor rules.** It asks for slapstick and absurd; `RUMOR_RULES.md` asks for believable and petty (`GAP_ANALYSIS.md` 2.2).
- **The chain has its own rules.** Anyone named in the story, or anyone who knows the truth, can't come later in the chain, because they'd know it's false. That's why Bev isn't in hunt 5's chain.
- **A chain can't run through people you can't question.** Hunt 7's approved truth had the dock crew asking. The chain would dead-end there, so Mildred asks instead (approved).
- **Ozzie's later name swap** never worked in any rumor. Ozzie only starts rumors.

**The cast traits**
- **Voice leaks into content.** Toby's plug ended up inside the rumor itself ("Sour Sips, two for a nickel. Tell your friends!"). David rejected it, so Toby no longer plugs anything (cast sheet and GDD updated).
- **Forced catchphrases made nonsense.** Every first line had to include the person's catchphrase, which gave lines like "the size of a wagon is calling you Mister Snuggle-Whiskers." Catchphrases are now optional.
- **Mildred's "AND you know what ELSE" invites inventions.** Her trait is merging two rumors, and with no second rumor the model makes one up ("you feed him sardines from a tin can").

**The model at play time**
- **It makes up facts in live lines,** like "the ink is still wet on your own stationery." Telling it not to helps only a little.
- **It's a poor fact checker.** A stricter check sends back good lines (Bev's "I can't even! You're talking baby-talk to the dock cat!") and still lets some inventions through.
- **It garbled confessions** when asked to retell the truth ("Bev asked me to protect him").
- **The paper invented names** ("Barnaby's Ear Sent Abroad").

**Pacing**
- **The night took about a minute** with nothing on screen to do (David: "not a good game at all").

### What changed in v3

- **The night (`rm/night.py`)** sets up the chosen hunt instead of generating one:
  - **Town:** Main Street with the Lemonade Stand (Toby), Post Office (Mildred), Dock (Gary), Theater (Ozzie) and Coffee Shop (Bev).
  - **Chain and beliefs:** the chain is word for word as approved. Code fills in where and when each hop happened, what each starter says when asked who told them, and the secret that each real culprit outside the chain keeps.
  - **Morning hook:** the last person in the chain says David's sentence word for word.
  - **First words and barks:** each person's approved version plus their catchphrase, with no model.
  - **The model at night** writes only the paper, the overheard lines and the town's reactions. The night takes about 9 seconds, and the screen shows a step count.
- **Looking around (new).** Type "look around" at a place to search it. The proof is at one place (two in hunt 1). The Intent Reader has a new `look_around` intent.
- **Solving a hunt:**
  - **Hunts 1, 2, 5 and 7:** the starter lies ("I saw it myself"). Call them out while holding the proof and they crack. Showing it to them doesn't crack them. The Gotcha Judge still runs on every call-out, so the timing never gives a liar away, but code decides the verdict by whether you hold the proof.
  - **Hunts 3 and 4:** the starter got it wrong by mistake. Show them the proof and it's solved.
- **Confessions.** The starter says one fixed line ("Fine! You got me. Here's what really happened."), and the game shows David's approved truth word for word. The model doesn't retell it.
- **Checks:**
  - **The paper** is checked for made-up names and for saying "the player."
  - **Live lines** go through a stricter fact check, which still makes mistakes both ways.
  - **Toby's lines** are rejected if they plug anything.
- **Not running in the prototype:** the Casting Director, Town Architect, History Seeder, Kernel Picker, Twist Dealer, Social Graph Builder, Spin Agent, Router, Mutation Agent, the night Consistency Agent, Red Herring Agent, Evidence writer, Clue Writer, Messenger and Solvability Check. Their code is still in `rm/agents.py` for when hunts are generated again.

### What stays from v2

- One model, Qwen3.5-4B, through llama.cpp, with schema-forced JSON.
- The ledger, saved after every update, and pruning.
- Typed conversation only, the Intent Reader, the NPC Actor, the Gotcha Judge and the daytime Consistency Agent.
- Heat, the Director, the notebook, the comeuppance, the replay and the DM view.
- The spoiler rules.

### Tested (2026-11-15)

- All six hunts play through to the bust with a stand-in model.
- Hunts 1, 3, 5 and 7 play through to the bust on Qwen3.5-4B. Hunt 4 also did, before the later fixes.
- The game screens run headless, including the night screen on the real model.
- David's first launch sat on the night screen for about a minute. That's what led to cutting the night down.

### Open

- **Live lines** still make things up at times.
- **Plain repeated lines.** Most first words and barks are the same approved line with a catchphrase, which is plain and repeats.
- **`model_test.py`** hasn't been updated for the six hunts, so it won't run.
- **`RUMOR_RULES.md`** is still a draft.
- **Generating hunts as good as the six.** How to scale isn't decided. The GDD's plan (6.2) is to fine-tune the 4B on hunts a strong model writes and David picks.

---

## v2 (2026-11-13), kept for history

**Built 2026-11-13.** David approved the whole plan ("proceed with the entire rebuild now"), so all six parts were built in one go instead of stopping at each checkpoint. The checkpoints that are David's (reading premises, playing it) are still his. Gemma is out (David, 2026-11-13): Qwen3.5-4B is the one model, and the model test runs only Qwen.

**Choices made while building, where the plan left room:**
- The source always lies about where they heard it, so they count as one of the 0 to 2 liars. Code adds at most one more, someone covering for a friend.
- A cover-up liar's tell is the place where they really heard it. If that place is their own building, the tell is the name of the friend who dropped by.
- Liars let their tell slip once per visit, when the player presses them (asks where they were, shows evidence, asks twice who told them, or calls them out).
- Bystanders heard the rumor in the street that morning. The paper is written later in the night (step 15), after their first words (step 13).
- The Comedy Critic sends a line back if it scores 1, or 2 and makes no sense. If every try passes the other checks but not the Critic, the best-scoring line is kept. Code builds a plain line only when a line fails its other checks three times.
- If the Intent Reader calls an accusation something else (for example, showing evidence), code treats it as a call-out.
- The Social Graph Builder runs before the Kernel Picker, so the Kernel Picker only picks an event that a chain of 3 to 5 people can carry. The night log lists them in the plan's order.
- Heat comes from believers and spread during the day, and hits Scandal at 6 PM.

v2 added David's answers from 2026-11-13.

## Why a rebuild

The current prototype is a script. `rm/gold.py` fixes:
- the true event
- the chain
- each change
- the liar
- the cracks
- the endings

The model only rewords them. Conversation runs on four buttons, so the player clicks through instead of figuring anything out.

The GDD says the opposite: "The designer writes only the bounds and the feel. The agents generate everything else" (section 4.5). The NPC Actor plays each person "in live conversation" (section 4.4).

The rebuild makes two things true:

1. **The AI generates everything, every game.** That means:
   - the town
   - the cast's jobs, relationships and secrets
   - the true events
   - who starts the rumor, and why
   - who passes it to whom, and what each person changes
   - who lies, and why
   - the twist
   - the evidence you start with

   Nothing is hand-written into the story.
2. **You figure it out by typing.** There are no conversation buttons. You type whatever you want to whoever you want, and they answer from what they know, believe and are hiding.

## What stays

- llama.cpp b12327 on this PC, and schema-forced JSON.
- The generate, check and rewrite loop in `rm/agents.py`.
- The ledger, saved after every update, and pruning.
- The pixel art: five portraits with six faces, the town, the title and the icons.
- The screens: title, night, paper, town, talk, payoff, replay and the DM view.
- The spoiler rules from 2026-11-13, listed at the end.

## What goes

- **The example story, completely.** It was only ever an example from David. That means:
  - `rm/gold.py` is deleted
  - there are no story examples in any prompt
  - there is no fallback premise
  - no hand-written lines are used anywhere
  - every trace of it leaves the code and art:
    - the food on the title screen, on Toby's portrait, on the shop roof and on the wanted poster
    - its icons and props in the catalog
    - its place names
    - its words in prompts, checks and `model_test.py`
- The four conversation buttons: "Who told you?", "You contradicted yourself!", "Show the receipt" and "Leave".
- The model switch: `--model`, `play gemma`, and the model name on the title screen and in the town's status bar.
- Offline mode (`--offline`, `play offline`). It played the hand-written script, which is gone.
- The hard-coded per-person rules in `rm/world.py`: who names whom, and the special crack instructions for each liar.
- The fake night steps: the History Seeder, Kernel Picker, Twist Dealer and Chain Walker lines that were never real.

## One model

The game ships with one model, Qwen3.5-4B. Players never choose a model and never see a model name.

If the model can't load, the game says so and doesn't start. There is no scripted version to fall back to.

## Part 1. The night shift generates the premise

The steps run in this order. LLM agents write, and plain code checks, counts and routes. Every result goes into the truth ledger and the belief ledgers, saved after each step. The player sees only the sleeping town. The DM view (`--dm`) shows all of it.

1. **Casting Director (LLM).** Each of the five actors keeps their type: how they bend a rumor, and their fingerprint. Everything else is generated each game:
   - their job and workplace
   - who they're friends with, who they owe, and who they can't stand
   - one secret each
2. **Town Architect (LLM).** It names the five places on the street, using the building kit that's already drawn: a shop with a rooftop prop, a house with a fence, a dock shed, a theater and a tavern. It picks each shop's rooftop prop from the catalog and says who works or lives where. The town drawing reads this file.
3. **History Seeder (LLM).** It writes 5 to 10 small, boring true events from the last two days. At least 3 involve you: small, ordinary things that give the rumor something true to grow from. You're never made guilty of anything. Each event is stored as story fields (who, what, how much, where, when), so the Consistency Agent can track every change. Code checks that every person and place exists and that nothing is a real crime.
4. **Kernel Picker (code).** It picks the event to spin, weighting events that involve you highest.
5. **Twist Dealer (code).** For Milestone 1 it draws from two cards: no twist, or the victim started it as a stunt. The last twist is saved between games, so there are no back-to-back repeats. The GDD's other twists ("you started it, at the tavern last night" and "it's true") depend on things the player really did. They join the deck once the player's real actions go into the ledger, in a later milestone.
6. **Social Graph Builder (code).** It turns the relationships into who talks to whom and how much they trust each other, so a chain of 3 to 5 hops exists. With five actors, 5 is the cap.
7. **Spin Agent (LLM).** It decides who starts the rumor, why, and its first version, following the twist.
8. **Router (code).** It picks each next listener along the graph, and when and where each hop happened, based on workplaces and a simple timeline. The chain ends with the person who tells you in the morning. Ozzie's one change is always swapping a name. If he's a hop, the rumor was about someone else until he made it about you. If he isn't a hop, he can still be a liar or a bystander.
9. **Mutation Agent (LLM) and Consistency Agent (LLM plus code).** Exactly one change per hop, in the teller's style, logged. These are built and now run on generated chains. Mildred merges in one of the other true events.
10. **Red Herring Agent (LLM).** Code picks 0 to 2 people with a reason to lie: covering for a friend from the relationships, or the source covering for themselves. The LLM writes each lie, alibi and tell. Code checks that the tell clashes with something a witness will say or with your evidence, so every lie can be caught.
11. **Evidence (part of the Kernel step).** This is what you're holding that proves the true event: a receipt, a ticket stub or a note. The type comes from a catalog, and the LLM writes its text from the kernel.
12. **Chain Walker (code).** It turns the chain into quest steps for the DM view and the Solvability Check.
13. **Clue Writer (LLM).** It writes each person's first words, with their fingerprint.
14. **Solvability Check (code, done for real).** It walks the hunt the way a player would:
    - Each honest person names who told them when asked.
    - Each liar has a catchable tell.
    - The source has a catchable contradiction.

    If a step can't be reached, it adds a clue (someone else saw that hop happen) and checks again. If it still fails, the whole premise is thrown out and generated again. After a set number of failed premises, the night stops with an error. That failure rate is measured in the model test.
15. **Morning and town lines:**
    - **Messenger (LLM):** the morning hook.
    - **Town Crier (LLM):** the paper.
    - **Gossip Barks (LLM):** one-liners each person says as you pass in town, written from what they believe.
    - **Escalation Agent (LLM):** what the town does at each heat tier, using only things already drawn: wanted posters, the guard and the stocks.

## Part 2. The day: typed conversation only

- **The talk screen is a text box.** Esc leaves. Each conversation costs an hour, and you get a set number of lines per visit.
- **Intent Reader (LLM judge).** This agent is new, not in the GDD; David approved it on 2026-11-13. It reads each line you type and returns what you're doing:
  - asking who told them
  - asking about a time, place or person
  - showing evidence, and which item
  - calling out a contradiction
  - just talking

  Plain code decides what that does.
- **What code does with each:**
  - **Asking:** the person answers from their belief ledger. Honest people tell what they know, liars give their lie, and the source deflects. Nobody is forced to answer. You have to ask the right thing.
  - **Evidence:** it only works if you have the item and actually show or describe it. It snaps an honest person's belief back to the truth. It never cracks anyone.
  - **Calling out:** the Gotcha Judge rules on it, for everyone. A failed call-out gets the same answer no matter who it was aimed at. A caught liar cracks and tells the truth.
  - **Talking:** they answer in character.
- **The NPC Actor stays grounded.** Each person's prompt holds only what they know:
  - their belief, who told them, and when and where
  - their relationships
  - their secret or lie
  - what they've already said to you
  - the morning paper

  Code rejects any line that names a person, place or event they don't know about. The Consistency Agent checks each line against what they've already said. Liars can't confess until they're cracked, and telltale faces and moves stay locked until then.
- **Win:** the source cracks before 6 PM. **Lose:** the rumor hits Scandal at 6 PM.
- **The notebook** stays word for word. It adds "In your pocket," which lists your evidence.

## Part 3. The Funny Gate

- **Comedy Critic (LLM):** scores every line you'll see against the tone guide and sends weak or nonsensical lines back with notes.
- **Joke Ledger (code):** bans repeated jokes.
- **Callback Bank (code):** saves funny details from the chain for the paper, the barks and the comeuppances.
- **Rails filter (code plus the Critic):** enforces the content rails.
- **Prompts:** no story examples. Prompts are built from the tone guide, the cast sheets and the JSON format only. A 4B model has nothing to copy, so the checks and the Critic carry more of the quality.

## Part 4. The rest of the day's systems

- Heat comes from the rumor spreading and how many people believe it, not just the clock.
- Reputation starts at 5, goes up 1 for a bust and down 2 for Scandal (GDD 2.2).
- Belief becomes reality: at the believer threshold, the town acts, using the Escalation Agent and the catalog.
- **Director (code):** pacing. If you go a few hours without progress, it gives you a push: a bark or an overheard line with a clue.
- Your actions become true events. What you did today (who you called out, what you showed, your comeuppance) is saved for the next game's History Seeder and Kernel Picker. This is also what the player twists need later.
- The model runs on a low-priority thread.

## Part 5. When a check fails

- **A premise that fails:** it's generated again, as described in Part 1, step 14. No canned story is ever used.
- **A line that fails its checks 3 times:** a plain line built by code from the ledger, in the person's voice ("Gary told me, at the tavern on Wednesday."). It's never a fixed script line.

## Part 6. The model test, redone on the real job

This measures the game's one model, Qwen3.5-4B, on generated hunts. One run by default.

- **Premise:**
  - valid JSON
  - checks passed on the first try
  - solvable on the first try
  - fixes needed
  - premises thrown out
  - seconds per premise
- **Conversation:** a scripted list of typed questions for each role, plus attempts to get the answer for free ("just tell me who started it"). Each answer is scored on:
  - whether the intent was read right
  - leaks
  - contradictions
  - made-up facts
  - judge calls, right and wrong
- **Performance and comedy:**
  - speed per line
  - video memory
  - funny: the Comedy Critic's score, plus every line side by side for David's call

## Build order and checkpoints

At each checkpoint I stop and wait for David.

1. Part 1 and the one-model change. **Checkpoint:** three generated premises, written out for David to read, before any work on the day.
2. Part 2. **Checkpoint:** David plays it.
3. Part 3. **Checkpoint:** before and after on a few lines.
4. Part 4. **Checkpoint:** David plays it.
5. Part 6, on Qwen only.

## Spoiler rules the rebuild keeps

- The night screen shows only the town.
- People show only their name and job, with no type or fingerprint labels.
- The notebook is word for word, with nothing worked out.
- A failed call-out gets the same answer for everyone, and the judge runs every time.
- Telltale faces and moves are locked until someone cracks, and liars can't confess early.
- The DM view only opens with `--dm`.
- There are no conversation buttons. Everything is typed.
- The README gives the solution only in the instructor section.

## Decisions (David, 2026-11-13)

1. The Intent Reader is added. Yes.
2. The five actors keep their type and fingerprint. Their jobs, places, relationships and secrets are generated. Yes.
3. The player twists wait until the player's real actions go into the ledger. Milestone 1 uses no twist or the victim's stunt.
4. The example story David gave was an example only. It isn't used anywhere: not in prompts, not as a fallback, not as a premise, and not in any document.
5. The game ships with one model. There's no player choice and no model name on screen.

The docs were updated to match on 2026-11-13: the GDD (and its PDF), the notes, the cast, the agent pipelines, the model choice, the visual ideas and the README.
