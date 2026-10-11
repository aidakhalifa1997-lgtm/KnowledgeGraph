#!/usr/bin/env bash
# Télécharge, pour un usage personnel de lecture, les prépublications arXiv citées dans
# "RESEARCH PAPERS/BIBLIOGRAPHIE.md". Les PDF ne sont PAS versionnés (licence arXiv par défaut :
# pas de redistribution par un tiers). Les articles hors arXiv sont à consulter via leur DOI.
set -euo pipefail
DEST="${1:-$(dirname "$0")/../../RESEARCH PAPERS/pdf}"
mkdir -p "$DEST"
IDS=(
  2005.11401 2312.10997 2404.16130 2408.08921 2501.00309 2405.14831 2307.07697 2410.05779
  2305.05003 2312.17617 2305.13168 2210.03629 2212.10509 2401.15884 2202.03629 2305.14627
  2307.03172 2302.12173 2309.15217 2405.07437 2104.08663 2003.02320 2306.08302 1603.09320
  2205.13147 1809.09600 1912.13318 2003.00911 1905.06397
)
for id in "${IDS[@]}"; do
  out="$DEST/arXiv-${id}.pdf"
  [ -s "$out" ] && { echo "déjà présent : $out"; continue; }
  echo "téléchargement : $id"
  curl -fsSL "https://arxiv.org/pdf/${id}" -o "$out" || echo "échec : $id (vérifier l'accès réseau)"
  sleep 3   # politesse envers arXiv
done
