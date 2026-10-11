"""Chargement des jeux de référence (corpus fictif)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from core.settings import DATA_DIR

SYNTH = DATA_DIR / "synthetic_data"
SOURCES = SYNTH / "sources"
GOLD = SYNTH / "gold"
DEV_DOCS = {f"D{i:02d}" for i in range(1, 21)}
TEST_DOCS = {f"D{i:02d}" for i in range(21, 36)}


@dataclass
class GoldDocument:
    doc_id: str
    file_name: str
    relations: set[tuple[str, str, str]]
    roles: dict[tuple[str, str, str], str]
    mentions: set[str]
    meta: dict


def load_gold_documents() -> dict[str, GoldDocument]:
    docs: dict[str, GoldDocument] = {}
    for path in sorted(SOURCES.glob("D*.md")):
        raw = path.read_text(encoding="utf-8")
        meta = yaml.safe_load(re.match(r"^---\n(.*?)\n---\n", raw, re.S).group(1))
        relations, roles = set(), {}
        for rel in meta["gold"]["relations"]:
            triple = (rel[0], rel[1], rel[2])
            relations.add(triple)
            if len(rel) > 3:
                roles[triple] = rel[3]
        mentions = {r[0] for r in relations} | {r[2] for r in relations} | set(meta["gold"].get("also_mentions", []))
        docs[meta["doc_id"]] = GoldDocument(meta["doc_id"], meta["file_name"], relations, roles, mentions, meta)
    return docs


def file_to_gold_id() -> dict[str, str]:
    return {g.file_name: g.doc_id for g in load_gold_documents().values()}


def load_questions() -> list[dict]:
    data = yaml.safe_load((GOLD / "questions.yaml").read_text(encoding="utf-8"))
    defaults = data.get("defaults", {})
    return [{**defaults, **q} for q in data["questions"]]


def load_yaml(name: str) -> dict:
    return yaml.safe_load((GOLD / name).read_text(encoding="utf-8"))


def documents_dir() -> Path:
    return DATA_DIR / "sample_documents"
