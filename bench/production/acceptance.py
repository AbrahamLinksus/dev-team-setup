#!/usr/bin/env python3
"""Black-box acceptance test for bench/production/spec.md, the same for both runs.

Start the API first (follow its README; port 8000, fresh database), then:
  python3 ~/dev-team-setup/bench/production/acceptance.py http://localhost:8000
Standard library only. Uses fresh random emails, so it can be re-run.
"""
import json
import secrets
import sys
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
RUN = secrets.token_hex(4)
results: list[tuple[str, bool]] = []


def call(method: str, path: str, body=None, token: str | None = None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw) if raw else None
        except ValueError:
            return e.code, None
    except urllib.error.URLError as e:
        if isinstance(e.reason, ConnectionRefusedError):
            sys.exit(f"Can't reach {BASE}: connection refused. Is the API running?")
        return 0, None          # counts as a failed check, the run continues
    except (TimeoutError, ConnectionError, OSError):
        return 0, None          # the server hung or dropped the connection on this request


def check(name: str, ok) -> bool:
    results.append((name, bool(ok)))
    print(("✅ " if ok else "❌ ") + name)
    return bool(ok)


def user(tag: str):
    email = f"{tag}-{RUN}@example.com"
    call("POST", "/auth/register", {"email": email, "password": "correct-horse-1"})
    st, body = call("POST", "/auth/login", {"email": email, "password": "correct-horse-1"})
    return email, (body or {}).get("access_token") if st == 200 else None


# ---- health + accounts ---------------------------------------------------------------
st, body = call("GET", "/health")
check("GET /health → 200 {status: ok}", st == 200 and (body or {}).get("status") == "ok")

email_a = f"alice-{RUN}@example.com"
st, body = call("POST", "/auth/register", {"email": email_a, "password": "correct-horse-1"})
check("register → 201 with id and email", st == 201 and (body or {}).get("email") == email_a and "id" in (body or {}))
st, _ = call("POST", "/auth/register", {"email": email_a, "password": "correct-horse-1"})
check("register same email → 409", st == 409)
st, _ = call("POST", "/auth/register", {"email": f"short-{RUN}@example.com", "password": "short"})
st2, _ = call("POST", "/auth/register", {"email": "not-an-email", "password": "correct-horse-1"})
check("register bad password / bad email → 422", st == 422 and st2 == 422)
st, body = call("POST", "/auth/login", {"email": email_a, "password": "correct-horse-1"})
token_a = (body or {}).get("access_token")
check("login → 200 bearer token", st == 200 and token_a and (body or {}).get("token_type", "").lower() == "bearer")
st, _ = call("POST", "/auth/login", {"email": email_a, "password": "wrong-password"})
check("login wrong password → 401", st == 401)
st, _ = call("GET", "/projects")
st2, _ = call("GET", "/projects", token="not-a-real-token")
check("no or invalid token → 401", st == 401 and st2 == 401)

# ---- projects + membership -----------------------------------------------------------
email_b, token_b = user("bob")
email_c, token_c = user("carol")
st, proj = call("POST", "/projects", {"name": f"Bench {RUN}"}, token_a)
pid = (proj or {}).get("id")
check("create project → 201, creator is owner", st == 201 and pid is not None and (proj or {}).get("owner_id") is not None)
st, lst = call("GET", "/projects", token=token_a)
check("owner sees project in GET /projects", st == 200 and any(p.get("id") == pid for p in (lst or [])))
st, _ = call("GET", f"/projects/{pid}/issues", token=token_b)
check("non-member → 404 on project issues", st == 404)
st, _ = call("POST", f"/projects/{pid}/members", {"email": email_b}, token_a)
check("owner adds member → 201", st == 201)
st, _ = call("POST", f"/projects/{pid}/members", {"email": f"ghost-{RUN}@example.com"}, token_a)
check("add unknown email → 404", st == 404)
st, _ = call("POST", f"/projects/{pid}/members", {"email": email_c}, token_b)
check("member adds member → 403", st == 403)
st, lst = call("GET", "/projects", token=token_b)
check("member sees project in GET /projects", st == 200 and any(p.get("id") == pid for p in (lst or [])))

# ---- issues --------------------------------------------------------------------------
st, issue = call("POST", f"/projects/{pid}/issues", {"title": "First bug", "description": "It breaks"}, token_b)
iid = (issue or {}).get("id")
check("member creates issue → 201, open, medium", st == 201 and (issue or {}).get("status") == "open"
      and (issue or {}).get("priority") == "medium")
st, _ = call("POST", f"/projects/{pid}/issues", {"title": ""}, token_a)
check("empty title → 422", st == 422)
st, _ = call("POST", f"/projects/{pid}/issues", {"title": "Assigned", "assignee_id": 10**9}, token_a)
check("assignee who isn't a member → 422", st == 422)
for n in range(3):
    call("POST", f"/projects/{pid}/issues", {"title": f"Issue {n}", "priority": "high"}, token_a)
st, page = call("GET", f"/projects/{pid}/issues?page=1&page_size=2", token=token_a)
items = (page or {}).get("items", [])
check("list is paginated (items, total, page, page_size)", st == 200 and len(items) == 2 and (page or {}).get("total") == 4
      and (page or {}).get("page") == 1 and (page or {}).get("page_size") == 2)
check("list is newest first", len(items) == 2 and items[0].get("title") == "Issue 2")
st, page = call("GET", f"/projects/{pid}/issues?priority=high", token=token_a)
check("filter by priority", st == 200 and (page or {}).get("total") == 3)
st, upd = call("PATCH", f"/issues/{iid}", {"status": "in_progress"}, token_b)
check("PATCH status → 200 in_progress", st == 200 and (upd or {}).get("status") == "in_progress")
st, _ = call("PATCH", f"/issues/{iid}", {"status": "finished"}, token_b)
check("PATCH invalid status → 422", st == 422)
st, page = call("GET", f"/projects/{pid}/issues?status=in_progress", token=token_a)
check("filter by status", st == 200 and (page or {}).get("total") == 1)
st, _ = call("PATCH", f"/issues/{iid}", {"status": "done"}, token_c)
check("non-member PATCH → 404", st == 404)

# ---- comments ------------------------------------------------------------------------
st, c1 = call("POST", f"/issues/{iid}/comments", {"body": "Looking into it"}, token_a)
call("POST", f"/issues/{iid}/comments", {"body": "Fixed locally"}, token_b)
st2, _ = call("POST", f"/issues/{iid}/comments", {"body": ""}, token_a)
check("comment → 201; empty body → 422", st == 201 and (c1 or {}).get("body") == "Looking into it" and st2 == 422)
st, cs = call("GET", f"/issues/{iid}/comments", token=token_b)
check("comments listed oldest first", st == 200 and [c.get("body") for c in (cs or [])] == ["Looking into it", "Fixed locally"])

# ---- delete permissions --------------------------------------------------------------
st, _ = call("DELETE", f"/issues/{iid}", token=token_b)
check("member DELETE → 403", st == 403)
st, _ = call("DELETE", f"/issues/{iid}", token=token_a)
st2, page = call("GET", f"/projects/{pid}/issues", token=token_a)
check("owner DELETE → 204 and it's gone", st == 204 and (page or {}).get("total") == 3)

# ---- login rate limit (last: it locks this email for a minute) -----------------------
codes = [call("POST", "/auth/login", {"email": email_c, "password": "wrong-password"})[0] for _ in range(5)]
st, _ = call("POST", "/auth/login", {"email": email_c, "password": "correct-horse-1"})
check("5 failed logins → 6th attempt 429", codes == [401] * 5 and st == 429)

passed = sum(ok for _, ok in results)
print(f"\nAcceptance: {passed}/{len(results)}")
sys.exit(0 if passed == len(results) else 1)
