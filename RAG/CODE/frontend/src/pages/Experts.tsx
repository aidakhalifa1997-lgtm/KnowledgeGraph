// Recherche d'experts : classement explicable, fondé sur des preuves documentaires typées et
// limité aux documents accessibles. Réservée aux profils « manager » et « admin ».

import { useCallback, useEffect, useId, useRef, useState, type FormEvent } from "react";
import { ApiError, api } from "../api";
import { Empty, ErrorBox, Loading } from "../components/States";
import { formatDate, formatNumber, formatPercent } from "../components/format";
import { useAsync } from "../components/useAsync";
import type { Domain, Expert, ExpertsResponse } from "../types";
import { hasRole, type PageProps } from "./contract";
import "./Experts.css";

type Navigate = PageProps["navigate"];

// Bornes imposées par l'API sur le paramètre « domain ».
const MIN_LENGTH = 2;
const MAX_LENGTH = 120;

const CONFIDENCE_BADGE: Record<string, string> = { "élevée": "badge-good", moyenne: "badge-info", faible: "badge-warn" };

const NOT_FOUND_MESSAGE = "Domaine non reconnu\u00a0: choisissez un domaine de la liste ou reformulez.";
const FORBIDDEN_MESSAGE =
  "Accès refusé\u00a0: la recherche d'experts nécessite le rôle «\u00a0manager\u00a0» ou «\u00a0admin\u00a0». "
  + "Si vos droits ont changé, reconnectez-vous ou adressez-vous à l'administrateur de la plateforme.";

type Search =
  | { status: "idle" }
  | { status: "loading"; query: string }
  | { status: "error"; query: string; message: string; retryable: boolean }
  | { status: "done"; query: string; response: ExpertsResponse };

interface RankedExpert { expert: Expert; rank: number; tied: boolean }

// Accord en français : singulier pour 0 et 1.
const plural = (n: number, one: string, many: string) => `${formatNumber(n)} ${n >= 2 ? many : one}`;
const formatScore = (v: number) => formatNumber(Math.round(v * 100) / 100);
const isDomainId = (v: string) => v.startsWith("dom:");
const sameText = (a: string, b: string) => a.toLocaleLowerCase("fr") === b.toLocaleLowerCase("fr");
// Le serveur sépare les motifs par « ; » sans espace : on rétablit l'espace insécable française.
const frenchList = (s: string) => s.split(/\s*;\s*/).filter(Boolean).join("\u00a0; ");

function validate(value: string): string | null {
  if (value.length < MIN_LENGTH) return `Saisissez un domaine ou une compétence (${MIN_LENGTH} caractères au moins).`;
  if (value.length > MAX_LENGTH) return `${MAX_LENGTH} caractères au maximum\u00a0: reformulez plus brièvement.`;
  return null;
}

function describeError(e: unknown): { message: string; retryable: boolean } {
  if (!(e instanceof ApiError)) return { message: "Erreur inattendue lors de la recherche.", retryable: true };
  if (e.status === 404) return { message: NOT_FOUND_MESSAGE, retryable: false };
  if (e.status === 403) return { message: FORBIDDEN_MESSAGE, retryable: false };
  return { message: e.message, retryable: e.status === 0 || e.status === 429 || e.status >= 500 };
}

// Classement « olympique » : deux scores égaux partagent le même rang.
function rankExperts(experts: Expert[]): RankedExpert[] {
  const sorted = [...experts].sort((a, b) => b.score - a.score);
  return sorted.map((expert) => {
    const same = sorted.filter((x) => x.score === expert.score);
    return { expert, rank: sorted.indexOf(same[0]) + 1, tied: same.length > 1 };
  });
}

export default function Experts({ user, navigate, param }: PageProps) {
  return (
    <div className="experts">
      <header className="page-header">
        <h1>Recherche d'experts</h1>
        <p>
          Le classement agrège des preuves documentaires typées (expertise déclarée, responsabilité d'une
          application, propriété d'une procédure, pilotage ou participation à un projet, rédaction de documents),
          pondérées selon leur force probante et la récence du document. Être cité ne vaut pas expertise&nbsp;: une
          simple mention ne compte que faiblement, dans une limite fixe.
        </p>
      </header>
      {hasRole(user, "manager") ? (
        <ExpertSearch navigate={navigate} param={param} />
      ) : (
        <div className="alert alert-warn">
          <span className="alert-icon" aria-hidden="true">!</span>
          <div>
            La recherche d'experts est réservée aux profils disposant du rôle «&nbsp;manager&nbsp;» ou
            «&nbsp;admin&nbsp;». Elle exploite des informations relatives aux personnes&nbsp;: son accès est donc
            restreint. Adressez-vous à votre responsable si vous avez besoin d'identifier un interlocuteur.
          </div>
        </div>
      )}
    </div>
  );
}

function ExpertSearch({ navigate, param }: Pick<PageProps, "navigate" | "param">) {
  const query = param?.trim() ?? "";
  const domains = useAsync(() => api.domains(), []);
  const [text, setText] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [search, setSearch] = useState<Search>({ status: "idle" });
  const requestSeq = useRef(0);

  // Seule la dernière requête lancée peut modifier l'affichage.
  const run = useCallback((value: string) => {
    const seq = ++requestSeq.current;
    setSearch({ status: "loading", query: value });
    api.experts(value).then(
      (response) => {
        if (seq === requestSeq.current) setSearch({ status: "done", query: value, response });
      },
      (e: unknown) => {
        if (seq === requestSeq.current) setSearch({ status: "error", query: value, ...describeError(e) });
      },
    );
  }, []);

  // Le domaine recherché est porté par l'URL (#/experts/<domaine>) : lien partageable, retour arrière opérant.
  useEffect(() => {
    setText(isDomainId(query) ? "" : query);
    const problem = query ? validate(query) : null;
    setFormError(problem);
    if (!query || problem) setSearch({ status: "idle" });
    else run(query);
    return () => { requestSeq.current += 1; };
  }, [query, run]);

  const choose = (value: string) => {
    setFormError(null);
    if (value === query) run(value);
    else navigate("experts", value);
  };

  const submit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const value = text.trim();
    const problem = validate(value);
    setFormError(problem);
    if (!problem) choose(value);
  };

  const selectedId = search.status === "done" ? search.response.domain.id : isDomainId(query) ? query : null;
  const announce = search.status === "loading"
    ? "Recherche des experts en cours…"
    : search.status === "done"
      ? `${plural(search.response.experts.length, "personne classée", "personnes classées")} pour le domaine «\u00a0${search.response.domain.name}\u00a0».`
      : "";

  return (
    <>
      <section className="card" aria-labelledby="experts-choose-title">
        <h2 id="experts-choose-title">Choisir un domaine</h2>
        <p className="small muted">
          Sélectionnez un domaine référencé ou saisissez librement une compétence&nbsp;: elle sera rattachée au
          domaine correspondant.
        </p>
        <form className="field-row" role="search" onSubmit={submit} noValidate>
          <label>
            Domaine ou compétence
            <input
              type="search"
              value={text}
              maxLength={MAX_LENGTH}
              placeholder={"Ex.\u00a0: conformité KYC, DevOps"}
              aria-invalid={formError ? true : undefined}
              aria-describedby={formError ? "experts-form-error" : undefined}
              onChange={(e) => {
                setText(e.target.value);
                if (formError) setFormError(null);
              }}
            />
          </label>
          <button type="submit" className="btn btn-primary">Rechercher</button>
        </form>
        {formError && <p id="experts-form-error" className="experts-form-error" role="alert">{formError}</p>}

        <h3 className="experts-subtitle">Domaines référencés</h3>
        <p className="small muted" aria-live="polite">
          {domains.data && domains.data.length > 0 && !domains.loading
            ? `${plural(domains.data.length, "domaine référencé", "domaines référencés")}. Le chiffre indique le nombre `
              + "d'experts déclarés dans les documents qui vous sont accessibles."
            : ""}
        </p>
        <DomainChips
          domains={domains.data}
          loading={domains.loading}
          error={domains.error}
          onRetry={domains.reload}
          selectedId={selectedId}
          onChoose={choose}
        />
      </section>

      <p className="visually-hidden" role="status" aria-live="polite">{announce}</p>
      <section className="card experts-results" aria-labelledby="experts-results-title"
               aria-busy={search.status === "loading"}>
        <Results search={search} onRetry={run} navigate={navigate} />
      </section>
    </>
  );
}

interface DomainChipsProps {
  domains: Domain[] | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  selectedId: string | null;
  onChoose: (id: string) => void;
}

function DomainChips({ domains, loading, error, onRetry, selectedId, onChoose }: DomainChipsProps) {
  if (loading) return <Loading label="Chargement des domaines…" />;
  if (error) return <ErrorBox message={`Liste des domaines indisponible\u00a0: ${error}`} onRetry={onRetry} />;
  if (!domains || domains.length === 0) {
    return <Empty>Aucun domaine n'est encore référencé. La saisie libre reste possible.</Empty>;
  }
  return (
    <ul className="examples experts-domains">
      {domains.map((d) => {
        const selected = d.id === selectedId;
        return (
          <li key={d.id}>
            <button type="button" className="chip experts-chip" aria-pressed={selected} onClick={() => onChoose(d.id)}>
              {selected && <span aria-hidden="true">✓</span>}
              {d.name}
              {d.declared_experts > 0 && (
                <>
                  <span className="experts-chip-count" aria-hidden="true">{d.declared_experts}</span>
                  <span className="visually-hidden">
                    , {plural(d.declared_experts, "expert déclaré", "experts déclarés")}
                  </span>
                </>
              )}
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function Results({ search, onRetry, navigate }: { search: Search; onRetry: (query: string) => void; navigate: Navigate }) {
  if (search.status !== "done") {
    return (
      <>
        <h2 id="experts-results-title">Résultats</h2>
        {search.status === "idle" && (
          <Empty>Choisissez un domaine ou saisissez une compétence pour afficher les personnes à solliciter.</Empty>
        )}
        {search.status === "loading" && <Loading label="Recherche des experts…" />}
        {search.status === "error" && (
          <ErrorBox message={search.message} onRetry={search.retryable ? () => onRetry(search.query) : undefined} />
        )}
      </>
    );
  }

  const { domain, limits, experts } = search.response;
  const ranked = rankExperts(experts);
  const topScore = ranked[0]?.expert.score ?? 0;
  const reformulated = !isDomainId(search.query) && !sameText(search.query, domain.name);

  return (
    <>
      <div className="card-title">
        <h2 id="experts-results-title">Experts — {domain.name}</h2>
        <span className="badge">{plural(experts.length, "personne classée", "personnes classées")}</span>
      </div>
      {reformulated && (
        <p className="small muted">
          Saisie «&nbsp;{search.query}&nbsp;» rattachée au domaine «&nbsp;{domain.name}&nbsp;».
        </p>
      )}
      <div className="alert alert-info experts-limits">
        <span className="alert-icon" aria-hidden="true">i</span>
        <div>
          <p className="experts-limits-title">Usage et limites</p>
          <p>{limits}</p>
        </div>
      </div>
      {ranked.length === 0 ? (
        <Empty>Aucune personne n'est rattachée à ce domaine dans les documents qui vous sont accessibles.</Empty>
      ) : (
        <>
          <p className="small muted experts-note">
            Le nombre de mentions est indiqué à titre de comparaison&nbsp;: il ne mesure pas l'expertise.
          </p>
          <ol className="experts-list">
            {ranked.map((r) => (
              <ExpertCard key={r.expert.person_id} {...r} topScore={topScore} navigate={navigate} />
            ))}
          </ol>
        </>
      )}
    </>
  );
}

function ExpertCard({ expert: x, rank, tied, topScore, navigate }: RankedExpert & { topScore: number; navigate: Navigate }) {
  const nameId = useId();
  const share = topScore > 0 ? Math.min(1, Math.max(0, x.score / topScore)) : 0;
  return (
    <li className="source-item experts-card">
      <span className="experts-rank" aria-hidden="true">{rank}</span>
      <div className="experts-body">
        <div className="experts-head">
          <h3 id={nameId}>
            <span className="visually-hidden">Rang {rank}{tied ? " ex æquo" : ""}&nbsp;: </span>
            {x.name}
          </h3>
          {tied && <span className="small muted" aria-hidden="true">ex æquo</span>}
          <span className={`badge ${CONFIDENCE_BADGE[x.confidence] ?? ""}`}>Confiance {x.confidence}</span>
        </div>
        <div className="experts-score">
          <div className="meter" aria-hidden="true"><span style={{ width: `${share * 100}%` }} /></div>
          <span className="small">
            Score <strong>{formatScore(x.score)}</strong>
            <span className="visually-hidden">, soit {formatPercent(share)} du meilleur score</span>
          </span>
        </div>
        <p><span className="experts-label">Justification&nbsp;:</span> {frenchList(x.justification)}</p>
        {x.mention_count !== undefined && (
          <p className="small muted">Mentions dans les documents&nbsp;: {formatNumber(x.mention_count)}</p>
        )}
        {x.evidence.length > 0 ? (
          <details className="experts-evidence">
            <summary>Preuves documentaires ({x.evidence.length})</summary>
            <p className="small muted">
              Poids&nbsp;: force probante du type de preuve, pondérée par la récence du document.
            </p>
            <ul className="experts-evidence-list">
              {x.evidence.map((ev, i) => (
                <li key={`${ev.kind}-${ev.doc_id}-${i}`} className="experts-evidence-item">
                  <div className="experts-evidence-head">
                    <span className="experts-evidence-label">{ev.label}</span>
                    <span className="badge">poids {formatScore(ev.weight)}</span>
                  </div>
                  <p className="small muted">
                    <button type="button" className="experts-doc" onClick={() => navigate("documents", ev.doc_id)}>
                      <span className="visually-hidden">Ouvrir le document </span>{ev.doc_title}
                    </button>
                    {" · "}
                    {ev.doc_date ? <time dateTime={ev.doc_date}>{formatDate(ev.doc_date)}</time> : "sans date"}
                  </p>
                  {ev.quote && <blockquote className="quote experts-quote">«&nbsp;{ev.quote}&nbsp;»</blockquote>}
                </li>
              ))}
            </ul>
          </details>
        ) : (
          <p className="small muted">Aucune preuve documentaire détaillée.</p>
        )}
        <div className="row">
          <button type="button" className="btn btn-sm" aria-describedby={nameId}
                  onClick={() => navigate("explorer", x.person_id)}>
            Voir dans le graphe
          </button>
        </div>
      </div>
    </li>
  );
}
