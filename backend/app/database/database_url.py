"""Normalize DATABASE_URL for SQLAlchemy driver selection (no secrets logged)."""

from __future__ import annotations


def normalize_database_url(url: str) -> str:
    """
    SQLAlchemy 2.x maps bare postgresql:// to the psycopg (v3) driver.
    This project installs psycopg2-binary — force the psycopg2 dialect.
    """
    raw = (url or "").strip()
    if not raw:
        return raw

    if raw.startswith("postgresql+psycopg2://") or raw.startswith("postgres+psycopg2://"):
        return raw

    if raw.startswith("postgresql+psycopg://"):
        return "postgresql+psycopg2://" + raw[len("postgresql+psycopg://") :]
    if raw.startswith("postgres+psycopg://"):
        return "postgresql+psycopg2://" + raw[len("postgres+psycopg://") :]

    if raw.startswith("postgres://"):
        return "postgresql+psycopg2://" + raw[len("postgres://") :]
    if raw.startswith("postgresql://"):
        return "postgresql+psycopg2://" + raw[len("postgresql://") :]

    return raw
