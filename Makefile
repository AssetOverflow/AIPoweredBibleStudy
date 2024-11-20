.PHONY: help setup build run stop clean logs test dev prod setup-traefik setup-hosts setup-ssl check-traefik prod-deploy check-domain build-all build-backend build-frontend build-no-cache up down restart ps top system-prune system-clean system-reset dev-build dev-up dev-down dev-restart prod-build prod-up prod-down prod-restart logs-all logs-backend logs-frontend logs-follow shell-backend shell-frontend

# Variables
DOMAIN=divine-haven.org
SUBDOMAINS=www api dashboard redis insight
DOCKER_COMPOSE=docker compose
NODE_ENV ?= development

# Default target
help:
	@echo "Available commands:"
	@echo "  make setup           - Initial setup (create directories, env files)"
	@echo "  make build          - Build all containers"
	@echo "  make run            - Run in API mode (default)"
	@echo "  make dev            - Run in development mode with hot reload"
	@echo "  make cli            - Run in CLI mode"
	@echo "  make stop           - Stop all containers"
	@echo "  make clean          - Remove all containers and volumes"
	@echo "  make logs           - View logs"
	@echo "  make test           - Run tests"
	@echo "  make setup-traefik  - Setup Traefik configuration and certificates"
	@echo "  make setup-hosts    - Add local domains to /etc/hosts"
	@echo "  make setup-ssl      - Generate local SSL certificates"
	@echo "  make prod-deploy    - Deploy to production"
	@echo "  make check-domain   - Check domain DNS configuration"
	@echo "  make build-all      - Build all services"
	@echo "  make build-backend  - Build only backend service"
	@echo "  make build-frontend - Build only frontend service"
	@echo "  make build-no-cache - Build all services without cache"
	@echo "  make up             - Start all services"
	@echo "  make down           - Stop and remove all containers"
	@echo "  make down-v         - Stop and remove all containers and volumes"
	@echo "  make restart        - Restart all services"
	@echo "  make ps             - List running containers"
	@echo "  make top            - Display running processes"
	@echo "  make system-prune   - Remove unused data"
	@echo "  make system-clean   - Remove all unused data including volumes"
	@echo "  make system-reset   - Reset entire Docker state"
	@echo "  make dev-build      - Build for development"
	@echo "  make dev-up         - Start development environment"
	@echo "  make dev-down       - Stop development environment"
	@echo "  make dev-restart    - Restart development environment"
	@echo "  make prod-build     - Build for production"
	@echo "  make prod-up        - Start production environment"
	@echo "  make prod-down      - Stop production environment"
	@echo "  make prod-restart   - Restart production environment"
	@echo "  make logs-all       - View all logs"
	@echo "  make logs-backend   - View backend logs"
	@echo "  make logs-frontend  - View frontend logs"
	@echo "  make logs-follow    - Follow all logs"
	@echo "  make shell-backend  - Access backend shell"
	@echo "  make shell-frontend - Access frontend shell"

# Environment setup
setup: setup-traefik setup-hosts
	@echo "Setting up environment..."
	mkdir -p backend/logs frontend/src letsencrypt
	test -f .env || cp .env.example .env
	test -f redis.conf || touch redis.conf
	@echo "Setup complete. Don't forget to edit .env with your configurations."

# Production deployment
prod-deploy: check-domain
	@echo "Deploying to production..."
	NODE_ENV=production $(DOCKER_COMPOSE) -f docker-compose.yml up -d

# Check domain configuration
check-domain:
	@echo "Checking DNS configuration for $(DOMAIN) and subdomains..."
	@for subdomain in $(SUBDOMAINS); do \
		echo "Checking $$subdomain.$(DOMAIN)..."; \
		host $$subdomain.$(DOMAIN) || echo "Warning: $$subdomain.$(DOMAIN) DNS not configured"; \
	done

# Traefik setup
setup-traefik:
	@echo "Setting up Traefik..."
	mkdir -p letsencrypt
	touch letsencrypt/acme.json
	chmod 600 letsencrypt/acme.json
	@echo "Traefik setup complete."

# Setup local hosts (development only)
setup-hosts:
	@if [ "$(NODE_ENV)" = "development" ]; then \
		echo "Setting up local hosts..."; \
		echo "127.0.0.1 traefik.localhost api.localhost bible-study.localhost" | sudo tee -a /etc/hosts; \
	fi

# Setup SSL for development
setup-ssl:
	@if [ "$(NODE_ENV)" = "development" ]; then \
		echo "Generating SSL certificates for development..."; \
		mkdir -p certs; \
		mkcert -install; \
		mkcert -cert-file certs/local-cert.pem -key-file certs/local-key.pem "*.localhost"; \
	else \
		echo "Production uses Let's Encrypt certificates automatically."; \
	fi

# Check Traefik status
check-traefik:
	@echo "Checking Traefik status..."
	@curl -s -o /dev/null -w "%{http_code}" http://traefik.localhost:8080/api/version || echo "Traefik is not running"

# Build containers
build:
	$(DOCKER_COMPOSE) build

# Run in API mode (default)
run: check-deps
	$(DOCKER_COMPOSE) up

# Development mode with hot reload
dev: check-deps
	NODE_ENV=development $(DOCKER_COMPOSE) up --build

# CLI mode
cli:
	$(DOCKER_COMPOSE) run --rm backend python app/main.py

# Stop containers
stop:
	$(DOCKER_COMPOSE) down

# Clean everything
clean:
	$(DOCKER_COMPOSE) down -v
	rm -rf backend/logs/*
	rm -rf letsencrypt/*
	find . -type d -name "__pycache__" -exec rm -r {} +
	find . -type f -name "*.pyc" -delete

# View logs
logs:
	$(DOCKER_COMPOSE) logs -f

# View Traefik logs specifically
logs-traefik:
	$(DOCKER_COMPOSE) logs -f traefik

# Run tests
test:
	$(DOCKER_COMPOSE) run --rm backend python -m pytest

# Create required directories
init-dirs:
	mkdir -p backend/logs
	mkdir -p frontend/src
	mkdir -p letsencrypt
	mkdir -p certs

# Check dependencies
check-deps:
	@echo "Checking dependencies..."
	@command -v docker >/dev/null 2>&1 || { echo "docker is required but not installed. Aborting." >&2; exit 1; }
	@command -v docker-compose >/dev/null 2>&1 || { echo "docker-compose is required but not installed. Aborting." >&2; exit 1; }
	@command -v mkcert >/dev/null 2>&1 || { echo "mkcert is recommended for local SSL. Install with: brew install mkcert" >&2; }

# Production mode
prod:
	NODE_ENV=production $(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml up -d

# Docker Build Commands
build-all: ## Build all services
	$(DOCKER_COMPOSE) build

build-backend: ## Build only backend service
	$(DOCKER_COMPOSE) build backend

build-frontend: ## Build only frontend service
	$(DOCKER_COMPOSE) build frontend

build-no-cache: ## Build all services without cache
	$(DOCKER_COMPOSE) build --no-cache

# Docker Compose Commands
up: ## Start all services
	$(DOCKER_COMPOSE) up -d

down: ## Stop and remove all containers
	$(DOCKER_COMPOSE) down --remove-orphans

down-v: ## Stop and remove all containers and volumes
	$(DOCKER_COMPOSE) down -v --remove-orphans

restart: down up ## Restart all services

ps: ## List running containers
	$(DOCKER_COMPOSE) ps

top: ## Display running processes
	$(DOCKER_COMPOSE) top

# Docker System Commands
system-prune: ## Remove unused data
	docker system prune -f

system-clean: ## Remove all unused data including volumes
	docker system prune -af --volumes

system-reset: down-v system-clean ## Reset entire Docker state

# Development Commands
dev-build: ## Build for development
	NODE_ENV=development $(DOCKER_COMPOSE) build

dev-up: ## Start development environment
	NODE_ENV=development $(DOCKER_COMPOSE) up -d

dev-down: ## Stop development environment
	NODE_ENV=development $(DOCKER_COMPOSE) down --remove-orphans

dev-restart: dev-down dev-up ## Restart development environment

# Production Commands
prod-build: ## Build for production
	NODE_ENV=production $(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml build

prod-up: ## Start production environment
	NODE_ENV=production $(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml up -d

prod-down: ## Stop production environment
	NODE_ENV=production $(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml down --remove-orphans

prod-restart: prod-down prod-up ## Restart production environment

# Utility Commands
logs-all: ## View all logs
	$(DOCKER_COMPOSE) logs

logs-backend: ## View backend logs
	$(DOCKER_COMPOSE) logs backend

logs-frontend: ## View frontend logs
	$(DOCKER_COMPOSE) logs frontend

logs-follow: ## Follow all logs
	$(DOCKER_COMPOSE) logs -f

# Shell Access Commands
shell-backend: ## Access backend shell
	$(DOCKER_COMPOSE) exec backend /bin/bash

shell-frontend: ## Access frontend shell
	$(DOCKER_COMPOSE) exec frontend /bin/sh