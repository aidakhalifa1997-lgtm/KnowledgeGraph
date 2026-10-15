# Bibliographie commentée du PFE

**Projet :** Plateforme intelligente de gestion des connaissances fondée sur un Knowledge Graph enrichi par un LLM
**Date de constitution :** octobre 2026
**Méthode de vérification :** chaque référence a été recherchée en ligne (moteur de recherche web) et ses métadonnées
(titre, auteurs, année, lieu de publication, DOI) ont été recoupées avec au moins une source de référence
(ACL Anthology, actes NeurIPS/ICLR, ACM DL, IEEE Xplore, now Publishers, page arXiv). Les points qui n'ont pas pu être
confirmés sont signalés explicitement par la mention **[à vérifier]**.

> **Limite d'accès.** Depuis l'environnement de développement, les serveurs arXiv, ACM, IEEE et ACL Anthology étaient
> inaccessibles en téléchargement direct (politique réseau du bac à sable). Les PDF n'ont donc **pas** été intégrés
> au dépôt. Cela est de toute façon préférable : la licence arXiv par défaut n'autorise pas la redistribution par un
> tiers. Le script `RAG/CODE/scripts/download_papers.sh` permet de télécharger, pour un usage personnel, les
> prépublications arXiv listées ci-dessous.

Légende du statut :
- **Publié (évalué par les pairs)** : article de conférence ou de revue avec comité de lecture.
- **Prépublication** : document arXiv non publié (ou dont la publication n'a pas pu être confirmée).
- **Documentation officielle** : documentation d'éditeur de logiciel (source professionnelle, non scientifique).

---

## Axe 1 — Retrieval-Augmented Generation (RAG)

### [1] Lewis et al. (2020) — RAG
- **Titre exact :** Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks
- **Auteurs :** Patrick Lewis, Ethan Perez, Aleksandra Piktus, Fabio Petroni, Vladimir Karpukhin, Naman Goyal, Heinrich Küttler, Mike Lewis, Wen-tau Yih, Tim Rocktäschel, Sebastian Riedel, Douwe Kiela
- **Année / lieu :** 2020, *Advances in Neural Information Processing Systems 33* (NeurIPS 2020)
- **URL officielle :** https://papers.nips.cc/paper/2020/hash/6b493230205f780e1bc26945df7481e5-Abstract.html — arXiv : 2005.11401
- **Statut :** Publié (évalué par les pairs)
- **Problématique :** les modèles de langue stockent leurs connaissances dans leurs paramètres ; ces connaissances sont difficiles à mettre à jour et à justifier.
- **Méthodologie :** couplage d'un générateur seq2seq (BART) et d'un récupérateur dense (DPR) sur un index Wikipédia ; deux variantes (RAG-Sequence, RAG-Token), entraînées de bout en bout.
- **Résultats importants :** état de l'art sur plusieurs tâches de questions-réponses en domaine ouvert ; générations jugées plus factuelles et plus spécifiques qu'un modèle purement paramétrique.
- **Limites :** récupération limitée à des passages indépendants ; aucune exploitation explicite des relations entre entités ; entraînement conjoint coûteux.
- **Contribution au projet :** définit le paradigme « mémoire non paramétrique + générateur » que la plateforme reprend (sans réentraînement : RAG « à l'inférence »).
- **Composants concernés :** `retrieval/`, `orchestration/`.
- **Pourquoi la citer :** article fondateur du terme RAG ; indispensable pour situer le sujet.

### [2] Gao et al. (2023) — Synthèse sur le RAG pour les LLM
- **Titre exact :** Retrieval-Augmented Generation for Large Language Models: A Survey
- **Auteurs :** Yunfan Gao, Yun Xiong, Xinyu Gao, Kangxiang Jia, Jinliu Pan, Yuxi Bi, Yi Dai, Jiawei Sun, Qianyu Guo, Meng Wang, Haofen Wang (liste des versions v2 et suivantes)
- **Année / lieu :** 2023 (v1), arXiv:2312.10997
- **URL :** https://arxiv.org/abs/2312.10997
- **Statut :** Prépublication
- **Problématique :** organiser un champ de recherche en croissance très rapide.
- **Méthodologie :** revue de littérature ; typologie Naive RAG / Advanced RAG / Modular RAG.
- **Résultats importants :** identification des leviers d'amélioration (pré-récupération, post-récupération, réordonnancement, boucles de récupération) et des dimensions d'évaluation.
- **Limites :** prépublication ; synthèse descriptive sans évaluation expérimentale propre.
- **Contribution au projet :** grille de lecture pour positionner notre architecture comme un « RAG modulaire » (routage, fusion, vérification).
- **Composants concernés :** `orchestration/`, `retrieval/`.
- **Pourquoi la citer :** cadre de référence commode pour le chapitre « état de l'art ».

### [3] Karpukhin et al. (2020) — Dense Passage Retrieval
- **Titre exact :** Dense Passage Retrieval for Open-Domain Question Answering
- **Auteurs :** Vladimir Karpukhin, Barlas Oguz, Sewon Min, Patrick Lewis, Ledell Wu, Sergey Edunov, Danqi Chen, Wen-tau Yih
- **Année / lieu :** 2020, *Proceedings of EMNLP 2020*, p. 6769–6781
- **DOI :** 10.18653/v1/2020.emnlp-main.550
- **Statut :** Publié (évalué par les pairs)
- **Problématique :** la recherche lexicale (BM25) rate les reformulations sémantiques.
- **Méthodologie :** double encodeur BERT entraîné par contraste sur des paires question/passage.
- **Résultats importants :** gain de 9 à 19 points absolus de précision top-20 par rapport à un BM25 Lucene sur les jeux évalués.
- **Limites :** nécessite des données d'entraînement supervisées ; la généralisation hors domaine n'est pas garantie (voir [6]).
- **Contribution au projet :** justifie la composante vectorielle ; sert aussi à expliquer pourquoi nos encodeurs hors-ligne (vecteurs de mots moyennés) sont une solution de repli moins performante.
- **Composants concernés :** `retrieval/embeddings.py`, `retrieval/vector.py`.

### [4] Reimers & Gurevych (2019) — Sentence-BERT
- **Titre exact :** Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks
- **Auteurs :** Nils Reimers, Iryna Gurevych
- **Année / lieu :** 2019, *Proceedings of EMNLP-IJCNLP 2019*, p. 3982–3992
- **DOI :** 10.18653/v1/D19-1410
- **Statut :** Publié (évalué par les pairs)
- **Problématique :** produire des vecteurs de phrases comparables par similarité cosinus.
- **Méthodologie :** réseau siamois BERT affiné sur des paires de phrases (NLI, STS).
- **Résultats importants :** embeddings de phrases efficaces pour la recherche sémantique, à coût d'inférence réduit par rapport à un cross-encodeur.
- **Limites :** dépend d'un modèle neuronal lourd (PyTorch) et de son téléchargement.
- **Contribution au projet :** référence pour expliquer les embeddings de phrases et la similarité cosinus ; option recommandée en perspective (modèle multilingue) lorsque l'environnement autorise le téléchargement de modèles.
- **Composants concernés :** `retrieval/embeddings.py`.

### [5] Robertson & Zaragoza (2009) — BM25
- **Titre exact :** The Probabilistic Relevance Framework: BM25 and Beyond
- **Auteurs :** Stephen Robertson, Hugo Zaragoza
- **Année / lieu :** 2009, *Foundations and Trends in Information Retrieval*, vol. 3, n° 4, p. 333–389
- **DOI :** 10.1561/1500000019
- **Statut :** Publié (monographie évaluée)
- **Problématique :** fonder théoriquement les modèles de pondération lexicale.
- **Méthodologie :** présentation du cadre probabiliste de pertinence et dérivation de BM25 / BM25F.
- **Résultats importants :** BM25 reste une référence robuste et peu coûteuse.
- **Limites :** insensible aux synonymes et paraphrases.
- **Contribution au projet :** composante lexicale de la recherche hybride (index plein texte Lucene de Neo4j).
- **Composants concernés :** `retrieval/lexical.py`, `knowledge_graph/schema.py`.

### [6] Thakur et al. (2021) — BEIR
- **Titre exact :** BEIR: A Heterogeneous Benchmark for Zero-shot Evaluation of Information Retrieval Models
- **Auteurs :** Nandan Thakur, Nils Reimers, Andreas Rücklé, Abhishek Srivastava, Iryna Gurevych
- **Année / lieu :** 2021, NeurIPS 2021, *Datasets and Benchmarks Track*
- **URL :** https://neurips.cc/virtual/2021/poster/29903 — arXiv : 2104.08663
- **Statut :** Publié (évalué par les pairs)
- **Problématique :** les récupérateurs neuronaux généralisent-ils hors de leur domaine d'entraînement ?
- **Méthodologie :** 18 jeux de données hétérogènes, 10 systèmes (lexicaux, denses, épars, réordonnancement).
- **Résultats importants :** BM25 est une baseline robuste ; les récupérateurs denses sous-performent souvent hors domaine.
- **Limites :** jeux de données majoritairement anglophones.
- **Contribution au projet :** justifie l'hybridation lexical + vectoriel plutôt qu'un RAG purement vectoriel, en particulier sur un vocabulaire d'entreprise spécifique (codes de procédures, noms d'applications).
- **Composants concernés :** `retrieval/hybrid.py`.

### [7] Cormack, Clarke & Büttcher (2009) — Reciprocal Rank Fusion
- **Titre exact :** Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods
- **Auteurs :** Gordon V. Cormack, Charles L. A. Clarke, Stefan Büttcher
- **Année / lieu :** 2009, *Proceedings of SIGIR 2009*, p. 758–759
- **DOI :** 10.1145/1571941.1572114
- **Statut :** Publié (évalué par les pairs, article court)
- **Problématique :** combiner des classements issus de systèmes hétérogènes dont les scores ne sont pas comparables.
- **Méthodologie :** score fusionné = Σ 1/(k + rang), avec k = 60 ; expériences TREC et LETOR 3.
- **Résultats importants :** RRF surpasse chaque système pris isolément et la méthode Condorcet.
- **Limites :** ignore l'amplitude des scores ; paramètre k fixé empiriquement.
- **Contribution au projet :** méthode de fusion retenue pour combiner BM25, recherche vectorielle et récupération par le graphe. Elle est simple, sans apprentissage et défendable.
- **Composants concernés :** `retrieval/fusion.py`.

### [8] Malkov & Yashunin (2018/2020) — HNSW
- **Titre exact :** Efficient and Robust Approximate Nearest Neighbor Search Using Hierarchical Navigable Small World Graphs
- **Auteurs :** Yu. A. Malkov, D. A. Yashunin
- **Année / lieu :** publication en ligne le 28/12/2018, *IEEE Transactions on Pattern Analysis and Machine Intelligence* — arXiv : 1603.09320
- **DOI :** 10.1109/TPAMI.2018.2889473 (recoupé via des sources secondaires ; page IEEE non consultée directement)
- **Statut :** Publié (évalué par les pairs)
- **Problématique :** recherche approximative des plus proches voisins à grande échelle.
- **Méthodologie :** graphe de proximité hiérarchique multi-couches.
- **Résultats importants :** excellent compromis rappel/latence.
- **Limites :** recherche approximative ; consommation mémoire.
- **Contribution au projet :** algorithme sous-jacent à l'index vectoriel de Neo4j (documentation Neo4j).
- **Composants concernés :** `knowledge_graph/schema.py` (index vectoriel).

### [9] Kusupati et al. (2022) — Matryoshka Representation Learning
- **Titre exact :** Matryoshka Representation Learning
- **Auteurs :** Aditya Kusupati, Gantavya Bhatt, Aniket Rege, Matthew Wallingford, Aditya Sinha, Vivek Ramanujan, William Howard-Snyder, Kaifeng Chen, Sham Kakade, Prateek Jain, Ali Farhadi
- **Année / lieu :** 2022, *Advances in Neural Information Processing Systems 35* (NeurIPS 2022)
- **URL :** https://proceedings.neurips.cc/paper_files/paper/2022/hash/c32319f4868da7613d78af9993100e42-Abstract.html
- **Statut :** Publié (évalué par les pairs)
- **Problématique :** obtenir des représentations utilisables à plusieurs dimensions sans réentraîner.
- **Contribution au projet :** principe utilisé par l'encodeur WordLlama testé dans l'ablation des embeddings. La référence explique pourquoi un vecteur peut être tronqué.
- **Composants concernés :** `retrieval/embeddings.py`.

---

## Axe 2 — Knowledge Graphs, bases de graphes et Cypher

### [10] Hogan et al. (2021) — Knowledge Graphs
- **Titre exact :** Knowledge Graphs
- **Auteurs :** Aidan Hogan, Eva Blomqvist, Michael Cochez, Claudia d'Amato, Gerard de Melo, Claudio Gutiérrez, Sabrina Kirrane, José Emilio Labra Gayo, Roberto Navigli, Sebastian Neumaier, Axel-Cyrille Ngonga Ngomo, Axel Polleres, Sabbir M. Rashid, Anisa Rula, Lukas Schmelzeisen, Juan Sequeda, Steffen Staab, Antoine Zimmermann (liste complétée en octobre 2026 à partir du PDF éditeur et du dépôt de l'Université de Southampton)
- **Année / lieu :** 2021, *ACM Computing Surveys*, vol. 54, n° 4, article 71
- **DOI :** 10.1145/3447772
- **Statut :** Publié (évalué par les pairs, accès ouvert)
- **Problématique :** unifier les définitions et techniques autour des graphes de connaissances.
- **Méthodologie :** revue (modèles de données, langages de requête, schémas, ontologies, construction, qualité, raffinement).
- **Résultats importants :** distinction claire entre modèles RDF et graphes de propriétés ; dimensions de qualité (exactitude, couverture, cohérence, fraîcheur).
- **Limites :** antérieure à la vague LLM.
- **Contribution au projet :** définitions (nœud, relation, schéma, ontologie), critères de qualité du graphe utilisés dans l'évaluation.
- **Composants concernés :** `knowledge_graph/`, `evaluation/`.
- **Pourquoi la citer :** référence académique de base sur les KG.

### [11] Francis et al. (2018) — Cypher
- **Titre exact :** Cypher: An Evolving Query Language for Property Graphs
- **Auteurs :** Nadime Francis, Alastair Green, Paolo Guagliardo, Leonid Libkin, Tobias Lindaaker, Victor Marsault, Stefan Plantikow, Mats Rydberg, Petra Selmer, Andrés Taylor
- **Année / lieu :** 2018, *Proceedings of SIGMOD 2018*, p. 1433–1445
- **DOI :** 10.1145/3183713.3190657
- **Statut :** Publié (évalué par les pairs, *industrial track*)
- **Problématique :** formaliser le langage Cypher pour graphes de propriétés.
- **Contribution au projet :** référence académique pour le langage de requête utilisé dans tous les modules d'accès au graphe.
- **Composants concernés :** `knowledge_graph/repository.py`, `retrieval/graph.py`.

### [12] Pan et al. (2024) — LLM et KG : feuille de route
- **Titre exact :** Unifying Large Language Models and Knowledge Graphs: A Roadmap
- **Auteurs :** Shirui Pan, Linhao Luo, Yufei Wang, Chen Chen, Jiapu Wang, Xindong Wu
- **Année / lieu :** 2024, *IEEE Transactions on Knowledge and Data Engineering*, vol. 36, n° 7, p. 3580–3599
- **DOI :** 10.1109/TKDE.2024.3352100
- **Statut :** Publié (évalué par les pairs)
- **Problématique :** articuler LLM (connaissances implicites, hallucinations) et KG (connaissances explicites, incomplètes).
- **Méthodologie :** revue structurée en trois cadres : KG-enhanced LLM, LLM-augmented KG, LLM+KG synergiques.
- **Résultats importants :** complémentarité des deux approches ; défis de construction et de mise à jour des KG.
- **Limites :** feuille de route conceptuelle.
- **Contribution au projet :** positionne la plateforme dans le cadre « synergique » : le LLM aide à construire le graphe, et le graphe ancre les réponses du LLM.
- **Composants concernés :** architecture globale.

---

## Axe 3 — GraphRAG et raisonnement sur graphe

### [13] Edge et al. (2024) — GraphRAG (Microsoft)
- **Titre exact :** From Local to Global: A Graph RAG Approach to Query-Focused Summarization
- **Auteurs (v1) :** Darren Edge, Ha Trinh, Newman Cheng, Joshua Bradley, Alex Chao, Apurva Mody, Steven Truitt, Jonathan Larson. La v2 (février 2025) ajoute Dasha Metropolitansky et Robert Osazuwa Ness **[ordre exact des auteurs de la v2 à vérifier]**.
- **Année / lieu :** 2024, arXiv:2404.16130
- **URL :** https://arxiv.org/abs/2404.16130
- **Statut :** Prépublication
- **Problématique :** le RAG vectoriel échoue sur les questions « globales » portant sur l'ensemble d'un corpus (synthèse de thèmes).
- **Méthodologie :** un LLM construit un graphe d'entités, détecte des communautés (Leiden), pré-génère des résumés de communautés, puis répond par agrégation map-reduce.
- **Résultats importants :** gains d'exhaustivité et de diversité des réponses sur des corpus d'environ 1 M de tokens, par rapport à un RAG vectoriel jugé plus direct.
- **Limites :** coût élevé en appels LLM pour l'indexation ; évaluation fondée sur des jugements de LLM ; peu adapté aux questions factuelles précises.
- **Contribution au projet :** distinction entre recherche « locale » (centrée entités) et « globale ». Notre plateforme implémente la recherche locale, adaptée aux questions relationnelles. Les résumés de communautés exigent une clé LLM et restent une perspective.
- **Composants concernés :** `retrieval/graph.py`, chapitre état de l'art.

### [14] Peng et al. (2024) — Synthèse GraphRAG
- **Titre exact :** Graph Retrieval-Augmented Generation: A Survey
- **Auteurs :** Boci Peng, Yun Zhu, Yongchao Liu, Xiaohe Bo, Haizhou Shi, Chuntao Hong, Yan Zhang, Siliang Tang
- **Année / lieu :** 2024, arXiv:2408.08921 (indiqué « ongoing work »)
- **Statut :** Prépublication (aucune publication en revue confirmée)
- **Méthodologie :** formalisation en trois étapes : indexation fondée sur le graphe, récupération guidée par le graphe, génération enrichie par le graphe.
- **Contribution au projet :** structure le découpage de notre pipeline GraphRAG et du chapitre correspondant du rapport.
- **Composants concernés :** `knowledge_graph/`, `retrieval/graph.py`, `orchestration/`.

### [15] Han et al. (2025) — RAG with Graphs
- **Titre exact :** Retrieval-Augmented Generation with Graphs (GraphRAG)
- **Auteurs :** Haoyu Han, Yu Wang, Harry Shomer, Kai Guo, Jiayuan Ding, Yongjia Lei, Mahantesh Halappanavar, Ryan A. Rossi, Subhabrata Mukherjee, Xianfeng Tang, Qi He, Zhigang Hua, Bo Long, Tong Zhao, Neil Shah, Amin Javari, Yinglong Xia, Jiliang Tang
- **Année / lieu :** v1 du 31/12/2024, v2 du 08/01/2025, arXiv:2501.00309
- **Statut :** Prépublication
- **Contribution au projet :** typologie des composants GraphRAG (query processor, retriever, organizer, generator, data source), utile pour justifier notre découpage en nœuds LangGraph.

### [16] Gutiérrez et al. (2024) — HippoRAG
- **Titre exact :** HippoRAG: Neurobiologically Inspired Long-Term Memory for Large Language Models
- **Auteurs :** Bernal Jiménez Gutiérrez, Yiheng Shu, Yu Gu, Michihiro Yasunaga, Yu Su
- **Année / lieu :** 2024, *Advances in Neural Information Processing Systems 37* (NeurIPS 2024)
- **DOI :** 10.52202/079017-1902 — arXiv : 2405.14831
- **Statut :** Publié (évalué par les pairs)
- **Problématique :** intégrer efficacement des connaissances réparties dans plusieurs documents (questions multi-sauts).
- **Méthodologie :** graphe d'entités extrait par LLM, puis Personalized PageRank initialisé sur les entités de la question pour classer les passages.
- **Résultats importants :** jusqu'à 20 % d'amélioration sur des questions multi-sauts ; récupération en une étape comparable à des méthodes itératives (IRCoT) pour un coût 10 à 20 fois moindre (chiffres de la version NeurIPS).
- **Limites :** dépend de la qualité de l'extraction et de la reconnaissance des entités de la question.
- **Contribution au projet :** **inspiration directe** de notre récupération par graphe : nous propageons un Personalized PageRank sur le sous-graphe local à partir des entités reconnues dans la question.
- **Composants concernés :** `retrieval/graph.py`.

### [17] Sun et al. (2024) — Think-on-Graph
- **Titre exact :** Think-on-Graph: Deep and Responsible Reasoning of Large Language Model on Knowledge Graph
- **Auteurs :** Jiashuo Sun, Chengjin Xu, Lumingyuan Tang, Saizhuo Wang, Chen Lin, Yeyun Gong, Lionel Ni, Heung-Yeung Shum, Jian Guo
- **Année / lieu :** 2024, ICLR 2024 — arXiv : 2307.07697
- **Statut :** Publié (évalué par les pairs)
- **Méthodologie :** le LLM agit comme agent qui explore le KG par recherche en faisceau sur les chemins de raisonnement.
- **Résultats importants :** état de l'art sur 6 des 9 jeux évalués, sans entraînement.
- **Limites :** nombreux appels LLM par question, donc latence et coût élevés.
- **Contribution au projet :** alternative étudiée et **écartée** pour la version de base : nous préférons une exploration déterministe bornée (1 à 2 sauts), auditable et sans coût LLM. Elle reste une piste pour les questions à plus de deux sauts.

### [18] Guo et al. (2024/2025) — LightRAG
- **Titre exact :** LightRAG: Simple and Fast Retrieval-Augmented Generation
- **Auteurs :** Zirui Guo, Lianghao Xia, Yanhua Yu, Tu Ao, Chao Huang
- **Année / lieu :** arXiv:2410.05779 (2024) ; publié dans *Findings of EMNLP 2025*, p. 10746–10761
- **Statut :** Publié (évalué par les pairs) ; métadonnées de l'ACL Anthology consultées en page de prévisualisation **[pagination à revérifier]**
- **Méthodologie :** indexation par graphe d'entités et récupération à deux niveaux (entités précises et thèmes généraux) avec mise à jour incrémentale.
- **Contribution au projet :** justifie la **mise à jour incrémentale** du graphe (sans reconstruction complète) et la combinaison graphe + vecteurs.

### [19] Yang et al. (2018) — HotpotQA
- **Titre exact :** HotpotQA: A Dataset for Diverse, Explainable Multi-hop Question Answering
- **Auteurs :** Zhilin Yang, Peng Qi, Saizheng Zhang, Yoshua Bengio, William Cohen, Ruslan Salakhutdinov, Christopher D. Manning
- **Année / lieu :** 2018, *Proceedings of EMNLP 2018*, p. 2369–2380
- **DOI :** 10.18653/v1/D18-1259
- **Statut :** Publié (évalué par les pairs)
- **Contribution au projet :** notions de question multi-sauts et de *supporting facts* (faits justificatifs annotés), reprises pour construire notre jeu de questions de référence et la métrique de couverture des preuves.

---

## Axe 4 — Extraction de connaissances par LLM et construction de KG

### [20] Wadhwa, Amir & Wallace (2023) — Extraction de relations à l'ère des LLM
- **Titre exact :** Revisiting Relation Extraction in the era of Large Language Models
- **Auteurs :** Somin Wadhwa, Silvio Amir, Byron Wallace
- **Année / lieu :** 2023, *Proceedings of ACL 2023 (Long Papers)*, p. 15566–15589
- **DOI :** 10.18653/v1/2023.acl-long.868
- **Statut :** Publié (évalué par les pairs)
- **Résultats importants :** GPT-3 en *few-shot* approche les modèles supervisés ; la correspondance exacte est inadaptée à l'évaluation de sorties génératives, d'où le recours à une évaluation humaine.
- **Contribution au projet :** justifie (a) l'usage du LLM pour l'extraction de relations, (b) une évaluation par correspondance **normalisée** des entités (résolution vers des identifiants canoniques) plutôt que par chaînes exactes.
- **Composants concernés :** `extraction/llm_extractor.py`, `evaluation/extraction_eval.py`.

### [21] Xu et al. (2024) — LLM pour l'extraction d'information générative
- **Titre exact :** Large Language Models for Generative Information Extraction: A Survey
- **Auteurs :** Derong Xu, Wei Chen, Wenjun Peng, Chao Zhang, Tong Xu, Xiangyu Zhao, Xian Wu, Yefeng Zheng, Yang Wang, Enhong Chen (article 186357 du volume 18, n° 6)
- **Année / lieu :** 2024, *Frontiers of Computer Science*, vol. 18, n° 6 — arXiv : 2312.17617
- **DOI :** 10.1007/s11704-024-40555-y
- **Statut :** Publié (évalué par les pairs)
- **Contribution au projet :** panorama des techniques (prompting, sortie structurée, schéma contraint) ; appui pour le choix d'un **schéma JSON validé** en sortie du LLM.

### [22] Zhu et al. (2024) — LLM pour la construction et le raisonnement sur KG
- **Titre exact :** LLMs for Knowledge Graph Construction and Reasoning: Recent Capabilities and Future Opportunities
- **Auteurs :** Yuqi Zhu, Xiaohan Wang, Jing Chen, Shuofei Qiao, Yixin Ou, Yunzhi Yao, Shumin Deng, Huajun Chen, Ningyu Zhang (Zhejiang University, National University of Singapore)
- **Année / lieu :** arXiv:2305.13168 (v4 de décembre 2024). Publication dans la revue *World Wide Web* (2024) signalée par des sources secondaires **[à vérifier sur le site de l'éditeur]**.
- **Statut :** Prépublication confirmée ; publication en revue non vérifiée
- **Résultats importants :** GPT-4 est plus performant comme assistant d'inférence que comme extracteur *few-shot*.
- **Contribution au projet :** argument central pour **ne pas considérer l'extraction LLM comme une vérité** : validation par schéma, vérification de la citation source, résolution d'entités, score de confiance.

---

## Axe 5 — Résolution d'entités et déduplication

### [23] Christophides et al. (2020/2021) — Résolution d'entités de bout en bout
- **Titre exact :** An Overview of End-to-End Entity Resolution for Big Data
- **Auteurs :** Vassilis Christophides, Vasilis Efthymiou, Themis Palpanas, George Papadakis, Kostas Stefanidis
- **Année / lieu :** *ACM Computing Surveys*, vol. 53, n° 6, article 127 (publication en ligne en décembre 2020)
- **DOI :** 10.1145/3418896
- **Statut :** Publié (évalué par les pairs)
- **Méthodologie :** revue du pipeline : *blocking*, *matching*, *clustering*.
- **Contribution au projet :** structure notre résolveur : blocage par type d'entité, appariement en cascade (exact, alias, normalisé, flou), seuils de décision.
- **Composants concernés :** `extraction/entity_resolution.py`.

### [24] Fellegi & Sunter (1969) — Théorie du couplage d'enregistrements
- **Titre exact :** A Theory for Record Linkage
- **Auteurs :** Ivan P. Fellegi, Alan B. Sunter
- **Année / lieu :** 1969, *Journal of the American Statistical Association*, vol. 64
- **DOI :** **[non vérifié — ne pas citer de DOI sans contrôle]**
- **Statut :** Publié (évalué par les pairs)
- **Contribution au projet :** fondement des trois zones de décision (lien, non-lien, revue manuelle). Notre résolveur reprend ce principe : au-dessus du seuil haut, fusion ; entre les deux seuils, création d'une entité **candidate** à valider ; en dessous, nouvelle entité.

### [25] Broder (1997) — Ressemblance de documents (MinHash)
- **Titre exact :** On the Resemblance and Containment of Documents
- **Auteur :** Andrei Z. Broder
- **Année / lieu :** *Proceedings of Compression and Complexity of Sequences* (1997) **[année et pagination divergentes selon les sources ; DOI non vérifié]**
- **Statut :** Publié
- **Contribution au projet :** mesure de ressemblance par *shingles* et estimation MinHash, utilisée pour détecter les quasi-doublons et versions redondantes à l'ingestion.
- **Composants concernés :** `ingestion/dedup.py`.

---

## Axe 6 — Orchestration de workflows LLM, récupération itérative et auto-correction

### [26] Yao et al. (2023) — ReAct
- **Titre exact :** ReAct: Synergizing Reasoning and Acting in Language Models
- **Auteurs :** Shunyu Yao, Jeffrey Zhao, Dian Yu, Nan Du, Izhak Shafran, Karthik Narasimhan, Yuan Cao
- **Année / lieu :** 2023, ICLR 2023 — arXiv : 2210.03629
- **Statut :** Publié (évalué par les pairs)
- **Contribution au projet :** paradigme d'agent qui alterne raisonnement et actions. Nous l'avons **écarté** au profit d'un workflow à transitions explicites : celui-ci est plus prévisible, plus auditable et ne dépend pas d'un LLM pour router.

### [27] Trivedi et al. (2023) — IRCoT
- **Titre exact :** Interleaving Retrieval with Chain-of-Thought Reasoning for Knowledge-Intensive Multi-Step Questions
- **Auteurs :** Harsh Trivedi, Niranjan Balasubramanian, Tushar Khot, Ashish Sabharwal
- **Année / lieu :** 2023, *Proceedings of ACL 2023 (Long Papers)*, p. 10014–10037
- **DOI :** 10.18653/v1/2023.acl-long.557
- **Statut :** Publié (évalué par les pairs)
- **Contribution au projet :** justifie la **boucle de récupération complémentaire** : quand le contexte est insuffisant, la requête est enrichie (entités voisines) et la récupération relancée.

### [28] Asai et al. (2024) — Self-RAG
- **Titre exact :** Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection
- **Auteurs :** Akari Asai, Zeqiu Wu, Yizhong Wang, Avirup Sil, Hannaneh Hajishirzi
- **Année / lieu :** 2024, ICLR 2024 — https://openreview.net/forum?id=hSyW5go0v8
- **Statut :** Publié (évalué par les pairs)
- **Contribution au projet :** idée de critique de la pertinence du contexte et du support de la réponse. Nous l'implémentons sans réentraînement, par des nœuds de vérification explicites.

### [29] Yan et al. (2024) — Corrective RAG
- **Titre exact :** Corrective Retrieval Augmented Generation
- **Auteurs :** Shi-Qi Yan, Jia-Chen Gu, Yun Zhu, Zhen-Hua Ling
- **Année / lieu :** 2024, arXiv:2401.15884
- **Statut :** Prépublication
- **Contribution au projet :** évaluateur de qualité de la récupération déclenchant une action corrective. C'est le modèle de notre nœud `assess_context` (suffisance du contexte, puis reformulation ou abstention).

---

## Axe 7 — Explicabilité, citations, hallucinations et sécurité

### [30] Ji et al. (2023) — Hallucinations
- **Titre exact :** Survey of Hallucination in Natural Language Generation
- **Auteurs :** Ziwei Ji, Nayeon Lee, Rita Frieske, Tiezheng Yu, Dan Su, Yan Xu, Etsuko Ishii, Yejin Bang, Wenliang Dai, Andrea Madotto, Pascale Fung (HKUST ; Wenliang Dai n'apparaît qu'à partir des versions arXiv postérieures à la v3)
- **Année / lieu :** 2023, *ACM Computing Surveys*, vol. 55, n° 12, article 248 — arXiv : 2202.03629
- **DOI :** **[non confirmé par la recherche ; ne pas l'indiquer sans vérification]**
- **Statut :** Publié (évalué par les pairs)
- **Contribution au projet :** définitions (hallucination intrinsèque et extrinsèque), justification des mécanismes d'ancrage, de vérification et d'abstention.

### [31] Gao, Yen, Yu & Chen (2023) — Génération avec citations (ALCE)
- **Titre exact :** Enabling Large Language Models to Generate Text with Citations
- **Auteurs :** Tianyu Gao, Howard Yen, Jiatong Yu, Danqi Chen
- **Année / lieu :** 2023, *Proceedings of EMNLP 2023*, p. 6465–6488
- **DOI :** 10.18653/v1/2023.emnlp-main.398
- **Statut :** Publié (évalué par les pairs)
- **Résultats importants :** même les meilleurs modèles manquent de support de citation complet dans environ 50 % des cas sur ELI5.
- **Contribution au projet :** définition des métriques de **rappel et de précision des citations**, adaptées dans `evaluation/generation_eval.py`.

### [32] Liu et al. (2024) — Lost in the Middle
- **Titre exact :** Lost in the Middle: How Language Models Use Long Contexts
- **Auteurs :** Nelson F. Liu, Kevin Lin, John Hewitt, Ashwin Paranjape, Michele Bevilacqua, Fabio Petroni, Percy Liang
- **Année / lieu :** 2024, *Transactions of the ACL*, vol. 12, p. 157–173
- **DOI :** 10.1162/tacl_a_00638
- **Statut :** Publié (évalué par les pairs)
- **Contribution au projet :** justifie de **limiter la taille du contexte** et de placer les éléments les plus pertinents en tête du prompt.

### [33] Greshake et al. (2023) — Injection indirecte de prompt
- **Titre exact :** Not what you've signed up for: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection
- **Auteurs :** Kai Greshake, Sahar Abdelnabi, Shailesh Mishra, Christoph Endres, Thorsten Holz, Mario Fritz
- **Année / lieu :** arXiv:2302.12173 (2023). Présenté à l'atelier AISec 2023 (ACM CCS) selon plusieurs sources **[DOI ACM non vérifié]**.
- **Statut :** Prépublication confirmée ; version d'atelier à vérifier
- **Contribution au projet :** modèle de menace central. Un document ingéré peut contenir des instructions malveillantes. D'où la détection à l'ingestion, l'isolement du contenu documentaire dans le prompt, l'absence d'outils exécutables par le LLM et le filtrage des liens sortants.
- **Composants concernés :** `ingestion/security.py`, `orchestration/prompts.py`, `orchestration/verification.py`.

---

## Axe 8 — Recherche d'experts et recommandation

### [34] Balog, Azzopardi & de Rijke (2006) — Recherche d'experts
- **Titre exact :** Formal Models for Expert Finding in Enterprise Corpora
- **Auteurs :** Krisztian Balog, Leif Azzopardi, Maarten de Rijke
- **Année / lieu :** 2006, *Proceedings of SIGIR 2006*, p. 43–50
- **DOI :** 10.1145/1148170.1148181
- **Statut :** Publié (évalué par les pairs)
- **Résultats importants :** sur TREC Enterprise, l'approche « centrée documents » (Model 2) surpasse la modélisation directe des candidats.
- **Contribution au projet :** notre score d'expertise est centré documents : il agrège des preuves documentaires typées, pondérées et datées.
- **Composants concernés :** `expert_discovery/`.

### [35] Balog et al. (2012) — Expertise Retrieval
- **Titre exact :** Expertise Retrieval
- **Auteurs :** Krisztian Balog, Yi Fang, Maarten de Rijke, Pavel Serdyukov, Luo Si
- **Année / lieu :** 2012, *Foundations and Trends in Information Retrieval*, vol. 6, n° 2–3, p. 127–256
- **DOI :** 10.1561/1500000024
- **Statut :** Publié (monographie évaluée)
- **Contribution au projet :** cadre conceptuel (preuves d'expertise, profils, évaluation) et discussion des enjeux éthiques et de confidentialité.

### [36] Guo et al. (2022) — Recommandation fondée sur les KG
- **Titre exact :** A Survey on Knowledge Graph-Based Recommender Systems
- **Auteurs :** Qingyu Guo, Fuzhen Zhuang, Chuan Qin, Hengshu Zhu, Xing Xie, Hui Xiong, Qing He
- **Année / lieu :** *IEEE Transactions on Knowledge and Data Engineering* (en ligne en 2020, numéro d'août 2022) — arXiv : 2003.00911
- **DOI :** 10.1109/TKDE.2020.3028705
- **Statut :** Publié (évalué par les pairs)
- **Contribution au projet :** typologie (méthodes fondées sur les embeddings, sur les connexions/chemins, sur la propagation) ; le graphe de connaissances y est présenté comme un moyen d'atténuer la rareté des données, le démarrage à froid et de **rendre les recommandations explicables** ; justification de notre score hybride contenu + chemins du graphe, dont les chemins fournissent l'explication des recommandations.
- **Composants concernés :** `recommendations/`.

---

## Axe 9 — Évaluation des systèmes RAG / GraphRAG

### [37] Järvelin & Kekäläinen (2002) — nDCG
- **Titre exact :** Cumulated Gain-Based Evaluation of IR Techniques
- **Auteurs :** Kalervo Järvelin, Jaana Kekäläinen
- **Année / lieu :** 2002, *ACM Transactions on Information Systems*, vol. 20, n° 4, p. 422–446
- **DOI :** 10.1145/582415.582418
- **Statut :** Publié (évalué par les pairs)
- **Contribution au projet :** définition de nDCG@k, utilisée pour les évaluations de récupération, d'experts et de recommandation.

### [38] Es et al. (2024) — RAGAS
- **Titre exact :** RAGAs: Automated Evaluation of Retrieval Augmented Generation
- **Auteurs :** Shahul Es, Jithin James, Luis Espinosa Anke, Steven Schockaert
- **Année / lieu :** 2024, *Proceedings of EACL 2024: System Demonstrations*, p. 150–158
- **URL :** https://aclanthology.org/2024.eacl-demo.16
- **Statut :** Publié (évalué par les pairs, démonstration)
- **Contribution au projet :** dimensions d'évaluation (fidélité, pertinence de la réponse, pertinence du contexte). Comme RAGAS repose sur un LLM juge, nous séparons les mesures automatiques déterministes des mesures produites par un LLM.

### [39] Yu et al. (2024) — Évaluation du RAG
- **Titre exact :** Evaluation of Retrieval-Augmented Generation: A Survey
- **Auteurs :** Hao Yu, Aoran Gan, Kai Zhang, Shiwei Tong, Qi Liu, Zhaofeng Liu
- **Année / lieu :** 2024, arXiv:2405.07437 (une parution dans *Communications in Computer and Information Science* est signalée par une source secondaire **[à vérifier]**)
- **Statut :** Prépublication confirmée
- **Contribution au projet :** grille d'évaluation séparant récupération et génération ; inventaire des métriques.

### [40] Zheng et al. (2023) — LLM-as-a-Judge
- **Titre exact :** Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena
- **Auteurs :** Lianmin Zheng, Wei-Lin Chiang, Ying Sheng, Siyuan Zhuang, Zhanghao Wu, Yonghao Zhuang, Zi Lin, Zhuohan Li, Dacheng Li, Eric P. Xing, Hao Zhang, Joseph E. Gonzalez, Ion Stoica
- **Année / lieu :** 2023, NeurIPS 2023, *Datasets and Benchmarks Track*
- **URL :** https://proceedings.neurips.cc/paper_files/paper/2023/hash/91f18a1287b398d378ef22505bf41832-Abstract.html
- **Statut :** Publié (évalué par les pairs)
- **Résultats importants :** accord supérieur à 80 % avec les préférences humaines, mais biais de position, de verbosité et d'auto-préférence.
- **Contribution au projet :** justifie de **ne pas confondre** jugement par LLM et exactitude vérifiée ; le juge LLM reste optionnel et ses résultats sont étiquetés comme tels.

---

## Axe 10 — OCR et compréhension documentaire

### [41] Smith (2007) — Tesseract
- **Titre exact :** An Overview of the Tesseract OCR Engine
- **Auteur :** Ray Smith
- **Année / lieu :** 2007, *Ninth International Conference on Document Analysis and Recognition (ICDAR 2007)*, p. 629–633
- **DOI :** 10.1109/ICDAR.2007.4376991
- **Statut :** Publié (évalué par les pairs)
- **Contribution au projet :** référence du moteur OCR utilisé (Tesseract 5.3.4, modèles `fra` et `eng`).
- **Composants concernés :** `ingestion/ocr.py`.

### [42] Xu et al. (2020) — LayoutLM
- **Titre exact :** LayoutLM: Pre-training of Text and Layout for Document Image Understanding
- **Auteurs :** Yiheng Xu, Minghao Li, Lei Cui, Shaohan Huang, Furu Wei, Ming Zhou
- **Année / lieu :** 2020, *Proceedings of KDD 2020*, p. 1192–1200
- **DOI :** 10.1145/3394486.3403172
- **Statut :** Publié (évalué par les pairs)
- **Contribution au projet :** alternative étudiée à l'OCR « texte seul » pour les formulaires et tableaux. Elle est écartée (modèle lourd, téléchargement impossible dans l'environnement) et proposée en perspective.

---

## Documentation officielle (sources professionnelles, non scientifiques)

| Réf. | Source | Usage dans le projet |
|---|---|---|
| [D1] | Neo4j — *Cypher Manual 5*, « Vector indexes » : https://neo4j.com/docs/cypher-manual/5/indexes/semantic-indexes/vector-indexes/ | Création et interrogation de l'index vectoriel (HNSW). Disponibilité en édition Community **vérifiée expérimentalement** sur Neo4j 5.26.31 Community (voir `DETAILS/KNOWLEDGE_GRAPH_NEO4J.txt`). |
| [D2] | Neo4j — *Cypher Manual 5*, « Full-text indexes » : https://neo4j.com/docs/cypher-manual/5/indexes/semantic-indexes/full-text-indexes/ | Index plein texte Lucene ; analyseur `french`. La documentation recommande de classer séparément les résultats plein texte et vectoriels avant de les combiner, d'où notre fusion par rangs (RRF). |
| [D3] | LangChain — référence API LangGraph, `StateGraph.add_conditional_edges` : https://reference.langchain.com/python/langgraph/graph/state/StateGraph/add_conditional_edges | Construction du workflow à transitions conditionnelles. |
| [D4] | Tesseract OCR — documentation : https://tesseract-ocr.github.io/ | Paramétrage OCR (langues, modes de segmentation). |
| [D5] | spaCy — modèle `fr_core_news_md` 3.8.0 (Explosion), distribué sur PyPI | Lemmatisation, NER (PER, ORG) et vecteurs de mots français (300 dimensions). |
| [D6] | WordLlama (D. Lee Miller), paquet PyPI `wordllama` 0.4.0 | Encodeur statique hors-ligne testé dans l'ablation des embeddings. |
