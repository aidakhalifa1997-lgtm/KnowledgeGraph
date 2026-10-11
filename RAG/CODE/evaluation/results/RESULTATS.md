# Résultats expérimentaux (générés automatiquement)

Ce fichier est produit par `python -m evaluation.report` à partir des fichiers bruts de
`evaluation/results/`. Aucune valeur n'est saisie à la main. Les intervalles entre crochets
sont des intervalles de confiance à 95 % (bootstrap percentile, 2 000 rééchantillonnages).

- Campagne principale (configuration gelée) : `results/wordllama/`, commit `cabb1d2`, 2026-10-11T18:33:18+00:00, Neo4j 5.26.31 community, Python 3.13.16, 4 processeurs.
- Encodeur : wordllama (256 dimensions) ; LLM : désactivé (générateur extractif hors-ligne) ; top-k = 8 passages ; RRF k = 60 ; seuil de suffisance = 0.55.
- Corpus et questions **synthétiques**, rédigés par l'auteur de la plateforme : les résultats valent pour ce
  banc d'essai et ne se généralisent pas sans validation sur des documents réels.

## 1. Ingestion

| Indicateur | Valeur |
|---|---|
| Fichiers traités | 35 |
| Statut final des documents | active : 31, quarantined : 1, duplicate : 2, superseded : 1 |
| Durée de l'ingestion complète | 18,45 s |
| Ré-exécution sans changement | 0,38 s (35 fichiers inchangés) |
| Passages (chunks) | 169 |
| Durée moyenne par format | .pdf : 0,91 s (n=15), .txt : 0,15 s (n=11), .docx : 0,19 s (n=9) |
| Signalements qualité | prompt_injection : 1, ocr_used : 1 |

## 2. Graphe de connaissances

| Indicateur | Valeur |
|---|---|
| Nœuds par type | Chunk : 169, Concept : 25, Department : 19, Document : 35, Domain : 16, IngestionRun : 2, Person : 24, Procedure : 9, Project : 7, System : 10 |
| Relations extraites des documents | 153 |
| Relations avec provenance (passage + document) | 1,000 |
| Confiance moyenne | 0,769 |
| Documents sources par relation (moyenne) | 1,67 |
| Relations confirmées par au moins 2 documents | 63 |
| Entités métier (hors taxonomie) | 69 (degré moyen 5,1, isolées : 0) |

## 3. Extraction de connaissances (règles, sans LLM)

Règles développées sur D01–D20 (développement), mesurées aussi sur D21–D35 (jamais utilisés pour la mise au point).

| Mesure | Développement (D01–D20) | Test (D21–D35) |
|---|---|---|
| Relations : précision / rappel / F1 | 1,000 / 0,968 / 0,984 | 0,986 / 0,717 / 0,830 |
| Mentions d'entités : précision / rappel / F1 | 0,924 / 0,953 / 0,938 | 0,789 / 0,912 / 0,846 |

Rappel par type de relation sur le test : DELIVERS 1,00 (n=1), DEPENDS_ON 0,44 (n=16), HAS_EXPERTISE 0,91 (n=33), PARTICIPATES_IN 1,00 (n=3), PART_OF 1,00 (n=5), RESPONSIBLE_FOR 0,17 (n=12), USES 0,00 (n=1), WORKS_IN 0,82 (n=28).

Résolution d'entités (34 cas) : alias present au referentiel : 1,00 (n=22), global : 1,00 (n=34), variante absente du referentiel : 1,00 (n=6), negatif (aucune entite attendue) : 1,00 (n=6).

## 4. Recherche documentaire (classement des documents)

55 questions avec documents de référence (hors questions sans réponse attendue).

| Stratégie | Recall@5 | Precision@5 | MRR | nDCG@5 | Couverture des preuves | Latence p50 / p95 (ms) |
|---|---|---|---|---|---|---|
| Vectoriel | 0,751 [0,68 ; 0,82] | 0,335 | 0,836 [0,76 ; 0,91] | 0,720 [0,65 ; 0,79] | 0,811 | 8,6 / 11,8 |
| BM25 (lexical) | 0,874 [0,81 ; 0,93] | 0,400 | 0,888 [0,82 ; 0,95] | 0,831 [0,77 ; 0,88] | 0,849 | 6,9 / 8,5 |
| Hybride (BM25 + vecteurs) | 0,852 [0,80 ; 0,90] | 0,386 | 0,874 [0,81 ; 0,93] | 0,803 [0,74 ; 0,86] | 0,868 | 11,4 / 14,2 |
| Graphe seul | 0,810 [0,73 ; 0,88] | 0,371 | 0,760 [0,67 ; 0,85] | 0,708 [0,63 ; 0,78] | 0,651 | 17,9 / 24,0 |
| Hybride + graphe (fixe) | 0,854 [0,79 ; 0,91] | 0,396 | 0,875 [0,80 ; 0,94] | 0,813 [0,75 ; 0,87] | 0,934 | 27,9 / 36,2 |
| Hybride final (routé) | 0,855 [0,79 ; 0,92] | 0,400 | 0,908 [0,84 ; 0,97] | 0,839 [0,78 ; 0,90] | 0,943 | 33,9 / 44,2 |

Fuites d'accès (document non autorisé dans le classement) : Vectoriel 0, BM25 (lexical) 0, Hybride (BM25 + vecteurs) 0, Graphe seul 0, Hybride + graphe (fixe) 0, Hybride final (routé) 0.

### 4.1 Questions de développement et questions jamais inspectées (nDCG@5)

| Stratégie | Développement (n=17 max.) | Jamais inspectées |
|---|---|---|
| Vectoriel | 0,675 [0,51 ; 0,84] | 0,733 [0,66 ; 0,81] |
| BM25 (lexical) | 0,797 [0,58 ; 0,97] | 0,841 [0,79 ; 0,89] |
| Hybride (BM25 + vecteurs) | 0,762 [0,63 ; 0,89] | 0,815 [0,75 ; 0,88] |
| Graphe seul | 0,776 [0,67 ; 0,87] | 0,689 [0,59 ; 0,78] |
| Hybride + graphe (fixe) | 0,731 [0,56 ; 0,87] | 0,836 [0,77 ; 0,89] |
| Hybride final (routé) | 0,793 [0,61 ; 0,94] | 0,851 [0,79 ; 0,91] |

### 4.2 Comparaisons appariées (nDCG@5, stratégie − référence)

| Stratégie | vs vectoriel : écart [IC 95 %] | gains / pertes / égalités | p (signes) | vs hybride : écart [IC 95 %] | p (signes) |
|---|---|---|---|---|---|
| BM25 (lexical) | 0,111 [0,04 ; 0,18] | 30 / 8 / 17 | 0,0005 | 0,028 [-0,02 ; 0,08] | 0,4421 |
| Hybride (BM25 + vecteurs) | 0,083 [0,04 ; 0,13] | 27 / 5 / 23 | 0,0001 | — | — |
| Graphe seul | -0,012 [-0,11 ; 0,08] | 23 / 24 / 8 | 1,0000 | -0,095 [-0,19 ; -0,01] | 0,0259 |
| Hybride + graphe (fixe) | 0,093 [0,03 ; 0,16] | 30 / 6 / 19 | 0,0001 | 0,010 [-0,04 ; 0,06] | 0,5716 |
| Hybride final (routé) | 0,118 [0,07 ; 0,17] | 31 / 3 / 21 | 0,0000 | 0,035 [-0,01 ; 0,08] | 0,1686 |

### 4.3 Ablation de l'encodeur (nDCG@5 moyen)

| Stratégie | spaCy (vecteurs de mots moyennés, 300 d) | WordLlama (256 d) |
|---|---|---|
| Vectoriel | 0,409 | 0,720 |
| BM25 (lexical) | 0,831 | 0,831 |
| Hybride (BM25 + vecteurs) | 0,680 | 0,803 |
| Graphe seul | 0,708 | 0,708 |
| Hybride + graphe (fixe) | 0,737 | 0,813 |
| Hybride final (routé) | 0,766 | 0,839 |

## 5. Questions-réponses de bout en bout (workflow LangGraph)

66 questions ; générateur : extractif (hors-ligne). Toutes les architectures partagent le même workflow (analyse, récupération, contrôle de suffisance, relance, génération, vérification) ; seule la stratégie de récupération change.

| Architecture | Exactitude (66) | Questions avec réponse (55) | Rappel d'abstention (11) | Précision d'abstention | Abstention abusive | Contradictions signalées (4) | Ambiguïtés (4) |
|---|---|---|---|---|---|---|---|
| RAG vectoriel | 0,651 [0,53 ; 0,76] | 0,582 [0,45 ; 0,71] | 1,000 | 0,407 | 0,291 | 1,000 | 0,750 |
| RAG hybride | 0,606 [0,48 ; 0,73] | 0,545 [0,42 ; 0,67] | 0,909 | 0,500 | 0,182 | 1,000 | 0,750 |
| GraphRAG | 0,515 [0,39 ; 0,64] | 0,418 [0,29 ; 0,55] | 1,000 | 0,297 | 0,473 | 0,750 | 0,750 |
| Hybride + graphe (fixe) | 0,773 [0,67 ; 0,88] | 0,746 [0,64 ; 0,85] | 0,909 | 0,500 | 0,182 | 0,750 | 0,750 |
| Hybride final (routé) | 0,742 [0,64 ; 0,85] | 0,709 [0,60 ; 0,82] | 0,909 | 0,500 | 0,182 | 0,750 | 0,750 |

| Architecture | Taux d'appui des phrases | Précision des citations | Cite un document essentiel | Citations invalides | Fuites d'accès | Chaînes interdites | Relance | Latence p50 / p95 (ms) |
|---|---|---|---|---|---|---|---|---|
| RAG vectoriel | 0,868 | 0,680 | 0,974 | 0 | 0 | 0 | 0,47 | 41,5 / 63,4 |
| RAG hybride | 0,898 | 0,660 | 0,933 | 0 | 0 | 0 | 0,33 | 38,6 / 62,6 |
| GraphRAG | 0,963 | 0,551 | 0,966 | 0 | 0 | 0 | 0,56 | 52,5 / 71,6 |
| Hybride + graphe (fixe) | 0,947 | 0,608 | 0,956 | 0 | 0 | 0 | 0,33 | 58,6 / 98,8 |
| Hybride final (routé) | 0,930 | 0,591 | 0,956 | 0 | 0 | 0 | 0,32 | 58,8 / 96,3 |

### 5.1 Exactitude par split et par catégorie

| Architecture | Développement (17) | Jamais inspectées (49) | accès | ambiguë | contradiction | expertise | factuelle | multi-documents | multi-sauts | relationnelle | sécurité | sans réponse |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RAG vectoriel | 0,882 [0,71 ; 1,00] | 0,571 [0,43 ; 0,71] | 1,00 | 0,50 | 0,75 | 1,00 | 0,92 | 0,29 | 0,30 | 0,12 | 1,00 | 1,00 |
| RAG hybride | 0,824 [0,65 ; 1,00] | 0,531 [0,41 ; 0,67] | 0,75 | 0,50 | 0,75 | 1,00 | 0,92 | 0,29 | 0,10 | 0,12 | 1,00 | 1,00 |
| GraphRAG | 0,706 [0,47 ; 0,88] | 0,449 [0,31 ; 0,59] | 0,50 | 0,50 | 0,25 | 1,00 | 0,31 | 0,00 | 0,60 | 0,38 | 1,00 | 1,00 |
| Hybride + graphe (fixe) | 0,882 [0,71 ; 1,00] | 0,735 [0,61 ; 0,86] | 0,50 | 0,75 | 0,75 | 1,00 | 0,92 | 0,43 | 0,70 | 0,62 | 1,00 | 1,00 |
| Hybride final (routé) | 0,882 [0,71 ; 1,00] | 0,694 [0,57 ; 0,82] | 0,50 | 0,75 | 0,75 | 1,00 | 0,92 | 0,29 | 0,60 | 0,62 | 1,00 | 1,00 |

### 5.2 Comparaisons appariées avec l'hybride final (exactitude)

| Architecture comparée | Écart (final − autre) [IC 95 %] | gains / pertes / égalités | p (signes) |
|---|---|---|---|
| RAG vectoriel | 0,091 [0,00 ; 0,18] | 9 / 3 / 54 | 0,1460 |
| RAG hybride | 0,136 [0,03 ; 0,24] | 11 / 2 / 53 | 0,0225 |
| GraphRAG | 0,227 [0,12 ; 0,33] | 16 / 1 / 49 | 0,0003 |
| Hybride + graphe (fixe) | -0,030 [-0,08 ; 0,00] | 0 / 2 / 64 | 0,5000 |

Accord du classifieur de questions avec la catégorie annotée (41 questions de catégories correspondantes) : 0,878.

## 6. Ablations du workflow (hybride final)

| Variante | Exactitude | Jamais inspectées | Rappel d'abstention | Abstention abusive | Taux de relance |
|---|---|---|---|---|---|
| seuil 0.35 | 0,742 [0,64 ; 0,85] | 0,714 | 0,727 | 0,127 | 0,24 |
| seuil 0.45 | 0,742 [0,64 ; 0,85] | 0,714 | 0,818 | 0,164 | 0,27 |
| seuil 0.55 | 0,742 [0,64 ; 0,85] | 0,694 | 0,909 | 0,182 | 0,32 |
| seuil 0.65 | 0,727 [0,62 ; 0,83] | 0,673 | 1,000 | 0,218 | 0,36 |
| seuil 0.75 | 0,682 [0,58 ; 0,80] | 0,612 | 1,000 | 0,327 | 0,48 |
| sans relance (seuil 0,55) | 0,742 [0,64 ; 0,85] | 0,694 | 0,909 | 0,200 | 0,00 |

## 7. Recherche d'experts (15 domaines)

| Méthode | Precision@1 | Recall@3 | nDCG@3 | MRR |
|---|---|---|---|---|
| Score pondéré par type de preuve (plateforme) | 1,000 [1,00 ; 1,00] | 0,967 [0,90 ; 1,00] | 0,975 [0,94 ; 1,00] | 1,000 [1,00 ; 1,00] |
| Baseline : nombre de mentions | 0,933 [0,80 ; 1,00] | 0,878 [0,73 ; 1,00] | 0,911 [0,78 ; 1,00] | 0,944 [0,83 ; 1,00] |

Écart apparié nDCG@3 : 0,064 [-0,02 ; 0,19], gains / pertes / égalités 4 / 1 / 10, p = 0,375.

## 8. Recommandations de documents (10 documents sources)

| Mode | Precision@5 | Recall@5 | nDCG@5 | MRR | Doublons ou mémo piégé recommandés |
|---|---|---|---|---|---|
| content | 0,440 [0,28 ; 0,60] | 0,497 [0,37 ; 0,63] | 0,648 [0,50 ; 0,79] | 0,920 [0,76 ; 1,00] | 0 |
| graph | 0,660 [0,52 ; 0,78] | 0,818 [0,65 ; 0,94] | 0,877 [0,70 ; 0,98] | 0,950 [0,85 ; 1,00] | 0 |
| hybrid | 0,640 [0,50 ; 0,78] | 0,784 [0,62 ; 0,92] | 0,908 [0,80 ; 0,97] | 1,000 [1,00 ; 1,00] | 0 |

Hybride vs contenu seul (nDCG@5) : écart 0,261, p = 0,0039.

## 9. Modification post-gel (garantie par source dans la fusion RRF)

Voir `evaluation/JOURNAL_DEVELOPPEMENT.md`. Résultats rapportés séparément de la campagne principale.

| Mesure (hybride final) | Gel | Post-gel |
|---|---|---|
| Recherche nDCG@5 (toutes) | 0,839 | 0,841 |
| Recherche nDCG@5 (jamais inspectées) | 0,851 | 0,854 |
| Couverture des preuves | 0,943 | 0,953 |
| Exactitude (toutes) | 0,742 | 0,758 |
| Exactitude (développement) | 0,882 | 0,941 |
| Exactitude (jamais inspectées) | 0,694 | 0,694 |

## Figures

- `figures/fig_experts.png`
- `figures/fig_ingestion.png`
- `figures/fig_qa_architectures.png`
- `figures/fig_recherche_categories.png`
- `figures/fig_recherche_encodeurs.png`
- `figures/fig_recommandations.png`
- `figures/fig_seuil_suffisance.png`
