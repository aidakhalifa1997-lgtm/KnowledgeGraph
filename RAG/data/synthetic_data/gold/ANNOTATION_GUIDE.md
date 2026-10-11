# Guide d'annotation des relations (vérité terrain)

Objectif : disposer d'annotations **cohérentes et vérifiables** pour mesurer l'extraction.
Principe général : on annote une relation **si et seulement si le document l'affirme**, de façon
explicite ou par une formulation dont le sens est univoque pour un lecteur métier. On n'annote
**jamais** une relation simplement plausible ou connue par ailleurs.

| Relation | Annoter quand le texte… | Ne pas annoter quand… |
|---|---|---|
| WORKS_IN | rattache une personne à une entité : titre (« Directrice Conformité »), « responsable du Pôle X », « analyste à la Cellule KYC », affiliation entre parenthèses « (DSI) », « X et Y pour la Cellule KYC » dans une liste d'équipe | la personne est seulement *désignée pour* une entité (correspondant PCA « pour la DSI ») ou *invitée* à une réunion |
| PART_OF | indique qu'une entité est rattachée à une autre (« Pôle X de la DSI », « rattachée à », « fait partie de ») | — |
| HAS_EXPERTISE | qualifie la compétence de la personne : expert, spécialiste, compétences, maîtrise, expérience, référent, ou titre professionnel nommant le domaine (« architecte SI ») | la personne travaille simplement sur un sujet, assiste à une réunion ou dirige une entité |
| PARTICIPATES_IN | décrit un rôle dans un projet : chef de projet / porteur (lead), sponsor, membre d'équipe, appui, contribution explicite (« le modèle développé par X ») | la personne est seulement présente à un comité ou destinataire d'un document |
| RESPONSIBLE_FOR | désigne le propriétaire d'une procédure ou le responsable applicatif / fonctionnel d'un système | la personne utilise ou valide simplement |
| OWNS | désigne l'entité propriétaire d'une procédure (« relève de », « portée par ») | — |
| DELIVERS | affirme qu'un projet déploie / met en place / a livré un système | le document parle seulement du pilote ou de l'usage du système |
| IMPACTS | affirme qu'un projet révise une procédure ou modifie un système (« réviser », « faire évoluer », « intègre les apports du projet ») | le projet teste ou utilise seulement le système |
| DEPENDS_ON | affirme une dépendance (« dépend de », « s'appuie sur », « alimenté par », « repose sur ») entre deux systèmes ou deux projets | — |
| USES | une étape de la procédure s'effectue dans le système (« saisi dans », « archivé dans », « au moyen de ») | le système n'est cité qu'à propos d'un autre système |
| REFERENCES | la procédure renvoie à une autre (« conformément à la procédure », « selon la procédure ») | — |

## Arbitrages documentés (avant toute évaluation sur l'ensemble de test)

Les ajustements ci-dessous ont été faits en relisant le texte des documents à la lumière de ce
guide. Ils ne s'appuient pas sur les sorties du système pour l'ensemble de test.

- D12 : retrait de `prj:sentinel DELIVERS sys:sentinel-kyc` (le rapport décrit le pilote, sans affirmer la livraison).
- D19 : retrait de `prj:resilience IMPACTS sys:corenova` (un test de bascule ne modifie pas le système).
- D17 : ajout de `sys:amlwatch DEPENDS_ON sys:corenova` (« AML Watch reste par ailleurs alimenté par CoreNova »).
- D05 : retrait de `prc:PRC-REC-003 USES sys:orion-crm` (Orion n'est cité que comme source de Réclam'Online).
- D02 : ajout de `prc:PRC-KYC-001 REFERENCES prc:PRC-LAB-005` (« selon la procédure PRC-LAB-005 »).
- D28 (relecture de l'ensemble de test, texte seul) : retrait de `sys:sentinel-kyc DEPENDS_ON sys:corenova` (dépendance suggérée par un impact, non affirmée).
- Relations de rattachement par titre ou par parenthèse (WORKS_IN) ajoutées sur l'ensemble du corpus après relecture systématique.

## Journal des modifications du système après le gel des règles

| Date | Modification | Origine | Effet sur l'impartialité du test |
|---|---|---|---|
| 2026-10-11 | Pronom en début de phrase positionné à sa place réelle (au lieu d'une mention « virtuelle » lointaine) | Fait erroné observé lors d'une démonstration de recherche (D29, document de test) : « Projet Sentinel a livré CoreNova » | Le cas D29 n'est plus strictement aveugle ; correction générique (non spécifique au document) |

## Limites

Un seul annotateur, qui est aussi l'auteur du corpus et des règles : pas d'accord inter-annotateurs
mesurable, risque de biais de conception. Les scores d'extraction obtenus sur ce corpus sont donc
indicatifs et optimistes.
