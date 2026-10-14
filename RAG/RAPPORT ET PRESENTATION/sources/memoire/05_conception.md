# Conception de la solution

Ce chapitre présente la conception de la plateforme. Nous en donnons d'abord une vue d'ensemble, puis nous détaillons le modèle de connaissances, le pipeline d'ingestion, l'extraction, la stratégie de recherche et le workflow de questions-réponses. Nous abordons ensuite la recherche d'experts, les recommandations et la sécurité, avant de justifier les choix technologiques.

## Vue d'ensemble de l'architecture

La plateforme est organisée en couches. L'interface web, exécutée dans le navigateur, dialogue avec une API qui authentifie l'utilisateur, vérifie son rôle et applique les protections d'usage. L'API délègue le traitement à des services métier : workflow de questions-réponses, recherche d'experts, recommandations, exploration du graphe et gestion des documents. Ces services s'appuient sur une couche de récupération de l'information, sur le graphe stocké dans Neo4j et, en amont, sur le pipeline d'ingestion qui alimente ce graphe. Un fournisseur de LLM peut être branché, mais il est optionnel : la plateforme fonctionne entièrement sans lui.

![Architecture en couches de la plateforme](../figures/schema_architecture.png){width=16cm}

Trois principes ont guidé cette conception.

**La provenance avant tout.** Chaque relation du graphe conserve les documents, passages et citations qui la justifient. Une information qui ne peut pas être rattachée à une source n'entre pas dans le graphe et ne peut donc pas apparaître dans une réponse.

**Le contrôle d'accès en amont.** L'ensemble des documents autorisés pour l'utilisateur est calculé avant toute recherche et appliqué dans chaque requête. Aucune donnée issue d'un document non autorisé n'entre dans le contexte, dans les faits du graphe ou dans une visualisation.

**Le déterminisme et l'indépendance vis-à-vis du LLM.** Toutes les décisions du traitement (routage, suffisance, abstention, vérification) sont prises par du code. Le LLM, lorsqu'il est disponible, n'intervient que pour l'extraction complémentaire et la rédaction, avec un mécanisme de repli déterministe.

## Modèle de connaissances

### Ontologie

L'ontologie définit sept types d'entités et treize types de relations, avec pour chaque relation les types autorisés pour le sujet et pour l'objet. Toute relation produite par un extracteur est validée contre ces contraintes avant d'être écrite : une relation « personne utilise application », par exemple, est rejetée, car la relation d'usage n'est définie que d'une procédure vers une application.

| Relation | Sujet | Objet | Origine |
|---|---|---|---|
| WORKS_IN | personne | entité organisationnelle | extraite |
| PART_OF | entité organisationnelle | entité organisationnelle | extraite |
| HAS_EXPERTISE | personne | domaine | extraite |
| PARTICIPATES_IN | personne | projet (avec rôle) | extraite |
| RESPONSIBLE_FOR | personne | procédure ou application | extraite |
| OWNS | entité organisationnelle | procédure | extraite |
| DELIVERS | projet | application | extraite |
| IMPACTS | projet | procédure ou application | extraite |
| DEPENDS_ON | application ou projet | application ou projet (même type) | extraite |
| USES | procédure | application | extraite |
| REFERENCES | procédure | procédure | extraite |
| COVERS | procédure ou projet | concept | dérivée par règle |
| BELONGS_TO | concept, procédure ou projet | domaine | référentiel |

Table: Relations de l'ontologie et contraintes de domaine

Les sept types d'entités sont les personnes, les entités organisationnelles (directions, pôles, cellules), les projets, les procédures, les applications, les concepts métier (bénéficiaire effectif, personne politiquement exposée, revue périodique…) et les domaines d'expertise. Chaque type est préfixé dans les identifiants (per, dep, prj, prc, sys, con, dom), ce qui rend les identifiants lisibles et stables.

### Schéma du graphe

Le graphe comporte deux couches. La **couche documentaire** décrit les documents et leurs passages : chaque passage (*chunk*) est relié à son document et au passage suivant, porte son texte, sa section, sa page et son vecteur. Les documents sont reliés entre eux par des relations de version (un document en remplace un autre), de doublon et de similarité. La **couche sémantique** contient les entités et leurs relations. Les deux couches sont reliées par les mentions (un passage mentionne une entité) et par les relations de description, de rédaction et d'émission entre un document et l'entité qu'il décrit, son rédacteur ou la direction émettrice.

![Modèle de données du graphe de connaissances](../figures/schema_modele_graphe.png){width=16cm}

### Une provenance portée par les relations

Le modèle de graphe de propriétés permet d'attacher des informations à une relation. Nous en tirons parti pour stocker, sur chaque relation extraite, des listes alignées : documents sources, passages justificatifs, citations exactes, extracteurs (règles ou LLM) et confiance. Une même relation peut ainsi être attestée par plusieurs documents ; dans notre corpus, 63 relations sur 153 le sont.

Ce choix a deux conséquences importantes. D'une part, la visibilité d'une relation se décide pour chaque utilisateur : elle est visible si au moins un de ses documents sources lui est autorisé, et seules les preuves issues de documents autorisés lui sont montrées. D'autre part, la suppression ou la modification d'un document retire précisément ses preuves des relations partagées, sans effacer la relation si un autre document la confirme.

## Pipeline d'ingestion

Le pipeline transforme un fichier en éléments du graphe. Chaque étape peut interrompre le traitement, et l'issue est consignée dans un rapport d'ingestion.

![Pipeline d'ingestion d'un document](../figures/schema_pipeline_ingestion.png){width=16cm}

1. **Empreinte.** Le contenu est haché (SHA-256). Si l'empreinte est identique à celle déjà enregistrée pour ce fichier, le traitement s'arrête : c'est ce qui rend la réingestion quasi instantanée.
2. **Validation de sécurité.** L'extension, la signature du fichier, sa taille, le nombre de pages d'un PDF et la taille décompressée d'un DOCX sont contrôlés, afin de refuser les fichiers déguisés et les archives piégées.
3. **Extraction du texte.** Le texte est lu selon le format. Si un PDF ne contient pas de texte exploitable, il est traité par OCR.
4. **Nettoyage et métadonnées.** Les en-têtes et pieds de page répétés sont supprimés, les lignes coupées recollées, les puces normalisées. Le cartouche est lu avant toute autre transformation, car c'est lui qui porte la liste de diffusion.
5. **Contrôle qualité.** Un texte trop court est rejeté ; un texte contenant des instructions adressées à un assistant est mis en quarantaine.
6. **Doublons.** Un doublon exact est repéré par son empreinte. Un quasi-doublon est repéré par une signature MinHash (128 permutations, fragments de cinq mots) et une similarité de Jaccard estimée d'au moins 0,8 entre documents de même référence et de même version ; la version officielle est conservée, la copie de travail écartée.
7. **Découpage.** Le texte est découpé en passages qui respectent les sections, d'environ 900 caractères, préfixés du titre du document et de la section pour la recherche.
8. **Extraction et écriture.** Les entités et relations sont extraites, les passages encodés, puis l'ensemble est écrit dans Neo4j de manière idempotente.

Après un lot, une étape de finalisation met à jour les versions (une nouvelle version d'une même référence remplace l'ancienne, qui prend le statut « remplacé »), dérive les relations de taxonomie et de couverture, calcule les similarités entre documents et supprime les entités devenues orphelines.

## Extraction des connaissances

### Un extracteur par règles comme socle

L'extracteur principal est déterministe. Il repère d'abord les mentions d'entités grâce au référentiel, en privilégiant la correspondance la plus longue (« plateforme Sentinel KYC » plutôt que « Sentinel »). Il applique ensuite dix-huit règles déclarées dans un fichier de configuration. Chaque règle associe des déclencheurs lexicaux (« dépend de », « est rattaché à », « pilote le projet »…) à un type de relation, et précise où chercher le sujet et l'objet. Les règles traitent des cas fréquents dans les documents administratifs : énumérations (« Orion CRM, AML Watch et Sentinel KYC dépendent de CoreNova »), titres (« Mme Salma Idrissi, Directrice Conformité »), affiliations entre parenthèses, sujet implicite renvoyant au document décrit, et pronoms.

Ce choix peut surprendre à l'heure des LLM. Il répond à trois besoins : fonctionner sans clé d'API, produire des résultats reproductibles et disposer d'une référence mesurable. Il a aussi un coût : les règles couvrent les formulations prévues et manquent les autres, ce que l'évaluation sur les documents de test met en évidence.

### Un extracteur par LLM, contraint et vérifié

Lorsqu'un LLM est configuré, un second extracteur peut compléter le premier. Sa sortie est contrainte par un schéma JSON et validée par Pydantic. Chaque relation proposée doit respecter l'ontologie, ses entités doivent être résolues dans le référentiel, et la citation fournie comme preuve doit figurer dans le passage source ; à défaut, la relation est rejetée. Sa confiance est plafonnée à 0,8. Lorsque les deux extracteurs proposent la même relation, leur accord renforce la confiance. Cet extracteur est implémenté et testé avec des réponses simulées ; il n'a pas été évalué avec un vrai modèle.

### Résolution d'entités

La résolution d'entités suit une cascade : correspondance exacte d'un nom ou d'un alias après normalisation, retrait des civilités, gestion des initiales, désambiguïsation des alias ambigus par des indices de contexte, puis comparaison approximative des chaînes. Pour cette dernière, nous reprenons les trois zones de Fellegi et Sunter (1969) : au-dessus d'un score de 90, la mention est liée ; entre 80 et 90, elle est signalée comme correspondance possible sans être liée ; en dessous, elle est ignorée.

## Recherche hybride et GraphRAG local

### Trois sources complémentaires

La récupération combine trois sources, toutes restreintes aux documents autorisés.

- La **recherche lexicale** interroge l'index plein texte de Neo4j avec l'analyseur français. La question est transformée en une requête dont les caractères spéciaux sont échappés et les opérateurs neutralisés, de sorte que l'utilisateur ne puisse pas modifier la syntaxe de la recherche.
- La **recherche vectorielle** interroge l'index HNSW avec le vecteur de la question.
- La **recherche par le graphe** reconnaît les entités de la question, explore leur voisinage jusqu'à deux relations, puis applique un PageRank personnalisé (probabilité de retour aux entités de départ de 0,15), inspiré de HippoRAG (Gutiérrez et al., 2024). Les relations qui correspondent à l'intention de la question (« dépend », « équipe », « expert »…) pèsent trois fois plus. Les relations les mieux classées deviennent des faits citables (F1, F2…), et les passages qui les prouvent ou qui mentionnent les entités importantes sont classés.

### Fusion et routage

Les trois classements sont fusionnés par RRF avec k = 60 (Cormack et al., 2009), et les huit meilleurs passages forment le contexte. Le poids du graphe dans la fusion dépend du type de question, déterminé par un classifieur déterministe fondé sur des indices lexicaux et sur les entités reconnues.

| Type de question | Exemple | Poids du graphe | Profondeur |
|---|---|---|---|
| Factuelle | Quel est le délai d'accusé de réception ? | 0,5 | 1 |
| Relationnelle | Qui fait partie de l'équipe du projet Sentinel ? | 1,0 | 2 |
| Multi-sauts | Quel projet dépend d'un projet piloté par cette personne ? | 1,5 | 2 |
| Expertise | Qui est expert en lutte anti-blanchiment ? | 1,0 | 1 |
| Ambiguë | Qui est responsable de Sentinel ? | 1,0 | 2 |

Table: Routage des questions selon leur type

Après la campagne principale, nous avons ajouté une garantie : le premier passage de chaque source est toujours conservé dans le contexte. Cette modification, motivée par une faiblesse structurelle de RRF que nous décrivons au chapitre 5, est désactivable et évaluée séparément.

## Workflow de questions-réponses

Le traitement d'une question est un graphe d'états déclaré avec LangGraph. L'état, typé, porte la question, les droits de l'utilisateur, la route choisie, les passages, les faits, le diagnostic de suffisance, la réponse et le rapport de vérification. Chaque nœud ajoute sa durée et ses décisions à une trace renvoyée avec la réponse.

![Workflow de questions-réponses orchestré par LangGraph](../figures/schema_workflow.png){width=16cm}

**Analyse.** Le nœud reconnaît les entités, classe la question, choisit la stratégie et calcule les documents autorisés.

**Récupération.** Il applique la stratégie retenue et produit le contexte.

**Contrôle de suffisance.** Inspiré de Corrective RAG (Yan et al., 2024), ce nœud vérifie que le contexte couvre la question avant toute génération. Il calcule une couverture des termes de la question pondérée par leur rareté (un terme rare comme « budget » compte davantage qu'un terme fréquent comme « procédure ») et vérifie la présence des entités de la question : toutes si la question en cite une ou deux, au moins la moitié au-delà. Lorsque la question demande une valeur (délai, seuil, taux), il exige en outre qu'une unité de sens du contexte associe une valeur chiffrée à l'objet de la question. Le seuil de couverture, fixé a priori à 0,55, fait l'objet d'une analyse de sensibilité. Ce nœud détecte aussi les versions multiples d'un même document et les valeurs divergentes.

**Relance.** Si le contexte est insuffisant au premier essai, le workflow enrichit la recherche (entités citées par les meilleurs passages, alias, exploration à deux relations) et recommence une fois.

**Génération ou abstention.** Si le contexte reste insuffisant, le système s'abstient en indiquant les éléments manquants et les documents consultés. Sinon, il génère la réponse. En mode hors-ligne, un générateur extractif sélectionne les phrases les plus pertinentes du contexte et les faits du graphe mobilisés, et les présente avec leurs citations : il ne reformule rien et ne peut donc pas inventer, mais il ne synthétise pas non plus. Avec un LLM, le prompt délimite les documents comme des données et impose les citations.

**Vérification.** Le dernier nœud supprime les citations qui ne correspondent à aucune source, mesure l'appui de chaque phrase sur les sources citées, retire les liens, images, adresses et balises HTML (vecteurs d'exfiltration) et bloque toute fuite des consignes du système. Si une réponse produite par un LLM ne contient aucune citation valide, elle est remplacée par la réponse extractive.

## Recherche d'experts et recommandations

### Experts

Suivant l'approche centrée documents de Balog et al. (2006), l'expertise d'une personne dans un domaine est estimée par l'agrégation de preuves documentaires typées. Les poids traduisent la force probante de chaque type de preuve : 3 pour une expertise déclarée dans un document, 2 pour le pilotage d'un projet du domaine ou la propriété d'une procédure du domaine, 1 pour la participation à un projet ou la responsabilité d'une application, 0,8 pour la rédaction d'un document, 0,3 pour le parrainage d'un projet, et 0,1 seulement par simple co-mention, avec un plafond de 0,5. Une preuve perd la moitié de son poids en trois ans. Chaque résultat est présenté avec sa justification et ses preuves, et accompagné d'un avertissement sur ses limites.

### Recommandations

La recommandation d'un document combine trois composantes : la similarité de contenu entre documents, le recouvrement des entités citées et la proximité dans le graphe (versions, objet décrit commun, relations). En mode hybride, elles sont pondérées respectivement à 40 %, 30 % et 30 %. Chaque recommandation est accompagnée des raisons qui la justifient (« version antérieure du même document », « décrit le même élément »…). Les doublons et les documents en quarantaine ne sont jamais recommandés.

## Sécurité dès la conception

La sécurité n'a pas été ajoutée après coup : elle structure plusieurs choix déjà présentés. Le tableau suivant récapitule les menaces prises en compte et les mesures correspondantes.

| Menace | Mesure |
|---|---|
| Accès à un document non diffusé | documents autorisés calculés avant la recherche et appliqués à chaque requête, aux faits et aux visualisations |
| Injection d'instructions dans un document | détection et quarantaine à l'ingestion ; documents présentés comme des données ; aucun outil confié au LLM |
| Exfiltration par la réponse | suppression des liens, images, adresses et balises ; blocage des fuites de consignes |
| Fichier malveillant | validation de l'extension, de la signature, de la taille et de la compression |
| Usurpation d'identité | mots de passe hachés (PBKDF2-SHA256, 600 000 itérations), jetons signés à durée limitée |
| Abus et épuisement du quota | limitation de débit par utilisateur et à la connexion |
| Fuite de secrets | secrets en variables d'environnement, masqués dans les journaux, jamais versionnés |
| Injection dans les requêtes | requêtes Cypher paramétrées ; échappement de la recherche plein texte |

Table: Menaces et mesures de sécurité

Les rôles sont hiérarchisés : un lecteur consulte, un manager accède en plus à la recherche d'experts, un administrateur gère les documents et l'ingestion.

## Choix technologiques

Le tableau suivant résume les choix structurants et leur justification. Le dossier de documentation technique du projet les détaille.

| Besoin | Choix | Alternatives étudiées | Justification |
|---|---|---|---|
| Graphe, recherche lexicale et vectorielle | Neo4j 5.26 Community | PostgreSQL avec extension vectorielle, base RDF, Memgraph | graphe de propriétés adapté à la provenance ; index plein texte et vectoriel dans la même base ; Cypher lisible |
| Orchestration | LangGraph | code Python séquentiel, agent | transitions conditionnelles explicites, état typé, trace ; pas de décision laissée au LLM |
| API | FastAPI et Pydantic | Flask, Django | validation des entrées, documentation automatique, performances |
| Extraction du texte et OCR | PyMuPDF, python-docx, Tesseract | services d'OCR en ligne | traitement local, sans envoi de documents à un tiers |
| Encodeur | WordLlama (256 dimensions) | vecteurs spaCy moyennés, modèles de phrases | utilisable hors-ligne ; meilleur que spaCy dans notre ablation |
| Résolution approximative | rapidfuzz | distance d'édition maison | rapide, éprouvé |
| Interface | React, TypeScript, Cytoscape.js | gabarits côté serveur, D3 | composants typés, visualisation de graphes interactive |
| Déploiement | Docker Compose, nginx, Caddy | installation manuelle, orchestrateur | reproductible, adapté à un pilote ; TLS automatique |

Table: Choix technologiques et justification

Ces choix privilégient la simplicité et la maîtrise. Une banque pourrait légitimement retenir d'autres briques, par exemple une base relationnelle déjà exploitée en interne ; l'architecture en couches limiterait alors l'effort de substitution à la couche d'accès aux données.
