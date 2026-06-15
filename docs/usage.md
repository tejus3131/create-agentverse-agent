---
layout: default
title: Usage
nav_order: 4
---

# Usage Guide

This page covers the **scaffold CLI** (`create-agentverse-agent`). After scaffolding, you work in a separate generated project with its own `pyproject.toml`, `Makefile`, and runtime — see [Getting Started](getting-started.md).

---

## Interactive Mode

```bash
uvx create-agentverse-agent
```

The wizard collects:

- Agent identity (name, handle, description, port)
- Network (testnet / mainnet)
- Postgres connection settings
- Optional Agentverse API key and seed

Use `--advanced` for:

- Payment methods (FET, Stripe, Skyfire)
- Protocol rate limits and access-control policies
- Coordinator TTLs (heartbeat, assignment, processing, session lock)
- Runtime log level

---

## Quick Start

```bash
uvx create-agentverse-agent --default
# or
uvx create-agentverse-agent -d
```

Defaults: testnet, FET-only payments, local Postgres, auto-generated seed and password.

---

## CLI Options

| Option | Short | Description |
|--------|-------|-------------|
| `--default` | `-d` | Use defaults, skip prompts |
| `--advanced` | `-a` | Payment + protocol + runtime options |
| `--overwrite` | `-o` | Re-scaffold into existing project directory |
| `--debug` | | Write debug log file |
| `--version` | `-v` | Show version |
| `--help` | | Show help |

### `--overwrite`

When the project directory already exists, `--overwrite` re-runs scaffolding into that folder. Template and bundle files are replaced; any extra files you added are left in place.

### Project directory name

The output folder is named after `agent.handle` from the wizard (e.g. `my-agent/`).

### Debug logging

With `--debug`, the CLI writes a log file in the current directory:

```
create-agentverse-agent-<version>-cli-execution-<uuid>.log
```

---

## After Scaffolding

```bash
cd my-agent
uv sync
make test
```

Full stack in Docker: `make run`. See `make help`.

Edit `src/agent/handler.py` to implement your handler.

---

## Examples

```bash
# Interactive
uvx create-agentverse-agent

# Quick prototype
uvx create-agentverse-agent -d

# Full config with overwrite
uvx create-agentverse-agent -a -o

# Debug
uvx create-agentverse-agent --debug
```

---

## Next Steps

See [Generated Structure](structure.md) and [Configuration](configuration.md).
