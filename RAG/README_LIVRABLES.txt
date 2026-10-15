====================================================================================================
                                     INDEX DES LIVRABLES DU PROJET
====================================================================================================

Projet : Conception et développement d'une plateforme intelligente de gestion des connaissances
basée sur un Knowledge Graph enrichi par un LLM (PFE, Master Data Engineering).

Chemins relatifs au dossier RAG/. État : prototype évalué, exécuté localement avec Docker
Compose ; aucun déploiement distant réalisé ; aucune mesure avec un vrai LLM (aucune clé fournie).


1. CODE ET PLATEFORME (CODE/)
============================

    Élément                                   Emplacement
    ----------------------------------------  ---------------------------------------------------
    Ingestion, OCR, qualité, doublons         CODE/ingestion/
    Extraction (règles, LLM, résolution)      CODE/extraction/, CODE/config/extraction_rules.yaml
    Ontologie, configuration, LLM, journaux   CODE/core/
    Graphe Neo4j (schéma, écriture, lecture)  CODE/knowledge_graph/
    Recherche hybride et GraphRAG             CODE/retrieval/
    Workflow LangGraph                        CODE/orchestration/
    Experts, recommandations                  CODE/expert_discovery/, CODE/recommendations/
    API FastAPI                               CODE/backend/
    Interface React + Cytoscape               CODE/frontend/
    Assemblage des composants                 CODE/services.py
    Scripts (ingestion, utilisateurs,         CODE/scripts/
    campagne, sauvegarde, restauration)
    Tests (106 cas)                           CODE/tests/
    Conteneurs et exploitation                docker-compose.yml, docker-compose.debug.yml,
                                              docker-compose.prod.yml, CODE/Dockerfile,
                                              CODE/frontend/Dockerfile, CODE/deploy/Caddyfile,
                                              Makefile
    Configuration (valeurs fictives)          .env.example
    Intégration continue                      ../.github/workflows/ci.yml, ../.gitleaks.toml


2. DONNÉES ET VÉRITÉS TERRAIN (data/)
====================================

    Corpus généré (35 documents)              data/sample_documents/
    Sources du corpus et générateur           data/synthetic_data/sources/, generate_corpus.py
    Référentiel d'entités                     data/synthetic_data/referentials/referentials.yaml
    Questions (66), experts, recommandations, data/synthetic_data/gold/
    résolution d'entités, guide d'annotation

Toutes les données sont synthétiques (banque fictive « Orizia »).


3. ÉVALUATION (CODE/evaluation/)
===============================

    Banc d'évaluation                         run_evaluation.py, metrics.py, extraction_eval.py
    Rapport et figures générés                results/RESULTATS.md, results/figures/
    Résultats bruts                           results/wordllama/ (campagne principale),
                                              results/wordllama_postgel/, results/spacy/
    Journal des modifications (gel)           JOURNAL_DEVELOPPEMENT.md
    Reproductibilité                          compare_runs.py, scripts/run_evaluation_campaign.sh


4. DOCUMENTATION PÉDAGOGIQUE (DETAILS/)
======================================

    GUIDE_COMPLET.txt                    point d'entrée, glossaire, parcours de lecture
    ARCHITECTURE.txt                     couches, parcours, contrôle d'accès
    TECHNOLOGIES_ET_JUSTIFICATIONS.txt   choix techniques, alternatives, justifications
    INGESTION_OCR_EXTRACTION.txt         du fichier aux entités et relations
    KNOWLEDGE_GRAPH_NEO4J.txt            modèle, provenance, Cypher
    WORKFLOW_RAG_GRAPHRAG.txt            BM25, vecteurs, RRF, GraphRAG, routage
    LANGGRAPH_ET_ORCHESTRATION.txt       workflow de réponse, nœud par nœud
    INSTALLATION_ET_EXECUTION.txt        installation, démonstration, tests, évaluation
    TESTS_ET_EVALUATION.txt              tests, protocole, métriques, résultats
    DEPLOIEMENT_ET_MAINTENANCE.txt       serveur, sauvegardes, supervision, hébergement
    PREPARATION_SOUTENANCE.txt           plan, démonstration, questions du jury


5. MÉMOIRE ET PRÉSENTATION (RAPPORT ET PRESENTATION/)
====================================================

    Mémoire (101 pages)                  Memoire_PFE_Knowledge_Graph_LLM.docx et .pdf
    Présentation (20 diapositives,       Presentation_PFE_Knowledge_Graph_LLM.pptx et .pdf
    notes de l'orateur)
    Figures de résultats et schémas      figures/
    Captures réelles de l'application    figures/captures/
    Sources (Markdown du mémoire,        sources/ : memoire/*.md, memoire.json,
    générateurs)                         build_memoire.js, finalize_memoire.py,
                                         build_presentation.cjs, schemas.html,
                                         render_schemas.cjs, captures.cjs

Éléments à compléter par l'auteure dans le mémoire et la présentation : nom, établissement,
encadrants (mentions « [à compléter] ») et remerciements (« [À personnaliser] »).


6. RECHERCHE BIBLIOGRAPHIQUE (RESEARCH PAPERS/)
==============================================

    BIBLIOGRAPHIE.md                     42 références vérifiées + 6 documentations techniques,
                                         statut (publié / prépublication), mentions
                                         « à vérifier » lorsque nécessaire
    MATRICE_LITTERATURE.md               comparaison des travaux
    SYNTHESE_CRITIQUE.md                 positionnement, questions de recherche, hypothèses

Les PDF des articles ne sont pas redistribués (licences) ; CODE/scripts/download_papers.sh
permet de télécharger les prépublications arXiv pour un usage personnel.


7. CE QUI RESTE À FAIRE (HORS PÉRIMÈTRE RÉALISÉ)
===============================================

  - mesurer l'apport d'un LLM (clé à fournir ; campagne à rejouer avec les mêmes questions) ;
  - déployer sur un hébergement choisi et VÉRIFIER l'application distante ;
  - avant tout usage réel : SSO, homologation, supervision, sauvegardes automatisées,
    évaluation sur documents réels (voir DETAILS/DEPLOIEMENT_ET_MAINTENANCE.txt, section 9).
