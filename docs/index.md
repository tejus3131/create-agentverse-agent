---
layout: default
title: Home
nav_order: 1
---

# create-agentverse-agent

A CLI tool to scaffold **production-ready uAgents** with a Postgres-backed multipod runtime.

Edit **`src/agent/handler.py`**, **`agent.yml`**, **`.env`**, and **`AGENTVERSE.md`** in generated projects. The runtime under `src/runtime/` is wired for you.

---

## Quick Start

```bash
uvx create-agentverse-agent -d
cd my-agent
uv sync
make test
```

---

## What You Get

| Feature | Description |
|---------|-------------|
| Postgres Runtime | Work queue, session locks, idempotency |
| Chat + Payment | Protocols with rate limits and ACL |
| Payments | FET, Stripe, Skyfire (configurable) |
| Agentverse | Smart registration on startup |
| Dual Config | `agent.yml` + `.env` |
| AGENTVERSE.md | Profile readme published on registration |
| Makefile | `db`, `test`, `run`, `down` |
| Docker | Compose for local Postgres + agent |

---

## Documentation

- [Installation Guide](installation.md)
- [Getting Started](getting-started.md)
- [Usage Guide](usage.md)
- [Generated Structure](structure.md)
- [Configuration](configuration.md)
- [Architecture](architecture.md)
- [Handler Guide](handler.md)
- [Agentverse](agentverse.md)
- [Migration from 0.2.x](migration.md)

---

## Links

- [PyPI](https://pypi.org/project/create-agentverse-agent/)
- [GitHub](https://github.com/tejus3131/create-agentverse-agent)
- [Changelog](https://github.com/tejus3131/create-agentverse-agent/blob/main/CHANGELOG.md)

---

MIT License — [Tejus Gupta](https://tejusgupta.dev)
