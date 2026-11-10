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


def load_capture():
    """Import capture.py as a module (it needs no third-party packages at import time)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("capture", CAP)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class CaptureHelpersTest(unittest.TestCase):
    def test_term_cmd_times_out(self):
        # C4: a command that never ends (a server) hung `term --cmd` forever
        import time
        cap = load_capture()
        slow = f'"{sys.executable}" -c "import time; print(\'started\', flush=True); time.sleep(60)"'
        t0 = time.time()
        text = cap.run_cmd(slow, None, 2)
        self.assertLess(time.time() - t0, 30)
        self.assertIn("timed out after 2s", text)
        self.assertIn("started", text)            # output before the timeout is kept
        self.assertIn("[exit 0]", cap.run_cmd(f'"{sys.executable}" -c "print(1)"', None, 30))


class TermColorsTest(unittest.TestCase):
    # C6: ANSI codes weren't stripped and "0 failed" / "no errors" were painted red
    RED, GREEN, YELLOW, PLAIN = "#ff7b72", "#7ee787", "#d29922", "#e6edf3"

    def test_strip_ansi(self):
        cap = load_capture()
        self.assertEqual(cap.strip_ansi("\x1b[32m5 passed\x1b[0m in 0.1s"), "5 passed in 0.1s")
        self.assertEqual(cap.strip_ansi("\x1b]8;;http://x\x07link\x1b]8;;\x07"), "link")

    def test_line_colors(self):
        cap = load_capture()
        cases = {
            "===== 5 passed, 0 failed in 0.21s =====": self.GREEN,
            "Found no errors": self.GREEN,
            "Success: no issues found in 12 source files": self.GREEN,
            "1 failed, 4 passed": self.RED,
            "Traceback (most recent call last):": self.RED,
            "src/errorhandler.py ok": self.GREEN,          # "error" inside a word isn't an error
            "terrorist_detector.py": self.PLAIN,
            "2 warnings": self.YELLOW,
            "$ pytest -q": "#79c0ff",
        }
        for line, want in cases.items():
            with self.subTest(line=line):
                self.assertEqual(cap.line_color(line), want)


class FontTest(unittest.TestCase):
    def test_font_found_on_every_os(self):
        # C7: only a Debian path was tried; macOS and Windows got a tiny bitmap font
        cap = load_capture()
        joined = " ".join(cap.MONO_FONTS)
        for marker in ("DejaVuSansMono", "Menlo", "consola"):
            self.assertIn(marker, joined)
        found = cap.find_mono_font()
        self.assertTrue(found is None or Path(found).is_file())
        with tempfile.NamedTemporaryFile(suffix=".ttf", delete=False) as f:
            pass
        try:
            os.environ["DEVTEAM_FONT"] = f.name
            self.assertEqual(cap.find_mono_font(), f.name)   # an explicit font wins
        finally:
            del os.environ["DEVTEAM_FONT"]
            os.unlink(f.name)


class SandboxTest(unittest.TestCase):
    def test_sandbox_only_dropped_when_needed(self):
        # C8: Chromium always ran with --no-sandbox
        cap = load_capture()
        needed = (hasattr(os, "geteuid") and os.geteuid() == 0) or cap.in_container()
        self.assertEqual(cap.chromium_args(), ["--no-sandbox"] if needed else [])
        os.environ["DEVTEAM_NO_SANDBOX"] = "1"
        try:
            self.assertEqual(cap.chromium_args(), ["--no-sandbox"])
        finally:
            del os.environ["DEVTEAM_NO_SANDBOX"]
        self.assertNotIn('launch(args=["--no-sandbox"])', CAP.read_text(encoding="utf-8"))


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

    def test_no_networkidle_waits(self):
        # C5: hot-reload and long-polling dev servers never go network-idle, so captures timed out
        self.assertNotIn("networkidle", CAP.read_text(encoding="utf-8"))

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
