# Changelog

All notable changes to this project are documented here.

---

# [1.0.1]

- Fix Agentverse registration and Docker packaging
- Fix payment commit validation when multiple payment methods are offered
- Exclude markdown files from Docker build context

---

# [1.0.0]

**Breaking:** Complete migration to standard uAgents multipod runtime scaffold.

- New generated layout: `agent.yml` + `.env`, nested `src/runtime`, `src/shared`, `src/agent`
- Postgres-backed coordination via bundled `schema.sql` and Docker Compose
- Chat + payment protocols, FET/Stripe/Skyfire payments (configurable)
- uv + Python 3.13 generated projects (replaces Poetry flat scaffold)
- Static runtime bundle copied from [standard-uagents-setup](https://github.com/tejus3131/standard-uagents-setup)
- Removed legacy flat templates (`main.py`, `agent.py`, Makefile, etc.)
- CLI wizard rewritten: identity, network, Postgres, Agentverse, advanced payments
- Default payment config: FET enabled, Stripe/Skyfire disabled
- Fixed cancel handlers (proper exit code), ScaffoldError handling

---

# [0.2.7]

- Fixed hosting settings option in advanced mode.

---

# [0.2.6]

- Updated README to include test command.
- Added fallback chat method in test.py and main.py
- Updated message structure in agent.py

---

# [0.2.5]

- Updated Docker template for better package installation

---

# [0.2.4]

- Added streamlit to dev dependencies
- New test template for tesing without agentverse
- New make command for starting streamlit server

---

# [0.2.3]

- New make command to run agent in poetry environment
- Updated Dockerfile Template to include README.md in container
- Updated README Template for usage instruction
- Updated CLI instruction at project generation

---

## [0.2.2]

- Added initial docs
- Updated tests that failed in previous ci

---

## [0.2.1]

- New context module for improved state management
- Enhanced prompt system with expanded configuration options
- New Makefile template for agent project management
- New .env template with comprehensive environment variables
- New README template for generated projects
- Template reorganization (template..env.j2 replaces template.env.j2)
- Removed requirements.txt template in favor of pyproject.toml
- Updated CLI with improved argument handling
- Expanded test coverage across all modules
- Pre-commit configuration improvements
- Project configuration updates for better compatibility

---

## [0.2.0]

- Initial stable release
- Interactive and non-interactive CLI modes
- Production-ready uAgent scaffolding
- Agentverse-compatible defaults
- Parallel message handling support
- Context-based logging
- Health and quota protocol support
- Docker and Docker Compose templates
