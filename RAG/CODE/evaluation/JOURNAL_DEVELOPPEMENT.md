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
| 2026-10 | ingestion (pipeline) | Les durées d'encodage et d'écriture Neo4j sont reportées dans le rapport d'ingestion (copie de liste par Pydantic) | section `ingestion` de l'évaluation | correction de mesure, sans effet sur les réponses |
| 2026-10 | configuration | **Encodeur par défaut : WordLlama au lieu de spaCy.** Ablation prévue au protocole : nDCG@5 de l'architecture hybride finale sur les 17 questions de développement 0,805 (WordLlama) contre 0,619 (spaCy). La décision est prise sur le split de développement ; les résultats sur toutes les questions ont toutefois été vus avant la décision (choix de configuration *a posteriori*, à signaler dans le mémoire). Les résultats spaCy sont conservés dans `results/spacy/` | ablation `results/spacy` vs `results/wordllama` | **gel de la configuration** après cette décision |

## Gel

La campagne principale (`results/wordllama/`) est exécutée après les modifications ci-dessus.
Toute modification ultérieure du code des heuristiques ou de la configuration sera ajoutée
ci-dessous avec la mention « post-gel » et ses effets seront rapportés séparément.

## Modifications post-gel

| Date | Composant | Modification | Déclencheur | Effet mesuré (gel → post-gel) |
|---|---|---|---|---|
| 2026-10 | retrieval (fusion) | **Post-gel.** Garantie par source dans la fusion RRF : le premier passage de chaque source active (BM25, vecteurs, graphe) est conservé dans le contexte (`RETRIEVAL_SOURCE_GUARANTEE=1` ; `0` reproduit exactement la configuration gelée). Motivation : un passage classé 1er par BM25 seul (acronyme exact « RTO ») était évincé par des passages moyens présents dans les trois listes. | Q62 (développement) | Recherche, hybride final : nDCG@5 0,839 → 0,841 (jamais inspectées 0,851 → 0,854), couverture des preuves 0,943 → 0,953 (valeurs de la campagne finale, après la correction de reproductibilité ci-dessous). Questions-réponses, hybride final : exactitude 0,742 → 0,758 ; développement 0,882 → 0,941 ; **jamais inspectées inchangées (0,694)**. Hybride à graphe fixe : jamais inspectées 0,735 → 0,714 (une question perdue). Résultats : `results/wordllama_postgel/`. |

Reproductibilité vérifiée : relancer la campagne gelée (`RETRIEVAL_SOURCE_GUARANTEE=0`) redonne
des réponses et des classements identiques sur les 660 lignes (330 recherche + 330 réponses).
| 2026-10 | retrieval (graphe), requêtes | **Post-gel, correction de reproductibilité (aucune modification de méthode).** Constat : après une réingestion complète, l'exactitude de GraphRAG variait (0,561 puis 0,530) alors que la campagne était identique à base constante. Causes : énumération des chemins tronquée par `LIMIT 600` sans ordre, tris sans départage des ex æquo, `LIMIT` sans `ORDER BY` (graines de relance, recherche lexicale et vectorielle, doublons exacts). Corrections : expansion du sous-graphe par niveaux (même ensemble de relations, sans troncature), départage par identifiant, arrondi des scores avant tri, `ORDER BY` avant chaque `LIMIT`. Contrôle : deux campagnes complètes séparées par une réingestion donnent 0 différence sur 1 056 lignes (`python -m evaluation.compare_runs`). | instabilité observée entre deux campagnes | Toutes les campagnes ont été relancées sur le code corrigé. Effet sur les agrégats (configuration gelée) : GraphRAG exactitude 0,530 → 0,515 ; recherche « graphe seul » nDCG@5 0,711 → 0,708 ; « hybride + graphe » 0,804 → 0,813 ; autres valeurs inchangées. |
| 2026-10 | ingestion, workflow | **Post-gel, corrections de sécurité issues d'une revue du code (aucune modification de méthode).** (1) Refus par défaut : un document sans ligne « Diffusion » dans son cartouche est rejeté au lieu d'être diffusé à tous. (2) Le classement d'experts produit par l'assistant exige le rôle manager, comme la page Experts. (3) `LLM_EXTRACTION_ENABLED` règle désormais l'extraction LLM par défaut à l'ingestion. | revue du code | Aucun effet sur les mesures : les 35 documents déclarent leur diffusion et les questions d'expertise sont posées avec le compte administrateur. Contrôle : rejeu de la campagne gelée (ingestion, recherche, questions-réponses) avec le code corrigé, 0 différence sur 660 lignes. Audit complémentaire du contrôle d'accès (`python -m evaluation.access_audit`) : 66 questions × 5 architectures × 3 comptes restreints = 990 réponses, 0 fuite (`results/audit_acces/access_audit.json`). |
