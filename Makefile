# =============================================================================
# Configuration
# =============================================================================

UV              := uv
UV_RUN          := uv run
PACKAGE_NAME    := create-agentverse-agent

PYTEST_ARGS     := tests/ -v --cov=.
RUFF_ARGS       := .
BLACK_ARGS      := .
MYPY_ARGS       := .

# =============================================================================
# Phony targets
# =============================================================================

.PHONY: help \
        install install-dev reinstall \
        lint lint-fix format typecheck test check \
        clean clean-caches

# =============================================================================
# Help
# =============================================================================

help:
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@echo "Development:"
	@echo "  install        Install production dependencies"
	@echo "  install-dev    Install production + dev dependencies"
	@echo "  reinstall      Clean and reinstall dev dependencies"
	@echo ""
	@echo "Quality:"
	@echo "  lint           Run ruff lint checks"
	@echo "  lint-fix       Run ruff with auto-fix"
	@echo "  format         Format code with black"
	@echo "  typecheck      Run mypy"
	@echo "  test           Run pytest with coverage"
	@echo "  check          Run full quality pipeline"
	@echo ""
	@echo "Maintenance:"
	@echo "  clean          Remove caches and build artifacts"
	@echo ""

# =============================================================================
# Dependency management
# =============================================================================

install:
	@echo "Installing dependencies..."
	@$(UV) sync

install-dev:
	@echo "Installing dev dependencies..."
	@$(UV) sync --dev

reinstall: clean
	@echo "Reinstalling dependencies..."
	@$(UV) sync --dev

# =============================================================================
# Quality checks
# =============================================================================

lint:
	@echo "Running ruff lint..."
	@$(UV_RUN) ruff check $(RUFF_ARGS)

lint-fix:
	@echo "Running ruff with auto-fix..."
	@$(UV_RUN) ruff check $(RUFF_ARGS) --fix

format:
	@echo "Formatting with black..."
	@$(UV_RUN) black $(BLACK_ARGS)

typecheck:
	@echo "Running mypy..."
	@$(UV_RUN) mypy $(MYPY_ARGS)

test:
	@echo "Running tests..."
	@$(UV_RUN) pytest $(PYTEST_ARGS)

check: lint-fix format typecheck test
	@echo ""
	@echo "✅ All checks passed"

# =============================================================================
# Cleanup
# =============================================================================

clean: clean-caches
	@echo "Clean complete."

clean-caches:
	@echo "Removing caches..."
	@rm -rf .mypy_cache .ruff_cache .pytest_cache
	@find . -type d -name "__pycache__" -prune -exec rm -rf {} +
