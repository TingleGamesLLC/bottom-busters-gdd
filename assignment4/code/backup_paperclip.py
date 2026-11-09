"""Copies Paperclip's backups to the NAS, so the board survives this PC's drive (gap analysis R1).

Paperclip writes one backup an hour and keeps the last 12 on this PC. This copies any the NAS doesn't have yet to
/volume1/backups/paperclip on the NAS, beside the other backups, checks every copy's size, and keeps all of them there (about 190 KB each).
The scheduled task "Paperclip NAS Backup" runs it every hour. The Foreman raises it with David when the last good copy is
over 3 hours old. Spends nothing.
usage: python backup_paperclip.py
"""
import json
import subprocess
import sys
import time
from pathlib import Path

LOCAL = Path.home() / ".paperclip" / "instances" / "default" / "data" / "backups"
REMOTE = "/volume1/backups/paperclip"   # a full path: ssh starts in gen's home, scp at /volume1 (2026-11-04)
STATUS = Path(__file__).with_name("paperclip_backup.json")
BEHIND_HOURS = 3
SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", "nas"]


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=600,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def on_nas(run):
    """File name to size, for every backup already on the NAS."""
    r = run(SSH + [f"mkdir -p {REMOTE} && cd {REMOTE} && stat -c '%s %n' -- *.sql.gz 2>/dev/null; true"])
    if r.returncode != 0:
        raise RuntimeError(f"couldn't list the NAS backups: {r.stderr.strip()[-300:]}")
    sizes = {}
    for line in r.stdout.splitlines():
        size, _, name = line.strip().partition(" ")
        if size.isdigit() and name:
            sizes[name] = int(size)
    return sizes


def backup(run=run):
    """Copies what the NAS lacks or holds cut short, checks the sizes, then records the time. Returns the names copied."""
    here = {p.name: p.stat().st_size for p in sorted(LOCAL.glob("*.sql.gz"))}
    there = on_nas(run)
    missing = [name for name in here if there.get(name) != here[name]]
    if missing:
        # Plain names from inside the folder: scp reads C:\... as a host called C (2026-11-04).
        r = run(["scp", "-q", "-o", "BatchMode=yes", *missing, f"nas:{REMOTE}/"], cwd=str(LOCAL))
        if r.returncode != 0:
            raise RuntimeError(f"scp to the NAS failed: {r.stderr.strip()[-300:]}")
        there = on_nas(run)
        bad = [name for name in missing if there.get(name) != here[name]]
        if bad:
            raise RuntimeError(f"these didn't reach the NAS whole: {', '.join(bad)}")
    STATUS.write_text(json.dumps({"newest": max(here) if here else None, "copied": len(missing),
                                  "at": time.strftime("%Y-%m-%d %H:%M"), "at_epoch": time.time()}), encoding="utf-8")
    return missing


def behind():
    """None while the last good copy is recent, else what's wrong (for the Foreman's pre-flight)."""
    status = json.loads(STATUS.read_text(encoding="utf-8")) if STATUS.exists() else {}
    if time.time() - status.get("at_epoch", 0) <= BEHIND_HOURS * 3600:
        return None
    return (f"Paperclip's backups haven't reached the NAS since {status.get('at', 'never')}: "
            f"the board is only on this PC's drive (run backup_paperclip.py to see why)")


if __name__ == "__main__":
    try:
        copied = backup()
        print(f"copied {len(copied)} backup(s) to nas:{REMOTE}")
    except RuntimeError as e:
        print(e)
        sys.exit(1)
