# SPDX-License-Identifier: LGPL-2.1-or-later
# Makefile pour gérer le conteneur Docker de test

.PHONY: help build up down clean test test-unit test-integration lint type-check shell

# Configuration
DOCKER_COMPOSE = docker-compose
DOCKER_COMPOSE_FILES = docker-compose.yml docker-compose.dev.yml
IMAGE_NAME = freecad-menuiserie-test

help: ## Affiche cette aide
	@echo "Commandes disponibles pour Docker :"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  make %-20s %s\n", $$1, $$2}'
	@echo ""

build: ## Construit l'image Docker
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILES) build

up: ## Démarre les services (conteneur persistant)
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILES) up -d

down: ## Arrête et supprime les conteneurs
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILES) down

clean: ## Supprime l'image Docker
	docker rmi -f $(IMAGE_NAME)
	test -d tmp && rm -rf tmp || true

# Tests
test: ## Exécute tous les tests
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILES) run --rm test

test-unit: ## Exécute seulement les tests unitaires
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILES) run --rm test-unit

test-integration: ## Exécute seulement les tests d'intégration
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILES) run --rm test-integration

# Qualité de code
lint: ## Exécute ruff (lint)
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILES) run --rm lint

type-check: ## Exécute mypy (vérification de typage)
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILES) run --rm type-check

# Shell
shell: ## Démarre un shell interactif dans le conteneur
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILES) run --rm shell

# Commande personnalisée
run: ## Exécute une commande personnalisée
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILES) run --rm test $(CMD)
