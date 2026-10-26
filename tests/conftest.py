import os
import tempfile

os.environ.setdefault("SMARTCHAIN_LOG_DIR", tempfile.mkdtemp(prefix="smartchain-logs-"))

import pytest
from fastapi.testclient import TestClient

from app.api.db import get_session
from app.api.main import create_app


class FakeSession:
    """Veritabanı olmadan testler için yer tutucu; sorgular repository'de taklit edilir."""


@pytest.fixture
def app():
    application = create_app()
    application.dependency_overrides[get_session] = lambda: FakeSession()
    return application


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)
