# Rumor Mill: gap analysis (2026-11-13, revised after the twist test)

Written after six rounds of rumor tests. David's verdict on each round: terrible. That's the starting point here, not something to argue with. No example stories appear in this file, on purpose.

**Update (2026-11-14):** the ceiling test in section 6 has run (`proto\results\rumor_ceiling_2026-11-13.md`). David liked 3 of the 10 Claude wrote, so good rumors can exist under these rules. The work now is a gold set of rumors at his bar. See `RUMOR_MILL_NOTES.md` section 0.

## The answer

Rumor Mill has three layers, and they're in very different shape:

1. **The hunt machinery works.** The ledgers, the chain, the mutation log, the solvability check, heat, the notebook and the replay are built and run end to end, and generated hunts are solvable. This is the Class 10 part, and it isn't the problem.
2. **The hook hasn't been tested, but it hasn't failed either.** Someone tells you a rumor about yourself, and you hunt down who started it. Nobody has played it yet.
3. **The content has failed every test.** The promise is that the AI invents every rumor and makes it funny. That has failed six rounds in a row, about 60 rumors on two models.

Layer 3 is what's thrashed. The concept as a whole isn't dead, but this promise is, unless something below changes.

## 1. Evidence

All reports are in `proto\results\`. All rounds ran on Qwen3.5-4B unless noted.

| Round | What was tried | Result |
|---|---|---|
| `rumor_spike_..._1421` | The whole ladder, truth to morning, in one call | 0 of 10 passed the judge |
| `rumor_spike_..._1531` | Code picks a kind of rumor (a "shape") | 1 of 10 passed; shapes mostly ignored |
| `rumor_step1_..._1554` | One sentence per call, nothing else | 1 of 10 usable; shapes ignored |
| `rumor_step2_..._1601` | Each shape asked as short questions | 10 of 10 on shape; quality poor |
| `rumor_step2_..._1624` | Plus code checks for stealing, names and overuse | Every check passed; David: all terrible |
| `rumor_twist_..._2238` | The player gets a life and 10 real acts; each act is twisted by the 4B and by the cluster's qwen3:30b-instruct | Both terrible; both stamped the player's one odd trait on nearly every rumor (4B 8 of 10, 30B 9 of 10) |

Each fix solved the problem it targeted. The content stayed bad. The bigger model wasn't better, but that comparison is muddied: the 4B wrote the player's life and the real acts both models worked from, and those were nonsense.

## 2. Concept gaps

**2.1 Nobody has shown that a good rumor can exist under all the rules at once.** We wrote down what a rumor must be: the five tests in RUMOR_RULES.md. No model has produced one that passes David's eye. More importantly, we never checked whether any writer, model or human, could meet all the rules and the tone at the same time. Every round so far has tested a model against a target that might not exist.

**2.2 Every prompt asks for two opposite things.**
- **Wild:** the tone guide goes into every prompt. It asks for slapstick, "deadpan about absurd things," escalation, and naming the exact thing and amount. The GDD's Pillar 2 says the joke is the gap between a boring truth and a wild rumor. The fingerprints are absurd by design: Gary's "hundreds," Toby's prices.
- **Believable:** RUMOR_RULES.md says every version must be believable, one claim, petty, and only a little worse at each step.
- **The result:** the models land in between. Their rumors are random and odd, which is neither funny-wild nor believable. Whether taking the tone guide out of rumor prompts would help hasn't been tested.

**2.3 A cartoon world has nothing at stake.**
- **The town is cartoon.** Generated towns are pun names, and jobs often just restate the actor's type.
- **The player is blank or cartoon.** Without a life, they're blank. When given one in the twist test, it was a cartoon too.
- **So nothing stings.** A rumor stings when it hits something real in a world that feels real, and nothing here does.

**2.4 The player never saw the truth.** Telephone's laugh comes from comparing how the message started with how it ended. In game 1 the start is something a stranger did, or nothing at all, so the reveal can't land. The GDD's answer was "the truth is something you really did," but in game 1 the player hasn't done anything yet. The twist test tried to fill that with generated real acts. The same model wrote those acts, and they came out as nonsense.

**2.5 The hunt is a chain of names.** Everyone you question tells you who they heard it from, so the core loop is ask, walk, ask.
- **The only real puzzle is a liar**, and there are 0 or 1 per hunt.
- **Fingerprints aren't needed** when people name their source.
- **Brute force works.** With 5 people and a chain of 3 to 5, asking everyone finds the source.

**2.6 The hardest jobs all land on the weakest part.** Four rules stack up: the AI generates everything, there's one 4B model, no examples are allowed, and the content has to be comedy. Each is workable alone. Together they put the hardest jobs (inventing premises, being funny) on the weakest part, with the fewest tools to help it. The art side already solved this exact problem with Pillar 4: art is made once, and the AI only recombines it. The story side has no equivalent.

## 3. Design gaps (how the systems are built)

- **Models fixate on the oddest detail they're given.** In the twist test, one quirky line about the player took over almost every rumor on both models.
- **Bad generated inputs poison everything after them.** Every later step builds on what earlier steps invented. When the first output is nonsense, there's nothing to recover.
- **Voice leaks into content.** A character's habit, like Toby's plug or Gary's numbers, ends up inside the claim. It showed up in every round.
- **The Telephone-like changes are missing from Milestone 1.**
  - Three distortions in the full cast are mechanical and reliably funny: mishearing, keeping only the last few words, and dropping a detail. None of them are in the five Milestone 1 actors.
  - Every Milestone 1 change makes the model invent something new, and inventing is where it fails.
- **Nothing can measure "good."** The 4B judge is unreliable: it passed a bad rumor and rejected made-up rumors for being made up. The code checks only catch format.
- **No examples in prompts.** This removes the strongest tool a small model has. The GDD's planned fix is fine-tuning on lines a strong model writes and David picks. It isn't started, and whether that training data counts as "examples" is David's call.

## 4. Usability gaps (the player)

- **Nobody has played the rebuild.** Everything here comes from reading outputs, not from play. That's the biggest usability gap.
- **Typed-only conversation on a 4B Intent Reader.** The player has to guess what to type, a misread is likely, and every reply takes 3 to 12 seconds.
- **The night takes 60 to 130 seconds** before play starts.
- **Asking everyone works as a strategy,** so there's little tension (2.5).
- **The player has no reason to care who started it** (2.3, 2.4).

## 5. Feature gaps (the GDD compared with what's built)

| GDD | Prototype now |
|---|---|
| 12-actor cast | 5 actors (Milestone 1 scope) |
| A week, Monday to Sunday | One hunt, on Thursday |
| Your actions today become tomorrow's rumors | Saved only for the next game |
| Twists: you started it, a parrot, the rumor is true | None, or the victim's stunt |
| Heat tiers, believers, reputation | Built |
| Evidence that can't change | Built: a receipt, a ticket stub, a note |
| Comeuppances and the chain replay | Built, in text and pixel art |
| Notebook | Built: only what the player saw and heard |
| Trained in Rumor Mill's voice | Not started |
| Unreal and the plugin check | Not started (Milestone 2) |

## 6. Recommendation: test the ceiling before anything else

One question decides whether layer 3 can be saved: **can a good rumor exist under these rules at all?** Nothing so far answers it, because every round tested a model too weak to tell.

**The test:** the strongest model available at development time writes 10 rumors from the same rules and the same town. That's Claude. It's a throwaway test, not game content, and David judges the results.

- **If David likes them:** the design is sound, and the problem is model strength. The fix is already in the GDD (6.2): fine-tune Qwen 4B on rumors the strong model writes and David picks. That needs his ruling on whether training data counts as examples.
- **If David doesn't like them:** the rumor design itself is wrong, and no model will fix it. The change has to happen at the premise. The strongest option is to do for stories what Pillar 4 does for art: make a set of rumor premises once, and have the AI pick, adapt, voice and mutate them. That reverses the rule that the AI generates everything, so it's David's call alone.

Separately, whichever way that goes, the hunt needs a puzzle beyond following names (2.5). And the player needs a reason to care (2.3, 2.4). Both are design work on paper, before any code.
