#!/usr/bin/env python3
"""Visual capture helper for /setup-project result cards.

Subcommands (all write PNGs; print the output paths):
  web     URL OUT_PREFIX [--mobile] [--full-page] [--wait-for SELECTOR] [--delay MS]
          Screenshot a running web page at desktop (1440x900) and optionally mobile (390x844).
  term    OUT.png (--cmd "pytest -q" | --file log.txt | stdin) [--title T] [--max-lines N] [--cwd DIR]
          Render terminal output as a dark terminal image.
  mermaid IN.mmd OUT.png [--width PX]
          Render a Mermaid diagram (installs mermaid via npm into a cache dir on first use).
  md      IN.md OUT.png [--width PX]
          Render Markdown (tables, cards, package lists) as a clean image.
  html    IN.html OUT.png [--width PX]
          Screenshot a local HTML file (e.g. plotly/Altair exports, coverage reports).

Requires: playwright (Python) with Chromium; markdown; npm for mermaid.
"""
import argparse
import html as htmllib
import os
import subprocess
import sys
from pathlib import Path

CACHE = Path(os.environ.get("DEVTEAM_CACHE", Path.home() / ".cache" / "dev-team-setup"))

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
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    try:
        browser = pw.chromium.launch(args=["--no-sandbox"])
    except Exception:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=False)
        browser = pw.chromium.launch(args=["--no-sandbox"])
    return pw, browser


def _shot_html(content: str, out: str, width: int, base_url: str | None = None):
    pw, browser = _browser()
    try:
        page = browser.new_page(viewport={"width": width, "height": 40}, device_scale_factor=2)
        if base_url:
            page.goto(base_url)
        else:
            page.set_content(content, wait_until="networkidle")
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
            page.goto(a.url, wait_until="networkidle", timeout=30000)
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


def cmd_term(a):
    from PIL import Image, ImageDraw, ImageFont
    if a.cmd:
        r = subprocess.run(a.cmd, shell=True, capture_output=True, text=True, cwd=a.cwd)
        text = f"$ {a.cmd}\n" + r.stdout + r.stderr + f"\n[exit {r.returncode}]"
    elif a.file:
        text = Path(a.file).read_text(errors="replace")
    else:
        text = sys.stdin.read()
    lines = text.expandtabs(4).splitlines() or [""]
    if len(lines) > a.max_lines:
        half = a.max_lines // 2
        lines = lines[:half] + [f"... ({len(lines) - a.max_lines} lines omitted) ..."] + lines[-half:]
    lines = [ln[:160] for ln in lines]
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
    font = ImageFont.truetype(font_path, 28) if Path(font_path).exists() else ImageFont.load_default()
    cw = font.getbbox("M")[2]
    lh = 38
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
        low = ln.lower()
        color = "#e6edf3"
        if ln.startswith("$ "):
            color = "#79c0ff"
        elif any(k in low for k in ("error", "failed", "traceback", "exception")):
            color = "#ff7b72"
        elif any(k in low for k in ("passed", " ok", "success", "done", "✓")):
            color = "#7ee787"
        elif "warn" in low:
            color = "#d29922"
        d.text((32, y), ln, font=font, fill=color)
        y += lh
    img.save(a.out)
    print(a.out)


def _mermaid_js() -> Path:
    js = CACHE / "node_modules" / "mermaid" / "dist" / "mermaid.min.js"
    if not js.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        subprocess.run(["npm", "install", "--prefix", str(CACHE), "mermaid@11", "--silent"], check=True)
    return js


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
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd_name", required=True)

    w = sub.add_parser("web"); w.add_argument("url"); w.add_argument("out_prefix")
    w.add_argument("--mobile", action="store_true"); w.add_argument("--full-page", action="store_true")
    w.add_argument("--wait-for"); w.add_argument("--delay", type=int, default=500)
    w.set_defaults(fn=cmd_web)

    t = sub.add_parser("term"); t.add_argument("out"); t.add_argument("--cmd"); t.add_argument("--file")
    t.add_argument("--title", default=""); t.add_argument("--max-lines", type=int, default=60)
    t.add_argument("--cwd"); t.set_defaults(fn=cmd_term)

    m = sub.add_parser("mermaid"); m.add_argument("input"); m.add_argument("out")
    m.add_argument("--width", type=int, default=1400); m.set_defaults(fn=cmd_mermaid)

    d = sub.add_parser("md"); d.add_argument("input"); d.add_argument("out")
    d.add_argument("--width", type=int, default=900); d.set_defaults(fn=cmd_md)

    h = sub.add_parser("html"); h.add_argument("input"); h.add_argument("out")
    h.add_argument("--width", type=int, default=1200); h.set_defaults(fn=cmd_html)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
