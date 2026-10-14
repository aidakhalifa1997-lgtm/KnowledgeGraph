# Contexte, enjeux et cadrage du projet

Ce chapitre situe le projet dans son environnement. Nous partons des enjeux de la gestion des connaissances dans une banque, puis nous établissons un diagnostic des difficultés rencontrées par les utilisateurs. Nous en déduisons les besoins, les objectifs et le périmètre, avant de formaliser les exigences et d'analyser les risques du projet.

## La gestion des connaissances dans une banque

### Une connaissance largement documentaire

Dans un établissement bancaire, une grande partie de la connaissance utile au fonctionnement quotidien est consignée par écrit. Les procédures décrivent les étapes d'un processus, les responsabilités de chaque acteur, les règles de gestion et les contrôles. Les notes d'organisation fixent les rattachements et les périmètres des directions. Les chartes et fiches de projet précisent les objectifs, les équipes et les dépendances des chantiers en cours. Les comptes rendus de comités enregistrent les décisions, parfois avant qu'elles ne soient reportées dans les procédures. Les rapports d'audit et les retours d'expérience, enfin, documentent les écarts constatés et les enseignements tirés.

Cette documentation n'est pas un simple support d'information. Elle engage la banque : une procédure validée fait foi lors d'un contrôle, et l'écart entre la pratique et la procédure constitue un constat. La gestion des connaissances relève donc autant de la performance opérationnelle que du dispositif de contrôle interne.

### Des exigences propres au secteur

Trois exigences distinguent le contexte bancaire d'un usage documentaire ordinaire.

La première est la **traçabilité**. Toute information transmise à un collaborateur doit pouvoir être rattachée à sa source, avec sa version et sa date, afin qu'il puisse vérifier qu'elle est en vigueur. Une réponse sans source n'est pas exploitable dans un processus contrôlé.

La deuxième est la **confidentialité**. Certains documents ne sont diffusés qu'à quelques directions : un plan de continuité d'activité détaille des scénarios de crise et des délais de reprise, un rapport d'audit expose des faiblesses de contrôle, une cartographie des compétences contient des informations sur les personnes. Un outil de recherche qui ignorerait ces restrictions créerait une fuite d'information, même si chaque document est correctement protégé dans son référentiel d'origine.

La troisième est la **fiabilité**. Une réponse fausse mais assurée est plus dangereuse qu'une absence de réponse, car elle peut conduire à appliquer une règle obsolète ou un seuil erroné. Un assistant destiné à un environnement régulé doit savoir s'abstenir.

## Diagnostic des difficultés rencontrées

Notre pratique de la rédaction et de la mise à jour de procédures nous a permis d'observer plusieurs difficultés récurrentes, que nous avons ensuite reproduites dans le corpus synthétique (chapitre 3).

**La dispersion.** Une même information peut se trouver dans une procédure, dans un compte rendu de comité qui a décidé de la modifier, dans la charte du projet qui l'a mise en œuvre et dans le guide utilisateur de l'outil concerné. Aucun de ces documents ne donne à lui seul une vision complète.

**La multiplicité des versions.** Les procédures évoluent. Lorsqu'une nouvelle version est publiée, l'ancienne reste souvent accessible, et les documents qui la citaient ne sont pas tous mis à jour. Dans notre corpus, la procédure de connaissance client existe en version 1.0 et 2.0 : la fréquence de revue des clients à risque élevé passe de 24 à 12 mois, mais le guide utilisateur de l'outil continue d'indiquer 24 mois.

**Les contradictions.** Au-delà des versions, deux documents en vigueur peuvent se contredire. Le plafond du taux d'endettement figure à 40 % dans la procédure d'octroi de crédit et à 33 % dans la charte du projet de digitalisation, qui reprend une règle antérieure.

**Le cloisonnement.** Les restrictions de diffusion sont légitimes, mais elles rendent difficile la réponse à des questions transverses : un collaborateur ne doit pas obtenir le délai de reprise d'une application critique s'il n'est pas destinataire du plan de continuité.

**La dépendance aux personnes.** Faute de savoir où chercher, les collaborateurs se tournent vers les personnes réputées savoir. Cette dépendance concentre la charge sur quelques experts et fragilise l'organisation lors des départs. Encore faut-il identifier ces experts : les personnes les plus souvent citées dans les documents ne sont pas toujours les plus compétentes, car un directeur apparaît dans de nombreux comptes rendus sans être expert de chaque sujet traité.

**Les documents piégés.** Les documents eux-mêmes peuvent contenir des contenus indésirables : copies de travail, brouillons, ou, de façon plus préoccupante avec l'arrivée des assistants, des instructions destinées à manipuler un modèle de langage (Greshake et al., 2023).

## Parties prenantes et profils d'utilisateurs

Nous avons identifié cinq profils d'utilisateurs, que nous avons traduits en comptes de démonstration dotés de rôles et de groupes de diffusion différents.

| Profil | Besoin principal | Rôle et groupes de démonstration |
|---|---|---|
| Collaborateur d'agence ou de back-office | trouver la règle applicable et sa source | viewer ; diffusion générale |
| Analyste conformité | retrouver les exigences, les constats d'audit et les décisions de comité | viewer ; générale et Conformité |
| Ingénieur des systèmes d'information | connaître les dépendances entre applications et les délais de reprise | viewer ; générale et DSI |
| Responsable (manager) | identifier les personnes compétentes sur un sujet | manager ; générale et sa direction |
| Administrateur de la plateforme | gérer le corpus, surveiller l'ingestion | admin ; tous les groupes |

Table: Profils d'utilisateurs et comptes de démonstration

À ces utilisateurs s'ajoutent des parties prenantes qui n'utilisent pas directement l'outil mais en conditionnent l'adoption : les propriétaires des documents, garants de leur mise à jour ; la fonction conformité et le contrôle interne, attentifs à la traçabilité et au respect des règles de diffusion ; la direction des systèmes d'information et la sécurité, qui valident l'architecture et l'hébergement. Le chapitre 7 revient sur leur rôle dans la gouvernance de la plateforme.

## Objectifs et périmètre

### Objectifs

Au regard de ce diagnostic, la plateforme doit permettre de poser une question en langage naturel et d'obtenir une réponse sourcée, de naviguer dans les relations entre personnes, directions, projets, applications et procédures, d'identifier des experts sur un domaine avec une justification et de découvrir des documents liés. Elle doit le faire en respectant les droits de chacun et en signalant ses propres limites : versions remplacées, contradictions, ambiguïtés, informations insuffisantes.

### Périmètre retenu

Le tableau suivant précise ce qui entre dans le périmètre du projet et ce qui en est exclu.

| Dans le périmètre | Hors périmètre |
|---|---|
| ingestion de PDF, DOCX, TXT et PDF scannés | autres formats (tableurs, courriels, images seules) |
| extraction d'entités et de relations selon une ontologie définie | apprentissage de l'ontologie ou de nouveaux types d'entités |
| contrôle d'accès par groupes de diffusion | intégration à l'annuaire de l'entreprise et authentification unique |
| questions-réponses en français, avec citations et abstention | conversation multi-tours et mémoire de dialogue |
| recherche d'experts et recommandations explicables | évaluation des personnes ou usage RH |
| déploiement conteneurisé et procédures d'exploitation | déploiement effectif sur l'infrastructure d'une banque |
| évaluation sur un corpus synthétique annoté | évaluation sur des documents réels ou par des utilisateurs |

Table: Périmètre du projet

## Exigences

### Exigences fonctionnelles

| Identifiant | Exigence |
|---|---|
| EF-1 | Ingérer des documents PDF, DOCX et TXT, y compris des PDF scannés, et en extraire le texte. |
| EF-2 | Extraire les métadonnées du cartouche : référence, version, date, direction, rédacteur, classification, diffusion. |
| EF-3 | Détecter les doublons exacts et les quasi-doublons, et rattacher les versions successives d'un même document. |
| EF-4 | Extraire les entités et les relations définies par l'ontologie, avec leur preuve textuelle. |
| EF-5 | Répondre à une question en langage naturel en citant les passages et les faits utilisés. |
| EF-6 | S'abstenir lorsque les documents accessibles ne permettent pas de répondre, en indiquant ce qui manque. |
| EF-7 | Signaler les versions remplacées, les valeurs contradictoires et les questions ambiguës. |
| EF-8 | Permettre l'exploration visuelle du graphe et la consultation de la provenance de chaque relation. |
| EF-9 | Proposer une recherche d'experts par domaine, justifiée par des preuves documentaires. |
| EF-10 | Recommander des documents liés à un document ou à un besoin exprimé, avec les raisons. |
| EF-11 | Permettre à un administrateur de téléverser, supprimer et resynchroniser des documents. |

Table: Exigences fonctionnelles

### Exigences non fonctionnelles

| Identifiant | Exigence |
|---|---|
| ENF-1 | Sécurité : contrôle d'accès appliqué avant toute recherche ; aucune information issue d'un document non autorisé dans une réponse, un fait ou une visualisation. |
| ENF-2 | Sécurité : résistance à l'injection d'instructions contenues dans les documents ; secrets hors du code et des journaux. |
| ENF-3 | Traçabilité : chaque relation du graphe conserve ses documents sources, ses passages et ses citations. |
| ENF-4 | Explicabilité : trace des étapes du workflow, des scores et des décisions renvoyée avec chaque réponse. |
| ENF-5 | Reproductibilité : résultats d'évaluation identiques d'une exécution à l'autre, y compris après réingestion. |
| ENF-6 | Indépendance vis-à-vis du fournisseur de LLM et fonctionnement complet hors-ligne. |
| ENF-7 | Performance : réponse en moins d'une seconde sur le corpus de démonstration ; réingestion sans changement quasi instantanée. |
| ENF-8 | Exploitabilité : déploiement conteneurisé, sondes de santé, sauvegarde et restauration documentées et testées. |
| ENF-9 | Accessibilité et ergonomie : interface en français, utilisable au clavier et sur téléphone. |

Table: Exigences non fonctionnelles

## Contraintes du projet

Trois contraintes ont fortement orienté nos choix.

**L'impossibilité d'utiliser des documents réels.** Les procédures et rapports d'une banque sont confidentiels et ne peuvent figurer ni dans un dépôt de code ni dans un mémoire. Nous avons donc construit un corpus entièrement synthétique, ce qui garantit la confidentialité mais limite la portée des conclusions (chapitre 3).

**L'absence de clé d'API de modèle de langage.** Aucun accès à un fournisseur de LLM n'a été disponible pendant le projet. Nous avons conçu la plateforme pour qu'elle fonctionne entièrement sans LLM, avec des mécanismes déterministes (extraction par règles, générateur extractif), tout en préparant des adaptateurs vers les fournisseurs. Cette contrainte a eu une conséquence positive : elle nous a obligée à rendre explicite chaque décision, plutôt que de la déléguer à un modèle.

**Un environnement de développement restreint.** Les modèles de langage et d'encodage ne pouvaient pas être téléchargés depuis les plateformes de modèles habituelles. Nous avons donc retenu des encodeurs installables depuis le dépôt de paquets Python, plus légers que les modèles de phrases de référence, et nous avons mesuré l'effet de ce choix.

## Analyse des risques du projet

Nous avons appliqué au projet lui-même la démarche que nous appliquons aux procédures : identifier les risques, en évaluer l'impact et définir des mesures.

| Risque | Impact | Mesure retenue |
|---|---|---|
| Résultats non généralisables (corpus synthétique) | conclusions surestimées | pièges réalistes intégrés au corpus, limites explicitées, distinction développement / jamais inspectées |
| Biais d'auto-évaluation (corpus et annotations par l'auteure) | résultats optimistes | guide d'annotation, partition des documents, gel de la configuration avant la campagne |
| Fuite d'information entre utilisateurs | risque de sécurité majeur | contrôle d'accès avant recherche, tests dédiés, métrique de fuite dans chaque campagne |
| Hallucination ou réponse non sourcée | perte de confiance, erreur opérationnelle | générateur extractif, vérification des citations, abstention |
| Dépendance à un fournisseur de LLM | blocage, coûts, confidentialité | couche d'abstraction, mode hors-ligne complet |
| Résultats non reproductibles | évaluation non crédible | graines fixes, tris déterministes, comparaison automatique de deux campagnes |
| Ampleur du projet pour une seule personne | livrables incomplets | découpage en phases, automatisation des tests et de l'évaluation |

Table: Analyse des risques du projet

## Organisation et déroulement

Le projet a été conduit en douze phases, de l'audit initial à la préparation de la soutenance. Les premières phases ont porté sur le cadrage, la structure du dépôt et la revue de littérature, avec une bibliographie vérifiée. Sont venus ensuite la construction du corpus synthétique et des vérités terrain, le développement du cœur de la plateforme (ingestion, extraction, graphe, recherche, workflow, API), puis l'interface web. Les tests automatisés et la campagne d'évaluation ont précédé la conteneurisation, les procédures d'exploitation et l'intégration continue. Les dernières phases ont été consacrées à la documentation, au présent mémoire et à la présentation.

Cette progression n'a pas été strictement linéaire. Plusieurs résultats intermédiaires ont conduit à revenir sur des choix antérieurs, par exemple l'encodeur vectoriel ou la fusion des classements. Chaque retour en arrière a été tracé dans un journal des modifications, afin de distinguer ce qui a été décidé avant la campagne d'évaluation principale de ce qui l'a été après. Le chapitre 3 détaille ce protocole.
