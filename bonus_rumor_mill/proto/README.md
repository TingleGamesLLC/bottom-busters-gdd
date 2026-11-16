# Rumor Mill, Milestone 1 prototype

The AI Dungeon Master in text, played in the terminal with pixel art, on a model running on this PC.

**Status (2026-11-15): built around David's six approved hunts** (`rm/hunts.py`). Each game plays one of them: the rumor, the chain, the truth and the proof are fixed. The AI plays every person live while you type, and writes the morning paper, the barks and the comeuppance.

## Play

Double-click `play.cmd`. It opens a maximized Windows Terminal window.

- `play` plays the game.
- Add `dm` (`play dm`) for instructor mode, where F2 opens the DM view. Players don't get it, since it shows the whole chain.

Or run it yourself from this folder: `python rumormill.py [--dm]`.

The night takes a minute or two while the agents build the town and the rumor. If the model can't load, the game says so and doesn't start.

Controls: in town, use the left and right arrows (or 1 to 5) to pick a place, Up and Down to read your notebook, and Enter to go talk. In a conversation, type anything and press Enter. Esc leaves. Each conversation costs an hour, you get six lines per visit, and at 6 PM the rumor hits Scandal. Ctrl+Q quits.

How to play: someone in town is telling a story about you. Find out who told whom, look around the places in town for proof, and when someone's story doesn't add up, call it out or show them what you found. Find who started it before 6 PM.

---

**Everything below is for the instructor.**

## Keeping it a mystery

The player only ever sees what they witness:
- The night screen is just the town.
- The notebook is a word-for-word record, with nothing worked out. It lists what's in your pocket.
- Nobody is labeled by type or fingerprint. People show only their name and job.
- There are no conversation buttons. Everything is typed, and the Intent Reader works out what you mean.
- A failed call-out gets the same answer for everyone, and the judge runs every time, so neither the wording nor the timing points at a liar.
- Telltale faces and moves stay locked until someone cracks. A liar's lines are checked, so they can't confess on their own.
- Evidence snaps an honest person's belief back to the truth. It never cracks anyone.
- The DM view needs `--dm`.

## How a hunt is solved (the solution)

The game plays one of the six hunts in `rm/hunts.py`. The DM view's Quest tab shows this game's: what really happened, the steps, the proof and where it is, and the lie. In general:
- Honest people name who told them, and where and when, if you ask.
- The starter says nobody told them: they saw it themselves.
- Type "look around" at a place to search it. The proof is at one place (two in hunt 1).
- Hunts 1, 2, 5 and 7: the starter is lying. Call them out while holding the proof and they crack. Showing it to them doesn't crack them.
- Hunts 3 and 4: the starter got it wrong by mistake. Show them the proof and it's solved.
- Then you pick their comeuppance.

## Where the Class 10 systems are

| Class 10 system | In the prototype |
|---|---|
| Facts Ledger, saved after every update | `state/ledger.json`: the truth ledger, a belief ledger per character, the rumor chain, the mutation log, the lies, who saw what, and the night shift's log |
| Narrative Consistency Agent | `rm/agents.py`: `consistency_line()` checks every live line against what that person already said, and the chain's one change per hop is logged in the mutation log |
| Remembering player actions | What you say, look at, show and call out goes in the ledger. At the end, your actions are saved to `state/carryover.json` |
| Pruning | `rm/ledger.py`, `prune_dialogue()`: keeps conversation prompts small using `relevance_score`, which is set when each line is born, from recency and the ledger's own keywords |

Every agent call, its result, its speed and whether code had to build a plain line show up in the DM view (F2, instructor mode) and in `state/agent_log.jsonl`.

## The agents

The night shift (`rm/night.py`) sets up one of the six hunts in `rm/hunts.py`: the town, the chain word for word, the lie, the proof and what everyone believes, all saved to the ledger. Then the LLM agents write the morning:
1. Clue Writer (LLM): everyone's first words, with their fingerprint.
2. Town Crier (LLM): the morning paper.
3. Gossip Barks (LLM): one-liners as you walk past, and overheard lines for the Director.
4. Escalation Agent (LLM): what the town does as the rumor heats up.

The morning hook is the approved rumor, word for word, from the last person in the chain.

In the day (`rm/world.py`): the Intent Reader (LLM), the NPC Actor (LLM), the Gotcha Judge (LLM), the Director (code), and at the end the Reward Menu Agent and Scene Director (LLM). The Funny Gate (`rm/funny.py`) checks every line you see: the Comedy Critic (LLM), the Joke Ledger, the Callback Bank and the rails filter (code).

## Model test

Not yet updated for the six hunts (2026-11-15), so it won't run as is. `python model_test.py` plays one generated hunt on the game's model (add `--runs N` for more) and writes `results/model_test_<date>.md`. It scores the premise (valid JSON, first-try passes, solvable on the first try, premises thrown out, time), a scripted typed conversation (intent read right, leaks, contradictions, made-up names, the judge's calls), speed, video memory and the Comedy Critic's scores, with every line written. It's a development tool. The game ships with one model and never shows its name.

## Files

| Path | What it is |
|---|---|
| `rumormill.py` | Starts the game |
| `rm/cast.py` | The five actors' types and fingerprints, the tone guide, the rails, the catalog and game numbers |
| `rm/hunts.py` | David's six approved hunts: the rumor, the chain, the truth and the proof |
| `rm/night.py` | The night shift: sets up one of the six, then the agents write the morning |
| `rm/agents.py` | Every LLM agent: prompt, JSON schema and checks |
| `rm/funny.py` | The Funny Gate |
| `rm/world.py` | The day: typed conversation, heat, the Director, the payoff and the score |
| `rm/ledger.py` | The ledger and pruning |
| `rm/llm.py` | Starts llama.cpp's server at low priority and calls it with schema-forced JSON |
| `rm/art.py` | All pixel art: portraits with six faces, the building kit, the rooftop props, the title and icons |
| `rm/ui.py` | The screens |
| `model_test.py` | The model test (development only) |
| `bin/` | llama.cpp build b12327, CUDA 13.5 |
| `models/` | Qwen3.5-4B, the game's one model, Q4_K_M |
