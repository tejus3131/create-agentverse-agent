# create-agentverse-agent

[![Fetch.ai](https://img.shields.io/badge/Fetch.ai-Ecosystem-blue?logo=fetch.ai&logoColor=white)](https://fetch.ai)
[![PyPI](https://img.shields.io/pypi/v/create-agentverse-agent?cacheSeconds=300)](https://pypi.org/project/create-agentverse-agent/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/create-agentverse-agent?cacheSeconds=300)](https://pypi.org/project/create-agentverse-agent/)
[![License](https://img.shields.io/github/license/tejus3131/create-agentverse-agent)](LICENSE)
[![CI](https://github.com/tejus3131/create-agentverse-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/tejus3131/create-agentverse-agent/actions/workflows/ci.yml)
[![Docs](https://img.shields.io/badge/docs-github--pages-blue)](https://create-agentverse-agent.tech/)

> **Full Documentation:** [create-agentverse-agent.tech](https://create-agentverse-agent.tech/)

CLI to scaffold **production-ready uAgents** with a Postgres-backed multipod runtime, chat + payment protocols, and Agentverse registration.

---

## Why this exists

Building agents with **uAgents** is powerful, but a production-grade setup — Postgres coordination, rate limits, payments, multipod runtime — is a lot to hand-roll every time.

This tool generates a complete project in seconds:

- Postgres-backed work queue, session locks, and idempotency
- Chat and payment protocol wiring
- FET, Stripe, and Skyfire payment support (configurable)
- Smart Agentverse registration on startup
- Dual config: `agent.yml` (non-secret) + `.env` (secrets)
- Docker Compose for local Postgres + agent
- uv-based Python 3.13 workflow

---

## Prerequisites

**CLI tool:** Python 3.12+, [uv](https://github.com/astral-sh/uv) (recommended)

**Generated projects:** Python 3.13, uv, Docker (Postgres via Compose)

Test the CLI from a local checkout:

```bash
uvx --from . create-agentverse-agent -d
```

---

## Installation

### Recommended: `uvx` (no install)

```bash
uvx create-agentverse-agent
```

### Other methods

```bash
pipx install create-agentverse-agent
# or
pip install create-agentverse-agent
```

---

## Usage

### Interactive setup

```bash
uvx create-agentverse-agent
```

### Quick start with defaults

```bash
uvx create-agentverse-agent --default
# or
uvx create-agentverse-agent -d
```

### Advanced configuration

```bash
uvx create-agentverse-agent --advanced
# or
uvx create-agentverse-agent -a
```

### Overwrite existing project

```bash
uvx create-agentverse-agent --overwrite
```

### Debug logging

```bash
uvx create-agentverse-agent --debug
```

---

## What gets generated?

```
my-agent/
├── agent.yml              # Identity, protocols, runtime config
├── .env                   # Secrets (Postgres, API keys)
├── .env.example           # Reference for env vars
├── AGENTVERSE.md          # Agentverse profile readme
├── schema.sql             # Postgres coordination schema
├── docker-compose.yml     # Local Postgres + agent
├── Dockerfile             # Container build
├── pyproject.toml         # uv / hatch project
├── uv.lock                # Locked dependencies
├── Makefile               # db, test, run, down
├── src/agent/handler.py   # Your handler (edit this)
├── src/runtime/           # Framework runtime
└── src/shared/            # Settings and types
```

### After scaffolding

```bash
cd my-agent
uv sync
make test    # Postgres in Docker + agent on host
```

Or full stack: `make run`. See `make help`.

---

## Documentation

| Guide | Description |
| --- | --- |
| [Installation](https://create-agentverse-agent.tech/installation) | Install methods |
| [Getting Started](https://create-agentverse-agent.tech/getting-started) | End-to-end tutorial |
| [Usage](https://create-agentverse-agent.tech/usage) | CLI options |
| [Generated Structure](https://create-agentverse-agent.tech/structure) | Project layout |
| [Configuration](https://create-agentverse-agent.tech/configuration) | agent.yml + .env reference |
| [Architecture](https://create-agentverse-agent.tech/architecture) | Runtime design |
| [Handler Guide](https://create-agentverse-agent.tech/handler) | Writing agent logic |
| [Agentverse](https://create-agentverse-agent.tech/agentverse) | Registration and profile |
| [Migration](https://create-agentverse-agent.tech/migration) | Upgrading from 0.2.x |

---

## Author

**Tejus Gupta** — [tejusgupta.dev](https://tejusgupta.dev)

---

## License

MIT — see [LICENSE](LICENSE).

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Runtime bundle sync procedure documented there.
