"""taskgraph.py: waves, overlap splits, the cap, the critical path, ready tasks, undeclared files.

Run: python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TG = ROOT / "skills" / "setup-project" / "scripts" / "taskgraph.py"

# A Recipe Box-shaped plan: one foundation task, then feature slices that touch their own module.
RECIPE_BOX = """# TASKS — recipe-box

## M1 · Recipes you can keep

### T-01 · App starts and shows the recipe list (foundation)
- Owner: backend-coder, frontend-coder
- Depends on: —
- Files: src/app.py, src/db.py, src/shared/*, web/index.html, web/shared/*
- Status: Done

### T-02 · Add a recipe
- Owner: backend-coder, frontend-coder
- Depends on: T-01
- Files: src/recipes/create.py, web/add-recipe.js, tests/test_create.py
- Status: In progress

### T-03 · Search recipes
- Owner: backend-coder, frontend-coder
- Depends on: T-01
- Files: src/search/*, web/search.js, tests/test_search.py
- Status: Backlog

### T-04 · Scale servings
- Owner: frontend-coder
- Depends on: T-02
- Files: web/scale.js, tests/scale.test.js
- Status: Backlog

### T-05 · Favourite a recipe
- Owner: backend-coder, frontend-coder
- Depends on: T-01
- Files: src/favourites/*, web/favourite-toggle.js, tests/test_favourites.py
- Status: Backlog

### T-06 · Favourites page
- Owner: frontend-coder
- Depends on: T-05
- Files: web/favourite-toggle.js, web/favourites.html
- Status: Backlog

### T-07 · Export to a file
- Owner: backend-coder
- Depends on: T-02
- Files: src/export/*, tests/test_export.py
- Status: Backlog
"""


def task(tid: str, deps: str = "—", files: str = "", status: str = "Backlog") -> str:
    return (f"### {tid} · task {tid}\n- Owner: backend-coder\n- Depends on: {deps}\n"
            f"- Files: {files or 'src/' + tid.lower() + '.py'}\n- Status: {status}\n\n")


class TaskGraphTest(unittest.TestCase):
    def run_tg(self, text: str, *args: str, stdin: str = "") -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "TASKS.md"
            p.write_text(text, encoding="utf-8")
            return subprocess.run([sys.executable, str(TG), str(p), *args], input=stdin,
                                  capture_output=True, text=True, encoding="utf-8")

    def graph(self, text: str, *args: str) -> dict:
        r = self.run_tg(text, "--json", *args)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_recipe_box_parses_into_a_foundation_and_parallel_rounds(self):
        g = self.graph(RECIPE_BOX)
        self.assertEqual(g["waves"][0], ["T-01"])
        # T-02, T-03, T-05 depend only on the foundation and share no files: one round
        self.assertEqual(sorted(g["waves"][1]), ["T-02", "T-03", "T-05"])
        # T-04 and T-07 follow T-02; T-06 follows T-05 but shares favourite-toggle.js with nobody running
        self.assertEqual(sorted(g["waves"][2]), ["T-04", "T-06", "T-07"])
        self.assertEqual(g["parallel_factor"], round(7 / 3, 2))
        self.assertEqual(g["warnings"], [])
        t1 = next(t for t in g["tasks"] if t["id"] == "T-01")
        self.assertEqual(t1["owner"], ["backend-coder", "frontend-coder"])
        self.assertEqual(t1["status"], "Done")

    def test_tasks_sharing_a_file_never_share_a_wave(self):
        # the T-17/T-18 collision: two tasks both edited favourite-toggle.js in the same round
        text = (task("T-01") + task("T-02", "T-01", "web/favourite-toggle.js, web/a.js")
                + task("T-03", "T-01", "web/favourite-toggle.js") + task("T-04", "T-01", "web/*.css"))
        g = self.graph(text)
        for wave in g["waves"]:
            self.assertFalse({"T-02", "T-03"} <= set(wave), wave)
        # a glob overlaps the paths it matches
        text = task("T-01", files="src/recipes/*") + task("T-02", files="src/recipes/create.py")
        self.assertEqual(len(self.graph(text)["waves"]), 2)
        # a folder overlaps what's inside it
        text = task("T-01", files="src/recipes") + task("T-02", files="src/recipes/create.py")
        self.assertEqual(len(self.graph(text)["waves"]), 2)

    def test_no_wave_holds_more_than_the_cap(self):
        text = task("T-01") + "".join(task(f"T-{n:02d}", "T-01") for n in range(2, 9))
        g = self.graph(text)
        self.assertEqual([len(w) for w in g["waves"]], [1, 3, 3, 1])
        g = self.graph(text, "--max", "2")
        self.assertTrue(all(len(w) <= 2 for w in g["waves"]))

    def test_critical_path_is_the_longest_chain(self):
        text = (task("T-01") + task("T-02", "T-01") + task("T-03", "T-02") + task("T-04", "T-03")
                + task("T-05", "T-01") + task("T-06"))
        self.assertEqual(self.graph(text)["critical_path"], ["T-01", "T-02", "T-03", "T-04"])

    def test_a_serial_plan_is_flagged(self):
        text = task("T-01") + task("T-02", "T-01") + task("T-03", "T-02") + task("T-04", "T-03")
        g = self.graph(text)
        self.assertEqual(g["parallel_factor"], 1.0)
        self.assertIn("under 1.5", g["warnings"][0])

    def test_cycles_unknown_ids_and_missing_fields_are_rejected(self):
        r = self.run_tg(task("T-01", "T-03") + task("T-02", "T-01") + task("T-03", "T-02"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("dependency cycle: T-01 → T-03 → T-02 → T-01", r.stderr)
        r = self.run_tg(task("T-01", "T-09"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("unknown task IDs in Depends on: T-01 → T-09", r.stderr)
        for field in ("Owner", "Depends on", "Files"):
            with self.subTest(missing=field):
                text = "\n".join(ln for ln in task("T-01").splitlines() if not ln.startswith(f"- {field}:"))
                r = self.run_tg(text)
                self.assertEqual(r.returncode, 2)
                self.assertIn(f"T-01 ({field.title()})", r.stderr)
        self.assertEqual(self.run_tg("# nothing here\n").returncode, 2)

    def test_ready_picks_unblocked_tasks_that_share_no_files_with_running_ones(self):
        ready = self.run_tg(RECIPE_BOX, "--ready").stdout.split()
        # T-02 is running; T-03 and T-05 are free; T-04/T-07 wait for T-02, T-06 for T-05
        self.assertEqual(sorted(ready), ["T-03", "T-05"])
        # running T-05 blocks a task with an overlapping file even when its dependency is Done
        text = (task("T-01", status="Done") + task("T-02", "T-01", "web/fav.js", "In progress")
                + task("T-03", "T-01", "web/fav.js") + task("T-04", "T-01", "web/b.js"))
        self.assertEqual(self.run_tg(text, "--ready").stdout.split(), ["T-04"])
        # never more than --max running in total; longest remaining chain first
        text = (task("T-01", status="Done") + task("T-02", "T-01") + task("T-03", "T-01")
                + task("T-04", "T-01") + task("T-05", "T-04"))
        self.assertEqual(self.run_tg(text, "--ready", "--max", "2").stdout.split(), ["T-04", "T-02"])
        out = json.loads(self.run_tg(text, "--ready", "--json").stdout)
        self.assertEqual([t["id"] for t in out], ["T-04", "T-02", "T-03"])

    def test_ready_stays_in_the_current_milestone_and_can_avoid_one_under_review(self):
        def ms(n: int, body: str) -> str:
            return f"## M{n} · part {n}\n\n{body}"
        text = (ms(1, task("T-01", status="Done") + task("T-02", "T-01", "src/list.py")) +
                ms(2, task("T-03", "T-01", "src/list.py") + task("T-04", "T-01", "src/search.py")))
        # M1 still has T-02 open: M2 waits
        self.assertEqual(self.run_tg(text, "--ready").stdout.split(), ["T-02"])
        # M1 done, its card waiting: M2 tasks may start, except one touching M1's files
        text = text.replace("- Files: src/list.py\n- Status: Backlog", "- Files: src/list.py\n- Status: Done", 1)
        self.assertEqual(sorted(self.run_tg(text, "--ready").stdout.split()), ["T-03", "T-04"])
        self.assertEqual(self.run_tg(text, "--ready", "--avoid", "M1").stdout.split(), ["T-04"])

    def test_undeclared_files_are_reported(self):
        r = self.run_tg(RECIPE_BOX, "--undeclared", "T-03",
                        stdin="src/search/index.py\nweb/search.js\nweb/favourite-toggle.js\n")
        self.assertEqual(r.stdout.split(), ["web/favourite-toggle.js"])
        r = self.run_tg(RECIPE_BOX, "--undeclared", "T-03", stdin="src/search/index.py\n")
        self.assertEqual(r.stdout.strip(), "")
        self.assertEqual(self.run_tg(RECIPE_BOX, "--undeclared", "T-99").returncode, 1)

    def test_card_outputs(self):
        m = self.run_tg(RECIPE_BOX, "--mermaid").stdout
        self.assertTrue(m.startswith("flowchart LR"))
        self.assertIn('subgraph R2["Round 2"]', m)
        self.assertIn("class T_01,", m)
        self.assertIn("classDef critical", m)
        self.assertIn("==>", m)
        s = self.run_tg(RECIPE_BOX, "--summary").stdout
        self.assertIn("Round 1: 1 task on its own (T-01)", s)
        self.assertIn("Round 2: 3 features at the same time", s)
        self.assertIn("Parallel factor: 2.33 (7 tasks in 3 rounds)", s)

    def test_runs_on_the_planning_template(self):
        tmpl = (ROOT / "skills" / "setup-project" / "templates" / "TASKS.md").read_text(encoding="utf-8")
        self.assertEqual(self.run_tg(tmpl).returncode, 0)


if __name__ == "__main__":
    unittest.main()
