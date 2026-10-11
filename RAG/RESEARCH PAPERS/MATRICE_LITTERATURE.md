# Matrice de littérature

Cette matrice compare les travaux retenus selon des critères homogènes. Les numéros renvoient à `BIBLIOGRAPHIE.md`.
Colonne « Décision » : **Retenu** = principe implémenté ; **Adapté** = principe repris sous une forme simplifiée ;
**Écarté** = étudié mais non implémenté (justification donnée) ; **Cadre** = référence conceptuelle ou métrique.

## 1. Vue comparative des approches de récupération et de génération

| Réf. | Approche | Type de connaissance exploitée | Besoin d'entraînement | Coût LLM à l'indexation | Coût LLM à la requête | Explicabilité native | Type de questions ciblé | Évaluation rapportée | Décision |
|---|---|---|---|---|---|---|---|---|---|
| [1] RAG (Lewis 2020) | Récupérateur dense + générateur | Passages | Oui (bout en bout) | Nul | 1 génération | Passages | Factuelles, domaine ouvert | EM sur NQ, TriviaQA… | Cadre |
| [3] DPR | Double encodeur dense | Passages | Oui | Nul | Nul (récupération) | Faible | Factuelles | Précision top-k | Cadre (encodeur remplacé, voir [4], [9]) |
| [5] BM25 | Lexical probabiliste | Termes | Non | Nul | Nul | Moyenne (termes) | Mots-clés, codes, noms propres | — | **Retenu** (Lucene / Neo4j) |
| [6] BEIR | Banc d'essai | — | — | — | — | — | Hors domaine | nDCG@10 | Cadre : justifie l'hybride |
| [7] RRF | Fusion de rangs | Rangs | Non | — | — | — | Toutes | MAP (TREC, LETOR) | **Retenu** (`fusion.py`) |
| [13] GraphRAG MS | Graphe d'entités + communautés + map-reduce | Entités, communautés | Non | Très élevé | Élevé | Résumés de communautés | Globales (thèmes) | Jugements LLM | **Adapté** : mode « local » seulement |
| [16] HippoRAG | KG + Personalized PageRank | Entités, passages | Non | Élevé (extraction LLM) | Faible | Entités activées | Multi-sauts | Recall@k (MuSiQue, 2Wiki, HotpotQA) | **Retenu** : PPR local |
| [17] Think-on-Graph | Agent LLM explorant le KG | Triplets | Non | Nul | Très élevé | Chemins | Multi-sauts KBQA | Hits@1 | Écarté (coût, non-déterminisme) |
| [18] LightRAG | Graphe + vecteurs, 2 niveaux | Entités, thèmes | Non | Élevé | Faible | Entités | Locales + globales | Jugements LLM | **Adapté** : mise à jour incrémentale |
| [27] IRCoT | Récupération entrelacée avec raisonnement | Passages | Non | Nul | Élevé (itératif) | Chaîne de raisonnement | Multi-sauts | Recall, F1 | **Adapté** : 1 boucle de récupération complémentaire |
| [28] Self-RAG | LM entraîné à se critiquer | Passages | Oui | Nul | Moyen | Jetons de réflexion | Mixtes | Divers | **Adapté** : critique par nœuds explicites, sans entraînement |
| [29] CRAG | Évaluateur de récupération + action corrective | Passages | Évaluateur léger | Nul | Moyen | Faible | Mixtes | Divers | **Retenu** : nœud `assess_context` |
| [26] ReAct | Agent raisonnement/action | Outils | Non | Nul | Élevé | Trace | Tâches interactives | Taux de succès | Écarté (prévisibilité) |

## 2. Construction du graphe et extraction

| Réf. | Problème | Méthode | Résultat clé | Limite clé | Décision dans le projet |
|---|---|---|---|---|---|
| [10] Hogan | Définir les KG | Revue | Modèle de graphe de propriétés, dimensions de qualité | Pré-LLM | **Cadre** : schéma, contraintes, critères de qualité |
| [11] Cypher | Langage de requête | Sémantique formelle | Standard de fait (influence GQL) | — | **Retenu** |
| [12] Pan | Articuler LLM et KG | Feuille de route | Cadre « synergique » | Conceptuel | **Cadre** de positionnement |
| [20] Wadhwa | RE avec LLM | Few-shot GPT-3, Flan-T5 | Proche du supervisé ; correspondance exacte inadaptée | Coût, variabilité | **Retenu** : extraction LLM + évaluation normalisée |
| [21] Xu | IE générative | Revue | Sorties structurées, schémas | — | **Retenu** : schéma JSON validé (Pydantic) |
| [22] Zhu | LLM pour KG | Évaluation de GPT-4 sur 8 jeux | Meilleur en inférence qu'en extraction few-shot | Prépublication | **Retenu** : extraction LLM jamais acceptée sans contrôle |
| [23] Christophides | Résolution d'entités | Revue blocking/matching/clustering | Pipeline de référence | Big Data, pas LLM | **Retenu** : cascade exact → alias → normalisé → flou |
| [24] Fellegi-Sunter | Couplage d'enregistrements | Modèle probabiliste | Trois zones de décision | — | **Adapté** : seuils haut et bas, statut `candidate` |
| [25] Broder | Quasi-doublons | Shingles + MinHash | Ressemblance de Jaccard estimée | Sensible à la taille des shingles | **Retenu** : `dedup.py` |

## 3. Fonctionnalités métier

| Réf. | Fonction | Approche de la littérature | Notre transposition | Risque identifié |
|---|---|---|---|---|
| [34] Balog 2006 | Recherche d'experts | Modèle centré documents (Model 2) | Agrégation de preuves typées issues des documents | Confusion mention et expertise |
| [35] Balog 2012 | Recherche d'experts | Synthèse, enjeux éthiques | Pondération transparente, preuves affichées, limites affichées | Données RH sensibles |
| [36] Guo 2022 | Recommandation | Embeddings, connexions, propagation | Score hybride : similarité de contenu + concepts partagés + proximité dans le graphe | Biais de popularité |

## 4. Évaluation

| Réf. | Ce que la référence mesure | Métrique reprise | Où dans le projet | Type de mesure |
|---|---|---|---|---|
| [37] Järvelin | Gain cumulé gradué | nDCG@k | `evaluation/metrics.py` | Automatique |
| [19] HotpotQA | Multi-sauts, faits justificatifs | Couverture des faits justificatifs | `evaluation/retrieval_eval.py` | Automatique (annotations de référence) |
| [31] ALCE | Qualité des citations | Rappel/précision des citations | `evaluation/generation_eval.py` | Automatique (proxy lexical) ou LLM |
| [38] RAGAS | Fidélité, pertinence | Fidélité (proxy) | `evaluation/generation_eval.py` | LLM juge **optionnel**, étiqueté |
| [39] Yu | Typologie de l'évaluation RAG | Séparation récupération / génération | Protocole expérimental | Cadre |
| [40] Zheng | Fiabilité du LLM juge | Mise en garde sur les biais | Rapport, chapitre limites | Cadre |
| [32] Lost in the Middle | Usage du contexte long | Budget de contexte, ordre | `orchestration/context.py` | Choix de conception |

## 5. Lacunes observées dans le corpus de travaux consultés (justifiant le projet)

> Ces constats portent **uniquement sur les travaux listés ici**. Ils ne prétendent pas résumer l'ensemble de la littérature.

1. Les travaux GraphRAG consultés ([13], [16], [17], [18]) sont évalués sur des corpus **publics et majoritairement anglophones** (Wikipédia, actualités, podcasts, jeux multi-sauts). Aucun n'évalue un corpus d'entreprise francophone soumis à des droits d'accès.
2. Deux d'entre eux ([13], [18]) s'appuient principalement sur des **jugements de LLM** (taux de victoire). Les mesures de récupération sur faits justificatifs annotés ([16], [19]) sont un complément nécessaire.
3. La **provenance fine** (relation vers passage source) et la **mise à jour incrémentale** ne sont pas au centre des articles consultés, alors qu'elles sont indispensables dans un contexte audité comme la banque.
4. La **sécurité** (injection indirecte, cloisonnement des droits) n'est pas traitée dans les architectures GraphRAG consultées ; [33] montre pourtant que le risque est concret pour toute application qui injecte des documents dans un prompt.
