"""Génère RESULTATS.md et les figures à partir des fichiers de résultats (aucune saisie manuelle).

Usage : python -m evaluation.report
Entrées : evaluation/results/wordllama (campagne principale gelée), results/spacy (ablation de
l'encodeur), results/wordllama_postgel (modification post-gel).
Sorties : evaluation/results/RESULTATS.md, evaluation/results/figures/*.png, et copie des
figures dans « RAG/RAPPORT ET PRESENTATION/figures ».
"""

from __future__ import annotations

import json
import shutil

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from core.settings import CODE_DIR, RAG_DIR  # noqa: E402

RESULTS = CODE_DIR / "evaluation" / "results"
FIGURES = RESULTS / "figures"
REPORT_FIGURES = RAG_DIR / "RAPPORT ET PRESENTATION" / "figures"
MAIN, ENCODER_ABLATION, POSTGEL = "wordllama", "spacy", "wordllama_postgel"

# Palette catégorielle de référence (ordre fixe, validée : contraste insuffisant de l'aqua
# compensé par des étiquettes de valeurs visibles et les tableaux du rapport).
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

STRATEGY_LABELS = {"vector": "Vectoriel", "lexical": "BM25 (lexical)", "hybrid": "Hybride (BM25 + vecteurs)",
                   "graph": "Graphe seul", "hybrid_graph": "Hybride + graphe (fixe)", "auto": "Hybride final (routé)"}
ARCH_LABELS = {"rag_vectoriel": "RAG vectoriel", "rag_hybride": "RAG hybride", "graphrag": "GraphRAG",
               "hybride_graphe_fixe": "Hybride + graphe (fixe)", "hybride_final": "Hybride final (routé)"}
CATEGORY_LABELS = {"factual": "factuelle", "multi_doc": "multi-documents", "multi_hop": "multi-sauts",
                   "relational": "relationnelle", "expert": "expertise", "ambiguous": "ambiguë",
                   "contradiction": "contradiction", "access": "accès", "security": "sécurité",
                   "unanswerable": "sans réponse"}


def load(tag: str, name: str):
    path = RESULTS / tag / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def fmt(x, digits=3) -> str:
    return "—" if x is None else f"{x:.{digits}f}".replace(".", ",")


def ci(summary: dict, digits=3) -> str:
    if not summary or summary.get("mean") is None:
        return "—"
    lo, hi = summary["ci95"]
    return f"{fmt(summary['mean'], digits)} [{fmt(lo, 2)} ; {fmt(hi, 2)}]"


def table(headers: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(out)


# ---------------------------------------------------------------------------- figures
def _french_ticks(ax, axis: str) -> None:
    formatter = matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}".replace(".", ","))
    (ax.xaxis if axis == "x" else ax.yaxis).set_major_formatter(formatter)


def _style(ax, grid_axis="x"):
    _french_ticks(ax, grid_axis)
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_2, labelsize=9, length=0)
    ax.grid(axis=grid_axis, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _figure(width=7.5, height=4.2):
    fig, ax = plt.subplots(figsize=(width, height), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    return fig, ax


def _title(fig, title: str, subtitle: str | None = None):
    fig.text(0.01, 0.97, title, fontsize=12, fontweight="bold", color=INK, va="top")
    if subtitle:
        fig.text(0.01, 0.91, subtitle, fontsize=9, color=INK_2, va="top")


def _save(fig, name: str) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / name, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)


def fig_encoders(main: dict, ablation: dict) -> None:
    order = ["vector", "hybrid", "hybrid_graph", "auto", "graph", "lexical"]
    fig, ax = _figure(7.5, 3.9)
    _style(ax)
    y = np.arange(len(order))
    a = [ablation["strategies"][s]["ndcg@5"]["mean"] for s in order]
    b = [main["strategies"][s]["ndcg@5"]["mean"] for s in order]
    for i in range(len(order)):
        ax.plot([a[i], b[i]], [y[i], y[i]], color=GRID, linewidth=2, zorder=1, solid_capstyle="round")
    independent = [i for i, s in enumerate(order) if s in ("lexical", "graph")]
    dependent = [i for i in range(len(order)) if i not in independent]
    ax.scatter([a[i] for i in dependent], y[dependent], s=64, color=ORANGE, edgecolor=SURFACE, linewidth=2, zorder=3,
               label="Encodeur spaCy (300 d)")
    ax.scatter([b[i] for i in dependent], y[dependent], s=64, color=BLUE, edgecolor=SURFACE, linewidth=2, zorder=3,
               label="Encodeur WordLlama (256 d)")
    ax.scatter([b[i] for i in independent], y[independent], s=64, color=INK_2, edgecolor=SURFACE, linewidth=2,
               zorder=3, label="Sans encodeur (identique)")
    for i in range(len(order)):
        ax.text(max(a[i], b[i]) + 0.015, y[i], fmt(b[i], 2) if b[i] >= a[i] else fmt(a[i], 2), va="center",
                fontsize=8.5, color=INK_2)
    ax.set_yticks(y, [STRATEGY_LABELS[s] for s in order], color=INK)
    ax.set_xlim(0.3, 0.95)
    ax.set_xlabel("nDCG@5 moyen (55 questions)", color=INK_2, fontsize=9)
    ax.legend(loc="upper left", frameon=False, fontsize=8.5)
    _title(fig, "Recherche documentaire : effet de l'encodeur", "BM25 et graphe seul n'utilisent pas d'encodeur")
    fig.subplots_adjust(top=0.84)
    _save(fig, "fig_recherche_encodeurs.png")


def fig_categories(main: dict) -> None:
    strategies = ["vector", "lexical", "hybrid", "graph", "hybrid_graph", "auto"]
    categories = ["factual", "multi_doc", "multi_hop", "relational", "expert", "ambiguous", "contradiction"]
    data = np.array([[main["by_category"][s][c]["ndcg@5"] for c in categories] for s in strategies])
    fig, ax = _figure(8, 4.0)
    ax.set_facecolor(SURFACE)
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("bleu", SEQUENTIAL)
    ax.imshow(data, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    for i in range(len(strategies)):
        for j in range(len(categories)):
            v = data[i, j]
            ax.text(j, i, fmt(v, 2), ha="center", va="center", fontsize=8.5, color="white" if v > 0.55 else INK)
    n = [main["by_category"]["auto"][c]["n"] for c in categories]
    ax.set_xticks(range(len(categories)), [f"{CATEGORY_LABELS[c]}\n(n={k})" for c, k in zip(categories, n, strict=True)],
                  fontsize=8.5, color=INK)
    ax.set_yticks(range(len(strategies)), [STRATEGY_LABELS[s] for s in strategies], fontsize=9, color=INK)
    ax.tick_params(length=0)
    for side in ax.spines.values():
        side.set_visible(False)
    ax.set_xticks(np.arange(-0.5, len(categories)), minor=True)
    ax.set_yticks(np.arange(-0.5, len(strategies)), minor=True)
    ax.grid(which="minor", color=SURFACE, linewidth=2)
    ax.tick_params(which="minor", length=0)
    _title(fig, "nDCG@5 par catégorie de question et stratégie", "Encodeur WordLlama, configuration gelée")
    fig.subplots_adjust(top=0.84)
    _save(fig, "fig_recherche_categories.png")


def fig_qa(qa: dict) -> None:
    order = ["graphrag", "rag_hybride", "rag_vectoriel", "hybride_final", "hybride_graphe_fixe"]
    fig, ax = _figure(7.5, 3.6)
    _style(ax)
    y = np.arange(len(order))
    means = [qa[a]["accuracy_overall"]["mean"] for a in order]
    lows = [qa[a]["accuracy_overall"]["ci95"][0] for a in order]
    highs = [qa[a]["accuracy_overall"]["ci95"][1] for a in order]
    unseen = [qa[a]["accuracy_by_split"]["jamais_inspectee"]["mean"] for a in order]
    for i in range(len(order)):
        ax.plot([lows[i], highs[i]], [y[i] + 0.12] * 2, color=BLUE, linewidth=2, alpha=0.35, solid_capstyle="round")
    ax.scatter(means, y + 0.12, s=64, color=BLUE, edgecolor=SURFACE, linewidth=2, zorder=3,
               label="Toutes les questions (66), IC 95 %")
    ax.scatter(unseen, y - 0.12, s=64, color=ORANGE, edgecolor=SURFACE, linewidth=2, zorder=3, marker="D",
               label="Questions jamais inspectées (49)")
    for i in range(len(order)):
        ax.text(highs[i] + 0.012, y[i] + 0.12, fmt(means[i], 2), va="center", fontsize=8.5, color=INK_2)
        ax.text(unseen[i] - 0.012, y[i] - 0.12, fmt(unseen[i], 2), va="center", ha="right", fontsize=8.5, color=INK_2)
    ax.set_yticks(y, [ARCH_LABELS[a] for a in order], color=INK)
    ax.set_xlim(0.35, 1.0)
    ax.set_xlabel("Exactitude bout en bout (générateur extractif hors-ligne)", color=INK_2, fontsize=9)
    ax.legend(loc="upper left", frameon=False, fontsize=8.5)
    _title(fig, "Questions-réponses : comparaison des architectures", "Même workflow, seule la récupération change")
    fig.subplots_adjust(top=0.84)
    _save(fig, "fig_qa_architectures.png")


def fig_threshold(ablations: dict) -> None:
    keys = [k for k in ablations if k.startswith("seuil_")]
    xs = [float(k.split("_")[1]) for k in keys]
    series = [("Exactitude", [ablations[k]["accuracy_overall"]["mean"] for k in keys], BLUE),
              ("Rappel d'abstention", [ablations[k]["abstention_recall"] for k in keys], ORANGE),
              ("Abstention abusive", [ablations[k]["false_abstention_rate"] for k in keys], AQUA)]
    fig, ax = _figure(7.5, 3.8)
    _style(ax, grid_axis="y")
    for label, values, color in series:
        ax.plot(xs, values, color=color, linewidth=2, solid_joinstyle="round", solid_capstyle="round", label=label)
        ax.scatter(xs, values, s=36, color=color, edgecolor=SURFACE, linewidth=2, zorder=3)
        ax.text(xs[-1] + 0.012, values[-1], f"{label} {fmt(values[-1], 2)}", va="center", fontsize=8.5, color=INK_2)
    ax.axvline(0.55, color=INK_2, linewidth=0.8)
    ax.text(0.555, 1.02, "seuil fixé a priori (0,55)", fontsize=8, color=INK_2, va="bottom")
    ax.set_xticks(xs, [fmt(x, 2) for x in xs])
    ax.set_xlim(0.32, 0.95)
    ax.set_ylim(0, 1.08)
    ax.set_xlabel("Seuil de couverture pondérée de la question", color=INK_2, fontsize=9)
    ax.legend(loc="center left", bbox_to_anchor=(0.0, 0.45), frameon=False, fontsize=8.5)
    _title(fig, "Sensibilité au seuil de suffisance du contexte", "Hybride final, 66 questions")
    fig.subplots_adjust(top=0.84)
    _save(fig, "fig_seuil_suffisance.png")


def _grouped_bars(name: str, title: str, subtitle: str, metrics: list[tuple[str, str]], groups: list[tuple[str, dict, str]],
                  xlabel: str) -> None:
    fig, ax = _figure(7.5, 3.6)
    _style(ax)
    y = np.arange(len(metrics))
    height = 0.8 / len(groups)
    for g, (label, values, color) in enumerate(groups):
        offsets = y + (g - (len(groups) - 1) / 2) * height
        vals = [values[m]["mean"] for m, _ in metrics]
        ax.barh(offsets, vals, height=height * 0.82, color=color, label=label)
        for o, v in zip(offsets, vals, strict=True):
            ax.text(v + 0.01, o, fmt(v, 2), va="center", fontsize=8, color=INK_2)
    ax.set_yticks(y, [lbl for _, lbl in metrics], color=INK)
    ax.invert_yaxis()
    ax.set_xlim(0, 1.12)
    ax.set_xlabel(xlabel, color=INK_2, fontsize=9)
    ax.legend(loc="upper center", bbox_to_anchor=(0.45, -0.2), ncol=len(groups), frameon=False, fontsize=8.5)
    _title(fig, title, subtitle)
    fig.subplots_adjust(top=0.84)
    _save(fig, name)


def fig_ingestion(ingestion: dict) -> None:
    labels = {"extraction_texte_ocr": "OCR (1 PDF scanné)", "ecriture_neo4j": "Écriture Neo4j",
              "entites_relations_regles": "Entités et relations (règles)", "embeddings": "Encodage vectoriel",
              "extraction_texte": "Extraction du texte", "validation": "Validation de sécurité",
              "nettoyage_metadonnees": "Nettoyage et métadonnées", "decoupage": "Découpage"}
    items = sorted(ingestion["stage_seconds_total"].items(), key=lambda kv: kv[1])
    fig, ax = _figure(7.5, 3.4)
    _style(ax)
    ax.barh(range(len(items)), [v for _, v in items], height=0.55, color=BLUE)
    for i, (_, v) in enumerate(items):
        ax.text(v + 0.08, i, f"{fmt(v, 2)} s", va="center", fontsize=8.5, color=INK_2)
    ax.set_yticks(range(len(items)), [labels.get(k, k) for k, _ in items], color=INK)
    ax.set_xlabel("Durée cumulée sur les 35 fichiers (secondes)", color=INK_2, fontsize=9)
    _title(fig, "Ingestion complète : durée par étape",
           f"Total {fmt(ingestion['full_ingestion_seconds'], 1)} s ; ré-exécution sans changement "
           f"{fmt(ingestion['idempotent_rerun_seconds'], 2)} s")
    fig.subplots_adjust(top=0.82)
    _save(fig, "fig_ingestion.png")


# ---------------------------------------------------------------------------- rapport
def build_markdown() -> str:
    env = load(MAIN, "environment.json")
    ing, kg, ext = load(MAIN, "ingestion.json"), load(MAIN, "kg_quality.json"), load(MAIN, "extraction.json")
    ret, qa, abl = load(MAIN, "retrieval_summary.json"), load(MAIN, "qa_summary.json"), load(MAIN, "ablations_summary.json")
    exp, rec = load(MAIN, "experts.json"), load(MAIN, "recommendations.json")
    ret_sp = load(ENCODER_ABLATION, "retrieval_summary.json")
    ret_pg, qa_pg = load(POSTGEL, "retrieval_summary.json"), load(POSTGEL, "qa_summary.json")
    lines = [
        "# Résultats expérimentaux (générés automatiquement)",
        "",
        "Ce fichier est produit par `python -m evaluation.report` à partir des fichiers bruts de",
        "`evaluation/results/`. Aucune valeur n'est saisie à la main. Les intervalles entre crochets",
        "sont des intervalles de confiance à 95 % (bootstrap percentile, 2 000 rééchantillonnages).",
        "",
        f"- Campagne principale (configuration gelée) : `results/{MAIN}/`, commit `{env['git_commit']}`, "
        f"{env['date']}, Neo4j {env['neo4j']['version']} {env['neo4j']['edition']}, Python {env['python']}, "
        f"{env['cpu_count']} processeurs.",
        f"- Encodeur : {env['embedding_provider']} ({env['embedding_dim']} dimensions) ; LLM : "
        f"{'activé' if env['llm_enabled'] else 'désactivé (générateur extractif hors-ligne)'} ; top-k = "
        f"{env['retrieval_top_k']} passages ; RRF k = {env['rrf_k']} ; seuil de suffisance = {str(env['sufficiency_threshold']).replace('.', ',')}.",
        "- Corpus et questions **synthétiques**, rédigés par l'auteure de la plateforme : les résultats valent pour ce",
        "  banc d'essai et ne se généralisent pas sans validation sur des documents réels.",
        "",
        "## 1. Ingestion",
        "",
        table(["Indicateur", "Valeur"], [
            ["Fichiers traités", ing["files"]],
            ["Statut final des documents", ", ".join(f"{k} : {v}" for k, v in ing["final_document_status"].items())],
            ["Durée de l'ingestion complète", f"{fmt(ing['full_ingestion_seconds'], 2)} s"],
            ["Ré-exécution sans changement", f"{fmt(ing['idempotent_rerun_seconds'], 2)} s "
                                             f"({ing['idempotent_rerun_unchanged']} fichiers inchangés)"],
            ["Passages (chunks)", ing["chunks"]],
            ["Durée moyenne par format", ", ".join(f"{k} : {fmt(v['mean'], 2)} s (n={v['n']})"
                                                   for k, v in ing["processing_seconds_by_format"].items())],
            ["Signalements qualité", ", ".join(f"{k} : {v}" for k, v in ing["quality_issues"].items())],
        ]),
        "",
        "## 2. Graphe de connaissances",
        "",
        table(["Indicateur", "Valeur"], [
            ["Nœuds par type", ", ".join(f"{k} : {v}" for k, v in sorted(kg["nodes_by_label"].items()))],
            ["Relations extraites des documents", kg["extracted_relations"]],
            ["Relations avec provenance (passage + document)", fmt(kg["provenance_coverage"], 3)],
            ["Confiance moyenne", fmt(kg["mean_confidence"], 3)],
            ["Documents sources par relation (moyenne)", fmt(kg["mean_source_documents_per_relation"], 2)],
            ["Relations confirmées par au moins 2 documents", kg["relations_supported_by_2plus_documents"]],
            ["Entités métier (hors taxonomie)", f"{kg['entities_excluding_taxonomy']} (degré moyen "
                                               f"{fmt(kg['mean_entity_degree'], 1)}, isolées : {kg['isolated_entities']})"],
        ]),
        "",
        "## 3. Extraction de connaissances (règles, sans LLM)",
        "",
        "Règles développées sur D01–D20 (développement), mesurées aussi sur D21–D35 (jamais utilisés pour la mise au point).",
        "",
        table(["Mesure", "Développement (D01–D20)", "Test (D21–D35)"], [
            ["Relations : précision / rappel / F1",
             f"{fmt(ext['relations']['dev']['precision'])} / {fmt(ext['relations']['dev']['recall'])} / "
             f"{fmt(ext['relations']['dev']['f1'])}",
             f"{fmt(ext['relations']['test']['precision'])} / {fmt(ext['relations']['test']['recall'])} / "
             f"{fmt(ext['relations']['test']['f1'])}"],
            ["Mentions d'entités : précision / rappel / F1",
             f"{fmt(ext['entity_mentions']['dev']['precision'])} / {fmt(ext['entity_mentions']['dev']['recall'])} / "
             f"{fmt(ext['entity_mentions']['dev']['f1'])}",
             f"{fmt(ext['entity_mentions']['test']['precision'])} / {fmt(ext['entity_mentions']['test']['recall'])} / "
             f"{fmt(ext['entity_mentions']['test']['f1'])}"],
        ]),
        "",
        "Rappel par type de relation sur le test : " + ", ".join(
            f"{k} {fmt(v['recall'], 2)} (n={v['tp'] + v['fn']})" for k, v in sorted(ext["relations_by_type"]["test"].items())) + ".",
        "",
        "Résolution d'entités (34 cas) : " + ", ".join(
            f"{k} : {fmt(v['accuracy'], 2)} (n={v['n']})" for k, v in ext["entity_resolution"]["accuracy_by_group"].items()) + ".",
        "",
        "## 4. Recherche documentaire (classement des documents)",
        "",
        f"{ret['n_questions']} questions avec documents de référence (hors questions sans réponse attendue).",
        "",
        table(["Stratégie", "Recall@5", "Precision@5", "MRR", "nDCG@5", "Couverture des preuves", "Latence p50 / p95 (ms)"],
              [[STRATEGY_LABELS[s], ci(v["recall@5"]), fmt(v["precision@5"]["mean"]), ci(v["mrr"]), ci(v["ndcg@5"]),
                fmt(v["evidence_recall"]["mean"]), f"{fmt(v['latency']['p50_ms'], 1)} / {fmt(v['latency']['p95_ms'], 1)}"]
               for s, v in ret["strategies"].items()]),
        "",
        "Fuites d'accès (document non autorisé dans le classement) : " + ", ".join(
            f"{STRATEGY_LABELS[s]} {v['leaked_documents']}" for s, v in ret["strategies"].items()) + ".",
        "",
        "### 4.1 Questions de développement et questions jamais inspectées (nDCG@5)",
        "",
        table(["Stratégie", "Développement (n=17 max.)", "Jamais inspectées"],
              [[STRATEGY_LABELS[s], ci(v["developpement"]["ndcg@5"]), ci(v["jamais_inspectee"]["ndcg@5"])]
               for s, v in ret["by_split"].items()]),
        "",
        "### 4.2 Comparaisons appariées (nDCG@5, stratégie − référence)",
        "",
        table(["Stratégie", "vs vectoriel : écart [IC 95 %]", "gains / pertes / égalités", "p (signes)",
               "vs hybride : écart [IC 95 %]", "p (signes)"],
              [[STRATEGY_LABELS[s], f"{fmt(v['mean_diff'])} [{fmt(v['ci95'][0], 2)} ; {fmt(v['ci95'][1], 2)}]",
                f"{v['wins']} / {v['losses']} / {v['ties']}", fmt(v["p_value"], 4),
                (lambda h: f"{fmt(h['mean_diff'])} [{fmt(h['ci95'][0], 2)} ; {fmt(h['ci95'][1], 2)}]" if h else "—")(
                    ret["paired_vs_hybrid"].get(s)),
                fmt(ret["paired_vs_hybrid"][s]["p_value"], 4) if s in ret["paired_vs_hybrid"] else "—"]
               for s, v in ret["paired_vs_vector"].items()]),
        "",
        "### 4.3 Ablation de l'encodeur (nDCG@5 moyen)",
        "",
        table(["Stratégie", "spaCy (vecteurs de mots moyennés, 300 d)", "WordLlama (256 d)"],
              [[STRATEGY_LABELS[s], fmt(ret_sp["strategies"][s]["ndcg@5"]["mean"]), fmt(v["ndcg@5"]["mean"])]
               for s, v in ret["strategies"].items()]) if ret_sp else "_Ablation non exécutée._",
        "",
        "## 5. Questions-réponses de bout en bout (workflow LangGraph)",
        "",
        f"66 questions ; générateur : {qa['generator']}. Toutes les architectures partagent le même workflow "
        "(analyse, récupération, contrôle de suffisance, relance, génération, vérification) ; seule la stratégie "
        "de récupération change.",
        "",
        table(["Architecture", "Exactitude (66)", "Questions avec réponse (55)", "Rappel d'abstention (11)",
               "Précision d'abstention", "Abstention abusive", "Contradictions signalées (4)", "Ambiguïtés (4)"],
              [[ARCH_LABELS[a], ci(v["accuracy_overall"]), ci(v["accuracy_answerable"]), fmt(v["abstention_recall"]),
                fmt(v["abstention_precision"]), fmt(v["false_abstention_rate"]), fmt(v["conflict_recall"]),
                fmt(v["ambiguity_recall"])] for a, v in qa.items() if a in ARCH_LABELS]),
        "",
        table(["Architecture", "Taux d'appui des phrases", "Précision des citations", "Cite un document essentiel",
               "Citations invalides", "Fuites d'accès", "Chaînes interdites", "Relance", "Latence p50 / p95 (ms)"],
              [[ARCH_LABELS[a], fmt(v["support_rate_mean"]), fmt(v["citation_precision_mean"]),
                fmt(v["cites_essential_document_rate"]), v["invalid_citations_total"], v["access_leaks"],
                v["forbidden_violations"], fmt(v["expansion_rate"], 2),
                f"{fmt(v['latency']['p50_ms'], 1)} / {fmt(v['latency']['p95_ms'], 1)}"]
               for a, v in qa.items() if a in ARCH_LABELS]),
        "",
        "### 5.1 Exactitude par split et par catégorie",
        "",
        table(["Architecture", "Développement (17)", "Jamais inspectées (49)"] +
              [CATEGORY_LABELS[c] for c in sorted(qa["hybride_final"]["accuracy_by_category"])],
              [[ARCH_LABELS[a], ci(v["accuracy_by_split"]["developpement"]), ci(v["accuracy_by_split"]["jamais_inspectee"])] +
               [fmt(v["accuracy_by_category"][c], 2) for c in sorted(v["accuracy_by_category"])]
               for a, v in qa.items() if a in ARCH_LABELS]),
        "",
        "### 5.2 Comparaisons appariées avec l'hybride final (exactitude)",
        "",
        table(["Architecture comparée", "Écart (final − autre) [IC 95 %]", "gains / pertes / égalités", "p (signes)"],
              [[ARCH_LABELS[a], f"{fmt(v['mean_diff'])} [{fmt(v['ci95'][0], 2)} ; {fmt(v['ci95'][1], 2)}]",
                f"{v['wins']} / {v['losses']} / {v['ties']}", fmt(v["p_value"], 4)]
               for a, v in qa["paired_vs_hybride_final"].items()]),
        "",
        f"Accord du classifieur de questions avec la catégorie annotée (41 questions de catégories correspondantes) : "
        f"{fmt(qa['classifier_agreement']['agreement'])}.",
        "",
        "## 6. Ablations du workflow (hybride final)",
        "",
        table(["Variante", "Exactitude", "Jamais inspectées", "Rappel d'abstention", "Abstention abusive", "Taux de relance"],
              [[k.replace("seuil_", "seuil ").replace(".", ",").replace("sans_relance", "sans relance (seuil 0,55)"),
                ci(v["accuracy_overall"]), fmt(v["accuracy_by_split"]["jamais_inspectee"]["mean"]),
                fmt(v["abstention_recall"]), fmt(v["false_abstention_rate"]), fmt(v["expansion_rate"], 2)]
               for k, v in abl.items()]),
        "",
        "## 7. Recherche d'experts (15 domaines)",
        "",
        table(["Méthode", "Precision@1", "Recall@3", "nDCG@3", "MRR"],
              [["Score pondéré par type de preuve (plateforme)"] + [ci(exp["ours"][m]) for m in ("precision@1", "recall@3", "ndcg@3", "mrr")],
               ["Baseline : nombre de mentions"] + [ci(exp["baseline_mentions"][m]) for m in ("precision@1", "recall@3", "ndcg@3", "mrr")]]),
        "",
        f"Écart apparié nDCG@3 : {fmt(exp['paired_ndcg@3']['mean_diff'])} [{fmt(exp['paired_ndcg@3']['ci95'][0], 2)} ; "
        f"{fmt(exp['paired_ndcg@3']['ci95'][1], 2)}], gains / pertes / égalités {exp['paired_ndcg@3']['wins']} / "
        f"{exp['paired_ndcg@3']['losses']} / {exp['paired_ndcg@3']['ties']}, p = {fmt(exp['paired_ndcg@3']['p_value'], 3)}.",
        "",
        "## 8. Recommandations de documents (10 documents sources)",
        "",
        table(["Mode", "Precision@5", "Recall@5", "nDCG@5", "MRR", "Doublons ou mémo piégé recommandés"],
              [[m, ci(v["precision@5"]), ci(v["recall@5"]), ci(v["ndcg@5"]), ci(v["mrr"]), v["forbidden_recommended"]]
               for m, v in rec["modes"].items()]),
        "",
        f"Hybride vs contenu seul (nDCG@5) : écart {fmt(rec['paired_hybrid_vs_content_ndcg@5']['mean_diff'])}, "
        f"p = {fmt(rec['paired_hybrid_vs_content_ndcg@5']['p_value'], 4)}.",
        "",
    ]
    if ret_pg and qa_pg:
        lines += [
            "## 9. Modification post-gel (garantie par source dans la fusion RRF)",
            "",
            "Voir `evaluation/JOURNAL_DEVELOPPEMENT.md`. Résultats rapportés séparément de la campagne principale.",
            "",
            table(["Mesure (hybride final)", "Gel", "Post-gel"], [
                ["Recherche nDCG@5 (toutes)", fmt(ret["strategies"]["auto"]["ndcg@5"]["mean"]),
                 fmt(ret_pg["strategies"]["auto"]["ndcg@5"]["mean"])],
                ["Recherche nDCG@5 (jamais inspectées)", fmt(ret["by_split"]["auto"]["jamais_inspectee"]["ndcg@5"]["mean"]),
                 fmt(ret_pg["by_split"]["auto"]["jamais_inspectee"]["ndcg@5"]["mean"])],
                ["Couverture des preuves", fmt(ret["strategies"]["auto"]["evidence_recall"]["mean"]),
                 fmt(ret_pg["strategies"]["auto"]["evidence_recall"]["mean"])],
                ["Exactitude (toutes)", fmt(qa["hybride_final"]["accuracy_overall"]["mean"]),
                 fmt(qa_pg["hybride_final"]["accuracy_overall"]["mean"])],
                ["Exactitude (développement)", fmt(qa["hybride_final"]["accuracy_by_split"]["developpement"]["mean"]),
                 fmt(qa_pg["hybride_final"]["accuracy_by_split"]["developpement"]["mean"])],
                ["Exactitude (jamais inspectées)", fmt(qa["hybride_final"]["accuracy_by_split"]["jamais_inspectee"]["mean"]),
                 fmt(qa_pg["hybride_final"]["accuracy_by_split"]["jamais_inspectee"]["mean"])],
            ]),
            "",
        ]
    lines += ["## Figures", ""] + [f"- `figures/{p.name}`" for p in sorted(FIGURES.glob("*.png"))] + [""]
    return "\n".join(lines)


def main() -> None:
    ret, qa, abl = load(MAIN, "retrieval_summary.json"), load(MAIN, "qa_summary.json"), load(MAIN, "ablations_summary.json")
    ret_sp, exp, rec, ing = (load(ENCODER_ABLATION, "retrieval_summary.json"), load(MAIN, "experts.json"),
                             load(MAIN, "recommendations.json"), load(MAIN, "ingestion.json"))
    plt.rcParams.update({"font.family": "DejaVu Sans"})
    if ret_sp:
        fig_encoders(ret, ret_sp)
    fig_categories(ret)
    fig_qa(qa)
    fig_threshold(abl)
    _grouped_bars("fig_experts.png", "Recherche d'experts : plateforme vs comptage de mentions", "15 domaines, pertinence graduée",
                  [("precision@1", "Precision@1"), ("recall@3", "Recall@3"), ("ndcg@3", "nDCG@3"), ("mrr", "MRR")],
                  [("Score pondéré par type de preuve", exp["ours"], BLUE),
                   ("Nombre de mentions (baseline)", exp["baseline_mentions"], ORANGE)], "Valeur moyenne")
    _grouped_bars("fig_recommandations.png", "Recommandations : contenu, graphe et hybride", "10 documents sources",
                  [("precision@5", "Precision@5"), ("recall@5", "Recall@5"), ("ndcg@5", "nDCG@5"), ("mrr", "MRR")],
                  [("Contenu (similarité vectorielle)", rec["modes"]["content"], ORANGE),
                   ("Graphe (entités partagées, proximité)", rec["modes"]["graph"], AQUA),
                   ("Hybride", rec["modes"]["hybrid"], BLUE)], "Valeur moyenne")
    fig_ingestion(ing)
    (RESULTS / "RESULTATS.md").write_text(build_markdown(), encoding="utf-8")
    REPORT_FIGURES.mkdir(parents=True, exist_ok=True)
    for png in FIGURES.glob("*.png"):
        shutil.copy(png, REPORT_FIGURES / png.name)
    print(f"RESULTATS.md et {len(list(FIGURES.glob('*.png')))} figures générés")


if __name__ == "__main__":
    main()
