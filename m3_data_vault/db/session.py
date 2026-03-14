"""
SQLAlchemy session factory for M3 Data-Vault.
"""
from __future__ import annotations

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker


def get_session(engine: Engine) -> Session:
    """
    Create and return a new SQLAlchemy session bound to the given engine.

    Args:
        engine: SQLAlchemy Engine instance.

    Returns:
        A new Session instance. Caller is responsible for closing it.
    """
    factory = sessionmaker(bind=engine)
    return factory()
