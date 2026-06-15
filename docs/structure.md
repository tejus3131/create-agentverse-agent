---
layout: default
title: Generated Structure
nav_order: 5
---

# Generated Structure

Running `create-agentverse-agent` produces a production-ready uAgents project with Postgres coordination.

---

## Project Layout

```
my-agent/
├── agent.yml                   # Non-secret configuration
├── .env                        # Secrets (never commit)
├── .env.example                # Reference for env vars
├── AGENTVERSE.md               # Agentverse profile readme
├── schema.sql                  # Postgres coordination schema
├── docker-compose.yml          # Local Postgres + agent
├── docker/init-pod-role.sh     # Postgres role bootstrap
├── Dockerfile                  # Container build (uv-based)
├── .dockerignore
├── Makefile                    # db, test, run, down
├── pyproject.toml              # Project metadata and dependencies
├── uv.lock                     # Locked dependencies
├── README.md
└── src/
    ├── agent/
    │   ├── __init__.py         # Exports handler definition
    │   └── handler.py          # Your agent handler (edit this)
    ├── runtime/                # Framework runtime (do not edit unless extending)
    │   ├── agent.py            # AgentRunner
    │   ├── main.py             # Entry point
    │   ├── pipeline.py         # Message pipeline
    │   ├── registration.py     # Agentverse smart registration
    │   ├── protocols/          # Chat + payment protocols
    │   ├── payments/           # FET, Stripe, Skyfire
    │   └── lifecycle/          # Coordinator + hooks
    └── shared/
        ├── settings.py         # agent.yml + .env loader
        ├── db.py               # Postgres runtime
        └── types.py            # Developer-facing handler types
```

---

## What to Edit

| Edit | Do not edit (unless extending) |
|------|--------------------------------|
| `src/agent/handler.py` | `src/runtime/` |
| `agent.yml` | `src/shared/` |
| `.env` | `schema.sql` |
| `AGENTVERSE.md` | |

---

## Configuration Flow

```
agent.yml  ──┐
             ├──► shared/settings.py ──► runtime (AgentRunner, protocols, payments)
.env       ──┘
```

Non-secret structured config lives in `agent.yml`. Secrets load from `.env` at runtime.

---

## Key Files

### `agent.yml`

Non-secret configuration: agent identity, protocol rate limits, access control, payment methods, runtime settings.

### `.env`

Secrets: Postgres credentials, `AGENT_SEED`, `AGENTVERSE_API_KEY`, payment provider keys. The scaffold writes `.env` directly; use `.env.example` as a reference.

### `AGENTVERSE.md`

Long-form Agentverse profile readme. Published on registration when `AGENTVERSE_API_KEY` is set. Short summary on Agentverse uses `agent.description` from `agent.yml`.

### `src/agent/handler.py`

Your agent logic. Export an `AgentDefinition` with `on_message`, optional startup/shutdown hooks, and scheduled tasks.

### `src/runtime/`

Framework code wired automatically. Handles uAgents lifecycle, Postgres coordination, protocols, payments, and Agentverse registration.

### `Makefile`

Common local dev commands:

```bash
make db    # Postgres only (docker compose)
make test  # db + uv run agent on host
make run   # full stack in Docker
make down  # stop compose services
```

### `schema.sql`

Postgres schema for multipod coordination. Applied automatically on first `docker compose up`.

---

## Features Included

- Postgres-backed work queue and session locks
- Chat and payment protocols with rate limiting and ACL
- FET, Stripe, and Skyfire payments (toggle in `agent.yml`)
- Smart Agentverse registration when `AGENTVERSE_API_KEY` is set
- Docker Compose for local development

---

## Next Steps

- [Configuration](configuration.md) — `agent.yml` and `.env` reference
- [Handler Guide](handler.md) — implement `handler.py`
- [Architecture](architecture.md) — how the runtime fits together
