import { Suspense, lazy, useCallback, useEffect, useState, type ReactNode } from "react";
import { api, setToken, setUnauthorizedHandler } from "./api";
import { Loading } from "./components/States";
import Login, { Logo } from "./pages/Login";
import { hasRole, type PageKey } from "./pages/contract";
import type { User } from "./types";

const Home = lazy(() => import("./pages/Home"));
const Ask = lazy(() => import("./pages/Ask"));
const Explorer = lazy(() => import("./pages/Explorer"));
const Experts = lazy(() => import("./pages/Experts"));
const Recommendations = lazy(() => import("./pages/Recommendations"));
const Documents = lazy(() => import("./pages/Documents"));

// Le jeton vit en mémoire de session (sessionStorage) : il disparaît à la fermeture de l'onglet.
const STORAGE_KEY = "orizia.session";

interface NavItem { key: PageKey; label: string; icon: ReactNode; role?: "manager" | "admin" }

const icon = (d: string) => (
  <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
       strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={d} /></svg>
);

const NAV: NavItem[] = [
  { key: "home", label: "Accueil", icon: icon("M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z") },
  { key: "ask", label: "Assistant", icon: icon("M4 5h16v11H8l-4 4zM8 9h8M8 12h5") },
  { key: "explorer", label: "Explorer le graphe", icon: icon("M6 6m-2.5 0a2.5 2.5 0 1 0 5 0a2.5 2.5 0 1 0-5 0M18 8m-2.5 0a2.5 2.5 0 1 0 5 0a2.5 2.5 0 1 0-5 0M10 18m-2.5 0a2.5 2.5 0 1 0 5 0a2.5 2.5 0 1 0-5 0M8.3 7l7.3 1M7 8.3l2 7.4M16 10l-4.4 6") },
  { key: "experts", label: "Experts", icon: icon("M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0"), role: "manager" },
  { key: "recommendations", label: "Recommandations", icon: icon("M12 3l2.6 5.6 6 .7-4.5 4.1 1.2 6L12 16.5 6.7 19.4l1.2-6L3.4 9.3l6-.7z") },
  { key: "documents", label: "Documents", icon: icon("M7 3h7l5 5v13H7zM14 3v5h5M10 13h6M10 17h6") },
];

function parseHash(): { page: PageKey; param?: string } {
  const [, page, ...rest] = window.location.hash.split("/");
  const known = NAV.some((n) => n.key === page);
  return { page: known ? (page as PageKey) : "home", param: rest.length ? decodeURIComponent(rest.join("/")) : undefined };
}

export default function App() {
  const [session, setSession] = useState<{ token: string; user: User } | null>(() => {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });
  const [route, setRoute] = useState(parseHash);

  const logout = useCallback(() => {
    setToken(null);
    try { sessionStorage.removeItem(STORAGE_KEY); } catch { /* stockage indisponible */ }
    setSession(null);
  }, []);

  useEffect(() => {
    setToken(session?.token ?? null);
    setUnauthorizedHandler(logout);
  }, [session, logout]);

  // Session restaurée depuis l'onglet : si le jeton a expiré, l'API répond 401 et la session est fermée.
  useEffect(() => {
    if (session) api.me().catch(() => undefined);
  }, []);

  useEffect(() => {
    const onHash = () => setRoute(parseHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    const item = NAV.find((n) => n.key === route.page);
    document.title = `${item?.label ?? "Accueil"} — Orizia Connaissances`;
    document.getElementById("main")?.focus();
  }, [route.page]);

  const navigate = useCallback((page: PageKey, param?: string) => {
    window.location.hash = `/${page}${param ? `/${encodeURIComponent(param)}` : ""}`;
  }, []);

  if (!session) {
    return (
      <Login onLogin={(token, user) => {
        setToken(token);
        try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ token, user })); } catch { /* non bloquant */ }
        setSession({ token, user });
      }} />
    );
  }

  const user = session.user;
  const visibleNav = NAV.filter((n) => !n.role || hasRole(user, n.role));
  const allowed = visibleNav.some((n) => n.key === route.page);
  const page = allowed ? route.page : "home";
  const props = { user, navigate, param: route.param };

  return (
    <div className="app">
      {/* Lien d'évitement : déplace le focus sans modifier l'ancre (qui sert à la navigation). */}
      <button type="button" className="skip-link" onClick={() => document.getElementById("main")?.focus()}>
        Aller au contenu
      </button>
      <aside className="sidebar">
        <div className="brand">
          <Logo />
          <div>
            <span className="brand-name">Orizia</span>
            <span className="brand-sub">Gestion des connaissances</span>
          </div>
        </div>
        <nav className="nav" aria-label="Navigation principale">
          {visibleNav.map((item) => (
            <button key={item.key} type="button" aria-current={page === item.key ? "page" : undefined}
                    onClick={() => navigate(item.key)}>
              {item.icon}<span>{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div>
            <div style={{ color: "var(--ink)" }}>{user.display_name}</div>
            <div>{user.roles.join(", ")} · {user.groups.length} groupe(s)</div>
          </div>
          <button className="btn btn-sm" type="button" onClick={logout}>Se déconnecter</button>
        </div>
      </aside>
      <main id="main" className="main" tabIndex={-1}>
        <Suspense fallback={<Loading />}>
          {page === "home" && <Home {...props} />}
          {page === "ask" && <Ask {...props} />}
          {page === "explorer" && <Explorer {...props} />}
          {page === "experts" && <Experts {...props} />}
          {page === "recommendations" && <Recommendations {...props} />}
          {page === "documents" && <Documents {...props} />}
        </Suspense>
      </main>
    </div>
  );
}
