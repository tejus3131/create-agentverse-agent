---
layout: default
title: Configuration
nav_order: 6
---

# Configuration

Generated projects use two configuration layers:

- **`agent.yml`** — structured, non-secret settings (committed to git)
- **`.env`** — secrets and credentials (never commit)

The scaffold writes `.env` directly. **`.env.example`** is copied into the project as a reference for available variables.

---

## agent.yml

### Agent identity

```yaml
agent:
  name: "My Agent"
  description: "What this agent does"
  handle: "my-agent"        # lowercase slug; also the project directory name
  port: 8000
  avatar_url: https://storage.googleapis.com/agentverse-prod-assets/agent-avatars-pub/1555524032.png
  banner_url: https://storage.googleapis.com/agentverse-prod-assets/agent-banners-pub/360350005.png
  geo_location: null
```

**Avatar and banner** are Agentverse profile assets. Defaults come from the scaffold; override in `agent.yml`.

**`geo_location`** (optional): latitude, longitude, and radius (meters). Set when you want location metadata on Agentverse:

```yaml
geo_location:
  latitude: 51.5074
  longitude: -0.1278
  radius: 0
```

### Protocols

Both `chat` and `payment` support:

- `maximum_processing_time_seconds`
- `rate_limits.session` / `rate_limits.user` (`max_requests` + `window`)
- `rate_limits.exemptions` (`policy`: none | all | allow | deny)
- `access_control` (`policy`: all | none | allow | deny)

Rate limit **window** format: duration strings like `30s`, `1m`, `2h`.

Payment protocol additionally has:

```yaml
protocols:
  payment:
    methods:
      fet: enabled      # enabled | disabled
      skyfire: disabled
      stripe: disabled
```

**Defaults with `-d` / `--default`:** FET enabled, Stripe and Skyfire disabled.

**Note:** Enabling `stripe` or `skyfire` requires the corresponding secrets in `.env`.

### Runtime

```yaml
runtime:
  log_level: INFO
  max_concurrent_sessions: 5
  mailbox: true
  network: testnet        # testnet | mainnet
  coordinator:
    heartbeat_interval_seconds: 20
    assignment_ttl_seconds: 90
    processing_ttl_seconds: 180
    session_lock_ttl_seconds: 180
    reclaim_worker_stale_seconds: 45
```

---

## AGENTVERSE.md

| File | Purpose |
|------|---------|
| `agent.yml` → `agent.description` | Short summary on Agentverse |
| `AGENTVERSE.md` | Long profile readme (markdown) |
| `README.md` | Developer docs for your repo (not sent to Agentverse) |

`AGENTVERSE.md` is read at startup and sent to Agentverse when `AGENTVERSE_API_KEY` is set. See [Agentverse](agentverse.md).

---

## Environment Variables (.env)

```env
# Agentverse (optional)
AGENTVERSE_API_KEY=
AGENT_SEED=

# Postgres (required)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=agent
POSTGRES_USER=agent_pod
POSTGRES_PASSWORD=

# Stripe (required when stripe enabled in agent.yml)
STRIPE_SECRET_KEY=
STRIPE_PUBLISHABLE_KEY=

# Skyfire (required when skyfire enabled in agent.yml)
SKYFIRE_API_KEY=
SKYFIRE_SELLER_ACCOUNT_ID=
SKYFIRE_SERVICE_ID=

# Optional FET LCD override
# FET_LCD_URL=

# Docker Compose port mapping
AGENT_PORT=8000
```

### `AGENT_SEED`

Holds the agent wallet seed phrase. In 0.2.x scaffolds this was `AGENT_SEED_PHRASE` — rename when migrating. See [Migration](migration.md).

---

## Local Development

```bash
docker compose up -d   # or: make db
uv sync
uv run agent           # or: make test
```

---

## Troubleshooting

**Postgres not reachable:** Run `docker compose up -d` and confirm `POSTGRES_HOST` / `POSTGRES_PORT` in `.env`.

**Payment config invalid:** Disable unused payment methods in `agent.yml` or add required provider keys to `.env`.

**Schema not found:** `schema.sql` is applied on first Postgres container boot via Docker Compose.

---

## Getting Help

- [GitHub Issues](https://github.com/tejus3131/create-agentverse-agent/issues)
- [Fetch.ai Discord](https://discord.gg/fetchai)
- [uAgents Documentation](https://fetch.ai/docs)
