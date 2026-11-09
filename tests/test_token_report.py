"""token_report.py on synthetic Claude Code session logs.

Covers: a reply logged across several lines (counted once, final output count kept),
old-style sidechain lines in the main file, subagent logs in <session>/subagents/,
agent names from the dev-team BRIEF header or a meta file, and --since across sessions.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "bench" / "tools" / "token_report.py"


def usage(i=0, cw=0, cr=0, o=0):
    return {"input_tokens": i, "cache_creation_input_tokens": cw, "cache_read_input_tokens": cr, "output_tokens": o}


def assistant(mid, model, u, ts, sidechain=False):
    return {"type": "assistant", "isSidechain": sidechain, "timestamp": ts,
            "message": {"id": mid, "model": model, "usage": u, "content": [{"type": "text", "text": "x"}]}}


def user(text, ts):
    return {"type": "user", "timestamp": ts, "message": {"role": "user", "content": text}}


def write(path: Path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(l) for l in lines) + "\n")


class TokenReportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        p = self.pdir = Path(self.tmp.name)
        t = "2026-11-09T10:{:02d}:00Z".format
        write(p / "sessA.jsonl", [
            user("build it", t(0)),
            assistant("m1", "claude-opus", usage(10, 100, 1000, 5), t(1)),     # same reply, partial
            assistant("m1", "claude-opus", usage(10, 100, 1000, 20), t(1)),    # same reply, final
            assistant("m2", "claude-opus", usage(3, 0, 1200, 50), t(2)),
            assistant("m3", "claude-haiku", usage(7, 0, 0, 9), t(3), sidechain=True),
        ])
        write(p / "sessA" / "subagents" / "agent-abc.jsonl", [
            user("BRIEF · T-07 · backend-coder · implement\nWorktree: x", t(4)),
            assistant("m4", "claude-sonnet", usage(20, 500, 0, 300), t(5)),
        ])
        write(p / "sessA" / "subagents" / "agent-def.jsonl", [
            user("review this", t(6)),
            assistant("m5", "claude-opus", usage(1, 0, 400, 40), t(7)),
        ])
        (p / "sessA" / "subagents" / "agent-def.meta.json").write_text(json.dumps({"agentType": "dev-team-setup:reviewer"}))
        write(p / "sessOld.jsonl", [user("old", "2026-11-08T09:00:00Z"),
                                    assistant("o1", "claude-opus", usage(999, 0, 0, 999), "2026-11-08T09:01:00Z")])
        write(p / "sessB.jsonl", [user("next milestone", t(30)),
                                  assistant("b1", "claude-opus", usage(4, 40, 0, 10), t(31))])

    def tearDown(self):
        self.tmp.cleanup()

    def run_report(self, *args):
        out = subprocess.run([sys.executable, str(SCRIPT), "--project-dir", str(self.pdir), "--json", *args],
                             capture_output=True, text=True, check=True).stdout
        return json.loads(out)

    def test_single_session_with_subagents(self):
        r = self.run_report("--session", "sessA")
        a = r["by_agent"]
        self.assertEqual(a["main session"], usage(13, 100, 2200, 70))           # m1 once (final), m2
        self.assertEqual(a["subagent (sidechain)"], usage(7, 0, 0, 9))
        self.assertEqual(a["backend-coder"], usage(20, 500, 0, 300))           # from BRIEF header
        self.assertEqual(a["reviewer"], usage(1, 0, 400, 40))                  # from meta file
        self.assertEqual(r["calls"], 5)
        self.assertEqual(r["all_tokens"], sum(sum(u.values()) for u in a.values()))
        self.assertEqual(r["subagent_tokens"], 16 + 820 + 441)
        self.assertEqual(r["minutes"], 6.0)
        self.assertEqual(r["by_model"]["claude-sonnet"]["output_tokens"], 300)

    def test_since_spans_fresh_sessions_and_skips_older(self):
        r = self.run_report("--since", "2026-11-09T09:59:00+00:00")
        self.assertEqual(sorted(r["sessions"]), ["sessA", "sessB"])
        self.assertEqual(r["by_agent"]["main session"], usage(17, 140, 2200, 80))
        self.assertNotIn(999, [v for u in r["by_agent"].values() for v in u.values()])

    def test_markdown_output(self):
        out = subprocess.run([sys.executable, str(SCRIPT), "--project-dir", str(self.pdir), "--session", "sessA",
                              "--label", "plugin"], capture_output=True, text=True, check=True).stdout
        self.assertIn("| backend-coder | 1 |", out)
        self.assertIn("| plugin |", out)


def cost_state(cost, models):
    camel = {"input_tokens": "inputTokens", "cache_creation_input_tokens": "cacheCreationInputTokens",
             "cache_read_input_tokens": "cacheReadInputTokens", "output_tokens": "outputTokens"}
    return {"type": "cost-state", "totalCostUSD": cost, "totalDuration": 609650, "hasUnknownModelCost": False,
            "modelUsage": {m: {camel[k]: v for k, v in u.items()} | {"thinkingTokens": 1, "costUSD": 0} for m, u in models.items()}}


class CostStateTest(unittest.TestCase):
    """Real numbers from the baseline run (Claude Code 2.1.312): replies in the log vs cost-state."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pdir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def report(self, *args):
        out = subprocess.run([sys.executable, str(SCRIPT), "--project-dir", str(self.pdir), "--json", *args],
                             capture_output=True, text=True, check=True).stdout
        return json.loads(out)

    def test_baseline_matches_cost(self):
        t = "2026-11-09T10:{:02d}:00Z".format
        write(self.pdir / "base.jsonl", [
            user("build", t(12)),
            assistant("a", "claude-opus-5-5", usage(2, 20862, 25156, 169), t(12)),
            assistant("a", "claude-opus-5-5", usage(2, 20862, 25156, 169), t(12)),   # same reply, 2nd line
            assistant("b", "claude-opus-5-5", usage(28, 16003, 672643, 12692), t(17)),
            cost_state(0.204, {"claude-opus-5-5": usage(510, 21311, 117430, 398)}),  # earlier snapshot
            cost_state(0.758604, {"claude-haiku-5-5": usage(1238, 0, 0, 136),
                                  "claude-opus-5-5": usage(1159, 38308, 932061, 13045)}),
        ])
        r = self.report("--session", "base")
        self.assertAlmostEqual(r["cost_usd"], 0.7586, places=4)
        self.assertTrue(r["cost_complete"])
        self.assertEqual(r["by_model"]["claude-opus-5-5"], usage(1159, 38308, 932061, 13045))
        self.assertEqual(r["all_tokens"], 1159 + 38308 + 932061 + 13045 + 1238 + 136)
        self.assertEqual(r["by_agent"]["main session"], usage(30, 36865, 697799, 12861))
        self.assertEqual(r["background"], usage(1159 - 30 + 1238, 38308 - 36865, 932061 - 697799, 13045 - 12861 + 136))
        self.assertEqual(r["minutes"], round(609650 / 60000, 1))

    def test_cost_state_covering_subagents(self):
        t = "2026-11-09T11:{:02d}:00Z".format
        write(self.pdir / "s.jsonl", [user("x", t(0)), assistant("m", "opus", usage(1, 10, 100, 5), t(1)),
                                      cost_state(1.0, {"opus": usage(5, 60, 700, 50)})])
        write(self.pdir / "s" / "subagents" / "agent-1.jsonl", [
            user("BRIEF · T-01 · tester · test", t(2)), assistant("n", "opus", usage(2, 40, 500, 30), t(3))])
        r = self.report("--session", "s")
        self.assertEqual(r["totals"], usage(5, 60, 700, 50))          # cost-state already includes the subagent
        self.assertEqual(r["by_agent"]["tester"], usage(2, 40, 500, 30))
        self.assertEqual(r["background"], usage(2, 10, 100, 15))
        self.assertTrue(r["cost_complete"])

    def test_cost_state_excluding_subagents(self):
        t = "2026-11-09T12:{:02d}:00Z".format
        write(self.pdir / "s.jsonl", [user("x", t(0)), assistant("m", "opus", usage(1, 10, 100, 5), t(1)),
                                      cost_state(1.0, {"opus": usage(1, 10, 100, 5)})])
        write(self.pdir / "s" / "subagents" / "agent-1.jsonl", [
            user("BRIEF · T-01 · tester · test", t(2)), assistant("n", "opus", usage(2, 40, 500, 30), t(3))])
        r = self.report("--session", "s")
        self.assertEqual(r["totals"], usage(3, 50, 600, 35))          # subagent replies added on top
        self.assertFalse(r["cost_complete"])
        self.assertTrue(any("excludes subagents" in n for n in r["notes"]))

    def test_sessions_add_up(self):
        t = "2026-11-09T13:{:02d}:00Z".format
        for i, c in ((1, 0.5), (2, 0.25)):
            write(self.pdir / f"m{i}.jsonl", [user("x", t(i)), assistant(f"r{i}", "opus", usage(1, 1, 1, 1), t(i)),
                                              cost_state(c, {"opus": usage(2, 2, 2, 2)})])
        r = self.report("--since", "2026-11-09T13:00:00+00:00")
        self.assertAlmostEqual(r["cost_usd"], 0.75)
        self.assertEqual(r["totals"], usage(4, 4, 4, 4))


if __name__ == "__main__":
    unittest.main()
