import { api } from "../api";
import { Empty, ErrorBox, Loading } from "../components/States";
import { formatNumber } from "../components/format";
import { TYPE_STYLE, relationLabel, typeLabel } from "../components/graphStyle";
import { useAsync } from "../components/useAsync";
import type { GraphStats, Health, User } from "../types";
import { hasRole, type PageKey, type PageProps } from "./contract";
import "./Home.css";

const EXAMPLE_QUESTIONS = [
  "Quelles applications dépendent de CoreNova ?",
  "Quelle est la fréquence de revue périodique des clients à risque élevé ?",
  "Qui fait partie de l'équipe du projet Sentinel ?",
  "Qui est responsable de Sentinel ?",
  "Quel est le plafond du taux d'endettement pour un crédit aux particuliers ?",
  "Quel est le budget du projet Vigilance ?",
];

const WORKFLOW_STEPS = [
  {
    title: "Analyse de la question",
    detail: "Repérage des entités citées (personnes, applications, projets…) et du type de question "
      + "(factuelle, relationnelle, multi-sauts, recherche d'expert, ambiguë), qui fixe le poids accordé au graphe.",
  },
  {
    title: "Recherche hybride",
    detail: "Recherche lexicale BM25, similarité vectorielle et parcours du graphe, combinés par fusion "
      + "des rangs (RRF), exclusivement sur les documents qui vous sont autorisés.",
  },
  {
    title: "Contrôle de suffisance du contexte",
    detail: "Les passages et faits retrouvés doivent couvrir les termes porteurs de sens et les entités de la question.",
  },
  {
    title: "Relance éventuelle",
    detail: "Si le contexte est insuffisant, une seule recherche complémentaire est lancée, élargie aux alias "
      + "et aux entités des meilleurs passages, avec une exploration plus profonde du graphe.",
  },
  {
    title: "Génération ou abstention",
    detail: "La réponse cite ses sources ([C1] pour un passage, [F1] pour un fait du graphe) ; si le contexte "
      + "reste insuffisant, l'assistant s'abstient plutôt que de deviner.",
  },
  {
    title: "Vérification",
    detail: "Les citations qui ne correspondent à aucune source sont retirées et chaque phrase doit être appuyée "
      + "par les sources qu'elle cite.",
  },
];

const PROVIDER_LABELS: Record<string, string> = {
  anthropic: "Anthropic",
  openai_compatible: "API compatible OpenAI",
};

const ROLE_INFO: Record<string, { label: string; detail: string }> = {
  viewer: {
    label: "Lecteur",
    detail: "assistant, exploration du graphe, recommandations et consultation des documents",
  },
  manager: {
    label: "Responsable",
    detail: "fonctions de lecteur et recherche d'experts",
  },
  admin: {
    label: "Administrateur",
    detail: "toutes les fonctions, dont l'ajout et la suppression de documents et le lancement de l'ingestion",
  },
};

interface QuickLink { page: PageKey; title: string; detail: string }

const QUICK_LINKS: QuickLink[] = [
  {
    page: "explorer",
    title: "Explorer le graphe",
    detail: "Parcourir les entités et leurs relations, chacune rattachée à ses documents sources.",
  },
  {
    page: "recommendations",
    title: "Recommandations",
    detail: "Retrouver les documents proches d'un document donné ou d'un besoin décrit en quelques mots.",
  },
  {
    page: "documents",
    title: "Documents",
    detail: "Consulter les documents de votre périmètre : version, statut, diffusion et qualité d'extraction.",
  },
];

const EXPERTS_LINK: QuickLink = {
  page: "experts",
  title: "Experts",
  detail: "Identifier les personnes compétentes sur un domaine, avec les éléments documentaires qui le justifient.",
};

const groupLabel = (group: string) => (group === "ALL" ? "Tous collaborateurs" : group);
const capitalize = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);
const total = (items: { n: number }[]) => items.reduce((acc, item) => acc + item.n, 0);
const plural = (n: number, one: string, many: string) => `${formatNumber(n)} ${n > 1 ? many : one}`;

export default function Home({ user, navigate }: PageProps) {
  const links = hasRole(user, "manager") ? [...QUICK_LINKS, EXPERTS_LINK] : QUICK_LINKS;

  return (
    <>
      <header className="page-header">
        <h1>Bienvenue, {user.display_name}</h1>
        <p>
          Cette plateforme relie les documents internes d'Orizia Banque dans un graphe de connaissances afin de
          répondre à vos questions en citant les passages et les faits qui fondent chaque réponse, ou de
          s'abstenir lorsque les documents ne permettent pas de conclure.
        </p>
      </header>

      <div className="home">
        <ServiceStatus />

        <section className="card home-section" aria-labelledby="home-ask-title">
          <div className="card-title">
            <h2 id="home-ask-title">Poser une question</h2>
            <button type="button" className="btn btn-primary btn-sm" onClick={() => navigate("ask")}>
              Ouvrir l'assistant
            </button>
          </div>
          <p className="home-lead">
            Choisissez un exemple pour l'ouvrir dans l'assistant, ou formulez votre propre question.
          </p>
          <div className="examples">
            {EXAMPLE_QUESTIONS.map((question) => (
              <button key={question} type="button" className="chip" onClick={() => navigate("ask", question)}>
                {question}
              </button>
            ))}
          </div>
          <p className="home-note">
            Ces exemples couvrent les principaux cas traités : relations entre applications et équipes, versions
            contradictoires d'une même règle, homonymie (« Sentinel » désigne à la fois un projet et une
            application) et question sans réponse dans le corpus, qui doit conduire à une abstention.
          </p>
        </section>

        <KeyFigures />

        <div className="split home-cards">
          <section className="card home-section" aria-labelledby="home-workflow-title">
            <h2 id="home-workflow-title">Comment fonctionne l'assistant</h2>
            <p className="home-lead">
              Chaque question suit le même enchaînement d'étapes, orchestré par un workflow LangGraph déterministe.
            </p>
            <ol className="trace home-steps">
              {WORKFLOW_STEPS.map((step) => (
                <li key={step.title} className="trace-step">
                  <div>
                    <strong>{step.title}</strong>
                    <div className="muted">{step.detail}</div>
                  </div>
                </li>
              ))}
            </ol>
          </section>
          <AccessScope user={user} />
        </div>

        <section className="home-section" aria-labelledby="home-links-title">
          <h2 id="home-links-title">Accès rapides</h2>
          <div className={`grid ${links.length === 4 ? "grid-4" : "grid-3"} home-cards`}>
            {links.map((link) => (
              <button key={link.page} type="button" className="card home-link" onClick={() => navigate(link.page)}>
                <span className="home-link-title">
                  {link.title}
                  <span aria-hidden="true">→</span>
                </span>
                <span className="home-link-desc">{link.detail}</span>
              </button>
            ))}
          </div>
        </section>
      </div>
    </>
  );
}

function ServiceStatus() {
  const { data, error, loading, reload } = useAsync(api.health, []);
  return (
    <div className="stack" aria-live="polite">
      {error ? (
        <ErrorBox message={`Impossible de vérifier l'état du service : ${error}`} onRetry={reload} />
      ) : loading && !data ? (
        <p className="small muted">Vérification de l'état du service…</p>
      ) : (
        data && <HealthBanner health={data} />
      )}
    </div>
  );
}

function HealthBanner({ health }: { health: Health }) {
  const offline = health.llm_provider === "offline";
  return (
    <>
      {health.status !== "ok" && (
        <div className="alert alert-warn">
          <span className="alert-icon" aria-hidden="true">!</span>
          <div>
            <strong>Service dégradé :</strong> la base de connaissances ne répond pas ; les recherches et les
            réponses peuvent échouer temporairement.
          </div>
        </div>
      )}
      <div className="alert alert-info">
        <span className="alert-icon" aria-hidden="true">i</span>
        <div>
          {offline ? (
            <div>
              <strong>Mode hors-ligne :</strong> les réponses sont extractives (phrases reprises des documents,
              sans reformulation par un LLM).
            </div>
          ) : (
            <div>
              <strong>Mode génératif :</strong> les réponses sont rédigées par un LLM (fournisseur :{" "}
              {PROVIDER_LABELS[health.llm_provider] ?? health.llm_provider}) à partir des seuls passages
              retrouvés, puis vérifiées avant affichage.
            </div>
          )}
          <div className="small muted">
            Version {health.version} · vectorisation : {health.embedding_provider}
          </div>
        </div>
      </div>
    </>
  );
}

function KeyFigures() {
  const { data, error, loading, reload } = useAsync(api.stats, []);
  return (
    <section className="home-section" aria-labelledby="home-figures-title" aria-busy={loading}>
      <h2 id="home-figures-title">Votre base documentaire en chiffres</h2>
      <p className="home-lead">Chiffres calculés sur les seuls documents de votre périmètre d'accès.</p>
      <div aria-live="polite">
        {error ? (
          <ErrorBox message={error} onRetry={reload} />
        ) : loading && !data ? (
          <Loading label="Chargement des chiffres clés…" />
        ) : (
          data && <Figures stats={data} />
        )}
      </div>
    </section>
  );
}

function Figures({ stats }: { stats: GraphStats }) {
  const countDocuments = (status: string) => stats.documents.find((d) => d.status === status)?.n ?? 0;
  const active = countDocuments("active");
  const superseded = countDocuments("superseded");

  if (active + superseded === 0) {
    return (
      <Empty>
        Aucun document n'est accessible dans votre périmètre pour le moment : les chiffres clés apparaîtront dès
        qu'un document vous sera diffusé.
      </Empty>
    );
  }

  const supersededNote = superseded === 0
    ? "Aucune version remplacée"
    : superseded === 1
      ? "+ 1 version remplacée, conservée pour l'historique"
      : `+ ${formatNumber(superseded)} versions remplacées, conservées pour l'historique`;

  const entityItems = stats.entities.map((e) => ({
    key: e.type, label: typeLabel(e.type), n: e.n, color: TYPE_STYLE[e.type]?.color,
  }));
  const relationItems = stats.relations.map((r) => ({
    key: r.type, label: capitalize(relationLabel(r.type)), n: r.n,
  }));

  return (
    <div className="stack">
      <div className="grid grid-4 home-cards">
        <StatTile value={active} label="Documents en vigueur" note={supersededNote} />
        <StatTile value={stats.chunks} label="Passages indexés"
                  note="Extraits interrogeables par mots-clés et par similarité" />
        <StatTile value={total(stats.entities)} label="Entités"
                  note={`${plural(stats.entities.length, "type", "types")} d'entités`} />
        <StatTile value={total(stats.relations)} label="Relations"
                  note={`${plural(stats.relations.length, "type", "types")} de relations`} />
      </div>
      <div className="grid grid-2 home-cards">
        <div className="card">
          <h3>Entités par type</h3>
          <BarList items={entityItems} emptyText="Aucune entité visible dans votre périmètre." />
        </div>
        <div className="card">
          <h3>Relations par type</h3>
          <BarList items={relationItems} emptyText="Aucune relation visible dans votre périmètre." />
        </div>
      </div>
    </div>
  );
}

function StatTile({ value, label, note }: { value: number; label: string; note: string }) {
  return (
    <div className="card stat">
      <span className="stat-value">{formatNumber(value)}</span>
      <span className="stat-label">{label}</span>
      <span className="home-note">{note}</span>
    </div>
  );
}

interface BarItem { key: string; label: string; n: number; color?: string }

function BarList({ items, emptyText }: { items: BarItem[]; emptyText: string }) {
  if (items.length === 0) return <Empty>{emptyText}</Empty>;
  const sorted = [...items].sort((a, b) => b.n - a.n);
  const max = Math.max(...sorted.map((item) => item.n), 1);
  return (
    <ul className="home-bars">
      {sorted.map((item) => (
        <li key={item.key}>
          <span className="home-bar-label">
            {item.color && <span className="dot" style={{ background: item.color }} aria-hidden="true" />}
            {item.label}
          </span>
          <span className="meter" aria-hidden="true">
            <span style={{ width: `${(item.n / max) * 100}%`, background: item.color }} />
          </span>
          <span className="home-bar-count">{formatNumber(item.n)}</span>
        </li>
      ))}
    </ul>
  );
}

function AccessScope({ user }: { user: User }) {
  return (
    <section className="card home-section" aria-labelledby="home-access-title">
      <h2 id="home-access-title">Votre périmètre d'accès</h2>
      <p className="home-lead">
        Vous ne voyez que les documents diffusés à vos groupes. L'assistant, le graphe, les recommandations et les
        chiffres de cette page se limitent à ce périmètre : un passage non autorisé n'entre jamais dans le contexte
        de l'assistant, et une relation n'apparaît que si l'un au moins de ses documents sources vous est accessible.
      </p>
      <dl className="home-access">
        <div>
          <dt>Groupes de diffusion</dt>
          <dd>
            {user.groups.length > 0 ? (
              <div className="badges">
                {user.groups.map((group) => (
                  <span key={group} className="badge badge-info">{groupLabel(group)}</span>
                ))}
              </div>
            ) : (
              <span className="muted">Aucun groupe</span>
            )}
            <p className="home-note">
              « Tous collaborateurs » ouvre les documents à diffusion générale ; les autres groupes, propres à une
              direction, donnent accès aux documents à diffusion restreinte qui leur sont adressés.
            </p>
          </dd>
        </div>
        <div>
          <dt>Rôles</dt>
          <dd>
            {user.roles.length > 0 ? (
              <ul className="home-roles">
                {user.roles.map((role) => (
                  <li key={role}>
                    <span className="badge badge-accent">{ROLE_INFO[role]?.label ?? role}</span>{" "}
                    {ROLE_INFO[role] && <span className="muted">{ROLE_INFO[role].detail}</span>}
                  </li>
                ))}
              </ul>
            ) : (
              <span className="muted">Aucun rôle</span>
            )}
          </dd>
        </div>
      </dl>
    </section>
  );
}
