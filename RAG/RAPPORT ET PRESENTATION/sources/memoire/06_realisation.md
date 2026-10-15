# Réalisation

Ce chapitre rend compte de la mise en œuvre. Nous présentons l'organisation du code, puis les points saillants de chaque composant, en insistant sur les difficultés rencontrées et sur la manière dont elles ont été résolues. Nous décrivons ensuite l'interface, la conteneurisation, l'exploitation et les tests.

## Environnement et organisation du code

Le code est écrit en Python 3.12 pour le serveur et en TypeScript pour l'interface. Il représente environ 7 800 lignes de Python hors tests, 1 200 lignes de tests et 4 200 lignes pour l'interface. Le dépôt suit une structure imposée par le cahier des charges du projet : un dossier de code, un dossier pour le mémoire et la présentation, un dossier de documentation pédagogique, un dossier bibliographique et un dossier de données.

Le code serveur est découpé en paquets qui correspondent aux couches présentées au chapitre 4 :

| Paquet | Rôle |
|---|---|
| core | configuration, texte, ontologie, modèles de données, accès aux LLM, journalisation |
| ingestion | validation, lecture, OCR, nettoyage, métadonnées, qualité, doublons, découpage, pipeline |
| extraction | référentiel, reconnaissance des mentions, règles, extracteur LLM, résolution d'entités |
| knowledge_graph | client Neo4j, schéma, écriture, requêtes d'exploration |
| retrieval | contrôle d'accès, encodeurs, recherche lexicale et vectorielle, graphe, fusion |
| orchestration | classification, suffisance, conflits, génération, vérification, workflow |
| expert_discovery, recommendations | recherche d'experts, recommandations |
| backend | API, sécurité, schémas d'entrée |
| evaluation | métriques, campagnes, rapport, comparaison de campagnes |

Table: Organisation du code serveur

Un module d'assemblage unique construit les objets partagés (client Neo4j, référentiel, extracteurs, encodeur, pipeline, moteur de recherche, workflow). L'API, les scripts et l'évaluation l'utilisent tous, ce qui garantit une configuration identique partout. La configuration provient de variables d'environnement, lues depuis un fichier non versionné ; un fichier d'exemple aux valeurs fictives documente chaque variable.

## Ingestion et extraction

### Lecture des documents et OCR

Les PDF sont lus avec PyMuPDF, les DOCX avec python-docx, et les PDF sans couche texte sont rendus en images puis traités par Tesseract en français et en anglais. Sur le document scanné du corpus, l'OCR restitue un texte exploitable, avec une confiance moyenne d'environ 94 %, et les relations qu'il contient sont extraites comme pour les autres documents. L'OCR reste l'étape la plus coûteuse de l'ingestion : de six à huit secondes selon les exécutions pour ce seul document.

### Le cartouche, un point critique pour la sécurité

La difficulté la plus instructive de l'ingestion est venue d'un détail de mise en forme. Dans les PDF, les lignes de texte sont souvent coupées, et le nettoyage recolle les lignes qui se suivent pour reconstituer les phrases. Appliqué au cartouche, ce recollement fusionnait les champs « Classification » et « Diffusion » avec les lignes voisines. Résultat : deux documents à diffusion restreinte étaient lus comme diffusés à tous.

Ce défaut n'était pas seulement une erreur de métadonnée : il ouvrait une fuite d'information, puisque la diffusion conditionne le contrôle d'accès. Nous l'avons corrigé en lisant le cartouche avant toute jointure de lignes, avec un analyseur à états qui ne considère que le bloc contigu des champs en tête du document, et en interdisant de recoller une ligne de la forme « champ : valeur ». Un test unitaire vérifie désormais qu'un cartouche de diffusion restreinte est correctement lu, et qu'une ligne « Rédacteur : » placée dans le corps du texte n'écrase pas celle du cartouche. Cet épisode illustre un principe que nous retenons : dans un système soumis à des règles d'accès, toute étape qui touche aux métadonnées de diffusion doit être testée comme un contrôle de sécurité.

D'autres ajustements, plus classiques, ont porté sur les puces isolées, les listes numérotées prises à tort pour des titres de section et la détection des en-têtes répétés.

### Extraction par règles

Les dix-huit règles ont été mises au point sur les documents D01 à D20. Plusieurs difficultés propres au français administratif ont dû être traitées : les énumérations, les titres accolés aux noms, les affiliations entre parenthèses, les sujets implicites (« elle relève du pôle Production », où « elle » désigne la procédure décrite par le document) et les pronoms. Un défaut détecté tardivement en est un bon exemple : un pronom en début de phrase était rattaché à une mention « virtuelle » lointaine, ce qui produisait un fait erroné (« le projet Sentinel a livré CoreNova »). La correction, qui place le pronom à sa position réelle, a été consignée dans le journal comme une modification postérieure au gel des règles, puisqu'elle a été découverte sur un document de test.

## Le graphe dans Neo4j

### Écriture idempotente

L'écriture d'un document dans le graphe commence par détacher ses anciennes preuves, puis recrée ses passages, ses mentions et ses relations avec des instructions de fusion (`MERGE`), qui créent un élément s'il n'existe pas et le réutilisent sinon. Réingérer un document inchangé ne modifie donc rien, et réingérer un document modifié remplace exactement sa contribution. Une difficulté technique est apparue lors de la suppression : une même requête ne peut pas lire une relation qu'elle vient de supprimer. Nous avons séparé la mise à jour des listes de provenance et la suppression des relations devenues sans source en deux instructions distinctes.

### Requêtes paramétrées et index

Toutes les requêtes sont paramétrées : les valeurs fournies par l'utilisateur ne sont jamais concaténées dans le texte de la requête. La recherche plein texte demande une précaution supplémentaire, car la syntaxe Lucene interprète certains caractères et les mots « AND », « OR » ou « NOT ». La question est donc découpée en termes, mise en minuscules et échappée avant d'être transmise. Les index vectoriel et plein texte ont été créés et vérifiés sur Neo4j 5.26 Community.

### Un défaut de reproductibilité

En comparant deux campagnes d'évaluation séparées par une réingestion complète, nous avons constaté que l'exactitude de l'architecture GraphRAG variait (0,561 puis 0,530), alors que deux exécutions sur la même base donnaient des résultats identiques. L'analyse a révélé trois causes : l'énumération des chemins du sous-graphe était tronquée à 600 chemins sans ordre défini, des tris ne départageaient pas les ex æquo, et certaines requêtes limitaient leurs résultats sans les ordonner. Dans ces trois cas, le résultat dépendait de l'ordre interne de stockage, qui change à chaque réingestion.

Nous avons remplacé l'énumération des chemins par une expansion niveau par niveau, qui produit exactement le même ensemble de relations sans troncature, départagé systématiquement les ex æquo par identifiant, arrondi les scores avant tri et ordonné toutes les requêtes avant de les limiter. Deux campagnes séparées par une réingestion ne présentent depuis aucune différence sur 1 056 lignes de résultats. Toutes les campagnes ont été relancées après cette correction, qui ne modifie pas la méthode.

## Recherche et workflow

### Une faiblesse structurelle de la fusion RRF

L'analyse d'une question de développement a mis en évidence une limite de RRF. À la question « Quel est le RTO de CoreNova ? » posée par un ingénieur de la DSI, le passage contenant la réponse était classé premier par la recherche lexicale, grâce au sigle exact, mais absent des classements vectoriel et graphe. Son score fusionné valait 1/61, soit environ 0,016, alors que des passages moyens présents dans les trois classements, au quatrième rang par exemple, obtenaient 3/64, soit environ 0,047. Le bon passage était donc évincé du contexte, et le système s'abstenait.

Nous avons ajouté une garantie par source : le premier passage de chaque source active est toujours conservé dans le contexte, à la place des derniers passages non garantis. Cette modification étant postérieure au gel, ses effets sont rapportés séparément au chapitre 6 ; elle est désactivable par configuration, ce qui permet de reproduire exactement la configuration gelée.

### Le contrôle de suffisance et les listes à puces

Un autre ajustement concerne le contrôle de suffisance. Pour une question demandant une valeur, il vérifie qu'une phrase du contexte associe un chiffre à l'objet de la question. Or, dans les procédures, les valeurs figurent souvent dans des listes : « La fréquence de revue périodique est modifiée comme suit : clients à risque élevé : tous les 12 mois ». Analysée isolément, la puce ne mentionne pas la revue périodique, et le contrôle échouait. Nous avons introduit la notion d'unité de sens, qui associe une phrase d'introduction à ses puces, et une ligne de tableau aux intitulés de ses colonnes. Le générateur extractif utilise la même notion.

## API et sécurité

L'API expose une vingtaine de points d'accès : authentification, questions, exploration du graphe, experts, recommandations, documents, ingestion et métriques. L'authentification par mot de passe produit un jeton signé, valable huit heures, qui porte l'identité, les rôles et les groupes de diffusion. Chaque point d'accès déclare le rôle requis, et ceux qui renvoient du contenu calculent la liste des documents autorisés pour l'utilisateur.

Une relecture de l'API a mis en évidence une fuite d'information secondaire : le détail d'un document renvoyait le chemin du fichier sur le serveur. Ce champ, comme la signature de dédoublonnage, n'est plus exposé, et un test le vérifie. Les réponses portent des en-têtes de sécurité, les journaux sont structurés et masquent tout ce qui ressemble à une clé ou à un mot de passe, et une limitation de débit protège la connexion et les questions.

## Interface utilisateur

L'interface est une application React écrite en TypeScript. Sa conception visuelle se veut sobre : fond clair et chaleureux, titres à empattements, contrastes suffisants et adaptation automatique au mode sombre du système. Elle comporte six pages : accueil, assistant, exploration du graphe, experts (réservée aux managers), recommandations et documents, avec des fonctions d'administration réservées aux administrateurs. Les captures suivantes ont été réalisées sur la plateforme réelle, déployée avec Docker Compose et alimentée par le corpus de démonstration.

![Page d'accueil : indicateurs du graphe, périmètre d'accès et questions d'exemple](../figures/captures/capture_accueil.png){width=15cm}

L'assistant affiche la réponse avec ses citations cliquables, le type de question et la stratégie retenue, puis, dans une colonne dédiée, les passages sources avec leur référence, leur version et leur statut. Les faits du graphe mobilisés, les chemins de raisonnement, le rapport de vérification et la trace du workflow sont accessibles sous la réponse.

![Assistant : réponse à une question relationnelle, avec faits du graphe et passages sources](../figures/captures/capture_assistant_relationnel.png){width=15cm}

Lorsque des sources se contredisent, l'assistant le signale et privilégie la source normative en vigueur. Lorsque l'utilisateur n'a pas accès aux documents qui contiennent la réponse, il s'abstient sans rien laisser paraître de leur contenu.

![Assistant : signalement de valeurs divergentes entre la procédure en vigueur et d'autres documents](../figures/captures/capture_assistant_contradiction.png){width=15cm}

![Assistant : abstention motivée pour un utilisateur qui n'est pas destinataire du plan de continuité](../figures/captures/capture_assistant_abstention.png){width=15cm}

L'explorateur permet de rechercher une entité, d'afficher son voisinage à une ou deux relations et de consulter, pour chaque relation, ses documents sources et ses citations. Une vue tabulaire des relations complète la visualisation pour les utilisateurs qui naviguent au clavier.

![Explorateur : voisinage de l'application CoreNova et fiche de l'entité](../figures/captures/capture_explorateur.png){width=15cm}

![Recherche d'experts : classement justifié par des preuves documentaires](../figures/captures/capture_experts.png){width=15cm}

![Recommandations : documents liés à la procédure de connaissance client, avec leurs raisons](../figures/captures/capture_recommandations.png){width=15cm}

![Documents : catalogue filtrable et détail d'un document (vue administrateur)](../figures/captures/capture_documents.png){width=15cm}

L'interface a été vérifiée par un parcours automatisé sur la plateforme réelle, sous quatre profils d'utilisateurs, avec relevé des erreurs de console et des violations de la politique de sécurité du contenu. Ce parcours a révélé deux défauts, corrigés depuis : la bibliothèque de visualisation injectait une feuille de style en ligne, refusée par la politique de sécurité stricte que nous appliquons, et la barre de navigation élargissait la page sur un écran de téléphone. Nous avons préféré corriger la cause plutôt qu'assouplir la politique de sécurité.

![Assistant sur écran de téléphone : signalement d'une question ambiguë](../figures/captures/capture_mobile.png){width=6cm}

## Conteneurisation, exploitation et intégration continue

La plateforme est déployée avec Docker Compose sous la forme de trois services : la base Neo4j, le serveur et l'interface. La base n'expose aucun port à l'extérieur. Le serveur et l'interface s'exécutent sous un utilisateur non privilégié, avec un système de fichiers en lecture seule et sans capacités système. Des sondes de santé conditionnent l'ordre de démarrage. Une surcharge de configuration prépare un déploiement sur un serveur exposé, avec un proxy inverse Caddy qui obtient et renouvelle automatiquement les certificats TLS ; elle a été validée syntaxiquement, mais aucun déploiement distant n'a été réalisé.

![Déploiement avec Docker Compose](../figures/schema_deploiement.png){width=16cm}

Neo4j Community ne permettant pas de sauvegarde à chaud, la sauvegarde arrête brièvement la base, produit un export, archive les fichiers téléversés et calcule leurs empreintes. Nous avons testé la procédure complète : sauvegarde, suppression volontaire de tout le contenu de la base, puis restauration, qui a retrouvé les 315 nœuds initiaux. Nous avons également vérifié la persistance des données après arrêt et redémarrage des services, et l'ingestion du corpus à l'intérieur du conteneur.

L'intégration continue, décrite dans un fichier GitHub Actions, enchaîne l'analyse statique du code, les tests unitaires, les tests d'intégration avec une base Neo4j de service, la compilation de l'interface, l'audit des vulnérabilités connues des dépendances, la recherche de secrets dans l'historique et la construction des images. La recherche de secrets a été exécutée localement sur tout l'historique sans signalement.

## Tests automatisés

La suite compte 106 cas de test. Les 69 tests unitaires n'ont besoin ni de base de données, ni de réseau, ni de clé d'API : ils couvrent le nettoyage, les métadonnées, le découpage, la validation des fichiers, la détection d'injection, MinHash, l'extraction, la résolution d'entités, la fusion, le PageRank personnalisé, la classification, la suffisance, les conflits, la génération, la vérification, la sécurité et les clients LLM, ces derniers à l'aide de réponses simulées. Les 37 tests d'intégration s'exécutent sur une base Neo4j dédiée, vidée à chaque exécution : ingestion réelle du corpus, idempotence, cycle de vie d'un document, versions, contrôle d'accès dans la recherche, le graphe et l'API, comportement du workflow (réponse, abstention, contradiction, LLM simulé qui invente une citation ou ne cite rien, panne du fournisseur), experts et recommandations.

## Difficultés rencontrées et enseignements

| Difficulté | Cause | Solution | Enseignement |
|---|---|---|---|
| Documents restreints lus comme diffusés à tous | recollement des lignes appliqué au cartouche | lecture du cartouche avant tout nettoyage, test dédié | traiter les métadonnées de diffusion comme un contrôle de sécurité |
| Passage pertinent évincé du contexte | un passage premier dans une seule source est noyé par RRF | garantie par source, évaluée à part | une méthode robuste en moyenne peut échouer sur des cas typiques du métier |
| Résultats variables après réingestion | troncatures et tris dépendants de l'ordre interne | expansion par niveaux, départage, ORDER BY | tester la reproductibilité entre réingestions, pas seulement entre exécutions |
| Valeurs non détectées dans les listes | puces analysées sans leur introduction | unités de sens | la structure des documents porte du sens |
| Encodeur vectoriel peu performant | vecteurs de mots moyennés | ablation, encodeur WordLlama | mesurer avant de conclure sur la recherche vectorielle |
| Style en ligne refusé par la sécurité du navigateur | injection par la bibliothèque de graphes | règle fournie par notre feuille de style | corriger la cause plutôt qu'assouplir la politique |
| Fait erroné avec un pronom | rattachement à une mention lointaine | position réelle du pronom, journalisée post-gel | consigner toute correction découverte sur les données de test |

Table: Difficultés rencontrées, solutions et enseignements
