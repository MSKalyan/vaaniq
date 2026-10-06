.PHONY: help setup backend-install frontend-install dev backend frontend worker \
	db-up db-migrate db-migrate-autogen db-downgrade db-shell test test-backend \
	test-frontend lint lint-backend lint-frontend typecheck typecheck-backend \
	typecheck-frontend docker-up docker-down docker-up-prod tunnel logs format clean backup

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-24s\033[0m %s\n", $$1, $$2}'

# ---------- Setup ----------
setup: ## Install all dependencies
	$(MAKE) backend-install frontend-install
	cp -n .env.example .env || true
	@echo "Copied .env.example -> .env (edit values)"

backend-install: ## Install backend deps (uv)
	cd apps/api && uv sync

frontend-install: ## Install frontend deps (pnpm)
	cd apps/web && pnpm install

# ---------- Dev servers ----------
dev: ## Run backend + frontend + worker
	$(MAKE) backend & $(MAKE) frontend & $(MAKE) worker & wait

backend: ## Run FastAPI dev server
	cd apps/api && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend: ## Run Next.js dev server
	cd apps/web && pnpm dev

worker: ## Run Celery worker
	cd apps/api && celery -A app.workers.celery_app.celery_app worker --loglevel=info

# ---------- Database ----------
db-up: ## Start PostgreSQL + Redis via docker compose
	docker compose up -d postgres redis

db-migrate: ## Apply Alembic migrations
	cd apps/api && alembic upgrade head

db-migrate-autogen: ## Autogenerate a migration after model changes
	cd apps/api && alembic revision --autogenerate -m "$(m)"

db-downgrade: ## Rollback last migration
	cd apps/api && alembic downgrade -1

db-shell: ## Open psql into the app database
	docker compose exec postgres psql -U nenu -d VoiceAI

# ---------- Tests ----------
test: ## Run all tests
	$(MAKE) test-backend test-frontend

test-backend: ## Run backend pytest suite
	cd apps/api && pytest

test-frontend: ## Run frontend tests
	cd apps/web && pnpm test

# ---------- Lint / typecheck ----------
lint: ## Lint all
	$(MAKE) lint-backend lint-frontend

lint-backend: ## Ruff lint + format check
	cd apps/api && ruff check . && ruff format --check .

lint-frontend: ## ESLint
	cd apps/web && pnpm lint

typecheck: ## Typecheck all
	$(MAKE) typecheck-backend typecheck-frontend

typecheck-backend: ## mypy typecheck
	cd apps/api && mypy app

typecheck-frontend: ## tsc no-emit
	cd apps/web && tsc --noEmit

# ---------- Docker ----------
docker-up: ## Full dev stack
	docker compose up --build

tunnel: ## Start the ngrok tunnel (Twilio webhooks/media stream)
	docker compose --profile ngrok up -d ngrok
	docker compose logs -f ngrok

docker-down: ## Stop dev stack
	docker compose down

docker-up-prod: ## Production stack
	docker compose -f docker-compose.prod.yml up --build -d

# ---------- Utilities ----------
logs: ## Tail all services
	docker compose logs -f

format: ## Format backend + frontend
	cd apps/api && ruff format .
	cd apps/web && pnpm format

clean: ## Remove caches and build artifacts
	cd apps/api && find . -name __pycache__ -type d -prune -exec rm -rf {} + 
	cd apps/web && rm -rf .next node_modules

backup: ## Dump database to ./scripts/backups
	mkdir -p scripts/backups
	docker compose exec -T postgres pg_dump -U nenu VoiceAI > scripts/backups/VoiceAI_$$(date +%Y%m%d_%H%M%S).sql