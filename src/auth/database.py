import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from src.auth.models import Base

def get_database_url() -> str:
    """
    Resolves the active database URL.
    Checks AUTH_DATABASE_URL, DATABASE_URL, and defaults to SQLite for local execution.
    """
    env_url = os.getenv("AUTH_DATABASE_URL") or os.getenv("DATABASE_URL")
    if env_url:
        # Standardize postgres:// to postgresql:// for SQLAlchemy compatibility
        if env_url.startswith("postgres://"):
            return env_url.replace("postgres://", "postgresql://", 1)
        return env_url

    # Fallback to local SQLite DB in project data directory
    data_dir = os.getenv("SPARKRAIL_DATA_DIR", os.path.join(os.getcwd(), "data"))
    os.makedirs(data_dir, exist_ok=True)
    db_path = os.path.join(data_dir, "sparkrail_auth.db")
    return f"sqlite:///{db_path}"


DATABASE_URL = get_database_url()

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for yielding database session with automatic cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(target_engine=None) -> None:
    """
    Non-destructive schema initialization: creates tables if they do not already exist.
    """
    active_engine = target_engine or engine
    Base.metadata.create_all(bind=active_engine)
