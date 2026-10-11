"""Ontologie (schéma conceptuel) du Knowledge Graph.

Ce module est la source de vérité sur :
- les types d'entités autorisés ;
- les types de relations autorisés, avec leurs contraintes de domaine (type du sujet) et de
  codomaine (type de l'objet) ;
- la verbalisation française des relations (utilisée pour les explications et le prompt).

Toute relation produite par un extracteur (règles ou LLM) est validée contre ces contraintes
avant d'être écrite dans Neo4j : une relation `Person -[USES]-> Concept`, par exemple, est
rejetée car `USES` n'est défini que de `Procedure` vers `System`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

ENTITY_TYPES: dict[str, str] = {
    "Person": "Personne (collaborateur, expert, responsable)",
    "Department": "Entité organisationnelle (direction, pôle, cellule, service)",
    "Project": "Projet ou programme",
    "Procedure": "Procédure, politique ou mode opératoire normatif",
    "System": "Application, outil ou système d'information",
    "Concept": "Concept métier (notion réglementaire, règle, indicateur)",
    "Domain": "Domaine fonctionnel ou d'expertise",
}

ID_PREFIX_TO_TYPE = {
    "per": "Person",
    "dep": "Department",
    "prj": "Project",
    "prc": "Procedure",
    "sys": "System",
    "con": "Concept",
    "dom": "Domain",
}
TYPE_TO_ID_PREFIX = {v: k for k, v in ID_PREFIX_TO_TYPE.items()}


@dataclass(frozen=True)
class RelationSpec:
    name: str
    subject_types: frozenset[str]
    object_types: frozenset[str]
    verb_fr: str
    description: str
    extracted: bool = True  # False : relation dérivée (règle métier) ou issue d'un référentiel
    properties: tuple[str, ...] = field(default_factory=tuple)


RELATIONS: dict[str, RelationSpec] = {
    spec.name: spec
    for spec in [
        RelationSpec("WORKS_IN", frozenset({"Person"}), frozenset({"Department"}), "travaille au sein de",
                     "Rattachement d'une personne à une entité organisationnelle."),
        RelationSpec("PART_OF", frozenset({"Department"}), frozenset({"Department"}), "fait partie de",
                     "Rattachement hiérarchique d'une entité à une autre."),
        RelationSpec("HAS_EXPERTISE", frozenset({"Person"}), frozenset({"Domain"}), "a une expertise en",
                     "Expertise explicitement affirmée dans un document."),
        RelationSpec("PARTICIPATES_IN", frozenset({"Person"}), frozenset({"Project"}), "participe au projet",
                     "Participation à un projet ; propriété `roles` (lead, sponsor, member).", properties=("roles",)),
        RelationSpec("RESPONSIBLE_FOR", frozenset({"Person"}), frozenset({"Procedure", "System"}), "est responsable de",
                     "Propriétaire d'une procédure ou responsable applicatif d'un système."),
        RelationSpec("OWNS", frozenset({"Department"}), frozenset({"Procedure"}), "est propriétaire de",
                     "Entité propriétaire d'une procédure (gouvernance documentaire)."),
        RelationSpec("DELIVERS", frozenset({"Project"}), frozenset({"System"}), "a livré",
                     "Système mis en place par un projet."),
        RelationSpec("IMPACTS", frozenset({"Project"}), frozenset({"Procedure", "System"}), "a impacté",
                     "Procédure révisée ou système modifié par un projet."),
        RelationSpec("DEPENDS_ON", frozenset({"System", "Project"}), frozenset({"System", "Project"}), "dépend de",
                     "Dépendance technique (système) ou de planning (projet) ; sujet et objet de même type."),
        RelationSpec("USES", frozenset({"Procedure"}), frozenset({"System"}), "s'appuie sur l'outil",
                     "Outil utilisé pour exécuter une procédure."),
        RelationSpec("REFERENCES", frozenset({"Procedure"}), frozenset({"Procedure"}), "renvoie à",
                     "Renvoi explicite d'une procédure vers une autre."),
        RelationSpec("COVERS", frozenset({"Procedure", "Project"}), frozenset({"Concept"}), "traite de",
                     "Dérivée par règle : concepts mentionnés dans le document qui décrit la procédure/le projet.",
                     extracted=False),
        RelationSpec("BELONGS_TO", frozenset({"Concept", "Procedure", "Project"}), frozenset({"Domain"}),
                     "relève du domaine", "Taxonomie issue du référentiel documentaire.", extracted=False),
    ]
}

EXTRACTED_RELATIONS = [name for name, spec in RELATIONS.items() if spec.extracted]
PARTICIPATION_ROLES = ("lead", "sponsor", "member")


def entity_type_from_id(entity_id: str) -> str | None:
    prefix = entity_id.split(":", 1)[0]
    return ID_PREFIX_TO_TYPE.get(prefix)


def validate_relation(subject_type: str, relation: str, object_type: str) -> tuple[bool, str]:
    """Vérifie qu'une relation respecte le schéma. Retourne (valide, motif)."""
    spec = RELATIONS.get(relation)
    if spec is None:
        return False, f"type de relation inconnu : {relation}"
    if subject_type not in spec.subject_types:
        return False, f"{relation} : sujet de type {subject_type} non autorisé"
    if object_type not in spec.object_types:
        return False, f"{relation} : objet de type {object_type} non autorisé"
    if relation == "DEPENDS_ON" and subject_type != object_type:
        return False, "DEPENDS_ON : le sujet et l'objet doivent être de même type"
    return True, "ok"


def verbalize(subject_name: str, relation: str, object_name: str, roles: list[str] | None = None) -> str:
    spec = RELATIONS.get(relation)
    verb = spec.verb_fr if spec else relation.lower()
    if relation == "PARTICIPATES_IN" and roles:
        labels = {"lead": "pilote", "sponsor": "sponsor", "member": "membre"}
        role_txt = ", ".join(labels.get(r, r) for r in roles)
        return f"{subject_name} {verb} {object_name} ({role_txt})"
    return f"{subject_name} {verb} {object_name}"
