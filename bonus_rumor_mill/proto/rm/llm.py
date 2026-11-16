"""The built-in model. llama.cpp's server runs on this PC at low priority, the game
talks to it over localhost, and every reply is forced to match a JSON schema.

The game ships with one model. Players never choose it and never see its name."""
from __future__ import annotations

import json
import re
import subprocess
import threading
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "bin" / "llama-server.exe"
MODELS_DIR = ROOT / "models"
MODEL_FILE = "Qwen3.5-4B-Q4_K_M.gguf"   # the one model the game ships with
PORT = 8181
URL = f"http://127.0.0.1:{PORT}"

# Model card, non-thinking preset, for creative lines. Judges run cold.
CREATIVE = {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "min_p": 0.0, "presence_penalty": 1.5}
JUDGE = {"temperature": 0.25, "top_p": 0.8, "top_k": 20, "min_p": 0.0, "presence_penalty": 0.0}


class LLMUnavailable(Exception):
    pass


def gpu_mem_used_mib() -> int | None:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout.strip().splitlines()
        return int(out[0])
    except Exception:
        return None


_NON_ENGLISH = re.compile(r"[^\x00-\x7F -ɏ‐-‧‰-⁞€]")

def english_only(s: str) -> bool:
    """The model card warns presence_penalty can make other languages slip in."""
    return not _NON_ENGLISH.search(s)


class Server:
    def __init__(self, model_file: str = MODEL_FILE):
        self.path = MODELS_DIR / model_file
        self.proc: subprocess.Popen | None = None
        self.vram_before: int | None = None
        self.vram_loaded: int | None = None
        self.ready = False
        self.error: str | None = None
        self.log: list[dict] = []
        self.listeners = []
        self.seed: int | None = None     # set by the model test so runs can be repeated
        self._calls = 0
        self._lock = threading.Lock()

    # -- lifecycle ---------------------------------------------------------
    def _running_model(self) -> str | None:
        try:
            r = httpx.get(f"{URL}/v1/models", timeout=2)
            data = r.json().get("data") or r.json().get("models") or []
            return json.dumps(data)
        except Exception:
            return None

    def start(self, timeout: float = 120) -> bool:
        running = self._running_model()
        if running is not None:
            if self.path.name in running or self.path.stem in running:
                self.ready = True
                self.vram_loaded = gpu_mem_used_mib()
                return True
            self.error = f"Another program is already using port {PORT}. Close it and start again."
            return False
        if not BIN.exists() or not self.path.exists():
            self.error = "The game's AI files are missing."
            return False
        self.vram_before = gpu_mem_used_mib()
        (ROOT / "state").mkdir(exist_ok=True)
        logf = open(ROOT / "state" / "llama_server.log", "w", encoding="utf-8", errors="replace")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
        self.proc = subprocess.Popen(
            [str(BIN), "-m", str(self.path), "-c", "8192", "-ngl", "99", "--port", str(PORT),
             "--host", "127.0.0.1", "--jinja", "-np", "1"],
            stdout=logf, stderr=subprocess.STDOUT, cwd=str(BIN.parent), creationflags=flags,
        )
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.proc.poll() is not None:
                self.error = "The AI stopped while loading. See state/llama_server.log."
                return False
            try:
                if httpx.get(f"{URL}/health", timeout=1).json().get("status") == "ok":
                    self.ready = True
                    self.vram_loaded = gpu_mem_used_mib()
                    return True
            except Exception:
                pass
            time.sleep(0.4)
        self.error = "The AI took too long to load."
        return False

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except Exception:
                self.proc.kill()

    # -- calls ---------------------------------------------------------------
    def call(self, agent: str, system: str, user: str, schema: dict, mode: str = "creative",
             max_tokens: int = 400) -> tuple[dict | None, dict]:
        if not self.ready:
            raise LLMUnavailable(self.error or "model not loaded")
        params = CREATIVE if mode == "creative" else JUDGE
        body = {
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_schema", "json_schema": {"name": agent, "schema": schema}},
            "chat_template_kwargs": {"enable_thinking": False},
            "max_tokens": max_tokens,
            **params,
        }
        with self._lock:
            self._calls += 1
            if self.seed is not None:
                body["seed"] = self.seed * 100003 + self._calls
            t0 = time.time()
            try:
                r = httpx.post(f"{URL}/v1/chat/completions", json=body, timeout=180)
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                raise LLMUnavailable(str(e))
            ms = (time.time() - t0) * 1000
        content = data["choices"][0]["message"].get("content") or ""
        tim = data.get("timings", {})
        stats = {
            "agent": agent, "ms": round(ms),
            "prompt_tokens": tim.get("prompt_n"), "output_tokens": tim.get("predicted_n"),
            "tokens_per_sec": round(tim.get("predicted_per_second") or 0, 1),
            "json_ok": False, "raw": content,
        }
        try:
            obj = json.loads(content)
            stats["json_ok"] = True
        except Exception:
            obj = None
        return obj, stats

    def record(self, entry: dict):
        entry["t"] = time.strftime("%H:%M:%S")
        self.log.append(entry)
        try:
            with open(ROOT / "state" / "agent_log.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps({k: v for k, v in entry.items() if k != "raw"}) + "\n")
        except Exception:
            pass
        for fn in list(self.listeners):
            try:
                fn(entry)
            except Exception:
                pass
