# Synthèse critique de la littérature et implications pour l'architecture

Les références entre crochets renvoient à `BIBLIOGRAPHIE.md`. Ce document distingue explicitement :
**(L)** ce qui relève de la littérature, **(M)** ce qui relève de notre méthodologie, **(D)** les décisions de conception
qui en découlent.

---

## 1. Du RAG classique au RAG hybride

**(L)** Le RAG [1] associe une mémoire non paramétrique (un index de passages) à un générateur. Cela permet de mettre
à jour les connaissances sans réentraîner le modèle et de citer des sources. Les synthèses récentes [2] distinguent un
RAG « naïf » (récupérer puis générer) d'un RAG « avancé » ou « modulaire », qui ajoute des étapes de pré- et
post-traitement : reformulation, fusion, réordonnancement, vérification.

**(L)** La récupération dense [3], [4] capte les paraphrases, mais BEIR [6] montre qu'elle ne généralise pas toujours
mieux que BM25 [5] hors de son domaine d'entraînement. Ce point est crucial pour un corpus d'entreprise : le
vocabulaire spécialisé (codes `PRC-KYC-001`, noms d'applications internes, acronymes) est par nature absent des
données d'entraînement des encodeurs. La fusion de classements par RRF [7] est une méthode simple et robuste pour
combiner des signaux dont les scores ne sont pas comparables. La documentation de Neo4j [D2] recommande d'ailleurs de
classer séparément les résultats plein texte et vectoriels avant de les combiner.

**(D)** Le RAG hybride de la plateforme combine BM25 (index Lucene de Neo4j, analyseur français) et recherche
vectorielle (index HNSW de Neo4j [8]). La fusion se fait par RRF avec k = 60, la valeur de [7].

**Point critique sur les embeddings.** **(M)** L'environnement de développement n'autorise pas le téléchargement de
modèles depuis HuggingFace. Nous avons donc comparé deux encodeurs **hors-ligne** installables depuis PyPI : les
vecteurs de mots français de spaCy `fr_core_news_md` (moyenne pondérée) et l'encodeur statique WordLlama ([9], [D6]).
Ces encodeurs sont nettement moins performants que des modèles de phrases récents ([4]). **Toute conclusion sur la
supériorité du graphe sur le RAG vectoriel est donc conditionnelle à cet encodeur** et doit être réévaluée avec un
encodeur multilingue neuronal (voir protocole dans `DETAILS/TESTS_ET_EVALUATION.txt`).

---

## 2. GraphRAG : ce que le graphe apporte, et ce qu'il n'apporte pas

**(L)** Les synthèses [14], [15] décrivent GraphRAG en trois temps : indexation fondée sur le graphe, récupération
guidée par le graphe, génération enrichie par le graphe. Trois familles se dégagent :

1. **Résumé global par communautés** (GraphRAG de Microsoft [13]). Il est efficace pour les questions « globales »
   (« quels sont les thèmes du corpus ? ») mais très coûteux en appels LLM à l'indexation. Ses auteurs le comparent
   au RAG vectoriel surtout par des jugements de LLM.
2. **Propagation sur le graphe d'entités** (HippoRAG [16]). Un Personalized PageRank initialisé sur les entités de la
   question classe les passages. Cette approche est efficace pour les questions multi-sauts et peu coûteuse à la
   requête.
3. **Exploration pilotée par un LLM** (Think-on-Graph [17]). C'est la plus flexible, mais aussi la plus coûteuse et la
   moins déterministe.

LightRAG [18] combine indexation par graphe et vecteurs et insiste sur la **mise à jour incrémentale**.

**(L)** Aucun de ces travaux ne montre que GraphRAG est supérieur pour **tous** les types de questions. [13] note
lui-même que le RAG vectoriel produit des réponses plus « directes ». Sur les questions factuelles simples, dont la
réponse tient dans un seul passage, le graphe n'apporte a priori rien et peut ajouter du bruit.

**(D)** Nous retenons une **récupération locale centrée entités**, inspirée de [16] :
- reconnaissance des entités de la question (*entity linking*) vers les nœuds canoniques du graphe ;
- expansion bornée (au plus 2 sauts) le long de relations typées ;
- Personalized PageRank sur ce sous-graphe local pour classer entités et passages ;
- priorité aux **passages qui prouvent les relations parcourues** (provenance).

Le résumé global par communautés [13] est écarté pour la version de base. Il exige une clé LLM pour l'indexation, et
nos besoins métier portent sur des questions relationnelles plutôt que sur des synthèses de corpus. Il est présenté
comme perspective.

**(D)** Le **routage par type de question** est un choix structurant : le système ne doit pas appliquer le graphe
systématiquement. Le classifieur de questions oriente les questions factuelles vers le RAG hybride, et les questions
relationnelles ou multi-sauts vers la combinaison hybride + graphe.

---

## 3. Construire un graphe fiable avec un LLM

**(L)** Les LLM sont des extracteurs de relations compétitifs en *few-shot* [20], [21], mais [22] observe que GPT-4
est meilleur comme assistant d'inférence que comme extracteur *few-shot*. [20] montre également que l'évaluation par
correspondance exacte est inadaptée aux sorties génératives.

**(L)** La résolution d'entités suit classiquement un pipeline *blocking → matching → clustering* [23]. Le modèle de
Fellegi-Sunter [24] formalise trois zones de décision : lien, non-lien, revue humaine.

**(D)** Dans la plateforme :
- **Le LLM n'est jamais une source de vérité.** Sa sortie est contrainte par un schéma JSON (types d'entités, types de
  relations, contraintes domaine/codomaine) et validée par Pydantic.
- Chaque relation extraite doit être accompagnée d'une **citation textuelle**. Cette citation est vérifiée dans le
  passage source ; sinon, la relation est rejetée.
- Les entités sont résolues vers un **référentiel maître** (annuaire, cartographie applicative, portefeuille de projets,
  catalogue de procédures), comme dans un système d'information bancaire réel. Une entité inconnue est créée avec le
  statut `candidate` (zone de revue de [24]) et non `validated`.
- Un **extracteur déterministe** (dictionnaire d'alias + règles de déclenchement en français) garantit un
  fonctionnement hors-ligne reproductible. Il sert aussi de baseline mesurable.

**Point critique.** **(M)** Le corpus de démonstration, les annotations de référence et les règles de l'extracteur
déterministe ont été conçus par la même personne. Les scores d'extraction obtenus sont donc **optimistes** et
**non généralisables**. Ils valident le bon fonctionnement de la chaîne, pas une performance sur des documents réels.

---

## 4. Orchestration : workflow explicite plutôt qu'agent libre

**(L)** ReAct [26] popularise les agents qui alternent raisonnement et appels d'outils. IRCoT [27] montre l'intérêt
d'entrelacer récupération et raisonnement pour les questions multi-étapes. Self-RAG [28] et CRAG [29] introduisent une
**critique de la récupération** qui déclenche une action corrective.

**(D)** Nous utilisons LangGraph [D3] pour un **workflow explicite** plutôt qu'un agent libre. Ce choix offre :
- un état partagé typé et inspectable ;
- des transitions conditionnelles déterministes (routage par type de question, boucle de récupération complémentaire
  bornée à une itération) ;
- une trace complète de l'exécution, réutilisable pour l'explicabilité et l'audit ;
- un comportement identique avec ou sans LLM : les nœuds qui appellent le LLM disposent d'une implémentation de repli.

Un agent ReAct aurait multiplié les appels LLM et rendu le parcours non reproductible. Ce serait incompatible avec
une exigence d'auditabilité bancaire.

---

## 5. Explicabilité, citations et hallucinations

**(L)** Les hallucinations [30] sont intrinsèques (contradiction avec la source) ou extrinsèques (ajout non
vérifiable). ALCE [31] mesure la qualité des citations par leur rappel (chaque affirmation est-elle soutenue ?) et
leur précision (chaque citation est-elle utile ?). Il montre que même les meilleurs modèles échouent souvent. [32]
montre que les LLM exploitent mal l'information placée au milieu de contextes longs.

**(D)**
- Le contexte est **borné** (budget en caractères) et ordonné par pertinence décroissante.
- Le prompt impose des citations `[C1]…[Cn]` pour les passages et `[F1]…[Fn]` pour les faits du graphe. Le nœud de
  vérification **supprime les citations inexistantes**, signale les phrases sans support et déclenche l'abstention si
  aucune affirmation n'est soutenue.
- Les **chemins du graphe affichés** à l'utilisateur sont exactement ceux récupérés pendant l'exécution, avec leurs
  passages sources. Ils ne sont jamais reconstruits a posteriori.

---

## 6. Sécurité : l'injection indirecte comme menace de premier rang

**(L)** [33] démontre qu'un document contenant des instructions peut détourner une application intégrant un LLM
(exfiltration, manipulation de la réponse).

**(D)** Nous mettons en place une défense en profondeur :
1. **détection à l'ingestion** de motifs d'injection (le passage est marqué `quarantined` et exclu du contexte) ;
2. **délimitation stricte** des données documentaires dans le prompt, avec une instruction système précisant que le
   contenu documentaire n'est jamais une instruction ;
3. **aucun outil exécutable** confié au LLM ;
4. **filtrage des liens et images** dans la réponse, vecteur classique d'exfiltration ;
5. **contrôle d'accès appliqué avant la récupération** : un passage non autorisé n'entre jamais dans le contexte du
   LLM.

---

## 7. Experts et recommandations

**(L)** En recherche d'experts, l'approche centrée documents surpasse la modélisation directe des candidats [34]. Les
travaux de synthèse [35] soulignent les enjeux de confidentialité. Les recommandations fondées sur les KG combinent
embeddings, chemins et propagation [36], et les chemins fournissent une **explication**.

**(D)**
- Score d'expertise : somme pondérée de **preuves typées** (expertise déclarée, rôle dans un projet du domaine, rôle
  de propriétaire de procédure, contribution, simple mention plafonnée). La pondération décroît avec l'ancienneté de la
  preuve. **Une simple mention n'est jamais suffisante** pour être classé expert.
- Recommandation : combinaison linéaire de la similarité de contenu, du recouvrement de concepts et systèmes
  (Jaccard) et de la proximité dans le graphe (personnes et projets partagés). Chaque recommandation est accompagnée de
  ses raisons.
- Les deux fonctions sont comparées à des baselines naïves (comptage de mentions ; similarité sémantique seule).

---

## 8. Questions de recherche et hypothèses

| # | Question de recherche | Hypothèse | Mesure |
|---|---|---|---|
| QR1 | La récupération guidée par le graphe améliore-t-elle la récupération des documents justificatifs pour les questions relationnelles et multi-sauts ? | H1 : l'approche hybride + graphe obtient un Recall@5 et un nDCG@5 supérieurs au RAG vectoriel et au RAG hybride sur ces catégories. | Recall@k, nDCG@k, MRR par catégorie |
| QR2 | Le graphe dégrade-t-il les questions factuelles simples ? | H2 : avec routage, l'approche finale n'est pas inférieure au RAG hybride sur les questions factuelles. | Écart de Recall@5 et MRR |
| QR3 | Le mécanisme de suffisance permet-il de s'abstenir à bon escient ? | H3 : le taux d'abstention correcte sur les questions sans réponse est élevé, avec un taux de fausses abstentions faible sur les questions répondables. | Précision et rappel de l'abstention |
| QR4 | Un score d'expertise multi-preuves est-il plus pertinent qu'un comptage de mentions ? | H4 : nDCG@3 supérieur à la baseline « mentions ». | nDCG@3, P@1 |
| QR5 | Les recommandations combinant contenu et graphe sont-elles plus pertinentes que la seule similarité de contenu ? | H5 : nDCG@5 supérieur. | P@5, R@5, nDCG@5 |

Ces hypothèses sont **réfutables** : les résultats négatifs seront rapportés tels quels dans le rapport.
