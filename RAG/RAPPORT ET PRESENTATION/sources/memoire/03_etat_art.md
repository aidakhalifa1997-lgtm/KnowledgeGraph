# État de l'art

Ce chapitre présente les travaux sur lesquels s'appuie notre solution. Nous partons de la recherche d'information classique et de la génération augmentée par la recherche, puis nous abordons les graphes de connaissances, leur construction à partir de textes et leur usage dans les approches dites GraphRAG. Nous traitons ensuite de l'orchestration, de la fiabilité et de la sécurité des systèmes qui associent recherche et modèles de langage, avant d'évoquer la recherche d'experts et la recommandation. Une synthèse comparative permet enfin de positionner notre travail.

## Gestion des connaissances et recherche d'information

La gestion des connaissances vise à rendre mobilisable un savoir dispersé entre des documents et des personnes. Du point de vue technique, elle repose d'abord sur la recherche d'information : retrouver, dans une collection, les documents ou passages pertinents pour un besoin exprimé. Deux grandes familles de méthodes coexistent.

La recherche **lexicale** compare les mots de la requête à ceux des documents. Sa forme la plus utilisée, BM25, pondère chaque terme selon sa fréquence dans le document et sa rareté dans la collection, avec une saturation qui évite qu'un terme répété ne domine le score (Robertson et Zaragoza, 2009). Elle est rapide, explicable et particulièrement efficace lorsque la requête contient des termes exacts : codes de procédure, noms d'applications, sigles.

La recherche **dense** représente requêtes et passages par des vecteurs, appelés plongements (*embeddings*), de sorte que des textes de sens voisin soient proches dans l'espace vectoriel. Les travaux de Karpukhin et al. (2020) sur la recherche dense de passages et ceux de Reimers et Gurevych (2019) sur les encodeurs de phrases ont montré que cette approche capte des paraphrases que la recherche lexicale manque. Elle repose en pratique sur des index de recherche approximative du plus proche voisin, dont HNSW, structure de graphes hiérarchiques à petits mondes navigables, est l'une des plus répandues (Malkov et Yashunin, 2020).

La supériorité de la recherche dense n'est cependant pas générale. Le banc d'essai BEIR a montré que des modèles denses entraînés sur un domaine ne généralisent pas toujours mieux que BM25 sur d'autres domaines (Thakur et al., 2021). Ce constat est important pour un corpus d'entreprise, dont le vocabulaire spécialisé est absent des données d'entraînement des encodeurs. Il justifie le recours à une recherche **hybride**, qui combine les deux signaux. La fusion par rang réciproque (*Reciprocal Rank Fusion*, RRF) en est la méthode la plus simple : chaque document reçoit la somme, sur les classements où il apparaît, de l'inverse de son rang augmenté d'une constante, fixée à 60 par ses auteurs (Cormack et al., 2009). Elle a l'avantage de ne pas exiger de rendre comparables des scores de natures différentes.

## La génération augmentée par la recherche

Lewis et al. (2020) ont introduit le terme RAG pour désigner l'association d'une mémoire non paramétrique, un index de passages, et d'un générateur. Le modèle répond à partir des passages récupérés, ce qui permet de mettre à jour les connaissances sans réentraînement et de citer des sources. Les synthèses ultérieures distinguent un RAG « naïf », qui récupère puis génère, de variantes « avancées » ou « modulaires » qui ajoutent des étapes : reformulation de la requête, fusion de plusieurs recherches, réordonnancement, vérification (Y. Gao et al., 2023).

Le RAG reste limité par la qualité de la récupération : si les passages pertinents ne sont pas retrouvés, le générateur ne peut que s'abstenir ou extrapoler. Il traite aussi mal les questions dont la réponse exige de relier plusieurs passages, par exemple « quelles applications seraient affectées par l'indisponibilité du système central, et qui en est responsable ? ». Le jeu de données HotpotQA a mis en évidence ces questions multi-sauts et l'intérêt d'annoter les « faits justificatifs » nécessaires à la réponse (Yang et al., 2018), idée que nous reprenons dans notre banc d'essai.

## Graphes de connaissances et bases de graphes

Un graphe de connaissances représente des entités (personnes, organisations, systèmes, concepts) et les relations typées qui les relient. Hogan et al. (2021) en proposent une synthèse : modèles de données, langages de requête, ontologies, raisonnement et qualité. Deux modèles dominent. Le modèle RDF décrit le graphe sous forme de triplets et s'appuie sur des standards du Web sémantique. Le modèle de **graphe de propriétés**, utilisé par Neo4j, attache des propriétés aux nœuds comme aux relations, ce qui facilite le stockage d'informations sur une relation elle-même, comme sa provenance ou sa confiance.

Le langage Cypher, formalisé par Francis et al. (2018), décrit les requêtes par des motifs visuels de nœuds et de relations. Il se prête bien aux parcours de voisinage et aux chemins de longueur variable. La documentation de Neo4j décrit par ailleurs des index plein texte fondés sur Lucene, avec des analyseurs par langue, et des index vectoriels de type HNSW, disponibles dans l'édition Community. Une même base peut ainsi porter le graphe, la recherche lexicale et la recherche vectorielle, ce que nous avons vérifié empiriquement sur la version 5.26.

## Construire un graphe de connaissances à partir de textes

### Extraction d'entités et de relations

La construction d'un graphe à partir de documents passe par la reconnaissance des entités, l'extraction des relations entre elles et la résolution des entités, qui rattache des mentions différentes (« Mme Idrissi », « S. Idrissi ») à une même entité canonique.

Les grands modèles de langage ont renouvelé l'extraction de relations. Wadhwa et al. (2023) montrent qu'ils sont compétitifs en apprentissage à partir de quelques exemples, mais soulignent que l'évaluation par correspondance exacte est mal adaptée à des sorties génératives. D. Xu et al. (2024) dressent un panorama de l'extraction d'information générative. Zhu et al. (2024) observent qu'un modèle comme GPT-4 est plus performant comme assistant d'inférence que comme extracteur à partir de quelques exemples. Pan et al. (2024) proposent une feuille de route pour unifier modèles de langage et graphes : les graphes apportent aux LLM des faits structurés et vérifiables, les LLM aident à construire et à interroger les graphes.

Ces travaux convergent vers une recommandation de prudence : la sortie d'un LLM doit être contrainte (schéma, ontologie) et vérifiée avant d'entrer dans un graphe destiné à servir de référence.

### Résolution d'entités et dédoublonnage

La résolution d'entités suit classiquement un enchaînement de blocage, de comparaison et de regroupement (Christophides et al., 2021). Le modèle de Fellegi et Sunter (1969), fondateur du couplage d'enregistrements, formalise trois zones de décision : lien, non-lien et revue humaine, selon que le score de similarité dépasse un seuil haut, reste sous un seuil bas ou se situe entre les deux.

Le dédoublonnage de documents relève d'une problématique voisine. Broder (1997) a proposé d'estimer la ressemblance entre deux documents par la similarité de Jaccard de leurs ensembles de fragments (*shingles*), approximée efficacement par des signatures MinHash. Cette technique permet de repérer des quasi-doublons, comme une copie de travail légèrement modifiée d'une procédure.

### Documents numérisés

Une partie de la documentation d'entreprise n'existe qu'en version scannée. La reconnaissance optique de caractères Tesseract, dont Smith (2007) décrit l'architecture, reste une référence libre. Des modèles plus récents exploitent conjointement le texte et la mise en page (Y. Xu et al., 2020), mais leur coût et leur dépendance à des modèles pré-entraînés dépassent le besoin d'un corpus où les documents scannés sont l'exception.

## GraphRAG : apports et limites

Les synthèses récentes décrivent GraphRAG en trois temps : indexation fondée sur un graphe, récupération guidée par le graphe et génération enrichie par le graphe (Peng et al., 2024 ; Han et al., 2025). Trois familles d'approches se dégagent.

**Le résumé global par communautés.** Le GraphRAG de Microsoft construit un graphe d'entités avec un LLM, le partitionne en communautés et rédige un résumé de chacune (Edge et al., 2024). Il répond bien aux questions globales sur un corpus, comme les thèmes dominants, mais l'indexation exige de nombreux appels au LLM. Ses auteurs évaluent surtout la qualité des réponses par des jugements produits par des LLM et reconnaissent que le RAG vectoriel donne des réponses plus directes.

**La propagation sur le graphe d'entités.** HippoRAG reconnaît les entités de la question, puis applique un PageRank personnalisé, c'est-à-dire une marche aléatoire qui revient régulièrement vers ces entités, pour classer les entités voisines et les passages qui les mentionnent (Gutiérrez et al., 2024). L'approche est peu coûteuse au moment de la requête et adaptée aux questions multi-sauts.

**L'exploration pilotée par un LLM.** Think-on-Graph fait parcourir le graphe pas à pas par un LLM, qui choisit les relations à suivre (Sun et al., 2024). C'est l'approche la plus souple, mais aussi la plus coûteuse et la moins déterministe.

LightRAG combine indexation par graphe et recherche vectorielle et insiste sur la mise à jour incrémentale de l'index (Z. Guo et al., 2025), point essentiel lorsque les documents évoluent.

Aucun de ces travaux ne montre une supériorité de GraphRAG sur tous les types de questions. Pour une question factuelle dont la réponse tient dans un passage, le graphe n'apporte a priori rien et peut ajouter du bruit. Cette observation fonde le choix d'un **routage** des questions, que nous présentons au chapitre 4.

## Orchestration : workflow explicite ou agent

Les systèmes récents ne se limitent plus à une recherche suivie d'une génération. ReAct fait alterner raisonnement et appels d'outils par le modèle (Yao et al., 2023). IRCoT entrelace récupération et raisonnement pour les questions en plusieurs étapes (Trivedi et al., 2023). Self-RAG apprend au modèle à décider quand récupérer et à critiquer ses propres sorties (Asai et al., 2024). Corrective RAG ajoute un évaluateur de la qualité des documents récupérés, qui déclenche une action corrective lorsque celle-ci est insuffisante (Yan et al., 2024).

Ces approches posent une question de conception : faut-il laisser le modèle piloter le déroulement, comme dans un agent, ou fixer ce déroulement dans un workflow explicite ? Un agent est plus souple, mais ses parcours varient d'une exécution à l'autre et multiplient les appels au modèle. Un workflow explicite, dont les transitions sont décidées par du code, est plus prévisible et plus facile à auditer. Les bibliothèques comme LangGraph permettent de déclarer de tels workflows sous forme de graphes d'états, avec des transitions conditionnelles. Pour un usage bancaire, où la reproductibilité et l'auditabilité priment, nous privilégions la seconde option, en reprenant l'idée d'une évaluation corrective de la récupération.

## Fiabilité : hallucinations, citations et abstention

Ji et al. (2023) distinguent les hallucinations intrinsèques, qui contredisent la source, des hallucinations extrinsèques, qui ajoutent une information invérifiable. Pour les réduire, la génération avec citations oblige le modèle à rattacher chaque affirmation à un passage. Le banc d'essai ALCE mesure la qualité des citations par leur rappel, chaque affirmation étant-elle soutenue, et leur précision, chaque citation étant-elle utile (T. Gao et al., 2023). Il montre que même les meilleurs modèles laissent de nombreuses affirmations sans soutien.

La place de l'information dans le contexte compte également : les modèles exploitent moins bien les informations situées au milieu d'un contexte long (Liu et al., 2024). Il est donc préférable de limiter le contexte et de placer les éléments les plus pertinents en tête.

L'évaluation des systèmes RAG a fait l'objet de nombreux travaux. RAGAS propose des métriques sans référence, comme la fidélité de la réponse au contexte, calculées à l'aide d'un LLM (Es et al., 2024). Yu et al. (2024) recensent les approches d'évaluation et soulignent la difficulté de mesurer séparément récupération et génération. L'usage d'un LLM comme juge est répandu, mais présente des biais documentés, comme la préférence pour les réponses longues ou pour la première réponse présentée (Zheng et al., 2023). Les métriques classiques de recherche d'information restent pertinentes pour évaluer la récupération, en particulier le nDCG, qui tient compte de la pertinence graduée et de la position des documents (Järvelin et Kekäläinen, 2002).

## Sécurité des systèmes associant recherche et LLM

Greshake et al. (2023) ont montré qu'un document contenant des instructions pouvait détourner une application intégrant un LLM : c'est l'injection indirecte de prompt. Le document n'a pas besoin d'être fourni par l'utilisateur ; il suffit qu'il soit récupéré et placé dans le contexte. Les conséquences vont de la manipulation de la réponse à l'exfiltration d'informations, par exemple au moyen d'une image dont l'adresse contient des données.

Pour un assistant documentaire, cette menace s'ajoute à une exigence plus classique : le contrôle d'accès. Si un passage non autorisé entre dans le contexte du modèle, aucune consigne ne garantit qu'il n'en restera rien dans la réponse. Le filtrage doit donc intervenir avant la récupération, et non après la génération.

## Recherche d'experts et recommandation

La recherche d'experts consiste à classer des personnes selon leur compétence sur un sujet, à partir des documents qui les associent à ce sujet. Balog et al. (2006) ont montré que les approches centrées sur les documents, qui agrègent les preuves documentaires associées à chaque candidat, sont plus efficaces que la modélisation directe des candidats. Leur synthèse ultérieure souligne aussi les enjeux de confidentialité propres à cet usage (Balog et al., 2012).

Les systèmes de recommandation fondés sur des graphes de connaissances combinent plongements, chemins et propagation dans le graphe (Q. Guo et al., 2022). Les chemins ont l'avantage de fournir une explication : un document est recommandé parce qu'il porte sur la même procédure, cite la même application ou en constitue une version antérieure.

## Synthèse et positionnement

Le tableau suivant résume les approches étudiées et leur intérêt pour notre contexte.

| Approche | Forces | Limites | Intérêt pour notre contexte |
|---|---|---|---|
| Recherche lexicale (BM25) | rapide, explicable, termes exacts | paraphrases mal traitées | forte : vocabulaire spécialisé, codes |
| Recherche dense | sens, paraphrases | dépend de l'encodeur et du domaine | moyenne, conditionnée à l'encodeur disponible |
| Hybride avec fusion RRF | robuste, sans calibration des scores | un signal isolé peut être noyé | forte : socle de la récupération |
| GraphRAG global (communautés) | questions globales | coût d'indexation élevé, LLM requis | faible pour des questions ciblées |
| GraphRAG local (PageRank personnalisé) | multi-sauts, peu coûteux à la requête | dépend de la qualité du graphe | forte : questions relationnelles |
| Exploration par LLM | souplesse | coût, non-déterminisme | faible : auditabilité |
| Workflow explicite avec évaluation corrective | contrôle, traçabilité | moins souple qu'un agent | forte : contexte régulé |
| Génération avec citations et vérification | traçabilité des réponses | ne garantit pas la justesse | indispensable |

Table: Synthèse des approches et intérêt pour le contexte bancaire

Notre travail se situe à l'intersection de ces approches. Il ne propose pas un nouvel algorithme, mais une **architecture contrôlée et évaluée** qui réunit des éléments souvent étudiés séparément : une recherche hybride, un GraphRAG local inspiré de HippoRAG, un contrôle de suffisance inspiré de Corrective RAG, des citations vérifiées et une abstention motivée, le tout soumis à un contrôle d'accès appliqué en amont de la récupération et à une provenance systématique des faits du graphe. Sa seconde originalité tient au banc d'essai : un corpus bancaire synthétique en français, conçu pour reproduire les difficultés observées en pratique, et un protocole qui distingue les questions utilisées pendant la mise au point de celles qui ne l'ont jamais été.
