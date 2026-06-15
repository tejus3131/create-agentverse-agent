---
layout: default
title: Migration
nav_order: 10
---

# Migration from 0.2.x

Version **1.0.0** replaces the flat uAgents scaffold with a Postgres-backed runtime from [standard-uagents-setup](https://github.com/tejus3131/standard-uagents-setup).

---

## What changed

| 0.2.x | 1.0.0 |
|-------|-------|
| Flat `main.py` + `agent.py` | `src/agent/handler.py` + `src/runtime/` |
| `.env` only | `agent.yml` + `.env` |
| Poetry / Makefile | uv + Makefile |
| `AGENT_SEED_PHRASE` | `AGENT_SEED` |
| Hosting ports in config | Mailbox model (no hosting ports) |
| No Postgres | Postgres coordination required |
| `src/agent/test.py` | `src/agent/handler.py` |

---

## Migrating an existing project

There is no automatic migrator. Recommended approach:

1. Scaffold a fresh project with 1.0.0:

   ```bash
   uvx create-agentverse-agent -d
   ```

2. Copy your handler logic into `src/agent/handler.py` (adapt to `AgentDefinition` + `HandlerRequest` / `HandlerResponse` types).

3. Move non-secret settings into `agent.yml`.

4. Move secrets into `.env` (rename `AGENT_SEED_PHRASE` → `AGENT_SEED`).

5. Add `AGENTVERSE.md` for your Agentverse profile.

6. Run `uv sync` and `make test`.

---

## Handler API changes

**Old:** Direct uAgents agent setup in `agent.py` / `main.py`.

**New:** Export an `AgentDefinition` from `handler.py`:

```python
definition = AgentDefinition(
    on_message=on_message,
    on_startup=[on_startup],
    on_shutdown=[on_shutdown],
)
```

See [Handler Guide](handler.md) for request/response types.

---

## Configuration split

**`agent.yml`** (commit to git):

- Agent name, handle, description, avatar, banner
- Protocol rate limits and access control
- Payment method toggles
- Runtime network, log level, coordinator TTLs

**`.env`** (never commit):

- `AGENT_SEED`, `AGENTVERSE_API_KEY`
- Postgres credentials
- Stripe / Skyfire keys

See [Configuration](configuration.md).

---

## Dev workflow changes

| Task | 0.2.x | 1.0.0 |
|------|-------|-------|
| Install deps | `poetry install` | `uv sync` |
| Run agent | `make run` / `poetry run` | `make test` or `uv run agent` |
| Postgres | None | `make db` or `docker compose up -d` |

---

## Re-scaffolding into same directory

To refresh template files while keeping extra files you added:

```bash
create-agentverse-agent --overwrite
```

Template and bundle files are replaced; other files in the project directory are preserved.

---

## Further reading

- [CHANGELOG](https://github.com/tejus3131/create-agentverse-agent/blob/main/CHANGELOG.md) — full 1.0.0 breaking changes
- [Architecture](architecture.md) — new runtime design
