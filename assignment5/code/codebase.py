"""The game's code, as the Builder sees it (Assignment #5): every C# file under Assets/Scripts, a whole-word search over them,
a short outline of one file for a prompt, and the files another session has changed and not committed.

Plain code, no model. Paths are relative to the repo with forward slashes, e.g. Assets/Scripts/UI/CharacterSelect.cs.
"""
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

SCRIPTS = "Assets/Scripts"


@dataclass
class Hit:
    path: str
    line_no: int
    line: str


@dataclass
class Index:
    repo: Path
    files: dict   # relative path -> text


def scan(repo, sub=SCRIPTS):
    """Every .cs file under repo/sub, read fresh."""
    repo = Path(repo)
    files = {}
    for p in sorted((repo / sub).rglob("*.cs")):
        files[p.relative_to(repo).as_posix()] = p.read_text(encoding="utf-8", errors="replace")
    return Index(repo, files)


def _pattern(term):
    term = term.strip().strip('"')
    if not term:
        return None
    left = r"\b" if re.match(r"\w", term) else ""
    right = r"\b" if re.search(r"\w$", term) else ""
    return re.compile(left + re.escape(term) + right, re.I)


def search(index, terms, limit=20):
    """Lines that hold any of the terms, whole words, any case. Files that match more distinct terms come first; at most
    `limit` hits."""
    pats = [(t, _pattern(t)) for t in terms]
    pats = [(t, p) for t, p in pats if p]
    ranked = []
    for path, text in index.files.items():
        found, hits = set(), []
        for n, line in enumerate(text.splitlines(), 1):
            for t, p in pats:
                if p.search(line):
                    found.add(t.lower())
                    hits.append(Hit(path, n, line.strip()))
                    break
        if hits:
            ranked.append((len(found), path, hits))
    ranked.sort(key=lambda r: (-r[0], r[1]))
    out = []
    for _, _, hits in ranked:
        out.extend(hits)
    return out[:limit]


def terms_found(index, terms):
    """How many of the terms appear anywhere in the code."""
    count = 0
    for t in terms:
        p = _pattern(t)
        if p and any(p.search(text) for text in index.files.values()):
            count += 1
    return count


SIGNATURE = re.compile(r"^\s*(?:\[[^\]]*\]\s*)*(?:(?:public|private|protected|internal|static|readonly|const|sealed|abstract|"
                       r"virtual|override|partial|async|extern|new)\s+)+[\w<>\[\],.?\s]+[\w>\]]\s*(?:\(|=|;|\{|=>)|"
                       r"^\s*(?:(?:public|private|protected|internal|static|sealed|abstract|partial)\s+)*"
                       r"(?:class|struct|enum|interface)\s+\w+")


def outline(index, path, numbered=True):
    """The file's usings, type declarations and member signatures, one line each, with line numbers unless numbered is
    False. No method bodies."""
    keep = []
    for n, line in enumerate(index.files[path].splitlines(), 1):
        s = line.rstrip()
        if s.lstrip().startswith("using ") or SIGNATURE.match(s):
            keep.append(f"{n}: {s.strip()}" if numbered else s.strip())
    return "\n".join(keep)


def around(index, path, line_no, before=6, after=6):
    """The lines around one line of a file, numbered."""
    lines = index.files[path].splitlines()
    lo, hi = max(1, line_no - before), min(len(lines), line_no + after)
    return "\n".join(f"{n}: {lines[n - 1]}" for n in range(lo, hi + 1))


def dirty(repo):
    """Paths git shows as modified, added, deleted, renamed or untracked, relative to the repo. A file here belongs to
    another session's work in progress."""
    out = subprocess.run(["git", "-C", str(repo), "status", "--porcelain=v1", "-z", "-uall"],
                         capture_output=True, check=True).stdout.decode("utf-8", "replace")
    paths, parts, i = set(), out.split("\0"), 0
    while i < len(parts):
        entry = parts[i]
        i += 1
        if len(entry) < 4:
            continue
        status, path = entry[:2], entry[3:]
        paths.add(path)
        if "R" in status or "C" in status:   # a rename carries its old path next
            if i < len(parts):
                paths.add(parts[i])
            i += 1
    return paths
