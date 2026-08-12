from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    form_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, index=True)
    education_level: Mapped[str | None] = mapped_column(String(50))
    grade: Mapped[str | None] = mapped_column(String(50))
    contact_reason: Mapped[str | None] = mapped_column(String(150))
    message: Mapped[str | None] = mapped_column(Text)
    privacy_accepted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    privacy_accepted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    source_url: Mapped[str | None] = mapped_column(String(500))
    utm_source: Mapped[str | None] = mapped_column(String(100))
    utm_medium: Mapped[str | None] = mapped_column(String(100))
    utm_campaign: Mapped[str | None] = mapped_column(String(150))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="new", server_default="new")
    admin_email_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    admin_email_sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    user_email_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    user_email_sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    email_error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
