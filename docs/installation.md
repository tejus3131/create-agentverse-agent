---
layout: default
title: Installation
nav_order: 2
---

# Installation

There are multiple ways to install and run `create-agentverse-agent`. Choose the method that best fits your workflow.

---

## ⭐ Recommended: uvx (No Install)

The easiest way to use the tool — no installation required, similar to `npx`:

```bash
uvx create-agentverse-agent
```

This downloads and runs the latest version in an isolated environment. Perfect for one-off usage or trying out the tool.

**Requirements:** [uv](https://github.com/astral-sh/uv) must be installed. Python **3.12+** for the CLI itself.

---

## Local Development (CLI contributors)

Run the CLI from a local checkout without publishing:

```bash
uvx --from /path/to/create-agentverse-agent create-agentverse-agent -d
```

Or install editable:

```bash
uv tool install --editable .
create-agentverse-agent --version
```

See [CONTRIBUTING.md](https://github.com/tejus3131/create-agentverse-agent/blob/main/CONTRIBUTING.md) for `make check` and bundle sync.

---

## Generated Project Requirements

Scaffolded agents are separate projects with their own toolchain:

| Requirement | Why |
|-------------|-----|
| Python **3.13** | Locked in generated `pyproject.toml` |
| [uv](https://github.com/astral-sh/uv) | Dependency management (`uv sync`) |
| Docker | Local Postgres via `docker compose` / `make db` |

---

## Using pipx (Global, Isolated)

Install globally in an isolated environment:

```bash
pipx install create-agentverse-agent
create-agentverse-agent
```

**Best for:** Users who want the CLI always available without polluting their global Python environment.

---

## Using pip

Install directly with pip:

```bash
pip install create-agentverse-agent
create-agentverse-agent
```

**Best for:** Adding to existing projects or virtual environments.

---

## Using Poetry

Add as a dependency in a Poetry-managed project:

```bash
poetry add create-agentverse-agent
poetry run create-agentverse-agent
```

**Note:** Poetry installs the **scaffolder CLI only**. Generated agent projects use **uv** and **hatch**, not Poetry.

---

## Verify Installation

Check that the installation was successful:

```bash
create-agentverse-agent --version
```

You should see the current version number printed.

---

## Next Steps

Once installed, head to [Getting Started](getting-started.md) or the [Usage Guide](usage.md).
