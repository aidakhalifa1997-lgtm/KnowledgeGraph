import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { ApiError, api } from "../api";
import { Empty, ErrorBox, Loading } from "../components/States";
import { formatDate, formatDateTime, formatNumber } from "../components/format";
import { TYPE_STYLE, docTypeLabel, statusLabel, typeLabel } from "../components/graphStyle";
import { useAsync } from "../components/useAsync";
import type { DocumentDetail, DocumentSummary, EntityRef, IngestionResult } from "../types";
import { hasRole, type PageProps } from "./contract";
import "./Documents.css";

const OUTCOMES: Record<string, { label: string; tone: string }> = {
  ingested: { label: "Ingéré", tone: "good" },
  updated: { label: "Mis à jour", tone: "good" },
  unchanged: { label: "Inchangé (contenu identique déjà indexé)", tone: "info" },
  duplicate: { label: "Doublon détecté (non indexé)", tone: "warn" },
  quarantined: { label: "Mis en quarantaine (contenu suspect)", tone: "bad" },
  rejected: { label: "Refusé", tone: "bad" },
  error: { label: "Erreur", tone: "bad" },
};

const statusTone = (status: string) =>
  status === "active" ? "badge-good" : status === "superseded" ? "badge-warn" : "badge-bad";

const groupLabel = (g: string) => (g === "ALL" ? "Tous collaborateurs" : g);

function StatusBadge({ status }: { status: string }) {
  return <span className={`badge ${statusTone(status)}`}>{statusLabel(status)}</span>;
}

function EntityChips({ entities, navigate }: { entities: EntityRef[]; navigate: PageProps["navigate"] }) {
  if (!entities.length) return <p className="muted small">Aucune.</p>;
  return (
    <div className="documents-chips">
      {entities.map((e) => (
        <button key={e.id} type="button" className="chip documents-chip" onClick={() => navigate("explorer", e.id)}
                title={`${typeLabel(e.type)} — ouvrir dans l'explorateur`}>
          <span className="dot" style={{ background: TYPE_STYLE[e.type]?.color ?? "#8a857a" }} aria-hidden="true" />
          {e.name}
          <span className="visually-hidden"> ({typeLabel(e.type)})</span>
        </button>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ détail d'un document
function Detail({ id, admin, navigate, onDeleted }: {
  id: string; admin: boolean; navigate: PageProps["navigate"]; onDeleted: () => void;
}) {
  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [error, setError] = useState<{ status: number; message: string } | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    let alive = true; // une réponse tardive pour un autre document est ignorée
    setDoc(null);
    setError(null);
    setConfirming(false);
    api.document(id)
      .then((d) => { if (alive) setDoc(d); })
      .catch((e: ApiError) => { if (alive) setError({ status: e.status, message: e.message }); });
    return () => { alive = false; };
  }, [id]);

  useEffect(() => { if (doc) heading.current?.focus(); }, [doc]);

  async function remove() {
    setDeleting(true);
    try {
      await api.deleteDocument(id);
      onDeleted();
    } catch (e) {
      setError({ status: (e as ApiError).status, message: (e as ApiError).message });
    } finally {
      setDeleting(false);
    }
  }

  if (error) {
    return error.status === 404
      ? <div className="alert alert-warn" role="alert">Document introuvable ou non autorisé.</div>
      : <ErrorBox message={error.message} />;
  }
  if (!doc) return <Loading label="Chargement du document…" />;

  const meta: [string, string][] = [
    ["Référence", doc.reference ?? "—"],
    ["Version", doc.version ?? "—"],
    ["Date", formatDate(doc.doc_date)],
    ["Type", docTypeLabel(doc.doc_type)],
    ["Direction", doc.department_name ?? "—"],
    ["Rédacteur", doc.author_name ?? "—"],
    ["Classification", doc.classification],
    ["Format", `${doc.format.toUpperCase()}${doc.pages ? ` · ${doc.pages} page(s)` : ""}${doc.ocr_used ? " · lu par OCR" : ""}`],
    ["Fichier", doc.file_name],
  ];

  return (
    <article className="stack" aria-labelledby="documents-detail-title">
      <div>
        <h2 id="documents-detail-title" ref={heading} tabIndex={-1}>{doc.title}</h2>
        <div className="badges">
          <StatusBadge status={doc.status} />
          {doc.diffusion.map((g) => <span key={g} className="badge badge-info">{groupLabel(g)}</span>)}
        </div>
      </div>
      <dl className="documents-meta">
        {meta.map(([k, v]) => (
          <div key={k}><dt>{k}</dt><dd>{v}</dd></div>
        ))}
      </dl>
      {doc.issues.length > 0 && (
        <div className="stack" style={{ gap: 6 }}>
          <h3>Contrôles qualité</h3>
          <ul className="documents-issues">
            {doc.issues.map((issue, i) => (
              <li key={i}>
                <span className={`badge ${issue.severity === "error" ? "badge-bad" : issue.severity === "warning" ? "badge-warn" : "badge-info"}`}>
                  {issue.severity === "error" ? "erreur" : issue.severity === "warning" ? "avertissement" : "information"}
                </span>{" "}
                {issue.message}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="row">
        <button type="button" className="btn btn-sm" onClick={() => navigate("recommendations", doc.id)}>Documents similaires</button>
        <button type="button" className="btn btn-sm" onClick={() => navigate("explorer", doc.id)}>Voir dans le graphe</button>
      </div>
      <div>
        <h3>Décrit</h3>
        <EntityChips entities={doc.describes} navigate={navigate} />
      </div>
      <div>
        <h3>Entités mentionnées ({doc.entities.length})</h3>
        <EntityChips entities={doc.entities} navigate={navigate} />
      </div>
      <details>
        <summary>Passages indexés ({doc.chunks.length})</summary>
        {doc.chunks.length === 0
          ? <p className="muted small">Aucun passage : ce document n'est pas utilisé pour répondre (doublon, quarantaine ou rejet).</p>
          : (
            <ol className="documents-chunks">
              {doc.chunks.map((c) => (
                <li key={c.id}>
                  <div className="small muted">{[c.section, c.page ? `page ${c.page}` : null].filter(Boolean).join(" · ") || "Sans section"}</div>
                  <div className="documents-chunk-text">{c.text}</div>
                </li>
              ))}
            </ol>
          )}
      </details>
      {admin && (
        <div className="documents-danger">
          {!confirming
            ? <button type="button" className="btn btn-sm btn-danger" onClick={() => setConfirming(true)}>Supprimer ce document…</button>
            : (
              <div className="alert alert-bad" role="alertdialog" aria-labelledby="documents-confirm-text">
                <div className="stack" style={{ gap: 8 }}>
                  <span id="documents-confirm-text">
                    Le document, ses passages et les preuves qu'il apporte au graphe seront supprimés. Confirmer ?
                  </span>
                  <div className="row">
                    <button type="button" className="btn btn-sm btn-danger" onClick={remove} disabled={deleting}>
                      {deleting ? "Suppression…" : "Confirmer la suppression"}
                    </button>
                    <button type="button" className="btn btn-sm" onClick={() => setConfirming(false)} disabled={deleting}>Annuler</button>
                  </div>
                </div>
              </div>
            )}
        </div>
      )}
    </article>
  );
}

// ------------------------------------------------------------------ administration
function Administration({ onChanged }: { onChanged: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<IngestionResult | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [sync, setSync] = useState<{ outcomes: Record<string, number>; duration_seconds: number } | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);
  const runs = useAsync(() => api.ingestionRuns(), []);
  const input = useRef<HTMLInputElement>(null);

  async function upload(e: FormEvent) {
    e.preventDefault();
    if (!file) return;
    setUploading(true);
    setUploadError(null);
    setResult(null);
    try {
      setResult(await api.upload(file));
      setFile(null);
      if (input.current) input.current.value = "";
      onChanged();
    } catch (err) {
      setUploadError((err as Error).message);
    } finally {
      setUploading(false);
    }
  }

  async function synchronise() {
    setSyncing(true);
    setSyncError(null);
    try {
      setSync(await api.runIngestion());
      onChanged();
      runs.reload();
    } catch (err) {
      setSyncError((err as Error).message);
    } finally {
      setSyncing(false);
    }
  }

  const outcome = result ? OUTCOMES[result.outcome] ?? { label: result.outcome, tone: "info" } : null;

  return (
    <section className="card stack" aria-labelledby="documents-admin-title">
      <h2 id="documents-admin-title">Administration</h2>
      <div className="grid grid-2">
        <form className="stack" onSubmit={upload}>
          <h3>Téléverser un document</h3>
          <label>
            Fichier PDF, DOCX ou TXT (taille maximale contrôlée par le serveur)
            <input ref={input} type="file" accept=".pdf,.docx,.txt"
                   onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </label>
          <div>
            <button type="submit" className="btn btn-primary" disabled={!file || uploading}>
              {uploading ? "Analyse et indexation…" : "Téléverser et indexer"}
            </button>
          </div>
          <div aria-live="polite">
            {uploadError && <ErrorBox message={uploadError} />}
            {result && outcome && (
              <div className={`alert alert-${outcome.tone === "good" ? "good" : outcome.tone === "bad" ? "bad" : outcome.tone === "warn" ? "warn" : "info"}`}>
                <div className="stack" style={{ gap: 4 }}>
                  <strong>{result.file_name} : {outcome.label}</strong>
                  {result.message && <span className="small">{result.message}</span>}
                  {(result.outcome === "ingested" || result.outcome === "updated") && (
                    <span className="small">{result.chunks} passage(s), {result.relations} relation(s) extraite(s).</span>
                  )}
                  {result.issues.length > 0 && (
                    <ul className="small">{result.issues.map((i, k) => <li key={k}>{i.message}</li>)}</ul>
                  )}
                </div>
              </div>
            )}
          </div>
        </form>
        <div className="stack">
          <h3>Synchroniser le répertoire du corpus</h3>
          <p className="small muted">
            Réindexe les fichiers nouveaux ou modifiés, ignore les fichiers inchangés et retire du graphe les
            documents supprimés du répertoire.
          </p>
          <div>
            <button type="button" className="btn" onClick={synchronise} disabled={syncing}>
              {syncing ? "Synchronisation…" : "Synchroniser le répertoire"}
            </button>
          </div>
          <div aria-live="polite">
            {syncError && <ErrorBox message={syncError} />}
            {sync && (
              <div className="alert alert-info">
                <span>
                  Terminé en {sync.duration_seconds.toFixed(1).replace(".", ",")} s :{" "}
                  {Object.entries(sync.outcomes).filter(([, n]) => n > 0)
                    .map(([k, n]) => `${(OUTCOMES[k]?.label ?? k).split(" (")[0].toLowerCase()} ${n}`).join(", ") || "aucun fichier"}.
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
      <div>
        <h3>Historique des ingestions</h3>
        {runs.loading && <Loading />}
        {runs.error && <ErrorBox message={runs.error} onRetry={runs.reload} />}
        {runs.data && runs.data.length === 0 && <Empty>Aucune exécution enregistrée.</Empty>}
        {runs.data && runs.data.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">Début</th><th scope="col">Durée</th><th scope="col">Fichiers</th>
                  <th scope="col">Ingérés</th><th scope="col">Mis à jour</th><th scope="col">Inchangés</th>
                  <th scope="col">Doublons</th><th scope="col">Quarantaine</th><th scope="col">Refusés</th>
                  <th scope="col">Erreurs</th><th scope="col">Supprimés</th>
                </tr>
              </thead>
              <tbody>
                {runs.data.map((r) => (
                  <tr key={r.id}>
                    <td>{formatDateTime(r.started_at)}</td>
                    <td>{r.duration_seconds.toFixed(1).replace(".", ",")} s</td>
                    <td>{r.files_seen}</td><td>{r.ingested}</td><td>{r.updated}</td><td>{r.unchanged}</td>
                    <td>{r.duplicates}</td><td>{r.quarantined}</td><td>{r.rejected}</td><td>{r.errors}</td><td>{r.deleted}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ page
export default function Documents({ user, navigate, param }: PageProps) {
  const admin = hasRole(user, "admin");
  const list = useAsync(() => api.documents(), []);
  const [selected, setSelected] = useState<string | null>(param?.startsWith("doc-") ? param : null);
  const [text, setText] = useState("");
  const [type, setType] = useState("");
  const [status, setStatus] = useState("");
  const [classification, setClassification] = useState("");

  useEffect(() => { if (param?.startsWith("doc-")) setSelected(param); }, [param]);

  const documents = list.data ?? [];
  const options = useMemo(() => ({
    types: [...new Set(documents.map((d) => d.doc_type))].sort((a, b) => docTypeLabel(a).localeCompare(docTypeLabel(b), "fr")),
    statuses: [...new Set(documents.map((d) => d.status))].sort(),
    classifications: [...new Set(documents.map((d) => d.classification))].sort(),
  }), [documents]);

  const filtered = useMemo(() => {
    const needle = text.trim().toLocaleLowerCase("fr");
    return documents.filter((d: DocumentSummary) =>
      (!needle || [d.title, d.reference ?? "", d.file_name].some((v) => v.toLocaleLowerCase("fr").includes(needle)))
      && (!type || d.doc_type === type) && (!status || d.status === status)
      && (!classification || d.classification === classification));
  }, [documents, text, type, status, classification]);

  const open = (id: string) => {
    setSelected(id);
    navigate("documents", id);
  };

  return (
    <div className="stack" style={{ gap: 20 }}>
      <header className="page-header">
        <h1>Documents</h1>
        <p>
          Catalogue des documents qui vous sont accessibles, avec leur version, leur statut et les éléments du graphe
          qu'ils alimentent.{admin ? " En tant qu'administrateur, vous voyez aussi les documents écartés (doublons, quarantaine) et pouvez gérer le corpus." : ""}
        </p>
      </header>

      <div className="split">
        <section className="card stack" aria-labelledby="documents-list-title">
          <h2 id="documents-list-title" className="visually-hidden">Liste des documents</h2>
          <div className="field-row">
            <label>
              Rechercher
              <input type="search" value={text} placeholder="Titre, référence ou fichier" onChange={(e) => setText(e.target.value)} />
            </label>
            <label>
              Type
              <select value={type} onChange={(e) => setType(e.target.value)}>
                <option value="">Tous</option>
                {options.types.map((t) => <option key={t} value={t}>{docTypeLabel(t)}</option>)}
              </select>
            </label>
            <label>
              Statut
              <select value={status} onChange={(e) => setStatus(e.target.value)}>
                <option value="">Tous</option>
                {options.statuses.map((s) => <option key={s} value={s}>{statusLabel(s)}</option>)}
              </select>
            </label>
            <label>
              Classification
              <select value={classification} onChange={(e) => setClassification(e.target.value)}>
                <option value="">Toutes</option>
                {options.classifications.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </label>
          </div>
          {list.loading && <Loading label="Chargement du catalogue…" />}
          {list.error && <ErrorBox message={list.error} onRetry={list.reload} />}
          {list.data && (
            <>
              <p className="small muted" aria-live="polite" style={{ margin: 0 }}>
                {formatNumber(filtered.length)} document{filtered.length > 1 ? "s" : ""} sur {formatNumber(documents.length)}
              </p>
              {filtered.length === 0
                ? <Empty>Aucun document ne correspond à ces critères.</Empty>
                : (
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th scope="col">Titre</th><th scope="col">Référence</th><th scope="col">Date</th>
                          <th scope="col">Type</th><th scope="col">Statut</th><th scope="col">Classification</th>
                          <th scope="col">Passages</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filtered.map((d) => (
                          <tr key={d.id} className={`clickable${selected === d.id ? " documents-selected" : ""}`} onClick={() => open(d.id)}>
                            <td>
                              <button type="button" className="documents-title-btn" aria-current={selected === d.id ? "true" : undefined}
                                      onClick={(e) => { e.stopPropagation(); open(d.id); }}>
                                {d.title}
                              </button>
                              <div className="small muted">
                                {d.format.toUpperCase()}{d.ocr_used ? " · OCR" : ""}
                              </div>
                            </td>
                            <td className="nowrap">{d.reference ?? "—"}{d.version ? ` v${d.version}` : ""}</td>
                            <td className="nowrap">{formatDate(d.date)}</td>
                            <td>{docTypeLabel(d.doc_type)}</td>
                            <td><StatusBadge status={d.status} /></td>
                            <td>{d.classification}</td>
                            <td>{d.chunks}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
            </>
          )}
        </section>

        <section className="card" aria-live="polite" aria-label="Détail du document">
          {selected
            ? <Detail key={selected} id={selected} admin={admin} navigate={navigate}
                      onDeleted={() => { setSelected(null); navigate("documents"); list.reload(); }} />
            : <Empty>Sélectionnez un document pour afficher ses métadonnées, ses passages et les entités qu'il mentionne.</Empty>}
        </section>
      </div>

      {admin && <Administration onChanged={list.reload} />}
    </div>
  );
}
