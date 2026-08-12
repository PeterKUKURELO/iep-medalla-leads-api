import pytest
from pydantic import ValidationError

from app.config import Settings


def test_development_cannot_connect_to_production_database():
    with pytest.raises(ValidationError):
        Settings(
            app_env="development",
            database_url=None,
            db_host="195.179.237.102",
            db_name="safe_testing",
        )


def test_production_requires_database_tls():
    with pytest.raises(ValidationError):
        Settings(app_env="production", db_use_tls=False)


def test_production_requires_https_frontend():
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            database_url=None,
            db_host="database.example.net",
            db_name="medalla",
            db_user="medalla",
            db_password="secret",
            db_use_tls=True,
            frontend_origins=["http://iepmedalla.com"],
            allowed_hosts=["api.iepmedalla.com"],
        )


def test_production_rejects_wildcard_host():
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            database_url=None,
            db_host="database.example.net",
            db_name="medalla",
            db_user="medalla",
            db_password="secret",
            db_use_tls=True,
            frontend_origins=["https://iepmedalla.com"],
            allowed_hosts=["*"],
        )
