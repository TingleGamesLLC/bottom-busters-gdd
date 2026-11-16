# Rumor Mill — Built-in Model: Pick and Best Practices (2026-11-10)

Web research, 2026-11-10. Model card facts are from the official Hugging Face page; everything else is from blogs, guides and forum posts, so the numbers are rough until Milestone 1 measures them.

## The pick: Qwen3.5-4B

- **License:** Apache 2.0 (official model card metadata). Can ship inside a commercial game.
- **Why it fits:** strong at following instructions and tool calling (the card says it "excels in tool calling"), small enough to share the graphics card with Unreal, supported by the main fine-tuning tool (Unsloth), and the most-recommended 4B model in 2026 roundups.
- **Its one weak spot for us:** forum anecdotes say Gemma 4 E4B (also Apache 2.0) is better at creative writing and subtle humor. No real head-to-head test exists. That's covered two ways: fine-tuning on our own funny lines, and Gemma 4 E4B as the backup in the Milestone 1 test.

## Facts from the model card that change how we use it

- **Thinking mode is ON by default.** Turn it off for every agent (`enable_thinking: false` in the chat template settings). The `/nothink` trick from older Qwen versions is not supported. Thinking would waste time and tokens on short JSON jobs.
- **It's a vision model too.** We only need text. Load it text-only (in llama.cpp the vision part is a separate file that can be left out). Confirm in Milestone 1.
- **New architecture** (Gated DeltaNet + attention). The llama.cpp version inside whichever Unreal plugin we use must be new enough to run it. Test first.
- **Huge context (262K tokens), but we don't want it.** Our prompts are about 2,000–3,000 tokens. Set the context window small (around 8K) to keep memory use and speed down.
- **Multi-turn history:** keep only final answers in the history. Our dialogue pruning (Class 10, slide 4) already does this.

## Settings

| Use | Settings | Source |
|---|---|---|
| Creative lines: NPC Actor, Spin, Mutation, barks, Town Crier | temperature 0.7, top_p 0.8, top_k 20, min_p 0, presence_penalty 1.5 | Model card, non-thinking general preset |
| Judges: Consistency Agent, Gotcha Judge, Comedy Critic scores | lower temperature (start around 0.2–0.3) | Our choice; the card uses 0.6 for precise work. Tune in Milestone 1 |

- The card warns that a high presence_penalty can cause **language mixing** (other languages slipping in). Keep it at 1.5 or lower, and have the validator reject lines with non-English characters.

## Getting reliable JSON

- **Constrained decoding.** llama.cpp can force output to match a JSON schema (`--json-schema` or a GBNF grammar), so the JSON is always valid. Generate the grammar from the schema; never hand-write it (a common mistake is grammars drifting from their schemas).
- **Still check the meaning.** Valid JSON can still name a prop that isn't in the catalog or a character who doesn't exist. Every output also gets a game-level check (IDs exist, one field changed, no self-contradiction) and a retry. After a few failed retries, use a gold-example fallback line.
- **Cost of constraints:** estimates range from single-digit percent to 15–30% slower. Measure it.
- One guide says 3B-class models are fine with constrained decoding but poor without it, so the constraint is required, not optional.

## Fine-tuning it into Rumor Mill's voice (development time)

1. A bigger open model on the development cluster writes thousands of example lines inside the bounds (tone guide, cast sheets, JSON formats).
2. The Comedy Critic and David keep the best ones.
3. Fine-tune Qwen3.5-4B on them with Unsloth. Reported guidance:
   - Use **bf16 LoRA**, not 4-bit QLoRA (Qwen3.5 loses more quality to QLoRA than other models do).
   - It needs about **10 GB of VRAM** for the 4B model, which fits the 16 GB RTX 5070 Ti.
   - Reported starting settings: **LoRA rank 16, 2 epochs, learning rate 2e-4.**
4. Merge, then compress to 4-bit GGUF (Q4_K_M, or Unsloth's UD-Q4_K_XL) for shipping.

Research backs this shape: a 2025 paper on NPC dialogue used fine-tuned small models with a fixed persona plus a swappable memory store, which is the same as our cast sheets plus belief ledgers.

## Memory and speed (estimates, measure in Milestone 1)

- **Weights at 4-bit:** about 2.5 GB, based on the older Qwen3-4B. Unsloth's table lists more for Qwen3.5-4B, so measure the real file.
- **Speed:** about 56 tokens/sec on an RTX 4090 for Qwen3-4B. One site reports 14–24 tokens/sec on 4 GB cards. Rendering the game at the same time will slow it down.
- **Run it on a low-priority thread.** One plugin developer notes the model competes with the game for the GPU.
- That's why the design leans on the night batch and the typewriter text with babble voices.

## Proof that shipping a local model in a PC game works

AI People made its whole game run offline on the player's PC with a local model.

## What Milestone 1 settles

Run the same generated hunts on Qwen3.5-4B and Gemma 4 E4B with the same prompts and settings. Score:
- valid JSON
- speed
- memory use
- how funny the lines are, with David making the final call

Qwen3.5-4B is the default unless Gemma clearly wins on funny. The game ships with the one winner. Players never choose a model (DAVID, 2026-11-13).

## Sources

- Qwen3.5-4B model card: https://huggingface.co/Qwen/Qwen3.5-4B
- Unsloth, Qwen3.5 run locally: https://unsloth.ai/docs/models/qwen3.5
- Unsloth Qwen3.5 fine-tune (summaries): https://feedbagel.com/post/guide-to-fine-tuning-qwen35-large-language-models-with-unsloth , https://wikidocs.net/blog/@jaehong/8728/ , https://insiderllm.com/guides/unsloth-studio-setup-guide/
- Thinking-mode parameter conflicts: https://docs.bswen.com/blog/2026-03-24-qwen35-thinking-mode-parameters/
- Qwen3-4B VRAM/speed: https://willitrunai.com/models/qwen-3-4b , https://insiderllm.com/guides/what-can-you-run-4gb-vram/
- Constrained decoding: https://www.aidancooper.co.uk/constrained-decoding/ , https://localaimaster.com/blog/json-mode-grammars-guide , https://llmconfigurator.com/en/guides/llm-json-structured-output
- NPC research: https://arxiv.org/pdf/2511.10277
- AI People offline: https://www.goodai.com/ai-people-now-with-local-llm/
- Gemma vs Qwen anecdotes: https://www.mindstudio.ai/blog/gemma-4-vs-qwen-3-5-open-weight-comparison
- Unreal plugin GPU note: https://forums.unrealengine.com/t/volley-studios-local-multimodal-llm/2746330
