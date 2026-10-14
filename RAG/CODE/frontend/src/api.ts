// Client HTTP de l'API : jeton porté en en-tête, erreurs normalisées, aucune donnée en cache.

import type {
  AskResponse, DocumentDetail, DocumentSummary, Domain, EntityDetail, EntitySearchResult, ExpertsResponse,
  GraphData, GraphStats, Health, IngestionResult, IngestionRun, Recommendation, SchemaInfo, User,
} from "./types";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

let token: string | null = null;
let onUnauthorized: (() => void) | null = null;

export function setToken(value: string | null) {
  token = value;
}

export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler;
}

function describe(status: number, detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return "Saisie invalide : vérifiez le contenu du formulaire.";
  if (status === 0) return "Serveur injoignable. Vérifiez votre connexion.";
  if (status === 429) return "Trop de requêtes, patientez quelques secondes.";
  if (status >= 500) return "Erreur du serveur. Réessayez dans un instant.";
  return `Erreur ${status}`;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  let response: Response;
  try {
    response = await fetch(`/api${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, describe(0, null));
  }
  if (response.status === 401 && path !== "/auth/login") {
    onUnauthorized?.();
  }
  const payload = response.headers.get("content-type")?.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    throw new ApiError(response.status, describe(response.status, payload?.detail));
  }
  return payload as T;
}

const q = (params: Record<string, string | number | undefined>) => {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => v !== undefined && v !== "" && search.set(k, String(v)));
  const s = search.toString();
  return s ? `?${s}` : "";
};

export const api = {
  health: () => request<Health>("/health"),
  login: (username: string, password: string) =>
    request<{ access_token: string; user: User }>("/auth/login", {
      method: "POST", body: JSON.stringify({ username, password }),
    }),
  me: () => request<User>("/auth/me"),
  ask: (question: string, strategy: string) =>
    request<AskResponse>("/ask", { method: "POST", body: JSON.stringify({ question, strategy }) }),
  stats: () => request<GraphStats>("/graph/stats"),
  schema: () => request<SchemaInfo>("/graph/schema"),
  searchEntities: (text: string) => request<EntitySearchResult[]>(`/graph/search${q({ q: text })}`),
  overview: (limit = 60) => request<GraphData>(`/graph/overview${q({ limit })}`),
  node: (id: string) => request<EntityDetail | DocumentDetail>(`/graph/node/${encodeURIComponent(id)}`),
  neighborhood: (id: string, depth = 1) =>
    request<GraphData>(`/graph/neighborhood/${encodeURIComponent(id)}${q({ depth })}`),
  domains: () => request<Domain[]>("/experts/domains"),
  experts: (domain: string) => request<ExpertsResponse>(`/experts${q({ domain })}`),
  recommendForDocument: (id: string, mode: string) =>
    request<Recommendation[]>(`/recommendations/document/${encodeURIComponent(id)}${q({ mode })}`),
  recommendForQuery: (text: string) =>
    request<Recommendation[]>("/recommendations/query", { method: "POST", body: JSON.stringify({ text }) }),
  documents: () => request<DocumentSummary[]>("/documents"),
  document: (id: string) => request<DocumentDetail>(`/documents/${encodeURIComponent(id)}`),
  upload: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<IngestionResult>("/documents", { method: "POST", body });
  },
  deleteDocument: (id: string) => request<{ deleted: string }>(`/documents/${encodeURIComponent(id)}`, { method: "DELETE" }),
  runIngestion: () => request<{ run_id: string; duration_seconds: number; outcomes: Record<string, number> }>(
    "/ingestion/run", { method: "POST" }),
  ingestionRuns: () => request<IngestionRun[]>("/ingestion/runs"),
};
