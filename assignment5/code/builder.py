"""Builder: a goal-oriented coding agent for Bottom Busters (Assignment #5, Multi-Agent AI for Game Development, ELVTR).

It reads the game design document (GDD), scans the game's C# code, finds the GDD features the code doesn't have yet,
ranks them with priority_score(), writes the code for the top one, builds the game to check it, and scans again. It stops
when every requirement it can build is met, when it has written the features it was allowed, or when something stops it.

GDD Section 16, the Builder: "Reads this GDD and the project's coding rules and implements one approved feature at a time
in C#, then runs the existing build-and-verify loop." The plan is C:\\cluster\\BUILDER_PLAN.md.

The model reads and writes; plain code checks every claim it makes. A GDD quote has to be in its section word for word, a
line of code it says proves a feature is built has to be in the code, and an edit has to find its place exactly once. The
cluster model (qwen3:30b-instruct, the crew-builder key) writes first; if its code fails the build twice, Claude Code takes
over that feature (DAVID, 2026-11-15: "go with your recommendations").

    python builder.py --dry                       rank the gaps and say which one it would build; writes nothing
    python builder.py --resume <run> --only <id>  build the requirement David approved, in the same run
    python builder.py --max N                     build up to N features, scanning again after each one

Guards: it never edits a file git shows as changed by someone else, writes only under Assets/Scripts, deletes nothing it
didn't make in this run, never commits, pushes or starts the game, and stops if Unity is open.
"""
import argparse
import concurrent.futures
import dataclasses
import difflib
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import codebase
import common
import gdd

AGENT = "builder"
REPO = Path(r"C:\bbust\BBUST")
UNITY = Path(r"C:\Program Files\Unity\Hub\Editor\6000.3.7f1\Editor\Unity.exe")
BUILD_METHOD = "HeadlessBuild.Build"   # the Steam demo and the full test copy; docs/build.md in the game's repo
SKIP_SECTIONS = {"0", "20"}            # the change list and the risks: not features
STATUSES = {"built", "planned", "retired", "on_hold"}
CONTENT = {"characters", "backgrounds", "wardrobe", "roast_lines"}
WORKERS = 3                            # MindRouter has three machines with qwen3:30b-instruct
PROMPT_VERSION = "4"


class Refused(common.MalformedOutput):
    """A change the guards won't write. Costs a cheek, like malformed output."""


# ---------------------------------------------------------------------------------------------------------------------
# Requirements from the GDD

@dataclasses.dataclass
class Requirement:
    id: str
    section: str
    feature: str
    quote: str
    paragraph: str
    status: str
    visible: bool
    content: str
    evidence: list


def flat(text):
    """Text with markdown marks and runs of space taken out, for word-for-word checks."""
    text = re.sub(r"[*`|]", " ", text).replace("\u2019", "'").replace("\u2013", "-").replace("\u2014", "-")
    return re.sub(r"\s+", " ", text).strip()


LABEL = re.compile(r"^\s*\*\*[^*]+\*\*\s*$")   # a line that is only a bold label, like **Full game:** or **Names.**


def paragraph_of(section_text, quote):
    """The bullet, table row or paragraph of the section that holds the quote, with the bold label it sits under (such
    as **Full game:** or **Planned later:**) on the line above it."""
    blocks, cur = [], []
    for line in section_text.splitlines():
        starts = re.match(r"\s*(?:[-*] |\| |\d+\. )", line) or not line.strip() or LABEL.match(line)
        if starts and cur and not re.match(r"\s{2,}\S", line):
            blocks.append("\n".join(cur))
            cur = []
        if line.strip():
            cur.append(line)
    if cur:
        blocks.append("\n".join(cur))
    q = flat(quote)
    label = ""
    for b in blocks:
        if LABEL.match(b):
            label = b.strip()
            continue
        if q in flat(b):
            return (label + "\n" + b.strip()) if label else b.strip()
    return ""


RULING = re.compile(r"(Studio Director|DAVID)[^()\n]{0,80}?\d{4}-\d{2}-\d{2}")


def has_ruling(paragraph):
    return bool(RULING.search(paragraph))


# The GDD's own words decide a feature's status, not the model (the practice run of 2026-11-15 had the model calling the
# cheek sets and the arm flap "planned"; both are in the game).
RETIRED = re.compile(r"\bretired\b|\btaken out\b|\bremoved\b", re.I)
ON_HOLD = re.compile(r"\bon hold\b", re.I)
PLANNED = re.compile(r"\(planned|\bplanned\b|\bnot yet\b|\bteaser\b|\bpromised\b|no gameplay behind it|"
                     r"^\*\*(?:Full game|Planned later):\*\*", re.I | re.M)


def status_of(paragraph):
    if RETIRED.search(paragraph):
        return "retired"
    if ON_HOLD.search(paragraph):
        return "on_hold"
    if PLANNED.search(paragraph):
        return "planned"
    return "built"


CONTENT_WORDS = {"characters": r"\bcharacters?\b|\bskins?\b", "backgrounds": r"\bbackgrounds?\b|\bbackdrops?\b",
                 "wardrobe": r"\bhats?\b|\bshades\b|\bwearables?\b", "roast_lines": r"\broast"}


REQ_SYSTEM = """You read one section of the game design document (GDD) for Bottom Busters, a 2D arcade game built in Unity C#.
List the features of the game that this section describes and that live in the game's code: modes, mechanics, rules, screens, menus, settings, systems.
Leave out business, prices, marketing, people, taste, and anything that is only content (one sprite, one sound, one line of text) rather than code.
For each feature give:
- feature: a short name, under 12 words.
- quote: one sentence or table row copied word for word from the section that states the feature. Copy it exactly, at least 5 words.
- visible: true if a player would see it on screen.
- content: the made content it lets into the game, if any: "characters", "backgrounds", "wardrobe" (hats and shades), "roast_lines", or "none".
- evidence: 3 to 6 names that would appear in the C# code if the feature were built. At least two of them must be method or field names, or exact string literals in double quotes, that belong to this feature alone; a class name (use the game's real class names listed below when they fit) proves little, because the class exists for other reasons.
List every feature the section says is planned, a teaser, promised, for the full game, or planned later, even small ones, each on its own. Then the other features, at most 15 in all.
Answer with only one JSON object: {"features": [...]}"""


def class_names(index):
    names = set()
    for text in index.files.values():
        names.update(re.findall(r"\b(?:class|struct|enum|interface)\s+(\w+)", text))
    return sorted(names)


def _sha(*parts):
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()


def _load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _save(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def read_section(section, classes, ask):
    """One model call: the features a section describes, each checked by plain code. Returns (kept, dropped)."""
    user = (f"GDD Section {section.number}, {section.title}:\n\n{section.text}\n\nEnd of the section.\n\n"
            f"The game's C# classes: {', '.join(classes)}")
    kept, dropped = [], []
    try:
        d = ask(AGENT, [{"role": "system", "content": REQ_SYSTEM}, {"role": "user", "content": user}], ["features"],
                max_tokens=4000)
    except common.MalformedOutput as e:
        return kept, [{"section": section.number, "feature": None, "quote": "", "why": f"the whole section: {e}"}]
    body = flat(section.text)
    for f in d.get("features") or []:
        if not isinstance(f, dict):
            continue
        quote = str(f.get("quote") or "").strip()
        why = None
        if len(flat(quote).split()) < 5:
            why = "quote under 5 words"
        elif flat(quote) not in body:
            why = "quote isn't in the section word for word"
        evidence = [str(e).strip() for e in (f.get("evidence") or []) if str(e).strip()][:6]
        if not why and not evidence:
            why = "no evidence names"
        if why:
            dropped.append({"section": section.number, "feature": f.get("feature"), "quote": quote, "why": why})
            continue
        content = f.get("content") if f.get("content") in CONTENT else "none"
        paragraph = paragraph_of(section.text, quote)
        kept.append(Requirement(id=f"{section.number}-{len(kept) + 1}", section=section.number,
                                feature=str(f.get("feature") or "").strip(), quote=quote, paragraph=paragraph,
                                status=status_of(paragraph or quote), visible=bool(f.get("visible")), content=content,
                                evidence=evidence))
    return kept, dropped


def requirements(sections, classes, ask=common.ask_json, cache=None, workers=WORKERS):
    """Every feature the GDD describes, one section at a time (sections 0 and 20 skipped). Cached by the GDD's text, so
    a rescan in the same loop doesn't read the GDD again. Returns (requirements, dropped)."""
    use = [s for s in sections if s.number not in SKIP_SECTIONS]
    key = _sha(PROMPT_VERSION, *(s.number + s.text for s in use))
    if cache:
        hit = _load(cache)
        if hit and hit.get("key") == key:
            return [Requirement(**r) for r in hit["requirements"]], hit["dropped"]
    with concurrent.futures.ThreadPoolExecutor(workers) as pool:
        results = list(pool.map(lambda s: read_section(s, classes, ask), use))
    reqs, dropped = [], []
    for kept, lost in results:
        reqs += kept
        dropped += lost
    if cache:
        _save(cache, {"key": key, "requirements": [dataclasses.asdict(r) for r in reqs], "dropped": dropped})
    return reqs, dropped


# ---------------------------------------------------------------------------------------------------------------------
# The gap pass

@dataclasses.dataclass
class Gap:
    req: Requirement
    targets: list      # existing files to change, plus at most one new file
    new_file: str
    hits: list         # codebase.Hit
    why: str
    lines: int = 0     # the second look's estimate of the lines the change needs
    context: str = ""  # the requirement's whole GDD section, for the writer


SECOND_SYSTEM = """You check whether a feature from the Bottom Busters game design document (GDD) is already built in the game's Unity C# code.
You see the feature, the GDD's words, and code found by search. Say built only if a line you copy from the code shown proves the specific thing the GDD's words describe is built. A class or struct declaration, a using line, or a class that only sounds related is not proof: when the code shown doesn't prove it, say false.
If it is not built, name the files a change would touch: existing files from the code shown, at most 3, and at most one new .cs file under Assets/Scripts/ if the new code belongs in its own file.
Answer with only one JSON object:
{"built": true or false, "code_quote": "one line copied word for word from the code shown, without its line number, or empty", "targets": ["Assets/Scripts/..."], "new_file": "Assets/Scripts/<Folder>/<Name>.cs or empty", "lines": about how many lines of code the change needs (a number, 0 if built), "why": "one sentence"}"""


def related_files(index, req, limit=3):
    """Files whose class names share the most words with the feature, for a feature the evidence search can't place."""
    words = {w.lower() for w in re.findall(r"[A-Za-z]{4,}", req.feature + " " + req.quote)}
    scored = []
    for path, text in index.files.items():
        for cls in re.findall(r"\bclass\s+(\w+)", text):
            parts = {p.lower() for p in re.findall(r"[A-Z][a-z]+|[a-z]+", cls) if len(p) >= 4}
            overlap = len(parts & words)
            if overlap:
                scored.append((-overlap, path))
    seen, out = set(), []
    for _, path in sorted(scored):
        if path not in seen:
            seen.add(path)
            out.append(path)
    return out[:limit]


def declaring_files(index, names):
    """The files that declare a class or struct with one of these names, in the order of the names."""
    out = []
    for e in names:
        if re.fullmatch(r"\w+", e.strip()):
            decl = re.compile(rf"\b(?:class|struct)\s+{re.escape(e.strip())}\b")
            out += [p for p, text in index.files.items() if p not in out and decl.search(text)]
    return out


def evidence_text(index, req, hits, max_files=3, per_file=4):
    """The code a second look sees: around the search hits, and the outline of related files."""
    # A file that declares a class the feature names comes first (official run 20261115-161537: the search ranked
    # GameManager.cs and CharacterBase.cs above CharacterSelect.cs, so the second look never saw Character Select).
    parts, files = [], declaring_files(index, req.evidence)
    for h in hits:
        if h.path not in files:
            files.append(h.path)
    for path in related_files(index, req):
        if path not in files:
            files.append(path)
    for path in files[:max_files]:
        mine = [h for h in hits if h.path == path][:per_file]
        chunk = [f"--- {path} ({len(index.files[path].splitlines())} lines)"]
        if mine:
            chunk += [codebase.around(index, path, h.line_no, 4, 4) + "\n..." for h in mine]
        chunk.append("Outline:\n" + "\n".join(codebase.outline(index, path).splitlines()[:80]))
        parts.append("\n".join(chunk))
    return "\n\n".join(parts) if parts else "(no code found)"


DECLARATION = re.compile(r"^(?:\[[^\]]*\]\s*)*(?:(?:public|private|protected|internal|static|sealed|abstract|partial)\s+)*"
                         r"(?:class|struct|enum|interface)\s+\w+|^using\s|^namespace\s")


def _quote_in_code(index, quote):
    """The file that holds the quoted line, or None. A type declaration or a using line proves nothing about a feature."""
    q = re.sub(r"^\d+:\s?", "", (quote or "").strip()).strip()
    if len(q) < 10 or DECLARATION.match(q):
        return None
    q = re.sub(r"\s+", " ", q)
    for path, text in index.files.items():
        if q in re.sub(r"\s+", " ", text):
            return path
    return None


def _clean_targets(index, targets, new_file):
    real = []
    for t in targets or []:
        t = str(t).replace("\\", "/").strip()
        if t in index.files and t not in real:
            real.append(t)
    new = str(new_file or "").replace("\\", "/").strip()
    if not (new.startswith(codebase.SCRIPTS + "/") and new.endswith(".cs") and ".." not in new and
            new not in index.files and (index.repo / new).exists() is False):
        new = ""
    return real[:3], new


def second_look(index, req, hits, ask, avoid=()):
    """avoid: files another session has changed and not committed. For a feature David approved, the second look is told
    they can't be changed, so it plans the change without them where it can (official run 20261115-161537 stopped when
    the names feature was planned through GameManager.cs, which the browser session had open)."""
    user = (f"Feature: {req.feature}\nGDD Section {req.section}: \"{req.quote}\"\nThe GDD's paragraph:\n{req.paragraph}\n\n"
            f"Code found by search:\n\n{evidence_text(index, req, hits)}")
    if avoid:
        user += ("\n\nThese files have another session's uncommitted work and can't be changed now: " +
                 ", ".join(sorted(avoid)) + ". Plan the change without them. If the feature truly can't be built without "
                 "one of them, still name it in targets and say why.")
    try:
        return ask(AGENT, [{"role": "system", "content": SECOND_SYSTEM}, {"role": "user", "content": user}],
                   ["built", "code_quote", "targets", "new_file", "lines", "why"], max_tokens=800)
    except common.MalformedOutput as e:
        return {"built": False, "code_quote": "", "targets": [], "new_file": "", "lines": 0,
                "why": f"no usable second look ({e})"}


def find_gaps(reqs, index, ask=common.ask_json, cache=None, workers=WORKERS):
    """The requirements the code doesn't meet. Only what the GDD's own words call planned can be a gap; a feature the GDD
    calls built is checked by its evidence names and listed as confirmed or not, never rebuilt. Returns (gaps, present),
    where present lists every requirement that isn't a gap, how it was checked, and whether that confirmed it."""
    looks = (_load(cache) or {}) if cache else {}
    classes = set(class_names(index))
    todo, present = [], []
    for r in reqs:
        if r.status in ("retired", "on_hold"):
            continue
        found = [e for e in r.evidence if codebase.terms_found(index, [e])]
        specific = [e for e in found if e.strip().strip('"') not in classes]
        hits = codebase.search(index, r.evidence, limit=12)
        if r.status == "built":
            # The GDD says it's built. The search confirms it or can't; either way it's not something to build again:
            # writing a second copy of a working feature is the worst thing this agent could do to the game.
            if len(found) >= 2 and specific:
                present.append({"id": r.id, "feature": r.feature, "confirmed": True,
                                "how": f"{len(found)} of {len(r.evidence)} evidence names in the code, {specific[0]} among them"})
            else:
                present.append({"id": r.id, "feature": r.feature, "confirmed": False,
                                "how": "the GDD says built; the search didn't confirm it (left for a person to check)"})
            continue
        files = sorted({h.path for h in hits} | set(related_files(index, r)))
        key = _sha(PROMPT_VERSION, r.id, r.quote, *(p + index.files[p] for p in files))
        todo.append((r, hits, key))

    def look(item):
        r, hits, key = item
        if key in looks:
            return item, looks[key]
        return item, second_look(index, r, hits, ask)

    with concurrent.futures.ThreadPoolExecutor(workers) as pool:
        answers = list(pool.map(look, todo))
    gaps = []
    for (r, hits, key), a in answers:
        looks[key] = a
        proof = _quote_in_code(index, a.get("code_quote")) if a.get("built") else None
        if proof:
            present.append({"id": r.id, "feature": r.feature, "confirmed": True,
                            "how": f"planned in the GDD, but the second look quoted it from {proof}"})
            continue
        targets, new = _clean_targets(index, a.get("targets"), a.get("new_file"))
        why = str(a.get("why") or "")
        if a.get("built"):
            why = "said built, but its code quote isn't in the code. " + why
        try:
            lines = int(a.get("lines") or 0)
        except (TypeError, ValueError):
            lines = 0
        gaps.append(Gap(r, targets, new, hits, why.strip(), lines))
    if cache:
        _save(cache, looks)
    return gaps, present


# ---------------------------------------------------------------------------------------------------------------------
# priority_score()

def waiting_counts(submissions=common.SUBMISSIONS):
    """How much finished crew work waits outside the game, by kind (C:\\cluster\\submissions\\<kind>)."""
    out = {}
    for kind in CONTENT:
        folder = Path(submissions) / kind
        out[kind] = len([p for p in folder.iterdir() if not p.name.lower().startswith("readme")]) if folder.is_dir() else 0
    return out


def priority_score(gap, dirty, waiting, failed):
    """(score, breakdown). The score is None when the gap is skipped, and the breakdown says why.

    score = 3 * unblocks   finished crew work of this kind waits in C:\\cluster\\submissions, and the GDD paragraph names it
          + 2 * ruling     the GDD paragraph carries a dated Studio Director / DAVID ruling
          + 2 * visible    a player sees it
          + size           1 file and about 120 lines or fewer: 2; up to 3 files and 300 lines: 1; bigger or unknown: 0
    Skipped: a file to change has someone else's uncommitted changes, or the requirement stopped twice before.
    Ties keep GDD order (the caller sorts stably)."""
    r = gap.req
    files = gap.targets + ([gap.new_file] if gap.new_file else [])
    b = {"id": r.id, "feature": r.feature, "section": r.section, "files": files}
    busy = [t for t in gap.targets if t in dirty]
    if busy:
        b["skipped"] = f"{busy[0]} has uncommitted changes (another session's work)"
        return None, b
    if r.id in failed:
        b["skipped"] = "stopped twice in an earlier run"
        return None, b
    words = CONTENT_WORDS.get(r.content)
    unblocks = 1 if waiting.get(r.content, 0) > 0 and words and re.search(words, r.paragraph, re.I) else 0
    ruling = 1 if has_ruling(r.paragraph) else 0
    visible = 1 if r.visible else 0
    n = len(files)
    lines = gap.lines if gap.lines > 0 else None
    size = 2 if n == 1 and lines and lines <= 120 else 1 if 1 <= n <= 3 and lines and lines <= 300 else 0
    score = 3 * unblocks + 2 * ruling + 2 * visible + size
    b.update({"unblocks": f"{waiting.get(r.content, 0)} {r.content} waiting" if unblocks else "nothing waiting",
              "ruling": RULING.search(r.paragraph).group(0) if ruling else "no dated ruling",
              "visible": bool(visible), "size": f"{n} file(s), about {gap.lines} lines", "score": score,
              "math": f"3x{unblocks} + 2x{ruling} + 2x{visible} + {size} = {score}"})
    return score, b


def rank(gaps, dirty, waiting, failed):
    """Every gap with its score, best first; skipped gaps last. Ties keep GDD order."""
    rows = [(priority_score(g, dirty, waiting, failed), k, g) for k, g in enumerate(gaps)]
    rows.sort(key=lambda r: (r[0][0] is None, -(r[0][0] or 0), r[1]))
    return [(score, b, g) for (score, b), _, g in rows]


# ---------------------------------------------------------------------------------------------------------------------
# The write step

WRITE_SYSTEM = """You are the Builder for Bottom Busters, a 2D arcade game in Unity 6.3 (C#, URP). You add one feature from the game design document (GDD) to the game's code.
Rules:
- New code goes in a new file. Change existing files only for the smallest hookup that calls it.
- Change only the files you are shown. Never rename, move or delete anything.
- It must compile in Unity 6.3: use UnityEngine, UnityEngine.UI, TMPro, System, System.Collections.Generic and the game's own classes and members you are shown, nothing invented.
- Find the menu canvas with UIKit.FindMenuCanvas(), never FindFirstObjectByType<Canvas>().
- A RectTransform made in code starts at sizeDelta (100, 100): set it to zero on stretch-anchored transforms.
- Sprite.Create takes SpriteMeshType.FullRect.
- No local UI ever waits on a network call.
- Anything a character draws during play must be recorded for replays, or replays won't show it.
- Never rename or move scenes or anything under Resources; Resources files load by string path.
Answer in this format and nothing else:
=== NEW FILE: Assets/Scripts/<Folder>/<Name>.cs
<the whole file>
=== EDIT: Assets/Scripts/<path>.cs
<<<<<<< FIND
<lines copied exactly from the file, without line numbers, enough of them to be unique>
=======
<the lines that replace them>
>>>>>>> REPLACE
=== END
Use as many NEW FILE and EDIT blocks as you need, and one or more FIND/REPLACE pairs in an EDIT block."""


@dataclasses.dataclass
class Edit:
    path: str
    find: str
    replace: str


@dataclasses.dataclass
class Change:
    new_files: dict
    edits: list


def words_of(req):
    """The feature's own longer words, for finding where it belongs in a big file."""
    return sorted({w for w in re.findall(r"[A-Za-z]{5,}", req.feature)})


def excerpt(text, line_nos, pad):
    """The lines around each of line_nos, as they are in the file (no line numbers: the practice run showed the cluster
    model copying numbers into its FIND text), overlapping ranges merged, gaps marked with '...'."""
    lines = text.splitlines()
    spans = sorted((max(1, n - pad), min(len(lines), n + pad)) for n in set(line_nos))
    merged = []
    for lo, hi in spans:
        if merged and lo <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    if not merged:
        merged = [[1, min(len(lines), 120)]]
    return "\n...\n".join("\n".join(lines[k - 1] for k in range(lo, hi + 1)) for lo, hi in merged)


def write_prompt(gap, index):
    r = gap.req
    parts = [f"The feature: {r.feature}", f"GDD Section {r.section}: \"{r.quote}\"", f"The GDD's paragraph:\n{r.paragraph}"]
    if gap.context:
        parts.append(f"The GDD's whole Section {r.section}, for the details the feature needs:\n{gap.context}")
    parts += [
             f"Why the code doesn't have it yet: {gap.why}"]
    for path in gap.targets:
        text = index.files[path]
        n = len(text.splitlines())
        if n <= 300 or (path == gap.targets[0] and n <= 1500):
            # The first target whole: an excerpt of CharacterSelect.cs left out where the tiles are built (checked
            # before the official run's write, 2026-11-15).
            body = text.rstrip("\n")
        else:
            at = [h.line_no for h in gap.hits if h.path == path]
            at += [h.line_no for h in codebase.search(codebase.Index(index.repo, {path: text}),
                                                      r.evidence + words_of(r), limit=8)]
            body = ("Its outline (signatures only):\n" + codebase.outline(index, path, numbered=False) +
                    "\n\nThe code around the places that matter, exactly as it is in the file:\n" + excerpt(text, at, 20))
        parts.append(f"--- {path} ({n} lines)\n{body}")
    if gap.new_file:
        parts.append(f"New file to create: {gap.new_file}")
    return "\n\n".join(parts)


LINE_NO = re.compile(r"^\d+: ?")


def unnumber(lines):
    """Takes off line numbers like '12: ' when every non-empty line has one (copied from a numbered listing)."""
    full = [l for l in lines if l.strip()]
    if full and all(LINE_NO.match(l) for l in full):
        return [LINE_NO.sub("", l, count=1) for l in lines]
    return lines


def strip_fences(text):
    """A new file's text without the wrappers models put around code: ``` fences, <file> tags, line numbers."""
    lines = text.strip("\n").splitlines()
    while lines and (lines[0].strip().startswith("```") or re.match(r"^\s*<file[^>]*>\s*$", lines[0])):
        lines = lines[1:]
    while lines and (lines[-1].strip().startswith("```") or re.match(r"^\s*</file>\s*$", lines[-1])):
        lines = lines[:-1]
    return "\n".join(unnumber(lines)) + "\n"


def parse_change(reply):
    """The NEW FILE and EDIT blocks of a write reply. Raises MalformedOutput when there are none."""
    reply = re.sub(r"<think>.*?</think>", "", reply, flags=re.S)
    new_files, edits = {}, []
    blocks = re.split(r"^=== (NEW FILE|EDIT|END)\b:?[ \t]*(.*)$", reply, flags=re.M)
    # blocks: [before, kind, path, body, kind, path, body, ...]
    for k in range(1, len(blocks) - 2, 3):
        kind, path, body = blocks[k], blocks[k + 1].strip().strip("`"), blocks[k + 2]
        path = path.replace("\\", "/")
        if kind == "NEW FILE" and path:
            new_files[path] = strip_fences(body)
        elif kind == "EDIT" and path:
            for m in re.finditer(r"^<<<<<<< FIND[ \t]*\n(.*?)^=======[ \t]*\n(.*?)^>>>>>>> REPLACE", body, re.M | re.S):
                find = "\n".join(unnumber(m.group(1).split("\n")))
                replace = "\n".join(unnumber(m.group(2).split("\n")))
                edits.append(Edit(path, find, replace))
    if not new_files and not edits:
        raise common.MalformedOutput("no NEW FILE or EDIT blocks in the reply")
    return Change(new_files, edits)


def _locate(text, find):
    """(start, end) of the one place `find` occurs in text, exactly or line by line ignoring indentation. None if it
    occurs zero times or more than once."""
    if text.count(find) == 1:
        start = text.index(find)
        return start, start + len(find)
    if text.count(find) > 1:
        return None
    want = [l.strip() for l in find.strip("\n").splitlines()]
    if not want or not any(want):
        return None
    lines = text.splitlines(keepends=True)
    found = []
    for i in range(len(lines) - len(want) + 1):
        if all(lines[i + j].strip() == want[j] for j in range(len(want))):
            found.append(i)
    if len(found) != 1:
        return None
    i = found[0]
    start = sum(len(l) for l in lines[:i])
    return start, start + sum(len(l) for l in lines[i:i + len(want)])


def apply(change, repo, dirty, mine=()):
    """Writes the change after checking all of it; nothing is written if any part is refused. Returns the backup:
    {path: original bytes, or None for a file this change created}."""
    repo = Path(repo)

    def check_path(path):
        if not (path.startswith(codebase.SCRIPTS + "/") and path.endswith(".cs")) or ".." in path:
            raise Refused(f"{path} is outside {codebase.SCRIPTS} or isn't a .cs file")
        if path in dirty and path not in mine:
            raise Refused(f"{path} has someone else's uncommitted changes")

    planned = {}
    for path, text in change.new_files.items():
        check_path(path)
        if (repo / path).exists():
            raise Refused(f"{path} already exists; change it with an EDIT block instead")
        planned[path] = text
    for e in change.edits:
        check_path(e.path)
        if e.path in planned and e.path in change.new_files:
            raise Refused(f"{e.path} is both a new file and an edit")
        if e.path not in planned:
            if not (repo / e.path).exists():
                raise Refused(f"{e.path} doesn't exist")
            planned[e.path] = (repo / e.path).read_bytes().decode("utf-8")
        text = planned[e.path]
        crlf = "\r\n" in text
        find = e.find.replace("\r\n", "\n")
        replace = e.replace.replace("\r\n", "\n")
        if crlf:
            find, replace = find.replace("\n", "\r\n"), replace.replace("\n", "\r\n")
        at = _locate(text, find)
        if at is None:
            raise Refused(f"in {e.path}, this FIND text isn't there exactly once:\n{e.find[:400]}")
        planned[e.path] = text[:at[0]] + replace + text[at[1]:]
    backup = {}
    for path in planned:
        p = repo / path
        backup[path] = p.read_bytes() if p.exists() else None
    for path, text in planned.items():
        p = repo / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.encode("utf-8"))
    return backup


def restore(backup, repo):
    """Puts back exactly what apply() changed: originals rewritten, files it created removed (with the .meta Unity made)."""
    repo = Path(repo)
    for path, original in backup.items():
        p = repo / path
        if original is None:
            for q in (p, Path(str(p) + ".meta")):
                if q.exists():
                    q.unlink()
        else:
            p.write_bytes(original)


def unity_running(repo):
    """True when a Unity process has this project open: the Editor, or another session's headless build."""
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='Unity.exe'\" | ForEach-Object { $_.CommandLine }")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout
    want = str(Path(repo).resolve()).replace("/", "\\").rstrip("\\").lower()
    for line in out.splitlines():
        m = re.search(r'-projectPath\s+("([^"]+)"|(\S+))', line, re.I)
        if m and (m.group(2) or m.group(3)).replace("/", "\\").rstrip("\\").lower() == want:
            return True
    return False


def build_check(repo, log, method=BUILD_METHOD, unity=UNITY, timeout=900):
    """Builds the game headless (docs/build.md). (ok, errors). ok only when the log says HeadlessBuild: Succeeded, or,
    with no method (a compile-only check), when Unity exits cleanly with no compiler errors."""
    if unity_running(repo):
        raise common.CrewStop(f"Unity has {repo} open (the Editor or another build); the Builder only builds when it's "
                              "closed. Close it and run again.")
    cmd = [str(unity), "-quit", "-batchmode", "-projectPath", str(repo), "-logFile", str(log)]
    if method:
        cmd += ["-executeMethod", method]
    try:
        proc = subprocess.run(cmd, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, [f"the build didn't finish in {timeout} seconds"]
    text = Path(log).read_text(encoding="utf-8", errors="replace") if Path(log).exists() else ""
    errors = sorted({l.strip() for l in text.splitlines() if re.search(r"error CS\d{4}", l)})
    ok = ("HeadlessBuild: Succeeded" in text) if method else (proc.returncode == 0 and not errors)
    if not ok and not errors:
        tail = [l for l in text.splitlines() if l.strip()][-15:]
        errors = ["no compiler errors in the log; its last lines:"] + tail
    return ok, errors


def claude_write(messages, timeout=900):
    """Claude Code, headless, no tools: the same prompt as the cluster model, one text answer back."""
    system = messages[0]["content"]
    convo = "\n\n".join(f"[{m['role']}]\n{m['content']}" for m in messages[1:])
    exe = shutil.which("claude")
    if not exe:
        raise common.CrewStop("Claude Code (claude) isn't on PATH")
    cmd = [exe, "-p", "--tools", "", "--output-format", "json", "--no-session-persistence", "--system-prompt", system]
    proc = subprocess.run(cmd, input=convo, capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    try:
        d = json.loads(proc.stdout)
    except ValueError:
        raise common.CrewStop(f"Claude Code didn't answer in JSON (exit {proc.returncode}): {proc.stderr[:300] or proc.stdout[:300]}")
    reply = d.get("result") or ""
    u = d.get("usage") or {}
    total = (u.get("input_tokens") or 0) + (u.get("output_tokens") or 0)
    common._record(AGENT, "claude-code", messages, reply, {"total_tokens": total})
    return reply


def cluster_write(messages):
    return common.ask(AGENT, messages, max_tokens=6000)


def diff_of(backup, repo):
    out = []
    for path, original in backup.items():
        new = (Path(repo) / path).read_text(encoding="utf-8").splitlines(keepends=True)
        old = original.decode("utf-8").splitlines(keepends=True) if original is not None else []
        out += difflib.unified_diff(old, new, f"a/{path}", f"b/{path}")
    return "".join(out)


def build_feature(gap, index, repo, dirty, mine, log_dir, writers, build=build_check, event=print):
    """Writes the gap's code, builds, and on a failed build sends the errors back. Each writer has two cheeks; the next
    writer takes over when they're gone. Returns (writer name, backup, reply) on a clean build. Raises TaskStopped with
    everything put back when every writer is out of cheeks."""
    base = [{"role": "system", "content": WRITE_SYSTEM}, {"role": "user", "content": write_prompt(gap, index)}]
    attempt = 0
    for name, write in writers:
        cheeks = common.Cheeks(name)
        messages = list(base)
        while cheeks.count > 0:
            attempt += 1
            reply = write(messages)
            backup = None
            try:
                change = parse_change(reply)
                backup = apply(change, repo, dirty, mine)
                ok, errors = build(repo, Path(log_dir) / f"build_{attempt:02}.log")
                if ok:
                    return name, backup, reply
                problem = "The build failed with these compiler errors:\n" + "\n".join(errors[:40])
            except common.MalformedOutput as e:
                problem = f"That answer couldn't be used: {e}"
            except BaseException:
                if backup:   # a stop mid-build (Unity opened, a timeout) never leaves a half-made change in the game
                    restore(backup, repo)
                raise
            if backup:
                restore(backup, repo)
            left = cheeks.pop()
            event(f"{name}, try {attempt}: {problem.splitlines()[0]} ({left} cheek(s) left)")
            messages = messages + [{"role": "assistant", "content": reply[-12000:]},
                                   {"role": "user", "content": problem + "\nThe files are back as they were. Write the "
                                                                         "whole answer again, fixed, in the same format."}]
        event(f"{name} is out of cheeks on {gap.req.id}")
    raise common.TaskStopped(f"{gap.req.id} ({gap.req.feature}): no writer got it to build; everything is put back")


# ---------------------------------------------------------------------------------------------------------------------
# The loop

def run(repo=REPO, gdd_path=gdd.SOURCE, run_id=None, dry=False, only=None, max_features=1, ask=common.ask_json,
        writers=None, build=build_check, submissions=common.SUBMISSIONS, work=common.WORK, workers=WORKERS):
    """scan -> requirements -> gaps -> scores -> write the top one -> build -> scan again. Returns the run's state."""
    repo = Path(repo)
    work = Path(work)
    old = _load(common.RUNS / run_id / "run.json") if run_id else None
    run_ = common.Run(run_id)
    if old:
        run_.state = old
        run_.state["status"] = "running"
        run_.save()
    run_.state.setdefault("builder", {"passes": [], "built": []})
    tokens_before = run_.state.get("tokens") or 0
    writers = writers if writers is not None else [("qwen3:30b-instruct", cluster_write), ("claude-code", claude_write)]
    failed_path = work / "builder_failed.json"
    failed = set(_load(failed_path) or [])
    waiting = waiting_counts(submissions)
    mine, built = [], 0
    try:
        sections = gdd.sections(gdd_path)
        index = codebase.scan(repo)
        run_.event(AGENT, f"read the GDD ({len(sections)} sections) and the code ({len(index.files)} C# files)")
        reqs, dropped = requirements(sections, class_names(index), ask, work / "builder_requirements.json", workers)
        _save(run_.dir / "requirements.json", [dataclasses.asdict(r) for r in reqs])
        _save(run_.dir / "dropped.json", dropped)
        run_.event(AGENT, f"{len(reqs)} requirements from the GDD; {len(dropped)} dropped by the checks")
        while True:
            n = len(run_.state["builder"]["passes"]) + 1
            index = codebase.scan(repo)
            dirty = codebase.dirty(repo) - set(mine)
            gaps, present = find_gaps(reqs, index, ask, work / "builder_second_looks.json", workers)
            ranked = rank(gaps, dirty, waiting, failed)
            _save(run_.dir / f"ranking_pass{n}.json", {"gaps": [b for _, b, _ in ranked], "present": present,
                                                        "dirty": sorted(dirty), "waiting": waiting})
            open_ids = [g.req.id for g in gaps]
            run_.state["builder"]["passes"].append({"pass": n, "gaps": len(gaps), "present": len(present),
                                                    "buildable": sum(1 for s, _, _ in ranked if s is not None)})
            for done in run_.state["builder"]["built"]:
                done["closed"] = done["id"] not in open_ids
            sure = sum(1 for p in present if p.get("confirmed"))
            run_.event(AGENT, f"pass {n}: {sure} requirements confirmed in the code, {len(present) - sure} the GDD calls "
                              f"built that the search couldn't confirm, {len(gaps)} gaps, "
                              f"{sum(1 for s, _, _ in ranked if s is not None)} it can build now")
            buildable = [(s, b, g) for s, b, g in ranked if s is not None]
            if not buildable:
                run_.state["status"] = "every requirement met" if not gaps else "nothing left it can build now"
                break
            if built >= max_features and not (only and built == 0):
                run_.state["status"] = f"built {built} feature(s), its limit for this run"
                break
            if only:
                pick = next(((s, b, g) for s, b, g in ranked if g.req.id == only), None)
                if pick and pick[0] is None and only in failed:   # David's approval overrides a past stop
                    s, b = priority_score(pick[2], dirty, waiting, failed - {only})
                    pick = (s, b, pick[2])
                unsure = next((p for p in present if p["id"] == only and not p.get("confirmed")), None)
                if not pick and unsure:
                    # The GDD calls it built, the search couldn't confirm it, and David checked: it isn't built. His
                    # approval makes it a gap; a second look names the files to change.
                    r = next(x for x in reqs if x.id == only)
                    a = second_look(index, r, codebase.search(index, r.evidence, limit=12), ask,
                                    avoid=[d for d in dirty if d.startswith(codebase.SCRIPTS + "/")])
                    targets, new = _clean_targets(index, a.get("targets"), a.get("new_file"))
                    # The files that hold the feature's own classes go first; the second look's picks only add to them
                    # (official run 20261115-161537: the second look aimed the names at Wearables.cs, the hats).
                    named = [p for p in declaring_files(index, r.evidence) if p not in dirty]
                    targets = (named + [t for t in targets if t not in named and t not in dirty])[:3]
                    try:
                        lines = int(a.get("lines") or 0)
                    except (TypeError, ValueError):
                        lines = 0
                    g = Gap(r, targets, new, codebase.search(index, r.evidence, limit=12),
                            "David checked: the GDD calls it built but it isn't in the game.", lines)
                    s, b = priority_score(g, dirty, waiting, failed - {only})   # his approval overrides a past stop
                    b["approved_by_david"] = "listed as unconfirmed; David approved building it"
                    pick = (s, b, g)
                    gaps.append(g)
                if not pick:
                    raise common.NeedsDavid(f"{only} isn't an open gap in this pass; see ranking_pass{n}.json")
                if pick[0] is None:
                    raise common.NeedsDavid(f"{only} is skipped: {pick[1]['skipped']}")
            else:
                pick = buildable[0]
            score, b, gap = pick
            run_.state["builder"]["pick"] = b
            if dry:
                run_.state["status"] = "waiting on David"
                run_.event(AGENT, f"would build {gap.req.id}, {gap.req.feature} ({b['math']}); waiting on David")
                break
            gap.context = next((s.text for s in sections if s.number == gap.req.section), "")
            run_.event(AGENT, f"building {gap.req.id}, {gap.req.feature} ({b['math']})")
            change_dir = run_.dir / f"change_{built + 1}"
            change_dir.mkdir(exist_ok=True)
            try:
                name, backup, reply = build_feature(gap, index, repo, dirty, mine, change_dir, writers, build,
                                                    lambda t: run_.event(AGENT, t))
            except common.TaskStopped:
                failed.add(gap.req.id)
                _save(failed_path, sorted(failed))
                raise
            mine += list(backup)
            (change_dir / "reply.txt").write_text(reply, encoding="utf-8")
            (change_dir / "change.diff").write_text(diff_of(backup, repo), encoding="utf-8")
            built += 1
            only = None
            run_.state["builder"]["built"].append({"id": gap.req.id, "feature": gap.req.feature, "writer": name,
                                                   "files": list(backup), "closed": None})
            run_.event(AGENT, f"{gap.req.id} built by {name} and the game builds; scanning again")
    except common.CrewStop as e:
        run_.state["status"] = f"stopped: {e}"
        run_.event(AGENT, f"stopped: {e}")
    finally:
        run_.state["tokens"] = tokens_before + common.usage.tokens.get(AGENT, 0)
        run_.save()
    return run_.state


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry", action="store_true", help="rank the gaps and name the pick; write nothing")
    ap.add_argument("--only", help="build exactly this requirement id (from a dry run's ranking)")
    ap.add_argument("--resume", help="continue this run id")
    ap.add_argument("--max", type=int, default=1, help="features to build in this run (default 1)")
    ap.add_argument("--repo", default=str(REPO))
    ap.add_argument("--gdd", default=str(gdd.SOURCE))
    a = ap.parse_args(argv)
    state = run(Path(a.repo), Path(a.gdd), a.resume, a.dry, a.only, a.max)
    print(json.dumps({"run": state["id"], "status": state["status"], "pick": state.get("builder", {}).get("pick"),
                      "built": state.get("builder", {}).get("built"), "tokens": state.get("tokens")}, indent=2))


if __name__ == "__main__":
    main()
