"""DATABASE_URL normalization for SQLAlchemy PostgreSQL driver selection."""

from __future__ import annotations

import unittest

from sqlalchemy.engine import make_url

from app.database.database_url import normalize_database_url


class TestDatabaseUrlNormalization(unittest.TestCase):
    def test_bare_postgresql_uses_psycopg2_dialect(self):
        normalized = normalize_database_url("postgresql://user:pass@db.example.com:5432/postgres")
        self.assertEqual(make_url(normalized).drivername, "postgresql+psycopg2")
        self.assertTrue(normalized.endswith("/postgres"))

    def test_postgres_scheme_alias(self):
        normalized = normalize_database_url("postgres://host/db")
        self.assertEqual(make_url(normalized).drivername, "postgresql+psycopg2")

    def test_psycopg_v3_scheme_rewritten_to_psycopg2(self):
        normalized = normalize_database_url("postgresql+psycopg://user:pass@host/db")
        self.assertEqual(make_url(normalized).drivername, "postgresql+psycopg2")

    def test_sqlite_unchanged(self):
        url = "sqlite:///./gramsakhi.db"
        self.assertEqual(normalize_database_url(url), url)

    def test_already_psycopg2_unchanged(self):
        url = "postgresql+psycopg2://user:pass@host/db"
        self.assertEqual(normalize_database_url(url), url)


if __name__ == "__main__":
    unittest.main()
