import os

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///./medalla_test.sqlite3"
os.environ["MAIL_ENABLED"] = "false"
os.environ["RATE_LIMIT_REQUESTS"] = "5"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Lead
from app.rate_limit import InMemoryRateLimiter


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        db.query(Lead).delete()
        db.commit()
    app.state.rate_limiter = InMemoryRateLimiter(5, 60)
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
