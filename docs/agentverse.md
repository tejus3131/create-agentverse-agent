---
layout: default
title: Agentverse
nav_order: 9
---

# Agentverse

How generated projects register and present themselves on [Agentverse](https://agentverse.ai).

---

## Registration

When `AGENTVERSE_API_KEY` is set in `.env`, the runtime calls smart registration on startup (`runtime/registration.py`):

1. Fetch existing Agentverse profile (if any)
2. Compare with desired fields from config + `AGENTVERSE.md`
3. Register, update missing fields, or no-op if already complete

Without an API key, the agent still runs locally but is not registered.

---

## Profile fields

| Source | Field |
|--------|-------|
| `agent.yml` → `agent.name` | Display name |
| `agent.yml` → `agent.handle` | Handle (slug) |
| `agent.yml` → `agent.description` | Short summary on Agentverse |
| `AGENTVERSE.md` | Long profile readme (markdown) |
| `agent.yml` → `agent.avatar_url` | Avatar image URL |
| `agent.yml` → `agent.banner_url` | Banner image URL |
| `agent.yml` → `agent.geo_location` | Optional location metadata |
| `agent.yml` → `runtime.network` | `testnet` or `mainnet` |

Default avatar and banner URLs are set by the scaffold. Override in `agent.yml`.

---

## Three readme files

| File | Audience |
|------|----------|
| `README.md` | Developers cloning your repo |
| `agent.yml` → `description` | Short blurb on Agentverse |
| `AGENTVERSE.md` | Full public profile page on Agentverse |

Edit `AGENTVERSE.md` for marketing copy, usage instructions, and links. It is published when registration runs.

---

## Setup steps

1. Create an agent on Agentverse and copy your API key.
2. Set `AGENTVERSE_API_KEY` in `.env`.
3. Set `agent.handle` in `agent.yml` to match your Agentverse handle.
4. Edit `AGENTVERSE.md`.
5. Restart the agent.

```bash
make test
```

Look for registration log lines (`registered`, `updated`, or `noop`).

---

## Mailbox model

Generated agents use the **mailbox** model (`runtime.mailbox: true` in `agent.yml`). Hosting port configuration from older scaffolds is gone — the agent connects outbound via Agentverse mailbox.

---

## Next steps

- [Getting Started](getting-started.md) — first run with Agentverse
- [Configuration](configuration.md) — identity and env vars
