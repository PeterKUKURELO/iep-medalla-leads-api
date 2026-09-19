from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine_options: dict[str, object] = {"pool_pre_ping": True, "hide_parameters": True}
if settings.sqlalchemy_url.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}
else:
    engine_options.update(
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=settings.db_pool_recycle,
    )
    if settings.db_use_tls:
        ssl_options = {"ca": str(settings.db_ssl_ca)} if settings.db_ssl_ca else {}
        engine_options["connect_args"] = {
            "ssl": ssl_options,
            "ssl_verify_cert": True,
            "ssl_verify_identity": True,
        }

engine = create_engine(settings.sqlalchemy_url, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
