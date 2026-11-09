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
        self.assertIn("scope_guard.py", cmd)

    def test_agents_frontmatter(self):
        self.assertEqual(len(AGENTS), 26)
        for path in AGENTS:
            with self.subTest(agent=path.name):
                fm = frontmatter(path)
                self.assertEqual(fm["name"], path.stem)
                self.assertIn(fm["model"], {"opus", "sonnet", "haiku", "inherit"})
                self.assertIn("<example>", fm["description"])
                tools = fm.get("tools", [])
                unknown = {t for t in tools if t not in KNOWN_TOOLS and not t.startswith("mcp__")}
                self.assertFalse(unknown, unknown)
                self.assertIn("team-rules.md", path.read_text())

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
            subprocess.run([sys.executable, str(ROOT / "tools" / "gen_agents.py"), d], check=True, capture_output=True)
            for path in AGENTS:
                with self.subTest(agent=path.name):
                    self.assertEqual((Path(d) / path.name).read_text(), path.read_text(),
                                     "agents/ is out of date: run python3 tools/gen_agents.py")

    def test_no_hardcoded_owner(self):
        for path in list((ROOT / "agents").glob("*.md")) + list(SKILL.rglob("*.md")):
            with self.subTest(file=str(path.relative_to(ROOT))):
                self.assertNotIn("AbrahamLinksus", path.read_text())
                self.assertNotIn("Jake", path.read_text())


if __name__ == "__main__":
    unittest.main()
