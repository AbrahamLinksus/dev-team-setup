# Benchmark: normal Claude Code vs `/setup-project`

Build the same app twice, once in a normal Claude Code session and once with the plugin,
then compare **tokens, cost, your effort and the quality of what got built**. Do it for a
small app and for a production-grade app.

```
A Setup (once) → B Overhead (once) → C Small app → D Production app → E Send results
                                      normal → plugin → check   (same for D)
```

Commands are for **fish**. Every step says **why** you're doing it.

---

## A · Setup (once, ~10 min)

**A1. Check your tools**
```fish
claude --version; python3 --version; uv --version; gh auth status; git --version
```
*Why:* both runs need Claude Code, Python and uv; the plugin needs `gh` to create repos.
If `gh` is missing: `sudo pacman -S github-cli`, then `gh auth login`
(GitHub.com → HTTPS → authenticate Git: Yes → login with browser).

**A2. Get or update the kit**
```fish
test -d ~/dev-team-setup; and git -C ~/dev-team-setup pull; or git clone https://github.com/AbrahamLinksus/dev-team-setup ~/dev-team-setup
```
*Why:* the specs, answer sheets and measuring scripts live in this repo.

**A3. Make a shortcut**
```fish
set -U B ~/dev-team-setup/bench
```
*Why:* every later command uses `$B` instead of the full path. `-U` keeps it in new terminals too.

**A4. Install the plugin and add your details**
```fish
claude plugin marketplace add AbrahamLinksus/dev-team-setup
claude plugin install dev-team-setup@dev-team-setup
```
Then open `claude`, run `/plugin configure dev-team-setup@dev-team-setup`, enter your name and GitHub username, and `/exit`.
*Why:* the plugin run needs the plugin; the name and username are used for cards and repos.
(Already installed? Run `claude plugin marketplace update` instead, to get the latest version.)

**A5. Note your model**
Open `claude`, type `/model`, write the model into `results.md`, then `/exit`.
*Why:* all four runs must use the same model, or the comparison is meaningless. Don't change it until you're done.

**A6. Set a budget**
Decide the most you'll spend on each plugin run (for example, 5× what the normal run cost).
*Why:* the plugin runs are much longer. You'll check `/cost` at every milestone and stop if you go over.

---

## B · Overhead (once, ~2 min)

**B1. Measure what the installed plugin adds to every session**
```fish
bash $B/tools/overhead.sh
```
*Why:* while it's enabled, the plugin's skill and 26 agent descriptions are sent with every
model call, even in sessions that never use it. Use the **steady** "with plugin" number (if the
first "with" run is lower than the other two, the plugin hadn't finished loading; ignore it).
Write the numbers into `results.md` → Overhead.

---

## C · Small app: link shortener

Spec: `$B/small/spec.md` (3 endpoints, SQLite, tests, lint, types).

**C1. Make one folder per run, each with a copy of the spec**
```fish
mkdir -p ~/bench/small-normal ~/bench/small-plugin
cp $B/small/spec.md ~/bench/small-normal/
cp $B/small/spec.md ~/bench/small-plugin/
```
*Why:* both runs get exactly the same file. Separate folders keep their session logs apart,
because Claude Code stores logs per folder and the token report reads them from there.

> **Already did the normal run in `~/bench-baseline`?** It used the same spec. Skip C2 and in C3 use
> `cd ~/bench-baseline` and `--latest` instead of `--since $START`. The later steps work as written.

**C2. Normal run (plugin off)**
```fish
claude plugin disable dev-team-setup@dev-team-setup
cd ~/bench/small-normal
set START (date -Iseconds)
claude
```
Paste:
```
Build the app described in spec.md in this folder. Work until every item in "Quality bar" is met, then stop and give me a short summary.
```
- Don't help it. If it stops before the quality bar is met, reply `continue until every item in Quality bar is met` (max 3 times).
- **Count every message you send** after the first.
- When it's finished: type `/cost`, write the dollar amount down, then `/exit`.

*Why:* plugin off = a normal session. `START` marks when the run began, so the report counts
only this run. **Keep this terminal open until the measure step**, because `$START` only exists in it. Not helping keeps both runs on equal terms.

**C3. Measure tokens and cost**
```fish
cd ~/bench/small-normal
python3 $B/tools/token_report.py --since $START --label small-normal
```
Copy the **Summary row** into `results.md`. Its cost should match your `/cost`.
*Why:* the report uses Claude Code's own accounting, which includes background calls, and
also shows where the tokens went.

**C4. Check what it built**
1. Start the app the way its README says (usually `uv run uvicorn …` on port 8000).
2. In a second terminal:
   ```fish
   python3 $B/small/acceptance.py http://localhost:8000
   bash $B/tools/check_outcome.sh ~/bench/small-normal
   ```
3. Stop the app, start it again, and open `http://localhost:8000/links/<code>/stats` with the code
   the acceptance test printed. Clicks should still be 2 (data survived a restart).
4. Stop the app.

*Why:* the acceptance test checks the spec from the outside, identically for both runs, so it
doesn't matter how each run wrote its own tests. `check_outcome.sh` adds tests, coverage, lint,
types and size.

**C5. Plugin run (plugin on)**
```fish
claude plugin enable dev-team-setup@dev-team-setup
cd ~/bench/small-plugin
set START (date -Iseconds)
claude
```
Paste:
```
/setup-project Build the app described in spec.md in this folder. Treat spec.md as the full requirements and answer spec questions from it.
```
- Answer everything using `$B/small/answers.md`. **Count every tap and message.**
- **At each milestone card** choose *Approve + continue in a fresh session*. Then type `/cost`, note it,
  `/exit`, and in **the same folder** run `claude` and `/setup-project resume bench-link-shortener`.
- If the summed `/cost` passes your budget, stop and write "stopped at M<n>" in Notes.
- After the handover card: `/cost`, note it, `/exit`.

*Why:* the answer sheet keeps your choices consistent between runs. Fresh sessions per
milestone is the plugin's token-saving path. Staying in the same folder keeps all its sessions'
logs together for the report.

**C6. Measure**
```fish
cd ~/bench/small-plugin
python3 $B/tools/token_report.py --since $START --label small-plugin
```
Copy the Summary row. Also copy the **By agent** table into Notes.
*Why:* `--since` adds up every fresh session since you started. The agent table shows which
agents used the most tokens.

**C7. Check what it built**
The plugin builds in `~/projects/bench-link-shortener`. Repeat C4 with that folder:
```fish
python3 $B/small/acceptance.py http://localhost:8000
bash $B/tools/check_outcome.sh ~/projects/bench-link-shortener
```

**C8. Fill in the small-app tables in `results.md`.**

---

## D · Production app: issue tracker

Spec: `$B/production/spec.md` (accounts, permissions, pagination, rate limit, web UI,
Docker, CI, migrations). Same steps as C, with these differences.

**D1. Folders**
```fish
mkdir -p ~/bench/prod-normal ~/bench/prod-plugin
cp $B/production/spec.md ~/bench/prod-normal/
cp $B/production/spec.md ~/bench/prod-plugin/
```

**D2. Normal run.** Same as C2 in `~/bench/prod-normal`, with the same prompt.
Expect a long run. Up to 3 `continue…` nudges are allowed, all counted.
*Why:* a big task is where a normal session is most likely to stop early or skip parts of the quality bar. That's part of what you're measuring.

**D3. Measure.** As C3 with `--label prod-normal`.

**D4. Check what it built**
1. Start the API on port 8000 with a **fresh database**, the way its README says.
2. In a second terminal:
   ```fish
   python3 $B/production/acceptance.py http://localhost:8000
   bash $B/tools/check_outcome.sh ~/bench/prod-normal
   ```
   If Docker is installed and running, add `--docker` to also build the Compose stack (slow).
3. Start the web UI as the README says and try it in a browser. Log in, create a project,
   create an issue, change its status, and add a comment. Then repeat at phone width
   (browser dev tools → 390 px). Record ✅/❌ for desktop and phone.

*Why:* 29 outside-in API checks (auth, permissions, pagination, rate limit) plus the
packaging and UI checks are what "production-grade" means in the spec.

**D5. Plugin run.** As C5 in `~/bench/prod-plugin`, answering from `$B/production/answers.md`.
The resume command is `/setup-project resume bench-issue-tracker`. Check `/cost` against your
budget at every milestone.

**D6. Measure.** As C6 with `--label prod-plugin`.

**D7. Check.** As D4 with `~/projects/bench-issue-tracker`.

**D8. Fill in the production tables in `results.md`.**

---

## E · Send the results

Send me `$B/results.md` (or paste it into a chat).
*Why:* I'll compare the runs and turn the findings into concrete plugin changes.

---

### If something goes wrong

| Problem | Fix |
|---|---|
| `token_report.py`: "No session logs" | Run it from the run's folder (`cd ~/bench/<run>`) |
| Report cost ≠ `/cost` | Send me both, plus the output of `python3 $B/tools/diagnose_logs.py` (no prompt or code text in it) |
| Port 8000 already in use | `fuser -k 8000/tcp` (from the `psmisc` package), then start the app again |
| The app won't start at all | Record acceptance as 0 and note why. That's a real result |
| A run is stuck on the same error for more than 10 minutes | Note it, nudge once (counts as an intervention), and note whether it recovered |
