"""capture.py tests that need no browser: CLI shape, the dependency doctor, and the venv switch.

Run: python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAP = ROOT / "skills" / "setup-project" / "scripts" / "capture.py"


def run(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(CAP), *args], capture_output=True, text=True,
                          env={**os.environ, **(env or {})}, timeout=120)


class CaptureCliTest(unittest.TestCase):
    def test_help_lists_doctor(self):
        p = run("--help")
        self.assertEqual(p.returncode, 0)
        self.assertIn("doctor", p.stdout)

    def test_doctor_reports_without_installing(self):
        # C1: a doctor check at intake instead of an ImportError at the first visual
        with tempfile.TemporaryDirectory() as d:
            p = run("doctor", env={"CLAUDE_PLUGIN_DATA": d})
            self.assertIn(p.returncode, (0, 1), p.stderr)
            if p.returncode:
                self.assertIn("missing:", p.stdout)
                self.assertIn("doctor --install", p.stdout)
                self.assertIn(str(Path(d) / "venv"), p.stdout)
            else:
                self.assertIn("ready", p.stdout)
            self.assertFalse((Path(d) / "venv").exists())   # checking never installs

    def test_installs_only_in_doctor(self):
        # C3: `playwright install chromium` and `npm install mermaid@11` ran mid-task, unpinned
        import ast
        import re
        tree = ast.parse(CAP.read_text(encoding="utf-8"))
        for fn in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name != "cmd_doctor"):
            for call in (n for n in ast.walk(fn) if isinstance(n, ast.Call)):
                words = {c.value for c in ast.walk(call) if isinstance(c, ast.Constant) and isinstance(c.value, str)}
                with self.subTest(function=fn.name):
                    self.assertNotIn("install", words, f"{fn.name} installs something at runtime")
        self.assertRegex(CAP.read_text(encoding="utf-8"), r'MERMAID = "mermaid@\d+\.\d+\.\d+"')

    def test_venv_is_used_when_deps_are_missing(self):
        # a fake "venv python" that just reports it was used
        with tempfile.TemporaryDirectory() as d:
            vp = Path(d) / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            vp.parent.mkdir(parents=True)
            if os.name == "nt":
                self.skipTest("needs a POSIX shell script as the fake interpreter")
            vp.write_text("#!/bin/sh\necho \"venv used: $DEVTEAM_CAPTURE_IN_VENV\"\n")
            vp.chmod(0o755)
            code = ("import importlib.util, runpy, sys; real = importlib.util.find_spec; "
                    "importlib.util.find_spec = lambda m, *a: None if m == 'markdown' else real(m, *a); "
                    f"sys.argv = ['capture.py', 'md', 'in.md', 'out.png']; runpy.run_path({str(CAP)!r}, run_name='__main__')")
            p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                               env={**os.environ, "CLAUDE_PLUGIN_DATA": d})
            self.assertIn("venv used: 1", p.stdout, p.stderr)


if __name__ == "__main__":
    unittest.main()
