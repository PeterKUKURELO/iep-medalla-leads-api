from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import quote_plus

from pydantic import Field, PrivateAttr, SecretStr, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class SMTPProfile(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", hide_input_in_errors=True)

    mail_host: str = Field(min_length=1)
    mail_port: int = Field(default=587, gt=0, le=65535)
    mail_username: str = Field(min_length=1)
    mail_password: SecretStr
    mail_from: str = Field(min_length=1)
    mail_from_name: str = ""
    mail_use_tls: bool = True
    mail_timeout_seconds: float = Field(default=10, gt=0)


class Settings(BaseSettings):
    _smtp_profiles: dict[str, SMTPProfile] = PrivateAttr(default_factory=dict)
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / f".env.{os.getenv('APP_ENV', 'development')}",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        hide_input_in_errors=True,
    )

    app_env: Literal["development", "test", "production"] = "development"
    app_name: str = "Belsitec Leads API"
    frontend_origins: list[str] = Field(default_factory=lambda: ["http://localhost:8443"])
    allowed_hosts: list[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1", "testserver"])
    docs_enabled: bool = True

    database_url: str | None = None
    db_host: str = "localhost"
    db_port: int = 3306
    db_name: str = "medalla_leads_testing"
    db_user: str = "medalla_leads_testing"
    db_password: str = ""
    db_use_tls: bool = False
    db_production_host: str = "srv775.hstgr.io"
    db_production_name: str = "u411722909_iepmedalla"
    db_pool_size: int = Field(default=2, gt=0)
    db_max_overflow: int = Field(default=1, ge=0)
    db_pool_recycle: int = Field(default=300, gt=0)
    db_ssl_ca: Path | None = None

    mail_host: str = "sandbox.smtp.mailtrap.io"
    mail_port: int = 587
    mail_username: str = ""
    mail_password: str = ""
    mail_from: str = "no-reply@example.com"
    mail_from_name: str = "I.E.P. Medalla (PRUEBAS)"
    mail_admin_to: str = "info@example.com"
    mail_reply_to: str = "info@example.com"
    mail_use_tls: bool = True
    mail_enabled: bool = False
    mail_timeout_seconds: float = Field(default=10.0, gt=0)

    rate_limit_requests: int = Field(default=5, gt=0)
    rate_limit_window_seconds: int = Field(default=60, gt=0)
    max_body_bytes: int = Field(default=16_384, gt=0)
    brand_registry_path: Path = BASE_DIR / "app" / "config" / "brands.json"

    @model_validator(mode="after")
    def reject_dangerous_environment(self) -> "Settings":
        if self.app_env != "production":
            production_host = self.db_production_host.strip().lower()
            production_name = self.db_production_name.strip().lower()
            configured_url = (self.database_url or "").lower()
            if self.db_host.strip().lower() == production_host:
                raise ValueError("Un entorno local no puede usar el host MySQL de produccion")
            if self.db_name.strip().lower() == production_name:
                raise ValueError("Un entorno local no puede usar la base MySQL de produccion")
            if production_host and production_host in configured_url:
                raise ValueError("DATABASE_URL apunta al host de produccion")
            if production_name and production_name in configured_url:
                raise ValueError("DATABASE_URL apunta a la base de produccion")
            if self.mail_enabled:
                recipients = {self.mail_from.lower(), self.mail_admin_to.lower(), self.mail_reply_to.lower()}
                if any(not address.endswith("@example.com") for address in recipients):
                    raise ValueError("En desarrollo los correos configurados deben usar example.com")
        if self.app_env == "production" and not self.db_use_tls:
            raise ValueError("MySQL debe usar TLS en produccion")
        if self.app_env == "production":
            if not self.database_url:
                required_database = {
                    "DB_HOST": self.db_host,
                    "DB_NAME": self.db_name,
                    "DB_USER": self.db_user,
                    "DB_PASSWORD": self.db_password,
                }
                missing_database = [name for name, value in required_database.items() if not str(value).strip()]
                if missing_database:
                    raise ValueError(f"Configuracion MySQL incompleta: {', '.join(missing_database)}")
            if not self.frontend_origins or any(
                not origin.lower().startswith("https://") for origin in self.frontend_origins
            ):
                raise ValueError("Los origenes del frontend deben usar HTTPS en produccion")
            if not self.allowed_hosts or "*" in self.allowed_hosts:
                raise ValueError("ALLOWED_HOSTS debe restringirse en produccion")
        return self

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url:
            return self.database_url
        user = quote_plus(self.db_user)
        password = quote_plus(self.db_password)
        database = quote_plus(self.db_name)
        return f"mysql+pymysql://{user}:{password}@{self.db_host}:{self.db_port}/{database}?charset=utf8mb4"

    def resolve_email_profile(self, name: str) -> SMTPProfile:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
            raise ValueError("Nombre de perfil SMTP invalido")
        if name in self._smtp_profiles:
            return self._smtp_profiles[name]
        try:
            if name == "default":
                profile = SMTPProfile(
                    _env_file=None,
                    **{key: getattr(self, key) for key in SMTPProfile.model_fields},
                )
            else:
                profile = SMTPProfile(
                    _env_prefix=f"{name.upper()}_",
                    _env_file=BASE_DIR / f".env.{self.app_env}",
                    _env_file_encoding="utf-8",
                )
        except ValidationError:
            raise ValueError(f"Configuracion SMTP incompleta o invalida para perfil {name}") from None
        if not profile.mail_password.get_secret_value().strip():
            raise ValueError(f"Password SMTP vacio para perfil {name}")
        if any(not getattr(profile, field).strip() for field in ("mail_host", "mail_username", "mail_from")):
            raise ValueError(f"Configuracion SMTP incompleta para perfil {name}")
        if self.app_env == "production" and not profile.mail_use_tls:
            raise ValueError(f"SMTP debe usar TLS en produccion: {name}")
        if self.app_env != "production" and not profile.mail_from.lower().endswith("@example.com"):
            raise ValueError("En desarrollo el remitente SMTP debe usar example.com")
        self._smtp_profiles[name] = profile
        return profile


@lru_cache
def get_settings() -> Settings:
    return Settings()
