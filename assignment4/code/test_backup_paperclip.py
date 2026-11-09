"""Paperclip's backups to the NAS, on a stand-in NAS: copies only what the NAS lacks, checks every copy's size, and says
when the NAS copy has fallen behind. Touches neither the NAS nor Paperclip.
usage: python test_backup_paperclip.py
"""
import json
import tempfile
import time
from pathlib import Path

import backup_paperclip as bp


class Nas:
    """A stand-in for ssh and scp to the NAS: a dict of file name to size."""

    def __init__(self, files=None, short=()):
        self.files, self.short, self.copied = dict(files or {}), set(short), []

    def __call__(self, cmd, cwd=None):
        class Done:
            returncode, stdout, stderr = 0, "", ""
        done = Done()
        if cmd[0] == "ssh":
            done.stdout = "".join(f"{size} {name}\n" for name, size in sorted(self.files.items()))
        else:   # scp: every source but the last argument lands on the NAS
            for src in cmd[cmd.index("-q") + 3:-1]:
                assert ":" not in src, f"scp reads {src} as host:path"   # 2026-11-04: C:\... went to a host called C
                p = Path(cwd) / src
                self.copied.append(p.name)
                self.files[p.name] = p.stat().st_size - (1 if p.name in self.short else 0)
        return done


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        bp.LOCAL, bp.STATUS = tmp / "backups", tmp / "status.json"
        bp.LOCAL.mkdir()
        for k, size in enumerate((100, 200, 300)):
            (bp.LOCAL / f"paperclip-2026110{k}-0334.sql.gz").write_bytes(b"x" * size)
        names = sorted(p.name for p in bp.LOCAL.iterdir())

        assert bp.REMOTE.startswith("/volume1/"), bp.REMOTE   # 2026-11-04: ssh starts in gen's home, scp at /volume1
        print("The NAS folder is a full path, so the listing and the copy look at the same place")
        nas = Nas({names[0]: 100, names[1]: 150})   # one already there, one cut short
        assert bp.backup(nas) == names[1:] and nas.copied == names[1:], nas.copied
        assert nas.files == {names[0]: 100, names[1]: 200, names[2]: 300}, nas.files
        print("Copies only what the NAS lacks, and redoes a copy that was cut short")
        status = json.loads(bp.STATUS.read_text(encoding="utf-8"))
        assert status["newest"] == names[2] and abs(status["at_epoch"] - time.time()) < 60, status
        assert bp.backup(nas) == [] and nas.copied == names[1:]
        print("Nothing new: nothing copied, and the status still moves on")

        bp.STATUS.unlink()
        try:
            bp.backup(Nas({}, short={names[2]}))
            raise AssertionError("a copy whose size doesn't match should fail")
        except RuntimeError as e:
            assert names[2] in str(e), e
        assert not bp.STATUS.exists()
        print("A copy that doesn't match its size fails, and the status isn't moved on")

        assert "never" in bp.behind()
        bp.STATUS.write_text(json.dumps({"newest": names[2], "at": "earlier", "at_epoch": time.time() - 4 * 3600}), encoding="utf-8")
        assert "earlier" in bp.behind()
        bp.STATUS.write_text(json.dumps({"newest": names[2], "at": "now", "at_epoch": time.time() - 600}), encoding="utf-8")
        assert bp.behind() is None
        print("Behind when the last good copy is over 3 hours old or never happened; fine otherwise")
    print("all passed")


if __name__ == "__main__":
    main()
