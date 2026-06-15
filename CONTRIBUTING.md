# Contributing to create-agentverse-agent

Thanks for your interest in contributing!
This project was built to stay **simple, predictable, and production-ready**.

Contributions are welcome — bug fixes, improvements, or small enhancements.

---

## 🧰 Development setup

### Requirements

- Python **3.12+**
- `uv` (recommended) or `pip`
- Git

---

### Clone the repository

```bash
git clone https://github.com/tejus3131/create-agentverse-agent.git
cd create-agentverse-agent
```

---

### Install dependencies

```bash
uv sync --dev
```

Or:

```bash
make install-dev  # requires uv package manager (recommended)
```

---

## 🧪 Running checks

Before opening a PR, make sure everything passes locally.

```bash
make check
```

This runs:

* Ruff (lint + autofix)
* Black (formatting)
* ty (type checking)
* Pytest (tests + coverage)

---

## 🧹 Code style & quality

This project enforces:

* **Formatting:** `black`
* **Linting:** `ruff`
* **Type safety:** `ty`
* **Tests:** `pytest`

Pre-commit hooks are configured — please use them.

```bash
pre-commit install
```

---

## 🧠 Design principles

When contributing, keep these in mind:

* Prefer **clarity over cleverness**
* Avoid unnecessary abstractions
* Defaults should be safe and production-friendly
* CLI UX matters — error messages should be helpful
* If it's not needed, don't add it

---

## 📦 Runtime bundle sync

Generated projects include a static copy of the uAgents runtime from [standard-uagents-setup](https://github.com/tejus3131/standard-uagents-setup).

**Bundle** (`src/create_agentverse_agent/bundle/`) — static runtime, schema, Docker files, copied verbatim into projects.

**Templates** (`src/create_agentverse_agent/templates/`) — Jinja files rendered per project (`handler.py`, `.env`, `README.md`, etc.). Not part of bundle sync.

When the reference runtime changes, re-copy into this repo:

```bash
SRC=../standard-uagents-setup
DST=src/create_agentverse_agent/bundle

cp -R "$SRC/src/runtime" "$DST/src/"
cp -R "$SRC/src/shared" "$DST/src/"
cp "$SRC/src/agent/__init__.py" "$DST/src/agent/"
cp "$SRC/schema.sql" "$DST/"
cp "$SRC/Dockerfile" "$DST/"
cp "$SRC/.dockerignore" "$DST/"
cp "$SRC/Makefile" "$DST/" 2>/dev/null || true
cp "$SRC/docker/init-pod-role.sh" "$DST/docker/"
cp "$SRC/uv.lock" "$DST/"
find "$DST" -name '__pycache__' -exec rm -rf {} +
```

Then run tests and update CHANGELOG if behavior changed.

---

## 🔀 Pull request guidelines

* Keep PRs focused and small
* Update tests if behavior changes
* **Update docs** when scaffold output or CLI behavior changes
* Ensure `make check` passes
* Describe **why** the change exists, not just what it does

---

## 🐛 Reporting issues

If you find a bug, please include:

* CLI command used
* Expected vs actual behavior
* Python version
* OS
* Relevant logs (use `--debug` if needed)

---

Thanks again for contributing 🙌
