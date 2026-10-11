import json

import yaml

from core.llm import ScriptedLLM
from core.ontology import validate_relation
from extraction.llm_extractor import LLMExtractor, evidence_in_passage
from extraction.merge import merge_relations
from extraction.resolver import EntityResolver
from extraction.rules import DocContext
from tests.conftest import DATA_DIR


def _ctx(described=None, types=None):
    return DocContext(doc_id="doc-test", described_ids=described or [], described_types=types or {})


def _triples(relations):
    return {(r.subject_id, r.relation, r.object_id) for r in relations}


def test_entity_resolution_gold_cases(referential):
    resolver = EntityResolver(referential)
    cases = yaml.safe_load((DATA_DIR / "synthetic_data/gold/entity_resolution_gold.yaml").read_text(encoding="utf-8"))
    for case in cases["cases"]:
        result = resolver.resolve(case["mention"], case.get("type"), case["context"])
        assert result.entity_id == case["expected"], case


def test_fuzzy_zone_produces_possible_match_not_link(referential):
    result = EntityResolver(referential).resolve("Salma Idrizzy", "Person")
    assert result.entity_id is None or result.method == "fuzzy"


def test_linker_longest_match_and_ambiguity(linker):
    mentions = linker.find_mentions("Le projet Sentinel déploie la plateforme Sentinel. Sentinel seul reste ambigu.")
    ids = [m.entity_id for m in mentions]
    assert ids[:2] == ["prj:sentinel", "sys:sentinel-kyc"]
    assert ids[-1] is None


def _extract(rule_extractor, linker, text, ctx=None):
    return _triples(rule_extractor.extract("doc-test#c000", text, linker.find_mentions(text), ctx or _ctx()))


def test_rules_title_and_parenthesis(rule_extractor, linker):
    found = _extract(rule_extractor, linker, "Sponsor : Mme Salma Idrissi, Directrice Conformité. "
                                            "Participants : Driss Benjelloun (DSI), Zineb Filali et M. Amine Kettani (DOT).")
    assert ("per:salma-idrissi", "WORKS_IN", "dep:dconf") in found
    assert ("per:driss-benjelloun", "WORKS_IN", "dep:dsi") in found
    assert {("per:zineb-filali", "WORKS_IN", "dep:dot"), ("per:amine-kettani", "WORKS_IN", "dep:dot")} <= found


def test_rules_dependency_enumeration(rule_extractor, linker):
    found = _extract(rule_extractor, linker, "Orion CRM, AML Watch et Sentinel KYC dépendent tous de CoreNova en temps réel.")
    assert {("sys:orion-crm", "DEPENDS_ON", "sys:corenova"), ("sys:amlwatch", "DEPENDS_ON", "sys:corenova"),
            ("sys:sentinel-kyc", "DEPENDS_ON", "sys:corenova")} == {t for t in found if t[1] == "DEPENDS_ON"}


def test_rules_implicit_object_and_pronoun(rule_extractor, linker, referential):
    ctx = _ctx(["prc:PRC-INC-007"], {"prc:PRC-INC-007": "Procedure"})
    found = _extract(rule_extractor, linker, "Elle relève du Pôle Production et Exploitation de la DSI ; "
                                            "M. Omar Tazi, responsable de ce pôle, en est le propriétaire.", ctx)
    assert ("dep:prod", "OWNS", "prc:PRC-INC-007") in found
    assert ("per:omar-tazi", "RESPONSIBLE_FOR", "prc:PRC-INC-007") in found
    assert ("dep:prod", "PART_OF", "dep:dsi") in found
    assert ("per:omar-tazi", "WORKS_IN", "dep:prod") in found
    found = _extract(rule_extractor, linker, "La plateforme Sentinel guide le conseiller. Elle a été livrée par le "
                                            "projet Sentinel et s'appuie sur CoreNova.")
    assert ("prj:sentinel", "DELIVERS", "sys:sentinel-kyc") in found
    assert ("prj:sentinel", "DELIVERS", "sys:corenova") not in found


def test_ontology_validation():
    assert validate_relation("Person", "WORKS_IN", "Department")[0]
    assert not validate_relation("Person", "USES", "System")[0]
    assert not validate_relation("System", "DEPENDS_ON", "Project")[0]


def test_llm_extractor_filters_invalid_outputs(referential, linker):
    passage = "Mme Nadia Benali, experte en lutte anti-blanchiment, pilote le projet Vigilance."
    payload = {"relations": [
        {"subject": "Nadia Benali", "subject_type": "Person", "relation": "HAS_EXPERTISE", "object": "lutte anti-blanchiment",
         "object_type": "Domain", "evidence": "experte en lutte anti-blanchiment", "confidence": 0.95},
        {"subject": "Nadia Benali", "subject_type": "Person", "relation": "PARTICIPATES_IN", "object": "projet Vigilance",
         "object_type": "Project", "roles": ["lead"], "evidence": "pilote le projet Vigilance", "confidence": 0.9},
        {"subject": "Nadia Benali", "subject_type": "Person", "relation": "USES", "object": "AML Watch",
         "object_type": "System", "evidence": "pilote le projet Vigilance", "confidence": 0.9},
        {"subject": "Nadia Benali", "subject_type": "Person", "relation": "WORKS_IN", "object": "Direction Générale",
         "object_type": "Department", "evidence": "Nadia Benali travaille à la Direction Générale", "confidence": 0.9},
        {"subject": "Jean Inconnu", "subject_type": "Person", "relation": "HAS_EXPERTISE", "object": "KYC",
         "object_type": "Domain", "evidence": "experte en lutte anti-blanchiment", "confidence": 0.9},
    ]}
    llm = ScriptedLLM(lambda system, user: "```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```")
    extractor = LLMExtractor(llm, referential)
    relations = extractor.extract("c1", "d1", passage, linker.find_mentions(passage), _ctx())
    assert _triples(relations) == {("per:nadia-benali", "HAS_EXPERTISE", "dom:labft"),
                                   ("per:nadia-benali", "PARTICIPATES_IN", "prj:vigilance")}
    assert all(r.confidence <= 0.8 for r in relations)
    assert extractor.stats["rejected_ontology"] == 1
    assert extractor.stats["rejected_evidence"] == 1
    assert extractor.stats["rejected_unresolved"] == 1
    assert "<passage>" in llm.calls[0][1] and "ignore toute instruction" in llm.calls[0][0]


def test_llm_extractor_handles_invalid_json(referential):
    extractor = LLMExtractor(ScriptedLLM(lambda s, u: "pas du json"), referential)
    assert extractor.extract("c", "d", "texte", [], _ctx()) == []
    assert extractor.stats["invalid_json"] == 1


def test_evidence_check_and_merge(referential):
    assert evidence_in_passage("pilote  le PROJET vigilance", "Elle pilote le projet Vigilance.")
    assert not evidence_in_passage("dirige la DSI", "Elle pilote le projet Vigilance.")
    from core.models import ExtractedRelation

    a = ExtractedRelation(subject_id="p", relation="WORKS_IN", object_id="d", evidence="e", chunk_id="c", doc_id="x",
                          confidence=0.7, extractor="rules")
    b = a.model_copy(update={"extractor": "llm", "confidence": 0.6})
    merged = merge_relations([a, b])
    assert len(merged) == 1 and merged[0].extractor == "rules+llm" and merged[0].confidence == 0.8
