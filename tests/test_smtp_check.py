import smtplib

from app.check_smtp import main, verify_smtp_profile
from app.config import Settings, get_settings


def configure_miedu(monkeypatch, password="hostinger-secret"):
    values = {
        "HOST": "smtp.titan.email",
        "PORT": "587",
        "USERNAME": "contacto-miedu@example.com",
        "PASSWORD": password,
        "FROM": "contacto-miedu@example.com",
        "FROM_NAME": "miedu.pe",
        "USE_TLS": "true",
        "TIMEOUT_SECONDS": "10",
    }
    for key, value in values.items():
        monkeypatch.setenv(f"MIEDU_MAIL_{key}", value)


def test_verify_smtp_profile_authenticates_without_sending(monkeypatch):
    configure_miedu(monkeypatch)
    calls = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls.update(host=host, port=port, timeout=timeout)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            calls["exited"] = True

        def ehlo(self):
            calls["ehlo"] = calls.get("ehlo", 0) + 1

        def starttls(self, context):
            calls["tls_context"] = context

        def login(self, username, password):
            calls["login"] = (username, password)

        def close(self):
            calls["closed"] = True

        def send_message(self, message):
            raise AssertionError("La validacion no debe enviar correos")

    monkeypatch.setattr("app.services.smtp.smtplib.SMTP", FakeSMTP)
    settings = Settings(app_env="test", database_url="sqlite://")
    verify_smtp_profile(settings, "miedu")

    assert calls["host"] == "smtp.titan.email"
    assert calls["port"] == 587
    assert calls["timeout"] == 10
    assert calls["ehlo"] == 2
    assert calls["tls_context"].check_hostname is True
    assert calls["login"] == ("contacto-miedu@example.com", "hostinger-secret")
    assert calls["exited"] is True


def test_check_command_does_not_disclose_password(monkeypatch, capsys):
    configure_miedu(monkeypatch, password="never-print-this")

    class AuthenticationFailure:
        def __init__(self, profile):
            pass

        def verify_connection(self):
            raise smtplib.SMTPAuthenticationError(535, b"never-print-this")

    get_settings.cache_clear()
    monkeypatch.setattr("app.check_smtp.SMTPTransport", AuthenticationFailure)
    try:
        assert main(["--profile", "miedu"]) == 1
    finally:
        get_settings.cache_clear()

    captured = capsys.readouterr()
    assert "SMTPAuthenticationError" in captured.err
    assert "never-print-this" not in captured.err
