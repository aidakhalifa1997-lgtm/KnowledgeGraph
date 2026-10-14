import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { ApiError, api } from "../api";
import { Empty, ErrorBox, Loading } from "../components/States";
import { formatPercent } from "../components/format";
import { docTypeLabel, statusLabel } from "../components/graphStyle";
import { useAsync } from "../components/useAsync";
import type { DocumentSummary, Recommendation } from "../types";
import type { PageProps } from "./contract";
import "./Recommendations.css";

type Navigate = PageProps["navigate"];
type Mode = "hybrid" | "content" | "graph";

const TABS = [
  { key: "document", label: "À partir d'un document" },
  { key: "query", label: "À partir d'un besoin (texte libre)" },
] as const;
type TabKey = (typeof TABS)[number]["key"];

const MODES: { value: Mode; label: string; short: string; detail: string; scoreNote: string }[] = [
  {
    value: "hybrid",
    label: "Hybride (recommandé)",
    short: "hybride",
    detail: "Combine le contenu (40\u00a0%), les entités partagées (30\u00a0%) et la proximité dans le graphe (30\u00a0%).",
    scoreNote: "Score global = 40\u00a0% contenu + 30\u00a0% entités partagées + 30\u00a0% proximité dans le graphe.",
  },
  {
    value: "content",
    label: "Contenu (similarité sémantique)",
    short: "contenu",
    detail: "Compare uniquement le sens des textes, à partir des vecteurs de leurs passages.",
    scoreNote: "Score global = contenu seul\u00a0; les entités partagées et la proximité sont affichées à titre indicatif.",
  },
  {
    value: "graph",
    label: "Graphe (entités partagées, proximité)",
    short: "graphe",
    detail: "S'appuie sur les éléments cités en commun et les liens explicites du graphe\u00a0: versions, objet décrit, relations.",
    scoreNote: "Score global = 50\u00a0% entités partagées + 50\u00a0% proximité dans le graphe\u00a0; le contenu est affiché à titre indicatif.",
  },
];

const CONTENT_NOTE = "La similarité de contenu est normalisée entre le candidat le plus éloigné (0\u00a0%) et le plus proche (100\u00a0%).";

const QUERY_SCORE_NOTE = "Score global = 40\u00a0% contenu + 30\u00a0% entités partagées (part des éléments reconnus dans "
  + "votre texte que le document cite) + 30\u00a0% proximité dans le graphe (le document décrit l'un de ces éléments). "
  + CONTENT_NOTE;

const COMPONENTS = [
  { key: "content", label: "Contenu" },
  { key: "entities", label: "Entités partagées" },
  { key: "graph", label: "Proximité dans le graphe" },
] as const;

const QUERY_MIN = 3;
const QUERY_MAX = 500;

const QUERY_EXAMPLES = [
  "Organiser la continuité d'activité après un sinistre",
  "Contrôles de connaissance client pour un client à risque élevé",
  "Attribuer et révoquer les droits d'accès aux applications",
];

const scoreFormatter = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const isEligible = (d: DocumentSummary) => d.status === "active" || d.status === "superseded";

function documentLabel(d: DocumentSummary): string {
  const ref = [d.reference, d.version ? `v${d.version}` : null].filter(Boolean).join(" ");
  const base = ref ? `${d.title} (${ref})` : d.title;
  return d.status === "superseded" ? `${base} — version remplacée` : base;
}

const truncate = (text: string, max: number) => (text.length > max ? `${text.slice(0, max - 1).trimEnd()}…` : text);

const quoted = (text: string) => `«\u00a0${text}\u00a0»`;

const countLabel = (n: number) => (n > 1 ? `${n} documents recommandés` : `${n} document recommandé`);

// ------------------------------------------------------------------ requêtes

type Outcome<C> =
  | { phase: "idle" }
  | { phase: "loading" }
  | { phase: "error"; message: string; retryable: boolean }
  | { phase: "done"; context: C; items: Recommendation[] };

// Seule la dernière requête lancée peut modifier l'affichage : une réponse plus ancienne,
// arrivée après un changement de document, de mode ou de texte, est ignorée.
function useLatestRequest<C>() {
  const seq = useRef(0);
  const last = useRef<{ context: C; load: () => Promise<Recommendation[]> } | null>(null);
  const [outcome, setOutcome] = useState<Outcome<C>>({ phase: "idle" });

  const run = useCallback((context: C, load: () => Promise<Recommendation[]>) => {
    const id = ++seq.current;
    last.current = { context, load };
    setOutcome({ phase: "loading" });
    load().then(
      (items) => {
        if (id === seq.current) setOutcome({ phase: "done", context, items });
      },
      (error: unknown) => {
        if (id !== seq.current) return;
        const status = error instanceof ApiError ? error.status : 0;
        setOutcome({
          phase: "error",
          message: error instanceof Error ? error.message : "Erreur inattendue.",
          retryable: status === 0 || status === 429 || status >= 500,
        });
      },
    );
  }, []);

  const reset = useCallback(() => {
    seq.current++;
    last.current = null;
    setOutcome({ phase: "idle" });
  }, []);

  const retry = useCallback(() => {
    if (last.current) run(last.current.context, last.current.load);
  }, [run]);

  return { outcome, run, reset, retry };
}

// ------------------------------------------------------------------ page

export default function Recommendations({ navigate, param }: PageProps) {
  const requestedDoc = param?.startsWith("doc-") ? param : null;
  const [tab, setTab] = useState<TabKey>("document");
  const tabRefs = useRef<Partial<Record<TabKey, HTMLButtonElement | null>>>({});

  useEffect(() => {
    if (requestedDoc) setTab("document");
  }, [requestedDoc]);

  const onTabKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const index = TABS.findIndex((t) => t.key === tab);
    const targets: Record<string, number> = { ArrowRight: index + 1, ArrowLeft: index - 1, Home: 0, End: TABS.length - 1 };
    const target = targets[event.key];
    if (target === undefined) return;
    event.preventDefault();
    const next = TABS[(target + TABS.length) % TABS.length].key;
    setTab(next);
    tabRefs.current[next]?.focus();
  };

  return (
    <>
      <header className="page-header">
        <h1>Recommandations</h1>
        <p>
          Retrouvez les documents liés à un document de référence ou à un besoin décrit en quelques mots.
          Chaque recommandation indique son score, le détail de ses trois composantes et les raisons qui la
          justifient&nbsp;; seuls les documents de votre périmètre sont pris en compte.
        </p>
      </header>

      <div className="recommendations">
        <div className="recommendations-tabs" role="tablist" aria-label="Point de départ des recommandations"
             onKeyDown={onTabKeyDown}>
          {TABS.map((t) => (
            <button key={t.key} type="button" role="tab" className="recommendations-tab"
                    id={`recommendations-tab-${t.key}`} aria-controls={`recommendations-panel-${t.key}`}
                    aria-selected={tab === t.key} tabIndex={tab === t.key ? 0 : -1}
                    ref={(el) => { tabRefs.current[t.key] = el; }}
                    onClick={() => setTab(t.key)}>
              {t.label}
            </button>
          ))}
        </div>

        <div role="tabpanel" id="recommendations-panel-document" aria-labelledby="recommendations-tab-document"
             className="recommendations-panel" hidden={tab !== "document"}>
          <DocumentPanel requestedDoc={requestedDoc} navigate={navigate} />
        </div>
        <div role="tabpanel" id="recommendations-panel-query" aria-labelledby="recommendations-tab-query"
             className="recommendations-panel" hidden={tab !== "query"}>
          <QueryPanel navigate={navigate} />
        </div>
      </div>
    </>
  );
}

// ------------------------------------------------------------------ onglet « document »

function DocumentPanel({ requestedDoc, navigate }: { requestedDoc: string | null; navigate: Navigate }) {
  const documents = useAsync(() => api.documents(), []);
  const [docId, setDocId] = useState(requestedDoc ?? "");
  const [mode, setMode] = useState<Mode>("hybrid");
  const { outcome, run, reset, retry } = useLatestRequest<{ docId: string; mode: Mode }>();

  useEffect(() => {
    if (requestedDoc) setDocId(requestedDoc);
  }, [requestedDoc]);

  useEffect(() => {
    if (!docId) {
      reset();
      return;
    }
    run({ docId, mode }, () => api.recommendForDocument(docId, mode));
  }, [docId, mode, run, reset]);

  const groups = useMemo(() => {
    const byType = new Map<string, DocumentSummary[]>();
    for (const d of documents.data ?? []) {
      if (!isEligible(d)) continue;
      const label = docTypeLabel(d.doc_type);
      byType.set(label, [...(byType.get(label) ?? []), d]);
    }
    const compare = (a: string, b: string) => a.localeCompare(b, "fr", { sensitivity: "base" });
    return [...byType.entries()]
      .sort(([a], [b]) => compare(a, b))
      .map(([label, docs]) => ({ label, docs: docs.sort((a, b) => compare(a.title, b.title)) }));
  }, [documents.data]);

  const findDoc = (id: string) => documents.data?.find((d) => d.id === id);
  const selected = docId ? findDoc(docId) : undefined;
  const listed = selected !== undefined && isEligible(selected);

  let summary = "";
  let scoreNote = "";
  if (outcome.phase === "done") {
    const { context } = outcome;
    const modeInfo = MODES.find((m) => m.value === context.mode);
    const title = findDoc(context.docId)?.title ?? context.docId;
    summary = `${countLabel(outcome.items.length)} pour ${quoted(truncate(title, 90))}, mode ${modeInfo?.short ?? context.mode}.`;
    scoreNote = `${modeInfo?.scoreNote ?? ""} ${CONTENT_NOTE}`.trim();
  }

  return (
    <>
      <section className="card recommendations-form" aria-labelledby="recommendations-doc-title">
        <h2 id="recommendations-doc-title">Document de référence</h2>

        {documents.loading && <Loading label="Chargement des documents…" />}
        {documents.error && <ErrorBox message={documents.error} onRetry={documents.reload} />}
        {!documents.loading && !documents.error && groups.length === 0 && (
          <Empty>Aucun document en vigueur ou remplacé n'est accessible dans votre périmètre.</Empty>
        )}
        {!documents.loading && !documents.error && groups.length > 0 && (
          <div className="stack">
            <label htmlFor="recommendations-doc-select">
              Document
              <select id="recommendations-doc-select" value={docId} aria-describedby="recommendations-doc-hint"
                      onChange={(e) => setDocId(e.target.value)}>
                <option value="">Choisissez un document…</option>
                {docId && !listed && <option value={docId}>{selected?.title ?? docId} (hors liste)</option>}
                {groups.map((g) => (
                  <optgroup key={g.label} label={g.label}>
                    {g.docs.map((d) => <option key={d.id} value={d.id}>{documentLabel(d)}</option>)}
                  </optgroup>
                ))}
              </select>
            </label>
            <p id="recommendations-doc-hint" className="recommendations-hint">
              Seuls les documents en vigueur ou remplacés sont proposés. Les recommandations se mettent à jour dès
              que vous changez de document ou de méthode.
            </p>
            {docId && !listed && (
              <p className="alert alert-info small">
                Le document demandé ne figure pas parmi les documents en vigueur ou remplacés de votre périmètre.
              </p>
            )}
            {selected?.status === "superseded" && (
              <p className="alert alert-warn small">
                Ce document est une version antérieure&nbsp;: une version plus récente est en vigueur.
              </p>
            )}
          </div>
        )}

        <fieldset className="recommendations-modes">
          <legend>Méthode de calcul</legend>
          <div className="recommendations-mode-list">
            {MODES.map((m) => (
              <label key={m.value} className="recommendations-mode">
                <input type="radio" name="recommendations-mode" value={m.value} checked={mode === m.value}
                       onChange={() => setMode(m.value)} />
                <span className="recommendations-mode-name">{m.label}</span>
                <span className="recommendations-mode-detail">{m.detail}</span>
              </label>
            ))}
          </div>
        </fieldset>
      </section>

      <Results idPrefix="recommendations-doc" outcome={outcome} onRetry={retry} navigate={navigate}
               idleText="Choisissez un document de référence pour afficher les documents qui lui sont liés."
               summary={summary} scoreNote={scoreNote} />
    </>
  );
}

// ------------------------------------------------------------------ onglet « besoin »

function QueryPanel({ navigate }: { navigate: Navigate }) {
  const [text, setText] = useState("");
  const [invalid, setInvalid] = useState(false);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const { outcome, run, retry } = useLatestRequest<{ text: string }>();

  const search = (value: string) => {
    const trimmed = value.trim();
    if (trimmed.length < QUERY_MIN) {
      setInvalid(true);
      textarea.current?.focus();
      return;
    }
    setInvalid(false);
    run({ text: trimmed }, () => api.recommendForQuery(trimmed));
  };

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    search(text);
  };

  const describedBy = ["recommendations-query-hint", "recommendations-query-count", invalid ? "recommendations-query-error" : null]
    .filter(Boolean).join(" ");

  const summary = outcome.phase === "done"
    ? `${countLabel(outcome.items.length)} pour le besoin ${quoted(truncate(outcome.context.text, 90))}.`
    : "";

  return (
    <>
      <section className="card recommendations-form" aria-labelledby="recommendations-query-title">
        <h2 id="recommendations-query-title">Votre besoin</h2>
        <form className="stack" onSubmit={submit} noValidate>
          <label htmlFor="recommendations-query-text">
            Décrivez votre besoin
            <textarea id="recommendations-query-text" ref={textarea} rows={3} maxLength={QUERY_MAX} value={text}
                      aria-invalid={invalid} aria-describedby={describedBy}
                      onChange={(e) => {
                        setText(e.target.value);
                        if (invalid && e.target.value.trim().length >= QUERY_MIN) setInvalid(false);
                      }} />
          </label>
          <div className="row recommendations-hint">
            <span id="recommendations-query-hint">
              Entre {QUERY_MIN} et {QUERY_MAX} caractères&nbsp;: un sujet, une situation ou une question métier.
            </span>
            <span className="spacer" />
            <span id="recommendations-query-count">{text.length}&nbsp;/&nbsp;{QUERY_MAX}&nbsp;caractères</span>
          </div>
          {invalid && (
            <p id="recommendations-query-error" className="recommendations-error" role="alert">
              Saisissez au moins {QUERY_MIN}&nbsp;caractères.
            </p>
          )}
          <div className="row">
            <button type="submit" className="btn btn-primary">Rechercher des documents</button>
          </div>
        </form>

        <div className="recommendations-examples">
          <p id="recommendations-examples-label" className="recommendations-hint">Exemples de besoins&nbsp;:</p>
          <div className="examples" role="group" aria-labelledby="recommendations-examples-label">
            {QUERY_EXAMPLES.map((example) => (
              <button key={example} type="button" className="chip"
                      onClick={() => { setText(example); search(example); }}>
                {example}
              </button>
            ))}
          </div>
        </div>
      </section>

      <Results idPrefix="recommendations-query" outcome={outcome} onRetry={retry} navigate={navigate}
               idleText="Décrivez votre besoin pour obtenir une sélection de documents pertinents."
               summary={summary} scoreNote={QUERY_SCORE_NOTE} />
    </>
  );
}

// ------------------------------------------------------------------ résultats

interface ResultsProps {
  idPrefix: string;
  outcome: Outcome<unknown>;
  idleText: string;
  summary: string;
  scoreNote: string;
  onRetry: () => void;
  navigate: Navigate;
}

function Results({ idPrefix, outcome, idleText, summary, scoreNote, onRetry, navigate }: ResultsProps) {
  const titleId = `${idPrefix}-results-title`;
  const items = outcome.phase === "done" ? outcome.items : [];

  return (
    <section className="recommendations-results" aria-labelledby={titleId}>
      <h2 id={titleId}>Documents recommandés</h2>

      <div aria-live="polite">
        {outcome.phase === "done" && items.length > 0 && <p className="recommendations-summary">{summary}</p>}
        {outcome.phase === "done" && items.length === 0 && (
          <Empty>Aucun document lié n'a été trouvé dans votre périmètre.</Empty>
        )}
      </div>

      {outcome.phase === "idle" && <Empty>{idleText}</Empty>}
      {outcome.phase === "loading" && <Loading label="Calcul des recommandations…" />}
      {outcome.phase === "error" && (
        <ErrorBox message={outcome.message} onRetry={outcome.retryable ? onRetry : undefined} />
      )}

      {items.length > 0 && (
        <>
          <p className="recommendations-hint">{scoreNote}</p>
          <ol className="recommendations-list">
            {items.map((item, index) => (
              <RecommendationCard key={item.doc_id} item={item} rank={index + 1} navigate={navigate} />
            ))}
          </ol>
        </>
      )}
    </section>
  );
}

function RecommendationCard({ item, rank, navigate }: { item: Recommendation; rank: number; navigate: Navigate }) {
  const superseded = item.status === "superseded";
  const statusClass = item.status === "active" ? "badge badge-good" : superseded ? "badge badge-warn" : "badge";

  return (
    <li className="card recommendations-item">
      <div className="recommendations-item-head">
        <span className="recommendations-rank"><span className="visually-hidden">Rang </span>{rank}</span>
        <div className="recommendations-item-main">
          <h3>
            <button type="button" className="recommendations-link" onClick={() => navigate("documents", item.doc_id)}>
              {item.title}
            </button>
          </h3>
          <div className="badges">
            <span className="badge">{docTypeLabel(item.doc_type)}</span>
            <span className={statusClass}>{statusLabel(item.status)}</span>
            {item.reference && <span className="mono recommendations-reference">{item.reference}</span>}
          </div>
          {superseded && (
            <p className="recommendations-note">
              Version antérieure&nbsp;: ce document a été remplacé par une version plus récente.
            </p>
          )}
        </div>
        <div className="recommendations-score">
          <span className="recommendations-score-value">{scoreFormatter.format(item.score)}</span>
          <span className="stat-label">score global</span>
        </div>
      </div>

      <dl className="recommendations-components">
        {COMPONENTS.map((c) => {
          const value = item.components[c.key];
          const ratio = typeof value === "number" ? Math.min(1, Math.max(0, value)) : null;
          return (
            <div key={c.key}>
              <dt>{c.label}</dt>
              <dd>
                <div className="meter" aria-hidden="true">
                  <span style={{ width: `${(ratio ?? 0) * 100}%` }} />
                </div>
                <span className="recommendations-component-value">{ratio === null ? "—" : formatPercent(ratio)}</span>
              </dd>
            </div>
          );
        })}
      </dl>

      <div className="recommendations-reasons">
        <h4>Pourquoi ce document&nbsp;?</h4>
        {item.reasons.length > 0 ? (
          <ul>{item.reasons.map((reason, i) => <li key={`${i}-${reason}`}>{reason}</li>)}</ul>
        ) : (
          <p className="recommendations-hint">Aucun motif détaillé&nbsp;: le document est retenu pour son score global.</p>
        )}
      </div>

      <div className="recommendations-actions">
        <button type="button" className="btn btn-sm" onClick={() => navigate("explorer", item.doc_id)}>
          Explorer<span className="visually-hidden"> le voisinage de {quoted(item.title)} dans le graphe</span>
        </button>
      </div>
    </li>
  );
}
