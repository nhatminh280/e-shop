# ============================================================================
# E-Shop Recommendation System - Makefile
# ============================================================================

.PHONY: help build up down logs status clean test smart-run run

.DEFAULT_GOAL := help

# Color definitions
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
NC := \033[0m

help: ## Show this help message
	@echo "$(GREEN)============================================================================$(NC)"
	@echo "$(GREEN)  E-Shop Recommendation System - Available Commands$(NC)"
	@echo "$(GREEN)============================================================================$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(BLUE)%-25s$(NC) %s\n", $$1, $$2}'
	@echo ""

# ============================================================================
# Build & Infrastructure
# ============================================================================

build: ## Build Docker images
	@echo "$(BLUE)Building Docker images...$(NC)"
	cd Docker && docker compose build

up: ## Start all services
	@echo "$(BLUE)Starting services...$(NC)"
	cd Docker && docker compose up -d postgres redis
	@sleep 5
	cd Docker && docker compose up -d api

down: ## Stop all services
	@echo "$(BLUE)Stopping services...$(NC)"
	cd Docker && docker compose down

restart: down up ## Restart all services

# ============================================================================
# Smart Pipeline Commands
# ============================================================================

smart-run: ## Smart pipeline - auto-skip completed steps (RECOMMENDED)
	@echo "$(GREEN)Running smart pipeline...$(NC)"
	@chmod +x Docker/smart_pipeline.sh
	@cd Docker && ./smart_pipeline.sh auto

run: smart-run ## Alias for smart-run

pipeline-status: ## Show pipeline status
	@echo "$(BLUE)Checking pipeline status...$(NC)"
	@chmod +x Docker/smart_pipeline.sh
	@cd Docker && ./smart_pipeline.sh status

force-etl: ## Force re-run ETL
	@cd Docker && ./smart_pipeline.sh force-etl

force-clip: ## Force re-run CLIP
	@cd Docker && ./smart_pipeline.sh force-clip

force-workflow: ## Force re-run workflow
	@cd Docker && ./smart_pipeline.sh force-workflow

force-faiss: ## Force rebuild legacy FAISS index
	@cd Docker && ./smart_pipeline.sh force-faiss

force-qdrant: ## Force rebuild Qdrant collection
	@cd Docker && ./smart_pipeline.sh force-qdrant

force-all: ## Force complete re-run
	@cd Docker && ./smart_pipeline.sh force-all

# ============================================================================
# SCHEDULER COMMANDS 
# ============================================================================

scheduler-start: ## Start scheduler daemon
	@echo "$(BLUE)Starting scheduler...$(NC)"
	cd Docker && docker compose --profile scheduler up -d scheduler
	@sleep 2
	@echo "$(GREEN)Scheduler started$(NC)"
	@make scheduler-status

scheduler-stop: ## Stop scheduler
	@echo "$(BLUE)Stopping scheduler...$(NC)"
	cd Docker && docker compose stop scheduler
	@echo "$(GREEN)Scheduler stopped$(NC)"

scheduler-restart: scheduler-stop scheduler-start ## Restart scheduler

scheduler-logs: ## Show scheduler logs
	cd Docker && docker compose logs -f scheduler

scheduler-status: ## Show scheduler status
	@echo "$(BLUE)Scheduler Status:$(NC)"
	@cd Docker && docker compose ps scheduler
	@echo ""
	@echo "$(BLUE)Recent logs:$(NC)"
	@cd Docker && docker compose logs --tail=20 scheduler

scheduler-run-once: ## Run full pipeline once via scheduler
	@echo "$(BLUE)Running pipeline once...$(NC)"
	cd Docker && docker compose run --rm scheduler python scheduler.py --run-once

scheduler-task: ## Run specific task (usage: make scheduler-task TASK=etl)
	@echo "$(BLUE)Running task: $(TASK)$(NC)"
	cd Docker && docker compose run --rm scheduler python scheduler.py --task $(TASK)

scheduler-config: ## Show scheduler configuration
	@echo "$(BLUE)Scheduler Configuration:$(NC)"
	@cat Docker/scheduler_config.json | python3 -m json.tool

scheduler-edit-config: ## Edit scheduler configuration
	@${EDITOR:-nano} Docker/scheduler_config.json

# ============================================================================
# Individual Pipeline Stages (Manual)
# ============================================================================

etl: ## Run ETL only
	@echo "$(BLUE)Running ETL...$(NC)"
	cd Docker && docker compose --profile etl up etl

clip: ## Generate CLIP embeddings
	@echo "$(BLUE)Generating CLIP embeddings...$(NC)"
	cd Docker && docker compose --profile clip up clip-embeddings

workflow: ## Run hybrid workflow
	@echo "$(BLUE)Running hybrid workflow...$(NC)"
	cd Docker && docker compose --profile workflow up workflow

build-index: ## Build Qdrant collection
	@echo "$(BLUE)Building Qdrant collection...$(NC)"
	cd Docker && docker compose --profile build-index up build-qdrant

rebuild-index: build-index ## Rebuild Qdrant collection and restart API
	@echo "$(BLUE)Restarting API...$(NC)"
	cd Docker && docker compose restart api

# ============================================================================
# Development
# ============================================================================

api: ## Start API server only
	@echo "$(BLUE)Starting API server...$(NC)"
	cd Docker && docker compose up -d postgres redis qdrant api
	@sleep 3
	@echo "$(GREEN)API available at: http://localhost:8000$(NC)"
	@echo "$(GREEN)API docs at: http://localhost:8000/docs$(NC)"

gradio: ## Start API + Gradio UI
	@echo "$(BLUE)Starting API + Gradio...$(NC)"
	cd Docker && docker compose --profile testing up -d api gradio-tester
	@sleep 3
	@echo "$(GREEN)API: http://localhost:8000$(NC)"
	@echo "$(GREEN)Gradio: http://localhost:7860$(NC)"

logs: ## Show API logs
	cd Docker && docker compose logs -f api

logs-all: ## Show all logs
	cd Docker && docker compose logs -f

status: ## Show system status
	@echo "$(BLUE)Container Status:$(NC)"
	@cd Docker && docker compose ps
	@echo ""
	@echo "$(BLUE)API Health:$(NC)"
	@curl -s http://localhost:8000/health 2>/dev/null | python3 -m json.tool || echo "$(YELLOW)API not available$(NC)"

# ============================================================================
# Testing
# ============================================================================

test: ## Run tests
	@echo "$(BLUE)Running tests...$(NC)"
	cd Docker && docker compose exec api pytest tests/ -v

test-api: ## Test API endpoints
	@echo "$(BLUE)Testing API endpoints...$(NC)"
	python etl/testAPI.py

benchmark: ## Run benchmark
	@echo "$(BLUE)Running benchmark...$(NC)"
	cd Docker && docker compose exec api python testAPI.py

# ============================================================================
# Database
# ============================================================================

db-shell: ## Connect to PostgreSQL
	cd Docker && docker compose exec postgres psql -U app -d eshop

redis-cli: ## Connect to Redis
	cd Docker && docker compose exec redis redis-cli

# ============================================================================
# Maintenance
# ============================================================================

clean: ## Remove containers and volumes
	@echo "$(YELLOW)Removing containers and volumes...$(NC)"
	cd Docker && docker compose down -v

clean-data: ## Remove processed data
	@echo "$(YELLOW)Removing processed data...$(NC)"
	rm -rf etl/data/processed/*.npy
	rm -rf etl/data/processed/*.pkl
	rm -rf etl/data/faiss/*.faiss
	rm -rf etl/logs/*.log

clean-all: clean clean-data ## Clean everything
	@echo "$(GREEN)Everything cleaned$(NC)"

prune: ## Prune Docker resources
	@echo "$(YELLOW)Pruning Docker resources...$(NC)"
	docker system prune -f

# ============================================================================
# Quick Start Guides
# ============================================================================

first-time: ## First time setup (run complete pipeline)
	@echo "$(GREEN)============================================================================$(NC)"
	@echo "$(GREEN)  First Time Setup$(NC)"
	@echo "$(GREEN)============================================================================$(NC)"
	@echo ""
	@make build
	@make smart-run

first-time-scheduled: ## Setup with automatic scheduling
	@echo "$(GREEN)============================================================================$(NC)"
	@echo "$(GREEN)  First Time Setup with Scheduler$(NC)"
	@echo "$(GREEN)============================================================================$(NC)"
	@echo ""
	@make build
	@make smart-run
	@make scheduler-start
	@echo ""
	@echo "$(GREEN)Setup complete! Scheduler will run daily at 2 AM$(NC)"

dev: ## Development mode (build and start API)
	@echo "$(GREEN)Development Mode$(NC)"
	@make build
	@make api
	@make logs

production: ## Production deployment with scheduler
	@echo "$(GREEN)Production Deployment$(NC)"
	@make build
	@make smart-run
	cd Docker && docker compose up -d api scheduler
	@echo ""
	@echo "$(GREEN)Services running:$(NC)"
	@echo "  - API Server"
	@echo "  - Scheduler (daily at 2 AM)"

# ============================================================================
# Information
# ============================================================================

info: ## Show system information
	@echo "$(BLUE)============================================================================$(NC)"
	@echo "$(BLUE)  System Information$(NC)"
	@echo "$(BLUE)============================================================================$(NC)"
	@echo ""
	@echo "Docker Version: $$(docker --version)"
	@echo "Docker Compose Version: $$(docker compose version)"
	@echo ""
	@echo "$(BLUE)Project Structure:$(NC)"
	@echo "  - ETL: etl/run_etl.py"
	@echo "  - CLIP: etl/clip_embedding_pipeline.py"
	@echo "  - Workflow: etl/workFLow.py"
	@echo "  - Legacy FAISS: etl/Content_Base_Model/build_faiss_index.py"
	@echo "  - Qdrant: etl/Content_Base_Model/build_qdrant_index.py"
	@echo "  - API: etl/Content_Base_Model/recommendation_api.py"
	@echo "  - Scheduler: etl/scheduler.py"
	@echo ""
	@make status

# Aliases
start: api ## Alias for 'api'
stop: down ## Alias for 'down'
sched: scheduler-start ## Short alias for scheduler-start
