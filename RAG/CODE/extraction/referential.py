"""Chargement des référentiels maîtres (catalogue d'entités canoniques).

Le référentiel fournit, pour chaque entité : un identifiant stable, un type, un nom canonique
et des alias. Il ne contient aucune relation entre entités, à l'exception de la taxonomie
des domaines (concept/procédure/projet -> domaine).

Des alias « de fonction » sont dérivés automatiquement pour les directions :
« Direction Conformité » -> « Directrice Conformité », « Directeur Conformité ». Ces formes
désignent la personne qui dirige l'entité et servent à détecter le rattachement d'une
personne citée avec son titre.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from core.ontology import entity_type_from_id

_SECTIONS = {
    "departments": "Department", "people": "Person", "systems": "System", "projects": "Project",
    "procedures": "Procedure", "domains": "Domain", "concepts": "Concept",
}


@dataclass
class RefEntity:
    id: str
    type: str
    name: str
    aliases: list[str] = field(default_factory=list)
    title_aliases: list[str] = field(default_factory=list)
    domain: str | None = None
    code: str | None = None

    @property
    def all_surfaces(self) -> list[str]:
        return [self.name, *self.aliases]


@dataclass
class AmbiguousAlias:
    surface: str
    candidates: list[tuple[str, list[str]]]  # (entity_id, indices de contexte)


@dataclass
class Referential:
    entities: dict[str, RefEntity]
    ambiguous: list[AmbiguousAlias]

    def by_type(self, entity_type: str) -> list[RefEntity]:
        return [e for e in self.entities.values() if e.type == entity_type]

    def get(self, entity_id: str) -> RefEntity | None:
        return self.entities.get(entity_id)

    def name(self, entity_id: str) -> str:
        entity = self.entities.get(entity_id)
        return entity.name if entity else entity_id

    def project_by_code(self, code: str) -> RefEntity | None:
        code = code.upper()
        return next((e for e in self.entities.values() if e.type == "Project" and e.code == code), None)


def _title_aliases(name: str) -> list[str]:
    if name.startswith("Direction "):
        rest = name[len("Direction "):]
        return [f"Directeur {rest}", f"Directrice {rest}"]
    return []


def load_referential(path: str | Path) -> Referential:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    entities: dict[str, RefEntity] = {}
    for section, entity_type in _SECTIONS.items():
        for item in data.get(section, []):
            assert entity_type_from_id(item["id"]) == entity_type, f"préfixe incohérent : {item['id']}"
            entities[item["id"]] = RefEntity(
                id=item["id"], type=entity_type, name=item["name"], aliases=list(item.get("aliases", [])),
                title_aliases=_title_aliases(item["name"]) if entity_type == "Department" else [],
                domain=item.get("domain"), code=item.get("code"),
            )
    ambiguous = [
        AmbiguousAlias(surface=a["surface"], candidates=[(c["id"], list(c.get("cues", []))) for c in a["candidates"]])
        for a in data.get("ambiguous_aliases", [])
    ]
    return Referential(entities=entities, ambiguous=ambiguous)


@lru_cache(maxsize=4)
def get_referential(path: str) -> Referential:
    return load_referential(path)
