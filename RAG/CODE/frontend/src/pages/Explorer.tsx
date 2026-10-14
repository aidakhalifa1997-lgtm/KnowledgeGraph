import { useEffect, useMemo, useRef, useState, type RefObject } from "react";
import { ApiError, api } from "../api";
import GraphView from "../components/GraphView";
import { Empty, ErrorBox, Loading } from "../components/States";
import { formatDate, formatNumber, formatPercent } from "../components/format";
import { TYPE_STYLE, docTypeLabel, relationLabel, statusLabel, typeLabel } from "../components/graphStyle";
import type { DocumentDetail, EntityDetail, GraphData, GraphNode } from "../types";
import type { PageProps } from "./contract";
import "./Explorer.css";

type Depth = 1 | 2;
type NodeDetail = EntityDetail | DocumentDetail;
type Relation = NonNullable<EntityDetail["relations"]>[number];
type Navigate = PageProps["navigate"];
type FocusHandler = (id: string) => void;
type HeadingRef = RefObject<HTMLHeadingElement | null>;

const OVERVIEW_LIMIT = 60;
const MIN_QUERY_LENGTH = 2;
const SEARCH_DELAY_MS = 300;
const TOP_ENTITIES = 10;
// L'API ne renvoie que les dix premiers documents qui mentionnent une entité.
const ENTITY_DOCUMENTS_LIMIT = 10;

// Relations propres au voisinage d'un document, absentes des libellés communs.
const DOCUMENT_RELATION_LABELS: Record<string, string> = {
  MENTIONS: "mentionne",
  AUTHORED_BY: "rédigé par",
  ISSUED_BY: "émis par",
  SUPERSEDES: "remplace",
  DUPLICATE_OF: "doublon de",
};

const ROLE_LABELS: Record<string, string> = { lead: "chef de projet", sponsor: "sponsor", member: "membre" };

const STATUS_TONES: Record<string, string> = {
  validated: "badge-good",
  active: "badge-good",
  candidate: "badge-warn",
  superseded: "badge-warn",
  duplicate: "badge-warn",
  quarantined: "badge-bad",
  rejected: "badge-bad",
};

const edgeLabel = (label: string) => DOCUMENT_RELATION_LABELS[label] ?? relationLabel(label);
const capitalize = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);
const plural = (n: number, one: string, many: string) => `${formatNumber(n)} ${n > 1 ? many : one}`;
const typeColor = (type: string) => TYPE_STYLE[type]?.color ?? "var(--ink-3)";
const isDocumentId = (id: string) => id.startsWith("doc-");
const isDocument = (detail: NodeDetail): detail is DocumentDetail => isDocumentId(detail.id);
const isNotFound = (error: unknown) => error instanceof ApiError && error.status === 404;
const messageOf = (error: unknown) => (error instanceof Error ? error.message : "Erreur inattendue.");
const loadOverview = () => api.overview(OVERVIEW_LIMIT);

/* ------------------------------------------------------------------ chargement */

interface KeyedRequest<T> {
  key: string;
  load: () => Promise<T>;
}

interface RequestState<T> {
  data: T | null;
  error: unknown;
  loading: boolean;
  retry: () => void;
}

interface Settled<T> {
  key: string;
  attempt: number;
  data: T | null;
  error: unknown;
}

// La clé résume tous les paramètres de la requête : seule la réponse correspondant à la clé
// courante est affichée, si bien qu'une réponse tardive (clics rapprochés) n'écrase jamais la plus récente.
function useKeyedRequest<T>(request: KeyedRequest<T> | null): RequestState<T> {
  const key = request?.key ?? null;
  const [settled, setSettled] = useState<Settled<T> | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!request) return;
    let alive = true;
    request.load().then(
      (data) => { if (alive) setSettled({ key: request.key, attempt, data, error: null }); },
      (error: unknown) => { if (alive) setSettled({ key: request.key, attempt, data: null, error }); },
    );
    return () => { alive = false; };
    // `request.load` ne dépend que des paramètres résumés par la clé : inutile de le suivre.
  }, [key, attempt]);

  const current = settled !== null && settled.key === key && settled.attempt === attempt ? settled : null;
  return {
    data: current?.data ?? null,
    error: current?.error ?? null,
    loading: key !== null && current === null,
    retry: () => setAttempt((n) => n + 1),
  };
}

interface Row {
  id: string;
  label: string;
  source: GraphNode;
  target: GraphNode;
}

// Arêtes dont les deux extrémités sont présentes, c'est-à-dire celles effectivement dessinées.
function graphRows(data: GraphData): Row[] {
  const nodes = new Map(data.nodes.map((node) => [node.id, node]));
  return data.edges.flatMap((edge) => {
    const source = nodes.get(edge.source);
    const target = nodes.get(edge.target);
    return source && target ? [{ id: edge.id, label: edge.label, source, target }] : [];
  });
}

/* ------------------------------------------------------------------ page */

export default function Explorer({ navigate, param }: PageProps) {
  const focus = param?.trim() || null;
  const [depth, setDepth] = useState<Depth>(1);
  const [tableOpen, setTableOpen] = useState(false);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const pendingFocus = useRef(false);

  // Le voisinage d'un document ne dépend pas de la profondeur.
  const documentFocus = focus !== null && isDocumentId(focus);
  const effectiveDepth: Depth = documentFocus ? 1 : depth;

  const overview = useKeyedRequest({ key: "overview", load: loadOverview });
  const neighborhood = useKeyedRequest(focus === null ? null : {
    key: `${effectiveDepth}|${focus}`,
    load: () => api.neighborhood(focus, effectiveDepth),
  });
  const node = useKeyedRequest(focus === null ? null : { key: focus, load: () => api.node(focus) });

  const graph = focus === null ? overview : neighborhood;
  const rows = useMemo(() => (graph.data ? graphRows(graph.data) : []), [graph.data]);

  // Après une sélection au clavier, le focus rejoint le titre de la fiche dès qu'elle est affichée.
  useEffect(() => {
    if (pendingFocus.current && headingRef.current) {
      pendingFocus.current = false;
      headingRef.current.focus();
    }
  });

  const focusOn: FocusHandler = (id) => {
    if (id === focus) {
      headingRef.current?.focus();
      return;
    }
    pendingFocus.current = true;
    navigate("explorer", id);
  };

  const showOverview = () => {
    pendingFocus.current = true;
    navigate("explorer");
  };

  const centerName = graph.data?.nodes.find((n) => n.id === focus)?.name ?? focus;
  const nodeCount = graph.data?.nodes.length ?? 0;
  const relationCount = plural(rows.length, "relation", "relations");
  const depthNote = documentFocus ? "" : ` (${plural(effectiveDepth, "saut", "sauts")})`;
  const summary = !graph.data
    ? ""
    : focus === null
      ? `${plural(nodeCount, "entité", "entités")} et ${relationCount} affichées.`
      : `Centré sur «\u00a0${centerName}\u00a0»${depthNote} : `
        + `${plural(nodeCount, "élément", "éléments")} et ${relationCount} affichés.`;
  const explanation = focus === null
    ? `Entités les plus connectées visibles avec vos droits (${OVERVIEW_LIMIT} au plus). Cliquez sur un nœud, `
      + "ou passez par la recherche, pour centrer le graphe sur une entité et afficher sa fiche."
    : documentFocus
      ? "Entités mentionnées ou décrites par le document, son auteur, l'entité émettrice et ses autres versions."
      : "Éléments reliés à l'entité sélectionnée. Une relation n'apparaît que si l'un au moins de ses documents "
        + "sources vous est accessible.";
  const loadingLabel = focus === null ? "Chargement de la vue d'ensemble…" : "Chargement du voisinage…";
  const graphEmpty = graph.data !== null && (nodeCount === 0 || (focus !== null && rows.length === 0));

  return (
    <>
      <header className="page-header">
        <h1>Explorer le graphe</h1>
        <p>
          Le graphe relie les personnes, entités organisationnelles, applications, projets, procédures, domaines et
          concepts extraits des documents. Chaque relation renvoie aux documents et aux extraits qui l'attestent ;
          seuls les éléments issus de documents de votre périmètre d'accès sont affichés.
        </p>
      </header>
      <div className="explorer">
        <EntitySearch onPick={focusOn} />

        {focus !== null && isNotFound(node.error) ? (
          <NotFound id={focus} headingRef={headingRef} onBack={showOverview} />
        ) : (
          <div className="split explorer-split">
            <section className="card" aria-labelledby="explorer-graph-title">
              <div className="card-title">
                <h2 id="explorer-graph-title">{focus === null ? "Vue d'ensemble" : "Voisinage"}</h2>
                {focus !== null && (
                  <div className="row">
                    {!documentFocus && (
                      <label className="explorer-depth">
                        Profondeur
                        <select value={depth} onChange={(e) => setDepth(e.target.value === "2" ? 2 : 1)}>
                          <option value={1}>1 saut</option>
                          <option value={2}>2 sauts</option>
                        </select>
                      </label>
                    )}
                    <button type="button" className="btn btn-sm" onClick={showOverview}>
                      Retour à la vue d'ensemble
                    </button>
                  </div>
                )}
              </div>
              <p className="small muted explorer-explain">{explanation}</p>
              <p className="small explorer-summary" aria-live="polite">{summary}</p>

              <div className="explorer-stage" aria-busy={graph.loading}>
                {graph.error ? (
                  <ErrorBox message={messageOf(graph.error)} onRetry={graph.retry} />
                ) : graph.loading || !graph.data ? (
                  <Loading label={loadingLabel} />
                ) : graphEmpty ? (
                  <Empty>
                    {focus === null
                      ? "Aucune entité n'est visible avec vos droits actuels."
                      : "Aucune relation visible autour de cet élément avec vos droits actuels."}
                  </Empty>
                ) : (
                  <GraphView
                    data={graph.data}
                    selected={focus}
                    onSelect={(id) => navigate("explorer", id)}
                    label={`${summary} Une vue tabulaire des relations est disponible sous le graphe.`}
                  />
                )}
              </div>

              {!graphEmpty && rows.length > 0 && (
                <RelationTable rows={rows} focus={focus} open={tableOpen} onToggle={setTableOpen} onFocus={focusOn} />
              )}
            </section>

            <aside className="card explorer-panel"
                 aria-label={focus === null ? "Entités les plus connectées" : "Fiche de l'élément sélectionné"}
                   aria-busy={focus === null ? overview.loading : node.loading}>
              {focus === null ? (
                <OverviewPanel data={overview.data} headingRef={headingRef} onFocus={focusOn} />
              ) : (
                <NodePanel request={node} headingRef={headingRef} onFocus={focusOn} navigate={navigate} />
              )}
            </aside>
          </div>
        )}
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ recherche */

function EntitySearch({ onPick }: { onPick: FocusHandler }) {
  const [query, setQuery] = useState("");
  const [term, setTerm] = useState("");

  useEffect(() => {
    const timer = window.setTimeout(() => setTerm(query.trim()), SEARCH_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [query]);

  const search = useKeyedRequest(term.length >= MIN_QUERY_LENGTH
    ? { key: term, load: () => api.searchEntities(term) }
    : null);

  const trimmed = query.trim();
  const active = trimmed.length >= MIN_QUERY_LENGTH;
  const pending = active && (trimmed !== term || search.loading);
  const results = active && !pending ? search.data : null;

  let status = "";
  if (trimmed.length > 0 && !active) status = `Saisissez au moins ${MIN_QUERY_LENGTH} caractères.`;
  else if (pending) status = "Recherche en cours…";
  else if (results) {
    status = results.length === 0
      ? `Aucune entité visible ne correspond à «\u00a0${trimmed}\u00a0».`
      : `${plural(results.length, "entité trouvée", "entités trouvées")}.`;
  }

  const pick = (id: string) => {
    setQuery("");
    setTerm("");
    onPick(id);
  };

  return (
    <section className="card explorer-search">
      <form role="search" aria-label="Recherche d'entités"
            onSubmit={(e) => { e.preventDefault(); setTerm(query.trim()); }}>
        <label>
          Rechercher une entité
          <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} autoComplete="off"
                 placeholder="Ex. : CoreNova, Sentinel, Nadia Benali" aria-describedby="explorer-search-hint" />
        </label>
        <p id="explorer-search-hint" className="small muted explorer-hint">
          Nom, alias ou sigle d'une personne, d'une application, d'un projet, d'une procédure…
        </p>
      </form>
      <p className="small muted explorer-status" aria-live="polite">{status}</p>
      {active && !pending && search.error !== null && (
        <ErrorBox message={messageOf(search.error)} onRetry={search.retry} />
      )}
      {results && results.length > 0 && (
        <ul className="explorer-results" aria-label="Résultats de la recherche">
          {results.map((result) => (
            <li key={result.id}>
              <button type="button" className="explorer-result" onClick={() => pick(result.id)}>
                <span className="dot" style={{ background: typeColor(result.type) }} aria-hidden="true" />
                <span className="explorer-result-name">{result.name}</span>
                {result.status !== "validated" && <StatusBadge status={result.status} />}
                <span className="explorer-result-meta">{typeLabel(result.type)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/* ------------------------------------------------------------------ vue tabulaire */

interface RelationTableProps {
  rows: Row[];
  focus: string | null;
  open: boolean;
  onToggle: (open: boolean) => void;
  onFocus: FocusHandler;
}

function RelationTable({ rows, focus, open, onToggle, onFocus }: RelationTableProps) {
  const sorted = useMemo(
    () => [...rows].sort((a, b) => a.source.name.localeCompare(b.source.name, "fr")),
    [rows],
  );
  return (
    <details className="explorer-table" open={open} onToggle={(e) => onToggle(e.currentTarget.open)}>
      <summary>Vue tabulaire des relations affichées ({formatNumber(rows.length)})</summary>
      <div className="table-wrap">
        <table>
          <caption className="visually-hidden">Relations affichées dans le graphe : source, relation et cible</caption>
          <thead>
            <tr>
              <th scope="col">Source</th>
              <th scope="col">Relation</th>
              <th scope="col">Cible</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((row) => (
              <tr key={row.id}>
                <td><NodeCell node={row.source} focus={focus} onFocus={onFocus} /></td>
                <td>{edgeLabel(row.label)}</td>
                <td><NodeCell node={row.target} focus={focus} onFocus={onFocus} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

function NodeCell({ node, focus, onFocus }: { node: GraphNode; focus: string | null; onFocus: FocusHandler }) {
  return (
    <>
      {node.id === focus ? (
        <strong>{node.name}</strong>
      ) : (
        <button type="button" className="explorer-link" onClick={() => onFocus(node.id)}>{node.name}</button>
      )}
      <span className="explorer-cell-type">{typeLabel(node.type)}</span>
    </>
  );
}

/* ------------------------------------------------------------------ fiches */

function OverviewPanel({ data, headingRef, onFocus }: {
  data: GraphData | null;
  headingRef: HeadingRef;
  onFocus: FocusHandler;
}) {
  const top = data
    ? [...data.nodes].sort((a, b) => (b.degree ?? 0) - (a.degree ?? 0)).slice(0, TOP_ENTITIES)
    : [];
  return (
    <>
      <h2 id="explorer-panel-title" ref={headingRef} tabIndex={-1}>Entités les plus connectées</h2>
      <p className="small muted">
        Choisissez une entité pour afficher sa fiche : relations, documents qui la mentionnent et extraits qui
        attestent chaque relation.
      </p>
      {top.length > 0 && (
        <ol className="explorer-results">
          {top.map((n) => (
            <li key={n.id}>
              <button type="button" className="explorer-result" onClick={() => onFocus(n.id)}>
                <span className="dot" style={{ background: typeColor(n.type) }} aria-hidden="true" />
                <span className="explorer-result-name">{n.name}</span>
                <span className="explorer-result-meta">
                  {typeLabel(n.type)}
                  {n.degree !== undefined && ` · ${plural(n.degree, "relation", "relations")}`}
                </span>
              </button>
            </li>
          ))}
        </ol>
      )}
    </>
  );
}

function NodePanel({ request, headingRef, onFocus, navigate }: {
  request: RequestState<NodeDetail>;
  headingRef: HeadingRef;
  onFocus: FocusHandler;
  navigate: Navigate;
}) {
  if (request.error) return <ErrorBox message={messageOf(request.error)} onRetry={request.retry} />;
  if (!request.data) return <Loading label="Chargement de la fiche…" />;
  return isDocument(request.data) ? (
    <DocumentPanel doc={request.data} headingRef={headingRef} navigate={navigate} />
  ) : (
    <EntityPanel entity={request.data} headingRef={headingRef} onFocus={onFocus} navigate={navigate} />
  );
}

function PanelHeading({ type, title, headingRef }: { type: string; title: string; headingRef: HeadingRef }) {
  return (
    <>
      <p className="explorer-kicker">
        <span className="dot" style={{ background: typeColor(type) }} aria-hidden="true" />
        {typeLabel(type)}
      </p>
      <h2 id="explorer-panel-title" ref={headingRef} tabIndex={-1}>{title}</h2>
    </>
  );
}

function StatusBadge({ status }: { status: string }) {
  return <span className={["badge", STATUS_TONES[status]].filter(Boolean).join(" ")}>{statusLabel(status)}</span>;
}

function EntityPanel({ entity, headingRef, onFocus, navigate }: {
  entity: EntityDetail;
  headingRef: HeadingRef;
  onFocus: FocusHandler;
  navigate: Navigate;
}) {
  const aliases = entity.aliases ?? [];
  const documents = entity.documents ?? [];
  const relations = entity.relations ?? [];
  const titles = new Map(documents.map((doc) => [doc.id, doc.title]));
  const groups = new Map<string, Relation[]>();
  for (const relation of relations) {
    groups.set(relation.relation, [...(groups.get(relation.relation) ?? []), relation]);
  }

  return (
    <>
      <PanelHeading type={entity.type} title={entity.name} headingRef={headingRef} />
      <div className="badges">
        <StatusBadge status={entity.status} />
        {entity.source === "referential" && <span className="badge badge-info">référentiel</span>}
      </div>
      <dl className="explorer-facts">
        {aliases.length > 0 && (
          <div><dt>Alias</dt><dd>{aliases.join(", ")}</dd></div>
        )}
        {entity.mentions !== undefined && (
          <div><dt>Mentions</dt><dd>{plural(entity.mentions, "passage", "passages")}</dd></div>
        )}
      </dl>

      <section className="explorer-section" aria-labelledby="explorer-documents-title">
        <h3 id="explorer-documents-title">Documents</h3>
        {documents.length === 0 ? (
          <p className="small muted">Aucun document de votre périmètre ne mentionne cette entité.</p>
        ) : (
          <ul className="explorer-list">
            {documents.map((doc) => (
              <li key={doc.id} className="explorer-doc">
                <button type="button" className="explorer-link" onClick={() => navigate("documents", doc.id)}>
                  {doc.title}
                </button>
                <span className="badges">
                  <StatusBadge status={doc.status} />
                  <span className="badge">{docTypeLabel(doc.doc_type)}</span>
                </span>
              </li>
            ))}
          </ul>
        )}
        {documents.length >= ENTITY_DOCUMENTS_LIMIT && (
          <p className="small muted explorer-note">Liste limitée aux {ENTITY_DOCUMENTS_LIMIT} premiers documents.</p>
        )}
      </section>

      <section className="explorer-section" aria-labelledby="explorer-relations-title">
        <h3 id="explorer-relations-title">Relations ({formatNumber(relations.length)})</h3>
        {relations.length === 0 ? (
          <p className="small muted">Aucune relation visible avec vos droits actuels.</p>
        ) : (
          [...groups].map(([type, items]) => (
            <div key={type} className="explorer-group">
              <h4>{capitalize(relationLabel(type))} ({formatNumber(items.length)})</h4>
              <ul className="explorer-list">
                {items.map((relation) => (
                  <RelationItem key={`${relation.outgoing ? "out" : "in"}|${relation.other_id}`} relation={relation}
                                selfName={entity.name} titles={titles} onFocus={onFocus} navigate={navigate} />
                ))}
              </ul>
            </div>
          ))
        )}
      </section>
    </>
  );
}

function RelationItem({ relation: r, selfName, titles, onFocus, navigate }: {
  relation: Relation;
  selfName: string;
  titles: Map<string, string>;
  onFocus: FocusHandler;
  navigate: Navigate;
}) {
  const self = <span>{selfName}</span>;
  const other = (
    <span className="explorer-entity">
      <span className="dot" style={{ background: typeColor(r.other_type) }} aria-hidden="true" />
      <button type="button" className="explorer-link" onClick={() => onFocus(r.other_id)}>{r.other_name}</button>
    </span>
  );
  const sources = r.source_doc_ids.length === 0
    ? "aucun document source visible"
    : plural(r.source_doc_ids.length, "document source", "documents sources");
  const meta = [r.confidence !== null ? `Confiance : ${formatPercent(r.confidence)}` : null, sources]
    .filter(Boolean)
    .join(" · ");

  return (
    <li className="source-item">
      <p className="explorer-rel-line">
        {r.outgoing ? self : other}
        <span aria-hidden="true">→</span>
        <span className="visually-hidden">{relationLabel(r.relation)}</span>
        {r.outgoing ? other : self}
      </p>
      {(r.roles.length > 0 || r.source === "referential") && (
        <div className="badges explorer-rel-badges">
          {r.roles.map((role) => (
            <span key={role} className="badge badge-accent">rôle : {ROLE_LABELS[role] ?? role}</span>
          ))}
          {r.source === "referential" && <span className="badge badge-info">référentiel</span>}
        </div>
      )}
      <p className="small muted explorer-rel-meta">{capitalize(meta)}</p>
      {(r.quotes.length > 0 || r.source_doc_ids.length > 0) && (
        <details className="explorer-evidence">
          <summary>Preuves ({formatNumber(r.quotes.length)})</summary>
          {r.quotes.length > 0 ? (
            <ul className="explorer-quotes">
              {r.quotes.map((quote, index) => (
                <li key={index}>
                  <blockquote className="quote explorer-quote">«&nbsp;{quote}&nbsp;»</blockquote>
                </li>
              ))}
            </ul>
          ) : (
            <p className="small muted">Aucun extrait disponible.</p>
          )}
          {r.source_doc_ids.length > 0 && (
            <div className="explorer-sources">
              <span className="muted">Documents sources :</span>
              <ul>
                {r.source_doc_ids.map((id) => (
                  <li key={id}>
                    <button type="button" className="explorer-link" onClick={() => navigate("documents", id)}>
                      {titles.get(id) ?? <span className="mono">{id}</span>}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </details>
      )}
    </li>
  );
}

function DocumentPanel({ doc, headingRef, navigate }: {
  doc: DocumentDetail;
  headingRef: HeadingRef;
  navigate: Navigate;
}) {
  return (
    <>
      <PanelHeading type="Document" title={doc.title} headingRef={headingRef} />
      {doc.status === "superseded" && (
        <div className="alert alert-warn explorer-note">
          <span className="alert-icon" aria-hidden="true">!</span>
          <span>Version remplacée par une version plus récente ; elle reste consultable pour l'historique.</span>
        </div>
      )}
      <dl className="explorer-facts">
        <div><dt>Référence</dt><dd>{doc.reference ?? "—"}</dd></div>
        <div><dt>Version</dt><dd>{doc.version ?? "—"}</dd></div>
        <div><dt>Date</dt><dd>{formatDate(doc.doc_date)}</dd></div>
        <div><dt>Type</dt><dd>{docTypeLabel(doc.doc_type)}</dd></div>
        <div><dt>Statut</dt><dd><StatusBadge status={doc.status} /></dd></div>
        {doc.department_name && <div><dt>Émetteur</dt><dd>{doc.department_name}</dd></div>}
        {doc.author_name && <div><dt>Auteur</dt><dd>{doc.author_name}</dd></div>}
        <div><dt>Entités citées</dt><dd>{formatNumber(doc.entities.length)}</dd></div>
      </dl>
      <div className="row explorer-actions">
        <button type="button" className="btn btn-primary btn-sm" onClick={() => navigate("documents", doc.id)}>
          Ouvrir le document
        </button>
        <button type="button" className="btn btn-sm" onClick={() => navigate("recommendations", doc.id)}>
          Documents similaires
        </button>
      </div>
    </>
  );
}

function NotFound({ id, headingRef, onBack }: { id: string; headingRef: HeadingRef; onBack: () => void }) {
  return (
    <section className="card" aria-labelledby="explorer-missing-title">
      <h2 id="explorer-missing-title" ref={headingRef} tabIndex={-1}>Élément introuvable</h2>
      <div className="alert alert-warn" role="alert">
        <span className="alert-icon" aria-hidden="true">!</span>
        <div className="stack">
          <span>
            L'élément <span className="mono">{id}</span> est introuvable ou ne vous est pas accessible : il
            n'existe pas, ou aucun document de votre périmètre d'accès ne le mentionne.
          </span>
          <div>
            <button type="button" className="btn btn-sm" onClick={onBack}>Retour à la vue d'ensemble</button>
          </div>
        </div>
      </div>
    </section>
  );
}
