#!/usr/bin/env bash
# Reproduit l'ensemble des campagnes d'évaluation rapportées dans le mémoire.
#
# Prérequis : deux bases Neo4j VIDABLES (leur contenu est effacé), par exemple :
#   EVAL_NEO4J_URI=bolt://localhost:7687  (campagnes principales)
#   ABLATION_NEO4J_URI=bolt://localhost:7688  (ablation de l'encodeur spaCy)
# Les mots de passe sont lus dans EVAL_NEO4J_PASSWORD et ABLATION_NEO4J_PASSWORD.
# Usage : depuis RAG/CODE, `bash scripts/run_evaluation_campaign.sh`
set -euo pipefail

: "${EVAL_NEO4J_URI:?définir EVAL_NEO4J_URI}"
: "${EVAL_NEO4J_PASSWORD:?définir EVAL_NEO4J_PASSWORD}"
: "${ABLATION_NEO4J_URI:?définir ABLATION_NEO4J_URI}"
: "${ABLATION_NEO4J_PASSWORD:?définir ABLATION_NEO4J_PASSWORD}"
export LLM_PROVIDER=offline

echo "1/3 Campagne principale, configuration gelée (WordLlama, RRF pure)"
NEO4J_URI="$EVAL_NEO4J_URI" NEO4J_PASSWORD="$EVAL_NEO4J_PASSWORD" EMBEDDING_PROVIDER=wordllama \
  RETRIEVAL_SOURCE_GUARANTEE=0 python -m evaluation.run_evaluation --reingest --tag wordllama

echo "2/3 Modification post-gel (garantie par source dans la fusion)"
NEO4J_URI="$EVAL_NEO4J_URI" NEO4J_PASSWORD="$EVAL_NEO4J_PASSWORD" EMBEDDING_PROVIDER=wordllama \
  RETRIEVAL_SOURCE_GUARANTEE=1 python -m evaluation.run_evaluation --sections retrieval,qa,ablations \
  --tag wordllama_postgel

echo "3/3 Ablation de l'encodeur (spaCy, configuration gelée)"
NEO4J_URI="$ABLATION_NEO4J_URI" NEO4J_PASSWORD="$ABLATION_NEO4J_PASSWORD" EMBEDDING_PROVIDER=spacy \
  RETRIEVAL_SOURCE_GUARANTEE=0 python -m evaluation.run_evaluation --reingest --sections ingestion,retrieval --tag spacy

python -m evaluation.report
