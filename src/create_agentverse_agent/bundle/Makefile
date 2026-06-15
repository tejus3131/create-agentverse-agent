.PHONY: help db test run down

# Local mailbox dev: Postgres in Docker, agent on host (uv run agent).
# Full stack after registration: make run

help:
	@echo "Usage:"
	@echo "  make db    Start Postgres only (docker compose)"
	@echo "  make test  Start db + run agent locally (uv run agent)"
	@echo "  make run   Start full stack (docker compose up)"
	@echo "  make down  Stop docker compose services"

db:
	docker compose up -d db

test: db
	uv run agent

run:
	docker compose up

down:
	docker compose down
