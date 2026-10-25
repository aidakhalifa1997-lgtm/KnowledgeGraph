#!/usr/bin/env bash
# Télécharge le benchmark public ObliQA (Gokhan, Wang, Gurevych et Briscoe, 2024) : 40 textes
# réglementaires de l'ADGM (Abu Dhabi Global Market) découpés en passages, et 27 869 questions
# rattachées à leurs passages sources. Les fichiers ne sont PAS versionnés dans ce dépôt : le dépôt
# d'origine ne déclare aucune licence de redistribution. Ils sont figés sur un commit et vérifiés
# par SHA-256 pour que toute campagne porte exactement sur les mêmes données.
set -euo pipefail
COMMIT="c1b2c3c04aee1f6ce75f76106ce13af672d48e02"
BASE="https://raw.githubusercontent.com/RegNLP/ObliQADataset/${COMMIT}"
DEST="${1:-$(dirname "$0")/../../data/external/obliqa}"
mkdir -p "$DEST"
cd "$DEST"
cat > SHA256SUMS <<'EOF'
0bf0fdb4ead84faa8b6865022cfd4fb3caaa4617a82c718e9978bb951f5fb64f  ObliQA_train.json
cf6584f892c2ddde2da380fadfadea2008be7667f50085c27135b2dd29c14e20  ObliQA_dev.json
cdca623b02f248ca736c2c2d98e9b6bebe4a82708f7984ef8f80f9fcd797e1b1  ObliQA_test.json
7f31af52e9bfacabfbe1f73c5bbd860afd93dd2aab72f05cb0608dd39ea1205d  StructuredRegulatoryDocuments.zip
EOF
for f in ObliQA_train.json ObliQA_dev.json ObliQA_test.json StructuredRegulatoryDocuments.zip; do
  [ -s "$f" ] || { echo "téléchargement : $f"; curl -fsSL "$BASE/$f" -o "$f"; }
done
sha256sum -c SHA256SUMS
# L'archive contient aussi des métadonnées macOS (__MACOSX) qui ne sont pas extraites.
unzip -q -o StructuredRegulatoryDocuments.zip 'StructuredRegulatoryDocuments/*' -d .
echo "ObliQA prêt dans $(pwd)"
