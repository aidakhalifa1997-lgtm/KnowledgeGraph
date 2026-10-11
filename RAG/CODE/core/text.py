"""Outils de normalisation de texte partagés par l'ingestion, l'extraction et la recherche."""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "`": "'", "´": "'", "ʼ": "'"})
_QUOTES = str.maketrans({"«": '"', "»": '"', "“": '"', "”": '"'})
_DASHES = str.maketrans({"–": "-", "—": "-", "‐": "-", "‑": "-"})
_LIGATURES = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl", "œ": "oe", "Œ": "OE"}

# Mots outils et mots interrogatifs ignorés pour le calcul de couverture et le score lexical.
STOPWORDS = set(
    """
    a à au aux avec ce ces cet cette dans de des du elle elles en et est été être eu il ils
    je la le les leur leurs lui ma mais me même mes moi mon ne nos notre nous on ou où par pas
    pour qu que qui sa se ses son sont sur ta te tes toi ton tu un une vos votre vous y d l s n c
    j m t quel quelle quels quelles quoi comment combien pourquoi quand est-ce estce ceux celle
    celui celles cela ça ont avait avaient sera seront doit doivent peut peuvent fait faire
    lors afin ainsi aussi tout tous toute toutes chaque entre vers chez sans sous selon plus
    moins très bien encore déjà toujours dont si non oui être avoir a-t-il a-t-elle
    t-il t-elle t-on y-a-t-il existe existent est-elle est-il sont-ils sont-elles a-t-elle a-t-on
    peut-on doit-on faut-il quelle quels
    """.split()
)


def fold_accents(text: str) -> str:
    """Supprime les accents (é -> e) en conservant la casse."""
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def normalize_unicode(text: str) -> str:
    """Normalisation sans perte de sens : NFC, apostrophes, guillemets, tirets, ligatures."""
    text = unicodedata.normalize("NFC", text)
    for lig, repl in _LIGATURES.items():
        text = text.replace(lig, repl)
    return text.translate(_APOSTROPHES).translate(_QUOTES).translate(_DASHES)


def normalize_key(text: str) -> str:
    """Clé de comparaison : minuscules, sans accents, ponctuation réduite, espaces simples."""
    text = fold_accents(normalize_unicode(text)).lower()
    text = re.sub(r"[^\w%'-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_with_map(text: str) -> tuple[str, list[int]]:
    """Normalise caractère par caractère (minuscules, sans accents) et renvoie la table de
    correspondance position normalisée -> position originale. Indispensable pour retrouver
    l'empan exact d'une mention détectée sur le texte normalisé."""
    out_chars: list[str] = []
    mapping: list[int] = []
    for idx, ch in enumerate(text):
        ch = ch.translate(_APOSTROPHES).translate(_DASHES)
        if ch in _LIGATURES:
            ch = _LIGATURES[ch]
        folded = fold_accents(ch).lower() or " "
        for f in folded:
            out_chars.append(f)
            mapping.append(idx)
    return "".join(out_chars), mapping


_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9'%-]*")


def tokenize(text: str) -> list[str]:
    """Tokenisation simple sur texte normalisé (sans accents, minuscules)."""
    norm = normalize_key(text).replace("'", " ")
    return _TOKEN_RE.findall(norm)


_INTERROGATIVE_SUFFIX = re.compile(r"-(t-)?(il|elle|ils|elles|on)$")
_ACCENTED_TOKEN = re.compile(r"[0-9a-zà-öø-ÿœ][0-9a-zà-öø-ÿœ%-]*")


def content_terms(text: str) -> list[str]:
    """Termes porteurs de sens, en minuscules AVEC accents (nécessaires au stemmer), sans mots
    outils. Les formes interrogatives « compte-t-elle », « peut-on » sont ramenées au verbe."""
    lowered = normalize_unicode(text).lower().replace("'", " ")
    terms = []
    for token in _ACCENTED_TOKEN.findall(lowered):
        token = _INTERROGATIVE_SUFFIX.sub("", token).strip("-")
        if len(token) >= 2 and fold_accents(token) not in STOPWORDS:
            terms.append(token)
    return terms


@lru_cache(maxsize=1)
def _snowball():
    import snowballstemmer

    return snowballstemmer.stemmer("french")


@lru_cache(maxsize=50000)
def light_stem(token: str) -> str:
    """Racine d'un mot français : algorithme Snowball (Porter adapté au français), sans accents.
    Utilisée pour comparer les mots indépendamment de leurs flexions (refus / refusée)."""
    return fold_accents(_snowball().stemWord(token.lower()))


_SENT_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-ZÉÈÀÂÎÔÛÇ0-9«\"(])")
_ABBREVIATION_END = re.compile(r"(?:^|\s)(M|Mme|Mlle|Mmes|MM|Dr|Pr|Me|cf|art|p|n°|St|etc|ex|env)\.$", re.IGNORECASE)


def split_sentences(text: str) -> list[str]:
    """Découpage en phrases : fin de phrase (. ! ?) suivie d'une majuscule, ou retour à la ligne.
    Les abréviations courantes (« M. », « Mme », « cf. ») ne terminent pas une phrase."""
    sentences: list[str] = []
    for line in text.split("\n"):
        pieces = _SENT_BOUNDARY.split(line)
        merged: list[str] = []
        for piece in pieces:
            if merged and _ABBREVIATION_END.search(merged[-1]):
                merged[-1] = f"{merged[-1]} {piece}"
            else:
                merged.append(piece)
        for sent in merged:
            sent = sent.strip(" \t-•*")
            if len(sent) >= 3:
                sentences.append(sent)
    return sentences


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalize_key(text)).strip("-")
