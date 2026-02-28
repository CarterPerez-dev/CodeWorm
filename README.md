```
 ██████╗ ██████╗ ██████╗ ███████╗██╗    ██╗ ██████╗ ██████╗ ███╗   ███╗
██╔════╝██╔═══██╗██╔══██╗██╔════╝██║    ██║██╔═══██╗██╔══██╗████╗ ████║
██║     ██║   ██║██║  ██║█████╗  ██║ █╗ ██║██║   ██║██████╔╝██╔████╔██║
██║     ██║   ██║██║  ██║██╔══╝  ██║███╗██║██║   ██║██╔══██╗██║╚██╔╝██║
╚██████╗╚██████╔╝██████╔╝███████╗╚███╔███╔╝╚██████╔╝██║  ██║██║ ╚═╝ ██║
 ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝ ╚══╝╚══╝  ╚═════╝ ╚═╝  ╚═╝╚═╝     ╚═╝
```

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Ollama](https://img.shields.io/badge/Ollama-local%20LLM-black?style=flat)](https://ollama.ai)
[![Docker](https://img.shields.io/badge/Docker-required-2496ED?style=flat&logo=docker&logoColor=white)](https://docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> Autonomous documentation daemon that crawls your codebases, generates docs with a local LLM, and commits at human-like intervals — while you do literally anything else.

## What It Does

- Picks a weighted-random doc type from 11 categories (function docs, security reviews, TILs, etc.)
- Scans configured repos and scores targets by complexity, git churn, and novelty
- Deduplicates — skips anything documented in the last 90 days per type
- Generates markdown via Ollama (qwen2.5:7b or any model you pull)
- Commits to a separate DevLog repo with a realistic commit message and pushes
- Runs on a human-like schedule: 120–144 commits/day at randomized intervals
- Live web dashboard shows activity, stats, and commit feed in real-time
- Telegram alerts if commits stop or Ollama goes down

## Quick Start

```bash
git clone https://github.com/CarterPerez-dev/CodeWorm
cd CodeWorm
uv sync

# Point it at your repos and DevLog
vim config/repos.yaml
vim config/config.yaml

# Start infrastructure (Ollama + Redis + dashboard)
docker compose -f dev.compose.yml up -d

# Test one cycle
codeworm run-once --dry-run

# Run the daemon
nohup uv run codeworm run >> /tmp/codeworm.log 2>&1 &
```

> [!TIP]
> This project uses [`just`](https://github.com/casey/just) as a command runner. Type `just` to see all available commands.
>
> Install: `curl -sSf https://just.systems/install.sh | bash -s -- --to ~/.local/bin`

## Commands

| Command | Description |
|---------|-------------|
| `just restart` | Kill and restart the daemon |
| `just logs` | Follow the daemon log |
| `just stop` | Stop the daemon |
| `codeworm run` | Start the full daemon with scheduler |
| `codeworm run-once` | Run one cycle and exit |
| `codeworm analyze` | Preview what would be documented |
| `codeworm stats` | Show documentation statistics |

## Documentation Types

| Type | Weight | What it generates |
|------|--------|-------------------|
| `function_doc` | 35% | Function and method documentation |
| `class_doc` | 12% | Class responsibility and interface |
| `file_doc` | 12% | File purpose and key exports |
| `security_review` | 10% | Injection, auth issues, race conditions |
| `til` | 10% | "Today I Learned" about interesting code |
| `performance_analysis` | 8% | Complexity, allocations, blocking calls |
| `code_evolution` | 5% | What changed recently and why |
| `module_doc` | 3% | Package structure and public API |
| `pattern_analysis` | 3% | Design patterns spotted in the code |
| `weekly_summary` | 1% | Weekly activity summary |
| `monthly_summary` | 1% | Monthly activity summary |

500 functions × 11 doc types = **5,500+ unique targets**. At 130/day that's 40+ days before anything repeats. Active repos keep changing, creating new targets continuously.

## Architecture

```
Your Repos ──> CodeWorm Daemon ──> Ollama (local LLM) ──> DevLog Repo
                    │                                          │
                    ├── SQLite (state + dedup)                 └── git push
                    ├── Redis (live events) ──> Dashboard
                    └── Scheduler (human-like timing)
```

```
codeworm/
├── core/        Config, SQLite state, logging, Redis events
├── analysis/    Tree-sitter parsing, complexity scoring, target finders
├── llm/         Ollama client, prompt templates per doc type
├── git/         GitPython operations, commit messages
├── scheduler/   APScheduler with human-like timing
└── daemon.py    Main orchestrator

dashboard/
├── backend/     FastAPI + WebSocket
└── frontend/    React + SCSS + recharts
```

## Requirements

- Python 3.12+
- Docker (for Ollama + Redis)
- Git repos you want documented
- A separate DevLog repo to commit to
- NVIDIA GPU recommended for Ollama performance

## License

MIT
