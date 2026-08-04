"""Test bootstrap: point the app at SQLite + local storage, force eager Celery."""

import os
from pathlib import Path

Path("./var").mkdir(exist_ok=True)

os.environ.setdefault("IIQ_DATABASE_URL", "sqlite:///./var/test_invoiceiq.db")
os.environ.setdefault("IIQ_STORAGE_BACKEND", "local")
os.environ.setdefault("IIQ_STORAGE_ROOT", "./var/test_storage")
os.environ.setdefault("IIQ_SECRET_KEY", "test-secret-key-that-is-at-least-32-bytes-long")

import pytest  # noqa: E402
from invoiceiq import models  # noqa: E402, F401  (register models on Base.metadata)
from invoiceiq.db import engine  # noqa: E402
from invoiceiq.models import Base  # noqa: E402
from invoiceiq.workers.app import celery_app  # noqa: E402

celery_app.conf.update(task_always_eager=True, task_eager_propagates=True)


@pytest.fixture(scope="session", autouse=True)
def _db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    engine.dispose()


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    from invoiceiq.main import app

    with TestClient(app) as c:
        yield c
