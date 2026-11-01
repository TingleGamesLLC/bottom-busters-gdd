# common.py (left out of this repository)

`common.py` is the file every agent in the crew shares. It isn't here because this repository is public and that file holds details of my private network: a machine's address on my home network, the login name on it, and where my SSH key sits on my PC. It holds no passwords or API keys, but those details don't belong in public.

The crew's code imports it, so the code here won't run without it. It needs my local setup anyway, as the README says under "Running it".

## What's in it

| Name | What it does |
|---|---|
| `ask` | One chat request through MindRouter, on the calling agent's own key. Stops the run with the reason if MindRouter can't be reached |
| `ask_json` | `ask`, but the reply must be a JSON object with the required fields. Malformed output gets one fix prompt, then raises `MalformedOutput` |
| `extract_json` | Finds the first JSON object in a model's reply, ignoring anything wrapped around it |
| `agent_key` | Reads each agent's own MindRouter key from the cluster into memory for the run. It's never written to the PC |
| `Usage`, `RUN_CAPS` | Counts each agent's tokens and stops it at its cap for the run |
| `Cheeks`, `cheeks_for` | Two cheeks per agent. A failed job pops one, both popped stops the agent, and a finished job refills them |
| `Run` | One crew run's folder and shared state. `save` writes `run.json` under a lock, `event` logs what happened, and `send` writes a handoff message |
| `CrewStop`, `MalformedOutput`, `NeedsDavid`, `NeedsAgent` | The ways a job can end short of done, each with its reason |
| `RUNS`, `MEMORY`, `SUBMISSIONS` | Where runs, the crew's memory and finished work are kept |
| `WRITER_MODEL`, `VISION_MODEL` | `qwen3:30b-instruct` and `qwen2.5vl:7b` |

## The handoff message

Agents never call each other. `Run.send` writes each handoff to the run's `messages` folder as a numbered JSON file, such as `0001_orchestrator_to_character-artist_task.json`, in this shape:

```json
{"n": 1, "at": "2026-10-31T21:12:59", "from": "orchestrator", "to": "character-artist", "kind": "task", "payload": {}}
```
