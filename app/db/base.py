"""Declarative base for all ORM models.

Separated from models.py so Alembic can import Base.metadata
without triggering circular imports from engine creation.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass
