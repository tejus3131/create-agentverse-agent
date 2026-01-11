---
layout: default
title: Configuration
nav_order: 5
---

# Configuration

This guide covers how to configure your generated agent and customize the scaffold.

---

## Environment Variables

The generated `.env` file contains essential configuration:

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

## Project Customization

### Adding Dependencies

Edit `pyproject.toml` to add dependencies:

```toml
[project]
dependencies = [
    "uagents>=0.10.0",
    "your-package>=1.0.0",  # Add here
]
```

Then install:

```bash
pip install -e .
# or
poetry install
```

## Docker Configuration

### Running with Docker Compose

```bash
docker-compose up
# or
make up
```

### Custom Docker Configuration

Edit `docker-compose.yml` for:

- Port mappings
- Volume mounts
- Environment overrides
- Network settings

---

## Deployment

### Local Development

```bash
make dev
# or
poetry run python main.py
```

### Agentverse Deployment

1. Set your `AGENTVERSE_API_KEY` in `.env`
2. Configure your agent endpoint
3. Register with Agentverse

See the [Agentverse documentation](https://fetch.ai/docs) for detailed deployment instructions.

---

## Troubleshooting

### Debug Logging

Enable debug output:

```bash
uvx create-agentverse-agent --debug
```

### Common Issues

**Agent not connecting:**
- Check your `AGENT_SEED` is set
- Verify network connectivity
- Ensure correct endpoint configuration

**Import errors:**
- Run `pip install -e .` to install in development mode
- Check Python version compatibility

**Docker build fails:**
- Verify Docker is running
- Check for syntax errors in Dockerfile
- Ensure all files are committed

---

## Getting Help

- [GitHub Issues](https://github.com/tejus3131/create-agentverse-agent/issues)
- [Fetch.ai Discord](https://discord.gg/fetchai)
- [uAgents Documentation](https://fetch.ai/docs)
