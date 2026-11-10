# Eval suite

Behaviour checks run with `claude plugin eval` (Claude Code 2.1.269+). The unit tests in
`tests/` cover the scripts and the guard; these cover what the model does with the skill.

| Case | Tag | Checks |
|---|---|---|
| `ignores-bare-continue` | routing | a bare "continue" with no setup-project STATE.md doesn't start the skill |
| `ignores-generic-setup` | routing | an ordinary setup question doesn't start the multi-agent pipeline |
| `stops-without-team-tools` | surface | without the Agent tool and Bash (claude.ai chat), the skill stops in one line (D6) |
| `explains-before-asking` | intake | the three-line opener comes before the first question (D31) |

Run all three groups (each needs different tool grants), capped at $11 in total:

```bash
sh evals/run.sh            # add --runs 1 for a quick, cheaper pass
```

Results go to `evals/results/` (git-ignored). The `intake` case grants Bash, which `claude plugin eval` only allows inside its sandbox (Linux or macOS), so on Windows run the other two groups. The `routing` and `surface` graders are free
(regex and tool checks); `intake` uses one judged rubric. CI runs the suite only on demand
(`Evals` workflow, needs an `ANTHROPIC_API_KEY` secret), because every run costs model calls.
