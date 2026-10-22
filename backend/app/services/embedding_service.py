"""Embedding provider router (Ollama local | Gemini cloud)."""

from __future__ import annotations

from typing import List

from app.core.config import settings


def embedding_provider() -> str:
    return (settings.EMBEDDING_PROVIDER or "ollama").strip().lower()


def embed_query(text: str) -> List[float]:
    from app.services import rag as rag_service

    return rag_service.get_embeddings(text)


def embed_documents(texts: List[str]) -> List[List[float]]:
    from app.services import rag as rag_service

    return rag_service.get_embeddings_batch(texts)
