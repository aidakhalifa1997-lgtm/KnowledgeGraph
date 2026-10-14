import { useState, type FormEvent } from "react";
import { api } from "../api";
import type { User } from "../types";

export default function Login({ onLogin }: { onLogin: (token: string, user: User) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await api.login(username.trim(), password);
      onLogin(result.access_token, result.user);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-wrap">
      <div className="login-card">
        <div className="brand" style={{ padding: 0, marginBottom: 18 }}>
          <Logo />
          <div>
            <span className="brand-name">Orizia — Connaissances</span>
            <span className="brand-sub">Graphe de connaissances documentaire</span>
          </div>
        </div>
        <form className="card stack" onSubmit={submit} aria-describedby="login-help">
          <h1 style={{ fontSize: "1.5rem" }}>Connexion</h1>
          <label>
            Identifiant
            <input type="text" autoComplete="username" value={username} required
                   onChange={(e) => setUsername(e.target.value)} />
          </label>
          <label>
            Mot de passe
            <input type="password" autoComplete="current-password" value={password} required
                   onChange={(e) => setPassword(e.target.value)} />
          </label>
          {error && <div className="alert alert-bad" role="alert">{error}</div>}
          <button className="btn btn-primary" type="submit" disabled={busy || !username || !password}>
            {busy ? "Connexion…" : "Se connecter"}
          </button>
          <p id="login-help" className="small muted" style={{ margin: 0 }}>
            Environnement de démonstration : corpus entièrement fictif. Les comptes de démonstration sont
            décrits dans la documentation d'installation.
          </p>
        </form>
      </div>
    </main>
  );
}

export function Logo() {
  return (
    <svg className="brand-mark" viewBox="0 0 32 32" aria-hidden="true">
      <path d="M9 9L23 12L14 24Z" fill="none" stroke="currentColor" strokeOpacity="0.45" strokeWidth="1.5" />
      <circle cx="9" cy="9" r="4.5" fill="#b4532f" />
      <circle cx="23" cy="12" r="3.8" fill="#2a78d6" />
      <circle cx="14" cy="24" r="4.5" fill="#1baf7a" />
    </svg>
  );
}
