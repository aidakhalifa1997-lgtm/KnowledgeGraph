"""Schémas de validation des entrées de l'API (Pydantic)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    password: str = Field(min_length=1, max_length=256)


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    strategy: Literal["auto", "vector", "lexical", "hybrid", "graph", "hybrid_graph"] = "auto"

    @field_validator("question")
    @classmethod
    def _clean(cls, value: str) -> str:
        value = " ".join(value.split())
        if not any(ch.isalpha() for ch in value):
            raise ValueError("la question doit contenir du texte")
        return value


class QueryRecommendationRequest(BaseModel):
    text: str = Field(min_length=3, max_length=500)
    limit: int = Field(default=5, ge=1, le=20)
