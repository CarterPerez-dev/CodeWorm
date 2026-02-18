# CodeWorm

An autonomous agent that crawls through your codebases and writes documentation while you sleep. Or while you're awake. It doesn't care. It just keeps documenting.

## What is this?

You know how you always tell yourself "I'll document this later" and then never do? CodeWorm does it for you. It runs as a daemon, picks code from your repos, generates technical documentation from **11 different perspectives** using a local LLM (Ollama), and commits it to a separate DevLog repository.

The kicker: it commits at human-like intervals throughout the day. Not 47 commits at 3am like a bot would. 120-144 commits spread across all hours with realistic gaps. Your GitHub contribution graph will thank you.

## How it works

```
Your Repos ──> CodeWorm Daemon ──> Ollama (local LLM) ──> DevLog Repo
                    │                                          │
                    ├── SQLite (dedup + state)                 └── git push
                    ├── Redis (live events) ──> Dashboard
                    └── Scheduler (human-like timing)
```

1. **Picks a doc type** — Weighted random from 11 types (function docs, security reviews, TILs, etc.)
2. **Picks a repo** — Weighted random from your configured repositories
3. **Finds a target** — Functions, classes, files, modules, or git diffs depending on the type
4. **Checks dedup** — Skips if this (entity + doc_type) was documented in the last 90 days
5. **Generates docs** — Sends code to Ollama with a type-specific prompt
6. **Commits & pushes** — Saves markdown to DevLog, commits with a realistic message, pushes

## Documentation Types

CodeWorm doesn't just write function docs. It documents the same codebase from multiple angles:

| Type | Weight | What it does |
|------|--------|-------------|
| `function_doc` | 35% | Standard function/method documentation |
| `class_doc` | 12% | Class responsibility, interface, patterns |
| `file_doc` | 12% | File purpose, key exports, project fit |
| `security_review` | 10% | Injection, auth issues, race conditions |
| `til` | 10% | Casual "today I learned" about interesting code |
| `performance_analysis` | 8% | O(n²), memory alloc, blocking calls |
| `code_evolution` | 5% | What changed recently and why (git diff) |
| `module_doc` | 3% | Package structure, public API |
| `pattern_analysis` | 3% | Design patterns (factory, observer, etc.) |
| `weekly_summary` | 1% | Weekly activity summary |
| `monthly_summary` | 1% | Monthly activity summary |

This means ~500 functions across your repos × 11 doc types = **5,000+ unique documentation targets**. At 130/day that's 38+ days before anything needs re-documenting. Active repos keep changing, creating new targets continuously.

## Quick Start

```bash
# Clone and install
git clone https://github.com/CarterPerez-dev/CodeWorm
cd CodeWorm
uv sync

# Configure your repos
vim config/repos.yaml

# Configure settings
vim config/config.yaml

# Start infrastructure (Ollama + Redis)
docker compose -f dev.compose.yml up -d

# Test it once
codeworm run-once

# Run the daemon
codeworm run
```

## Docker Infrastructure

CodeWorm runs on the host (systemd), but Ollama and Redis run in Docker:

```bash
# Development (with hot reload dashboard)
docker compose -f dev.compose.yml up -d

# Production
docker compose up -d
```

Services:
- **Ollama** — Local LLM with GPU passthrough
- **Redis** — Event streaming for the dashboard
- **Dashboard** — FastAPI backend + React frontend
- **Nginx** — Reverse proxy

```bash
# Useful commands via justfile
just dev-up          # Start dev stack
just dev-down        # Stop dev stack
just ollama-pull     # Pull the LLM model
just ollama-list     # List installed models
```

## Web Dashboard

A live dashboard shows what CodeWorm is doing in real-time:

```bash
# Start standalone (without Docker)
codeworm dashboard

# Or via Docker
docker compose -f dev.compose.yml up -d
# Open http://localhost:38491
```

The dashboard shows:
- **Stats** — Total docs, today/7d/30d counts, language breakdown, repo activity
- **Current Activity** — What the daemon is doing right now (idle/analyzing/generating)
- **Repositories** — All configured repos with activity indicators
- **Live Log** — Real-time colored log stream from the daemon
- **Commit Feed** — Recent documentation commits with doc type badges

The daemon publishes events to Redis, the FastAPI backend subscribes and fans out over WebSocket to the React frontend.

## Configuration

### repos.yaml

```yaml
repositories:
  - name: my-project
    path: ~/dev/my-project
    weight: 8        # Higher = more likely to be picked
    enabled: true

  - name: side-project
    path: ~/dev/side-project
    weight: 5
    enabled: true
```

### config.yaml

```yaml
devlog:
  repo_path: ~/DevLog
  remote: origin
  branch: main

ollama:
  host: localhost
  port: 47311
  model: qwen2.5:7b
  num_ctx: 16384

schedule:
  min_commits_per_day: 120
  max_commits_per_day: 144
  timezone: America/New_York
  min_gap_minutes: 10

documentation:
  redocument_after_days: 90
  type_weights:
    function_doc: 35
    class_doc: 12
    file_doc: 12
    security_review: 10
    til: 10
    # ... see config.yaml for full list

dashboard:
  enabled: false
  port: 53172
  redis:
    enabled: false
    port: 26849
```

## CLI Commands

```bash
# Run the full daemon with scheduler
codeworm run

# Run once and exit (good for testing)
codeworm run-once

# Start the web dashboard
codeworm dashboard

# See what functions would be documented
codeworm analyze --repo ~/dev/my-project --limit 20

# Preview the commit schedule
codeworm schedule-preview --days 3

# Check stats
codeworm stats

# Initialize DevLog directory structure
codeworm init

# Show version
codeworm version
```

## Architecture

```
codeworm/
├── core/           # Config, state (SQLite), logging, events (Redis)
├── analysis/       # Tree-sitter parsing, complexity scoring, target finders
├── llm/            # Ollama client, prompt templates per doc type
├── git/            # GitPython operations, commit messages
├── scheduler/      # APScheduler with human-like timing
├── models.py       # DocType enum, data models
├── daemon.py       # Main orchestrator
└── cli.py          # Click CLI

dashboard/
├── backend/        # FastAPI app, REST API, WebSocket
└── frontend/       # React + SCSS + recharts

infra/
├── docker/         # Dockerfiles (dev + prod)
└── nginx/          # Nginx configs (dev + prod)
```

## Requirements

- Python 3.12+
- Docker (for Ollama + Redis)
- Git repos you want documented
- A DevLog repo to commit to
- NVIDIA GPU recommended (for Ollama performance)

## Running as a Service

```bash
# Use the systemd installer
sudo ./scripts/install.sh
sudo systemctl enable codeworm
sudo systemctl start codeworm

# Check status
sudo systemctl status codeworm
journalctl -u codeworm -f
```

## FAQ

**Does this actually work?**

Yeah. You're reading documentation that might have been written by it.

**Won't it run out of things to document?**

Not anymore. With 11 doc types, the same function can be documented as a function doc, a security review, a TIL, and a performance analysis — all unique. Plus file-level, class-level, and module-level docs multiply the targets further.

**Won't my DevLog repo get huge?**

Eventually. But markdown files are tiny. You'll hit heat death of the universe before you hit storage limits.

**What if Ollama crashes?**

CodeWorm has OOM recovery. It'll reload the model and retry. If Ollama is completely dead, it'll skip that cycle and try again later.

**Is this cheating?**

It's documenting code that exists. The code is real. The documentation explains real code. Make of that what you will.

## License

MIT
