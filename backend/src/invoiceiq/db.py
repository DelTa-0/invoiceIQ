"""Database engine, session factory, and tenancy-scoped sessions.

Tenancy model: single shared schema, org isolation enforced by Postgres
Row-Level Security. Every session sets `app.org_id` (transaction-local GUC)
before running queries; RLS policies filter rows by that value.

For portability (unit tests run on SQLite in-memory), the RLS GUC is only
emitted when the dialect is PostgreSQL.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .settings import get_settings

_settings = get_settings()

engine = create_engine(_settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope(org_id: str | None = None, *, commit: bool = True) -> Iterator[Session]:
    """Yield a transaction-scoped session, optionally bound to an org for RLS.

    The `app.org_id` GUC is set with `SET LOCAL`, which only lives for the
    duration of the transaction — safe against cross-request leakage.
    """
    session = SessionLocal()
    try:
        if org_id is not None and session.get_bind().dialect.name == "postgresql":
            session.execute(text("SELECT set_config('app.org_id', :oid, true)"), {"oid": str(org_id)})
        yield session
        if commit:
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
