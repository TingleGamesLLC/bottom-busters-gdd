# Rumor Mill (bonus assignment)

**An original game by Tingle Games LLC.** Designed by David St. Onge. © 2026 Tingle Games LLC. All rights reserved.

Multi-Agent AI for Game Development (ELVTR), Class 10 bonus: an AI virtual Dungeon Master built on AI narrative systems.

Rumor Mill is a comedy detective game built on the childhood game Telephone. Every morning someone in town tells you a rumor about yourself. You trace it back from mouth to mouth, catch the liars, find the proof, and pick the starter's comeuppance before the rumor turns into a scandal. The Dungeon Master is a crew of AI agents running on a small model on the player's own PC, with a truth ledger and a mutation log so every rumor can be traced back to what really happened.

## What's here

| File | What it is |
|---|---|
| `RUMOR_MILL_GDD.md` / `.pdf` | The game design document. The current spec. |
| `proto/` | Milestone 1, the class deliverable: the AI Dungeon Master in text, a Python terminal game with pixel art. Start with `proto/README.md`, which also explains how a hunt is solved and where each Class 10 system lives in the code. |
| `proto/rm/` | The game's source: the agents, the facts ledger, the night shift, the world and the screens |
| `proto/results/` | The rumor tests and the gold set of six rumors the game plays |
| `proto/spikes/` | Throwaway scripts behind those rumor tests |
| `proto/state/` | The ledger, carryover and agent log from a test game |
| `CAST.md` | The 12-actor repertory cast |
| `MODEL_CHOICE.md` | Why Qwen3.5-4B, its settings, and the fine-tuning plan |
| `RUMOR_RULES.md` | What a rumor is and how one is built (draft) |
| `GAP_ANALYSIS.md` | Why the early rumor tests failed, and what changed |
| `AGENT_PIPELINES.md`, `VISUAL_UNREAL_IDEAS.md` | Early agent and visual brainstorms (the GDD is current) |
| `RUMOR_MILL_NOTES.md` | The working log: status, decisions and dates |

## Running the prototype

Windows PC with an NVIDIA GPU, Python 3.13.

1. `pip install rich textual httpx`
2. Put llama.cpp's Windows CUDA 13 build in `proto/bin/` (release b12327, from https://github.com/ggml-org/llama.cpp/releases). The game starts `proto/bin/llama-server.exe`.
3. Put a Q4_K_M GGUF of Qwen3.5-4B (https://huggingface.co/Qwen/Qwen3.5-4B) in `proto/models/`, named `Qwen3.5-4B-Q4_K_M.gguf`.
4. Run `proto/play.cmd`, or `play dm` for instructor mode, where F2 opens the DM view.

The model (2.6 GB) and the llama.cpp program files (751 MB) aren't in this repo because of their size.
