"""Détection des doublons exacts et des quasi-doublons.

- Doublon exact : même empreinte SHA-256 du contenu binaire.
- Quasi-doublon : forte ressemblance textuelle, mesurée par l'indice de Jaccard entre les
  ensembles de « shingles » (séquences de k mots) des deux textes. L'indice est estimé par
  MinHash (Broder, 1997) : chaque document est résumé par une signature de 128 entiers, et la
  proportion de positions égales entre deux signatures estime leur indice de Jaccard. Cette
  signature est stockée dans le graphe : la comparaison d'un nouveau document à N documents
  existants ne nécessite pas de relire leur texte.
"""

from __future__ import annotations

import hashlib

import numpy as np

from core.text import tokenize

NUM_PERM = 128
SHINGLE_SIZE = 5
_PRIME = (1 << 61) - 1
_rng = np.random.default_rng(20251011)  # graine fixe : signatures reproductibles
_A = _rng.integers(1, _PRIME, size=NUM_PERM, dtype=np.uint64)
_B = _rng.integers(0, _PRIME, size=NUM_PERM, dtype=np.uint64)


def sha256_file(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def shingles(text: str, k: int = SHINGLE_SIZE) -> set[str]:
    tokens = tokenize(text)
    if len(tokens) < k:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[i : i + k]) for i in range(len(tokens) - k + 1)}


def _hash64(value: str) -> int:
    return int.from_bytes(hashlib.blake2b(value.encode("utf-8"), digest_size=8).digest(), "big") & ((1 << 61) - 1)


def minhash_signature(text: str) -> list[int]:
    items = shingles(text)
    if not items:
        return [0] * NUM_PERM
    hashes = np.array([_hash64(s) for s in items], dtype=np.uint64)
    # (a*x + b) mod p calculé en Python int pour éviter les débordements 64 bits.
    sig = []
    for a, b in zip(_A.tolist(), _B.tolist(), strict=True):
        sig.append(min(((a * int(h) + b) % _PRIME) for h in hashes.tolist()))
    return sig


def estimated_jaccard(sig_a: list[int], sig_b: list[int]) -> float:
    if not sig_a or not sig_b or len(sig_a) != len(sig_b):
        return 0.0
    equal = sum(1 for x, y in zip(sig_a, sig_b, strict=True) if x == y)
    return equal / len(sig_a)


def exact_jaccard(text_a: str, text_b: str) -> float:
    a, b = shingles(text_a), shingles(text_b)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)
