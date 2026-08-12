from __future__ import annotations

import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import Settings
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
        subject = f"Nuevo lead de {lead.form_type} #{lead.id}"
        context = {"lead": lead}
        text = self._admin_text(lead)
        html = self.templates.get_template("new_lead.html").render(**context)
        self._send(self.settings.mail_admin_to, subject, text, html)

    def send_user_confirmation(self, lead: Lead) -> None:
        subject = "Recibimos tus datos - I.E.P. Medalla"
        text = (
            f"Hola {lead.full_name},\n\n"
            "Recibimos tus datos correctamente. Nuestro equipo se pondra en contacto contigo.\n\n"
            "I.E.P. Medalla"
        )
        html = self.templates.get_template("lead_confirmation.html").render(lead=lead)
        self._send(lead.email, subject, text, html)

    def _send(self, recipient: str, subject: str, text: str, html: str) -> None:
        if not self.settings.mail_enabled:
            raise RuntimeError("el envio SMTP esta desactivado")
        if self.settings.app_env != "production" and not recipient.lower().endswith("@example.com"):
            raise RuntimeError("destinatario bloqueado fuera de produccion")
        if not self.settings.mail_host or not self.settings.mail_username or not self.settings.mail_password:
            raise RuntimeError("configuracion SMTP incompleta")

        message = EmailMessage()
        message["From"] = formataddr((self.settings.mail_from_name, self.settings.mail_from))
        message["To"] = recipient
        message["Reply-To"] = self.settings.mail_reply_to
        message["Subject"] = subject
        message.set_content(text)
        message.add_alternative(html, subtype="html")

        with smtplib.SMTP(
            self.settings.mail_host,
            self.settings.mail_port,
            timeout=self.settings.mail_timeout_seconds,
        ) as smtp:
            smtp.ehlo()
            if self.settings.mail_use_tls:
                smtp.starttls()
                smtp.ehlo()
            smtp.login(self.settings.mail_username, self.settings.mail_password)
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
