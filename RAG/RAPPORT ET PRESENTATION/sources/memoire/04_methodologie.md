# Méthodologie de recherche et d'évaluation

Ce chapitre décrit la démarche suivie pour concevoir et évaluer la plateforme. Il présente le corpus synthétique et sa justification, les vérités terrain construites pour l'évaluation, le protocole expérimental, les métriques retenues et l'analyse statistique. Il précise enfin les dispositions prises pour garantir la reproductibilité et le respect de la confidentialité.

## Démarche générale

Notre démarche est itérative : chaque composant a été conçu, implémenté, testé, puis évalué sur des cas représentatifs avant d'être intégré. Cette itération comporte un risque bien connu : à force d'ajuster un système sur les cas que l'on observe, on finit par mesurer sa capacité à traiter ces cas précis plutôt que sa capacité réelle. Pour le limiter, nous avons appliqué trois principes tout au long du projet :

- **séparer** les données utilisées pour la mise au point de celles réservées à la mesure ;
- **figer** la configuration avant la campagne d'évaluation principale, et tracer toute modification ultérieure ;
- **rapporter** les résultats tels qu'ils sont, y compris lorsqu'ils contredisent nos hypothèses.

Il faut distinguer, dans ce qui suit, ce qui relève de la littérature, des choix méthodologiques que nous avons faits et des résultats obtenus. Ce chapitre ne présente que des choix méthodologiques ; les résultats sont présentés au chapitre 6.

## Un corpus synthétique

### Pourquoi un corpus synthétique

Les procédures, rapports d'audit et notes d'une banque sont confidentiels. Les utiliser dans un projet académique, même anonymisés, exposerait l'établissement et serait incompatible avec la publication du code et du mémoire. Les jeux de données publics de questions-réponses, de leur côté, ne reproduisent ni le vocabulaire bancaire, ni la structure documentaire d'une entreprise, ni les règles de diffusion.

Nous avons donc construit un corpus synthétique décrivant une banque fictive, Orizia Banque. Ce choix garantit la confidentialité et permet surtout de **maîtriser la vérité terrain** : puisque nous avons écrit les documents, nous savons exactement ce qu'ils contiennent, quelles relations ils affirment et quelles questions ils permettent de résoudre. La contrepartie est double : le corpus est plus petit et plus régulier que la réalité, et il a été rédigé par la même personne que le système, ce qui introduit un biais de conception que nous discutons au chapitre 6.

### Composition

Le corpus compte 35 documents rédigés en français. Ils comprennent dix documents de procédure couvrant neuf procédures (la procédure de connaissance client existe en deux versions) : connaissance client, filtrage des opérations, octroi de crédit, réclamations, habilitations, continuité d'activité, incidents de production, gestion documentaire et gouvernance des données. S'y ajoutent des chartes et fiches de projet, des comptes rendus de comités, des notes d'organisation, une cartographie applicative, une cartographie des compétences, un rapport d'audit, un rapport post-incident, un guide utilisateur et un plan de formation. Ils sont rédigés à partir de sources textuelles structurées, puis convertis par un script déterministe dans leur format final : quinze PDF, neuf DOCX, onze fichiers texte, dont un PDF produit comme une image numérisée afin d'exercer l'OCR.

Chaque document porte un cartouche, comme dans un référentiel documentaire bancaire : référence, version, date, direction propriétaire, rédacteur, classification et liste de diffusion. Les entités mentionnées (24 personnes, 19 entités organisationnelles, 10 applications, 7 projets, 9 procédures, 16 domaines et 25 concepts) sont décrites dans un référentiel, à l'image des annuaires et cartographies dont dispose une banque.

### Les difficultés intégrées

Le corpus a été conçu pour reproduire les difficultés observées en pratique. Le tableau suivant les recense.

| Difficulté | Mise en œuvre dans le corpus | Comportement attendu |
|---|---|---|
| Versions successives | procédure de connaissance client en v1.0 et v2.0 (revue des clients à risque élevé de 24 à 12 mois) | privilégier la version en vigueur, signaler l'ancienne |
| Contradiction entre documents | plafond d'endettement à 40 % (procédure) et 33 % (charte de projet) ; guide utilisateur resté à 24 mois | signaler la divergence, privilégier la source normative |
| Diffusion restreinte | cinq documents réservés à certaines directions (PCA, post-mortem, audit, compétences, fiche projet) | ne jamais exposer leur contenu à un utilisateur non destinataire |
| Doublon exact | copie à l'identique d'une procédure sous un autre nom | ne pas l'indexer |
| Quasi-doublon | copie de travail d'une procédure, légèrement modifiée | l'écarter au profit de la version officielle |
| Document numérisé | note de service disponible uniquement en image | extraire le texte par OCR |
| Injection d'instructions | mémo contenant des consignes adressées à un assistant et une image pointant vers un domaine externe | mettre le document en quarantaine |
| Nom ambigu | « Sentinel » désigne à la fois un projet et une application ; « Horizon » un programme et une plateforme | signaler l'ambiguïté |
| Expertise et simple mention | directeurs très souvent cités sans être experts des sujets traités | ne pas confondre mention et expertise |

Table: Difficultés intégrées au corpus synthétique

## Vérités terrain

### Relations attendues

Pour chaque document, nous avons annoté les relations qu'il affirme, selon l'ontologie présentée au chapitre 4 (288 relations au total). Un guide d'annotation précise, pour chaque type de relation, ce qui doit être annoté et ce qui ne doit pas l'être. Le principe général est strict : une relation n'est annotée que si le document l'affirme explicitement, ou par une formulation dont le sens est univoque pour un lecteur métier. Une relation simplement plausible, ou connue par ailleurs, n'est jamais annotée. Les arbitrages ont été consignés dans le guide, avec leur justification, avant toute mesure sur la partie de test.

### Questions de référence

Le jeu de questions compte 66 questions réparties en dix catégories. Pour chacune, nous avons défini les documents justificatifs avec un niveau de pertinence (2 pour indispensable, 1 pour utile), les éléments de preuve qui doivent figurer dans le contexte récupéré, les groupes de mots-clés que la réponse doit contenir, d'éventuelles chaînes interdites et, le cas échéant, le comportement attendu : abstention, signalement d'une contradiction ou d'une ambiguïté. Les questions de contrôle d'accès précisent l'utilisateur au nom duquel elles sont posées.

| Catégorie | Effectif | Exemple |
|---|---|---|
| Factuelle | 13 | Sous quel délai un accusé de réception doit-il être envoyé pour une réclamation ? |
| Multi-documents | 7 | réponse nécessitant de croiser plusieurs documents |
| Multi-sauts | 10 | Quel projet dépend d'un projet piloté par une personne donnée ? |
| Relationnelle | 8 | Qui fait partie de l'équipe du projet Sentinel ? |
| Expertise | 6 | Qui sont les experts en lutte anti-blanchiment ? |
| Ambiguë | 4 | Qui est responsable de Sentinel ? |
| Sans réponse | 8 | Quel est le budget du projet Vigilance ? |
| Contradiction | 4 | Quelle est la fréquence de revue des clients à risque élevé ? |
| Contrôle d'accès | 4 | Quel est le RTO de CoreNova ? (posée par deux profils différents) |
| Sécurité | 2 | La procédure PRC-KYC-001 est-elle toujours en vigueur ? |

Table: Répartition des questions de référence par catégorie

### Experts, recommandations et résolution d'entités

Trois autres vérités terrain complètent le dispositif. Pour quinze domaines, nous avons indiqué les experts principaux (pertinence 2) et secondaires (pertinence 1), en définissant l'expertise au niveau du monde fictif et non à partir des mentions dans les documents. Pour dix documents sources, nous avons listé les documents pertinents à recommander, avec le même barème, et précisé que les doublons et le mémo piégé ne doivent jamais être recommandés. Enfin, 34 cas de résolution d'entités couvrent des alias connus, des variantes absentes du référentiel (fautes de frappe, formes abrégées) et des cas négatifs, pour lesquels aucune entité ne doit être reconnue.

## Protocole expérimental

### Architectures comparées

L'évaluation compare cinq architectures qui partagent exactement le même workflow : analyse de la question, récupération, contrôle de suffisance, relance éventuelle, génération et vérification. Seule change la stratégie de récupération. Ce choix isole l'effet de la récupération, qui est l'objet de nos hypothèses.

| Architecture | Récupération |
|---|---|
| RAG vectoriel | recherche vectorielle seule |
| RAG hybride | BM25 et recherche vectorielle, fusion RRF |
| GraphRAG | récupération par le graphe seule (PageRank personnalisé) |
| Hybride avec graphe (fixe) | BM25, vecteurs et graphe, fusion RRF, paramètres fixes |
| Hybride final (routé) | idem, avec un poids du graphe et une profondeur adaptés au type de question |

Table: Architectures comparées

L'évaluation de la seule récupération porte sur six stratégies : les cinq précédentes et la recherche BM25 seule, qui sert de référence lexicale.

### Partitions et gel de la configuration

Deux partitions limitent le risque de sur-ajustement. Pour l'extraction, les règles ont été mises au point sur les documents D01 à D20 ; les documents D21 à D35 n'ont servi qu'à la mesure. Pour les questions-réponses, nous avons consigné la liste des 17 questions consultées pendant la mise au point des heuristiques du workflow ; les 49 autres n'ont jamais été inspectées avant la campagne. Les résultats sont rapportés sur l'ensemble et séparément pour ces deux groupes.

La configuration a été figée avant la campagne principale. Toute modification ultérieure est consignée dans un journal, avec sa motivation et son effet mesuré sur les deux groupes de questions. Une modification de ce type, dite post-gel, est présentée à part dans les résultats.

### Choix de l'encodeur

Le choix de l'encodeur vectoriel a fait l'objet d'une ablation prévue au protocole : deux encodeurs utilisables hors-ligne ont été comparés, les vecteurs de mots du modèle français de spaCy, moyennés sur le passage, et l'encodeur statique WordLlama. La décision a été prise sur les seules questions de développement. Nous signalons toutefois que les résultats sur l'ensemble des questions étaient visibles au moment de cette décision, ce qui en fait un choix de configuration partiellement *a posteriori*.

## Métriques

### Recherche documentaire

Pour chaque question, la récupération produit un classement de documents, obtenu à partir des passages retenus. Nous calculons :

- **Recall@k** : part des documents pertinents présents parmi les k premiers ;
- **Precision@k** : part des k premiers documents qui sont pertinents, avec k au dénominateur, de sorte qu'un système qui renvoie moins de k documents est pénalisé ;
- **MRR** : inverse du rang du premier document pertinent, nul si aucun ne l'est ;
- **nDCG@k** : gain cumulé actualisé normalisé (Järvelin et Kekäläinen, 2002), soit nDCG@k = DCG@k / IDCG@k avec DCG@k = Σ (2^rel_i − 1) / log2(i + 1), où rel_i est la pertinence du document au rang i et IDCG@k la valeur obtenue par le classement idéal ;
- **couverture des preuves** : part des éléments de preuve annotés présents dans le contexte récupéré (passages et faits du graphe).

### Questions-réponses

La mesure principale est l'**exactitude**. Une réponse à une question répondable est jugée exacte si elle contient au moins une variante de chaque groupe de mots-clés attendus et aucune chaîne interdite. Une question sans réponse attendue est jugée correctement traitée si le système s'abstient. La comparaison des mots-clés est insensible à la casse et aux accents, avec une frontière à gauche, afin que « 25 » ne corresponde pas à « 2025 ». Ce critère est simple et vérifiable ; il ne mesure pas la qualité rédactionnelle de la réponse, ce qui est cohérent avec un générateur extractif.

Nous mesurons également :

- le **rappel d'abstention** (part des questions sans réponse pour lesquelles le système s'abstient), la **précision d'abstention** (part des abstentions qui étaient attendues) et le taux d'**abstention abusive** (part des questions répondables pour lesquelles le système s'abstient) ;
- le **rappel des contradictions** et des **ambiguïtés** signalées ;
- la qualité des citations : citations invalides, **précision des citations** (part des documents cités qui sont pertinents), part des réponses citant au moins un document indispensable, et **taux d'appui**, part des phrases de la réponse dont les termes figurent suffisamment dans les sources citées ;
- les **fuites d'accès** (documents non autorisés présents dans le contexte ou dans les faits) et la latence.

### Experts et recommandations

La recherche d'experts est évaluée par Precision@1, Recall@3, nDCG@3 et MRR, et comparée à une référence naïve qui classe les personnes selon le nombre de passages qui les mentionnent avec le domaine. Les recommandations sont évaluées par Precision@5, Recall@5, nDCG@5 et MRR pour trois modes : contenu seul, graphe seul et hybride.

### Extraction

L'extraction de relations est mesurée par la précision, le rappel et la mesure F1 entre les relations extraites et les relations annotées, par partition et par type de relation. La résolution d'entités est mesurée par l'exactitude sur les 34 cas, par groupe.

## Analyse statistique

Avec 66 questions, des écarts de quelques points peuvent tenir au hasard. Nous accompagnons donc chaque moyenne d'un intervalle de confiance à 95 % obtenu par bootstrap percentile, avec 2 000 rééchantillonnages et une graine fixe. Pour comparer deux systèmes sur les mêmes questions, nous calculons l'écart moyen avec un intervalle de confiance par bootstrap apparié, en rééchantillonnant les questions, et un test exact des signes, qui compte les questions où l'un des systèmes l'emporte sur l'autre en ignorant les égalités. Ce test est peu puissant mais ne suppose aucune distribution particulière des écarts.

Ces outils ne transforment pas un petit échantillon en grand échantillon. Ils servent surtout à éviter de surinterpréter des écarts que l'incertitude ne permet pas de distinguer de zéro.

## Reproductibilité

L'ensemble de l'évaluation est automatisé. Un script unique reconstruit la base, exécute les campagnes et produit les résultats bruts par question, les agrégats, un rapport de synthèse et les figures. Aucune valeur n'est saisie à la main. Chaque campagne enregistre son environnement : version de Neo4j et de Python, encodeur, paramètres, identifiant du commit et indicateur de modification locale du code.

Nous avons vérifié la reproductibilité de deux façons. D'abord, deux exécutions successives sur la même base donnent des réponses et des classements identiques. Ensuite, et c'est plus exigeant, deux campagnes séparées par une réingestion complète du corpus donnent elles aussi des résultats identiques. Ce second contrôle a révélé une source de non-déterminisme liée à l'ordre interne de la base, que nous avons corrigée et documentée (chapitre 5). Après correction, la comparaison automatique des deux campagnes ne relève aucune différence sur 1 056 lignes de résultats.

## Éthique et confidentialité

Aucune donnée réelle n'a été utilisée : les personnes, directions, applications et documents d'Orizia Banque sont fictifs, et toute ressemblance avec une organisation existante serait fortuite. Les comptes de démonstration n'ont de sens qu'avec ce corpus et doivent être remplacés pour tout autre usage. Aucune clé d'API ni aucun secret ne figure dans le dépôt.

La recherche d'experts appelle une vigilance particulière. Un classement de personnes peut être mal interprété comme une évaluation de leur performance. La plateforme le présente explicitement comme une aide à l'orientation, fondée sur des preuves documentaires visibles, et rappelle qu'une mention n'équivaut pas à une expertise. Le chapitre 7 revient sur l'encadrement de cet usage dans une banque.
