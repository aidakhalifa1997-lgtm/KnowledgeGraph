# Cadrage V2 du PFE : du démonstrateur au projet de recherche appliquée

Document de travail à valider avec l'encadrant. Les chiffres cités sont mesurés et reproductibles
(`scripts/download_obliqa.sh`, puis `python -m benchmarks.obliqa profile|baselines`). Ce qui n'est pas
encore mesuré est signalé comme hypothèse ou estimation.

## 1. Diagnostic de la version 1

| Point | Constat | Conséquence pour le jury |
|---|---|---|
| Corpus | 35 documents fictifs rédigés par le même auteur que les questions | Validité externe faible ; risque de circularité (questions taillées pour le système) |
| LLM | Aucune mesure avec un vrai LLM (mode hors ligne, générateur extractif) | Le « enrichi par un LLM » du titre n'est pas démontré |
| Extraction | Règles YAML et heuristiques ; LLM prévu mais non exécuté | Le graphe reflète des règles écrites à la main, pas une construction automatique |
| Évaluation | 66 questions, métriques à mots-clés | Puissance statistique faible ; qualité des réponses non mesurée |
| Résultat principal | GraphRAG ≈ RAG hybride | Honnête, mais sans explication causale ni contexte où le graphe devrait aider |

Ce qui reste solide et sera conservé : architecture en couches, Neo4j avec provenance, LangGraph,
contrôle d'accès audité (0 fuite sur 990 réponses), protocole statistique (bootstrap apparié, test des
signes, gel des campagnes), tests automatisés, Docker, sécurité de l'ingestion.

## 2. Données : un benchmark public réel

### 2.1 Kaggle

`www.kaggle.com` est refusé par la politique réseau de l'environnement d'exécution : aucun jeu Kaggle n'a
pu être téléchargé ni sa licence vérifiée. Les jeux repérés par recherche (FAQ bancaires synthétiques,
journaux RAG synthétiques, défi FinanceRAG de l'ACM ICAIF 2024) sont soit synthétiques, soit orientés
questions numériques sur rapports financiers, où un graphe apporte peu. L'origine « Kaggle » n'est pas
un critère de valeur pour un jury ; ce qui compte : corpus réel, vérité terrain publiée, lignes de base
comparables.

### 2.2 Jeu retenu : ObliQA (réglementation financière)

ObliQA (Gokhan, Wang, Gurevych et Briscoe, 2024, arXiv:2409.05677) : questions de conformité sur 40
textes réglementaires de l'ADGM (Abu Dhabi Global Market), autorité de régulation financière. Le domaine
correspond au métier visé (banque, conformité, procédures). Figé sur le commit `c1b2c3c` du dépôt
`RegNLP/ObliQADataset`, contrôlé par SHA-256.

Profil mesuré (`evaluation/results/obliqa/profile.json`) :

| Mesure | Valeur |
|---|---|
| Documents / passages | 40 / 13 732 (720 passages vides, 17 identifiants en double) |
| Volume | 835 799 mots ; médiane 40 mots par passage |
| Renvois explicites (« Rule 11.2.1 ») | 1 382 passages ; 1 056 arêtes résolues dans le même document |
| Questions train / dev / test | 22 295 / 2 788 / 2 786 |
| Questions test multi-passages | 660 (dont 221 inter-documents) |
| Passages attendus introuvables dans le corpus | 0 |

Limites à écrire dans le mémoire :

- les questions sont générées par un LLM puis filtrées par un modèle d'inférence (NLI), elles ne sont pas
  rédigées par des experts ; leur proximité lexicale avec les passages favorise BM25 ;
- le dépôt ne déclare aucune licence : les données ne sont pas versionnées, seulement téléchargées ;
- corpus en anglais : la chaîne de traitement doit être rendue bilingue (analyseur plein texte, modèle
  spaCy, règles) ; le corpus de démonstration français est conservé.

Constat préalable important : sur les 1 187 paires de passages attendus du jeu de test, 2 seulement
sont reliées par un renvoi explicite et 85 partagent la même section parente. Les questions
multi-passages ont été construites par thèmes, pas en suivant les renvois. Un graphe purement
structurel ne suffira donc pas : la valeur ajoutée doit venir d'un graphe de concepts (obligations,
acteurs, termes définis) construit par le LLM. C'est l'hypothèse centrale à tester.

### 2.3 Rôle du corpus fictif

Il devient une suite de tests ciblés, impossible à obtenir sur un corpus public : contrôle d'accès par
direction, injection de consignes, documents périmés, conflits de versions, abstention. Il n'est plus
utilisé pour conclure sur la qualité de recherche.

## 3. Problématique et questions de recherche

Problématique : dans quelle mesure un graphe de connaissances construit automatiquement par un LLM
améliore-t-il la recherche et la génération de réponses sur des questions de conformité qui exigent de
réunir plusieurs dispositions réglementaires, et à quel coût ?

| Question | Hypothèse testable | Mesure |
|---|---|---|
| QR1 Recherche | Le graphe de concepts LLM améliore le Recall@10 multi-passages par rapport au meilleur système sans graphe | Recall@10, MAP@10, nDCG@10 ; différence appariée et IC 95 % |
| QR2 Construction | Le LLM extrait obligations et termes plus fidèlement que les règles | Précision et rappel sur 200 passages annotés à la main ; kappa inter-annotateurs |
| QR3 Génération | Le contexte issu du graphe réduit les affirmations non étayées | Fidélité et couverture des obligations (juge LLM calibré sur annotation humaine), précision des citations |
| QR4 Coût | Le gain justifie le coût | Jetons, coût, latence p50/p95 par question ; coût de construction du graphe |

Seuil fixé avant expérience : un gain de Recall@10 multi-passages inférieur à 3 points, ou dont l'IC
95 % contient zéro, sera déclaré non significatif.

## 4. Lignes de base mesurées (jeu de test, 2 786 questions)

`evaluation/results/obliqa/baselines_test.json` (IC 95 % par bootstrap, 2 000 rééchantillonnages) :

| Système | Sous-ensemble | n | Recall@10 | MAP@10 | nDCG@10 |
|---|---|---|---|---|---|
| BM25 | toutes | 2 786 | 0,752 [0,737 ; 0,766] | 0,600 | 0,654 |
| BM25 | 1 passage | 2 126 | 0,833 | 0,676 | 0,714 |
| BM25 | multi-passages | 660 | **0,492** [0,468 ; 0,516] | 0,355 | 0,460 |
| Dense WordLlama 256d | toutes | 2 786 | 0,616 | 0,440 | 0,495 |
| Dense WordLlama 256d | multi-passages | 660 | 0,344 | 0,224 | 0,305 |
| Fusion RRF BM25 + dense | toutes | 2 786 | 0,726 | 0,547 | 0,606 |
| Fusion RRF BM25 + dense | multi-passages | 660 | 0,453 | 0,301 | 0,403 |

Lecture : le meilleur système retrouve 83 % des passages attendus quand la question n'en exige qu'un,
mais 49 % quand elle en exige plusieurs. C'est l'écart que le projet doit réduire. L'encodeur dense
actuel, conçu pour être léger, dégrade la fusion (−2,6 points, IC [−3,6 ; −1,6]) : un encodeur plus
performant est nécessaire pour une base hybride crédible.

## 5. Architecture cible

```
Benchmarks (ObliQA, corpus fictif)            Sources métier (PDF, DOCX)
        │ adaptateur JSON                             │ OCR, validation, quarantaine
        └──────────────┬──────────────────────────────┘
                       ▼
        Passages normalisés (id, document, section, texte, droits)
                       │
        ┌──────────────┼────────────────────────────────────────────┐
        ▼              ▼                                            ▼
  Index BM25    Index vectoriel (encodeur à choisir)     Extraction LLM à schéma contraint
        │              │                                  obligations, acteurs, termes, renvois
        │              │                                  + provenance, résolution d'entités
        │              │                                            ▼
        │              │                              Neo4j : Document–Section–Passage,
        │              │                              Obligation, Acteur, Terme, REFERS_TO
        └──────┬───────┴────────────────────────────────────────────┘
               ▼
   Recherche : graines BM25/dense → expansion par concepts partagés (1–2 sauts) → reclassement
               ▼
   LangGraph : analyse → recherche → suffisance → génération LLM avec citations → vérification → abstention
               ▼
   Évaluation : recherche (gold ObliQA), génération (juge calibré), coût et latence, tests de sécurité
```

Changements par rapport à la V1 :

1. adaptateur de benchmark qui charge les passages tels quels (pas d'OCR nécessaire pour ObliQA) ;
2. schéma de graphe réglementaire : `Obligation` (sujet, modalité, action, condition), `Actor`,
   `DefinedTerm`, `REFERS_TO` entre passages ;
3. extraction par LLM réellement exécutée, sortie JSON validée par schéma, mise en cache par
   empreinte SHA-256 du passage (aucun appel répété, coût maîtrisé) ;
4. génération par LLM, le générateur extractif devenant une ligne de base ;
5. évaluation de la génération par un juge LLM dont l'accord avec une annotation humaine est mesuré
   avant usage (l'expertise conformité de l'auteure est ici un atout).

## 6. Protocole expérimental

- **Systèmes** : S0 BM25 ; S1 dense ; S2 hybride RRF ; S3 S2 + graphe structurel (renvois) ;
  S4 S2 + graphe de concepts LLM ; S5 S4 sans résolution d'entités (ablation).
- **Découpage** : réglages sur dev uniquement ; test gelé. Pour les expériences coûteuses (génération),
  échantillon stratifié tiré une fois avec graine fixe : les 660 questions multi-passages et 340
  questions à un passage.
- **Statistiques** : bootstrap apparié, test des signes, correction de Holm pour les comparaisons
  multiples ; même LLM, même température (0) et même prompt pour tous les systèmes.
- **Abstention** : questions dont les documents sources sont retirés de l'index (vérité connue :
  le système doit s'abstenir), sans écrire de nouvelles questions.
- **Coût** : pilote de 50 questions pour mesurer jetons et latence réels avant toute campagne complète.
- **Annotation humaine** : 200 passages (extraction) et 100 réponses (génération), double annotation
  partielle pour le kappa.

## 7. Prérequis bloquants

| Prérequis | Pourquoi | Action |
|---|---|---|
| Clé API du LLM | QR2, QR3, QR4 impossibles sans | À enregistrer comme variable d'environnement de l'environnement cloud (`LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_BASE_URL`), jamais dans le chat ni dans le dépôt |
| Fournisseur confirmé | L'adaptateur dépend de l'API réelle | Nom du fournisseur et lien vers sa documentation |
| Accès `huggingface.co` | Encodeurs denses plus performants, modèle NLI de la métrique RePASs | Ajouter le domaine aux domaines autorisés de l'environnement |
| Budget | La construction du graphe porte sur environ 836 000 mots | Plafond de dépense validé avant le pilote |

## 8. Planning indicatif (semaines relatives)

| Semaine | Livrable |
|---|---|
| 1 | Adaptateur ObliQA, chaîne bilingue, encodeur dense retenu, lignes de base définitives |
| 2–3 | Extraction LLM (pilote puis corpus complet), annotation de 200 passages, mesure QR2 |
| 4 | Graphe réglementaire, recherche S3–S5 sur dev, gel des réglages |
| 5 | Campagne test recherche (QR1), génération et juge calibré (QR3), coûts (QR4) |
| 6 | Tests de sécurité sur corpus fictif, rédaction des résultats, mise à jour du mémoire et de la soutenance |

## 9. Références à vérifier avant intégration à la bibliographie

- Gokhan, T., Wang, K., Gurevych, I. et Briscoe, T. (2024). *RIRAG: Regulatory Information Retrieval and
  Answer Generation*. arXiv:2409.05677.
- Gokhan, T. et Briscoe, T. (2025). *Grounded Answers from Multi-Passage Regulations: Learning-to-Rank for
  Regulatory RAG*. Natural Legal Language Processing Workshop 2025, ACL, p. 135–146.
  doi:10.18653/v1/2025.nllp-1.10.
