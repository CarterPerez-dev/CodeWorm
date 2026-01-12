# CodeWorm

An autonomous agent that crawls through your codebases and writes documentation while you sleep. Or while you're awake. It doesn't care. It just keeps documenting.

## What is this?

You know how you always tell yourself "I'll document this later" and then never do? CodeWorm does it for you. It runs as a daemon, picks random functions from your repos, generates technical documentation using a local LLM (Ollama), and commits it to a separate DevLog repository.

The kicker: it commits at human-like intervals throughout the day. Not 47 commits at 3am like a bot would. More like 12-18 commits spread across normal working hours with realistic gaps between them. Your GitHub contribution graph will thank you.

## How it works

```
Your Repos ──> CodeWorm ──> Ollama (local LLM) ──> DevLog Repo
                  │
                  └── SQLite (tracks what's documented)
```

1. **Scans** your configured repositories for functions/methods
2. **Scores** them by complexity, length, git churn, and other factors
3. **Picks** interesting candidates using weighted random selection
4. **Generates** documentation via Ollama (qwen2.5:7b by default)
5. **Commits** to your DevLog repo with natural-sounding messages
6. **Pushes** automatically
7. **Repeats** on a human-like schedule

## Quick Start

```bash
# Clone and install
git clone https://github.com/CarterPerez-dev/CodeWorm
cd CodeWorm
uv sync

# Configure your repos
vim config/repos.yaml

# Configure settings (Ollama, schedule, etc)
vim config/config.yaml

# Make sure Ollama is running
ollama serve
ollama pull qwen2.5:7b

# Test it once
codeworm run-once

# Run the daemon
codeworm run
```

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
  port: 11434
  model: qwen2.5:7b
  num_ctx: 4096

schedule:
  min_commits_per_day: 12
  max_commits_per_day: 18
  timezone: America/Los_Angeles
  prefer_hours: [9, 10, 11, 14, 15, 16, 20, 21, 22]
  avoid_hours: [3, 4, 5, 6, 7]

analyzer:
  min_complexity: 1
  min_lines: 8
  max_lines: 250
```

## CLI Commands

```bash
# Run the full daemon with scheduler
codeworm run

# Run once and exit (good for testing)
codeworm run-once

# See what functions would be documented
codeworm analyze --repo ~/dev/my-project --limit 20

# Preview the commit schedule
codeworm schedule-preview --days 3

# Check stats
codeworm stats

# Initialize DevLog directory structure
codeworm init
```

## The Schedule

CodeWorm doesn't just spam commits. It generates a daily schedule that looks human:

```
2026-01-12 09:04:57  (Monday)
2026-01-12 09:49:10  (Monday)
2026-01-12 10:34:11  (Monday)
2026-01-12 13:06:40  (Monday)
2026-01-12 14:31:56  (Monday)
...
```

- Prefers configured "work hours"
- Avoids 3-7am (unless you're into that)
- Reduces activity on weekends
- Minimum 30 minute gaps between commits
- Randomized count per day (12-18 by default)

## What Gets Documented

CodeWorm looks for functions that are actually worth documenting:

- **Complexity score** - More branches/loops = more interesting
- **Length** - Not too short (getters), not too long (god functions)
- **Git churn** - Recently modified code gets priority
- **Patterns** - Async functions, decorators, context managers get bonus points

It skips the boring stuff:
- `__init__`, `__str__`, `main()`
- Test files (`test_*.py`, `*_test.go`)
- Generated code, node_modules, etc.

## Architecture

```
codeworm/
├── core/           # Config, state (SQLite), logging
├── analysis/       # Tree-sitter parsing, complexity analysis, scoring
├── llm/            # Ollama client, prompt templates
├── git/            # GitPython operations, commit messages
├── scheduler/      # APScheduler with human-like timing
├── daemon.py       # Main orchestrator
└── cli.py          # Click CLI
```

The daemon is the brain. Ollama is stateless - it just writes what we tell it to. All the intelligence (what to document, when to commit, deduplication) lives in the Python code.

## Requirements

- Python 3.11+
- Ollama running locally
- Git repos you want documented
- A DevLog repo to commit to

## Running as a Service

For the "set it and forget it" experience:

```bash
# Quick and dirty
nohup codeworm run > /tmp/codeworm.log 2>&1 &

# Or use the systemd installer
sudo ./scripts/install.sh
sudo systemctl enable codeworm
sudo systemctl start codeworm
```

## FAQ

**Does this actually work?**

Yeah. You're reading documentation that might have been written by it.

**Won't my DevLog repo get huge?**

Eventually. But markdown files are tiny. You'll hit heat death of the universe before you hit storage limits.

**What if Ollama crashes?**

CodeWorm has OOM recovery. It'll reload the model and retry. If Ollama is completely dead, it'll just skip that cycle and try again later.

**Is this cheating?**

It's documenting code that exists. The code is real. The documentation explains real code. Make of that what you will.

## License

MIT
