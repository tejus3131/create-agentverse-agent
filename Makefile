# -----------------------------
# Configuration
# -----------------------------
UV              = uv
UV_RUN          = uv run
PACKAGE_NAME    = create-agentverse-agent
DIST_DIR        = dist

# -----------------------------
# Phony targets
# -----------------------------
.PHONY: help \
        install install-dev reinstall \
        lint lint-fix format typecheck test check \
        build publish login \
        clean

# -----------------------------
# Help
# -----------------------------
help:
	@echo ""
	@echo "Development:"
	@echo "  make install        Install project dependencies"
	@echo "  make install-dev    Install project + dev dependencies"
	@echo "  make reinstall      Reinstall dependencies from scratch"
	@echo ""
	@echo "Quality:"
	@echo "  make lint           Run ruff lint checks"
	@echo "  make lint-fix       Run ruff with auto-fix"
	@echo "  make format         Format code with black"
	@echo "  make typecheck      Run mypy"
	@echo "  make test           Run pytest"
	@echo "  make check          Full check (lint → format → typecheck → test)"
	@echo ""
	@echo "Release:"
	@echo "  make build          Build wheel + sdist"
	@echo "  make publish        Publish to PyPI"
	@echo "  make login          Login to PyPI (uv auth)"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean          Remove build and cache artifacts"
	@echo ""

# -----------------------------
# Install
# -----------------------------
install:
	$(UV) sync

install-dev:
	$(UV) sync --dev

reinstall: clean
	$(UV) sync --dev

# -----------------------------
# Quality
# -----------------------------
lint:
	$(UV_RUN) ruff check .

lint-fix:
	$(UV_RUN) ruff check . --fix

format:
	$(UV_RUN) black .

typecheck:
	$(UV_RUN) mypy .

test:
	$(UV_RUN) pytest

check: lint-fix format typecheck test

# -----------------------------
# Build & Publish
# -----------------------------
build: clean
	$(UV) build

login:
	$(UV) auth login

publish: check build
	$(UV) publish

# -----------------------------
# Cleanup
# -----------------------------
clean:
	rm -rf \
		.mypy_cache \
		.ruff_cache \
		.pytest_cache \
		__pycache__ \
		$(DIST_DIR) \
		build
	find . -type d -name "__pycache__" -exec rm -rf {} +
