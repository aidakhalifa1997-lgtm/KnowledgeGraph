# Introduction générale {-}

## Contexte {-}

Une banque produit en continu une documentation abondante : procédures, modes opératoires, notes d'organisation, chartes et rapports de projet, comptes rendus de comités, guides utilisateurs, rapports d'audit. Cette documentation porte une part essentielle de la connaissance de l'établissement. Elle dit qui est responsable de quoi, quelles règles s'appliquent, quelles applications dépendent les unes des autres et quels délais doivent être respectés. Elle sert aussi de référence aux fonctions de contrôle, qui vérifient que les pratiques sont conformes aux procédures en vigueur.

Notre activité de consultante en organisation, consacrée à la rédaction et à la mise à jour de procédures, nous a rendue attentive à une difficulté récurrente : la connaissance existe, mais elle est difficile à mobiliser. Les documents sont nombreux et hétérogènes, coexistent en plusieurs versions, se contredisent parfois, et certains ne sont diffusés qu'à quelques directions. Trouver la bonne information suppose souvent de savoir déjà où elle se trouve, ou de connaître la personne qui la détient.

Les grands modèles de langage (LLM) ont relancé l'intérêt pour les assistants capables de répondre en langage naturel. Leur usage direct dans une banque pose cependant trois problèmes : ils peuvent produire des réponses plausibles mais fausses, ils ne connaissent pas les documents internes, et ils ne respectent pas d'eux-mêmes les règles de confidentialité. L'approche dite RAG (*Retrieval-Augmented Generation*), qui consiste à rechercher des passages pertinents avant de générer une réponse (Lewis et al., 2020), répond en partie au deuxième problème. Les approches récentes de type GraphRAG proposent d'y ajouter un graphe de connaissances pour mieux traiter les questions qui relient plusieurs entités (Edge et al., 2024 ; Peng et al., 2024).

## Problématique {-}

Ce travail part d'une question simple en apparence : **comment permettre à un collaborateur d'interroger la documentation interne d'une banque en langage naturel, en obtenant des réponses exactes, sourcées et conformes à ses droits d'accès, y compris lorsque la réponse dépend de relations entre plusieurs documents, entités et versions ?**

Cette question en recouvre plusieurs. Un graphe de connaissances apporte-t-il réellement un gain par rapport à une recherche documentaire bien réglée, et pour quels types de questions ? Comment garantir qu'un utilisateur n'obtienne jamais une information issue d'un document qui ne lui est pas diffusé ? Comment un système peut-il reconnaître qu'il ne sait pas, plutôt que d'extrapoler ? Et comment évaluer tout cela de manière rigoureuse, alors que les documents réels d'une banque ne peuvent pas être utilisés dans un projet académique ?

## Objectifs {-}

Le projet poursuit quatre objectifs :

1. **Construire** une plateforme complète, de l'ingestion des documents jusqu'à l'interface utilisateur : extraction du texte (y compris par OCR), nettoyage, métadonnées, dédoublonnage, extraction des entités et des relations, graphe Neo4j avec provenance, recherche hybride, workflow de questions-réponses, recherche d'experts, recommandations et visualisation du graphe.
2. **Garantir** les propriétés attendues en contexte bancaire : contrôle d'accès appliqué avant toute recherche, citations vérifiables, abstention motivée, détection des contradictions et des versions remplacées, protection contre l'injection d'instructions malveillantes dans les documents.
3. **Comparer expérimentalement** plusieurs architectures (RAG vectoriel, RAG hybride, GraphRAG, hybride avec graphe) sur un banc d'essai annoté, avec des métriques reconnues et une analyse statistique honnête.
4. **Documenter** la solution pour qu'elle puisse être installée, comprise, maintenue et défendue, en tenant compte des exigences de gouvernance propres à une banque.

## Questions de recherche et hypothèses {-}

À partir de l'état de l'art, nous avons formulé cinq questions de recherche, chacune associée à une hypothèse testable.

| Question | Hypothèse |
|---|---|
| QR1 : la récupération guidée par le graphe améliore-t-elle la recherche des documents justificatifs pour les questions relationnelles et multi-sauts ? | H1 : l'approche hybride avec graphe obtient un Recall@5 et un nDCG@5 supérieurs au RAG vectoriel et au RAG hybride sur ces catégories. |
| QR2 : le graphe dégrade-t-il les questions factuelles simples ? | H2 : avec routage, l'approche finale n'est pas inférieure au RAG hybride sur les questions factuelles. |
| QR3 : le contrôle de suffisance permet-il de s'abstenir à bon escient ? | H3 : l'abstention est fréquente sur les questions sans réponse et rare sur les questions répondables. |
| QR4 : un score d'expertise fondé sur des preuves typées est-il plus pertinent qu'un comptage de mentions ? | H4 : nDCG@3 supérieur à la référence « nombre de mentions ». |
| QR5 : des recommandations combinant contenu et graphe sont-elles plus pertinentes que la seule similarité de contenu ? | H5 : nDCG@5 supérieur. |

Table: Questions de recherche et hypothèses

## Démarche et contributions {-}

Notre démarche alterne conception et évaluation. Faute de pouvoir utiliser des documents réels, nous avons construit un corpus synthétique de 35 documents d'une banque fictive, « Orizia Banque », dans lequel nous avons volontairement introduit les difficultés observées en pratique : versions successives d'une même procédure, valeurs contradictoires entre documents, doublons, document scanné, diffusion restreinte et document piégé contenant des instructions destinées à un assistant. Nous avons annoté ce corpus (relations attendues, documents justificatifs, réponses attendues, experts, recommandations) avant d'évaluer la plateforme.

Les contributions de ce travail sont les suivantes :

- une plateforme fonctionnelle, conteneurisée et testée (99 fonctions de test, intégration continue), dont l'architecture place le contrôle d'accès et la provenance au cœur du modèle de données ;
- un banc d'essai reproductible en français pour la gestion des connaissances bancaires, avec un protocole qui distingue les questions utilisées pendant la mise au point de celles jamais inspectées ;
- une comparaison expérimentale de cinq architectures à workflow identique, qui montre notamment que l'apport du graphe dépend fortement du type de question et que la qualité de l'encodeur vectoriel conditionne l'intérêt d'une recherche hybride ;
- une réflexion sur la gouvernance et le déploiement d'un tel outil dans une banque, nourrie par notre expérience de l'organisation et du contrôle interne.

Précisons d'emblée une limite importante : aucune clé d'API de modèle de langage n'ayant été disponible pendant le projet, toutes les mesures ont été réalisées en mode hors-ligne, avec un générateur extractif qui reprend des phrases des documents. Les adaptateurs vers des fournisseurs de LLM sont implémentés et testés avec des réponses simulées, mais leur apport n'a pas été mesuré.

## Organisation du mémoire {-}

Le premier chapitre présente le contexte bancaire, les besoins et le cadrage du projet. Le deuxième dresse l'état de l'art de la recherche d'information, des graphes de connaissances, des approches RAG et GraphRAG, de leur fiabilité et de leur sécurité. Le troisième décrit la méthodologie : construction du corpus, annotation, protocole expérimental et métriques. Le quatrième expose la conception de la solution et justifie les choix techniques, et le cinquième rend compte de sa réalisation et des difficultés rencontrées. Le sixième présente et discute les résultats expérimentaux au regard des hypothèses. Le septième aborde la gouvernance, le déploiement et la conduite du changement dans une banque. La conclusion générale synthétise les apports, les limites et les perspectives.
