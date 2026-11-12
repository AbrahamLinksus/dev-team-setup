"""Structural checks: manifest, agents, scopes, references, generator drift.

Run: python3 -m unittest discover -s tests -v   (needs pyyaml)
"""
import json
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "setup-project"
# D11: SKILL.md is a core; each stage's instructions live in references/stage-*.md and are read
# when the stage starts. Content checks look at the core plus every stage file.
STAGE_FILES = ("stage-0-intake.md", "stage-1-6-planning.md", "stage-7-build.md", "stage-8-handover.md",
               "anytime.md", "resume.md")


def skill_text() -> str:
    return "\n".join([(SKILL / "SKILL.md").read_text(encoding="utf-8")]
                     + [(SKILL / "references" / f).read_text(encoding="utf-8") for f in STAGE_FILES])


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
        self.assertEqual(uc["approval_mode"]["options"], ["every-task", "batch-low-risk", "autopilot"])
        self.assertEqual(uc["cost_mode"]["options"], ["quality", "balanced", "fast"])
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
        text = skill_text()
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
        skill = skill_text()
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
        self.assertIn("docs/images/", skill_text())

    def test_project_lives_in_session_folder(self):
        # K3: ~/projects is outside the session's folders: permission prompts, refused in remote sessions
        for f in [SKILL / "SKILL.md", *SKILL.glob("references/*.md")]:
            with self.subTest(file=f.name):
                self.assertNotIn("Clone to `~/projects", f.read_text(encoding="utf-8"))
        self.assertIn("<base>/<repo>-wt/", skill_text())

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
        skill = skill_text()
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
        self.assertNotIn("There's no round limit", skill_text())

    def test_orchestrator_runs_taskgit_itself(self):
        # K13: spawning git-pr for every approve/reject cost a whole agent start-up to run one script
        skill = skill_text()
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
        skill = skill_text()
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
        skill = skill_text()
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

    def test_tracked_text_files_have_no_cr(self):
        # D3: if the directory's validator rejects .gitattributes, the file goes and this test is the
        # guard instead: a CRLF shell script fails on Linux/macOS ("$'\r': command not found").
        out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True).stdout
        binary = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".plugin"}
        bad = [name for name in out.decode().split("\0")
               if name and (ROOT / name).is_file() and (ROOT / name).suffix.lower() not in binary
               and b"\r" in (ROOT / name).read_bytes()]
        self.assertEqual(bad, [], "CR line endings: run `git add --renormalize .`")

    def test_changelog_top_entry_is_the_current_version(self):
        # D4: a release without a version bump never reaches installed users; tie the bump to a
        # changelog entry so neither is forgotten.
        version = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        top = re.search(r"^## (\S+)", changelog, re.M)
        self.assertIsNotNone(top, "CHANGELOG.md has no release heading")
        self.assertEqual(top.group(1), version, "plugin.json version and the top CHANGELOG entry differ")

    def test_skill_stops_without_agents_or_bash(self):
        # D6: in claude.ai chat agents and hooks are ignored; the skill must refuse rather than run
        # the stages itself with no team and no guard.
        # The check sits in the core, before the step that sends you to any stage file.
        core = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        start = core[core.index("## Start here"):]
        self.assertLess(start.index("Surface check"), start.index("references/stage-0-intake.md"))
        self.assertIn("Agent tool", start[:600])

    def test_skill_core_is_small_and_wired_to_every_stage_file(self):
        # D11: the core is re-read on every Orchestrator call (H2); stage files are read on demand.
        core = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertLess(len(core), 10000, "SKILL.md core grew; move stage detail into references/stage-*.md")
        for f in STAGE_FILES:
            self.assertIn(f"references/{f}", core)
            self.assertTrue((SKILL / "references" / f).read_text(encoding="utf-8").startswith("# "))
        for heading in ("## 0 · Intake", "## 7 · Build loop", "## 8 · Handover", "## Resume"):
            self.assertNotIn(heading, core)
        version = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
        self.assertEqual(frontmatter(SKILL / "SKILL.md")["metadata"]["version"], version)

    def test_brief_puts_stable_lines_before_task_specific_ones(self):
        # D12 (H3): the prompt cache matches the longest identical opening, so the lines that are
        # the same in every brief come before the first task-specific one.
        brief = (SKILL / "references" / "brief-template.md").read_text(encoding="utf-8")
        block = brief[brief.index("```\nTEAM_RULES:"):]
        block = block[:block.index("\n```", 4)]
        stable_end = max(block.index(k) for k in ("TEAM_RULES:", "CAPTURE:", "Return:"))
        for specific in ("BRIEF ·", "Worktree:", "Task:", "Read:", "Port:", "Write full report to:"):
            self.assertLess(stable_end, block.index(specific), specific)

    def test_full_reports_only_when_someone_reads_them(self):
        # D13 (H4): output is the priciest token; a full report nobody opens is pure cost.
        rules = (SKILL / "references" / "team-rules.md").read_text(encoding="utf-8")
        self.assertIn("only when\n   someone will read it", rules)
        self.assertIn("Full report: <path> | none", rules)
        for reader_needs in ("a check or test failed", "Critical or Major", "`## Task impact`", "· always"):
            self.assertIn(reader_needs, rules)
        self.assertIn("· always", (SKILL / "references" / "brief-template.md").read_text(encoding="utf-8"))
        reviewer = (ROOT / "agents" / "reviewer.md").read_text(encoding="utf-8")
        self.assertIn("With only Minor findings, write no full report", reviewer)

    def test_always_on_context_stays_under_budget(self):
        # D14 (H6): the skill description and every agent's name + description ride in every
        # session's system prompt, plugin used or not. The directory listing flags plugins at
        # 2,000+ tokens per turn. At 4,165 characters `claude plugin details` reports ~1,593 tokens
        # (about 2.6 characters per token), so 4,800 characters keeps a margin under 2,000.
        skill = " ".join(frontmatter(SKILL / "SKILL.md")["description"].split())
        agents = sum(len(frontmatter(p)["name"]) + len(frontmatter(p)["description"]) for p in AGENTS)
        self.assertLess(len(skill) + agents, 4800,
                        "always-on text grew; shorten SHORT descriptions in tools/gen_agents.py")

    def test_long_sessions_are_cut_between_tasks(self):
        # D15 (H1): the Orchestrator's own context is the biggest cost on long builds; subagents
        # can't spawn subagents, so it is cut by fresh sessions, not by a task-runner agent.
        build = (SKILL / "references" / "stage-7-build.md").read_text(encoding="utf-8")
        self.assertIn("**Long session check (between tasks).**", build)
        self.assertIn("6 or more tasks", build)
        self.assertIn("SESSION DONE", (SKILL / "references" / "unattended.md").read_text(encoding="utf-8"))

    def test_tester_and_reviewer_run_in_parallel(self):
        # D19: both read the same diff; running them together removes a sequential step per task
        build = (SKILL / "references" / "stage-7-build.md").read_text(encoding="utf-8")
        step3 = build[build.index("3. **tester and reviewer in parallel.**"):build.index("\n4. ")]
        self.assertLess(step3.index("changes.diff"), step3.index("one message"))
        self.assertIn('"test+review started"', step3)
        # D19 fix: scope checks every change since the checkpoint against ONE role, so scoping the
        # reviewer after a parallel step reverted the tester's tests; scope runs once, as tester
        self.assertIn("scope <repo> T-xx tester` **once**", step3)
        self.assertIn("Never run `scope` as reviewer", step3)
        self.assertNotIn("`scope` for each", step3)
        self.assertIn("stage-7-build.md` step 3", (SKILL / "SKILL.md").read_text(encoding="utf-8"))
        tools = frontmatter(ROOT / "agents" / "reviewer.md")["tools"]
        self.assertFalse({"Edit", "Bash"} & set(tools), "parallel is only safe while the reviewer can't change files")

    def test_independent_work_continues_while_a_card_waits(self):
        # D20: owner wait dominates wall time; the team keeps working (background agent, or two
        # cards in one question) in every approval mode, not only batch mode
        build = (SKILL / "references" / "stage-7-build.md").read_text(encoding="utf-8")
        self.assertIn("**Don't let the team idle while a card waits.**", build)
        self.assertIn("run_in_background", build)
        self.assertIn("one\n  AskUserQuestion call", build)
        self.assertIn("Don't let the team idle", (SKILL / "references" / "approval-modes.md").read_text(encoding="utf-8"))

    def test_subagent_status_line(self):
        # D22: the agent panel shows who works on what, for this plugin's agents only
        settings = json.loads((ROOT / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(settings["subagentStatusLine"]["type"], "command")
        self.assertIn("hooks/subagent_status.sh", settings["subagentStatusLine"]["command"])
        now_ms = int(time.time() * 1000)
        rows = {"columns": 60, "tasks": [
            {"id": "a", "agentType": "dev-team-setup:tester", "status": "running",
             "description": "T-04 · test", "startTime": now_ms - 75000, "tokenCount": 41234,
             "contextWindowSize": 200000},
            {"id": "b", "agentType": "Explore", "status": "running", "description": "x",
             "startTime": now_ms, "tokenCount": 5},
            {"id": "c", "agentType": "dev-team-setup:reviewer", "status": "completed",
             "description": "T-04 · review " + "x" * 80, "startTime": now_ms, "tokenCount": 900}]}
        out = subprocess.run([sys.executable, str(ROOT / "hooks" / "subagent_status.py")], input=json.dumps(rows),
                             capture_output=True, text=True, encoding="utf-8").stdout
        lines = [json.loads(ln) for ln in out.splitlines()]
        self.assertEqual([ln["id"] for ln in lines], ["a", "c"])          # Explore keeps its default row
        self.assertEqual(lines[0]["content"], "⏳ tester · T-04 · test · 1m15s · 41k tok · 21% ctx")
        self.assertTrue(lines[1]["content"].startswith("✅ reviewer · T-04 · review"))
        self.assertLessEqual(len(lines[1]["content"]), 60)
        # B-37: a step running 20 minutes or more is marked on its row
        slow = {"columns": 80, "tasks": [{"id": "s", "agentType": "dev-team-setup:backend-coder", "status": "running",
                                          "description": "T-19 · implement", "startTime": now_ms - 21 * 60000}]}
        out = subprocess.run([sys.executable, str(ROOT / "hooks" / "subagent_status.py")], input=json.dumps(slow),
                             capture_output=True, text=True, encoding="utf-8").stdout
        self.assertTrue(json.loads(out)["content"].startswith("⚠️ stalled? backend-coder · T-19 · implement · 21m"))
        bad = subprocess.run([sys.executable, str(ROOT / "hooks" / "subagent_status.py")], input="not json",
                             capture_output=True, text=True)
        self.assertEqual((bad.returncode, bad.stdout), (0, ""))
        self.assertIn('description: "<id> · <step>"', (SKILL / "SKILL.md").read_text(encoding="utf-8"))

    def test_agent_id_cards_match_scopes(self):
        # D25: one plain-language line per role, generated from scopes.json so it can't drift
        sys.path.insert(0, str(ROOT / "tools"))
        import gen_agents
        with tempfile.TemporaryDirectory() as d:
            fresh = Path(d) / "cards.md"
            gen_agents.write_cards(fresh)
            current = (SKILL / "references" / "agent-cards.md").read_text(encoding="utf-8")
            self.assertEqual(current, fresh.read_text(encoding="utf-8"), "run python3 tools/gen_agents.py")
        scopes = json.loads((SKILL / "scopes.json").read_text(encoding="utf-8"))
        for name in scopes["agents"]:
            self.assertIn(f"\n- {name} · may change:", current)
        self.assertIn("- tester · may change: tests, its own reports · can't: anything else", current)
        self.assertIn("agent-cards.md", (SKILL / "SKILL.md").read_text(encoding="utf-8"))

    def test_cards_explain_themselves(self):
        # D26: progress line, fixed order, a gloss for jargon, and why a decision is asked
        card = (SKILL / "references" / "result-card.md").read_text(encoding="utf-8")
        self.assertLess(card.index("## Every card, every time"), card.index("## Per-task card"))
        self.assertIn("Stage 7 Build · Milestone 2/3 · Task 4/12", card)
        self.assertIn("what happened → what it means for you → what you decide", card)
        for term in ("| spec |", "| HLD |", "| LLD |", "| worktree |", "| Tier 1 |"):
            self.assertIn(term, card)
        self.assertIn("**Why we're asking:**", (SKILL / "references" / "decision-policy.md").read_text(encoding="utf-8"))

    def test_owner_mode_is_asked_once_and_sets_card_wording(self):
        # B-01: cards were written for a developer whoever the owner was
        intake = (SKILL / "references" / "stage-0-intake.md").read_text(encoding="utf-8")
        self.assertIn('**"Do you write code?"**', intake)
        self.assertIn("Record `Owner mode: builder|developer` in STATE.md", intake)
        self.assertIn("Both get every\n   Tier 1 decision", intake)
        self.assertIn("| Owner mode |", (SKILL / "templates" / "STATE.md").read_text(encoding="utf-8"))
        self.assertIn('"Owner mode" for every card', (SKILL / "references" / "resume.md").read_text(encoding="utf-8"))
        self.assertIn("`Technical detail: …`", (SKILL / "references" / "result-card.md").read_text(encoding="utf-8"))

    def test_resume_shows_where_we_are(self):
        # D27: a resumed project opens with a one-screen summary, not one line
        resume = (SKILL / "references" / "resume.md").read_text(encoding="utf-8")
        block = resume[resume.index("Where we are ·"):]
        block = block[:block.index("```")]
        self.assertLessEqual(len(block.strip().splitlines()), 9)
        for must in ("Waiting on you:", "Recent decisions:", "Spent:", "Next:"):
            self.assertIn(must, block)

    def test_guardrails_page_is_generated_and_complete(self):
        # D28: the least-privilege page is generated (can't drift from scopes.json) and lists
        # every closed bypass, each of which must still have its test
        sys.path.insert(0, str(ROOT / "tools"))
        import gen_agents
        with tempfile.TemporaryDirectory() as d:
            fresh = Path(d) / "g.md"
            gen_agents.write_guardrails(fresh)
            page = (ROOT / "docs" / "guardrails.md").read_text(encoding="utf-8")
            self.assertEqual(page, fresh.read_text(encoding="utf-8"), "run python3 tools/gen_agents.py")
        for n in range(1, 21):
            self.assertIn(f"| S{n} |", page)
        for _, _, test_file in gen_agents.BYPASSES:
            self.assertTrue((ROOT / "tests" / test_file).exists())
        self.assertIn("docs/guardrails.md", (ROOT / "README.md").read_text(encoding="utf-8"))

    def test_try_locally_needs_no_github(self):
        # D29: a reviewer can see a full run with no GitHub account: a local bare repo is origin
        intake = (SKILL / "references" / "stage-0-intake.md").read_text(encoding="utf-8")
        self.assertIn("**Try locally (no\n   GitHub)**", intake)
        self.assertIn("git init --bare -b main <base>/<repo>.git", intake)
        manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertFalse(manifest["userConfig"]["github_owner"].get("required", False))
        self.assertIn("Try locally", (ROOT / "README.md").read_text(encoding="utf-8"))

    def test_project_size_is_set_at_the_spec_and_recorded(self):
        # O3: run B gave a 5-task app the process of a large one; the size decides how much it gets
        # B-29: a guessed task count sized Recipe Box as medium; risk signals are in the spec itself
        size = "Size: <small|medium|large> · signals: <the risk signals present, or none> · <n> stories"
        for f in ("spec-interview.md", "team-rules.md"):
            self.assertIn(size, (SKILL / "references" / f).read_text(encoding="utf-8"))
        planner = (ROOT / "agents" / "planner.md").read_text(encoding="utf-8")
        self.assertIn("never by a task count", planner)
        signals = "backend, auth, database, multi-user, external services/payments, AI/ML, deployment"
        self.assertIn(signals, planner)
        self.assertIn("**0–1 signals = small, 2–3 = medium, 4+ = large**", planner)
        self.assertIn("more than 15 user stories bumps it up one size", planner)
        planning = (SKILL / "references" / "stage-1-6-planning.md").read_text(encoding="utf-8")
        self.assertIn(signals, " ".join(planning.split()))
        self.assertIn("**Project size.**", planning)
        self.assertIn("High-risk tasks always get the full team", planning)
        self.assertNotIn("update it from the real task count", planning)
        self.assertIn("| Size |", (SKILL / "templates" / "STATE.md").read_text(encoding="utf-8"))

    def test_task_graph_on_the_planning_card(self):
        # B-41: the owner sees what runs together before the build; B-42: foundation first, then slices
        planning = (SKILL / "references" / "stage-1-6-planning.md").read_text(encoding="utf-8")
        self.assertIn("**The task graph goes on the planning card:**", planning)
        self.assertIn("--mermaid", planning)
        self.assertIn("`--summary` lines", planning)
        self.assertIn("exit 2 (a cycle, an unknown ID, a task missing", planning)
        self.assertIn("## Planning card (stage 6)", (SKILL / "references" / "result-card.md").read_text(encoding="utf-8"))
        planner = (ROOT / "agents" / "planner.md").read_text(encoding="utf-8")
        self.assertIn("first and alone in the plan", planner)
        self.assertIn("touches only its own screen or module", planner)
        self.assertIn("aim for a parallel factor of 2 or more", planner)
        self.assertIn("Name the **shared modules** in the LLD", (ROOT / "agents" / "architect.md").read_text(encoding="utf-8"))

    def test_stages_overlap_and_milestone_cards_leave_no_gap(self):
        # B-44: B's implement starts while A is tested; B-45: next-milestone work while the card waits
        build = (SKILL / "references" / "stage-7-build.md").read_text(encoding="utf-8")
        self.assertIn("**as soon as a task's implement step\nends**", build)
        self.assertIn("**No idle gap while the milestone card waits:**", build)
        self.assertIn("--ready --avoid M<n>", build)
        self.assertIn("let each finish its current step (checkpointed), then restart", build)

    def test_open_tasks_catch_up_after_each_approve(self):
        # B-46: conflicts surfaced only at the final sync, after the whole task was done
        build = (SKILL / "references" / "stage-7-build.md").read_text(encoding="utf-8")
        self.assertIn("**Early sync:** right after it, `$TASKGIT catchup <repo>", build)
        self.assertIn("  catchup)", (SKILL / "scripts" / "taskgit.sh").read_text(encoding="utf-8"))

    def test_plan_vs_actual_files(self):
        # B-43: a task that edits files it didn't declare would let --ready start a colliding task
        build = (SKILL / "references" / "stage-7-build.md").read_text(encoding="utf-8")
        self.assertIn("`$TASKGIT changed <repo> T-xx | python3 $TASKGRAPH <repo>/TASKS.md --undeclared T-xx`", build)
        self.assertIn("add them to its `Files:` in TASKS.md", build)
        self.assertIn("Plan vs actual:", (SKILL / "references" / "result-card.md").read_text(encoding="utf-8"))
        self.assertIn("  changed)", (SKILL / "scripts" / "taskgit.sh").read_text(encoding="utf-8"))

    def test_lld_has_a_size_cap_and_a_narrow_sync(self):
        # B-20: the LLD grew past what any brief reads, and every milestone re-synced all of it
        architect = (ROOT / "agents" / "architect.md").read_text(encoding="utf-8")
        self.assertIn('**Size cap by STATE.md "Size": small 150 lines, medium 400, large 900**', architect)
        self.assertIn("Edit **only the sections that describe those paths**", architect)
        self.assertIn("small 150 lines, medium 400, large 900", (SKILL / "templates" / "LLD.md").read_text(encoding="utf-8"))
        build = (SKILL / "references" / "stage-7-build.md").read_text(encoding="utf-8")
        self.assertIn("changed-files.txt", build)
        self.assertIn("**Skip the sync**", build)

    def test_tasks_are_feature_slices_under_a_cap(self):
        # B-30: run B split features by layer (API task, then screen task), doubling the task count
        planner = (ROOT / "agents" / "planner.md").read_text(encoding="utf-8")
        self.assertIn("**a task is one user-visible feature slice end to end**", planner)
        self.assertIn("never split a feature by layer", planner)
        self.assertIn("which must still be user-visible (the app starts and shows its first screen)", planner)
        self.assertIn('**Task caps by STATE.md "Size": small 8, medium 15, large 30**', planner)
        self.assertIn("`Why separate:`", planner)
        planning = (SKILL / "references" / "stage-1-6-planning.md").read_text(encoding="utf-8")
        self.assertIn("**small 8, medium 15, large 30**", planning)
        self.assertIn("never one layer", (SKILL / "templates" / "TASKS.md").read_text(encoding="utf-8"))
        build = (SKILL / "references" / "stage-7-build.md").read_text(encoding="utf-8")
        self.assertIn("one implement step per owner, in the listed order", build)

    def test_milestones_follow_the_size_and_the_last_one_is_the_handover(self):
        # O4: run B had 4 milestones for 5 tasks; each cost a docs task and a session restart
        # B-31: milestones sit at risk checkpoints only; a small project has one
        planner = (ROOT / "agents" / "planner.md").read_text(encoding="utf-8")
        self.assertIn("milestones only at risk checkpoints (first end-to-end flow working, data model locked, "
                      "first external integration, before deploy)", planner)
        self.assertIn("never just to group tasks; a small project has 1", planner)
        self.assertNotIn("milestones (3–6", planner)
        build = (SKILL / "references" / "stage-7-build.md").read_text(encoding="utf-8")
        self.assertIn("(every milestone but the last)", build)
        self.assertIn("**The last milestone** has no docs task and no milestone card", build)
        handover = (SKILL / "references" / "stage-8-handover.md").read_text(encoding="utf-8")
        self.assertIn("as-built sync of `docs/LLD.md`", handover)

    def test_low_risk_reviews_are_batched_on_small_and_medium_projects(self):
        # O6: one reviewer per milestone for low-risk tasks instead of one per task; every change
        # still gets a review, and high-risk tasks and large projects keep the per-task reviewer
        build = (SKILL / "references" / "stage-7-build.md").read_text(encoding="utf-8")
        step3 = build[build.index("3. **tester and reviewer in parallel.**"):build.index("\n4. ")]
        self.assertIn('**Small and medium projects (STATE.md "Size"): one agent per low-risk task.**', step3)
        self.assertIn("keep the separate tester and per-task reviewer", step3)
        # O5: the coder writes and runs the tests there, opened per task; the gates never open
        self.assertIn("`$TASKGIT coder-tests <repo> T-xx` right after `start`", step3)
        self.assertIn("`Tests: yours`", step3)
        self.assertIn("The gates (`check.sh`, coverage and lint configs) stay closed to the coder", step3)
        # B-34: the tester only comes in when the coder's own run leaves coverage short
        self.assertIn("The **tester spawns only on failure**", step3)
        rules = (SKILL / "references" / "team-rules.md").read_text(encoding="utf-8")
        self.assertIn("except when your brief says `Tests: yours`", rules)
        self.assertIn("Never weaken or delete an existing test", rules)
        self.assertIn("Tests:        <coder only", (SKILL / "references" / "brief-template.md").read_text(encoding="utf-8"))
        self.assertIn("`Tests: coder` also gets", (SKILL / "references" / "resume.md").read_text(encoding="utf-8"))
        self.assertIn("**One per-task exception:**", (ROOT / "docs" / "guardrails.md").read_text(encoding="utf-8"))
        batch = build[build.index("**Batched review** (first"):build.index("**Milestone end ⏸**")]
        self.assertIn('--grep="^Task: $id\\$"', batch)   # the trailer approve writes
        self.assertIn("without opening it", batch)
        self.assertIn("a fix task per affected task", batch)
        self.assertIn("**batched\nreview**", (SKILL / "references" / "stage-8-handover.md").read_text(encoding="utf-8"))

    def test_tester_tests_what_the_task_promises(self):
        # O8: run B wrote 119 tests where a plain session wrote 26 for the same 8/8; output is the
        # priciest token, and coverage is still enforced by check.sh
        tester = (ROOT / "agents" / "tester.md").read_text(encoding="utf-8")
        self.assertIn("one per error path the task adds", tester)
        self.assertIn("Don't test the framework, libraries or language", tester)
        self.assertIn("don't repeat a case another test already covers", tester)
        self.assertIn("scripts/check.sh", tester)

    def test_each_agent_step_costs_two_orchestrator_calls(self):
        # O9: mark + checkpoint + scope + mark + checkpoint took 3–4 Orchestrator turns per step,
        # each re-reading ~76k tokens; `taskgit step` does each end in one call
        core = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        protocol = core[core.index("## Step protocol"):core.index("## Modes")]
        self.assertIn("`$TASKGIT step <repo> <id> <step> started`", protocol)
        self.assertIn('`$TASKGIT step <repo> <id> <step> done|failed <agent> "<note>"`', protocol)
        self.assertNotIn("$TASKGIT checkpoint", protocol)
        self.assertNotIn("$TASKGIT scope", protocol)
        build = (SKILL / "references" / "stage-7-build.md").read_text(encoding="utf-8")
        self.assertIn("step <repo> T-xx test+review done tester", build)
        self.assertIn("step <repo> <id> <step> started", (SKILL / "references" / "checkpointing.md").read_text(encoding="utf-8"))
        self.assertIn("  step)", (SKILL / "scripts" / "taskgit.sh").read_text(encoding="utf-8"))

    def test_agents_read_only_the_sections_their_brief_lists(self):
        # O13: briefs name LLD sections, but Read loads a whole file; every start pays for it
        rules = (SKILL / "references" / "team-rules.md").read_text(encoding="utf-8")
        self.assertIn("read only those sections, not the whole file", rules)
        self.assertIn("Read with `offset` and `limit`", rules)
        self.assertIn("Every agent start pays for what it reads", rules)

    def test_visual_tools_install_while_the_owner_answers(self):
        # O15 (P7): the Chromium install takes minutes; nothing needs it until the first render
        intake = (SKILL / "references" / "stage-0-intake.md").read_text(encoding="utf-8")
        self.assertIn("(`run_in_background`), start it that way and go straight on to step 3", intake)
        self.assertIn("Check that it finished before the first render", intake)

    def test_routine_roles_run_at_lower_effort(self):
        # O18: without `effort`, an agent runs at the session's effort (often high/xhigh); the
        # routine roles don't need it, while design, review, debugging and code keep the session's
        want = {"git-pr": "low", "docs": "medium", "env-setup": "medium", "researcher": "medium", "tester": "medium"}
        levels = {"low", "medium", "high", "xhigh", "max"}
        for p in AGENTS:
            fm = frontmatter(p)
            with self.subTest(agent=fm["name"]):
                self.assertEqual(fm.get("effort"), want.get(fm["name"]))
                if "effort" in fm:
                    self.assertIn(fm["effort"], levels)
        for keep in ("planner", "architect", "reviewer", "debugger", "backend-coder", "frontend-coder"):
            self.assertNotIn("effort", frontmatter(ROOT / "agents" / f"{keep}.md"))

    def test_build_model_tip_only_when_the_owner_chose_cheaper(self):
        # O17: the Orchestrator is ~40% of a run and is the owner's session; Sonnet is half Opus's
        # price. Suggest it once for the build in balanced/fast, never switch it, never in quality.
        modes = (SKILL / "references" / "approval-modes.md").read_text(encoding="utf-8")
        tip = modes[modes.index("## Build model tip"):modes.index("## Things that never")]
        self.assertIn("(`/model sonnet`)", tip)
        self.assertIn("never switch it yourself, and never in `quality`", tip)
        planning = (SKILL / "references" / "stage-1-6-planning.md").read_text(encoding="utf-8")
        self.assertIn("In `balanced` or `fast` cost mode, add the build-model tip", planning)

    def test_quick_track_for_small_ideas(self):
        # D30: small ideas skip the separate HLD, team-pick and LLD stops, never the Tier 1 ones
        planning = (SKILL / "references" / "stage-1-6-planning.md").read_text(encoding="utf-8")
        quick = planning[planning.index("## Quick track"):planning.index("## 2 ·")]
        self.assertIn("at most 5 user stories", planning)
        # O7: runs B and C (9 and 7 stories, 5 tasks) missed it on the story count alone; offer it
        # by size, and keep its one design pass short
        self.assertIn("When the size is **small**", planning)
        self.assertIn("**short**: HLD about one screen", quick)
        self.assertIn("only the sections the tasks will read", (ROOT / "agents" / "architect.md").read_text(encoding="utf-8"))
        self.assertIn("**One design card ⏸:**", quick)
        self.assertIn("Tier 1 never shrinks", quick)
        self.assertIn("installing is Tier 1", quick)
        self.assertIn("**batch-low-risk**", quick)
        self.assertIn("quick track", (SKILL / "SKILL.md").read_text(encoding="utf-8"))

    def test_intake_opens_with_what_happens_next(self):
        # D31: three lines before the first question; no unmeasured cost claims
        intake = (SKILL / "references" / "stage-0-intake.md").read_text(encoding="utf-8")
        self.assertLess(intake.index("three-line opener"), intake.index("One AskUserQuestion call: repo name"))
        self.assertIn("Never state a cost that wasn't measured", intake)

    def test_eval_suite_is_complete_and_runnable(self):
        # D33: every case has a prompt and a grader, and run.sh covers every tag a case uses
        cases = [p.parent for p in (ROOT / "evals").glob("*/prompt.md")]
        self.assertGreaterEqual(len(cases), 4)
        runner = (ROOT / "evals" / "run.sh").read_text(encoding="utf-8")
        for case in cases:
            with self.subTest(case=case.name):
                self.assertTrue(list((case / "graders").glob("*.md")), "a case needs at least one grader")
                meta = frontmatter(case / "prompt.md")
                for tag in meta["tags"]:
                    self.assertIn(f"--tag {tag}", runner)
        self.assertIn("evals/results/", (ROOT / ".gitignore").read_text(encoding="utf-8"))
        self.assertIn("workflow_dispatch", (ROOT / ".github" / "workflows" / "evals.yml").read_text(encoding="utf-8"))

    def test_directory_listing_fields(self):
        # D36: what the directory reads for the listing; the icon is fixed at the first submission
        manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        for key in ("documentationUrl", "supportUrl", "privacyPolicyUrl", "homepage"):
            self.assertTrue(manifest.get(key, "").startswith("https://"), key)
        icon = ROOT / manifest["icon"]
        data = icon.read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        width, height = int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
        self.assertEqual(width, height, "the icon must be square")
        self.assertTrue(512 <= width <= 2048, width)
        self.assertLess(len(data), 2 * 1024 * 1024)
        self.assertTrue(manifest["privacyPolicyUrl"].endswith("docs/PRIVACY.md"))
        self.assertTrue((ROOT / "docs" / "PRIVACY.md").exists())

    def test_autopilot_approves_only_safe_tasks_and_keeps_undo(self):
        # P1: the biggest wait is the owner; autopilot removes it for low-risk, all-✅ tasks only
        manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertIn("autopilot", manifest["userConfig"]["approval_mode"]["options"])
        modes = (SKILL / "references" / "approval-modes.md").read_text(encoding="utf-8")
        auto = modes[modes.index("**autopilot**"):modes.index("## cost_mode")]
        for must in ("low-risk (above) **and** has every goal ✅", "$TASKGIT undo", "Tier 1 never shrinks",
                     "milestone cards and the handover card"):
            self.assertIn(must, auto)
        self.assertIn("taskgit.sh undo", (SKILL / "scripts" / "taskgit.sh").read_text(encoding="utf-8"))
        self.assertIn("autopilot", (SKILL / "references" / "stage-7-build.md").read_text(encoding="utf-8"))

    def test_modes_are_in_the_core(self):
        # Run C (fast + autopilot) ran like the defaults: the rules lived only in approval-modes.md,
        # which nothing made the Orchestrator read before spawning. The core is always read.
        core = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        modes = core[core.index("## Modes"):core.index("## Context budget")]
        for must in ('**fast**', 'model: "sonnet"', "except planner and architect", "Opus reviewer",
                     "**autopilot**", "Auto-approved <id> · Undo?", "**balanced**", "**batch-low-risk**",
                     "STATE.md win over Config", "references/approval-modes.md"):
            self.assertIn(must, modes)
        protocol = core[core.index("## Step protocol"):core.index("## Modes")]
        self.assertIn("`model:` per **Modes**", protocol)

    def test_independent_tasks_start_in_one_message(self):
        # P2: agents only run concurrently when spawned in the same message
        build = (SKILL / "references" / "stage-7-build.md").read_text(encoding="utf-8")
        block = build[build.index("**Schedule from the graph"):build.index("**Don't let the team idle")]
        self.assertIn("same message", block)
        self.assertIn("one Agent call per task", block)
        # B-36: the graph decides what is independent (T-17/T-18 shared a file nobody noticed)
        self.assertIn("`python3 $TASKGRAPH <repo>/TASKS.md --ready`", block)
        self.assertIn("up to\n3 running in total, longest remaining chain first", block)
        self.assertIn("run `--ready` again", block)
        self.assertIn("`Status: In progress` in TASKS.md", build)
        self.assertIn("TASKGRAPH=<root>/skills/setup-project/scripts/taskgraph.py", (SKILL / "SKILL.md").read_text(encoding="utf-8"))

    def test_fast_mode_keeps_design_and_risky_reviews_strong(self):
        # P3: faster models for mechanical roles, never for the design or high-risk reviews
        modes = (SKILL / "references" / "approval-modes.md").read_text(encoding="utf-8")
        fast = modes[modes.index("**fast**"):modes.index("## Things that never")]
        self.assertIn("**except planner and\n  architect**", fast)
        self.assertIn("**High-risk tasks still get an Opus reviewer.**", fast)
        # every Opus agent other than planner/architect is one that fast mode may downgrade
        opus = {frontmatter(p)["name"] for p in AGENTS if frontmatter(p).get("model") == "opus"}
        for name in opus - {"planner", "architect"}:
            self.assertIn(name, fast, f"fast mode doesn't say what happens to {name}")

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
