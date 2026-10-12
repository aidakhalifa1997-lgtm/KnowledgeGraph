#!/usr/bin/env bash
# Restauration d'une sauvegarde produite par backup.sh.
# Usage : bash CODE/scripts/ops/restore.sh backups/<horodatage>
# ATTENTION : remplace intégralement la base et les fichiers téléversés actuels.
set -euo pipefail
cd "$(dirname "$0")/../../.."   # dossier RAG/
SRC="${1:?Usage : restore.sh backups/<horodatage>}"
SRC="${SRC%/}"
[ -f "${SRC}/neo4j.dump" ] || { echo "Dump introuvable : ${SRC}/neo4j.dump" >&2; exit 1; }
echo "[1/5] Vérification des empreintes"
(cd "${SRC}" && sha256sum -c SHA256SUMS)
NAME="$(basename "${SRC}")"
echo "[2/5] Arrêt du backend et de Neo4j"
docker compose stop backend neo4j >/dev/null
chmod 0755 "${SRC}"
echo "[3/5] Chargement du dump (écrase la base actuelle)"
LOG="$(mktemp)"
docker compose run --rm --no-deps -T neo4j neo4j-admin database load neo4j --from-path="/backups/${NAME}" \
  --overwrite-destination=true >"${LOG}" 2>&1 || { tail -n 20 "${LOG}" >&2; exit 1; }
rm -f "${LOG}"
chmod 0700 "${SRC}"
echo "[4/5] Restauration des fichiers téléversés"
docker compose run --rm --no-deps -T --entrypoint sh backend -c 'find /app/data/uploads -mindepth 1 -delete && tar xzf - -C /app/data' < "${SRC}/uploads.tar.gz"
echo "[5/5] Redémarrage"
docker compose start neo4j >/dev/null
docker compose start backend >/dev/null
echo "Restauration terminée depuis ${SRC}. Vérifier : docker compose ps ; curl http://localhost:\${HTTP_PORT:-8080}/api/health"
