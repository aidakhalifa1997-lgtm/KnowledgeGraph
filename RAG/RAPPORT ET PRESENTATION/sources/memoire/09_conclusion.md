# Conclusion générale {-}

## Synthèse du travail {-}

Ce mémoire est parti d'une difficulté observée dans notre pratique de consultante : dans une banque, la connaissance est largement écrite, mais elle reste difficile à mobiliser, parce qu'elle est dispersée entre des documents hétérogènes, des versions successives et des diffusions restreintes. Nous nous sommes demandé comment permettre à un collaborateur d'interroger cette documentation en langage naturel et d'obtenir des réponses exactes, sourcées et conformes à ses droits, y compris lorsque la réponse dépend de relations entre plusieurs documents.

Pour y répondre, nous avons conçu et réalisé une plateforme complète. Elle ingère des documents PDF, DOCX et texte, y compris un document scanné lu par OCR, les nettoie, en extrait les métadonnées, écarte les doublons et met en quarantaine les documents contenant des instructions destinées à un assistant. Elle en tire un graphe de connaissances Neo4j dans lequel chaque relation porte sa provenance : documents sources, passages et extraits justificatifs. Elle répond aux questions par un workflow explicite, orchestré avec LangGraph, qui analyse la question, combine recherche lexicale, vectorielle et parcours du graphe, contrôle la suffisance du contexte, génère une réponse citée, la vérifie et s'abstient lorsque les sources ne suffisent pas. Elle propose enfin une recherche d'experts, des recommandations de documents et une exploration visuelle du graphe, dans une interface web conteneurisée.

Faute de documents réels utilisables, nous avons construit un corpus synthétique de 35 documents d'une banque fictive, dans lequel nous avons introduit les difficultés rencontrées en pratique, puis un banc d'évaluation annoté. Le protocole distingue les questions utilisées pendant la mise au point de celles jamais inspectées, fige la configuration avant la campagne principale et trace toute modification ultérieure. Toutes les mesures ont été réalisées en mode hors-ligne, avec un générateur extractif.

## Réponses aux questions de recherche {-}

**QR1, apport du graphe pour les questions relationnelles et multi-sauts.** La réponse est positive mais nuancée. En recherche documentaire, l'architecture finale fait mieux que le RAG vectoriel sur ces catégories, mais ne se distingue que peu ou pas du RAG hybride. L'effet est plus net sur les réponses : l'exactitude passe de 0,12 à 0,62 sur les questions relationnelles et de 0,30 à 0,60 sur les questions multi-sauts entre le RAG vectoriel et l'architecture finale. L'hypothèse H1 n'est donc que partiellement validée : le graphe aide surtout à rassembler les faits nécessaires à la réponse, davantage qu'à classer les documents.

**QR2, effet sur les questions factuelles.** Le routage protège les questions simples. L'architecture finale conserve une exactitude de 0,92 sur les questions factuelles, comme les RAG vectoriel et hybride, alors que le GraphRAG seul tombe à 0,31. L'hypothèse H2 est validée.

**QR3, abstention.** Le contrôle de suffisance détecte dix des onze questions sans réponse (rappel de 0,909) et aucune information à diffusion restreinte n'a été divulguée. Mais il s'abstient à tort sur 18 % des questions répondables, parce qu'il repose sur une couverture lexicale sensible aux paraphrases. L'hypothèse H3 n'est que partiellement validée.

**QR4, recherche d'experts.** Le score fondé sur des preuves typées obtient un nDCG@3 de 0,975 contre 0,911 pour le comptage de mentions, mais l'écart n'est pas significatif sur quinze domaines (p = 0,375). L'hypothèse H4 n'est pas démontrée ; l'intérêt de la méthode tient surtout à la justification qu'elle fournit pour chaque expert.

**QR5, recommandations.** La combinaison du contenu, des entités partagées et de la proximité dans le graphe améliore nettement les recommandations : nDCG@5 de 0,908 contre 0,648 pour la seule similarité de contenu (p = 0,004). L'hypothèse H5 est validée.

Au-delà des hypothèses, deux résultats nous paraissent instructifs. D'abord, sur ce corpus, la recherche lexicale BM25 est une référence difficile à battre : elle dépasse la recherche vectorielle et même la recherche hybride, et l'ablation de l'encodeur montre que l'intérêt d'une fusion dépend directement de la qualité des vecteurs. Ensuite, l'écart d'exactitude entre questions de développement (0,882) et questions jamais inspectées (0,694) rappelle qu'un système dont les heuristiques sont ajustées à la main sur quelques exemples paraît toujours meilleur sur ces exemples.

## Contributions {-}

Nos contributions sont de trois ordres. Sur le plan technique, la plateforme montre qu'il est possible de placer le contrôle d'accès et la provenance au cœur du modèle de données : les documents autorisés sont calculés avant toute recherche, et chaque fait du graphe reste rattaché aux passages qui le justifient, ce qui permet de le citer et de le retirer avec son document. Sur le plan méthodologique, le banc d'essai en français, avec ses pièges documentaires, son gel de configuration et son journal post-gel, offre un cadre d'évaluation reproductible, dont les campagnes successives produisent des résultats identiques. Sur le plan organisationnel, la réflexion sur la gouvernance traduit les mécanismes du prototype en rôles, en contrôles et en indicateurs, dans les termes du contrôle interne bancaire.

## Limites {-}

Les limites de ce travail sont importantes et doivent encadrer la lecture des résultats. Le corpus, les questions et les annotations sont synthétiques et ont été conçus par une seule personne, qui a aussi développé la plateforme. Les 66 questions donnent des intervalles de confiance larges. Les règles d'extraction ont été mises au point sur la première moitié du corpus, et leur rappel baisse nettement sur la seconde (0,717). Les encodeurs vectoriels utilisés sont légers et fonctionnent hors-ligne. Surtout, aucun modèle de langage n'a été évalué : les adaptateurs existent et sont testés avec des réponses simulées, mais le générateur mesuré se contente d'extraire des phrases des documents. Enfin, la plateforme n'a été exécutée que localement ; elle n'a fait l'objet d'aucun déploiement distant et n'est pas prête pour la production.

## Perspectives {-}

Plusieurs prolongements découlent directement de ces limites.

- **Mesurer l'apport d'un LLM.** Rejouer la campagne d'évaluation avec un modèle de langage, pour la génération comme pour l'extraction, sur les mêmes questions, en complétant les métriques automatiques par une relecture humaine.
- **Remplacer le contrôle de suffisance lexical.** Un contrôle fondé sur l'implication textuelle ou sur un LLM juge, dont les biais seraient mesurés, devrait réduire les abstentions abusives.
- **Évaluer sur des documents réels.** Un pilote sur un domaine documentaire délimité, avec des questions posées par les métiers et annotées par eux, permettrait de vérifier si les résultats se transposent.
- **Outiller la gouvernance.** Un écran de validation des entités candidates et un traitement de la quarantaine rendraient le gestionnaire des connaissances autonome.
- **Explorer le GraphRAG global.** Les résumés de communautés proposés par Edge et al. (2024) répondraient à des questions de synthèse que notre approche locale ne traite pas.
- **Améliorer la lecture des documents complexes.** Des modèles tenant compte de la mise en page, comme LayoutLM (Y. Xu et al., 2020), amélioreraient le traitement des tableaux et des formulaires scannés.

Au terme de ce travail, notre conviction est que la valeur d'un assistant documentaire en banque tient moins à la sophistication de son modèle de langage qu'à la rigueur de ce qui l'entoure : la qualité des documents, la traçabilité des faits, le respect des droits et la capacité à dire « je ne sais pas ». Ce sont ces propriétés que nous avons cherché à construire et à mesurer.
