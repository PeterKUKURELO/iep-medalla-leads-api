from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import Settings
from app.brands import get_brand_registry
from app.models.lead import Lead

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "email"


class EmailService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.templates = Environment(
            loader=FileSystemLoader(TEMPLATE_DIR),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def send_admin_notification(self, lead: Lead) -> None:
        brand = get_brand_registry().require(lead.brand_key)
        if not brand.notifications_enabled:
            return
        subject = f"Nuevo lead {brand.display_name}: {lead.form_type} #{lead.id}"
        context = {"lead": lead, "brand": brand}
        text = self._admin_text(lead)
        html = self.templates.get_template(brand.templates["admin"]).render(**context)
        is_legacy_medalla = lead.brand_key == "iep-medalla" and brand.email_profile == "default"
        recipients = [self.settings.mail_admin_to] if is_legacy_medalla else [str(value) for value in brand.admin_recipients]
        reply_to = self.settings.mail_reply_to if is_legacy_medalla else str(brand.reply_to)
        self._send(recipients, subject, text, html, reply_to=reply_to, email_profile=brand.email_profile)

    def send_user_confirmation(self, lead: Lead) -> None:
        brand = get_brand_registry().require(lead.brand_key)
        if not brand.notifications_enabled:
            return
        subject = f"Recibimos tus datos - {brand.display_name}"
        text = (
            f"Hola {lead.full_name},\n\n"
            "Recibimos tus datos correctamente. Nuestro equipo se pondra en contacto contigo.\n\n"
            f"{brand.display_name}"
        )
        html = self.templates.get_template(brand.templates["user"]).render(lead=lead, brand=brand)
        reply_to = self.settings.mail_reply_to if lead.brand_key == "iep-medalla" and brand.email_profile == "default" else str(brand.reply_to)
        self._send(lead.email, subject, text, html, reply_to=reply_to, email_profile=brand.email_profile)

    def _send(self, recipient: str | list[str], subject: str, text: str, html: str, reply_to: str | None = None, email_profile: str = "default") -> None:
        if not self.settings.mail_enabled:
            raise RuntimeError("el envio SMTP esta desactivado")
        recipients = [recipient] if isinstance(recipient, str) else recipient
        if self.settings.app_env != "production" and any(not value.lower().endswith("@example.com") for value in recipients):
            raise RuntimeError("destinatario bloqueado fuera de produccion")
        profile = self.settings.resolve_email_profile(email_profile)

        message = EmailMessage()
        message["From"] = formataddr((profile.mail_from_name, profile.mail_from))
        message["To"] = ", ".join(recipients)
        message["Reply-To"] = reply_to or self.settings.mail_reply_to
        message["Subject"] = subject
        message.set_content(text)
        message.add_alternative(html, subtype="html")

        with smtplib.SMTP(
            profile.mail_host,
            profile.mail_port,
            timeout=profile.mail_timeout_seconds,
        ) as smtp:
            smtp.ehlo()
            if profile.mail_use_tls:
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
            smtp.login(profile.mail_username, profile.mail_password.get_secret_value())
            smtp.send_message(message)

    @staticmethod
    def _admin_text(lead: Lead) -> str:
        values = [
            f"Lead: #{lead.id}",
            f"Formulario: {lead.form_type}",
            f"Nombre: {lead.full_name}",
            f"Telefono: {lead.phone}",
            f"Correo: {lead.email}",
        ]
        if lead.education_level:
            values.extend([f"Nivel: {lead.education_level}", f"Grado: {lead.grade}"])
        if lead.contact_reason:
            values.extend([f"Motivo: {lead.contact_reason}", f"Mensaje: {lead.message}"])
        return "\n".join(values)
