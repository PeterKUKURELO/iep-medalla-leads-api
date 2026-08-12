from app.config import Settings
from app.services.email import EmailService


def test_development_blocks_real_recipient():
    settings = Settings(
        app_env="development",
        database_url="sqlite://",
        mail_enabled=True,
        mail_username="sandbox-user",
        mail_password="sandbox-password",
    )
    service = EmailService(settings)
    try:
        service._send("family@gmail.com", "test", "text", "<p>text</p>")
    except RuntimeError as exc:
        assert "bloqueado" in str(exc)
    else:
        raise AssertionError("SMTP delivery should be disabled")
