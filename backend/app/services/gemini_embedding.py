"""Gemini embedding API (google-genai)."""

from __future__ import annotations

import logging
import math
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import List

from app.core.config import settings

logger = logging.getLogger("gramsakhi.embeddings")


class GeminiEmbeddingError(Exception):
    def __init__(self, message: str, *, code: str = "unavailable", retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def get_gemini_embedding_model() -> str:
    return (settings.GEMINI_EMBEDDING_MODEL or "gemini-embedding-001").strip()


def embed_text(text: str) -> List[float]:
    return embed_texts([text])[0]


def embed_texts(texts: List[str]) -> List[List[float]]:
    if not texts:
        return []
    api_key = (settings.GEMINI_API_KEY or "").strip()
    if not api_key:
        raise GeminiEmbeddingError("GEMINI_API_KEY not configured", code="missing_api_key")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    model = get_gemini_embedding_model()
    dim = int(settings.EMBEDDING_DIMENSIONS)
    timeout_s = float(settings.GEMINI_EMBEDDING_TIMEOUT_SECONDS)
    batch_size = max(1, int(settings.GEMINI_EMBEDDING_BATCH_SIZE))
    max_attempts = max(1, int(settings.GEMINI_EMBEDDING_MAX_RETRIES) + 1)

    config = types.EmbedContentConfig(output_dimensionality=dim)
    out: List[List[float]] = []

    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        last_exc: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    fut = pool.submit(
                        client.models.embed_content,
                        model=model,
                        contents=batch,
                        config=config,
                    )
                    response = fut.result(timeout=timeout_s)
                vectors = []
                for emb in getattr(response, "embeddings", None) or []:
                    values = getattr(emb, "values", None) or []
                    vectors.append([float(x) for x in values])
                if len(vectors) != len(batch):
                    raise GeminiEmbeddingError(
                        f"Expected {len(batch)} embeddings, got {len(vectors)}",
                        code="invalid_response",
                    )
                for vec in vectors:
                    if len(vec) != dim:
                        raise GeminiEmbeddingError(
                            f"Embedding dimension {len(vec)} != configured {dim}",
                            code="dimension_mismatch",
                        )
                    for x in vec:
                        if not math.isfinite(float(x)):
                            raise GeminiEmbeddingError(
                                "Embedding contains non-finite values",
                                code="invalid_response",
                            )
                out.extend(vectors)
                break
            except GeminiEmbeddingError:
                raise
            except FuturesTimeout as exc:
                last_exc = exc
                if attempt >= max_attempts:
                    raise GeminiEmbeddingError("Gemini embedding timed out", code="timeout", retryable=True) from exc
                time.sleep(min(4.0, 0.5 * (2 ** (attempt - 1))))
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                msg = str(exc).lower()
                retryable = "429" in msg or "quota" in msg or "resource_exhausted" in msg
                if retryable and attempt < max_attempts:
                    time.sleep(min(8.0, 0.5 * (2 ** (attempt - 1))))
                    continue
                raise GeminiEmbeddingError(
                    f"Gemini embedding failed: {type(exc).__name__}",
                    code="rate_limited" if retryable else "unavailable",
                    retryable=retryable,
                ) from exc
        else:
            raise GeminiEmbeddingError(
                f"Gemini embedding failed: {type(last_exc).__name__ if last_exc else 'unknown'}",
                code="unavailable",
            )

    logger.info(
        "gemini_embed_ok model=%s count=%s dim=%s",
        model,
        len(out),
        dim,
    )
    return out
