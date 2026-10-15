# Gouvernance, déploiement et conduite du changement

Les chapitres précédents ont évalué la plateforme comme un objet technique. Dans une banque, un tel outil ne crée de la valeur que s'il s'insère dans une organisation : quelqu'un doit répondre de la qualité des documents, de la justesse du graphe, des droits d'accès et de l'usage fait des réponses. Ce chapitre traite de cette dimension. Il mobilise notre pratique de consultante en organisation plus que la littérature scientifique, et son statut doit être clair : il s'agit de **propositions**, construites à partir du prototype et de ses limites mesurées, et non de résultats expérimentaux. Pour chaque dispositif, nous distinguons ce que le prototype réalise déjà de ce qu'il faudrait ajouter avant un usage réel.

## Gouvernance des connaissances

### Principes directeurs

Quatre principes structurent nos propositions.

1. **Le document source reste la référence.** Le graphe est une représentation dérivée, reconstructible à tout moment à partir des documents. Une réponse de la plateforme n'a pas de valeur normative propre : elle renvoie à une procédure, une note ou un compte rendu, qui seul fait foi. C'est ce qui justifie les citations obligatoires et l'abstention.
2. **La responsabilité du contenu reste aux métiers.** La plateforme ne transfère pas la propriété des documents à l'équipe qui l'exploite. Le propriétaire d'une procédure reste responsable de son exactitude et de sa mise à jour.
3. **Le modèle de connaissances est un actif gouverné.** L'ontologie, les référentiels d'entités, les alias et les règles d'extraction déterminent ce que le graphe sait représenter. Leur évolution doit être décidée et tracée, comme celle d'un référentiel de données.
4. **Les droits d'accès suivent les règles de diffusion existantes.** La plateforme n'invente pas de nouvelle politique : elle applique la diffusion déclarée dans chaque document, avant toute recherche.

### Rôles

Le tableau suivant décrit les rôles que nous proposons et leur correspondance avec le prototype.

| Rôle | Responsabilités principales | Dans le prototype |
|---|---|---|
| Propriétaire de document | exactitude, mise à jour, diffusion déclarée | hors outil (cartouche du document) |
| Gestionnaire des connaissances | référentiels, alias, entités candidates, quarantaine | non outillé (fichiers de configuration) |
| Architecte de données | ontologie, règles d'extraction, évolutions du modèle | fichiers YAML versionnés |
| Administrateur de la plateforme | ingestion, sauvegardes, comptes, supervision | rôle admin |
| Contrôle permanent et conformité | contrôles par échantillonnage, revue des incidents | non outillé |
| Sécurité des SI et DPO | habilitations, homologation, données personnelles | hors outil |

Table: Rôles proposés pour la gouvernance de la plateforme

Le rôle de gestionnaire des connaissances est le plus nouveau. Il correspond à ce que la gouvernance des données appelle un *data steward* : une personne proche des métiers, capable de juger que « Salma Idrissi » et « S. Idrissi » désignent la même personne ou qu'une entité extraite est pertinente, sans être informaticienne. Dans le prototype, ce travail se fait en modifiant des fichiers de configuration, ce qui ne convient pas à un usage réel.

### Matrice RACI

La matrice suivante répartit les principales activités entre ces rôles (R : réalise ; A : approuve et rend compte ; C : consulté ; I : informé).

| Activité | Propriétaire | Gestionnaire | Admin | Conformité | Sécurité |
|---|---|---|---|---|---|
| Publier ou réviser un document | A, R | I | I | I | - |
| Ingérer et contrôler la qualité | I | C | A, R | - | - |
| Traiter un document en quarantaine | C | R | A | I | C |
| Valider les entités candidates | C | A, R | I | - | - |
| Faire évoluer l'ontologie et les règles | C | C | R | I | - |
| Attribuer les groupes de diffusion | C | - | R | C | A |
| Choisir un fournisseur de LLM | - | - | R | C | A |
| Contrôler la qualité des réponses | C | R | I | A | - |

Table: Matrice RACI proposée

Deux choix méritent une justification. D'abord, l'évolution de l'ontologie est réalisée par l'administrateur, en pratique une équipe data, mais elle consulte les métiers : un type de relation n'a de sens que s'il répond à une question qu'ils se posent. Ensuite, le contrôle de la qualité des réponses est placé sous la responsabilité de la conformité et non de l'équipe qui exploite l'outil, pour préserver la séparation entre celui qui produit et celui qui contrôle.

## Cycle de vie documentaire et validation

Le prototype gère déjà une partie du cycle de vie d'un document. À l'ingestion, chaque fichier reçoit un statut. Le tableau suivant les récapitule et indique, pour chacun, l'action humaine que nous proposons.

| Statut | Signification dans le prototype | Action proposée |
|---|---|---|
| actif | document intégré au graphe et interrogeable | revue périodique par le propriétaire |
| remplacé | version antérieure liée à la nouvelle par SUPERSEDES | archivage après délai de conservation |
| doublon | copie exacte ou quasi identique d'un document canonique | suppression de la copie à la source |
| rejeté | document illisible ou sans contenu exploitable | correction par le propriétaire |
| quarantaine | instructions destinées à un assistant détectées | analyse sécurité, puis décision |

Table: Statuts documentaires et actions de gouvernance proposées

Les entités suivent une logique comparable. Lorsque la résolution d'entités hésite entre deux seuils, elle crée une entité de statut `candidate`, rattachée à l'entité existante la plus proche par une indication de correspondance possible. Ce mécanisme, inspiré des zones de revue manuelle de Fellegi et Sunter (1969), est en place ; il manque en revanche l'écran qui permettrait à un gestionnaire de confirmer ou de rejeter ces propositions. C'est l'une des premières évolutions à prévoir.

Le cycle de vie complet que nous proposons s'enchaîne ainsi :

1. le propriétaire dépose un document conforme au modèle de la banque, dont le cartouche renseigne la référence, la version, la date et la diffusion ;
2. les contrôles automatiques s'exécutent : format, signature du fichier, taille, qualité du texte, doublons, détection d'injection ;
3. selon le résultat, le document est intégré, rejeté avec un motif ou placé en quarantaine ;
4. si le document remplace une version antérieure, celle-ci passe au statut remplacé et reste consultable pour l'historique ;
5. les entités candidates issues du document sont soumises au gestionnaire des connaissances ;
6. lorsque le document est retiré de la source, la synchronisation le supprime du graphe, avec les relations qu'il était seul à justifier.

Cette dernière étape est importante pour la conformité. Grâce à la provenance portée par les relations, le retrait d'un document entraîne celui des faits qu'il était seul à établir, alors qu'un fait confirmé par un autre document est conservé. Un graphe sans provenance ne permettrait pas ce nettoyage ciblé.

Un point mérite d'être souligné : dans cette architecture, le cartouche du document devient un élément de contrôle. Le champ de diffusion qu'il contient détermine qui pourra voir le document à travers la plateforme. Une erreur de saisie dans ce champ produit donc une erreur d'habilitation. La rigueur des modèles de documents, sujet familier des équipes d'organisation, prend ici une dimension de sécurité.

## Dispositif de contrôle interne

Nous avons construit une matrice des risques et des contrôles selon la logique habituelle du contrôle interne bancaire : pour chaque risque, la cause, les contrôles déjà présents dans le prototype et les contrôles complémentaires que nous proposons.

| Risque | Cause principale | Contrôle existant | Contrôle proposé |
|---|---|---|---|
| Réponse inexacte | passage mal choisi, synthèse erronée | citations vérifiées, appui lexical, abstention | revue mensuelle d'un échantillon de réponses |
| Fuite d'information restreinte | droits mal appliqués | filtrage avant recherche, tests d'accès | recertification des groupes, tests de non-régression |
| Information obsolète | version ancienne non retirée | versions liées, conflits signalés | alerte de revue périodique par document |
| Injection de prompt | instruction cachée dans un document | détection et quarantaine, assainissement | revue humaine de la quarantaine, tests d'intrusion |
| Fait erroné dans le graphe | erreur d'extraction ou de résolution | provenance, confiance, entités candidates | contrôle par échantillonnage des relations |
| Usage abusif des profils d'experts | lecture évaluative d'un classement | preuves affichées, accès réservé aux managers | finalité écrite, information des collaborateurs |
| Transfert de données à un tiers | appel à un LLM externe | mode hors-ligne par défaut, clé hors du code | analyse de risques et contrat avant activation |
| Perte du graphe | panne, erreur de manipulation | sauvegarde et restauration testées | sauvegardes planifiées, test de restauration périodique |

Table: Matrice des risques et des contrôles

Trois risques appellent un commentaire.

**La réponse inexacte** est le risque le plus visible. Nos mesures montrent que les mécanismes de vérification éliminent les citations inventées, mais pas les réponses incomplètes ou mal ciblées : l'exactitude de l'architecture finale reste de 0,694 sur les questions jamais inspectées. Le contrôle proposé consiste donc à rejouer régulièrement un jeu de questions de référence, comme le fait notre campagne d'évaluation, et à faire relire un échantillon de réponses réelles par la conformité. Le banc d'évaluation développé pour ce mémoire peut servir directement à ce contrôle récurrent.

**La recherche d'experts** relève du traitement de données personnelles, puisqu'elle associe des personnes à des domaines de compétence à partir de leurs écrits et de leurs participations. Même si le prototype en réserve l'accès aux managers et justifie chaque classement par des preuves, un déploiement réel supposerait de définir une finalité limitée (orienter une question vers la bonne personne), d'exclure tout usage en évaluation individuelle, d'informer les collaborateurs et d'associer le délégué à la protection des données.

**Le recours à un LLM externe** déplace une partie du traitement hors de la banque. Le prototype a été conçu pour que ce recours soit optionnel : sans clé, il fonctionne entièrement en local, et la clé n'est jamais écrite dans le code ni dans les journaux. Mais l'activation d'un fournisseur supposerait une décision formelle, que nous détaillons plus loin.

Enfin, la journalisation mérite une décision explicite. Le prototype enregistre, pour chaque requête, l'utilisateur, la route appelée, le code de retour et la durée, mais pas le texte des questions. Conserver les questions faciliterait l'audit et l'amélioration de l'outil ; cela reviendrait aussi à constituer un historique de ce que chaque collaborateur a cherché. Ce choix relève de la sécurité et de la protection des données, pas de l'équipe technique seule.

## Trajectoire de déploiement en banque

### Une démarche progressive

Nous ne considérons pas la plateforme comme prête pour la production. Ses résultats ont été obtenus sur un corpus synthétique, sans LLM, avec des comptes de démonstration. Le passage à un usage réel devrait suivre une trajectoire progressive, dont le tableau suivant donne les étapes.

| Étape | Objectif | Périmètre | Condition de passage |
|---|---|---|---|
| Cadrage et homologation | valider l'architecture et les risques | sécurité, DPO, conformité | analyse de risques approuvée |
| Pilote | mesurer la valeur sur des documents réels | un domaine, utilisateurs volontaires | exactitude et absence de fuite vérifiées |
| Industrialisation | rendre l'outil exploitable | SSO, supervision, sauvegardes | exigences d'exploitation satisfaites |
| Extension | élargir le corpus | domaines successifs | gouvernance du domaine en place |

Table: Trajectoire de déploiement proposée

Le pilote est l'étape décisive. Il devrait porter sur un domaine documentaire bien délimité, par exemple les procédures de conformité, et reconstituer sur ce domaine le dispositif d'évaluation du mémoire : un jeu de questions réelles, annotées par les métiers, avec une partie jamais vue pendant la mise au point. C'est à cette condition que l'on saura si les résultats obtenus sur le corpus synthétique se transposent.

### Prérequis techniques et de sécurité

Plusieurs écarts entre le prototype et un service bancaire ont été identifiés pendant la réalisation.

- **Authentification.** Les comptes de démonstration, définis dans un fichier, doivent être remplacés par l'authentification unique de la banque, et les groupes de diffusion alimentés par l'annuaire.
- **Homologation.** L'architecture doit être conforme à la politique de sécurité des systèmes d'information de l'établissement et faire l'objet d'une homologation avant toute mise en service.
- **Journalisation.** Les journaux, déjà produits au format JSON avec masquage des secrets, doivent être centralisés dans l'outil de supervision de sécurité de la banque.
- **Base de graphes.** L'édition Community de Neo4j ne permet ni la sauvegarde à chaud ni un contrôle d'accès fin au niveau de la base. Le prototype compense ce second point par un contrôle applicatif ; un usage réel conduirait à évaluer l'édition Enterprise ou à conserver ce contrôle applicatif en le renforçant par des tests.
- **Montée en charge.** Le limiteur de débit est conservé en mémoire et suppose une seule instance du service ; plusieurs instances exigeraient un stockage partagé.
- **Secrets.** Les secrets, aujourd'hui dans un fichier d'environnement non versionné, devraient être gérés par un coffre-fort de secrets.

### Options d'hébergement

Le prototype est conteneurisé, ce qui le rend portable. Le tableau suivant compare les principales options d'hébergement.

| Option | Avantages | Limites | Usage adapté |
|---|---|---|---|
| Serveur interne avec Docker Compose | maîtrise des données, simplicité | une seule machine, exploitation manuelle | pilote |
| Cloud privé de la banque | intégration au SI, sauvegardes gérées | délais de mise à disposition | industrialisation |
| Orchestrateur de conteneurs interne | haute disponibilité, montée en charge | complexité d'exploitation | extension à grande échelle |
| Hébergeur public de conteneurs | rapidité, coût faible | données hors de la banque | démonstration sur corpus fictif uniquement |

Table: Options d'hébergement de la plateforme

Pour un pilote, un serveur interne avec Docker Compose suffit : c'est la configuration testée dans ce projet, y compris la sauvegarde et la restauration. Un hébergeur public ne convient qu'à une démonstration sur le corpus fictif, jamais à des documents de la banque. Aucun déploiement distant n'a été réalisé dans le cadre de ce mémoire.

### Le cas particulier du LLM

L'activation d'un modèle de langage est la décision la plus structurante, car elle change à la fois la qualité attendue des réponses et le profil de risque. Nous recommandons de la conditionner à cinq vérifications.

1. **Compatibilité technique.** L'interface du fournisseur doit être vérifiée et non supposée : le prototype dispose d'un adaptateur pour l'interface Anthropic et d'un adaptateur pour les interfaces compatibles OpenAI, et aucun n'a été testé contre un service réel.
2. **Classification des données.** Seuls les documents dont la classification autorise un traitement externe devraient être transmis ; à défaut, un modèle hébergé dans la banque serait nécessaire.
3. **Engagements contractuels.** Localisation et durée de conservation des données, absence d'utilisation pour l'entraînement, réversibilité.
4. **Réévaluation.** La campagne d'évaluation doit être rejouée avec le LLM, sur les mêmes questions et avec les mêmes métriques, complétée par une relecture humaine, puisque les métriques lexicales ne suffisent plus à juger une réponse rédigée.
5. **Gestion de la clé.** La clé d'accès doit être conservée dans un coffre-fort de secrets ; toute clé qui aurait circulé en clair doit être considérée comme compromise, révoquée et remplacée.

## Indicateurs de pilotage

Un outil de gestion des connaissances se dégrade silencieusement : documents obsolètes, entités non validées, questions sans réponse. Des indicateurs sont nécessaires pour le détecter. Le tableau suivant propose un premier jeu d'indicateurs ; les seuils seraient à fixer pendant le pilote, à partir des valeurs observées.

| Domaine | Indicateur | Mode de calcul | Disponibilité |
|---|---|---|---|
| Qualité | exactitude sur le jeu de référence | campagne d'évaluation rejouée | existant |
| Qualité | taux d'abstention | abstentions / questions posées | à journaliser |
| Sécurité | fuites détectées par les tests d'accès | nombre, cible nulle | existant |
| Fraîcheur | documents dont la revue est dépassée | date du cartouche et périodicité | à développer |
| Gouvernance | entités candidates en attente | statut candidate dans le graphe | requête simple |
| Gouvernance | documents en quarantaine non traités | statut et ancienneté | requête simple |
| Service | latence au 95e centile | métriques de l'API | existant |
| Adoption | utilisateurs actifs par mois | journaux d'accès | à agréger |
| Satisfaction | part des réponses jugées utiles | retour des utilisateurs | à développer |

Table: Indicateurs de pilotage proposés

Nous avons volontairement indiqué la disponibilité de chaque indicateur. Certains existent déjà dans le prototype, comme les métriques de latence de l'API ou le journal de chaque ingestion ; d'autres demandent un développement, notamment le retour des utilisateurs sur la qualité des réponses, qui n'est pas implémenté.

## Conduite du changement

L'adoption d'un tel outil modifie les pratiques de plusieurs populations. Le tableau suivant résume les impacts attendus et les leviers d'accompagnement que nous proposons.

| Population | Impact principal | Leviers d'accompagnement |
|---|---|---|
| Rédacteurs de procédures | discipline accrue sur les cartouches et la structure | modèles de documents, contrôles à la publication |
| Utilisateurs | nouvelle manière de chercher l'information | formation courte à la lecture des citations et des abstentions |
| Managers | nouvel outil d'orientation vers les experts | règles d'usage écrites, finalité limitée |
| Experts identifiés | sollicitations plus nombreuses | information préalable, possibilité de signaler une erreur |
| Fonctions de contrôle | nouveaux contrôles à opérer | intégration au plan de contrôle permanent |

Table: Impacts et leviers de conduite du changement

Le principal risque d'adoption tient, selon nous, à un malentendu sur ce que fait l'outil. Un utilisateur qui le prendrait pour un oracle serait déçu par les abstentions, ou, pire, s'appuierait sur une réponse incomplète. La communication doit donc présenter la plateforme comme un moyen d'accéder plus vite aux bons documents, et non comme un substitut à leur lecture. Les abstentions doivent être expliquées comme une garantie : la plateforme préfère dire qu'elle ne sait pas plutôt que d'inventer.

L'outil peut aussi produire un effet vertueux sur la documentation elle-même. En rendant visibles les contradictions entre versions, les doublons et les documents mal structurés, il fournit aux propriétaires de documents un diagnostic de leur propre corpus. Dans notre corpus synthétique, la contradiction sur la périodicité de revue des dossiers à risque élevé, douze mois dans une version et vingt-quatre dans une autre, est signalée explicitement à l'utilisateur. Dans une banque, ce type de signalement alimenterait directement le plan de mise à jour des procédures.

## Synthèse

Ce chapitre a montré que la plateforme, pour être utile et maîtrisée, doit s'accompagner d'une organisation : des rôles clairs, au premier rang desquels le gestionnaire des connaissances, un cycle de vie documentaire dont plusieurs étapes sont déjà automatisées, un dispositif de contrôle interne qui s'appuie sur les mécanismes du prototype et une trajectoire de déploiement prudente, centrée sur un pilote évalué avec la même rigueur que le corpus synthétique. Les écarts qui séparent le prototype d'un service bancaire sont identifiés ; ils relèvent davantage de l'intégration au système d'information et de la gouvernance que de l'architecture de la solution.
