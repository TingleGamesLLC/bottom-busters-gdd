"""ComfyUI on the dev PC: paints one picture with Flux schnell. Free and local; the Level Architect's only painter.

When ComfyUI isn't running, start() launches it with comfy-cli in the background and waits until it answers (DAVID,
2026-11-07: "the cluster should know to run comfy ui if needed"). A run that still can't reach it stops and says so.
"""
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from PIL import Image

from common import CrewStop

URL = "http://127.0.0.1:8188"
OUTPUT = Path(r"C:\comfy\ComfyUI\output")
CHECKPOINT = "flux1-schnell-fp8.safetensors"
COMFY_CLI = Path(r"C:\comfy\venv\Scripts\comfy.exe")
WORKSPACE = Path(r"C:\comfy\ComfyUI")
START_WAIT = 300   # seconds for ComfyUI to answer after a launch


def up():
    try:
        with urllib.request.urlopen(URL + "/system_stats", timeout=5):
            return True
    except OSError:
        return False


def start(wait=START_WAIT, launch=subprocess.Popen, sleep=time.sleep, clock=time.time):
    """ComfyUI answering on this PC: launched in the background if it isn't, then waited for. Returns True if it was launched."""
    if up():
        return False
    # comfy-cli's background launch calls "comfy" through the shell, so its venv's Scripts folder goes first on the PATH.
    env = dict(os.environ, PATH=f"{COMFY_CLI.parent}{os.pathsep}{os.environ.get('PATH', '')}")
    launch([str(COMFY_CLI), "--skip-prompt", "--workspace", str(WORKSPACE), "launch", "--background"], env=env,
           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    deadline = clock() + wait
    while clock() < deadline:
        sleep(5)
        if up():
            return True
    raise CrewStop(f"ComfyUI was launched but didn't answer at {URL} within {wait} seconds: see {WORKSPACE}\\user\\comfyui_8188.log")


def _get(path, body=None, timeout=60):
    req = urllib.request.Request(URL + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.URLError as e:
        raise CrewStop(f"ComfyUI isn't answering at {URL}: start it ({e.reason})") from None


def queue(graph, timeout=600):
    """Run one graph and return the path of the picture it saved."""
    pid = _get("/prompt", {"prompt": graph, "client_id": str(uuid.uuid4())})["prompt_id"]
    end = time.time() + timeout
    while time.time() < end:
        h = _get(f"/history/{pid}", timeout=30).get(pid) or {}
        for node in (h.get("outputs") or {}).values():
            for img in node.get("images", []):
                return OUTPUT / img.get("subfolder", "") / img["filename"]
        if (h.get("status") or {}).get("status_str") == "error":
            raise CrewStop(f"ComfyUI's job failed: {json.dumps(h['status'])[:400]}")
        time.sleep(1)
    raise CrewStop(f"ComfyUI didn't finish in {timeout} s")


def graph(prompt, seed, width, height):
    """Flux schnell, 4 steps, as in the tests of 2026-11-04."""
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CHECKPOINT}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["2", 0]}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "5": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0],
                                                    "latent_image": ["4", 0], "seed": seed, "steps": 4, "cfg": 1.0,
                                                    "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "crew_level_architect"}},
    }


def paint(prompt, seed, width, height):
    return Image.open(queue(graph(prompt, seed, width, height))).convert("RGB")
