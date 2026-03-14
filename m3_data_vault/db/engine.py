"""
Database engine setup for M3 Data-Vault.

Supports SQLite (development) and PostgreSQL (production)
via SQLAlchemy's URL-based engine creation.
"""
from __future__ import annotations

from sqlalchemy import create_engine as sa_create_engine, Engine

from m3_data_vault.db.tables import Base


def create_engine_and_tables(url: str = "sqlite:///:memory:") -> Engine:
    """
    Create a SQLAlchemy engine and ensure all tables exist.

    Args:
        url: Database connection URL.
            - "sqlite:///:memory:" for in-memory testing
            - "sqlite:///path/to/db.sqlite" for file-based SQLite
            - "postgresql://user:pass@host/dbname" for production

    Returns:
        Configured SQLAlchemy Engine with all tables created.
    """
    engine = sa_create_engine(url, echo=False)
    Base.metadata.create_all(engine)
    return engine
