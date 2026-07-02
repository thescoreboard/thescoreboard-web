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

engine = create_engine(
    db_url,
    pool_size=20,          # was 10 — background WS push tasks consume their own connections
    max_overflow=30,       # was 20 — burst capacity for concurrent live scoring
    pool_recycle=600,
    pool_pre_ping=True,
    pool_timeout=15,       # was 30 — fail fast rather than queue indefinitely
    connect_args={
        "prepare_threshold": None,  # disable prepared statements for pgbouncer
    },
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