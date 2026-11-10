"""In-memory reference server for the production spec (validates bench.py's acceptance test).
BREAK=<name> breaks one behaviour; PORT sets the port."""
import json, re, secrets, time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import socketserver
from urllib.parse import urlparse, parse_qs
users, tokens, projects, members, issues, comments, fails = {}, {}, {}, set(), {}, {}, {}
seq = {"u": 0, "p": 0, "i": 0, "c": 0}
BREAK = __import__("os").environ.get("BREAK", "")
def nid(k): seq[k] += 1; return seq[k]
def now(): return datetime.now(timezone.utc).isoformat()
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def out(self, st, body=None):
        b = json.dumps(body).encode() if body is not None else b""
        self.send_response(st); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n)) if n else {}
    def me(self):
        h = self.headers.get("Authorization", "")
        return tokens.get(h[7:]) if h.startswith("Bearer ") else None
    def can(self, uid, pid): return pid in projects and (projects[pid]["owner_id"] == uid or (pid, uid) in members)
    def route(self, m):
        u = urlparse(self.path); p, q = u.path, parse_qs(u.query)
        if m == "GET" and p == "/health": return self.out(200, {"status": "ok"})
        if m == "POST" and p == "/auth/register":
            d = self.body(); e, pw = d.get("email", ""), d.get("password", "")
            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", e) or len(pw) < 8: return self.out(422, {})
            if any(x["email"] == e for x in users.values()): return self.out(409, {})
            i = nid("u"); users[i] = {"id": i, "email": e, "pw": pw}; return self.out(201, {"id": i, "email": e})
        if m == "POST" and p == "/auth/login":
            d = self.body(); e = d.get("email", ""); f = [t for t in fails.get(e, []) if time.time() - t < 60]
            if len(f) >= 5 and BREAK != "ratelimit": return self.out(429, {})
            x = next((x for x in users.values() if x["email"] == e and x["pw"] == d.get("password")), None)
            if not x: fails[e] = f + [time.time()]; return self.out(401, {})
            t = secrets.token_hex(8); tokens[t] = x["id"]; return self.out(200, {"access_token": t, "token_type": "bearer"})
        uid = self.me()
        if uid is None: return self.out(401, {})
        if p == "/projects":
            if m == "POST":
                i = nid("p"); projects[i] = {"id": i, "name": self.body()["name"], "owner_id": uid}; return self.out(201, projects[i])
            return self.out(200, [x for x in projects.values() if self.can(uid, x["id"])])
        mm = re.fullmatch(r"/projects/(\d+)/(members|issues)", p)
        if mm:
            pid = int(mm.group(1))
            if not self.can(uid, pid): return self.out(404, {})
            if mm.group(2) == "members":
                if projects[pid]["owner_id"] != uid: return self.out(403, {})
                em = self.body().get("email"); x = next((x for x in users.values() if x["email"] == em), None)
                if not x: return self.out(404, {})
                members.add((pid, x["id"])); return self.out(201, {"user_id": x["id"], "project_id": pid})
            if m == "POST":
                d = self.body()
                if not d.get("title"): return self.out(422, {})
                a = d.get("assignee_id")
                if a is not None and not self.can(a, pid): return self.out(422, {})
                i = nid("i"); issues[i] = {"id": i, "project_id": pid, "title": d["title"], "description": d.get("description", ""),
                    "status": "open", "priority": d.get("priority", "medium"), "assignee_id": a, "created_at": now(), "updated_at": now()}
                return self.out(201, issues[i])
            xs = [x for x in issues.values() if x["project_id"] == pid]
            if "status" in q: xs = [x for x in xs if x["status"] == q["status"][0]]
            if "priority" in q: xs = [x for x in xs if x["priority"] == q["priority"][0]]
            xs = sorted(xs, key=lambda x: x["id"], reverse=BREAK != "order")
            pg, ps = int(q.get("page", ["1"])[0]), min(int(q.get("page_size", ["20"])[0]), 100)
            return self.out(200, {"items": xs[(pg - 1) * ps: pg * ps], "total": len(xs), "page": pg, "page_size": ps})
        mi = re.fullmatch(r"/issues/(\d+)(/comments)?", p)
        if mi:
            i = int(mi.group(1)); x = issues.get(i)
            if not x or not self.can(uid, x["project_id"]): return self.out(404, {})
            if mi.group(2) and BREAK == "hang" and m == "GET": time.sleep(20)
            if mi.group(2):
                if m == "POST":
                    b = self.body().get("body", "")
                    if not b: return self.out(422, {})
                    c = nid("c"); comments[c] = {"id": c, "issue_id": i, "author_id": uid, "body": b, "created_at": now()}; return self.out(201, comments[c])
                return self.out(200, [c for c in comments.values() if c["issue_id"] == i])
            if m == "PATCH":
                d = self.body()
                if d.get("status", "open") not in ("open", "in_progress", "done"): return self.out(422, {})
                x.update(d); x["updated_at"] = now(); return self.out(200, x)
            if m == "DELETE":
                if projects[x["project_id"]]["owner_id"] != uid and BREAK != "delete": return self.out(403, {})
                del issues[i]; return self.out(204)
        return self.out(404, {})
    def do_GET(self): self.route("GET")
    def do_POST(self): self.route("POST")
    def do_PATCH(self): self.route("PATCH")
    def do_DELETE(self): self.route("DELETE")
class Server(ThreadingHTTPServer):
    # No reverse-DNS lookup on start: HTTPServer.server_bind calls socket.getfqdn(), which can stall
    # for seconds on CI machines (macOS) before the server starts listening.
    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = "127.0.0.1", self.server_address[1]


Server(("127.0.0.1", int(__import__("os").environ.get("PORT", "8766"))), H).serve_forever()
