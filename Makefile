# =============================================================================
# Configuration
# =============================================================================

UV              := uv
UV_RUN          := uv run
PACKAGE_NAME    := create-agentverse-agent

PYTEST_ARGS     := tests/ -v --cov=. --cov-report=term-missing
RUFF_ARGS       := .
BLACK_ARGS      := .
TY_ARGS         := .

# =============================================================================
# Phony targets
# =============================================================================

.PHONY: help \
        install install-dev reinstall \
        lint lint-fix format typecheck test check \
        clean clean-caches clean-build \
        pre-commit pre-commit-install

# =============================================================================
# Help
# =============================================================================

help:
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@echo "Development:"
	@echo "  install            Install production dependencies"
	@echo "  install-dev        Install production + dev dependencies"
	@echo "  reinstall          Clean and reinstall dev dependencies"
	@echo "  pre-commit-install Install pre-commit hooks"
	@echo ""
	@echo "Quality:"
	@echo "  lint               Run ruff lint checks"
	@echo "  lint-fix           Run ruff with auto-fix"
	@echo "  format             Format code with black"
	@echo "  typecheck          Run ty type checker"
	@echo "  test               Run pytest with coverage"
	@echo "  check              Run full quality pipeline (lint-fix + format + typecheck + test)"
	@echo "  pre-commit         Run pre-commit on all files"
	@echo ""
	@echo "Maintenance:"
	@echo "  clean              Remove all caches and build artifacts"
	@echo "  clean-caches       Remove only cache directories"
	@echo "  clean-build        Remove only build artifacts"
	@echo ""

# =============================================================================
# Dependency management
# =============================================================================

install:
	@echo "📦 Installing dependencies..."
	@$(UV) sync

install-dev:
	@echo "📦 Installing dev dependencies..."
	@$(UV) sync --dev

reinstall: clean
	@echo "🔄 Reinstalling dependencies..."
	@$(UV) sync --dev

pre-commit-install:
	@echo "🪝 Installing pre-commit hooks..."
	@$(UV_RUN) pre-commit install

# =============================================================================
# Quality checks
# =============================================================================

lint:
	@echo "🔍 Running ruff lint..."
	@$(UV_RUN) ruff check $(RUFF_ARGS)

lint-fix:
	@echo "🔧 Running ruff with auto-fix..."
	@$(UV_RUN) ruff check $(RUFF_ARGS) --fix

format:
	@echo "✨ Formatting with black..."
	@$(UV_RUN) black $(BLACK_ARGS)

typecheck:
	@echo "🔎 Running ty type checker..."
	@$(UV_RUN) ty check $(TY_ARGS)

test:
	@echo "🧪 Running tests..."
	@$(UV_RUN) pytest $(PYTEST_ARGS)

pre-commit:
	@echo "🪝 Running pre-commit on all files..."
	@$(UV_RUN) pre-commit run --all-files

check: lint-fix format typecheck test
	@echo ""
	@echo "✅ All checks passed!"
	@echo ""

# =============================================================================
# Cleanup
# =============================================================================

clean: clean-caches clean-build
	@echo "🧹 Clean complete."

clean-caches:
	@echo "🗑️  Removing caches..."
	@rm -rf .ruff_cache .pytest_cache .coverage
	@find . -type d -name "__pycache__" -prune -exec rm -rf {} +

clean-build:
	@echo "🗑️  Removing build artifacts..."
	@rm -rf dist/ build/ *.egg-info

# =============================================================================
# Build & Release
# =============================================================================

build: check
	@echo "📦 Building package..."
	@$(UV) build

# =============================================================================
# Development helpers
# =============================================================================

watch-typecheck:
	@echo "👀 Watching for type errors..."
	@$(UV_RUN) ty check --watch

dev: install-dev pre-commit-install
	@echo ""
	@echo "✅ Development environment ready!"
	@echo ""
	@echo "Run 'make check' to verify your setup"
	@echo ""
