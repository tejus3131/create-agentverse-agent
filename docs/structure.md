---
layout: default
title: Generated Structure
nav_order: 4
---

# Generated Structure

When you run `create-agentverse-agent`, it generates a production-ready project structure. Here's what you get:

---

## Project Layout

```
my-agent/
├── .env                      # Environment variables
├── agent.py                  # Agent definition & handlers
├── docker-compose.yml        # Local container orchestration
├── Dockerfile                # Container build definition
├── main.py                   # Application entrypoint
├── Makefile                  # Common development commands
├── pyproject.toml            # Project metadata & dependencies
└── README.md                 # Project documentation
```

---

## Key Files Explained

### `agent.py`

The main agent definition file containing:

- Agent initialization with proper configuration
- Message handlers with async support
- Health and quota protocol integration
- Context-aware logging setup

### `main.py`

The application entrypoint that:

- Loads environment configuration
- Initializes the agent
- Starts the agent runtime

### `.env`

Environment variables for configuration:

```env
# Environment Configuration
ENV=

# API Keys
AGENTVERSE_API_KEY=

# Agent Configuration
AGENT_NAME=
AGENT_SEED_PHRASE=
AGENT_PORT=
AGENT_ROUTE=
AGENT_HANDLE=

# Hosting Configuration
HOSTING_ENDPOINT=

# Message Processing Configuration
MAX_PROCESSED_MESSAGES=
PROCESSED_MESSAGE_TTL_MINUTES=
CLEANUP_INTERVAL_SECONDS=

# Rate limiting configuration
RATE_LIMIT_MAX_REQUESTS=
RATE_LIMIT_WINDOW_MINUTES=
```

### `pyproject.toml`

Modern Python project configuration with:

- Project metadata
- Dependencies (uagents, etc.)
- Development dependencies
- Tool configurations

### `Makefile`

Common commands for development:

```bash
make install   # Install dependencies
make env       # Activate virtual environment
make dev       # Start the agent in poetry environment
make run       # Start agent in docker container (requires AGENTVERSE_API_KEY in .env)
```

### `Dockerfile`

Multi-stage Docker build optimized for:

- Small image size
- Fast builds with layer caching
- Production-ready configuration

### `docker-compose.yml`

Local development setup with:

- Environment variable loading
- Volume mounts for development
- Network configuration

---

## Features Included

### ⚡ Parallel Message Processing

Messages are handled asynchronously, allowing your agent to process multiple requests concurrently.

### 🧠 Context-Aware Logging

Structured logging with request context, making debugging and monitoring straightforward.

### 📡 Progress/Status Messages

Built-in support for sending progress updates during long-running operations.

### 🩺 Health & Quota Protocol

Standard health check endpoint and quota management for production deployments.

### 🤖 Agentverse Compatibility

Ready to deploy to [Agentverse](https://agentverse.ai) with proper configuration.

---

## Next Steps

Learn how to customize your agent in [Configuration](configuration.md).
