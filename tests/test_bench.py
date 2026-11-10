"""bench.py tests.

- Token/cost/intervention measurement on synthetic and real-shaped logs.
- Acceptance tests against reference servers (correct and deliberately broken).
- End to end: `run small normal`, `run small plugin`, `overhead`, `report`, `clean`, driven
  by a fake `claude` (tests/fixtures/fake_claude.py) that writes real-format session logs.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "bench.py"
FIX = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(ROOT))
import bench  # noqa: E402


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def usage(i=0, cw=0, cr=0, o=0):
    return {"input_tokens": i, "cache_creation_input_tokens": cw, "cache_read_input_tokens": cr, "output_tokens": o}


class MeasureTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, lines):
        p = self.d / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(json.dumps(x) for x in lines) + "\n")

    def test_real_baseline_numbers(self):
        """Numbers from the first real run (Claude Code 2.1.312): replies miss background calls."""
        a = lambda mid, u: {"type": "assistant", "timestamp": "2026-11-09T10:12:00Z",
                            "message": {"id": mid, "model": "claude-opus-5-5", "usage": u}}
        cs = lambda cost, models: {"type": "cost-state", "totalCostUSD": cost, "totalDuration": 609650,
                                   "modelUsage": {m: {"inputTokens": u[0], "cacheCreationInputTokens": u[1],
                                                      "cacheReadInputTokens": u[2], "outputTokens": u[3]}
                                                  for m, u in models.items()}}
        self.write("s.jsonl", [
            {"type": "user", "timestamp": "2026-11-09T10:12:00Z", "message": {"content": "build"}},
            a("x", usage(2, 20862, 25156, 169)), a("x", usage(2, 20862, 25156, 169)),
            a("y", usage(28, 16003, 672643, 12692)),
            cs(0.204, {"claude-opus-5-5": (510, 21311, 117430, 398)}),
            cs(0.758604, {"claude-haiku-5-5": (1238, 0, 0, 136), "claude-opus-5-5": (1159, 38308, 932061, 13045)}),
        ])
        m = bench.measure(self.d, ["s"])
        self.assertAlmostEqual(m["cost_usd"], 0.7586, places=4)
        self.assertEqual(m["all_tokens"], 1159 + 38308 + 932061 + 13045 + 1238 + 136)
        self.assertEqual(m["by_agent"]["main session"], usage(30, 36865, 697799, 12861))
        self.assertEqual(m["background"], usage(2367, 1443, 234262, 320))
        self.assertEqual(m["calls"], 2)
        self.assertEqual(m["interventions"], 0)

    def test_interventions(self):
        ts = "2026-11-09T10:00:00Z"
        self.write("s.jsonl", [
            {"type": "user", "timestamp": ts, "message": {"content": "/setup-project build it"}},       # launch: not counted
            {"type": "user", "timestamp": ts, "isMeta": True, "message": {"content": "meta"}},
            {"type": "user", "timestamp": ts, "message": {"content": "<command-name>/cost</command-name>"}},
            {"type": "assistant", "timestamp": ts, "message": {"id": "a", "model": "m", "usage": usage(1, 1, 1, 1),
             "content": [{"type": "tool_use", "id": "t1", "name": "AskUserQuestion", "input": {}}]}},
            {"type": "assistant", "timestamp": ts, "message": {"id": "a", "model": "m", "usage": usage(1, 1, 1, 1),
             "content": [{"type": "tool_use", "id": "t1", "name": "AskUserQuestion", "input": {}}]}},  # same call
            {"type": "user", "timestamp": ts, "message": {"content": [{"type": "tool_result", "tool_use_id": "t1"}]}},
            {"type": "user", "timestamp": ts, "message": {"content": [{"type": "text", "text": "use postgres instead"}]}},
        ])
        m = bench.measure(self.d, ["s"])
        self.assertEqual((m["typed"], m["answered_questions"], m["interventions"]), (1, 1, 2))

    def test_subagents_and_cost_state_including_them(self):
        ts = "2026-11-09T11:00:00Z"
        self.write("s.jsonl", [{"type": "user", "timestamp": ts, "message": {"content": "x"}},
                               {"type": "assistant", "timestamp": ts, "message": {"id": "m", "model": "opus", "usage": usage(1, 10, 100, 5)}},
                               {"type": "cost-state", "totalCostUSD": 1.0, "modelUsage": {"opus": {
                                   "inputTokens": 5, "cacheCreationInputTokens": 60, "cacheReadInputTokens": 700, "outputTokens": 50}}}])
        self.write("s/subagents/agent-1.jsonl", [
            {"type": "user", "timestamp": ts, "message": {"content": "BRIEF · T-01 · tester · test"}},
            {"type": "assistant", "timestamp": ts, "message": {"id": "n", "model": "opus", "usage": usage(2, 40, 500, 30)}}])
        m = bench.measure(self.d, ["s"])
        self.assertEqual(m["tokens"], usage(5, 60, 700, 50))
        self.assertEqual(m["by_agent"]["tester"], usage(2, 40, 500, 30))
        self.assertTrue(m["cost_complete"])
        # D9: split by step from the BRIEF line, and price-weighted shares
        self.assertEqual(m["by_step"]["test"], usage(2, 40, 500, 30))
        self.assertEqual(m["by_step"]["orchestrator"], usage(1, 10, 100, 5))
        tester = m["shares"]["tester"]
        self.assertAlmostEqual(tester["cache_write_share"], 40 / 540, places=4)
        self.assertAlmostEqual(tester["output_cost_share"], 150 / (2 + 50 + 50 + 150), places=4)
        total = sum(bench.weighted(u) for u in m["by_agent"].values())
        self.assertAlmostEqual(tester["cost_share"], bench.weighted(usage(2, 40, 500, 30)) / total, places=4)
        table = bench.token_table(m, "x")
        self.assertIn("| step |", table)
        self.assertIn("| test |", table)

    def test_cost_script_for_cards_and_budget(self):
        # D23: skills/setup-project/scripts/cost.py reuses this reader for the card's Cost line
        import re as _re
        base = self.d / "base"
        base.mkdir()
        logs = self.d / "logs"
        ld = logs / _re.sub(r"[^A-Za-z0-9]", "-", str(base.resolve()))
        ts = "2026-11-10T10:00:00Z"
        main = [{"type": "user", "timestamp": ts, "message": {"content": "go"}},
                {"type": "assistant", "timestamp": ts, "message": {"id": "m", "model": "opus", "usage": usage(0, 0, 1000, 100)}},
                {"type": "cost-state", "totalCostUSD": 2.0, "modelUsage": {"opus": {
                    "inputTokens": 0, "cacheCreationInputTokens": 0, "cacheReadInputTokens": 2000, "outputTokens": 200}}}]
        sub = [{"type": "user", "timestamp": ts, "message": {"content": "TEAM_RULES: x\nBRIEF · T-04 · tester · test"}},
               {"type": "assistant", "timestamp": ts, "message": {"id": "s", "model": "opus", "usage": usage(0, 0, 1000, 100)}}]
        (ld / "s1" / "subagents").mkdir(parents=True)
        (ld / "s1.jsonl").write_text("\n".join(json.dumps(x) for x in main) + "\n")
        (ld / "s1" / "subagents" / "a.jsonl").write_text("\n".join(json.dumps(x) for x in sub) + "\n")
        script = ROOT / "skills" / "setup-project" / "scripts" / "cost.py"

        def run(*a):
            return subprocess.run([sys.executable, str(script), str(base), *a], capture_output=True, text=True,
                                  encoding="utf-8", env={**os.environ, "BENCH_LOGS": str(logs)})
        p = run("--task", "T-04", "--since", "2026-11-10 09:00 +00:00", "--budget", "25", "--json")
        r = json.loads(p.stdout)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(r["total_usd"], 2.0)
        self.assertEqual(r["task_usd"], 1.0)        # the tester's tokens are half the run's weighted tokens
        self.assertEqual(r["line"], "Cost: ≈$1.00 this task · $2.00 so far · budget $25 (8%)")
        self.assertEqual(run("--budget", "1.5").returncode, 3)             # over budget
        self.assertIn("$0.00 so far", run("--since", "2026-11-11 00:00 +00:00").stdout)   # before the project

    def test_claude_p_survives_large_output(self):
        # A real run hung 1.5 h: Claude Code's final JSON outgrew the pipe buffer while bench.py
        # waited for it to exit. A fake claude printing 300 KB must still come back, parsed.
        script = self.d / "big.py"
        script.write_text("import json, sys\nsys.stderr.write('w' * 100000)\n"
                          "print(json.dumps({'is_error': False, 'result': 'x' * 300000}))\n")
        if os.name == "nt":
            fake = self.d / "claude.cmd"
            fake.write_text(f'@"{sys.executable}" "{script}" %*\n')
        else:
            fake = self.d / "claude"
            fake.write_text(f"#!/bin/sh\nexec {sys.executable} {script} \"$@\"\n")
            fake.chmod(0o755)
        import threading
        old, bench.CLAUDE = bench.CLAUDE, str(fake)
        box = {}
        try:
            t = threading.Thread(target=lambda: box.update(r=bench.claude_p("hi", self.d, False)), daemon=True)
            t.start()
            t.join(60)
        finally:
            bench.CLAUDE = old
        self.assertIn("r", box, "claude_p deadlocked on large output")
        self.assertFalse(box["r"]["is_error"])
        self.assertEqual(len(box["r"]["result"]), 300000)

    def test_step_times(self):
        # D10: started→done pairs per step, and the wait between the last event and the answer
        (self.d / ".git").mkdir()
        (self.d / ".git" / "devteam-timing.log").write_text("\n".join([
            "2026-11-10T10:00:00Z\tT-01\tstart",
            "2026-11-10T10:00:00Z\tT-01\timplement started",
            "2026-11-10T10:06:00Z\tT-01\timplement done",
            "2026-11-10T10:06:00Z\tT-01\ttest started",
            "2026-11-10T10:09:00Z\tT-01\ttest done",
            "2026-11-10T10:30:00Z\tT-01\tapproved",
            "2026-11-10T10:00:00Z\tT-02\timplement started",
            "2026-11-10T10:04:00Z\tT-02\timplement done",
            "garbage line"]) + "\n")
        t = bench.step_times(self.d)
        self.assertEqual(t["implement"], {"minutes": 10.0, "count": 2})
        self.assertEqual(t["test"], {"minutes": 3.0, "count": 1})
        self.assertEqual(t["waiting for you (card → answer)"], {"minutes": 21.0, "count": 1})
        self.assertIn("| implement | 2 | 10.0 |", bench.times_table(t))
        self.assertEqual(bench.step_times(self.d / "missing"), {})

    def test_tokens_cli(self):
        self.write("s.jsonl", [{"type": "user", "timestamp": "2026-11-09T10:00:00Z", "message": {"content": "x"}},
                               {"type": "assistant", "timestamp": "2026-11-09T10:01:00Z",
                                "message": {"id": "a", "model": "opus", "usage": usage(1, 2, 3, 4)}}])
        out = subprocess.run([sys.executable, str(BENCH), "tokens", "--project-dir", str(self.d), "--json"],
                             capture_output=True, text=True, check=True).stdout
        self.assertEqual(json.loads(out)["all_tokens"], 10)


class AcceptanceTest(unittest.TestCase):
    def serve(self, script, env=None):
        port = free_port()
        p = subprocess.Popen([sys.executable, str(script)], cwd=Path(script).parent,
                             env={**os.environ, "PORT": str(port), **(env or {})})
        for _ in range(200):   # up to 20 s: slow CI runners (macOS) took over 5 s to start the server
            if bench.port_open(port):
                break
            time.sleep(0.1)
        def stop():
            if os.name == "nt":   # D34: end the whole tree, or a child keeps the SQLite file open
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
            p.kill()
            p.wait()
        self.addCleanup(stop)
        return f"http://127.0.0.1:{port}"

    def test_production_reference_passes(self):
        res, _ = bench.accept_production(self.serve(FIX / "prod_ref.py"))
        self.assertEqual([n for n, ok in res if not ok], [])
        self.assertEqual(len(res), bench.APPS["production"]["checks"])

    def test_production_broken_variants_fail_their_check(self):
        cases = {"ratelimit": "5 failed logins → 6th attempt 429", "order": "list is newest first",
                 "delete": "member DELETE → 403"}
        for brk, check in cases.items():
            with self.subTest(brk=brk):
                res, _ = bench.accept_production(self.serve(FIX / "prod_ref.py", {"BREAK": brk}))
                self.assertIn(check, [n for n, ok in res if not ok])

    def test_small_app_passes(self):
        # D34: remove the folder only after the server is stopped (cleanups run last-in, first-out);
        # Windows can't delete the SQLite file while the server still has it open
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        d = tmp.name
        for f in (FIX / "small_app").iterdir():
            (Path(d) / f.name).write_bytes(f.read_bytes())
        base = self.serve(Path(d) / "app.py")
        res, ctx = bench.accept_small(base)
        self.assertEqual([n for n, ok in res if not ok], [])
        self.assertTrue(bench.persist_small(base, ctx))


class EndToEndTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        if os.name == "nt":   # D34: Windows runs a .cmd, not a shebang script
            fake = t / "claude.cmd"
            fake.write_text(f'@"{sys.executable}" "{FIX / "fake_claude.py"}" %*\n')
        else:
            fake = t / "claude"
            fake.write_text(f"#!/bin/sh\nexec {sys.executable} {FIX / 'fake_claude.py'} \"$@\"\n")
            fake.chmod(0o755)
        self.env = {**os.environ, "BENCH_DIR": str(t / "bench"), "BENCH_PROJECTS": str(t / "projects"),
                    "BENCH_LOGS": str(t / "logs"), "CLAUDE_BIN": str(fake), "BENCH_PORT": str(free_port()),
                    "FAKE_CLAUDE_STATE": str(t / "plugin-state")}
        self.t = t

    def tearDown(self):
        self.tmp.cleanup()

    def bench(self, *args, stdin=""):
        p = subprocess.run([sys.executable, str(BENCH), *args], input=stdin, capture_output=True, text=True,
                           env=self.env, timeout=300)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        return p.stdout

    def state(self):
        return json.loads((self.t / "bench" / "state.json").read_text())

    def test_full_small_benchmark(self):
        # normal run: settings → skip permissions y, headless y, plugin unattended n, budget 10
        out = self.bench("run", "small", "normal", stdin="y\ny\nn\n10\n")
        self.assertIn("acceptance 8/8", out)
        n = self.state()["runs"]["small-normal"]
        self.assertAlmostEqual(n["tokens"]["cost_usd"], 0.7586, places=4)
        self.assertEqual(n["test"]["acceptance"], 8)
        self.assertTrue(n["test"]["persists"])
        self.assertEqual(n["quality"]["files"]["README"], "✅")
        self.assertEqual((self.t / "plugin-state").read_text(), "disabled")   # plugin was off

        # plugin run: Enter to open, resume once, then done
        out = self.bench("run", "small", "plugin", stdin="\nr\nd\n")
        self.assertIn("Budget: $7.59", out)
        p = self.state()["runs"]["small-plugin"]
        self.assertEqual(len(p["tokens"]["sessions"]), 2)
        self.assertAlmostEqual(p["tokens"]["cost_usd"], 5.0)
        self.assertEqual(p["tokens"]["interventions"], 4)                     # per session: 1 typed + 1 answer
        self.assertIn("backend-coder", p["tokens"]["by_agent"])
        self.assertEqual(p["test"]["acceptance"], 8)
        self.assertTrue((self.t / "projects" / "bench-link-shortener" / "start.sh").exists())

        report = (self.t / "bench" / "results.md").read_text()
        self.assertIn("**plugin ÷ normal** | **6.6×**", report)
        self.assertIn("| small-plugin | 8/8 | ✅ |", report)

    def test_unattended_plugin_run(self):
        # D7: settings → skip permissions y, headless y, plugin unattended y, budget 10
        self.bench("run", "small", "normal", stdin="y\ny\ny\n10\n")
        out = self.bench("run", "small", "plugin")          # no stdin: nothing may ask
        self.assertIn("Handover done.", out)
        p = self.state()["runs"]["small-plugin"]
        self.assertFalse(p["stopped"])
        self.assertEqual(len(p["tokens"]["sessions"]), 2)    # first session ends at the milestone
        self.assertEqual(p["tokens"]["interventions"], 3)    # the answers logged, not the markers
        self.assertEqual(p["test"]["acceptance"], 8)

    def test_overhead(self):
        self.bench("overhead")
        o = self.state()["overhead"]
        self.assertEqual((o["without"], o["with"], o["overhead"]), (28677, 34239, 5562))
        self.assertEqual((self.t / "plugin-state").read_text(), "enabled")    # restored afterwards

    def test_clean(self):
        (self.t / "bench" / "small-normal").mkdir(parents=True)
        (self.t / "projects" / "bench-link-shortener").mkdir(parents=True)
        (self.t / "projects" / "keep-me").mkdir(parents=True)
        self.bench("clean", stdin="n\n")
        self.assertTrue((self.t / "bench").exists())                          # declined: nothing deleted
        self.bench("clean", stdin="y\n")
        self.assertFalse((self.t / "bench").exists())
        self.assertFalse((self.t / "projects" / "bench-link-shortener").exists())
        self.assertTrue((self.t / "projects" / "keep-me").exists())


if __name__ == "__main__":
    unittest.main()
