# Agent catalog

Use this to pick the team. "Pick when" is the test for including an agent.

## Core software pack

| Agent | Model | Tools | Pick when |
|---|---|---|---|
| planner | Opus | Read, Write, Edit, Glob | Always (HLD, DS problem framing, TASKS.md) |
| researcher | Sonnet | WebSearch, WebFetch, Read, Write (docs/research.md only) | Any choice of libraries, frameworks, models or papers |
| architect | Opus | Read, Write, Edit, Glob, Grep | Always (LLD, stack, package table) |
| env-setup | Sonnet | Bash, Read, Write, Edit, Glob | Always |
| backend-coder | Sonnet | Read, Write, Edit, Bash, Glob, Grep | Any server, API, CLI, pipeline or library code |
| frontend-coder | Sonnet | Read, Write, Edit, Bash, Glob, Grep | Any UI (web app, dashboard UI) |
| tester | Sonnet | Read, Write, Edit, Bash, Glob, Grep (tests only) | Always when code is written |
| reviewer | Opus | Read, Grep, Glob | Always when code is written (read-only) |
| debugger | Opus | Read, Edit, Bash, Glob, Grep | Always when code is written (on failures) |
| docs | Haiku | Read, Write, Edit, Glob | Always (README, architecture notes) |
| devops | Sonnet | Bash, Read, Write, Edit, Glob | CI needed, Docker, or deployment (GCP, Vercel, Render) |
| git-pr | Haiku | Bash, Read | Always (repo, commits, pushes, reverts) |

## AI/ML pack

| Agent | Model | Tools | Pick when |
|---|---|---|---|
| trainer | Sonnet | Bash, Read, Write, Edit, Glob | Deep learning, fine-tuning (LoRA/PEFT) |
| evaluator | Opus | Bash, Read, Write (eval files only), Glob, Grep | Any model or LLM output to measure; includes LLM-as-judge |
| rag-engineer | Sonnet | Bash, Read, Write, Edit, Glob, Grep, WebFetch | Retrieval over documents: chunking, embeddings, vector DB, reranking |
| prompt-engineer | Sonnet | Bash, Read, Write, Edit, Glob | LLM prompts, structured outputs, prompt iteration against evals |
| agent-engineer | Sonnet | Bash, Read, Write, Edit, Glob, Grep, WebFetch | LLM agents, tool calling, LangGraph, multi-agent, custom MCP servers |
| mlops | Sonnet | Bash, Read, Write, Edit, Glob | Serving a model, model/data versioning, drift monitoring |

## Data science pack

| Agent | Model | Tools | Pick when |
|---|---|---|---|
| data-acquisition | Sonnet | Bash, Read, Write, Glob, WebFetch, Google Drive | Data must be pulled (SQL, APIs, Kaggle/HF, Drive, web scraping) |
| data-cleaner | Sonnet | Bash, Read, Write, Edit, Glob | Any raw tabular data (asks before dropping data; Pandera schema) |
| eda | Sonnet | Bash, Read, Write, Edit, Glob | Any dataset to understand (delivers a .ipynb notebook) |
| statistician | Opus | Bash, Read, Glob | Hypothesis tests, A/B tests, causal inference (read-only on data) |
| modeler | Sonnet | Bash, Read, Write, Edit, Glob | Classical ML + feature engineering + time-series forecasting |
| explainer | Opus | Bash, Read, Write, Glob | Model must be explained (SHAP, PDP, fairness) |
| visualizer | Sonnet | Bash, Read, Write, Edit, Glob | Charts or dashboards (Plotly, Streamlit) |
| insights-reporter | Sonnet | Read, Write, Glob | Stakeholder report of findings |

## Typical teams

- **Full-stack web app**: planner, researcher, architect, env-setup, backend-coder, frontend-coder, tester, reviewer, debugger, docs, devops, git-pr
- **RAG / LLM app**: core minus frontend (add it if there's a UI) + rag-engineer, prompt-engineer, evaluator; + agent-engineer if it uses tools/agents
- **ML model project**: planner, researcher, architect, env-setup, data-acquisition, data-cleaner, eda, modeler, evaluator, explainer, tester, reviewer, debugger, docs, git-pr; + mlops if served
- **Analysis / A-B test**: planner, env-setup, data-acquisition, data-cleaner, eda, statistician, visualizer, insights-reporter, reviewer, git-pr
