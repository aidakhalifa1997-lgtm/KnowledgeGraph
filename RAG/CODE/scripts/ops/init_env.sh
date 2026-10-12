#!/usr/bin/env bash
# Crée RAG/.env à partir de .env.example en générant des secrets aléatoires
# (mot de passe Neo4j, clé de signature des jetons). Les secrets ne sont jamais affichés.
set -euo pipefail
cd "$(dirname "$0")/../../.."   # dossier RAG/
if [ -e .env ]; then
  echo ".env existe déjà : rien n'est modifié." >&2
  exit 0
fi
umask 077
rand() { python3 -c "import secrets; print(secrets.token_urlsafe($1))"; }
sed -e "s|^NEO4J_PASSWORD=.*|NEO4J_PASSWORD=$(rand 24)|" \
    -e "s|^APP_SECRET_KEY=.*|APP_SECRET_KEY=$(rand 48)|" \
    -e "s|^LLM_API_KEY=.*|LLM_API_KEY=|" \
    .env.example > .env
echo ".env créé (droits 600). Renseignez LLM_PROVIDER / LLM_API_KEY si un LLM doit être utilisé."
