# Makefile for Flask Markdown app (docker compose)
# Usage examples:
#   make up                 # start prod service
#   make up-dev             # start dev profile (auto-reload)
#   make logs               # recent logs for 'web'
#   make logs-f             # follow logs
#   make sh                 # shell into the 'web' container
#   make health             # hit /health locally
#   make down               # stop and remove containers
#   make restart            # restart (down+up)
#   make ps                 # list services
#   make help               # show this help

# ---- Config ---------------------------------------------------------------
COMPOSE ?= docker compose
PROJECT ?= pistlar          # compose project name
SERVICE ?= web              # default service for logs/exec
PROFILE ?=                  # empty or "dev"
PORT    ?= 8000             # host port to hit /health
TAIL    ?= 100              # log tail lines

DC = $(COMPOSE) -p $(PROJECT)
PROFILE_ARG = $(if $(PROFILE),--profile $(PROFILE),)

# ---- Meta ----------------------------------------------------------------
.PHONY: help build up up-dev down stop restart logs logs-f ps sh run health \
        images config init clean

## Show this help
help:
	@awk 'BEGIN {FS = ":.*##"; printf "\nTargets:\n"} /^[a-zA-Z0-9_.-]+:.*##/ { printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
	@echo ""
	@echo "Variables you can override, e.g.: make logs SERVICE=dev TAIL=200"
	@echo "  PROJECT=$(PROJECT)"
	@echo "  SERVICE=$(SERVICE)"
	@echo "  PROFILE=$(PROFILE)"
	@echo "  PORT=$(PORT)"
	@echo "  TAIL=$(TAIL)"

## Build images
build:
	$(DC) build $(PROFILE_ARG)

## Start in background (prod by default)
up:
	$(DC) up -d $(PROFILE_ARG)

## Start the dev profile (equivalent to: PROFILE=dev make up)
up-dev:
	$(MAKE) PROFILE=dev up

## Stop containers but keep resources
stop:
	$(DC) stop

## Stop and remove containers, networks
down:
	$(DC) down

## Restart (down + up, keeping current PROFILE)
restart: down up ## Restart stack

## Show service status
ps:
	$(DC) ps

## Show recent logs for $(SERVICE)
logs:
	$(DC) logs --no-color --tail=$(TAIL) $(SERVICE)

## Follow logs for $(SERVICE)
logs-f:
	$(DC) logs -f $(SERVICE)

## Open a shell in the running $(SERVICE) container
sh:
	$(DC) exec $(SERVICE) sh -lc 'exec $${SHELL:-/bin/sh}'

## Run a one-off command in a throwaway $(SERVICE) container
# Example: make run CMD="python -V"
CMD ?= sh -lc 'exec $${SHELL:-/bin/sh}'
run:
	$(DC) run --rm $(SERVICE) $(CMD)

## Curl local /health
health:
	@curl -fsS "http://localhost:$(PORT)/health" | jq . || (echo "Health check failed"; exit 1)

## Show compose config after interpolation
config:
	$(DC) config $(PROFILE_ARG)

## List images referenced by the compose file
images:
	$(DC) images

## Create expected content folders (first run convenience)
init:
	mkdir -p content/posts content/assets templates

## Remove containers + dangling images/networks (careful)
clean: down
	@docker image prune -f
	@docker network prune -f
