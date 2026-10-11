"""Création ou mise à jour d'un utilisateur dans un fichier d'utilisateurs YAML.

Exemple :
    python -m scripts.create_user --file config/users.local.yaml --username marie \
        --name "Marie Dupont" --roles manager --groups ALL DCONF
Le mot de passe est demandé de façon interactive (jamais passé en argument ni journalisé).
"""

from __future__ import annotations

import argparse
import getpass
from pathlib import Path

import yaml

from backend.security import hash_password


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--roles", nargs="+", default=["viewer"], choices=["viewer", "manager", "admin"])
    parser.add_argument("--groups", nargs="+", default=["ALL"])
    args = parser.parse_args()
    password = getpass.getpass("Mot de passe : ")
    if len(password) < 12:
        raise SystemExit("Le mot de passe doit contenir au moins 12 caractères.")
    path = Path(args.file)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {"users": []}
    data["users"] = [u for u in data.get("users", []) if u["username"] != args.username]
    data["users"].append({"username": args.username, "display_name": args.name, "roles": args.roles,
                          "groups": [g.upper() for g in args.groups], "password_hash": hash_password(password)})
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"Utilisateur {args.username} enregistré dans {path}")


if __name__ == "__main__":
    main()
