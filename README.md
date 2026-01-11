# create-agentverse-agent

[![Fetch.ai](https://img.shields.io/badge/Fetch.ai-Ecosystem-blue?logo=fetch.ai&logoColor=white)](https://fetch.ai)
[![PyPI](https://img.shields.io/pypi/v/create-agentverse-agent?cacheSeconds=300)](https://pypi.org/project/create-agentverse-agent/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/create-agentverse-agent?cacheSeconds=300)](https://pypi.org/project/create-agentverse-agent/)
[![License](https://img.shields.io/github/license/tejus3131/create-agentverse-agent)](LICENSE)
[![CI](https://github.com/tejus3131/create-agentverse-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/tejus3131/create-agentverse-agent/actions/workflows/ci.yml)
[![Docs](https://img.shields.io/badge/docs-github--pages-blue)](https://tejus3131.github.io/create-agentverse-agent/)
[![Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://black.readthedocs.io/)
[![Ruff](https://img.shields.io/badge/lint-ruff-red)](https://docs.astral.sh/ruff/)
[![Mypy](https://img.shields.io/badge/type%20check-mypy-blue)](https://mypy.readthedocs.io/)

> 📖 **Full Documentation:** [tejus3131.github.io/create-agentverse-agent](https://tejus3131.github.io/create-agentverse-agent/)

A CLI tool to scaffold **production-ready uAgents** with best practices baked in — in seconds.

---

## 🚀 Why this exists

Building agents with **uAgents** is powerful, but setting things up *correctly* every time is not trivial.

This tool solves that by generating a **production-grade agent scaffold** with:

- ⚡ Parallel message processing
- 🧠 Context-aware logging
- 📡 Progress / status message support
- 🩺 Built-in health & quota protocol
- 🤖 AAgentverse-compatible Agents
- 🧱 Clean, extensible project structure
- 🛠 Sensible defaults that don’t fight you later

Instead of starting from scratch (or copying old projects), you get a **clean, consistent, battle-tested starting point** every time.

---

## 👥 Who is this for?

This tool is designed for **all of the following**:

- uAgents developers
- Agentverse builders
- Hackathon & rapid-prototyping teams
- Python developers who want a clean CLI-driven workflow

If you build agents more than once — this saves you time.

---

## 📦 Installation

> 📦 PyPI: [https://pypi.org/project/create-agentverse-agent/](https://pypi.org/project/create-agentverse-agent/)

### ⭐ Recommended: `uvx` (no install, like `npx`)

```bash
uvx create-agentverse-agent
```

That’s it. No environment pollution, no setup.

---

### Using `pipx` (global, isolated)

```bash
pipx install create-agentverse-agent
create-agentverse-agent
```

---

### Using `pip`

```bash
pip install create-agentverse-agent
create-agentverse-agent
```

---

### Using Poetry

```bash
poetry add create-agentverse-agent
poetry run create-agentverse-agent
```

---

## 🧑‍💻 Usage

### Interactive setup (recommended)

Launch the interactive wizard to configure your agent step by step:

```bash
uvx create-agentverse-agent
```

---

### Quick start with defaults

Skip all prompts and generate an agent using sensible defaults:

```bash
uvx create-agentverse-agent --default
# or
uvx create-agentverse-agent -d
```

Ideal for rapid prototyping, automation, or CI pipelines.

---

### Advanced configuration mode

Enable **advanced mode** to access all available configuration options:

```bash
uvx create-agentverse-agent --advanced
# or
uvx create-agentverse-agent -a
```

Use this if you want full control over the generated agent setup.

---

### Overwrite existing project

If a project already exists in the target directory, you can overwrite it:

```bash
uvx create-agentverse-agent --overwrite
# or
uvx create-agentverse-agent -o
```

⚠️ This will replace existing files.

---

### Debug mode

Run the CLI with debug logging enabled.
A detailed log file will be created in the current directory:

```bash
uvx create-agentverse-agent --debug
```

Log file format:

```
create-agentverse-agent-<version>-cli-execution-<uuid>.log
```

Useful for troubleshooting or reporting issues.

---

### Show version

Display the installed version and exit:

```bash
uvx create-agentverse-agent --version
# or
uvx create-agentverse-agent -v
```

---

### Help

Show the full help message with all options and examples:

```bash
uvx create-agentverse-agent --help
```

---

## 🧱 What gets generated?

The scaffold is designed to be **production-ready from day one**, not a demo:

* Agent entrypoint
* Proper async message handling
* Agentverse-compatible configuration
* Logging & context utilities
* Health & quota protocol support
* Docker & Docker Compose templates
* Clean dependency management
* Minimal but extensible structure

You can ship this, not just demo it.

---

## 📚 Documentation

Full documentation is available at **[tejus3131.github.io/create-agentverse-agent](https://tejus3131.github.io/create-agentverse-agent/)**

| Guide | Description |
|-------|-------------|
| [Installation](https://tejus3131.github.io/create-agentverse-agent/installation) | Multiple installation methods |
| [Usage](https://tejus3131.github.io/create-agentverse-agent/usage) | CLI options and examples |
| [Generated Structure](https://tejus3131.github.io/create-agentverse-agent/structure) | What gets created |
| [Configuration](https://tejus3131.github.io/create-agentverse-agent/configuration) | Customization options |

---

## 🧠 Design philosophy

* **Opinionated, but not restrictive**
* **Defaults that scale**
* **Explicit over clever**
* **Production first, demos second**

This tool exists because repeatedly hand-rolling agent scaffolds is boring — and error-prone.

---

## 🧑‍🏫 Author

**Tejus Gupta**
🌐 [https://tejusgupta.dev](https://tejusgupta.dev)
📧 [hello@tejusgupta.dev](mailto:hello@tejusgupta.dev)

Built as a weekend project — because sometimes the best tools come from *personal pain* 😭

---

## 📄 License

MIT License.
See [`LICENSE`](LICENSE) for details.

---

## 🤝 Contributing

Contributions are welcome!

Please read:
- [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) to understand community expectations
- [CHANGELOG.md](CHANGELOG.md) to see recent changes

---

Made with ❤️ by [Tejus Gupta](https://tejusgupta.dev).
