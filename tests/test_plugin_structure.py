"""Structural checks: manifest, agents, scopes, references, generator drift.

Run: python3 -m unittest discover -s tests -v   (needs pyyaml)
"""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "setup-project"
AGENTS = sorted((ROOT / "agents").glob("*.md"))
KNOWN_TOOLS = {"Read", "Write", "Edit", "Bash", "Grep", "Glob", "WebSearch", "WebFetch",
               "TaskCreate", "NotebookEdit"}


def frontmatter(path: Path) -> dict:
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, f"{path.name}: no frontmatter"
    return yaml.safe_load(m.group(1))


class StructureTest(unittest.TestCase):
    def test_manifest(self):
        m = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
        self.assertRegex(m["name"], r"^[a-z0-9-]+$")
        self.assertRegex(m["version"], r"^\d+\.\d+\.\d+$")
        allowed = {"type", "title", "description", "required", "default", "options", "multiple", "sensitive", "min", "max"}
        for key, opt in m.get("userConfig", {}).items():
            with self.subTest(option=key):
                self.assertRegex(key, r"^[A-Za-z_][A-Za-z0-9_]*$")
                self.assertTrue({"type", "title", "description"} <= set(opt))
                self.assertTrue(set(opt) <= allowed, set(opt) - allowed)

    def test_hooks_json(self):
        h = json.loads((ROOT / "hooks" / "hooks.json").read_text())
        cmd = h["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        self.assertIn("${CLAUDE_PLUGIN_ROOT}", cmd)
        self.assertIn("scope_guard.sh", cmd)   # S15: shell pre-filter in front of scope_guard.py
        self.assertIn("scope_guard.py", (ROOT / "hooks" / "scope_guard.sh").read_text())

    def test_agents_frontmatter(self):
        self.assertEqual(len(AGENTS), 26)
        for path in AGENTS:
            with self.subTest(agent=path.name):
                fm = frontmatter(path)
                self.assertEqual(fm["name"], path.stem)
                self.assertIn(fm["model"], {"opus", "sonnet", "haiku", "inherit"})
                # the Claude app rejects XML-like tags in descriptions
                self.assertNotRegex(fm["description"], r"[<>]")
                # K1: never picked for ordinary work outside /setup-project
                self.assertTrue(fm["description"].startswith("Only when spawned by the /setup-project Orchestrator with a BRIEF"))
                tools = fm.get("tools", [])
                unknown = {t for t in tools if t not in KNOWN_TOOLS and not t.startswith("mcp__")}
                self.assertFalse(unknown, unknown)
                self.assertIn("team-rules.md", path.read_text())

    def test_report_writers_have_write(self):
        # K5: every agent must write its full report to .results/ (team-rules), so it needs Write
        for path in AGENTS:
            with self.subTest(agent=path.stem):
                self.assertIn("Write", frontmatter(path).get("tools", []))

    def test_every_agent_has_a_scope(self):
        scopes = json.loads((SKILL / "scopes.json").read_text())
        names = {p.stem for p in AGENTS}
        self.assertEqual(names, set(scopes["agents"]))
        for name, spec in scopes["agents"].items():
            with self.subTest(agent=name):
                self.assertIn(spec.get("bash", "none"), {"none", "readonly", "code", "full", "git"})
                for g in spec.get("write", []) + spec.get("deny", []):
                    if g.startswith("@"):
                        self.assertIn(g[1:], scopes["groups"])
        # agents without Bash in their tools must have bash "none"
        for path in AGENTS:
            fm = frontmatter(path)
            if "Bash" not in fm.get("tools", []):
                self.assertEqual(scopes["agents"][path.stem].get("bash", "none"), "none", path.stem)

    def test_skill_description_has_no_tags(self):
        fm = frontmatter(SKILL / "SKILL.md")
        self.assertNotRegex(fm["description"], r"[<>]")   # "description cannot contain XML tags"
        self.assertLessEqual(len(fm["description"]), 1024)

    def test_skill_references_exist(self):
        text = (SKILL / "SKILL.md").read_text()
        for ref in set(re.findall(r"`([a-z-]+\.md)`", text)):
            if ref in {"SKILL.md"}:
                continue
            candidates = [SKILL / "references" / ref, SKILL / "templates" / ref.upper().replace(".MD", ".md")]
            with self.subTest(ref=ref):
                self.assertTrue(any(c.exists() for c in candidates), ref)
        for tpl in ["SPEC", "HLD", "LLD", "CONVENTIONS", "TASKS", "STATE", "DECISIONS", "ARCHITECTURE", "WALKTHROUGH"]:
            self.assertTrue((SKILL / "templates" / f"{tpl}.md").exists(), tpl)

    def test_generated_agents_up_to_date(self):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run([sys.executable, str(ROOT / "tools" / "gen_agents.py"), "--out", d], check=True, capture_output=True)
            for path in AGENTS:
                with self.subTest(agent=path.name):
                    self.assertEqual((Path(d) / path.name).read_text(), path.read_text(),
                                     "agents/ is out of date: run python3 tools/gen_agents.py")
            # G2: an agent in agents/ that the spec no longer generates is stale
            self.assertEqual(sorted(p.name for p in AGENTS), sorted(p.name for p in Path(d).glob("*.md")),
                             "agents/ has files the spec doesn't generate: run python3 tools/gen_agents.py")

    def test_drive_is_optional_and_configurable(self):
        # G3: Drive tool names were hard-coded to a server called Google_Drive
        text = (ROOT / "agents" / "data-acquisition.md").read_text(encoding="utf-8")
        self.assertIn("Google Drive access is optional", text)
        with tempfile.TemporaryDirectory() as d:
            subprocess.run([sys.executable, str(ROOT / "tools" / "gen_agents.py"), "--out", d, "--drive-server", "gdrive"],
                           check=True, capture_output=True)
            tools = frontmatter(Path(d) / "data-acquisition.md")["tools"]
            self.assertIn("mcp__gdrive__read_file_content", tools)
            self.assertFalse(any("Google_Drive" in t for t in tools))
            subprocess.run([sys.executable, str(ROOT / "tools" / "gen_agents.py"), "--out", d, "--drive-server", ""],
                           check=True, capture_output=True)
            self.assertFalse(any(t.startswith("mcp__") for t in frontmatter(Path(d) / "data-acquisition.md")["tools"]))

    def test_gen_agents_removes_stale_agents(self):
        with tempfile.TemporaryDirectory() as d:
            stale = Path(d) / "old-agent.md"
            stale.write_text("---\nname: old-agent\n---\nRead skills/setup-project/references/team-rules.md\n")
            mine = Path(d) / "my-notes.md"
            mine.write_text("not generated\n")
            subprocess.run([sys.executable, str(ROOT / "tools" / "gen_agents.py"), "--out", d], check=True, capture_output=True)
            self.assertFalse(stale.exists())
            self.assertTrue(mine.exists())   # only files the generator wrote are removed

    def test_gen_agents_cli(self):
        # G1: any first argument was taken as the output folder (`--help` wrote 26 files into ./--help/)
        with tempfile.TemporaryDirectory() as d:
            p = subprocess.run([sys.executable, str(ROOT / "tools" / "gen_agents.py"), "--help"], cwd=d,
                               capture_output=True, text=True)
            self.assertEqual(p.returncode, 0)
            self.assertIn("--out", p.stdout)
            self.assertEqual(list(Path(d).iterdir()), [])
            p = subprocess.run([sys.executable, str(ROOT / "tools" / "gen_agents.py"), "stray"], cwd=d,
                               capture_output=True, text=True)
            self.assertNotEqual(p.returncode, 0)
            self.assertFalse((Path(d) / "stray").exists())

    def test_token_rules(self):
        rules = (SKILL / "references" / "team-rules.md").read_text()
        self.assertIn("Read only what your brief's `Read:` field lists", rules)
        self.assertIn("at most 12 lines", rules)
        self.assertNotRegex(rules, r"Read your task in the brief, then `docs/")
        brief = (SKILL / "references" / "brief-template.md").read_text()
        self.assertIn("Read:", brief)
        self.assertIn("Write full report to: <wt>/.results/<task-id>/<step>-<agent>.md", brief)
        # K2: subagents don't start in the worktree, so no path in the brief block may be relative
        block = brief.split("```")[1]
        for line in block.splitlines():
            for path in re.findall(r"(?<![\w<>/.-])((?:docs|src|\.results)/\S*|TASK_PROGRESS\.md)", line):
                self.fail(f"relative path in the brief template: {path!r} in {line!r}")
        self.assertIn("cd <worktree> &&", rules)
        self.assertNotIn("Inputs:", brief)
        self.assertIn("§0", (SKILL / "templates" / "LLD.md").read_text())
        self.assertIn("- Context:", (SKILL / "templates" / "TASKS.md").read_text())
        skill = (SKILL / "SKILL.md").read_text()
        for phrase in ("Never read diffs", "Rework continuation", "fresh session"):
            self.assertIn(phrase, skill)
        build_agents = {"backend-coder", "frontend-coder", "tester", "reviewer", "debugger", "rag-engineer",
                        "agent-engineer", "prompt-engineer", "trainer", "modeler", "evaluator", "mlops"}
        for path in AGENTS:
            if path.stem in build_agents:
                with self.subTest(agent=path.stem):
                    self.assertNotIn("docs/HLD.md", path.read_text())

    def test_runs_on_python_39(self):
        # C2: `str | None` in a signature raises TypeError at import on Python 3.9 (macOS's stock
        # python3) unless annotations are postponed
        for path in [*ROOT.glob("hooks/*.py"), *ROOT.glob("skills/**/*.py"), *ROOT.glob("tools/*.py"), *ROOT.glob("tests/test_*.py")]:
            text = path.read_text(encoding="utf-8")
            if re.search(r"^\s*def .*(:|->)\s*[\w\[\], ]+\s*\|\s*(None|\w)", text, re.M):
                with self.subTest(file=str(path.relative_to(ROOT))):
                    self.assertTrue("from __future__ import annotations" in text,
                                    "uses `X | Y` annotations: add `from __future__ import annotations`")

    def test_coverage_belongs_to_tester(self):
        # K4: coders may not write tests (S7), so they can't be held to the coverage threshold
        for name in ("backend-coder", "frontend-coder", "debugger"):
            with self.subTest(agent=name):
                self.assertIn("CHECK_NO_COVERAGE=1 scripts/check.sh", (ROOT / "agents" / f"{name}.md").read_text(encoding="utf-8"))
        self.assertNotIn("CHECK_NO_COVERAGE", (ROOT / "agents" / "tester.md").read_text(encoding="utf-8"))
        self.assertIn("CHECK_NO_COVERAGE=1 scripts/check.sh", (SKILL / "references" / "team-rules.md").read_text(encoding="utf-8"))

    def test_readme_images_are_tracked(self):
        # K6: .results/ is git-ignored and removed on approve, so README images must live in docs/images/
        docs = (ROOT / "agents" / "docs.md").read_text(encoding="utf-8")
        self.assertIn("docs/images/", docs)
        self.assertNotIn("screenshots of the running app from `.results/`", docs)
        self.assertIn("docs/images/", (SKILL / "SKILL.md").read_text(encoding="utf-8"))

    def test_project_lives_in_session_folder(self):
        # K3: ~/projects is outside the session's folders: permission prompts, refused in remote sessions
        for f in [SKILL / "SKILL.md", *SKILL.glob("references/*.md")]:
            with self.subTest(file=f.name):
                self.assertNotIn("Clone to `~/projects", f.read_text(encoding="utf-8"))
        self.assertIn("<base>/<repo>-wt/", (SKILL / "SKILL.md").read_text(encoding="utf-8"))

    def test_cards_have_a_cli_fallback(self):
        # K8: SendUserFile / SendUserMessage don't exist in the terminal CLI
        card = (SKILL / "references" / "result-card.md").read_text(encoding="utf-8")
        self.assertIn("Not available", card)
        self.assertIn("card.md", card)
        self.assertIn("absolute paths", card)

    def test_data_and_models_stay_out_of_git(self):
        # T8: nothing ignored data/, models/, *.parquet, *.pt, *.pkl; only the 20 MB limit stopped them
        env = (ROOT / "agents" / "env-setup.md").read_text(encoding="utf-8")
        for pattern in ("`data/`", "`models/`", "`*.parquet`", "`*.pt`", "`*.pkl`"):
            self.assertIn(pattern, env)
        self.assertIn("DVC", (SKILL / "references" / "decision-policy.md").read_text(encoding="utf-8"))

    def test_handover_commands_run_by_a_role_with_bash(self):
        # K7: the reviewer (no Bash) was asked to confirm that every documented command works
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        handover = skill[skill.index("## 8 · Handover"):skill.index("## Change requests")]
        self.assertNotIn("checks that every path, command and function", handover)
        self.assertIn("**tester** (it has Bash): runs every command", handover)
        self.assertIn("Bash", frontmatter(ROOT / "agents" / "tester.md")["tools"])

    def test_every_return_format_is_documented(self):
        # K9: team-rules allowed only REPORT and DECISION NEEDED, but the planner returns QUESTIONS / SPEC COMPLETE
        rules = (SKILL / "references" / "team-rules.md").read_text(encoding="utf-8")
        for fmt in ("REPORT <task-id>", "DECISION NEEDED", "QUESTIONS (round", "SPEC COMPLETE"):
            self.assertIn(fmt, rules)

    def test_no_hardcoded_owner(self):
        for path in list((ROOT / "agents").glob("*.md")) + list(SKILL.rglob("*.md")):
            with self.subTest(file=str(path.relative_to(ROOT))):
                self.assertNotIn("AbrahamLinksus", path.read_text())
                self.assertNotIn("Jake", path.read_text())


if __name__ == "__main__":
    unittest.main()
