from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    brand_key: Mapped[str] = mapped_column(String(50), nullable=False, default="iep-medalla", server_default="iep-medalla", index=True)
    form_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_key: Mapped[str | None] = mapped_column(String(100))
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    phone_country: Mapped[str | None] = mapped_column(String(2))
    email: Mapped[str] = mapped_column(String(254), nullable=False, index=True)
    organization_name: Mapped[str | None] = mapped_column(String(200))
    job_title: Mapped[str | None] = mapped_column(String(120))
    education_level: Mapped[str | None] = mapped_column(String(50))
    grade: Mapped[str | None] = mapped_column(String(50))
    contact_reason: Mapped[str | None] = mapped_column(String(150))
    message: Mapped[str | None] = mapped_column(Text)
    form_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    privacy_accepted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    privacy_accepted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    source_url: Mapped[str | None] = mapped_column(String(500))
    utm_source: Mapped[str | None] = mapped_column(String(100))
    utm_medium: Mapped[str | None] = mapped_column(String(100))
    utm_campaign: Mapped[str | None] = mapped_column(String(150))
    utm_content: Mapped[str | None] = mapped_column(String(150))
    utm_term: Mapped[str | None] = mapped_column(String(150))
    device_type: Mapped[str | None] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="new", server_default="new")
    classification: Mapped[str | None] = mapped_column(String(30))
    assigned_to: Mapped[str | None] = mapped_column(String(120))
    next_follow_up_at: Mapped[datetime | None] = mapped_column(DateTime)
    admin_email_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    admin_email_sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    user_email_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    user_email_sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    email_error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
