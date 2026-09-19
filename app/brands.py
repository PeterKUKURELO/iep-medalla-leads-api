from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

if TYPE_CHECKING:
    from app.config import Settings


class BrandConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    display_name: str = Field(min_length=1, max_length=100)
    enabled: bool
    notifications_enabled: bool = True
    allowed_forms: set[str] = Field(min_length=1)
    allowed_origins: set[str] = Field(min_length=1)
    email_profile: str = Field(min_length=1, max_length=50)
    admin_recipients: list[EmailStr] = Field(min_length=1)
    reply_to: EmailStr
    templates: dict[str, str]
    default_assignee: str | None = None

    @model_validator(mode="after")
    def validate_templates(self) -> "BrandConfig":
        if set(self.templates) != {"admin", "user"}:
            raise ValueError("templates debe declarar admin y user")
        if any("/" in path or "\\" in path or not path.endswith(".html") for path in self.templates.values()):
            raise ValueError("ruta de template no permitida")
        for origin in self.allowed_origins:
            parsed = urlsplit(origin)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
                raise ValueError("origen no permitido en configuracion")
        if not re.fullmatch(r"[a-z][a-z0-9_]*", self.email_profile):
            raise ValueError("perfil SMTP invalido")
        return self


class BrandRegistryFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    brands: list[BrandConfig] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_keys(self) -> "BrandRegistryFile":
        keys = [brand.key for brand in self.brands]
        if len(keys) != len(set(keys)):
            raise ValueError("las claves de marca deben ser unicas")
        return self


class BrandRegistry:
    def __init__(self, config: BrandRegistryFile) -> None:
        self._brands = {brand.key: brand for brand in config.brands}

    @classmethod
    def from_path(cls, path: Path) -> "BrandRegistry":
        data = json.loads(path.read_text(encoding="utf-8"))
        config = BrandRegistryFile.model_validate(data)
        template_root = Path(__file__).resolve().parent / "templates" / "email"
        missing = [name for brand in config.brands for name in brand.templates.values() if not (template_root / name).is_file()]
        if missing:
            raise ValueError(f"templates inexistentes: {', '.join(sorted(set(missing)))}")
        return cls(config)

    def get(self, key: str) -> BrandConfig | None:
        return self._brands.get(key)

    def validate_email_profiles(self, settings: Settings) -> None:
        if settings.mail_enabled:
            for brand in self._brands.values():
                if brand.enabled and brand.notifications_enabled:
                    settings.resolve_email_profile(brand.email_profile)
                    if brand.key == "iep-medalla" and brand.email_profile == "default":
                        if not settings.mail_admin_to.strip() or not settings.mail_reply_to.strip():
                            raise ValueError("MAIL_ADMIN_TO y MAIL_REPLY_TO son obligatorios para Medalla default")

    def require(self, key: str) -> BrandConfig:
        brand = self.get(key)
        if brand is None:
            raise UnknownBrandError(key)
        if not brand.enabled:
            raise DisabledBrandError(key)
        return brand


class UnknownBrandError(ValueError):
    pass


class DisabledBrandError(ValueError):
    pass


@lru_cache
def get_brand_registry() -> BrandRegistry:
    from app.config import get_settings

    settings = get_settings()
    registry = BrandRegistry.from_path(settings.brand_registry_path)
    registry.validate_email_profiles(settings)
    return registry
