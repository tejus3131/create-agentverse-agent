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
````

---

### Install dependencies

```bash
make install-dev  # requires uv package manager (recommended)
```

Or with pip:

```bash
pip install -e ".[dev]"
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
* Mypy (type checking)
* Pytest (tests + coverage)

---

## 🧹 Code style & quality

This project enforces:

* **Formatting:** `black`
* **Linting:** `ruff`
* **Type safety:** `mypy --strict`
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
* If it’s not needed, don’t add it

---

## 🔀 Pull request guidelines

* Keep PRs focused and small
* Update tests if behavior changes
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
