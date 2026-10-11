"""Compare deux répertoires de résultats (contrôle de reproductibilité).

Usage : python -m evaluation.compare_runs results/A results/B
Compare ligne à ligne les fichiers *_per_question.csv en ignorant les durées (latency_ms), qui
varient naturellement d'une exécution à l'autre. Code de sortie 1 en cas de différence.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

IGNORED = {"latency_ms"}
KEYS = {"retrieval_per_question.csv": ("question", "strategy"), "qa_per_question.csv": ("question", "architecture"),
        "ablations_per_question.csv": ("question", "architecture")}


def load(path: Path, key: tuple[str, ...]) -> dict:
    with path.open(encoding="utf-8") as f:
        return {tuple(r[k] for k in key): {k: v for k, v in r.items() if k not in IGNORED} for r in csv.DictReader(f)}


def main() -> int:
    a, b = Path(sys.argv[1]), Path(sys.argv[2])
    differences = 0
    for name, key in KEYS.items():
        if not (a / name).exists() or not (b / name).exists():
            continue
        left, right = load(a / name, key), load(b / name, key)
        diff = [k for k in left.keys() | right.keys() if left.get(k) != right.get(k)]
        differences += len(diff)
        print(f"{name} : {len(left)} lignes, {len(diff)} différence(s)")
        for k in sorted(diff)[:10]:
            changed = {c for c in (left.get(k) or {}) if (left.get(k) or {}).get(c) != (right.get(k) or {}).get(c)}
            print("   ", k, sorted(changed))
    return 1 if differences else 0


if __name__ == "__main__":
    sys.exit(main())
