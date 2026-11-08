"""The PixelLab calls the crew needs: paint inside a mask, and read the balance.

The token stays where Claude Code keeps it, in ~/.claude.json. It's read into memory for the run and only ever sent to
api.pixellab.ai. Every call is charged, so this also counts what each one cost. Standard library only, so it can be read on its own.
"""
import base64
import json
import os
import time
import urllib.error
import urllib.request

from common import CrewStop, MalformedOutput, NeedsDavid


class ContentBlocked(MalformedOutput):
    """PixelLab's safety filter refused the prompt. It misfires on harmless requests and rewording usually clears it, so this
    is a send-back with new words, not a stop (run 20261107-165733 stopped the Character Artist's card on one)."""

API = "https://api.pixellab.ai/v2"
POLL_SECONDS = 5
BUSY_TRIES = 6       # how many times a "too many jobs" answer gets waited out before the run stops
BUSY_SECONDS = 15
GENERATIONS_PER_CALL = 5   # what inpaint-image-pro-flash charged on every call so far (runs of 2026-11-01)

_token = None
_spent = {"calls": 0, "usd": 0.0, "generations": 0.0}


def token():
    global _token
    if _token is None:
        with open(os.path.expanduser("~/.claude.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        servers = [p.get("mcpServers", {}) for p in cfg.get("projects", {}).values()] + [cfg.get("mcpServers", {})]
        found = [s["pixellab"]["headers"]["Authorization"] for s in servers if s.get("pixellab", {}).get("headers", {}).get("Authorization")]
        if not found:
            raise CrewStop("no PixelLab token in ~/.claude.json")
        _token = found[0]
    return _token


def _call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    for _ in range(BUSY_TRIES):
        req = urllib.request.Request(API + path, data=data, method=method,
                                     headers={"Authorization": token(), "Content-Type": "application/json", "User-Agent": "bbust-crew/1"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 529):
                time.sleep(int(e.headers.get("Retry-After") or BUSY_SECONDS))
                continue
            if e.code == 401:
                raise CrewStop("PixelLab rejected the token")
            if e.code == 402:
                raise CrewStop("PixelLab is out of credits and generations")
            raise CrewStop(f"PixelLab answered HTTP {e.code} on {path}: {e.read().decode('utf-8', 'replace')[:300]}")
        except urllib.error.URLError as e:
            raise CrewStop(f"could not reach PixelLab: {e.reason}")
    raise CrewStop(f"PixelLab stayed too busy on {path}")


def balance():
    """{"usd": credits left, "generations": subscription generations left}."""
    d = _call("GET", "/balance")
    return {"usd": d["credits"]["usd"], "generations": d["subscription"]["generations"]}


def check_room():
    """Before a call: ask David rather than run PixelLab dry in the middle of a character. DAVID, 2026-11-03: no per-run cap."""
    left = balance()
    if left["generations"] < GENERATIONS_PER_CALL and left["usd"] <= 0:
        raise NeedsDavid(f"PixelLab has {left['generations']:g} generations and ${left['usd']:.2f} left, and a call takes "
                         f"{GENERATIONS_PER_CALL}: it needs a plan or credits")


def spent():
    """This run's calls and what they cost."""
    return dict(_spent)


def _charge(usage):
    usage = usage or {}
    _spent["usd"] += usage.get("usd") or 0.0
    _spent["generations"] += usage.get("generations") or 0.0


def _find_image(node):
    """The first base64 image in a job's reply. The spec leaves its place open for this call."""
    if isinstance(node, dict):
        if isinstance(node.get("base64"), str):
            return node["base64"]
        node = list(node.values())
    if isinstance(node, list):
        for item in node:
            found = _find_image(item)
            if found:
                return found
    return None


def _png(data):
    return {"type": "base64", "base64": base64.b64encode(data).decode(), "format": "png"}


def inpaint(image_png, mask_png, description, seed, timeout=600):
    """Paint the white part of the mask and keep every other pixel exactly. Same size in and out. Returns (png bytes, usage)."""
    job = _call("POST", "/inpaint-image-pro-flash", {"image": _png(image_png), "mask_image": _png(mask_png), "description": description[:2000],
                                                     "seed": seed, "no_background": True, "output_method": "Modify current layer"})
    _spent["calls"] += 1
    end = time.time() + timeout
    while time.time() < end:
        state = _call("GET", f"/background-jobs/{job['background_job_id']}")
        if state["status"] == "completed":
            usage = state.get("usage") or job.get("usage") or {}
            _charge(usage)
            found = _find_image(state.get("last_response"))
            if not found:
                raise CrewStop(f"PixelLab finished with no image: {sorted((state.get('last_response') or {}).keys())}")
            return base64.b64decode(found), usage
        if state["status"] == "failed":
            said = str(state.get("last_response"))
            if "content policy" in said.lower():
                raise ContentBlocked("PixelLab's safety filter refused the picture's description: describe the hair and face in "
                                     "other words")
            raise CrewStop(f"PixelLab's job failed: {said[:300]}")
        time.sleep(POLL_SECONDS)
    raise CrewStop(f"PixelLab did not finish within {timeout} s")
