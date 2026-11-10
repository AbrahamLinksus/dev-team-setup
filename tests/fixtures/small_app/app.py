"""Tiny link shortener that follows bench.py's small spec (stdlib only, for tests)."""
import json, os, random, re, sqlite3, string
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
import socketserver
from pathlib import Path

db = sqlite3.connect(Path(__file__).with_name("links.db"), check_same_thread=False)
db.execute("create table if not exists l(code text primary key, url text, clicks int, created text)")
PORT = int(os.environ.get("PORT", "8000"))


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send(self, st, body=None, loc=None):
        self.send_response(st)
        if loc: self.send_header("Location", loc)
        b = json.dumps(body).encode() if body is not None else b""
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if not re.match(r"https?://\S+\.\S+", d.get("url", "")): return self.send(422, {"detail": "bad url"})
        c = "".join(random.choices(string.ascii_letters + string.digits, k=6))
        db.execute("insert into l values(?,?,0,?)", (c, d["url"], datetime.now(timezone.utc).isoformat())); db.commit()
        self.send(201, {"code": c, "short_url": f"http://localhost:{PORT}/{c}"})

    def do_GET(self):
        m = re.fullmatch(r"/links/(\w+)/stats", self.path)
        code = m.group(1) if m else self.path[1:]
        r = db.execute("select url, clicks, created from l where code=?", (code,)).fetchone()
        if not r: return self.send(404, {"detail": "not found"})
        if m: return self.send(200, {"url": r[0], "clicks": r[1], "created_at": r[2]})
        db.execute("update l set clicks=clicks+1 where code=?", (code,)); db.commit(); self.send(307, loc=r[0])


class Server(HTTPServer):
    # No reverse-DNS lookup on start: HTTPServer.server_bind calls socket.getfqdn(), which can stall
    # for seconds on CI machines (macOS) before the server starts listening.
    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = "127.0.0.1", self.server_address[1]


Server(("127.0.0.1", PORT), H).serve_forever()
