"""
Database engine and session factory.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

# Ensure we use psycopg3 dialect
db_url = settings.DATABASE_URL
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
elif db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)

if db_url.startswith("postgresql+psycopg://"):
    engine = create_engine(
        db_url,
        # Sized for Supabase's connection pooler (server-side pool defaults to
        # ~15 on small plans): exceeding it just queues at the pooler. 10+10
        # comfortably covers 100-150 concurrent users because reads are served
        # from the in-memory page caches.
        pool_size=10,
        max_overflow=10,
        pool_recycle=600,
        pool_pre_ping=True,
        pool_timeout=15,       # was 30 — fail fast rather than queue indefinitely
        connect_args={
            "prepare_threshold": None,  # disable prepared statements for pgbouncer
        },
    )
else:
    # Non-Postgres URL (tests / local dev without a DB) — the pool and psycopg
    # options above are Postgres-specific and crash other dialects at import.
    engine = create_engine(db_url or "sqlite://")

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