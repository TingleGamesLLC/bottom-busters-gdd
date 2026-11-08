"""What every agent in the crew shares: paths, the cluster call, cheeks, and the handoff messages between agents.

Handoffs are files. An agent never calls another agent; it writes a message with a declared shape into the run's
messages folder, and the Orchestrator hands it to the next agent. Only the Orchestrator writes run.json, under a lock,
so no two agents can change the shared state at once. (Class notes: structured message passing, global state protection.)
"""
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

import paramiko

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
MEMORY = HERE / "memory.md"
WORK = HERE / "work"
SUBMISSIONS = Path(r"C:\cluster\submissions")

ROUTER = "http://192.168.1.10:8000"
NODE_A = "192.168.1.10"
SSH_KEY = "C:/Users/david/.ssh/genevieve_ed25519"
DASHBOARD = "/Users/gen/bbust-dashboard"

WRITER_MODEL = "qwen3:30b-instruct"
VISION_MODEL = "qwen2.5vl:7b"

# Token caps per run. The GDD's per-agent budgets are for the whole semester and live on the Crew tab.
RUN_CAPS = {"orchestrator": 12000, "character-artist": 30000, "technical-writer": 12000, "level-architect": 30000,
            "critic": 120000,   # a GDD check on every design and roast batch, a second look at each finding, the picture reviews
            "roast-writer": 60000,   # two calls per event in a batch: write, then pick
            "wardrobe-stylist": 40000}   # one recipe call per item, up to 5 a run, with a fix prompt each


class CrewStop(RuntimeError):
    """Something the crew can't fix by retrying. The run stops, says why, and waits for David."""


class NeedsDavid(CrewStop):
    """This work can't go on without David's answer. The question is the message."""


class NeedsAgent(CrewStop):
    """This work needs an answer from another agent, carried through the Orchestrator."""

    def __init__(self, to, question):
        super().__init__(f"needs {to}: {question}")
        self.to, self.question = to, question


def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(NODE_A, username="gen", key_filename=SSH_KEY, timeout=15, look_for_keys=False, allow_agent=False)
    return c


_keys = None


def agent_key(agent):
    """Each agent's own MindRouter key, read from Node A into memory for this run. Never written to this PC."""
    global _keys
    if _keys is None:
        c = ssh()
        try:
            _, out, _ = c.exec_command(f"cat {DASHBOARD}/crew_keys.json", timeout=20)
            _keys = json.loads(out.read())
        finally:
            c.close()
    entry = _keys.get(f"crew-{agent}")
    if not entry or entry.get("revoked"):
        raise CrewStop(f"{agent} has no MindRouter key on Node A")
    return entry["key"]


class Usage:
    def __init__(self):
        self.tokens = {}
        self.by_model = {}  # (agent, model): [input, output], for Paperclip's cost records

    def add(self, agent, n, model=None, prompt=0, completion=0):
        self.tokens[agent] = self.tokens.get(agent, 0) + (n or 0)
        if model:
            split = self.by_model.setdefault((agent, model), [0, 0])
            split[0] += prompt or 0
            split[1] += completion or 0

    def check(self, agent):
        cap = RUN_CAPS.get(agent)
        if cap and self.tokens.get(agent, 0) >= cap:
            raise CrewStop(f"{agent} reached its cap of {cap} tokens for this run")


usage = Usage()

# Every model call in a run, its prompt and reply word for word, in the run's prompts.jsonl. Run sets it. It's the record that
# each maker read the GDD before it wrote, and of what the Critic checked.
PROMPT_LOG = None


def _record(agent, model, messages, reply, u):
    if PROMPT_LOG is None:
        return
    def plain(content):   # pictures are recorded as a placeholder, not their bytes
        if isinstance(content, list):
            return [p if p.get("type") != "image_url" else {"type": "image_url", "image_url": "(picture)"} for p in content]
        return content
    entry = {"at": now(), "agent": agent, "model": model, "tokens": u.get("total_tokens"),
             "messages": [dict(m, content=plain(m.get("content"))) for m in messages], "reply": reply}
    with open(PROMPT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def ask(agent, messages, model=WRITER_MODEL, max_tokens=1500, timeout=600):
    """One chat request through MindRouter on this agent's own key. Returns the reply text."""
    usage.check(agent)
    req = urllib.request.Request(ROUTER + "/v1/chat/completions",
                                 data=json.dumps({"model": model, "messages": messages, "max_tokens": max_tokens}).encode(),
                                 headers={"Authorization": "Bearer " + agent_key(agent), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        raise CrewStop(f"MindRouter answered HTTP {e.code} for {agent}: {e.read().decode('utf-8', 'replace')[:300]}")
    except urllib.error.URLError as e:
        raise CrewStop(f"could not reach MindRouter for {agent}: {e.reason}")
    u = d.get("usage") or {}
    usage.add(agent, u.get("total_tokens"), model, u.get("prompt_tokens"), u.get("completion_tokens"))
    reply = d["choices"][0]["message"]["content"] or ""
    _record(agent, model, messages, reply, u)
    return reply


def extract_json(text):
    """The first JSON object in a model's reply, ignoring anything it wrapped around it. Returns None if there isn't one."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    start = text.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for k, ch in enumerate(text[start:], start):
            if in_str:
                esc = (ch == "\\") and not esc
                if ch == '"' and not esc:
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:k + 1])
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    return None


def ask_json(agent, messages, required, model=WRITER_MODEL, max_tokens=1500, tries=2):
    """ask(), but the reply must be a JSON object with the required fields. Malformed output gets one fix prompt."""
    messages = list(messages)
    problem = "no reply"
    for _ in range(tries):
        reply = ask(agent, messages, model=model, max_tokens=max_tokens)
        d = extract_json(reply)
        missing = [k for k in required if not isinstance(d, dict) or k not in d]
        if not missing:
            return d
        problem = "not a JSON object" if not isinstance(d, dict) else f"missing fields {missing}"
        messages += [{"role": "assistant", "content": reply[:2000]},
                     {"role": "user", "content": f"That reply was {problem}. Answer again with only one JSON object with the "
                                                 f"fields {required}."}]
    raise MalformedOutput(f"{agent} gave malformed output twice ({problem})")


class MalformedOutput(RuntimeError):
    """Output that failed its format check. Costs the agent a cheek; it gets a fix prompt if it has a cheek left."""


class Cheeks:
    """Two per agent, like the characters in the game. A failed job pops one, both popped stops the agent, a finished
    job refills them."""

    def __init__(self, agent):
        self.agent = agent
        self.count = 2

    def pop(self):
        self.count -= 1
        return self.count

    def refill(self):
        self.count = 2


def cheeks_for(agent):
    return Cheeks(agent)


class Run:
    """One crew run's folder and its shared state. Only the Orchestrator holds this object."""

    def __init__(self, run_id=None):
        global PROMPT_LOG
        self.id = run_id or time.strftime("%Y%m%d-%H%M%S")
        self.dir = RUNS / self.id
        self.messages = self.dir / "messages"
        self.messages.mkdir(parents=True, exist_ok=True)
        PROMPT_LOG = self.dir / "prompts.jsonl"
        self.count = 0
        self.state = {"id": self.id, "started": now(), "status": "running", "card": None, "tasks": [], "events": []}
        self.save()

    def save(self):
        lock = self.dir / "run.lock"
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)  # raises if another writer holds it
        try:
            tmp = self.dir / "run.tmp"
            tmp.write_text(json.dumps(self.state, indent=2), encoding="utf-8")
            tmp.replace(self.dir / "run.json")
        finally:
            os.close(fd)
            lock.unlink()

    def event(self, agent, text):
        self.state["events"].append({"at": now(), "agent": agent, "text": text})
        self.save()
        print(f"[{time.strftime('%H:%M:%S')}] {agent}: {text}", flush=True)

    def send(self, sender, receiver, kind, payload):
        """Write one handoff message and return it."""
        self.count += 1
        msg = {"n": self.count, "at": now(), "from": sender, "to": receiver, "kind": kind, "payload": payload}
        path = self.messages / f"{self.count:04}_{sender}_to_{receiver}_{kind}.json"
        path.write_text(json.dumps(msg, indent=2), encoding="utf-8")
        return msg


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")
