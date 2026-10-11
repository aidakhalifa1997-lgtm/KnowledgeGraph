# Journal des modifications des heuristiques de questions-réponses

Ce journal trace chaque modification des heuristiques du workflow (classification, suffisance,
conflits, génération extractive) avec la question qui l'a motivée. Il permet de distinguer, dans
les résultats, les questions **de développement** (observées pendant la mise au point, liste
`development_questions` de `questions.yaml`) des questions **jamais inspectées**, sur lesquelles
la mesure n'est pas biaisée par l'ajustement.

Règle : seules les questions de développement peuvent motiver une modification. Toute
modification après le gel (première exécution de `evaluation/run_all.py`) est signalée comme
« post-gel » et ses effets sont rapportés séparément.

| Date | Composant | Modification | Question / test déclencheur | Statut |
|---|---|---|---|---|
| 2026-10 | sufficiency | Contrôle « valeur chiffrée » appliqué aux unités de sens (phrase d'introduction + puces, lignes de tableau avec intitulés) au lieu des phrases isolées | Q57 (développement), test d'intégration `test_workflow_flags_contradiction_and_ambiguity` | avant gel |
| 2026-10 | merge (extraction) | Arrondi de la confiance fusionnée à 3 décimales (artefact de virgule flottante) | test unitaire `test_evidence_check_and_merge` | avant gel, sans effet sur les résultats |
