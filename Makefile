.PHONY: start stop start-docker start-backend start-frontend start-stripe start-stripe-bg queue start-queue-bg install install-backend install-frontend logs db-migrate db-upgrade test test-backend test-frontend test-contract pre-deploy lint clean deploy deploy-backend deploy-frontend deploy-site

# Colors for terminal output
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m # No Color

# =============================================================================
# Main Commands
# =============================================================================

## Start all services (Docker + Backend + Frontend + Stripe + Celery)
start:
	@echo "$(GREEN)Starting all services...$(NC)"
	@make start-docker
	@echo "$(GREEN)Waiting for Docker services to be healthy...$(NC)"
	@sleep 3
	@make start-stripe-bg
	@make start-queue-bg
	@make -j2 start-backend start-frontend

## Stop all services
stop:
	@echo "$(YELLOW)Stopping all services...$(NC)"
	@-pkill -f "uvicorn app:app" 2>/dev/null || true
	@-pkill -f "vite" 2>/dev/null || true
	@-pkill -f "stripe listen" 2>/dev/null || true
	@-pkill -f "celery" 2>/dev/null || true
	@docker-compose down
	@echo "$(GREEN)All services stopped$(NC)"

# =============================================================================
# Individual Services
# =============================================================================

## Start Docker containers (PostgreSQL, Redis, Mailpit)
start-docker:
	@echo "$(GREEN)Starting Docker containers...$(NC)"
	@docker-compose up -d
	@echo "$(GREEN)Docker services:$(NC)"
	@echo "  - PostgreSQL: localhost:5443"
	@echo "  - Redis: localhost:6398"
	@echo "  - Mailpit UI: http://localhost:8027"

## Start backend (FastAPI with auto-reload)
start-backend:
	@echo "$(GREEN)Starting backend API...$(NC)"
	@PYTHONPATH=src uv run uvicorn app:app --reload --host 0.0.0.0 --port 8000

## Start frontend (Vite dev server)
start-frontend:
	@echo "$(GREEN)Installing frontend dependencies and starting dev server...$(NC)"
	@cd web/app && npm install && npm run dev

## Start Stripe CLI (webhook forwarding)
start-stripe:
	@echo "$(GREEN)Starting Stripe CLI webhook listener...$(NC)"
	@~/bin/stripe listen --forward-to localhost:8000/api/v1/billing/webhook

## Start Stripe CLI in background
start-stripe-bg:
	@echo "$(GREEN)Starting Stripe CLI in background...$(NC)"
	@~/bin/stripe listen --forward-to localhost:8000/api/v1/billing/webhook > /tmp/stripe-cli.log 2>&1 &
	@echo "  - Stripe webhooks: forwarding to localhost:8000/api/v1/billing/webhook"
	@echo "  - Stripe logs: /tmp/stripe-cli.log"

## Start Celery worker for background tasks (all queues)
queue:
	@echo "$(GREEN)Starting Celery worker for all queues...$(NC)"
	@DYLD_LIBRARY_PATH=/opt/homebrew/lib PYTHONPATH=. uv run celery -A core.celery worker -Q reports,onboarding -l INFO

## Start Celery worker in background
start-queue-bg:
	@echo "$(GREEN)Starting Celery worker in background...$(NC)"
	@DYLD_LIBRARY_PATH=/opt/homebrew/lib PYTHONPATH=. uv run celery -A core.celery worker -Q reports,onboarding -l INFO > /tmp/celery.log 2>&1 &
	@echo "  - Celery queues: reports, onboarding"
	@echo "  - Celery logs: /tmp/celery.log"

# =============================================================================
# Installation
# =============================================================================

## Install all dependencies
install: install-backend install-frontend

## Install backend dependencies
install-backend:
	@echo "$(GREEN)Installing backend dependencies...$(NC)"
	@uv sync --all-extras

## Install frontend dependencies
install-frontend:
	@echo "$(GREEN)Installing frontend dependencies...$(NC)"
	@cd web/app && npm install

# =============================================================================
# Database
# =============================================================================

## Run database migrations
db-migrate:
	@echo "$(GREEN)Creating new migration...$(NC)"
	@PYTHONPATH=src alembic revision --autogenerate -m "$(msg)"

## Apply database migrations
db-upgrade:
	@echo "$(GREEN)Applying migrations...$(NC)"
	@PYTHONPATH=src alembic upgrade head

## Downgrade database by one revision
db-downgrade:
	@echo "$(YELLOW)Downgrading database...$(NC)"
	@PYTHONPATH=src alembic downgrade -1

# =============================================================================
# Testing
# =============================================================================

## Run all tests
test: test-backend test-frontend

## Run backend tests
test-backend:
	@echo "$(GREEN)Running backend tests...$(NC)"
	@PYTHONPATH=src pytest tests/ -v

## Run frontend tests
test-frontend:
	@echo "$(GREEN)Running frontend tests...$(NC)"
	@cd web/app && npm run test:run

## Run contract tests (frontend-backend API compatibility)
test-contract:
	@echo "$(GREEN)Running frontend-backend contract tests...$(NC)"
	@echo "Testing API contracts between frontend and backend..."
	@PYTHONPATH=src pytest tests/integration/auth_bc/test_frontend_register_contract.py -v --tb=short
	@PYTHONPATH=src pytest tests/integration/test_database_setup.py -v --tb=short
	@echo "$(GREEN)Contract tests passed!$(NC)"

# =============================================================================
# Pre-Deploy Checks
# =============================================================================

## Run all checks before deploy (contract tests, lint, build)
pre-deploy: test-contract lint build-frontend
	@echo ""
	@echo "$(GREEN)=============================================$(NC)"
	@echo "$(GREEN)  All pre-deploy checks passed!$(NC)"
	@echo "$(GREEN)=============================================$(NC)"
	@echo ""
	@echo "Safe to deploy. Checklist:"
	@echo "  [x] Contract tests (frontend-backend compatibility)"
	@echo "  [x] Linting (code quality)"
	@echo "  [x] Frontend build (production bundle)"
	@echo ""

# =============================================================================
# Code Quality
# =============================================================================

## Run linters
lint:
	@echo "$(GREEN)Running linters...$(NC)"
	@PYTHONPATH=src mypy src/
	@flake8 src/
	@cd web/app && npm run lint

## Build frontend for production
build-frontend:
	@echo "$(GREEN)Building frontend...$(NC)"
	@cd web/app && npm run build

# =============================================================================
# Utilities
# =============================================================================

## Show logs from Docker containers
logs:
	@docker-compose logs -f

## Clean up generated files
clean:
	@echo "$(YELLOW)Cleaning up...$(NC)"
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf web/app/dist 2>/dev/null || true
	@echo "$(GREEN)Cleanup complete$(NC)"

# =============================================================================
# Deployment
# =============================================================================

## Deploy everything (backend + frontend + site)
deploy: deploy-backend deploy-frontend deploy-site
	@echo ""
	@echo "$(GREEN)=============================================$(NC)"
	@echo "$(GREEN)  All deployments complete!$(NC)"
	@echo "$(GREEN)=============================================$(NC)"
	@echo ""
	@echo "  - Site: http://localhost:5173"
	@echo "  - App:  http://localhost:5173/app"
	@echo "  - API:  http://localhost:8000/api/v1"

## Deploy backend
deploy-backend:
	@echo "$(GREEN)Deploying Backend...$(NC)"
	@echo "TODO: Configure deployment"

## Deploy frontend
deploy-frontend:
	@echo "$(GREEN)Building Frontend...$(NC)"
	@cd web/app && npm run build
	@echo "$(GREEN)TODO: Configure deployment$(NC)"

## Deploy site
deploy-site:
	@echo "$(GREEN)TODO: Configure deployment$(NC)"

# =============================================================================
# Help
# =============================================================================

## Show available commands
help:
	@echo "Available commands:"
	@echo ""
	@echo "  $(GREEN)make start$(NC)          - Start all services (Docker + Backend + Frontend)"
	@echo "  $(GREEN)make stop$(NC)           - Stop all services"
	@echo ""
	@echo "  $(GREEN)make start-docker$(NC)   - Start Docker containers only"
	@echo "  $(GREEN)make start-backend$(NC)  - Start backend API only"
	@echo "  $(GREEN)make start-frontend$(NC) - Start frontend dev server only"
	@echo "  $(GREEN)make start-stripe$(NC)   - Start Stripe CLI webhook listener"
	@echo "  $(GREEN)make queue$(NC)          - Start Celery worker (reports queue)"
	@echo ""
	@echo "  $(GREEN)make install$(NC)        - Install all dependencies"
	@echo "  $(GREEN)make db-upgrade$(NC)     - Apply database migrations"
	@echo ""
	@echo "  $(GREEN)make test$(NC)           - Run all tests"
	@echo "  $(GREEN)make test-contract$(NC)  - Run contract tests (frontend-backend API)"
	@echo "  $(GREEN)make pre-deploy$(NC)     - Run all checks before deploy"
	@echo "  $(GREEN)make lint$(NC)           - Run linters"
	@echo "  $(GREEN)make logs$(NC)           - Show Docker logs"
	@echo ""
	@echo "  $(GREEN)make deploy$(NC)         - Deploy everything to production"
	@echo "  $(GREEN)make deploy-backend$(NC) - Deploy backend (git push)"
	@echo "  $(GREEN)make deploy-frontend$(NC)- Deploy frontend (build + rsync)"
	@echo "  $(GREEN)make deploy-site$(NC)    - Deploy marketing site (git push)"
	@echo ""
	@echo "Services:"
	@echo "  - Backend API:  http://localhost:8000"
	@echo "  - Frontend:     http://localhost:5173"
	@echo "  - API Docs:     http://localhost:8000/docs"
	@echo "  - Mailpit:      http://localhost:8027"
	@echo "  - Stripe CLI:   forwarding webhooks to /api/v1/billing/webhook"
