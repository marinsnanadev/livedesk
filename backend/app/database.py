"""
Database engine and session setup.

Uses SQLite by default (zero setup, great for a portfolio project),
but since we go through SQLAlchemy, swapping to Postgres in production
is just a DATABASE_URL change — no code changes needed.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from .config import settings

DATABASE_URL = settings.database_url

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
# pre_ping quietly replaces connections the host dropped while the app was idle.
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
