---
layout: default
title: Getting Started
nav_order: 3
---

# Getting Started

End-to-end: scaffold a project, run locally, optionally register on Agentverse.

---

## 1. Scaffold a project

```bash
uvx create-agentverse-agent -d
```

`-d` uses defaults: testnet, FET-only payments, local Postgres, auto-generated seed and password.

The project directory is named after the agent handle (default: `my-agent/`).

```bash
cd my-agent
```

For interactive setup instead:

```bash
uvx create-agentverse-agent
```

---

## 2. Install dependencies

```bash
uv sync
```

Requires Python **3.13** and [uv](https://github.com/astral-sh/uv).

---

## 3. Run locally

```bash
make test
```

This starts Postgres in Docker (if not already running) and runs the agent on your host via `uv run agent`.

Alternative — Postgres only:

```bash
make db
uv run agent
```

Full stack in Docker:

```bash
make run
```

---

## 4. Implement your handler

Edit `src/agent/handler.py`. The default echoes user messages. Export an `AgentDefinition` — see [Handler Guide](handler.md).

Adjust non-secret settings in `agent.yml` and secrets in `.env`.

---

## 5. Register on Agentverse (optional)

1. Get an API key from [Agentverse](https://agentverse.ai).
2. Set `AGENTVERSE_API_KEY` in `.env`.
3. Edit `AGENTVERSE.md` for your public profile page.
4. Restart the agent (`make test` or `uv run agent`).

On startup, the runtime reads `AGENTVERSE.md`, compares your profile, and registers or updates Agentverse. See [Agentverse](agentverse.md).

---

## Expected behavior

After `make test`, you should see:

- Postgres connection established
- Agent starting on the configured port
- Log lines from your `on_startup` hook in `handler.py`
- With `AGENTVERSE_API_KEY` set: registration or update messages

---

## Common failures

| Symptom | Fix |
|---------|-----|
| Postgres connection refused | Run `make db` or `docker compose up -d`; check `POSTGRES_HOST` / `POSTGRES_PORT` in `.env` |
| Payment config error | Disable unused methods in `agent.yml` or add Stripe/Skyfire keys to `.env` |
| Python version error | Generated projects require Python 3.13 |
| Directory already exists | Use `--overwrite` or pick a different handle |

---

## Next steps

- [Configuration](configuration.md) — full `agent.yml` and `.env` reference
- [Architecture](architecture.md) — how messages flow through the runtime
- [Migration](migration.md) — upgrading from 0.2.x scaffolds
