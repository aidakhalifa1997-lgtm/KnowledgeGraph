#!/usr/bin/env bash
# Sauvegarde de la plateforme : dump Neo4j + fichiers téléversés + empreintes SHA-256.
# Neo4j Community ne propose pas de sauvegarde à chaud : la base est arrêtée pendant le dump
# (quelques secondes pour ce volume), le backend aussi pour éviter toute écriture concurrente.
# Le fichier .env (secrets) n'est volontairement PAS sauvegardé ici : il relève du coffre-fort.
set -euo pipefail
cd "$(dirname "$0")/../../.."   # dossier RAG/
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="backups/${STAMP}"
mkdir -p "${DEST}"
chmod 0777 "${DEST}"   # écriture par l'utilisateur neo4j du conteneur

restart() { docker compose start neo4j >/dev/null; docker compose start backend >/dev/null || true; }
trap restart EXIT

echo "[1/4] Arrêt du backend et de Neo4j"
docker compose stop backend neo4j >/dev/null
echo "[2/4] Dump de la base Neo4j"
LOG="$(mktemp)"
docker compose run --rm --no-deps -T neo4j neo4j-admin database dump neo4j --to-path="/backups/${STAMP}" \
  >"${LOG}" 2>&1 || { tail -n 20 "${LOG}" >&2; exit 1; }
rm -f "${LOG}"
echo "[3/4] Archive des fichiers téléversés"
docker compose run --rm --no-deps -T --entrypoint tar backend czf - -C /app/data uploads > "${DEST}/uploads.tar.gz"
echo "[4/4] Empreintes"
(cd "${DEST}" && sha256sum neo4j.dump uploads.tar.gz > SHA256SUMS)
chmod 0700 "${DEST}"
echo "Sauvegarde terminée : ${DEST}"
