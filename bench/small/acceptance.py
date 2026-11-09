#!/usr/bin/env python3
"""Black-box acceptance test for bench/small/spec.md, the same for both runs.

Start the app first (follow its README), then:
  python3 ~/dev-team-setup/bench/small/acceptance.py http://localhost:8000
Standard library only.
"""
import json
import re
import sys
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"} if data else {})
    try:
        r = OPENER.open(req, timeout=10)
        return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()
    except urllib.error.URLError as e:
        if isinstance(e.reason, ConnectionRefusedError):
            sys.exit(f"Can't reach {BASE}: connection refused. Is the app running?")
        return 0, {}, b""
    except (TimeoutError, ConnectionError, OSError):
        return 0, {}, b""       # hung or dropped: counts as a failed check


results = []


def check(name, ok):
    results.append((name, bool(ok)))
    print(("✅ " if ok else "❌ ") + name)


st, _, body = call("POST", "/links", {"url": "https://example.com/page"})
created = json.loads(body) if st == 201 else {}
code = created.get("code", "")
check("POST /links valid URL → 201", st == 201)
check("code is 6 chars [A-Za-z0-9]", re.fullmatch(r"[A-Za-z0-9]{6}", code or ""))
check("short_url ends with the code", str(created.get("short_url", "")).endswith(code) and code)
st, _, _ = call("POST", "/links", {"url": "not a url"})
check("POST /links invalid URL → 422", st == 422)
st, headers, _ = call("GET", f"/{code}")
check("GET /{code} → 307 to the original URL", st == 307 and headers.get("Location") == "https://example.com/page")
call("GET", f"/{code}")
st, _, body = call("GET", f"/links/{code}/stats")
stats = json.loads(body) if st == 200 else {}
check("stats → 200 with url and created_at", st == 200 and stats.get("url") == "https://example.com/page" and stats.get("created_at"))
check("clicks counted (2 redirects → 2)", stats.get("clicks") == 2)
st, _, _ = call("GET", "/zzzzzz")
st2, _, _ = call("GET", "/links/zzzzzz/stats")
check("unknown code → 404 (redirect and stats)", st == 404 and st2 == 404)

passed = sum(ok for _, ok in results)
print(f"\nAcceptance: {passed}/{len(results)}")
print("Manual check: restart the app and open /links/" + code + "/stats; clicks should still be 2.")
sys.exit(0 if passed == len(results) else 1)
