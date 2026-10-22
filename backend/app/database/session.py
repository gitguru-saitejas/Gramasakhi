import socket
from urllib.parse import urlparse

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings
from app.database.database_url import normalize_database_url

DATABASE_URL = normalize_database_url(settings.DATABASE_URL)

is_sqlite = DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}

# Prefer IPv4 for Postgres hosts. Direct db.*.supabase.co is often IPv6-only;
# forcing an IPv6 hostaddr on networks without IPv6 yields "Network is unreachable".
if not is_sqlite:
    host = urlparse(DATABASE_URL).hostname or ""
    if host.endswith(".supabase.co") and host.startswith("db."):
        has_v4 = False
        try:
            socket.getaddrinfo(host, 5432, socket.AF_INET, socket.SOCK_STREAM)
            has_v4 = True
        except OSError:
            has_v4 = False
        if not has_v4:
            print(
                "WARNING: DATABASE_URL uses direct Supabase host (IPv6-only). "
                "This machine cannot reach it over IPv6. "
                "In Supabase Dashboard > Project Settings > Database, copy the "
                "Session pooler URI (aws-0-<region>.pooler.supabase.com) into "
                "DATABASE_URL, or enable the IPv4 add-on / unpause the project.",
                flush=True,
            )

# Pool pre ping checks connection liveliness before executing SQL commands
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=not is_sqlite,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
