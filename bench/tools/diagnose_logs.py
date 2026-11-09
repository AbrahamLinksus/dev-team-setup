#!/usr/bin/env python3
"""Print the structure and token fields of the latest Claude Code session log, without
any message text, so token_report.py can be checked against /cost.

Run from the folder you started `claude` in:
  python3 ~/dev-team-setup/bench/tools/diagnose_logs.py
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

cwd = Path.cwd().resolve()
pdir = Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(cwd))
if len(sys.argv) > 1:
    pdir = Path(sys.argv[1])
if not pdir.is_dir():
    sys.exit(f"no logs at {pdir}")

print("== files in project log dir")
for p in sorted(pdir.rglob("*")):
    if p.is_file():
        print(f"  {p.relative_to(pdir)}  {p.stat().st_size} bytes")

main = max(pdir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
print(f"\n== latest session: {main.name}")
types, usage_keys, other_usage = Counter(), Counter(), Counter()
rows = []
for i, line in enumerate(main.open(encoding="utf-8", errors="replace")):
    try:
        d = json.loads(line)
    except ValueError:
        continue
    types[d.get("type")] += 1
    msg = d.get("message") if isinstance(d.get("message"), dict) else {}
    u = msg.get("usage") if isinstance(msg, dict) else None
    if d.get("type") != "assistant":
        blob = json.dumps(d)
        for k in ("usage", "costUSD", "input_tokens", "cache_read_input_tokens"):
            if f'"{k}"' in blob:
                other_usage[f"{d.get('type')}:{k}"] += 1
        continue
    if not u:
        continue
    usage_keys.update(u.keys())
    its = u.get("iterations")
    rows.append({
        "line": i, "id": str(msg.get("id"))[-8:], "req": str(d.get("requestId"))[-8:],
        "model": msg.get("model"), "side": d.get("isSidechain"),
        "in": u.get("input_tokens"), "cw": u.get("cache_creation_input_tokens"),
        "cr": u.get("cache_read_input_tokens"), "out": u.get("output_tokens"),
        "iters": len(its) if isinstance(its, list) else its,
        "blocks": [b.get("type") for b in msg.get("content", []) if isinstance(b, dict)],
        "top_keys": sorted(k for k in d if k not in ("message", "uuid", "parentUuid", "cwd", "sessionId", "version", "gitBranch")),
    })

print("line types:", dict(types))
print("usage keys seen:", dict(usage_keys))
print("usage-like fields on non-assistant lines:", dict(other_usage) or "none")
print("\n== assistant lines (no text)")
print("line | msg id | req id | model | side | in | cw | cr | out | iters | blocks")
for r in rows:
    print(f"{r['line']} | {r['id']} | {r['req']} | {r['model']} | {r['side']} | {r['in']} | {r['cw']} | {r['cr']} | {r['out']} | {r['iters']} | {','.join(map(str, r['blocks']))}")
if rows:
    print("top-level keys on assistant lines:", rows[0]["top_keys"])

# iteration detail, if present
for line in main.open(encoding="utf-8", errors="replace"):
    try:
        d = json.loads(line)
    except ValueError:
        continue
    u = (d.get("message") or {}).get("usage") if isinstance(d.get("message"), dict) else None
    if u and isinstance(u.get("iterations"), list) and u["iterations"]:
        print("\n== example iterations entry:", json.dumps(u["iterations"])[:600])
        break


def scrub(v, depth=0):
    """Keep structure and numbers; cut any string longer than 40 chars (no message text)."""
    if isinstance(v, dict):
        return {k: scrub(x, depth + 1) for k, x in v.items()} if depth < 6 else "{...}"
    if isinstance(v, list):
        return [scrub(x, depth + 1) for x in v[:5]] + (["..."] if len(v) > 5 else [])
    if isinstance(v, str) and len(v) > 40:
        return f"<{len(v)} chars>"
    return v


print("\n== keys per line type")
keys_by_type, samples = {}, {}
for line in main.open(encoding="utf-8", errors="replace"):
    try:
        d = json.loads(line)
    except ValueError:
        continue
    t = d.get("type")
    keys_by_type.setdefault(t, set()).update(d.keys())
    if t in ("cost-state", "api-request", "api-request-shape", "system"):
        samples.setdefault(t, []).append(d)
for t, ks in sorted(keys_by_type.items(), key=lambda kv: str(kv[0])):
    print(f"  {t}: {sorted(ks)}")

print("\n== cost-state lines (all)")
for d in samples.get("cost-state", []):
    print(json.dumps(scrub(d), indent=1))
for t in ("api-request", "api-request-shape", "system"):
    if samples.get(t):
        print(f"\n== {t}: first and last line")
        print(json.dumps(scrub(samples[t][0]), indent=1)[:1500])
        if len(samples[t]) > 1:
            print(json.dumps(scrub(samples[t][-1]), indent=1)[:1500])


def total(key_fn):
    seen = {}
    for r in rows:
        seen[key_fn(r)] = r
    t = Counter()
    for r in seen.values():
        for k in ("in", "cw", "cr", "out"):
            t[k] += int(r[k] or 0)
    return len(seen), dict(t)


print("\n== totals by counting method")
print("every line        :", total(lambda r: r["line"]))
print("unique message id :", total(lambda r: r["id"]))
print("unique request id :", total(lambda r: r["req"]))
