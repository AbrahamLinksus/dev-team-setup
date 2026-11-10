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

    def test_modes_are_choices(self):
        # K15: approval_mode and cost_mode accepted any text, so a typo went unnoticed
        uc = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["userConfig"]
        self.assertEqual(uc["approval_mode"]["options"], ["every-task", "batch-low-risk"])
        self.assertEqual(uc["cost_mode"]["options"], ["quality", "balanced"])
        for key in ("approval_mode", "cost_mode"):
            self.assertIn(uc[key]["default"], uc[key]["options"])

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

    def test_bare_continue_needs_context(self):
        # K11: a bare "continue" after any interrupted session could trigger the skill
        desc = " ".join(frontmatter(SKILL / "SKILL.md")["description"].split())
        self.assertNotIn('or says "continue" after a setup-project session was interrupted', desc)
        self.assertIn("STATE.md", desc)

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

    def test_catalog_matches_the_agents(self):
        # K16: the catalog drifted (git-pr, reviewer, statistician had Write but the catalog didn't list it)
        catalog = SKILL / "references" / "agent-catalog.md"
        with tempfile.TemporaryDirectory() as d:
            copy = Path(d) / "agent-catalog.md"
            copy.write_text(catalog.read_text(encoding="utf-8"), encoding="utf-8")
            subprocess.run([sys.executable, str(ROOT / "tools" / "gen_agents.py"), "--out", d, "--catalog", str(copy)],
                           check=True, capture_output=True)
            self.assertEqual(copy.read_text(encoding="utf-8"), catalog.read_text(encoding="utf-8"),
                             "agent-catalog.md is out of date: run python3 tools/gen_agents.py")
        text = catalog.read_text(encoding="utf-8")
        for path in AGENTS:
            fm = frontmatter(path)
            row = next(ln for ln in text.splitlines() if ln.startswith(f"| {fm['name']} |"))
            for tool in fm["tools"]:
                if not tool.startswith("mcp__"):
                    with self.subTest(agent=fm["name"], tool=tool):
                        self.assertIn(tool, row)

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

    def test_push_policy_is_consistent(self):
        # K10: "any push" was Tier 1, contradicting pre-approved wip pushes and card approvals
        policy = (SKILL / "references" / "decision-policy.md").read_text(encoding="utf-8")
        self.assertNotIn("repo visibility, any push\n", policy)
        self.assertIn("`wip/*` checkpoint pushes", policy)

    def test_spec_interview_is_capped(self):
        # K12: no round limit, and every round an Opus planner re-reads the whole SPEC
        interview = (SKILL / "references" / "spec-interview.md").read_text(encoding="utf-8")
        self.assertIn("at most 6 rounds", interview)
        self.assertNotIn("There's no round limit", (SKILL / "SKILL.md").read_text(encoding="utf-8"))

    def test_orchestrator_runs_taskgit_itself(self):
        # K13: spawning git-pr for every approve/reject cost a whole agent start-up to run one script
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("**git-pr** `$TASKGIT approve", skill)
        self.assertNotIn("**git-pr** `$TASKGIT reject", skill)
        self.assertIn("run `$TASKGIT approve <repo> T-xx", skill)

    def test_no_shared_default_ports(self):
        # K14: parallel tasks all used 3000/8000/8501, so a screenshot could come from another task's server
        for f in [SKILL / "references" / "visual-capture.md", *(ROOT / "agents").glob("*.md")]:
            with self.subTest(file=f.name):
                self.assertNotRegex(f.read_text(encoding="utf-8"), r"localhost:(3000|8000|8501)\b")
        self.assertIn("Port:", (SKILL / "references" / "brief-template.md").read_text(encoding="utf-8"))

    def test_state_template_uses_the_pipeline_numbering(self):
        # K17: the Stage placeholder used old numbering ("1 Team pick · 3 HLD …")
        state = (SKILL / "templates" / "STATE.md").read_text(encoding="utf-8")
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        for n, name in [(1, "Spec"), (2, "HLD"), (3, "Team pick"), (4, "LLD"), (5, "Env"), (6, "Tasks"), (7, "Build"), (8, "Handover")]:
            with self.subTest(stage=n):
                self.assertIn(f"{n} {name}", state)
                self.assertIn(f"## {n} · ", skill)

    def test_spec_progress_count_matches(self):
        # K18: progress said x/12 but the checklist had 11 rows (SPEC.md has 12 sections)
        spec_sections = re.findall(r"^## \d+\. ", (SKILL / "templates" / "SPEC.md").read_text(encoding="utf-8"), re.M)
        interview = (SKILL / "references" / "spec-interview.md").read_text(encoding="utf-8")
        table = interview.split("## Completeness checklist")[1].split("\n## ")[0]
        rows = [ln for ln in table.splitlines() if ln.startswith("| ") and not ln.startswith("| Section")]
        self.assertEqual(len(rows), len(spec_sections))
        for count in re.findall(r"\d+/(\d+) (?:sections )?compl", interview):
            self.assertEqual(int(count), len(spec_sections))

    def test_marketplace_description_is_neutral(self):
        # K19: "Jake's Claude plugins" (the owner's name belongs in the author field, not the description)
        desc = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))["description"]
        self.assertNotIn("'s Claude plugins", desc)

    def test_typescript_coverage_has_a_threshold(self):
        # K20: Python failed under 80% coverage, TypeScript had no threshold at all
        conventions = (SKILL / "templates" / "CONVENTIONS.md").read_text(encoding="utf-8")
        row = next(ln for ln in conventions.splitlines() if ln.startswith("| Tests + coverage"))
        self.assertIn("coverage.thresholds", row)
        self.assertIn("coverage.thresholds", (ROOT / "agents" / "env-setup.md").read_text(encoding="utf-8"))

    def test_agent_duties_are_not_repeated(self):
        # K21: the reviewer's duties 4 and 5 said the same thing (severity, file:line, fix)
        for path in AGENTS:
            duties = [ln for ln in path.read_text(encoding="utf-8").split("## Responsibilities")[1].split("## Team rules")[0].splitlines()
                      if re.match(r"\d+\. ", ln)]
            mentions = [d for d in duties if "file:line" in d]
            with self.subTest(agent=path.stem):
                self.assertLessEqual(len(mentions), 1, "the same instruction appears in more than one duty")

    def test_cancel_pause_and_abandon_are_defined(self):
        # K22: "Cancel" on the install card went nowhere; no way to stop or abandon a project
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        stage5 = skill[skill.index("## 5 · "):skill.index("## 6 · ")]
        self.assertIn("**Cancel** (", stage5)
        self.assertIn("## Pause or abandon", skill)
        self.assertIn("Paused", (SKILL / "templates" / "STATE.md").read_text(encoding="utf-8"))

    def test_agent_descriptions_are_short(self):
        # K23: all 26 descriptions are loaded into every session, even ones that never use the plugin
        total = sum(len(frontmatter(p)["description"]) for p in AGENTS)
        self.assertLess(total, 3500, f"agent descriptions total {total} characters")

    def test_how_it_works_describes_the_scope_check(self):
        # M4: it claimed the scope check "reverts anything written some other way", which was false
        # for edits an agent committed itself until S1
        text = (ROOT / "docs" / "how-it-works.md").read_text(encoding="utf-8")
        self.assertIn("step started from", " ".join(text.split()))
        self.assertNotIn("reverts anything written some other way", " ".join(text.split()))
        self.assertIn("scope_guard.sh", text)

    def test_readme_lists_requirements(self):
        # M5: no prerequisites list, and "That's it" set the wrong expectation
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for need in ("gh auth login", "Python 3.9", "uv", "npm", "Playwright"):
            self.assertIn(need, readme)
        self.assertIn("gh auth status && python3 --version", readme)
        self.assertNotIn("That's it.", readme)

    def test_readme_config_instructions_exist(self):
        # M6: options are prompted on enable; afterwards `/plugin configure <plugin>` (named by the CLI's own
        # install message) or a row per option in `/config` change them
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("/plugin configure dev-team-setup@dev-team-setup", readme)
        self.assertIn("`/config`", readme)

    def test_example_says_how_old_it_is(self):
        # M7: the only example is from v0.2 (no spec stage, no build); readers must know that
        example = (ROOT / "examples" / "todo-app" / "README.md").read_text(encoding="utf-8")
        self.assertIn("Dated example (plugin v0.2)", example)
        self.assertIn("v0.2", (ROOT / "README.md").read_text(encoding="utf-8"))

    def test_readme_discloses_what_it_runs_and_sends(self):
        # D1: the directory's security scan expects every network, install and repo action disclosed
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("## What this plugin runs and sends", readme)
        for must in ("gh repo create", "doctor --install", "telemetry", "scope_guard", "Google Drive"):
            self.assertIn(must, readme)
        web = {p.stem for p in (ROOT / "agents").glob("*.md")
               if re.search(r"^tools:.*(WebFetch|WebSearch)", p.read_text(encoding="utf-8"), re.M)}
        for agent in web:
            self.assertIn(agent, readme, f"{agent} fetches the web but the README doesn't say so")

    def test_guard_prefix_matches_plugin_name(self):
        # D2: the guard only checks agents named "<plugin name>:<agent>". Renaming the plugin without
        # updating both hook files would silently turn the guard off, so pin them to plugin.json.
        manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        prefix = manifest["name"] + ":"
        self.assertIn(prefix, (ROOT / "hooks" / "scope_guard.sh").read_text(encoding="utf-8"))
        self.assertIn(f'PLUGIN = "{manifest["name"]}"', (ROOT / "hooks" / "scope_guard.py").read_text(encoding="utf-8"))
        self.assertTrue(manifest.get("displayName"), "plugin.json needs a displayName for the listing")

    def test_every_known_hole_keeps_its_regression_test(self):
        # M1: each problem fixed in code got a test that names it (S = scope guard, T = taskgit,
        # C = capture.py, G = gen_agents.py). Removing one of those tests should be a conscious act.
        ids = ([f"S{n}" for n in range(1, 21)] + [f"T{n}" for n in range(1, 13)] +
               [f"C{n}" for n in range(1, 10)] + [f"G{n}" for n in range(1, 4)])
        text = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "tests").glob("test_*"))
        missing = [i for i in ids if not re.search(rf"\b{i}\b", text)]
        self.assertEqual(missing, [], "these fixed problems no longer have a regression test")

    def test_no_hardcoded_owner(self):
        for path in list((ROOT / "agents").glob("*.md")) + list(SKILL.rglob("*.md")):
            with self.subTest(file=str(path.relative_to(ROOT))):
                self.assertNotIn("AbrahamLinksus", path.read_text())
                self.assertNotIn("Jake", path.read_text())
                # K19: no fixed time zone or gendered wording for the owner
                self.assertNotRegex(path.read_text(encoding="utf-8"), r"\bIST\b|\b(his|her) phone\b")


if __name__ == "__main__":
    unittest.main()
