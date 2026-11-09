# Benchmark results

Date: · Claude Code (`claude --version`): · Plugin version: · Model (`/model`):

## Overhead (Part B)
| Without plugin | With plugin (steady) | Overhead per model call |
|---|---|---|
| | | |

---

## Small app: link shortener (Part C)

### Tokens and cost (summary rows from token_report.py)
| Run | All tokens | Output | Cache reads | Subagent tokens | Logged replies | Time | Cost |
|---|---|---|---|---|---|---|---|
| small-normal | | | | | | | |
| small-plugin | | | | | | | |

### Effort
| Run | Sessions | Your interventions | `/cost` sum (cross-check) |
|---|---|---|---|
| small-normal | 1 | | |
| small-plugin | | | |

### Outcome
| Run | Acceptance | Restart keeps data | Tests passed | Failed | Coverage | Ruff | Mypy | Lines |
|---|---|---|---|---|---|---|---|---|
| small-normal | /8 | | | | | | | |
| small-plugin | /8 | | | | | | | |

---

## Production app: issue tracker (Part D)

### Tokens and cost
| Run | All tokens | Output | Cache reads | Subagent tokens | Logged replies | Time | Cost |
|---|---|---|---|---|---|---|---|
| prod-normal | | | | | | | |
| prod-plugin | | | | | | | |

### Effort
| Run | Sessions | Your interventions | `/cost` sum (cross-check) | Finished? |
|---|---|---|---|---|
| prod-normal | 1 | | | |
| prod-plugin | | | | |

### Outcome: API
| Run | Acceptance | Tests passed | Failed | Coverage | Ruff | Mypy | Lines |
|---|---|---|---|---|---|---|---|
| prod-normal | /29 | | | | | | |
| prod-plugin | /29 | | | | | | |

### Outcome: web, packaging, UI
| Run | Web build | Web lint | Web tests | README | Dockerfile | Compose | CI | Migrations | .env.example | Docker build | UI works (desktop / phone) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| prod-normal | | | | | | | | | | | |
| prod-plugin | | | | | | | | | | | |

---

## Notes
- Where a run got stuck, needed nudging, or was stopped (and why):
- Plugin run, "By agent" table (paste from token_report.py):
