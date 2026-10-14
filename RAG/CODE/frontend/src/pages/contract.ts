// Contrat commun des pages : chaque page reçoit l'utilisateur connecté, une fonction de
// navigation et un paramètre optionnel (identifiant d'entité, de document, question…).

import type { User } from "../types";

export type PageKey = "home" | "ask" | "explorer" | "experts" | "recommendations" | "documents";

export interface PageProps {
  user: User;
  navigate: (page: PageKey, param?: string) => void;
  param?: string;
}

export const hasRole = (user: User, role: "viewer" | "manager" | "admin") => {
  const order = { viewer: 0, manager: 1, admin: 2 } as const;
  return user.roles.some((r) => (order[r as keyof typeof order] ?? -1) >= order[role]);
};
