#!/usr/bin/env python3
"""Visual capture helper for /setup-project result cards.

Subcommands (all write PNGs; print the output paths):
  web     URL OUT_PREFIX [--mobile] [--full-page] [--wait-for SELECTOR] [--delay MS]
          Screenshot a running web page at desktop (1440x900) and optionally mobile (390x844).
  term    OUT.png (--cmd "pytest -q" | --file log.txt | stdin) [--title T] [--max-lines N] [--cwd DIR] [--timeout S]
          Render terminal output as a dark terminal image.
  mermaid IN.mmd OUT.png [--width PX]
          Render a Mermaid diagram (needs mermaid from `doctor --install`).
  md      IN.md OUT.png [--width PX]
          Render Markdown (tables, cards, package lists) as a clean image.
  html    IN.html OUT.png [--width PX]
          Screenshot a local HTML file (e.g. plotly/Altair exports, coverage reports).

  doctor  [--install]
          Check the dependencies below; --install puts them in a private venv
          (${CLAUDE_PLUGIN_DATA}/venv) that the other subcommands then use automatically.

Requires: playwright (Python) with Chromium; pillow; markdown; npm for mermaid.
"""
from __future__ import annotations  # `str | None` annotations on Python 3.9 (macOS's python3)

import argparse
import html as htmllib
import os
import re
import subprocess
import sys
from pathlib import Path

CACHE = Path(os.environ.get("DEVTEAM_CACHE", Path.home() / ".cache" / "dev-team-setup"))
# The plugin's own Python deps live in a private venv, not in the project's or the system's
# Python (PEP 668 blocks a plain `pip install` on modern Ubuntu, Debian and Homebrew).
DATA = Path(os.environ.get("CLAUDE_PLUGIN_DATA") or CACHE)
VENV = DATA / "venv"
PY_DEPS = {"playwright": "playwright==1.49.1", "PIL": "pillow==11.0.0", "markdown": "markdown==3.7"}
MERMAID = "mermaid@11.4.1"   # pinned (C3); installed by `doctor --install`, never mid-task
MERMAID_JS = CACHE / "node_modules" / "mermaid" / "dist" / "mermaid.min.js"


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def missing_modules() -> list[str]:
    import importlib.util
    return [m for m in PY_DEPS if importlib.util.find_spec(m) is None]


def use_venv_if_needed() -> None:
    """Re-run this script under the plugin venv when the current Python lacks the deps."""
    vp = venv_python()
    if (missing_modules() and vp.exists() and os.environ.get("DEVTEAM_CAPTURE_IN_VENV") != "1"
            and Path(sys.executable).resolve() != vp.resolve()):
        env = {**os.environ, "DEVTEAM_CAPTURE_IN_VENV": "1"}
        sys.exit(subprocess.run([str(vp), str(Path(__file__).resolve()), *sys.argv[1:]], env=env).returncode)


def cmd_doctor(a):
    """Check (and with --install, set up) everything capture.py needs. Exit 0 when ready."""
    if a.install:
        if not venv_python().exists():
            subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
        py = str(venv_python())
        subprocess.run([py, "-m", "pip", "install", "-q", *PY_DEPS.values()], check=True)
        subprocess.run([py, "-m", "playwright", "install", "chromium"], check=True)
        from shutil import which
        if which("npm") and not MERMAID_JS.exists():
            CACHE.mkdir(parents=True, exist_ok=True)
            subprocess.run(["npm", "install", "--prefix", str(CACHE), MERMAID, "--silent", "--no-audit", "--no-fund"], check=True)
        os.environ["DEVTEAM_CAPTURE_IN_VENV"] = "1"
        return subprocess.run([py, str(Path(__file__).resolve()), "doctor"]).returncode
    problems = [f"python module {m} ({PY_DEPS[m]})" for m in missing_modules()]
    if "playwright" not in missing_modules():
        try:
            pw, browser = _browser()
            browser.close(); pw.stop()
        except (Exception, SystemExit) as exc:  # noqa: BLE001 - any launch failure means "not ready"
            problems.append(f"Chromium for Playwright ({type(exc).__name__})")
    from shutil import which
    if not which("npm"):
        problems.append("npm (only needed for Mermaid diagrams)")
    elif not MERMAID_JS.exists():
        problems.append(f"{MERMAID} (only needed for Mermaid diagrams)")
    for p in problems:
        print(f"missing: {p}")
    if problems:
        print(f"fix: python3 {Path(__file__).resolve()} doctor --install   (venv: {VENV})")
        return 1
    print(f"capture.py ready (python: {sys.executable})")
    return 0

CSS = """
body{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:0;padding:28px;
background:#ffffff;color:#1f2328;font-size:16px;line-height:1.5}
table{border-collapse:collapse;margin:8px 0;width:100%}
th,td{border:1px solid #d0d7de;padding:8px 12px;text-align:left;vertical-align:top}
th{background:#f6f8fa;font-weight:600}
tr:nth-child(even) td{background:#fbfcfd}
code,pre{font-family:'DejaVu Sans Mono',Menlo,monospace;font-size:14px}
pre{background:#f6f8fa;padding:12px;border-radius:6px;overflow:auto}
h1,h2,h3{margin:12px 0 8px}
"""


def _browser():
    """Launch Chromium. Never installs it mid-task (C3): that's `doctor --install`'s job."""
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    try:
        browser = pw.chromium.launch(args=["--no-sandbox"])
    except Exception as exc:
        pw.stop()
        raise SystemExit(f"Chromium isn't installed for Playwright ({type(exc).__name__}). "
                         f"Run: python3 {Path(__file__).resolve()} doctor --install") from exc
    return pw, browser


def _shot_html(content: str, out: str, width: int, base_url: str | None = None):
    pw, browser = _browser()
    try:
        page = browser.new_page(viewport={"width": width, "height": 40}, device_scale_factor=2)
        if base_url:
            page.goto(base_url)
        else:
            page.set_content(content, wait_until="load")
        page.wait_for_timeout(300)
        page.screenshot(path=out, full_page=True)
    finally:
        browser.close()
        pw.stop()
    print(out)


def cmd_web(a):
    pw, browser = _browser()
    outs = []
    try:
        views = [("desktop", {"width": 1440, "height": 900}, 1)]
        if a.mobile:
            views.append(("mobile", {"width": 390, "height": 844}, 3))
        for name, vp, scale in views:
            ctx = browser.new_context(viewport=vp, device_scale_factor=scale,
                                      is_mobile=(name == "mobile"), has_touch=(name == "mobile"))
            page = ctx.new_page()
            # C5: dev servers with hot-reload or long-polling never go network-idle; wait for the
            # load event, then for --wait-for if the caller named what "ready" looks like
            page.goto(a.url, wait_until="load", timeout=30000)
            if a.wait_for:
                page.wait_for_selector(a.wait_for, timeout=15000)
            page.wait_for_timeout(a.delay)
            out = f"{a.out_prefix}-{name}.png"
            page.screenshot(path=out, full_page=a.full_page)
            outs.append(out)
            ctx.close()
    finally:
        browser.close()
        pw.stop()
    print("\n".join(outs))


ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(\x07|\x1b\\)|\x1b[@-Z\\-_]")
ZERO_BAD = re.compile(r"\b(0|no|zero) (failed|failures?|errors?|warnings?)\b|\bwithout errors\b")
BAD = re.compile(r"\b(errors?|failed|failures?|failing|traceback|exception|fatal|panic)\b")
GOOD = re.compile(r"\b(passed|passing|ok|success|successful|succeeded|done)\b|✓|✅")
WARN = re.compile(r"\bwarn(ings?)?\b")


def strip_ansi(text: str) -> str:
    """C6: colour codes from pytest, npm, ruff … rendered as garbage like `[32m`."""
    return ANSI.sub("", text)


def line_color(line: str) -> str:
    """Colour a terminal line by meaning, using whole words: "0 failed" and "no errors" are good news."""
    low = line.lower()
    if line.startswith("$ "):
        return "#79c0ff"
    if ZERO_BAD.search(low) and not BAD.search(ZERO_BAD.sub("", low)):
        return "#7ee787"
    if BAD.search(low):
        return "#ff7b72"
    if GOOD.search(low):
        return "#7ee787"
    if WARN.search(low):
        return "#d29922"
    return "#e6edf3"


# C7: the font used to be a Linux-only path; elsewhere the fallback was a tiny bitmap font
MONO_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",            # Debian / Ubuntu
    "/usr/share/fonts/dejavu-sans-mono-fonts/DejaVuSansMono.ttf",     # Fedora
    "/usr/share/fonts/TTF/DejaVuSansMono.ttf",                        # Arch
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    "/System/Library/Fonts/Menlo.ttc", "/System/Library/Fonts/Monaco.ttf",   # macOS
    "/Library/Fonts/Andale Mono.ttf",
    "C:/Windows/Fonts/consola.ttf", "C:/Windows/Fonts/cour.ttf",      # Windows
]


def find_mono_font() -> str | None:
    for f in [os.environ.get("DEVTEAM_FONT", ""), *MONO_FONTS]:
        if f and Path(f).is_file():
            return f
    return None


def load_mono_font(image_font, size: int):
    path = find_mono_font()
    if path:
        return image_font.truetype(path, size)
    try:
        return image_font.load_default(size=size)   # Pillow >= 10.1: a scalable default font
    except TypeError:
        return image_font.load_default()


def run_cmd(cmd: str, cwd: str | None, timeout: float) -> str:
    """Run `cmd` through the shell and return the transcript to render. C4: a command that never
    ends (e.g. one that starts a server) is stopped after `timeout` seconds, with its whole
    process group, instead of hanging the capture forever."""
    import signal
    posix = os.name != "nt"
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         errors="replace", cwd=cwd, start_new_session=posix)
    try:
        out, _ = p.communicate(timeout=timeout)
        status = f"exit {p.returncode}"
    except subprocess.TimeoutExpired:
        if posix:
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
        out, _ = p.communicate()
        status = f"timed out after {timeout:g}s and was stopped"
    return f"$ {cmd}\n" + (out or "") + f"\n[{status}]"


def cmd_term(a):
    from PIL import Image, ImageDraw, ImageFont
    if a.cmd:
        text = run_cmd(a.cmd, a.cwd, a.timeout)
    elif a.file:
        text = Path(a.file).read_text(errors="replace")
    else:
        text = sys.stdin.read()
    lines = strip_ansi(text).expandtabs(4).splitlines() or [""]
    if len(lines) > a.max_lines:
        half = a.max_lines // 2
        lines = lines[:half] + [f"... ({len(lines) - a.max_lines} lines omitted) ..."] + lines[-half:]
    lines = [ln[:160] for ln in lines]
    font = load_mono_font(ImageFont, 28)
    cw = font.getbbox("M")[2]
    lh = font.getbbox("Mgy|")[3] + 10   # from the font itself, not a fixed 38 px
    title_h = 56
    width = max(900, min(160, max(len(ln) for ln in lines)) * cw + 64)
    height = title_h + len(lines) * lh + 40
    img = Image.new("RGB", (width, height), "#0d1117")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, width, title_h], fill="#161b22")
    for i, c in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        d.ellipse([20 + i * 34, 18, 40 + i * 34, 38], fill=c)
    if a.title:
        d.text((130, 12), a.title, font=font, fill="#8b949e")
    y = title_h + 20
    for ln in lines:
        d.text((32, y), ln, font=font, fill=line_color(ln))
        y += lh
    img.save(a.out)
    print(a.out)


def _mermaid_js() -> Path:
    if not MERMAID_JS.exists():
        raise SystemExit(f"{MERMAID} isn't installed. Run: python3 {Path(__file__).resolve()} doctor --install")
    return MERMAID_JS


def cmd_mermaid(a):
    js = _mermaid_js().read_text()
    src = htmllib.escape(Path(a.input).read_text())
    page = f"""<html><head><style>body{{margin:0;padding:24px;background:#fff}}</style>
<script>{js}</script></head><body><pre class="mermaid">{src}</pre>
<script>mermaid.initialize({{startOnLoad:false,theme:'default'}});
mermaid.run().then(()=>document.body.setAttribute('data-done','1'))
 .catch(e=>{{document.body.innerText='Mermaid error: '+e;document.body.setAttribute('data-done','1')}});</script>
</body></html>"""
    from playwright.sync_api import sync_playwright  # noqa: F401
    pw, browser = _browser()
    try:
        p = browser.new_page(viewport={"width": a.width, "height": 600}, device_scale_factor=2)
        p.set_content(page)
        p.wait_for_selector("body[data-done='1']", timeout=20000)
        el = p.query_selector("svg") or p.query_selector("body")
        el.screenshot(path=a.out)
        if not p.query_selector("svg"):
            print("WARNING: mermaid failed to render; see image text", file=sys.stderr)
    finally:
        browser.close()
        pw.stop()
    print(a.out)


def cmd_md(a):
    import markdown
    body = markdown.markdown(Path(a.input).read_text(), extensions=["tables", "fenced_code"])
    _shot_html(f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>",
               a.out, a.width)


def cmd_html(a):
    _shot_html("", a.out, a.width, base_url=Path(a.input).resolve().as_uri())


def main():
    # allow_abbrev=False: the scope guard inspects --cmd; a prefix like --cm must not slip past it
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                 allow_abbrev=False)
    sub = ap.add_subparsers(dest="cmd_name", required=True)

    w = sub.add_parser("web", allow_abbrev=False); w.add_argument("url"); w.add_argument("out_prefix")
    w.add_argument("--mobile", action="store_true"); w.add_argument("--full-page", action="store_true")
    w.add_argument("--wait-for"); w.add_argument("--delay", type=int, default=500)
    w.set_defaults(fn=cmd_web)

    t = sub.add_parser("term", allow_abbrev=False); t.add_argument("out"); t.add_argument("--cmd"); t.add_argument("--file")
    t.add_argument("--title", default=""); t.add_argument("--max-lines", type=int, default=60)
    t.add_argument("--cwd"); t.add_argument("--timeout", type=float, default=120,
                                            help="stop --cmd after this many seconds (default 120)")
    t.set_defaults(fn=cmd_term)

    m = sub.add_parser("mermaid", allow_abbrev=False); m.add_argument("input"); m.add_argument("out")
    m.add_argument("--width", type=int, default=1400); m.set_defaults(fn=cmd_mermaid)

    d = sub.add_parser("md", allow_abbrev=False); d.add_argument("input"); d.add_argument("out")
    d.add_argument("--width", type=int, default=900); d.set_defaults(fn=cmd_md)

    h = sub.add_parser("html", allow_abbrev=False); h.add_argument("input"); h.add_argument("out")
    h.add_argument("--width", type=int, default=1200); h.set_defaults(fn=cmd_html)

    doc = sub.add_parser("doctor", allow_abbrev=False)
    doc.add_argument("--install", action="store_true", help="create the plugin venv and install everything")
    doc.set_defaults(fn=cmd_doctor)

    a = ap.parse_args()
    if a.cmd_name != "doctor":
        use_venv_if_needed()
    sys.exit(a.fn(a) or 0)


if __name__ == "__main__":
    main()
