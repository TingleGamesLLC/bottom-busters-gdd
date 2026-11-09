"""One-time setup: catch the Trello key and token from the browser and save them to .trello_key, without printing them.

The browser page opens http://127.0.0.1:8765/#key=... and then /#token=...; the fragment never leaves the browser
until this page's script posts it here. Listens on loopback only and exits once it has both.
"""
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

KEY_FILE = Path(__file__).with_name(".trello_key")
AUTHORIZE = ("https://trello.com/1/authorize?expiration=never&scope=read,write&response_type=token"
             "&name=BBUST%20Agent%20Crew&key=")
PAGE = """<!doctype html><title>BBUST crew setup</title><body>Saving...<script>
const [field, value] = location.hash.slice(1).split("=");
history.replaceState(null, "", "/");
fetch("/save", {method: "POST", body: JSON.stringify({field, value})}).then(r => r.json()).then(d => {
  document.body.textContent = d.next ? "Saved. Going to Trello..." : "Saved. You can close this tab.";
  if (d.next) location.replace(d.next);
});
</script>"""
saved = {}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = PAGE.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if d.get("field") in ("key", "token") and d.get("value"):
            saved[d["field"]] = d["value"]
            KEY_FILE.write_text(json.dumps(saved), encoding="ascii")
            os.chmod(KEY_FILE, 0o600)
            print("saved", d["field"], flush=True)
        body = json.dumps({"next": AUTHORIZE + saved["key"] if d.get("field") == "key" and "key" in saved else None}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # the request log would not hold the values, but nothing here needs logging


server = HTTPServer(("127.0.0.1", 8765), Handler)
while not ({"key", "token"} <= saved.keys()):
    server.handle_request()
print("done: both saved to", KEY_FILE, flush=True)
