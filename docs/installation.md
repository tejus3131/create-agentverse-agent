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

**Requirements:** [uv](https://github.com/astral-sh/uv) must be installed.

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

**Best for:** Projects already using Poetry for dependency management.

---

## Verify Installation

Check that the installation was successful:

```bash
create-agentverse-agent --version
```

You should see the current version number printed.

---

## Next Steps

Once installed, head to the [Usage Guide](usage.md) to learn how to create your first agent.
