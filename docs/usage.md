---
layout: default
title: Usage
nav_order: 3
---

# Usage Guide

This guide covers all CLI options and common usage patterns.

---

## Interactive Mode (Recommended)

Launch the interactive wizard to configure your agent step by step:

```bash
uvx create-agentverse-agent
```

The wizard will guide you through:
- Project name and location
- Agent configuration
- Feature selection
- Dependency preferences

---

## Quick Start with Defaults

Skip all prompts and generate an agent using sensible defaults:

```bash
uvx create-agentverse-agent --default
# or
uvx create-agentverse-agent -d
```

**Best for:** Rapid prototyping, automation, or CI pipelines.

---

## Advanced Configuration Mode

Enable advanced mode to access all available configuration options:

```bash
uvx create-agentverse-agent --advanced
# or
uvx create-agentverse-agent -a
```

This unlocks additional options not shown in standard interactive mode.

---

## CLI Options Reference

| Option | Short | Description |
|--------|-------|-------------|
| `--default` | `-d` | Use default values, skip prompts |
| `--advanced` | `-a` | Show all configuration options |
| `--overwrite` | `-o` | Overwrite existing project directory |
| `--debug` | | Enable debug logging |
| `--version` | `-v` | Show version and exit |
| `--help` | | Show help message |

---

## Overwrite Existing Project

If a project already exists in the target directory:

```bash
uvx create-agentverse-agent --overwrite
# or
uvx create-agentverse-agent -o
```

⚠️ **Warning:** This will replace existing files without prompting.

---

## Debug Mode

Run with debug logging enabled for troubleshooting:

```bash
uvx create-agentverse-agent --debug
```

This creates a detailed log file in the current directory:

```
create-agentverse-agent-<version>-cli-execution-<uuid>.log
```

**Useful for:** Troubleshooting issues or filing bug reports.

---

## Examples

### Create a new agent interactively

```bash
uvx create-agentverse-agent
```

### Quick prototype in current directory

```bash
uvx create-agentverse-agent -d
```

### Full configuration with overwrite

```bash
uvx create-agentverse-agent -a -o
```

### Debug a failing scaffold

```bash
uvx create-agentverse-agent --debug
```

---

## Next Steps

Learn about what gets generated in [Generated Structure](structure.md).
