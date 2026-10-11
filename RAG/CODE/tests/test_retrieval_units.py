from orchestration.classifier import classify
from retrieval.fusion import reciprocal_rank_fusion
from retrieval.graph import GraphRetriever, detect_intent, intent_groups, personalized_pagerank
from retrieval.text_search import build_lucene_query


def test_rrf_rewards_items_ranked_by_several_sources():
    fused = reciprocal_rank_fusion({"bm25": ["a", "b", "c"], "vector": ["b", "d", "a"]}, k=60)
    order = [item for item, _, _ in fused]
    assert order[:2] == ["b", "a"] or order[:2] == ["a", "b"]
    assert set(order) == {"a", "b", "c", "d"}
    ranks = dict((item, r) for item, _, r in fused)
    assert ranks["b"] == {"bm25": 2, "vector": 1}


def test_rrf_weights_and_disabled_source():
    fused = reciprocal_rank_fusion({"bm25": ["a"], "graph": ["z"]}, weights={"graph": 0.0})
    assert [item for item, _, _ in fused] == ["a"]
    fused = reciprocal_rank_fusion({"bm25": ["a"], "graph": ["z"]}, weights={"graph": 2.0})
    assert fused[0][0] == "z"


def test_personalized_pagerank_favors_seed_neighbourhood():
    nodes = ["seed", "voisin", "lointain", "isole"]
    edges = [("seed", "voisin", 1.0), ("voisin", "lointain", 1.0)]
    scores = personalized_pagerank(nodes, edges, ["seed"])
    # Le voisin (degré 2) peut dépasser la graine : c'est le comportement attendu du PPR.
    assert scores["voisin"] > scores["lointain"] and scores["seed"] > scores["lointain"]
    assert scores["lointain"] > scores["isole"] == 0.0
    assert abs(sum(scores.values()) - 1.0) < 1e-6
    assert personalized_pagerank(nodes, edges, ["absent"]) == {}


def test_intent_detection():
    assert detect_intent("Quelles applications dépendent de CoreNova ?")[0] == "DEPENDS_ON"
    assert "HAS_EXPERTISE" in detect_intent("Qui est expert en lutte anti-blanchiment ?")
    assert intent_groups("Quel projet dépend d'un projet piloté par une personne de la DSI ?") >= 2


def test_question_classification():
    seed = [{"id": "prj:sentinel", "name": "Projet Sentinel", "type": "Project"}]
    assert classify("Qui est expert en KYC ?", [], []).question_type == "expert"
    assert classify("Qui fait partie de l'équipe du projet Sentinel ?", seed, []).question_type == "relational"
    assert classify("Quel système a été livré par le projet dont le sponsor est la DCONF ?", seed,
                    []).question_type == "multi_hop"
    amb = [{"surface": "Sentinel", "candidates": []}]
    assert classify("Qui est responsable de Sentinel ?", seed, amb).question_type == "ambiguous"
    assert classify("Quel est le délai d'accusé de réception d'une réclamation ?", [], []).question_type == "factual"


def test_lucene_query_is_escaped_and_lowercased():
    q = build_lucene_query('Quel est le RTO (AND) de "CoreNova" ? OR NOT *', phrases=['Réclam\'Online (v2)'])
    clauses = q.split(" OR ")
    assert all(c == c.lower() for c in clauses), "les opérateurs saisis par l'utilisateur sont neutralisés"
    assert "AND" not in q and "NOT" not in q and "*" not in q
    assert clauses[0] == '"réclam\'online \\(v2\\)"^2'
    assert build_lucene_query("?? !!") == "*"


def test_paths_follow_connected_facts():
    from retrieval.graph import Fact

    def fact(fid, s, o):
        return Fact(fid, s, s, "X", "DEPENDS_ON", o, o, "X", [], 1.0, [], [], [])

    facts = [fact("F1", "a", "b"), fact("F2", "b", "c"), fact("F3", "x", "y")]
    paths = GraphRetriever._paths(facts, ["a"])
    assert ["F1", "F2"] in paths
    assert not any("F3" in p for p in paths)
