# Commandes usuelles (à lancer depuis le dossier RAG/).
COMPOSE ?= docker compose

.PHONY: help env up down ps logs ingest reingest backup restore test test-integration lint frontend-build evaluate clean

help:            ## Affiche cette aide
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*## /\t/'

env:             ## Crée .env avec des secrets aléatoires (si absent)
	bash CODE/scripts/ops/init_env.sh

up: env          ## Construit et démarre la plateforme
	$(COMPOSE) up -d --build

down:            ## Arrête la plateforme (les données sont conservées)
	$(COMPOSE) down

ps:              ## État des services
	$(COMPOSE) ps

logs:            ## Journaux du backend
	$(COMPOSE) logs -f --tail=200 backend

ingest:          ## Synchronise le corpus de démonstration dans le graphe
	$(COMPOSE) exec backend python -m scripts.ingest

reingest:        ## Vide le graphe puis réingère tout le corpus
	$(COMPOSE) exec backend python -m scripts.ingest --reset

backup:          ## Sauvegarde Neo4j + fichiers téléversés dans backups/
	bash CODE/scripts/ops/backup.sh

restore:         ## Restaure une sauvegarde : make restore BACKUP=backups/<horodatage>
	bash CODE/scripts/ops/restore.sh $(BACKUP)

lint:            ## Analyse statique du code Python
	cd CODE && ruff check .

test:            ## Tests unitaires (sans base de données)
	cd CODE && python -m pytest -m "not integration" -q

test-integration: ## Tests d'intégration (NEO4J_TEST_URI vers une base JETABLE)
	cd CODE && python -m pytest -m integration -q

frontend-build:  ## Vérification de types et compilation de l'interface
	cd CODE/frontend && npm ci && npm run build

evaluate:        ## Campagne d'évaluation complète (voir CODE/scripts/run_evaluation_campaign.sh)
	cd CODE && bash scripts/run_evaluation_campaign.sh

clean:           ## Supprime conteneurs ET volumes (données perdues) après confirmation
	@read -p "Supprimer définitivement les volumes de données ? [oui/N] " a; [ "$$a" = "oui" ] && $(COMPOSE) down -v || echo "Annulé."
