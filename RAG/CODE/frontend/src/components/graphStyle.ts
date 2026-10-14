// Codage visuel des types d'entités : couleur (palette catégorielle validée pour la lisibilité,
// y compris en cas de daltonisme pour les paires voisines) ET forme, pour ne jamais reposer
// sur la seule couleur.

export const TYPE_STYLE: Record<string, { label: string; color: string; shape: string }> = {
  Person: { label: "Personne", color: "#2a78d6", shape: "ellipse" },
  Department: { label: "Entité organisationnelle", color: "#eb6834", shape: "round-rectangle" },
  System: { label: "Application", color: "#1baf7a", shape: "hexagon" },
  Project: { label: "Projet", color: "#eda100", shape: "diamond" },
  Procedure: { label: "Procédure", color: "#e87ba4", shape: "round-tag" },
  Domain: { label: "Domaine", color: "#008300", shape: "octagon" },
  Concept: { label: "Concept", color: "#6250d6", shape: "triangle" },
  Document: { label: "Document", color: "#8a857a", shape: "rectangle" },
};

export const RELATION_LABELS: Record<string, string> = {
  WORKS_IN: "travaille dans",
  PART_OF: "fait partie de",
  PARTICIPATES_IN: "participe à",
  RESPONSIBLE_FOR: "responsable de",
  OWNS: "propriétaire de",
  USES: "utilise",
  DEPENDS_ON: "dépend de",
  DELIVERS: "livre",
  HAS_EXPERTISE: "expertise",
  REFERENCES: "renvoie à",
  IMPACTS: "impacte",
  COVERS: "traite de",
  BELONGS_TO: "relève de",
  DESCRIBES: "décrit",
};

export const STATUS_LABELS: Record<string, string> = {
  active: "en vigueur",
  superseded: "remplacé",
  duplicate: "doublon",
  quarantined: "quarantaine",
  rejected: "rejeté",
  validated: "validée",
  candidate: "à valider",
};

export const DOC_TYPE_LABELS: Record<string, string> = {
  procedure: "Procédure",
  compte_rendu: "Compte rendu",
  charte_projet: "Charte de projet",
  note_de_service: "Note de service",
  note_organisation: "Note d'organisation",
  note_technique: "Note technique",
  guide: "Guide",
  rapport: "Rapport",
  fiche_projet: "Fiche projet",
  plan: "Plan",
  cartographie: "Cartographie",
  memo: "Mémo",
  rapport_audit: "Rapport d'audit",
  referentiel_rh: "Référentiel RH",
  document: "Document",
};

export const docTypeLabel = (t: string) => DOC_TYPE_LABELS[t] ?? t;
export const statusLabel = (s: string) => STATUS_LABELS[s] ?? s;
export const typeLabel = (t: string) => TYPE_STYLE[t]?.label ?? t;
export const relationLabel = (r: string) => RELATION_LABELS[r] ?? r;
