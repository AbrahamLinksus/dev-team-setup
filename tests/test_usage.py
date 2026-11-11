"""usage.py and cost.py: tokens, cost and interventions from Claude Code's session logs."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "setup-project" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import usage  # noqa: E402


def usage_of(i=0, cw=0, cr=0, o=0):
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
            a("x", usage_of(2, 20862, 25156, 169)), a("x", usage_of(2, 20862, 25156, 169)),
            a("y", usage_of(28, 16003, 672643, 12692)),
            cs(0.204, {"claude-opus-5-5": (510, 21311, 117430, 398)}),
            cs(0.758604, {"claude-haiku-5-5": (1238, 0, 0, 136), "claude-opus-5-5": (1159, 38308, 932061, 13045)}),
        ])
        m = usage.measure(self.d, ["s"])
        self.assertAlmostEqual(m["cost_usd"], 0.7586, places=4)
        self.assertEqual(m["all_tokens"], 1159 + 38308 + 932061 + 13045 + 1238 + 136)
        self.assertEqual(m["by_agent"]["main session"], usage_of(30, 36865, 697799, 12861))
        self.assertEqual(m["background"], usage_of(2367, 1443, 234262, 320))
        self.assertEqual(m["calls"], 2)
        self.assertEqual(m["interventions"], 0)

    def test_interventions(self):
        ts = "2026-11-09T10:00:00Z"
        self.write("s.jsonl", [
            {"type": "user", "timestamp": ts, "message": {"content": "/setup-project build it"}},       # launch: not counted
            {"type": "user", "timestamp": ts, "isMeta": True, "message": {"content": "meta"}},
            {"type": "user", "timestamp": ts, "message": {"content": "<command-name>/cost</command-name>"}},
            {"type": "assistant", "timestamp": ts, "message": {"id": "a", "model": "m", "usage": usage_of(1, 1, 1, 1),
             "content": [{"type": "tool_use", "id": "t1", "name": "AskUserQuestion", "input": {}}]}},
            {"type": "assistant", "timestamp": ts, "message": {"id": "a", "model": "m", "usage": usage_of(1, 1, 1, 1),
             "content": [{"type": "tool_use", "id": "t1", "name": "AskUserQuestion", "input": {}}]}},  # same call
            {"type": "user", "timestamp": ts, "message": {"content": [{"type": "tool_result", "tool_use_id": "t1"}]}},
            {"type": "user", "timestamp": ts, "message": {"content": [{"type": "text", "text": "use postgres instead"}]}},
        ])
        m = usage.measure(self.d, ["s"])
        self.assertEqual((m["typed"], m["answered_questions"], m["interventions"]), (1, 1, 2))

    def test_subagents_and_cost_state_including_them(self):
        ts = "2026-11-09T11:00:00Z"
        self.write("s.jsonl", [{"type": "user", "timestamp": ts, "message": {"content": "x"}},
                               {"type": "assistant", "timestamp": ts, "message": {"id": "m", "model": "opus", "usage": usage_of(1, 10, 100, 5)}},
                               {"type": "cost-state", "totalCostUSD": 1.0, "modelUsage": {"opus": {
                                   "inputTokens": 5, "cacheCreationInputTokens": 60, "cacheReadInputTokens": 700, "outputTokens": 50}}}])
        self.write("s/subagents/agent-1.jsonl", [
            {"type": "user", "timestamp": ts, "message": {"content": "BRIEF · T-01 · tester · test"}},
            {"type": "assistant", "timestamp": ts, "message": {"id": "n", "model": "opus", "usage": usage_of(2, 40, 500, 30)}}])
        m = usage.measure(self.d, ["s"])
        self.assertEqual(m["tokens"], usage_of(5, 60, 700, 50))
        self.assertEqual(m["by_agent"]["tester"], usage_of(2, 40, 500, 30))
        self.assertTrue(m["cost_complete"])
        # split by step from the BRIEF line, and price-weighted shares
        self.assertEqual(m["by_step"]["test"], usage_of(2, 40, 500, 30))
        self.assertEqual(m["by_step"]["orchestrator"], usage_of(1, 10, 100, 5))
        tester = m["shares"]["tester"]
        self.assertAlmostEqual(tester["cache_write_share"], 40 / 540, places=4)
        self.assertAlmostEqual(tester["output_cost_share"], 150 / (2 + 50 + 50 + 150), places=4)
        total = sum(usage.weighted(u) for u in m["by_agent"].values())
        self.assertAlmostEqual(tester["cost_share"], usage.weighted(usage_of(2, 40, 500, 30)) / total, places=4)

    def test_cost_script_for_cards_and_budget(self):
        # the result card's Cost line and the budget cap
        import re as _re
        base = self.d / "base"
        base.mkdir()
        logs = self.d / "logs"
        ld = logs / _re.sub(r"[^A-Za-z0-9]", "-", str(base.resolve()))
        ts = "2026-11-10T10:00:00Z"
        main = [{"type": "user", "timestamp": ts, "message": {"content": "go"}},
                {"type": "assistant", "timestamp": ts, "message": {"id": "m", "model": "opus", "usage": usage_of(0, 0, 1000, 100)}},
                {"type": "cost-state", "totalCostUSD": 2.0, "modelUsage": {"opus": {
                    "inputTokens": 0, "cacheCreationInputTokens": 0, "cacheReadInputTokens": 2000, "outputTokens": 200}}}]
        sub = [{"type": "user", "timestamp": ts, "message": {"content": "TEAM_RULES: x\nBRIEF · T-04 · tester · test"}},
               {"type": "assistant", "timestamp": ts, "message": {"id": "s", "model": "opus", "usage": usage_of(0, 0, 1000, 100)}}]
        (ld / "s1" / "subagents").mkdir(parents=True)
        (ld / "s1.jsonl").write_text("\n".join(json.dumps(x) for x in main) + "\n")
        (ld / "s1" / "subagents" / "a.jsonl").write_text("\n".join(json.dumps(x) for x in sub) + "\n")
        script = SCRIPTS / "cost.py"

        def run(*a):
            return subprocess.run([sys.executable, str(script), str(base), *a], capture_output=True, text=True,
                                  encoding="utf-8", env={**os.environ, "DEVTEAM_LOGS": str(logs)})
        p = run("--task", "T-04", "--since", "2026-11-10 09:00 +00:00", "--budget", "25", "--json")
        r = json.loads(p.stdout)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(r["total_usd"], 2.0)
        self.assertEqual(r["task_usd"], 1.0)        # the tester's tokens are half the run's weighted tokens
        self.assertEqual(r["line"], "Cost: ≈$1.00 this task · $2.00 so far · budget $25 (8%)")
        self.assertEqual(run("--budget", "1.5").returncode, 3)             # over budget
        self.assertIn("$0.00 so far", run("--since", "2026-11-11 00:00 +00:00").stdout)   # before the project

    def test_text_io_names_its_encoding(self):
        # Without encoding=, Python uses the locale (cp1252 on Windows), which can't read or write
        # the logs' "·" and "→". Linux CI never sees it, so check the code.
        import ast
        for path in (SCRIPTS / "usage.py", SCRIPTS / "cost.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                f = node.func
                name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
                kw = {k.arg for k in node.keywords}
                binary = any(isinstance(a, ast.Constant) and "b" in str(a.value) for a in node.args)
                if name == "open" and isinstance(f, ast.Attribute) and ast.unparse(f.value).endswith("opener"):
                    continue   # urllib's opener.open(request), not a file
                if name in ("read_text", "write_text") or (name == "open" and isinstance(f, ast.Attribute) and not binary):
                    with self.subTest(file=path.name, line=node.lineno):
                        self.assertIn("encoding", kw, f"{path.name}:{node.lineno} {name}() without encoding=")
                if name == "run" and isinstance(f, ast.Attribute) and "text" in kw:
                    with self.subTest(file=path.name, line=node.lineno):
                        self.assertIn("encoding", kw, f"{path.name}:{node.lineno} subprocess text=True without encoding=")



if __name__ == "__main__":
    unittest.main()
