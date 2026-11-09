# Token benchmark: normal session vs plugin

Build the same small app twice in Claude Code, once normally and once with
`/setup-project`, then compare tokens, cost, effort and quality.

**You need:** Claude Code (signed in), Python 3.12+, [`uv`](https://docs.astral.sh/uv/),
`gh` (signed in), and this repo cloned:

```bash
git clone https://github.com/AbrahamLinksus/dev-team-setup ~/dev-team-setup
B=~/dev-team-setup/bench        # used below
```

---

## 1 · Overhead (2 min)

What the plugin adds to every session just by being installed.

```bash
bash $B/overhead.sh
```
Write the three numbers into `results.md`.

## 2 · Normal session

```bash
claude plugin disable dev-team-setup@dev-team-setup
mkdir ~/bench-baseline && cd ~/bench-baseline && claude
```
Paste the prompt from `baseline-prompt.md` (with `spec.md` pasted in).
Answer anything it asks, counting each time you type something.
When it's done, type `/cost`, write it down, and exit.

```bash
python3 $B/token_report.py --latest --label baseline
```

## 3 · Plugin session

```bash
claude plugin enable dev-team-setup@dev-team-setup
mkdir ~/bench-plugin && cd ~/bench-plugin
date -Iseconds        # note this start time
claude
```
Type `/setup-project`, then paste the contents of `spec.md` as the idea.
Answer using `answers.md`, counting every tap or message.

At each milestone pick **"Approve + continue in a fresh session"**: type `/cost`, note it,
exit, then in the **same folder** run `claude` and `/setup-project resume bench-link-shortener`.

When the handover is approved:
```bash
cd ~/bench-plugin
python3 $B/token_report.py --since <start time> --label plugin
```

## 4 · Check what each run built

For each project (`~/bench-baseline` and `~/projects/bench-link-shortener`):

```bash
# start the app as its README says, then in another terminal:
python3 $B/acceptance.py http://localhost:8000
bash $B/check_outcome.sh <project folder>
```

## 5 · Results

Fill in `results.md` and send it to me (or paste it into a chat).

---

**How tokens are counted:** `token_report.py` reads Claude Code's session logs in
`~/.claude/projects/` (the main session plus every subagent's log), counts each model
reply once, and splits totals by agent and model. Cache reads are much cheaper than
normal input, so compare `/cost` too, not just token totals.
