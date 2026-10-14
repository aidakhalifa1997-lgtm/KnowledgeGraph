import type { ReactNode } from "react";

export function Loading({ label = "Chargement…" }: { label?: string }) {
  return (
    <div className="state" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <div className="small" style={{ marginTop: 8 }}>{label}</div>
    </div>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="alert alert-bad" role="alert">
      <span className="alert-icon" aria-hidden="true">!</span>
      <div className="stack" style={{ gap: 6 }}>
        <span>{message}</span>
        {onRetry && <button className="btn btn-sm" onClick={onRetry}>Réessayer</button>}
      </div>
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="state small">{children}</div>;
}
