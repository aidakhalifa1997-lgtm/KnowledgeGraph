# Remerciements {nontoc}

[À personnaliser avant le dépôt.]

Nous remercions notre encadrant académique pour ses conseils méthodologiques et son exigence, ainsi que notre encadrant professionnel pour la confiance accordée et le temps consacré aux échanges sur les enjeux de gestion des connaissances en milieu bancaire.

Nos remerciements vont également à l'équipe pédagogique du Master Data Engineering, aux collègues de la Direction Transformation, Processus, Organisation et SI qui ont nourri notre réflexion par leur pratique quotidienne des procédures, ainsi qu'à nos proches pour leur soutien tout au long de ce projet.

# Résumé {nontoc}

Dans une banque, la connaissance opérationnelle est dispersée dans des procédures, des comptes rendus, des chartes de projet et des notes, souvent en plusieurs versions, parfois contradictoires et soumises à des règles de diffusion. Ce mémoire présente la conception, le développement et l'évaluation d'une plateforme de gestion des connaissances qui combine un graphe de connaissances Neo4j, une recherche hybride (lexicale, vectorielle et par le graphe) et un workflow de questions-réponses orchestré par LangGraph. La plateforme ingère des documents hétérogènes (PDF, DOCX, TXT, PDF scanné lu par OCR), en extrait les entités et les relations avec leur provenance, applique le contrôle d'accès avant toute recherche, cite ses sources et s'abstient lorsque le contexte ne suffit pas. Elle propose aussi une recherche d'experts justifiée et des recommandations de documents expliquées.

L'évaluation repose sur un corpus synthétique de 35 documents d'une banque fictive et sur un jeu de 66 questions annotées réparties en dix catégories. En mode hors-ligne, sans modèle de langage, l'architecture hybride finale atteint un nDCG@5 de 0,839 en recherche documentaire et une exactitude de 0,742 de bout en bout, contre 0,651 pour un RAG vectoriel et 0,515 pour un GraphRAG seul, sans fuite d'accès ni citation inventée. Ces résultats doivent être lus avec leurs limites : corpus et questions rédigés par l'auteure, échantillon réduit, encodeurs légers et absence d'évaluation avec un vrai modèle de langage. L'écart entre les questions de développement (0,882) et les questions jamais inspectées (0,694) montre en outre une part de sur-ajustement des heuristiques.

**Mots-clés :** graphe de connaissances, RAG, GraphRAG, recherche hybride, LangGraph, Neo4j, gestion des connaissances, banque, explicabilité, contrôle d'accès.

# Abstract {nontoc}

In a bank, operational knowledge is scattered across procedures, meeting minutes, project charters and notes, often in several versions, sometimes contradictory, and subject to restricted distribution. This thesis presents the design, development and evaluation of a knowledge-management platform that combines a Neo4j knowledge graph, hybrid retrieval (lexical, dense and graph-based) and a question-answering workflow orchestrated with LangGraph. The platform ingests heterogeneous documents (PDF, DOCX, TXT and an OCR-processed scanned PDF), extracts entities and relations together with their provenance, enforces access control before any retrieval, cites its sources and abstains when the context is insufficient. It also offers justified expert finding and explained document recommendations.

The evaluation relies on a synthetic corpus of 35 documents from a fictional bank and on 66 annotated questions spread over ten categories. In offline mode, without any language model, the final hybrid architecture reaches an nDCG@5 of 0.839 for document retrieval and an end-to-end accuracy of 0.742, against 0.651 for a dense RAG baseline and 0.515 for graph-only retrieval, with no access leak and no invented citation. These results must be read with their limitations: corpus and questions written by the author, small sample, lightweight encoders and no evaluation with an actual language model. The gap between development questions (0.882) and never-inspected questions (0.694) also reveals some overfitting of the heuristics.

**Keywords:** knowledge graph, RAG, GraphRAG, hybrid retrieval, LangGraph, Neo4j, knowledge management, banking, explainability, access control.

# Sommaire {nontoc}

[[SOMMAIRE]]

# Liste des figures {nontoc}

[[FIGURES]]

# Liste des tableaux {nontoc}

[[TABLEAUX]]

# Liste des abréviations {nontoc}

| Sigle | Signification |
|---|---|
| API | Application Programming Interface (interface de programmation) |
| BM25 | Best Matching 25, fonction de pondération lexicale |
| CI | Intégration continue (Continuous Integration) |
| CRAG | Corrective Retrieval-Augmented Generation |
| CSP | Content Security Policy |
| DOCX | Format de document Office Open XML |
| DPR | Dense Passage Retrieval |
| DSI | Direction des Systèmes d'Information |
| ER | Résolution d'entités (Entity Resolution) |
| GraphRAG | RAG guidé par un graphe de connaissances |
| HNSW | Hierarchical Navigable Small World (index de recherche approximative) |
| IC | Intervalle de confiance |
| IDF | Inverse Document Frequency |
| JWT | JSON Web Token |
| KG | Graphe de connaissances (Knowledge Graph) |
| KPI | Indicateur clé de performance |
| KYC | Know Your Customer (connaissance client) |
| LAB-FT | Lutte anti-blanchiment et contre le financement du terrorisme |
| LLM | Grand modèle de langage (Large Language Model) |
| MRR | Mean Reciprocal Rank |
| nDCG | normalized Discounted Cumulative Gain |
| NER | Reconnaissance d'entités nommées |
| OCR | Reconnaissance optique de caractères |
| PBKDF2 | Password-Based Key Derivation Function 2 |
| PCA | Plan de continuité d'activité |
| PDF | Portable Document Format |
| PPR | PageRank personnalisé (Personalized PageRank) |
| PSSI | Politique de sécurité des systèmes d'information |
| RACI | Réalisateur, Approbateur, Consulté, Informé |
| RAG | Génération augmentée par la recherche (Retrieval-Augmented Generation) |
| RPO | Recovery Point Objective (perte de données maximale admissible) |
| RRF | Reciprocal Rank Fusion |
| RTO | Recovery Time Objective (durée maximale d'interruption admissible) |
| SSO | Authentification unique (Single Sign-On) |
| TLS | Transport Layer Security |

Table: Sigles et abréviations utilisés
