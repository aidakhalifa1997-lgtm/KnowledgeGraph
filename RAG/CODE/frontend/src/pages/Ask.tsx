// Assistant de questions-réponses : réponse citée ([C1] passage, [F1] fait du graphe), vérifiée,
// avec abstention lorsque les documents accessibles ne suffisent pas.

import {
  Fragment, useCallback, useEffect, useMemo, useRef, useState,
  type FormEvent, type KeyboardEvent, type ReactNode,
} from "react";
import { ApiError, api } from "../api";
import AnswerText from "../components/AnswerText";
import GraphView from "../components/GraphView";
import { Empty, ErrorBox, Loading } from "../components/States";
import { formatDate, formatMs, formatNumber, formatPercent } from "../components/format";
import { docTypeLabel, statusLabel, typeLabel } from "../components/graphStyle";
import type { AskResponse, Citation, Expert, Fact, TraceStep, User } from "../types";
import { hasRole, type PageProps } from "./contract";
import "./Ask.css";

type Strategy = "auto" | "vector" | "lexical" | "hybrid" | "graph" | "hybrid_graph";
type Navigate = PageProps["navigate"];

const MIN_LENGTH = 3;
const MAX_LENGTH = 500;
const MAX_HISTORY = 10;
const EXCERPT_LENGTH = 400;

const STRATEGIES: { value: Strategy; label: string }[] = [
  { value: "auto", label: "Hybride final (recommandé)" },
  { value: "vector", label: "RAG vectoriel" },
  { value: "lexical", label: "BM25 (lexical)" },
  { value: "hybrid", label: "RAG hybride (BM25 + vecteurs)" },
  { value: "graph", label: "GraphRAG (graphe seul)" },
  { value: "hybrid_graph", label: "Hybride + graphe (sans routage)" },
];

// Stratégie réellement exécutée : le mode « auto » se résout toujours en l'une de celles-ci.
const EXECUTED_STRATEGIES: Record<string, string> = {
  vector: "RAG vectoriel",
  lexical: "BM25 (lexical)",
  hybrid: "RAG hybride (BM25 + vecteurs)",
  graph: "GraphRAG (graphe seul)",
  hybrid_graph: "Hybride + graphe",
};

const QUESTION_TYPES: Record<string, string> = {
  factual: "factuelle",
  relational: "relationnelle",
  multi_hop: "multi-sauts",
  expert: "expertise",
  ambiguous: "ambiguë",
};

const STEP_LABELS: Record<string, string> = {
  analyze: "Analyse",
  retrieve: "Recherche",
  assess: "Contrôle de suffisance",
  expand: "Relance",
  generate: "Génération",
  verify: "Vérification",
  abstain: "Abstention",
};

const RETRIEVERS: Record<string, string> = { graph: "graphe", lexical: "BM25", vector: "vecteurs" };
const STATUS_BADGE: Record<string, string> = { active: "badge-good", superseded: "badge-warn" };
const CONFIDENCE_BADGE: Record<string, string> = { "élevée": "badge-good", moyenne: "badge-info", faible: "badge-warn" };

const EXAMPLES: { kind: string; question: string }[] = [
  { kind: "Relations", question: "Quelles applications dépendent de CoreNova ?" },
  { kind: "Multi-sauts", question: "Qui est le responsable de la procédure qui utilise l'outil AML Watch ?" },
  { kind: "Valeur précise", question: "Quelle est la fréquence de revue périodique des clients à risque élevé ?" },
  { kind: "Expertise", question: "Qui sont les experts en lutte anti-blanchiment ?" },
  { kind: "Nom ambigu", question: "Qui est responsable de Sentinel ?" },
  { kind: "Information absente", question: "Quel est le budget du projet Vigilance ?" },
];

const strategyLabel = (s: string) => EXECUTED_STRATEGIES[s] ?? s;
const questionTypeLabel = (t: string) => QUESTION_TYPES[t] ?? t;
// Accord en français : singulier pour 0 et 1.
const plural = (n: number, one: string, many: string) => `${formatNumber(n)} ${n >= 2 ? many : one}`;
const ratio = (v: number) => Math.min(1, Math.max(0, v));
const asNumber = (v: unknown) => (typeof v === "number" && Number.isFinite(v) ? v : null);
const asText = (v: unknown) => (typeof v === "string" && v.trim() !== "" ? v : null);
const asCount = (v: unknown) => (Array.isArray(v) ? v.length : asNumber(v));
const timeFormatter = new Intl.DateTimeFormat("fr-FR", { timeStyle: "short" });

function generatorLabel(generator: string | null): string {
  if (!generator) return "aucune réponse générée";
  if (generator === "extractive") return "extractif (sans LLM)";
  return generator.startsWith("llm") ? "LLM" : generator;
}

// Coupe un passage long à la frontière d'un mot ; null si le texte tient en entier.
function truncate(text: string): string | null {
  if (text.length <= EXCERPT_LENGTH) return null;
  const cut = text.slice(0, EXCERPT_LENGTH);
  const space = cut.lastIndexOf(" ");
  return `${(space > EXCERPT_LENGTH * 0.6 ? cut.slice(0, space) : cut).trimEnd()}…`;
}

// Les étapes de la trace ont des champs propres à chaque nœud : on n'en retient que les plus parlants.
function stepSummary(step: TraceStep): { details: string[]; note: string | null } {
  const details: (string | null)[] = [];
  let note: string | null = null;
  switch (step.node) {
    case "analyze": {
      const type = asText(step.question_type);
      const strategy = asText(step.strategy);
      const entities = asCount(step.entities);
      const documents = asNumber(step.authorized_documents);
      details.push(
        type && `type\u00a0: ${questionTypeLabel(type)}`,
        strategy && strategyLabel(strategy),
        entities !== null ? plural(entities, "entité reconnue", "entités reconnues") : null,
        documents !== null ? plural(documents, "document autorisé", "documents autorisés") : null,
      );
      break;
    }
    case "retrieve": {
      const attempt = asNumber(step.attempt);
      const chunks = asCount(step.chunks);
      const facts = asCount(step.facts);
      details.push(
        attempt !== null ? `tentative ${attempt}` : null,
        chunks !== null ? plural(chunks, "passage", "passages") : null,
        facts !== null ? plural(facts, "fait", "faits") : null,
      );
      break;
    }
    case "assess": {
      const sufficient = step.sufficient;
      const terms = asNumber(step.term_coverage);
      const entities = asNumber(step.entity_coverage);
      details.push(
        typeof sufficient === "boolean" ? (sufficient ? "contexte suffisant" : "contexte insuffisant") : null,
        terms !== null ? `termes couverts\u00a0: ${formatPercent(ratio(terms))}` : null,
        entities !== null ? `entités couvertes\u00a0: ${formatPercent(ratio(entities))}` : null,
      );
      note = asText(step.reason);
      break;
    }
    case "expand": {
      const seeds = asCount(step.extra_seeds);
      details.push(seeds !== null
        ? plural(seeds, "entité ajoutée comme point d'entrée", "entités ajoutées comme points d'entrée")
        : null);
      break;
    }
    case "generate": {
      details.push(`générateur\u00a0: ${generatorLabel(asText(step.generator))}`);
      const error = asText(step.error);
      note = error && `Erreur signalée\u00a0: ${error}`;
      break;
    }
    case "verify": {
      const valid = asCount(step.valid_citations);
      const invalid = asCount(step.invalid_citations);
      const support = asNumber(step.support_rate);
      details.push(
        valid !== null ? plural(valid, "citation valide", "citations valides") : null,
        invalid !== null ? plural(invalid, "invalide", "invalides") : null,
        support !== null ? `appui\u00a0: ${formatPercent(ratio(support))}` : null,
        step.fallback_extractive === true ? "repli sur la réponse extractive" : null,
      );
      break;
    }
    case "abstain":
      note = asText(step.reason);
      break;
  }
  return { details: details.filter((d): d is string => Boolean(d)), note };
}

function summarize(r: AskResponse): string {
  if (r.status === "abstained") {
    return "L'assistant s'est abstenu\u00a0: les documents accessibles ne suffisent pas pour répondre.";
  }
  const cited = r.citations.filter((c) => c.cited).length + r.facts.filter((f) => f.cited).length;
  return `Réponse disponible, ${plural(cited, "source citée", "sources citées")}.`;
}

interface Entry { id: number; strategy: Strategy; askedAt: Date; response: AskResponse }
interface Pending { question: string; strategy: Strategy }
interface Failure { message: string; retryable: boolean; question: string; strategy: Strategy }

export default function Ask({ user, navigate, param }: PageProps) {
  const [question, setQuestion] = useState(() => param?.trim().slice(0, MAX_LENGTH) ?? "");
  const [strategy, setStrategy] = useState<Strategy>("auto");
  const [formError, setFormError] = useState<string | null>(null);
  const [history, setHistory] = useState<Entry[]>([]);
  const [shownId, setShownId] = useState<number | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);
  const [failure, setFailure] = useState<Failure | null>(null);
  const requestSeq = useRef(0);
  const autoAsked = useRef<string | null>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);

  // Seule la dernière requête lancée peut modifier l'affichage : une réponse plus ancienne
  // arrivée en retard est ignorée.
  const ask = useCallback((text: string, chosen: Strategy) => {
    const seq = ++requestSeq.current;
    setPending({ question: text, strategy: chosen });
    setFailure(null);
    setShownId(null);
    api.ask(text, chosen).then(
      (response) => {
        if (seq !== requestSeq.current) return;
        setHistory((h) => [{ id: seq, strategy: chosen, askedAt: new Date(), response }, ...h].slice(0, MAX_HISTORY));
        setShownId(seq);
        setPending(null);
      },
      (e: unknown) => {
        if (seq !== requestSeq.current) return;
        const status = e instanceof ApiError ? e.status : 0;
        setFailure({
          message: e instanceof Error ? e.message : "Erreur inattendue.",
          retryable: status === 0 || status === 429 || status >= 500,
          question: text,
          strategy: chosen,
        });
        setShownId(null);
        setPending(null);
      },
    );
  }, []);

  // Question transmise par une autre page : pré-remplie, puis posée une seule fois.
  useEffect(() => {
    const text = param?.trim() ?? "";
    if (!text || autoAsked.current === text) return;
    autoAsked.current = text;
    setQuestion(text.slice(0, MAX_LENGTH));
    setStrategy("auto");
    if (text.length > MAX_LENGTH) {
      setFormError(`La question transmise dépasse ${MAX_LENGTH} caractères\u00a0: vérifiez-la avant de l'envoyer.`);
    } else if (text.length >= MIN_LENGTH) {
      ask(text, "auto");
    }
  }, [param, ask]);

  const submit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const text = question.trim();
    if (text.length < MIN_LENGTH) {
      setFormError(`Saisissez au moins ${MIN_LENGTH} caractères.`);
      textarea.current?.focus();
      return;
    }
    setFormError(null);
    ask(text, strategy);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      e.currentTarget.form?.requestSubmit();
    }
  };

  const pickExample = (text: string) => {
    setQuestion(text);
    setFormError(null);
    // Le bouton cliqué disparaît : le focus revient sur la question, au-dessus de l'indicateur de chargement.
    textarea.current?.focus();
    ask(text, strategy);
  };

  const showEntry = (id: number) => {
    setShownId(id);
    setFailure(null);
  };

  const shown = history.find((entry) => entry.id === shownId) ?? null;
  const duplicate = pending !== null && pending.question === question.trim() && pending.strategy === strategy;
  const chosenLabel = STRATEGIES.find((s) => s.value === strategy)?.label;

  let content: ReactNode;
  if (shown) {
    content = <Result key={shown.id} entry={shown} user={user} navigate={navigate} />;
  } else if (pending) {
    content = <Loading label="Analyse de la question, recherche et vérification…" />;
  } else if (failure) {
    content = (
      <ErrorBox
        message={failure.message}
        onRetry={failure.retryable ? () => ask(failure.question, failure.strategy) : undefined}
      />
    );
  } else {
    content = <Examples onPick={pickExample} />;
  }

  return (
    <div className="ask">
      <header className="page-header">
        <h1>Assistant</h1>
        <p>
          Posez une question en langage naturel. L'assistant interroge les documents auxquels vous avez accès et
          le graphe de connaissances, cite chacune de ses sources et s'abstient lorsque les éléments trouvés ne
          suffisent pas.
        </p>
      </header>

      <section className="card" aria-label="Poser une question">
        <form className="ask-box" onSubmit={submit} noValidate>
          <label htmlFor="ask-question" className="ask-label">Votre question</label>
          <textarea
            id="ask-question"
            ref={textarea}
            rows={3}
            value={question}
            maxLength={MAX_LENGTH}
            placeholder={"Par exemple\u00a0: quelles applications dépendent de CoreNova\u00a0?"}
            aria-describedby={`ask-question-help ask-question-count${formError ? " ask-question-error" : ""}`}
            aria-invalid={formError ? true : undefined}
            onChange={(e) => {
              setQuestion(e.target.value);
              setFormError(null);
            }}
            onKeyDown={onKeyDown}
          />
          <div className="ask-form-meta small muted">
            <span id="ask-question-help">
              Entre {MIN_LENGTH} et {MAX_LENGTH} caractères. Envoi rapide&nbsp;: Ctrl + Entrée (⌘ + Entrée sur Mac).
            </span>
            <span id="ask-question-count" className="ask-count">
              {formatNumber(question.length)}&nbsp;/&nbsp;{MAX_LENGTH} caractères
            </span>
          </div>
          {formError && <p id="ask-question-error" className="ask-form-error" role="alert">{formError}</p>}
          <details className="ask-options">
            <summary>Options avancées</summary>
            <label>
              Stratégie de recherche
              <select
                value={strategy}
                onChange={(e) => {
                  const next = STRATEGIES.find((s) => s.value === e.target.value);
                  if (next) setStrategy(next.value);
                }}
              >
                {STRATEGIES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </label>
            <p className="small muted">
              Le mode recommandé adapte la recherche au type de question. Les autres stratégies, fixes, existent
              pour comparer les architectures évaluées et ne sont pas destinées à l'usage courant.
            </p>
          </details>
          <div className="row">
            <button type="submit" className="btn btn-primary" disabled={duplicate}>Poser la question</button>
            {strategy !== "auto" && <span className="badge badge-info">Stratégie imposée&nbsp;: {chosenLabel}</span>}
          </div>
        </form>
        {history.length > 0 && <History entries={history} shownId={shownId} onShow={showEntry} />}
      </section>

      <p className="visually-hidden" role="status">{shown ? summarize(shown.response) : ""}</p>
      <div className="ask-result">
        {shown && pending && (
          <p className="ask-pending small muted" role="status">
            <span className="spinner" aria-hidden="true" />
            Nouvelle question en cours de traitement&nbsp;; sa réponse remplacera l'affichage actuel.
          </p>
        )}
        {content}
      </div>
    </div>
  );
}

function History({ entries, shownId, onShow }: {
  entries: Entry[];
  shownId: number | null;
  onShow: (id: number) => void;
}) {
  return (
    <details className="ask-history">
      <summary>Historique de la session ({entries.length})</summary>
      <p className="small muted">
        Les {MAX_HISTORY} dernières questions restent consultables sans nouvelle recherche tant que vous restez sur
        cette page.
      </p>
      <ol className="ask-history-list">
        {entries.map((entry) => {
          const current = entry.id === shownId;
          const meta = [
            timeFormatter.format(entry.askedAt),
            entry.response.status === "abstained" ? "abstention" : "réponse",
            entry.strategy !== "auto" ? strategyLabel(entry.strategy) : null,
            current ? "affichée" : null,
          ].filter(Boolean).join(" · ");
          return (
            <li key={entry.id}>
              <button
                type="button"
                className="ask-history-item"
                aria-current={current ? "true" : undefined}
                onClick={() => onShow(entry.id)}
              >
                <span>{entry.response.question}</span>
                <span className="small muted">{meta}</span>
              </button>
            </li>
          );
        })}
      </ol>
    </details>
  );
}

function Examples({ onPick }: { onPick: (question: string) => void }) {
  return (
    <section className="card" aria-labelledby="ask-examples-title">
      <h2 id="ask-examples-title">Exemples de questions</h2>
      <p className="small muted">
        Chaque exemple illustre un type de question traité par l'assistant, y compris un cas où il doit s'abstenir.
      </p>
      <ul className="examples ask-examples">
        {EXAMPLES.map(({ kind, question }) => (
          <li key={question}>
            <button type="button" className="chip" onClick={() => onPick(question)}>
              <span className="ask-chip-kind">{kind}</span>{question}
            </button>
          </li>
        ))}
      </ul>
      <hr className="divider" />
      <h3>Lire une réponse</h3>
      <ul className="ask-legend small">
        <li>
          <span className="cite">C1</span> renvoie à un passage de document et <span className="cite fact">F1</span> à
          un fait du graphe de connaissances&nbsp;; un clic sur la référence affiche la source.
        </li>
        <li>Seuls les documents autorisés pour votre profil sont consultés.</li>
        <li>
          Chaque citation est vérifiée&nbsp;; si les éléments trouvés sont insuffisants, l'assistant s'abstient plutôt
          que d'extrapoler.
        </li>
      </ul>
    </section>
  );
}

function Result({ entry, user, navigate }: { entry: Entry; user: User; navigate: Navigate }) {
  const r = entry.response;
  const abstained = r.status === "abstained";
  const [active, setActive] = useState<{ id: string; tick: number } | null>(null);
  const [openOthers, setOpenOthers] = useState({ C: false, F: false });

  // En cas d'abstention, rien n'est une preuve : tous les éléments sont présentés comme « consultés ».
  const groups = useMemo(() => {
    const split = <T extends { cited: boolean }>(items: T[]) => (abstained
      ? { main: items, others: [] as T[] }
      : { main: items.filter((i) => i.cited), others: items.filter((i) => !i.cited) });
    return { citations: split(r.citations), facts: split(r.facts) };
  }, [r, abstained]);

  const validIds = useMemo(() => new Set([...r.citations, ...r.facts].map((item) => item.id)), [r]);
  const collapsed = useMemo(
    () => new Set([...groups.citations.others, ...groups.facts.others].map((item) => item.id)),
    [groups],
  );

  const chains = useMemo(() => {
    const byId = new Map(r.facts.map((f) => [f.id, f]));
    const seen = new Set<string>();
    const result: Fact[][] = [];
    for (const path of r.paths) {
      // Un chemin peut référencer des faits non transmis avec la réponse : ils sont ignorés.
      const steps = path.map((id) => byId.get(id)).filter((f): f is Fact => f !== undefined);
      const key = steps.map((f) => f.id).join(">");
      if (steps.length > 0 && !seen.has(key)) {
        seen.add(key);
        result.push(steps);
      }
    }
    return result.sort((a, b) => b.length - a.length);
  }, [r]);

  const cite = useCallback((id: string) => {
    if (collapsed.has(id)) setOpenOthers((o) => (id.startsWith("F") ? { ...o, F: true } : { ...o, C: true }));
    setActive((a) => ({ id, tick: (a?.tick ?? 0) + 1 }));
  }, [collapsed]);

  // Le compteur « tick » permet de recentrer la même source lors d'un second clic.
  useEffect(() => {
    if (!active) return;
    const target = document.getElementById(`src-${active.id}`);
    if (!target) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    target.scrollIntoView({ block: "nearest", behavior: reduced ? "auto" : "smooth" });
    target.focus({ preventScroll: true });
  }, [active]);

  const missing = r.sufficiency?.missing_terms ?? [];
  const showAlerts = abstained || r.conflicts.length > 0 || r.ambiguity.length > 0;

  return (
    <div className="split">
      <div>
        <article className="card" aria-labelledby="ask-answer-title">
          <div className="badges">
            <span className={`badge ${abstained ? "badge-warn" : "badge-good"}`}>{abstained ? "Abstention" : "Réponse"}</span>
            <span className="badge">Type&nbsp;: {questionTypeLabel(r.question_type)}</span>
            <span className="badge badge-info">{strategyLabel(r.strategy)}</span>
          </div>
          <h2 id="ask-answer-title" className="ask-question">{r.question}</h2>
          <p className="small muted ask-route">
            {r.route_reason && <>Routage&nbsp;: {r.route_reason} · </>}
            stratégie {entry.strategy === "auto" ? "choisie automatiquement" : "imposée"} · durée&nbsp;: {formatMs(r.latency_ms)}
          </p>

          {showAlerts && (
            <div className="stack ask-alerts">
              {abstained && (
                <div className="alert alert-info">
                  <span className="alert-icon" aria-hidden="true">i</span>
                  <div>
                    <strong>Éléments insuffisants</strong>
                    <p>
                      L'assistant préfère ne pas répondre plutôt que d'extrapoler&nbsp;: les passages retrouvés dans
                      les documents accessibles ne permettent pas d'étayer une réponse.
                    </p>
                    {r.sufficiency?.reason && <p>Motif de l'abstention&nbsp;: {r.sufficiency.reason}</p>}
                    {missing.length > 0 && (
                      <div className="ask-terms">
                        <span>Éléments non trouvés&nbsp;:</span>
                        {missing.map((term) => <span key={term} className="badge">{term}</span>)}
                      </div>
                    )}
                  </div>
                </div>
              )}
              {r.conflicts.map((message, i) => (
                <div key={i} className="alert alert-warn">
                  <span className="alert-icon" aria-hidden="true">!</span>
                  <div>
                    <strong>Sources divergentes</strong>
                    <p>{message}</p>
                  </div>
                </div>
              ))}
              {r.ambiguity.map((item) => (
                <div key={item.surface} className="alert alert-info">
                  <span className="alert-icon" aria-hidden="true">?</span>
                  <div>
                    <strong>Nom ambigu</strong>
                    <p>
                      «&nbsp;{item.surface}&nbsp;» peut désigner plusieurs éléments&nbsp;; la réponse couvre chacune
                      de ces interprétations. Précisez votre question pour n'en retenir qu'une.
                    </p>
                    <ul className="ask-candidates">
                      {item.candidates.map((c) => (
                        <li key={c.id}>
                          <span>{c.name}</span>
                          <span className="badge">{typeLabel(c.type)}</span>
                          <button
                            type="button"
                            className="btn btn-sm btn-ghost"
                            aria-label={`Voir dans le graphe\u00a0: ${c.name}`}
                            onClick={() => navigate("explorer", c.id)}
                          >
                            Voir dans le graphe
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div aria-live="polite">
            <AnswerText text={r.answer} validIds={validIds} onCite={cite} />
          </div>

          {r.limits.length > 0 && (
            <div className="ask-limits small muted">
              <h3>Limites de cette réponse</h3>
              <ul>{r.limits.map((limit, i) => <li key={i}>{limit}</li>)}</ul>
            </div>
          )}
        </article>

        {r.experts.length > 0 && (
          <ExpertsCard experts={r.experts} canBrowse={hasRole(user, "manager")} navigate={navigate} />
        )}
        {r.graph.nodes.length > 0 && <GraphCard response={r} abstained={abstained} navigate={navigate} />}
        {chains.length > 0 && <ChainsCard chains={chains} onCite={cite} />}
        <VerificationCard response={r} />
        <TraceCard response={r} />
      </div>

      <div>
        <section className="card" aria-labelledby="ask-sources-title">
          <div className="card-title">
            <h2 id="ask-sources-title">{abstained ? "Documents consultés" : "Sources"}</h2>
            <span className="small muted">{plural(r.citations.length, "passage", "passages")}</span>
          </div>
          {abstained && r.citations.length > 0 && (
            <p className="small muted">
              Passages examinés sans réponse suffisante&nbsp;: ils ne constituent pas une preuve.
            </p>
          )}
          <Group
            {...groups.citations}
            empty="Aucun passage n'a été retrouvé dans les documents accessibles."
            noneCited="Aucun passage n'est cité dans la réponse."
            othersLabel="Autres passages consultés"
            open={openOthers.C}
            onOpenChange={(open) => setOpenOthers((o) => ({ ...o, C: open }))}
            render={(c) => <CitationItem citation={c} active={active?.id === c.id} navigate={navigate} />}
          />
        </section>

        <section className="card" aria-labelledby="ask-facts-title">
          <div className="card-title">
            <h2 id="ask-facts-title">{abstained ? "Faits du graphe consultés" : "Faits du graphe"}</h2>
            <span className="small muted">{plural(r.facts.length, "fait", "faits")}</span>
          </div>
          <Group
            {...groups.facts}
            empty="Aucun fait du graphe n'a été mobilisé pour cette question."
            noneCited="Aucun fait du graphe n'est cité dans la réponse."
            othersLabel="Autres faits consultés"
            open={openOthers.F}
            onOpenChange={(open) => setOpenOthers((o) => ({ ...o, F: open }))}
            render={(f) => <FactItem fact={f} active={active?.id === f.id} navigate={navigate} />}
          />
        </section>
      </div>
    </div>
  );
}

interface GroupProps<T> {
  main: T[];
  others: T[];
  empty: string;
  noneCited: string;
  othersLabel: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  render: (item: T) => ReactNode;
}

// Éléments cités en tête, éléments seulement consultés repliés en dessous.
function Group<T extends { id: string }>(props: GroupProps<T>) {
  const { main, others, empty, noneCited, othersLabel, open, onOpenChange, render } = props;
  if (main.length === 0 && others.length === 0) return <Empty>{empty}</Empty>;
  return (
    <>
      {main.length > 0 ? (
        <ul className="ask-plain-list">{main.map((item) => <li key={item.id}>{render(item)}</li>)}</ul>
      ) : (
        <p className="small muted ask-group-note">{noneCited}</p>
      )}
      {others.length > 0 && (
        <details open={open} onToggle={(e) => onOpenChange(e.currentTarget.open)}>
          <summary>{othersLabel} ({others.length})</summary>
          <ul className="ask-plain-list">{others.map((item) => <li key={item.id}>{render(item)}</li>)}</ul>
        </details>
      )}
    </>
  );
}

function CitationItem({ citation: c, active, navigate }: { citation: Citation; active: boolean; navigate: Navigate }) {
  const [expanded, setExpanded] = useState(false);
  const short = truncate(c.text);
  const textId = `src-${c.id}-text`;
  const meta = [
    [c.reference, c.version && `version ${c.version}`].filter(Boolean).join(", "),
    c.date && formatDate(c.date),
    docTypeLabel(c.doc_type),
    c.section,
    c.page !== null && `page ${c.page}`,
  ].filter(Boolean).join(" · ");
  const ranks = Object.entries(c.retrieval_ranks)
    .sort(([, a], [, b]) => a - b)
    .map(([name, rank]) => `${RETRIEVERS[name] ?? name} (rang ${rank})`)
    .join(", ");

  return (
    <article
      id={`src-${c.id}`}
      tabIndex={-1}
      className={`source-item${active ? " active" : ""}`}
      aria-labelledby={`src-${c.id}-title`}
    >
      <div className="ask-item-head">
        <span className="badge badge-accent">{c.id}</span>
        <h3 id={`src-${c.id}-title`} className="ask-item-title">{c.title}</h3>
        <span className={`badge ${STATUS_BADGE[c.status] ?? ""}`}>{statusLabel(c.status)}</span>
      </div>
      {meta && <p className="ask-meta">{meta}</p>}
      <p id={textId} className="quote">{expanded || !short ? c.text : short}</p>
      {ranks && <p className="ask-meta">Retrouvé par&nbsp;: {ranks}</p>}
      <div className="row ask-item-actions">
        {short && (
          <button
            type="button"
            className="btn btn-sm btn-ghost"
            aria-expanded={expanded}
            aria-controls={textId}
            onClick={() => setExpanded((v) => !v)}
          >
            {expanded ? "Réduire le passage" : "Lire tout le passage"}
          </button>
        )}
        <button type="button" className="btn btn-sm" onClick={() => navigate("documents", c.doc_id)}>
          Ouvrir le document
        </button>
      </div>
    </article>
  );
}

function FactItem({ fact: f, active, navigate }: { fact: Fact; active: boolean; navigate: Navigate }) {
  return (
    <article
      id={`src-${f.id}`}
      tabIndex={-1}
      className={`source-item${active ? " active" : ""}`}
      aria-labelledby={`src-${f.id}-title`}
    >
      <div className="ask-item-head">
        <span className="badge badge-info">{f.id}</span>
        <h3 id={`src-${f.id}-title`} className="ask-item-title">{f.text}</h3>
      </div>
      <p className="ask-meta">
        Confiance {formatPercent(ratio(f.confidence))} · {plural(f.source_doc_ids.length, "document source", "documents sources")}
      </p>
      {f.evidence.length > 0 ? (
        <details>
          <summary>Extraits justificatifs ({f.evidence.length})</summary>
          <ul className="ask-plain-list ask-evidence">
            {f.evidence.map((ev, i) => {
              const docId = ev.chunk_id.split("#")[0];
              return (
                <li key={`${ev.chunk_id}-${i}`}>
                  <p className="quote">«&nbsp;{ev.quote}&nbsp;»</p>
                  {docId.startsWith("doc-") && (
                    <button type="button" className="btn btn-sm btn-ghost" onClick={() => navigate("documents", docId)}>
                      Ouvrir le document
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        </details>
      ) : (
        <p className="ask-meta">Aucun extrait textuel n'est rattaché à ce fait.</p>
      )}
    </article>
  );
}

function ExpertsCard({ experts, canBrowse, navigate }: { experts: Expert[]; canBrowse: boolean; navigate: Navigate }) {
  return (
    <section className="card" aria-labelledby="ask-experts-title">
      <div className="card-title">
        <h2 id="ask-experts-title">Experts identifiés</h2>
        {canBrowse && (
          <button type="button" className="btn btn-sm" onClick={() => navigate("experts")}>
            Recherche d'experts par domaine
          </button>
        )}
      </div>
      <p className="small muted">Classement indicatif, fondé uniquement sur les preuves des documents accessibles.</p>
      <ul className="ask-plain-list grid grid-2 ask-experts">
        {experts.map((x) => (
          <li key={x.person_id} className="source-item">
            <div className="ask-item-head">
              <h3 className="ask-item-title">{x.name}</h3>
              <span className={`badge ${CONFIDENCE_BADGE[x.confidence] ?? ""}`}>Confiance {x.confidence}</span>
            </div>
            <p className="ask-meta">Score {formatNumber(Math.round(x.score * 100) / 100)}</p>
            <p className="small">{x.justification}</p>
            {x.evidence.length > 0 && (
              <details>
                <summary>Preuves documentaires ({x.evidence.length})</summary>
                <ul className="ask-plain-list ask-evidence">
                  {x.evidence.map((ev, i) => (
                    <li key={`${ev.doc_id}-${ev.kind}-${i}`}>
                      <p className="small"><strong>{ev.label}</strong></p>
                      <p className="ask-meta">{ev.doc_title}{ev.doc_date && ` · ${formatDate(ev.doc_date)}`}</p>
                      {ev.quote && <p className="quote">«&nbsp;{ev.quote}&nbsp;»</p>}
                      <button type="button" className="btn btn-sm btn-ghost" onClick={() => navigate("documents", ev.doc_id)}>
                        Ouvrir le document
                      </button>
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function GraphCard({ response: r, abstained, navigate }: { response: AskResponse; abstained: boolean; navigate: Navigate }) {
  const start = r.graph.nodes.find((n) => n.seed) ?? r.graph.nodes[0];
  const counts = `${plural(r.graph.nodes.length, "entité", "entités")} et ${plural(r.graph.edges.length, "relation", "relations")}`;
  return (
    <section className="card" aria-labelledby="ask-graph-title">
      <div className="card-title">
        <h2 id="ask-graph-title">Graphe mobilisé</h2>
        <button type="button" className="btn btn-sm" onClick={() => navigate("explorer", start.id)}>
          Ouvrir dans l'explorateur
        </button>
      </div>
      <p className="small muted">
        {counts}. Les entités repérées dans la question sont agrandies et cerclées
        {abstained ? "." : "\u00a0; les relations citées dans la réponse sont tracées en trait épais."}
      </p>
      <GraphView
        small
        data={r.graph}
        label={`Graphe mobilisé pour la question\u00a0: ${counts}. Le détail de chaque relation figure dans la liste «\u00a0Faits du graphe\u00a0».`}
      />
    </section>
  );
}

function ChainsCard({ chains, onCite }: { chains: Fact[][]; onCite: (id: string) => void }) {
  return (
    <section className="card" aria-labelledby="ask-chains-title">
      <h2 id="ask-chains-title">Raisonnement en plusieurs étapes</h2>
      <p className="small muted">Chemins parcourus dans le graphe à partir des entités de la question, fait après fait.</p>
      <ol className="ask-chains">
        {chains.map((steps) => (
          <li key={steps.map((f) => f.id).join(">")}>
            <span className="badge">{plural(steps.length, "étape", "étapes")}</span>
            {steps.map((f, i) => (
              <Fragment key={i}>
                {i > 0 && (
                  <>
                    <span className="ask-chain-arrow" aria-hidden="true">→</span>
                    <span className="visually-hidden">puis</span>
                  </>
                )}
                <button
                  type="button"
                  className="cite fact"
                  aria-label={`Voir le fait du graphe ${f.id}`}
                  onClick={() => onCite(f.id)}
                >
                  {f.id}
                </button>
                <span>{f.text}</span>
              </Fragment>
            ))}
          </li>
        ))}
      </ol>
    </section>
  );
}

function Gauge({ label, value }: { label: string; value: number }) {
  const share = ratio(value);
  return (
    <div className="ask-gauge">
      <div className="ask-gauge-head">
        <span>{label}</span>
        <strong>{formatPercent(share)}</strong>
      </div>
      <div className="meter" aria-hidden="true"><span style={{ width: `${share * 100}%` }} /></div>
    </div>
  );
}

function VerificationCard({ response: r }: { response: AskResponse }) {
  const v = r.verification;
  const s = r.sufficiency;
  return (
    <section className="card" aria-labelledby="ask-verification-title">
      <h2 id="ask-verification-title">Vérification</h2>
      {v ? (
        <>
          <Gauge label="Phrases de la réponse appuyées par leurs sources" value={v.support_rate} />
          <dl className="ask-dl">
            <div>
              <dt>Citations valides</dt>
              <dd>{formatNumber(v.valid_citations.length)}</dd>
            </div>
            <div>
              <dt>Citations invalides</dt>
              <dd>
                {formatNumber(v.invalid_citations.length)}
                {v.invalid_citations.length > 0 && <span className="mono"> ({v.invalid_citations.join(", ")})</span>}
              </dd>
            </div>
            <div>
              <dt>Mode de génération</dt>
              <dd>
                {generatorLabel(r.generator)}
                {r.llm_model && <span className="mono"> · {r.llm_model}</span>}
              </dd>
            </div>
          </dl>
          {v.unsupported_sentences.length > 0 && (
            <details>
              <summary>Phrases sans appui vérifié ({v.unsupported_sentences.length})</summary>
              <ul className="small">{v.unsupported_sentences.map((sentence, i) => <li key={i}>{sentence}</li>)}</ul>
            </details>
          )}
          {v.sanitized.length > 0 && (
            <>
              <h3 className="ask-subtitle">Corrections appliquées à la réponse</h3>
              <ul className="small">{v.sanitized.map((action, i) => <li key={i}>{action}</li>)}</ul>
            </>
          )}
        </>
      ) : (
        <p className="small muted">
          Aucune réponse n'a été générée&nbsp;: la vérification des citations ne s'applique pas.
        </p>
      )}
      {s && (
        <>
          <h3 className="ask-subtitle">Suffisance du contexte</h3>
          <Gauge label="Termes de la question retrouvés" value={s.term_coverage} />
          <Gauge label="Entités de la question retrouvées" value={s.entity_coverage} />
        </>
      )}
    </section>
  );
}

function TraceCard({ response: r }: { response: AskResponse }) {
  return (
    <section className="card" aria-labelledby="ask-trace-title">
      <div className="card-title">
        <h2 id="ask-trace-title">Déroulé du workflow</h2>
        <span className="small muted">{formatMs(r.latency_ms)} au total</span>
      </div>
      {r.trace.length === 0 ? (
        <p className="small muted">Aucune étape n'a été enregistrée.</p>
      ) : (
        <details>
          <summary>Étapes du workflow ({r.trace.length})</summary>
          <ol className="trace ask-trace">
            {r.trace.map((step, i) => {
              const { details, note } = stepSummary(step);
              return (
                <li key={i} className="trace-step">
                  <div>
                    <strong>{STEP_LABELS[step.node] ?? step.node}</strong>
                    {details.length > 0 && <span className="muted">{details.join(" · ")}</span>}
                    {note && <span className="muted">{note}</span>}
                  </div>
                  <span className="muted ask-trace-ms">{step.ms !== undefined ? formatMs(step.ms) : ""}</span>
                </li>
              );
            })}
          </ol>
        </details>
      )}
    </section>
  );
}
