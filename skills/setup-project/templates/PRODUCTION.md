# PRODUCTION — {{project}}

> The production gate. At stage 6 the planner copies the **All projects** section plus the
> section for each project type that applies, marks each item **Applies** (with the task whose
> acceptance criterion proves it, tagged `(G-xx)`) or **N/A** (with a one-line reason), and
> deletes the other sections. At handover every applicable item must be **Built + tested**
> (the proof below passed) or **Waived by the owner** (consequence stated, logged in
> DECISIONS.md). Handover can't be approved while any item is open.

Status values: `Open` · `Built + tested (<test or capture>)` · `Waived by the owner (D-xx: <consequence>)` · `N/A (<reason>)`

## All projects

| ID | Item | Proven by | Task | Status |
|---|---|---|---|---|
| G-01 | Errors reach the user in plain words; no stack traces or raw codes | a test that triggers each error path the spec names and checks the message | | Open |
| G-02 | Saved data survives a restart of the app | a test that saves, restarts (or reopens the store) and reads it back | | Open |
| G-03 | The SPEC §13 data-safety choice is built (backup/export, undo), or "no backup" is stated in the README | a test of the export/backup/undo path, or the README line | | Open |
| G-04 | No secrets in the repo; every key the app reads is listed in `.env.example` | the `check.sh` secret scan + the reviewer's check of config reads | | Open |
| G-05 | Every user input is validated (empty, too long, wrong type) | one test per input the spec names | | Open |
| G-06 | A fresh clone installs and runs with the README's commands | the handover tester's fresh-clone run | | Open |

## Local app (desktop, CLI or single-device mobile)

| ID | Item | Proven by | Task | Status |
|---|---|---|---|---|
| G-L1 | Works with no network connection | a test run with the network disabled (or no network calls in the code, per the reviewer) | | Open |
| G-L2 | An update keeps the user's existing data (schema changes migrate) | a migration test on data saved by the previous version | | Open |
| G-L3 | Starts with one documented command or a packaged build | the handover tester's run of that command | | Open |

## Web app

| ID | Item | Proven by | Task | Status |
|---|---|---|---|---|
| G-W1 | Passwords are hashed; sessions expire; logout ends the session | tests on login, expiry and logout | | Open |
| G-W2 | A user can never see or change another user's data | a test acting as user B on user A's records (403/404) | | Open |
| G-W3 | Forms are protected against CSRF and output is escaped (no XSS) | tests posting without a token and rendering `<script>` input | | Open |
| G-W4 | Login and sign-up are rate-limited | a test of the 6th attempt in a minute | | Open |
| G-W5 | Usable on a 390px phone screen; inputs have labels | a 390px screenshot of each screen + an accessibility lint | | Open |
| G-W6 | The database schema is created by migrations, and a backup can be restored | a migration test from empty + a restore of a dump | | Open |
| G-W7 | Served over HTTPS where deployed, with an error page instead of a stack trace | the deploy check (devops) + a test of an unknown URL | | Open |

## API

| ID | Item | Proven by | Task | Status |
|---|---|---|---|---|
| G-A1 | Bad requests get a 4xx with a clear error body; nothing returns 500 for user mistakes | tests of malformed, missing and oversized input | | Open |
| G-A2 | Every endpoint that needs a caller identity checks it, and checks what that caller may access | tests without a token and with another caller's token | | Open |
| G-A3 | The published contract (OpenAPI or LLD contracts) matches what the code serves | a contract test against the running app | | Open |
| G-A4 | Outbound calls have timeouts and fail with a clear error | a test with the dependency slow or down | | Open |
| G-A5 | Lists are paginated with a maximum page size | a test asking for more than the maximum | | Open |
| G-A6 | A health endpoint reports the app and its dependencies | a test of the health endpoint | | Open |

## AI/ML service

| ID | Item | Proven by | Task | Status |
|---|---|---|---|---|
| G-M1 | Quality is measured on a fixed eval set and meets the agreed metric against a baseline | the evaluator's report on the eval set | | Open |
| G-M2 | The model and prompt versions in use are recorded and pinned | the reviewer's check of config + a test that reads them | | Open |
| G-M3 | A model error or timeout gives the user a fallback, not a crash | a test with the model call failing | | Open |
| G-M4 | Spend is capped (per request and per day) | a test that hits the cap | | Open |
| G-M5 | Personal data isn't logged or sent where the owner didn't approve | the reviewer's check of logging and outbound calls | | Open |
| G-M6 | User text can't override the system's instructions (prompt injection) | an eval or test with injection attempts | | Open |
