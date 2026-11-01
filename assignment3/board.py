"""The Trello board "Bottom Busters Agent Crew", top to bottom. The card order is David's priority list.

With .trello_key present it talks to Trello directly. Without it, it works from board.json (a copy of the board) and
queues each change in board_outbox.jsonl, to be applied through the Trello connector.
"""
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
KEY_FILE = HERE / ".trello_key"
COPY_FILE = HERE / "board.json"
OUTBOX = HERE / "board_outbox.jsonl"

BOARD = "MWTqyVmK"
BACKLOG, LEASED, REVIEW, PLAYTEST, DONE = "Backlog", "In Progress (leased)", "Review", "Your Playtest", "Done"


class TrelloBoard:
    def __init__(self, creds):
        self.auth = {"key": creds["key"], "token": creds["token"]}
        self.lists = {l["name"]: l["id"] for l in self._call("GET", f"/boards/{BOARD}/lists")}

    def _call(self, method, path, params=None):
        query = urllib.parse.urlencode({**self.auth, **(params or {})})
        req = urllib.request.Request(f"https://api.trello.com/1{path}?{query}", method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            # The URL holds the token, so only the status goes in the error.
            raise RuntimeError(f"Trello answered HTTP {e.code} on {method} {path}") from None

    def cards(self, list_name):
        return [{"id": c["id"], "name": c["name"], "desc": c.get("desc", ""), "url": c.get("shortUrl"), "list": list_name}
                for c in self._call("GET", f"/lists/{self.lists[list_name]}/cards")]

    def move(self, card, list_name):
        self._call("PUT", f"/cards/{card['id']}", {"idList": self.lists[list_name], "pos": "bottom"})
        card["list"] = list_name

    def comment(self, card, text):
        self._call("POST", f"/cards/{card['id']}/actions/comments", {"text": text[:16000]})

    def archive(self, card):
        self._call("PUT", f"/cards/{card['id']}", {"closed": "true"})


class CopyBoard:
    """board.json holds {"lists": {name: [card, ...]}}. Changes apply to the copy and queue for the connector."""

    def __init__(self):
        self.data = json.loads(COPY_FILE.read_text(encoding="utf-8"))

    def _queue(self, op):
        with OUTBOX.open("a", encoding="utf-8") as f:
            f.write(json.dumps(op) + "\n")
        COPY_FILE.write_text(json.dumps(self.data, indent=1), encoding="utf-8")

    def cards(self, list_name):
        return [dict(c, list=list_name) for c in self.data["lists"].get(list_name, [])]

    def move(self, card, list_name):
        for cards in self.data["lists"].values():
            cards[:] = [c for c in cards if c["id"] != card["id"]]
        self.data["lists"].setdefault(list_name, []).append({k: card[k] for k in ("id", "name", "desc", "url")})
        card["list"] = list_name
        self._queue({"op": "move", "card": card["id"], "name": card["name"], "list": list_name})

    def comment(self, card, text):
        self._queue({"op": "comment", "card": card["id"], "name": card["name"], "text": text})

    def archive(self, card):
        for cards in self.data["lists"].values():
            cards[:] = [c for c in cards if c["id"] != card["id"]]
        self._queue({"op": "archive", "card": card["id"], "name": card["name"]})


def open_board():
    if KEY_FILE.exists():
        creds = json.loads(KEY_FILE.read_text(encoding="ascii"))
        if creds.get("key") and creds.get("token"):
            return TrelloBoard(creds)
    return CopyBoard()
