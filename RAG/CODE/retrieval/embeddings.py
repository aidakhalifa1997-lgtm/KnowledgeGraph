"""Encodeurs de texte en vecteurs (embeddings), utilisables hors-ligne.

Contrainte de l'environnement de développement : aucun modèle ne peut être téléchargé depuis
HuggingFace. Deux encodeurs installables depuis PyPI sont donc proposés et comparés
expérimentalement :

- `spacy` : moyenne des vecteurs de mots français (300 dimensions) du modèle
  `fr_core_news_md`, mots outils exclus. Méthode classique, simple et explicable, mais qui
  ignore l'ordre des mots et capte mal les nuances de phrase.
- `wordllama` : encodeur statique (256 dimensions) distillé à partir des embeddings de jetons
  d'un LLM, entraîné surtout sur de l'anglais.

Ces encodeurs sont moins performants que les modèles neuronaux de phrases (Sentence-BERT,
modèles multilingues récents). Les conclusions expérimentales en dépendent : voir
DETAILS/TESTS_ET_EVALUATION.txt.

Tous les vecteurs sont normalisés (norme 1) : le produit scalaire égale alors la similarité
cosinus.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Protocol

import numpy as np

from core.text import STOPWORDS, fold_accents


class Embedder(Protocol):
    name: str
    dim: int

    def embed(self, texts: list[str]) -> np.ndarray: ...


def _normalize_rows(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (matrix / norms).astype(np.float32)


class SpacyEmbedder:
    name = "spacy-fr_core_news_md"
    dim = 300

    def __init__(self) -> None:
        import spacy

        # Seuls le tokeniseur et la table de vecteurs sont nécessaires : chargement allégé.
        self._nlp = spacy.load("fr_core_news_md", exclude=["tok2vec", "morphologizer", "parser",
                                                            "attribute_ruler", "lemmatizer", "ner"])

    def embed(self, texts: list[str]) -> np.ndarray:
        rows = []
        for doc in self._nlp.pipe(texts, batch_size=64):
            vectors = [tok.vector for tok in doc
                       if tok.has_vector and not tok.is_punct and not tok.is_space
                       and fold_accents(tok.lower_) not in STOPWORDS]
            rows.append(np.mean(vectors, axis=0) if vectors else np.zeros(self.dim, dtype=np.float32))
        return _normalize_rows(np.vstack(rows)) if rows else np.zeros((0, self.dim), dtype=np.float32)


class WordLlamaEmbedder:
    name = "wordllama-l2_supercat-256"
    dim = 256

    def __init__(self) -> None:
        import wordllama
        from wordllama import WordLlama

        # Les poids sont fournis dans le paquet PyPI : aucun téléchargement n'est effectué.
        package_dir = Path(wordllama.__file__).parent
        self._model = WordLlama.load(cache_dir=package_dir, disable_download=True)

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return _normalize_rows(np.asarray(self._model.embed(texts, norm=True), dtype=np.float32))


@lru_cache(maxsize=2)
def get_embedder(provider: str = "spacy") -> Embedder:
    if provider == "wordllama":
        return WordLlamaEmbedder()
    return SpacyEmbedder()


def cosine_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return a @ b.T
