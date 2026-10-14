// Types des réponses de l'API (miroir des structures renvoyées par FastAPI).

export interface User {
  username: string;
  display_name: string;
  roles: string[];
  groups: string[];
}

export interface Health {
  status: string;
  version: string;
  neo4j: string;
  llm_provider: string;
  embedding_provider: string;
}

export interface Citation {
  id: string;
  chunk_id: string;
  doc_id: string;
  title: string;
  reference: string | null;
  version: string | null;
  date: string | null;
  status: string;
  doc_type: string;
  section: string;
  page: number | null;
  text: string;
  cited: boolean;
  retrieval_ranks: Record<string, number>;
  score: number;
}

export interface EntityRef {
  id: string;
  name: string;
  type: string;
}

export interface Fact {
  id: string;
  text: string;
  relation: string;
  roles: string[];
  confidence: number;
  subject: EntityRef;
  object: EntityRef;
  source_doc_ids: string[];
  evidence: { chunk_id: string; quote: string }[];
  cited: boolean;
  score: number;
}

export interface GraphNode {
  id: string;
  name: string;
  type: string;
  status?: string;
  seed?: boolean;
  degree?: number;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label: string;
  roles?: string[];
  confidence?: number | null;
  cited?: boolean;
  docs?: string[];
}

export interface GraphData {
  center?: string | null;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface TraceStep {
  node: string;
  ms?: number;
  [key: string]: unknown;
}

export interface Ambiguity {
  surface: string;
  candidates: EntityRef[];
}

export interface ExpertEvidence {
  kind: string;
  label: string;
  doc_id: string;
  doc_title: string;
  doc_date: string | null;
  quote: string | null;
  weight: number;
}

export interface Expert {
  person_id: string;
  name: string;
  score: number;
  confidence: string;
  justification: string;
  mention_count?: number;
  evidence: ExpertEvidence[];
}

export interface AskResponse {
  question: string;
  answer: string;
  status: "answered" | "abstained";
  question_type: string;
  strategy: string;
  route_reason: string;
  citations: Citation[];
  facts: Fact[];
  graph: GraphData;
  paths: string[][];
  conflicts: string[];
  ambiguity: Ambiguity[];
  experts: Expert[];
  sufficiency: {
    sufficient: boolean;
    term_coverage: number;
    entity_coverage: number;
    missing_terms: string[];
    reason: string;
  } | null;
  verification: {
    valid_citations: string[];
    invalid_citations: string[];
    support_rate: number;
    unsupported_sentences: string[];
    sanitized: string[];
  } | null;
  generator: string | null;
  llm_model: string | null;
  limits: string[];
  trace: TraceStep[];
  latency_ms: number;
  llm_enabled: boolean;
}

export interface GraphStats {
  entities: { type: string; n: number }[];
  relations: { type: string; n: number }[];
  documents: { status: string; n: number }[];
  chunks: number;
}

export interface SchemaInfo {
  entity_types: { name: string; description: string }[];
  relation_types: { name: string; subjects: string[]; objects: string[]; description: string; derived: boolean }[];
}

export interface EntitySearchResult {
  id: string;
  name: string;
  type: string;
  status: string;
  score: number;
}

export interface DocumentSummary {
  id: string;
  title: string;
  file_name: string;
  reference: string | null;
  version: string | null;
  date: string | null;
  doc_type: string;
  status: string;
  classification: string;
  diffusion: string[];
  department: string | null;
  author: string | null;
  format: string;
  ocr_used: boolean;
  quality_score: number | null;
  issues: { code: string; severity: string; message: string }[];
  chunks: number;
}

export interface DocumentDetail extends Omit<DocumentSummary, "date" | "department" | "author" | "chunks"> {
  doc_date: string | null;
  department_name: string | null;
  author_name: string | null;
  pages: number | null;
  updated_at: string | null;
  chunks: { id: string; index: number; section: string | null; page: number | null; text: string }[];
  entities: EntityRef[];
  describes: EntityRef[];
}

export interface EntityDetail {
  id: string;
  name: string;
  type: string;
  status: string;
  aliases?: string[];
  mentions?: number;
  documents?: { id: string; title: string; doc_type: string; status: string }[];
  relations?: {
    relation: string;
    outgoing: boolean;
    other_id: string;
    other_name: string;
    other_type: string;
    roles: string[];
    confidence: number | null;
    source_doc_ids: string[];
    quotes: string[];
    source: string;
  }[];
  [key: string]: unknown;
}

export interface Domain {
  id: string;
  name: string;
  declared_experts: number;
}

export interface ExpertsResponse {
  domain: { id: string; name: string };
  limits: string;
  experts: Expert[];
}

export interface Recommendation {
  doc_id: string;
  title: string;
  doc_type: string;
  status: string;
  reference: string | null;
  score: number;
  components: Record<string, number>;
  reasons: string[];
}

export interface IngestionResult {
  file_name: string;
  doc_id: string | null;
  outcome: string;
  status: string | null;
  message: string;
  chunks: number;
  relations: number;
  issues: { code: string; severity: string; message: string }[];
}

export interface IngestionRun {
  id: string;
  started_at: string;
  finished_at: string | null;
  duration_seconds: number;
  files_seen: number;
  ingested: number;
  updated: number;
  unchanged: number;
  duplicates: number;
  quarantined: number;
  rejected: number;
  errors: number;
  deleted: number;
}
