# Visual capture

Every result card needs a visual. Use the first option that works:
**screenshot → chart/diagram → rendered table → text**.

Script: `<skill base dir>/scripts/capture.py` (pass its absolute path to agents in their
brief, as `CAPTURE`). Save images under `<project>/.results/<task-id>/`, which is git-ignored.
Send them to the owner with SendUserFile where it exists (they open on the owner's phone);
otherwise print their absolute paths (see `result-card.md`, "How to deliver it").

**Ports:** tasks run in parallel, so never use a framework's default port. Each brief carries
`Port: <n>` (8000 + the task number, e.g. T-07 → 8007; T-07's second server → 9007): start
servers on it (`--port $PORT`, `PORT=$PORT npm run dev -- --port $PORT`) and capture from it,
so a screenshot can never come from another task's server.

| Task type | Visual | Command |
|---|---|---|
| Frontend / UI | App screenshots, desktop + mobile | start dev server in background → `python3 $CAPTURE web http://localhost:$PORT/<page> .results/T-07/ui --mobile --full-page --wait-for '<selector that means loaded>'` → stop server |
| Backend / API | FastAPI `/docs` screenshot + a real request/response | `python3 $CAPTURE web http://localhost:$PORT/docs .results/T-07/docs` and `python3 $CAPTURE term .results/T-07/req.png --cmd "curl -s -X POST localhost:$PORT/login -d '...' \| python3 -m json.tool" --title "POST /login"` |
| CLI / scripts | Terminal output | `python3 $CAPTURE term out.png --cmd "<command>" --title "<what>"` |
| Tests | Pass/fail + coverage | `python3 $CAPTURE term tests.png --cmd "uv run pytest -q --cov=src --cov-report=term" --title "tests"` |
| Spec wireframes | Lo-fi screen mock-ups, mobile + desktop | `python3 $CAPTURE html docs/wireframes/<screen>.html docs/wireframes/<screen>.png --width 390` (and `--width 1280`) |
| HLD / LLD / architecture | Mermaid diagram | write `.mmd` → `python3 $CAPTURE mermaid diagram.mmd diagram.png` |
| Package list / comparison / decision options | Rendered table | write `.md` → `python3 $CAPTURE md table.md table.png` |
| ML training | Loss curves, metric bars, confusion matrix | matplotlib/plotly → PNG (`fig.savefig(..., dpi=150, bbox_inches="tight")`) |
| Evaluation | Metrics vs baseline chart + per-metric table | chart PNG + `md` table |
| EDA / stats | Key notebook plots | save the 2–4 most informative plots as PNG from the notebook |
| Data cleaning | Before/after table (rows, nulls, dtypes) | `md` table |
| Interactive charts (plotly html, coverage html) | Screenshot of the HTML | `python3 $CAPTURE html report.html report.png` |
| CI / DevOps | Pipeline status, live URL screenshot | `term` with `gh run list`/`gh run view`; `web` on the deployed URL |
| Docs | Rendered README top section | `md README.md readme.png` |

## Phone preview (milestone end, opt-in)

Screenshots show the app; a preview lets the owner use it on their phone. It is offered at each
milestone card of a project with a UI or an API, and is **opt-in and Tier 1** (a public link):
- **Ask once**, at the first milestone card: "Try it on your phone? We'd open a temporary link:
  anyone who has it can use this build for 30 minutes, then it closes." **Yes, each milestone** /
  **Not now**. Record the answer in STATE.md and DECISIONS.md.
- **Private first:** if your tools can show a port to the owner's app without making it public
  (e.g. a `report_preview_port` tool in a cloud session), use that and skip the tunnel.
- **Otherwise:** the first time, a **devops** step writes `deploy/preview.sh` (devops must be on the
  team; add it with the owner's yes if not). Run it yourself from the milestone's worktree with
  Bash in the background: `timeout 1800 bash deploy/preview.sh` (Port 8000 + milestone number ×
  100). Put the `PREVIEW:` URL on the milestone card with "open on your phone; closes in 30 min".
  It stops by itself; stop it early when the owner answers the card. This is the only server
  allowed to outlive a step, and only because `timeout` bounds it.

Rules:
- Start servers in the background, wait for the port, capture, then kill the server in
  the same command. Never leave servers running after the turn.
- Show real output, never mock-ups. If the app can't run yet, say so and use the
  next visual in the order.
- Two to four images per card at most; pick the ones that prove the goals were met.
- Mobile check: always include the `--mobile` shot for user-facing pages.
