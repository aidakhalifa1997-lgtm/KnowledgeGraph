# Orizia Knowledge Graph — plateforme de gestion des connaissances

Projet de fin d'études de Master Data Engineering : **conception et développement d'une plateforme intelligente de gestion des connaissances fondée sur un Knowledge Graph enrichi par un LLM**, appliquée au contexte d'une banque.

La plateforme permet d'interroger une documentation interne en langage naturel et d'obtenir des réponses **citées**, **conformes aux droits d'accès** de l'utilisateur, avec **abstention motivée** lorsque les sources ne suffisent pas. Elle combine recherche lexicale (BM25), recherche vectorielle et parcours d'un graphe de connaissances Neo4j (GraphRAG local), orchestrés par un workflow LangGraph explicite.

> **Données** : la banque « Orizia » est fictive. Les 35 documents du corpus et les 66 questions d'évaluation sont **entièrement synthétiques**, rédigés pour ce projet. Aucune donnée réelle d'entreprise n'est présente dans le dépôt.
>
> **LLM** : aucune clé d'API n'a été utilisée pendant le projet. Toutes les mesures ont été faites en **mode hors-ligne** (extraction par règles, générateur extractif). Les adaptateurs LLM (Anthropic, API compatibles « Chat Completions ») sont implémentés et testés avec des réponses simulées, mais leur apport n'a pas été mesuré.
>
> **Statut** : prototype évalué, exécuté et testé localement avec Docker Compose. **Aucun déploiement distant n'a été réalisé** et la plateforme n'est pas présentée comme prête pour la production.

## Fonctionnalités

- **Ingestion** de documents PDF, DOCX, TXT et PDF scannés (OCR Tesseract) : validation de sécurité des fichiers, nettoyage, lecture du cartouche (référence, version, diffusion…), contrôle qualité, détection des doublons exacts et approchés (SHA-256, MinHash), gestion des versions, quarantaine des documents contenant des injections de prompt, ingestion idempotente.
- **Extraction** d'entités et de relations : 18 règles déterministes, extracteur LLM optionnel contraint par l'ontologie et vérifié (preuve présente dans le texte), résolution d'entités en cascade avec entités candidates à valider.
- **Graphe de connaissances Neo4j** dont chaque relation conserve sa **provenance** (documents, passages, citations, extracteurs, confiance).
- **Questions-réponses** : recherche hybride BM25 + vecteurs + graphe fusionnée par Reciprocal Rank Fusion et routée selon le type de question ; contrôle de suffisance ; détection des versions et des valeurs contradictoires ; génération citée ; vérification des citations et assainissement de la réponse.
- **Contrôle d'accès** : documents autorisés calculés **avant** toute recherche et appliqués à chaque requête (texte, vecteurs, graphe, exploration).
- **Recherche d'experts** (preuves typées pondérées), **recommandations** de documents (contenu + entités + graphe), **exploration visuelle** du graphe (Cytoscape.js).
- **Interface web** React + TypeScript, **API** FastAPI (JWT, rôles, limitation de débit), **Docker Compose** (conteneurs en lecture seule, Neo4j non exposé, HTTPS par Caddy en production), sauvegarde et restauration testées, intégration continue.

## Démarrage rapide (Docker)

Prérequis : Docker et le plugin Docker Compose v2.

```bash
cd RAG
make env        # crée .env avec des secrets aléatoires (jamais versionné)
make up         # construit et démarre neo4j, backend et frontend
make ingest     # charge le corpus de démonstration (environ 20 s)
```

Interface : <http://localhost:8080>. Comptes de démonstration (corpus fictif uniquement) : voir `CODE/config/users.example.yaml`.

Installation locale de développement, tests, évaluation et dépannage : [`DETAILS/INSTALLATION_ET_EXECUTION.txt`](DETAILS/INSTALLATION_ET_EXECUTION.txt).

## Brancher un LLM (optionnel)

Renseigner dans `RAG/.env` (jamais dans le code ni dans un fichier versionné) : `LLM_PROVIDER` (`anthropic` ou `openai_compatible`), `LLM_API_KEY`, `LLM_MODEL` et, si besoin, `LLM_BASE_URL`, puis redémarrer (`make up`). La compatibilité d'un fournisseur avec l'interface « Chat Completions » doit être vérifiée dans sa documentation. Toute clé qui aurait circulé en clair doit être révoquée et remplacée avant usage.

## Résultats principaux

Configuration gelée, encodeur WordLlama, générateur extractif hors-ligne. Source unique : [`CODE/evaluation/results/RESULTATS.md`](CODE/evaluation/results/RESULTATS.md).

| Mesure | Résultat |
|---|---|
| Recherche, nDCG@5 (55 questions) | final routé 0,839 ; BM25 0,831 ; hybride 0,803 ; vectoriel 0,720 ; graphe seul 0,708 |
| Réponses, exactitude (66 questions) | final 0,742 [0,64 ; 0,85] — 0,882 sur les questions de développement, **0,694 sur les questions jamais inspectées** |
| Apport du graphe (exactitude) | relationnelles 0,12 → 0,62 ; multi-sauts 0,30 → 0,60 (RAG vectoriel → final) |
| Fiabilité | 0 citation inventée, 0 fuite d'accès, 0 chaîne interdite |
| Abstention (final) | rappel 0,909 ; 18 % d'abstentions abusives |
| Experts / recommandations | nDCG@3 0,975 vs 0,911 (non significatif) ; nDCG@5 0,908 vs 0,648 (p = 0,004) |
| Extraction par règles | F1 0,984 (documents de mise au point) ; 0,830 (documents de test) |
| Tests | 106 cas (69 unitaires, 37 d'intégration) |
| Audit d'accès | 990 réponses rejouées avec 3 comptes restreints, 0 fuite |

Limites détaillées dans le mémoire (chapitre 6) et dans [`DETAILS/TESTS_ET_EVALUATION.txt`](DETAILS/TESTS_ET_EVALUATION.txt).

## Organisation du dossier

| Dossier | Contenu |
|---|---|
| [`CODE/`](CODE) | backend Python (ingestion, extraction, graphe, recherche, orchestration, API), interface React, tests, évaluation, scripts d'exploitation, Dockerfiles |
| [`data/`](data) | corpus synthétique (sources, documents générés), référentiel d'entités, vérités terrain |
| [`DETAILS/`](DETAILS) | onze fiches pédagogiques ; commencer par [`GUIDE_COMPLET.txt`](DETAILS/GUIDE_COMPLET.txt) |
| [`RAPPORT ET PRESENTATION/`](RAPPORT%20ET%20PRESENTATION) | mémoire (DOCX, PDF), présentation (PPTX, PDF), figures et captures, sources de génération |
| [`RESEARCH PAPERS/`](RESEARCH%20PAPERS) | bibliographie vérifiée, matrice de littérature, synthèse critique |

L'index complet des livrables est dans [`README_LIVRABLES.txt`](README_LIVRABLES.txt).

## Sécurité

- Aucun secret dans le dépôt : `.env` est ignoré par Git, `.env.example` ne contient que des valeurs fictives, la CI recherche les secrets (gitleaks) et les vulnérabilités des dépendances (pip-audit).
- Les comptes de `CODE/config/users.example.yaml` servent **uniquement** à la démonstration sur le corpus fictif ; en dehors, créer des comptes avec `python -m scripts.create_user` dans un fichier non versionné et, en production, passer par l'annuaire de l'entreprise.
- Ne jamais placer de documents confidentiels dans `data/`.
