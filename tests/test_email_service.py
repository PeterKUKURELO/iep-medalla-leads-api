from app.config import Settings
from app.services.email import EmailService
import pytest
from app.brands import BrandConfig, BrandRegistry, BrandRegistryFile
from app.models.lead import Lead


def configure_profile(monkeypatch, name):
    prefix = name.upper() + "_MAIL_"
    for key, value in {
        "HOST": f"smtp.{name}.example.com",
        "USERNAME": f"user-{name}",
        "PASSWORD": f"secret-{name}",
        "FROM": f"{name}@example.com",
        "FROM_NAME": name,
    }.items():
        monkeypatch.setenv(prefix + key, value)


@pytest.mark.parametrize("name,brand_key", [
    ("medalla", "iep-medalla"), ("belsitec", "belsitec"), ("miedu", "miedu-pe"),
])
@pytest.mark.parametrize("kind", ["admin", "user"])
def test_brand_selects_own_smtp_credentials(monkeypatch, name, brand_key, kind):
    for profile in ("medalla", "belsitec", "miedu"):
        configure_profile(monkeypatch, profile)
    calls = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls["host"] = host
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def ehlo(self):
            pass
        def starttls(self, context):
            assert context.check_hostname
        def login(self, username, password):
            calls["login"] = (username, password)
        def send_message(self, message):
            calls["message"] = message

    brand = BrandConfig(
        key=brand_key, display_name=name, enabled=True, allowed_forms={"contact"},
        allowed_origins={"https://example.com"}, email_profile=name,
        admin_recipients=[f"admin-{name}@example.com"], reply_to=f"reply-{name}@example.com",
        templates={"admin": "new_lead.html", "user": "lead_confirmation.html"},
    )
    registry = BrandRegistry(BrandRegistryFile(brands=[brand]))
    monkeypatch.setattr("app.services.email.get_brand_registry", lambda: registry)
    monkeypatch.setattr("app.services.email.smtplib.SMTP", FakeSMTP)
    settings = Settings(app_env="test", database_url="sqlite://", mail_enabled=True,
                        mail_username="legacy", mail_password="legacy-secret")
    lead = Lead(id=1, brand_key=brand_key, form_type="contact", full_name="Test",
                email="family@example.com", phone="999999999")
    service = EmailService(settings)
    if kind == "admin":
        service.send_admin_notification(lead)
    else:
        service.send_user_confirmation(lead)
    assert calls["host"] == f"smtp.{name}.example.com"
    assert calls["login"] == (f"user-{name}", f"secret-{name}")
    assert calls["message"]["From"] == f"{name} <{name}@example.com>"
    assert calls["message"]["Reply-To"] == f"reply-{name}@example.com"
    assert calls["message"]["To"] == (f"admin-{name}@example.com" if kind == "admin" else "family@example.com")


def test_missing_profile_does_not_fallback_to_default():
    settings = Settings(app_env="test", database_url="sqlite://",
                        mail_username="legacy", mail_password="legacy-secret")
    with pytest.raises(ValueError, match="perfil missing_test_profile") as error:
        settings.resolve_email_profile("missing_test_profile")
    assert "legacy-secret" not in str(error.value)


def test_profile_password_hidden_and_empty_password_rejected(monkeypatch):
    configure_profile(monkeypatch, "miedu")
    settings = Settings(app_env="test", database_url="sqlite://")
    assert "secret-miedu" not in repr(settings.resolve_email_profile("miedu"))
    monkeypatch.setenv("MIEDU_MAIL_PASSWORD", "")
    with pytest.raises(ValueError, match="Password SMTP vacio"):
        Settings(app_env="test", database_url="sqlite://").resolve_email_profile("miedu")


def test_production_profile_requires_tls(monkeypatch):
    configure_profile(monkeypatch, "miedu")
    monkeypatch.setenv("MIEDU_MAIL_USE_TLS", "false")
    settings = Settings(app_env="production", database_url="sqlite://", db_use_tls=True,
                        frontend_origins=["https://example.com"])
    with pytest.raises(ValueError, match="SMTP debe usar TLS"):
        settings.resolve_email_profile("miedu")


def test_invalid_profile_does_not_expose_secret(monkeypatch):
    configure_profile(monkeypatch, "miedu")
    monkeypatch.setenv("MIEDU_MAIL_PORT", "secret-port")
    with pytest.raises(ValueError) as error:
        Settings(app_env="test", database_url="sqlite://").resolve_email_profile("miedu")
    assert "secret-port" not in str(error.value)
    assert "secret-miedu" not in str(error.value)


def test_registry_validates_enabled_profiles_before_delivery():
    brand = BrandConfig(
        key="testing", display_name="Test", enabled=True, allowed_forms={"contact"},
        allowed_origins={"https://example.com"}, email_profile="missing_test_profile",
        admin_recipients=["admin@example.com"], reply_to="reply@example.com",
        templates={"admin": "new_lead.html", "user": "lead_confirmation.html"},
    )
    registry = BrandRegistry(BrandRegistryFile(brands=[brand]))
    settings = Settings(app_env="test", database_url="sqlite://", mail_enabled=True)
    with pytest.raises(ValueError, match="perfil missing_test_profile"):
        registry.validate_email_profiles(settings)
    brand.enabled = False
    registry.validate_email_profiles(settings)


def test_profile_reads_dotenv_and_environment_takes_priority(monkeypatch, tmp_path):
    monkeypatch.setattr("app.config.BASE_DIR", tmp_path)
    (tmp_path / ".env.test").write_text(
        "CUSTOM_MAIL_HOST=smtp.custom.example.com\n"
        "CUSTOM_MAIL_USERNAME=file-user\n"
        "CUSTOM_MAIL_PASSWORD=file-secret\n"
        "CUSTOM_MAIL_FROM=custom@example.com\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CUSTOM_MAIL_PASSWORD", "env-secret")
    profile = Settings(app_env="test", database_url="sqlite://").resolve_email_profile("custom")
    assert profile.mail_username == "file-user"
    assert profile.mail_password.get_secret_value() == "env-secret"


def test_medalla_default_keeps_legacy_recipient_and_reply_to(monkeypatch):
    from app.brands import get_brand_registry
    monkeypatch.setattr("app.services.email.get_brand_registry", get_brand_registry)
    settings = Settings(app_env="test", database_url="sqlite://",
                        mail_admin_to="legacy@example.com", mail_reply_to="legacy-reply@example.com")
    service = EmailService(settings)
    calls = {}
    monkeypatch.setattr(service, "_send", lambda *args, **kwargs: calls.update(args=args, kwargs=kwargs))
    service.send_admin_notification(Lead(id=1, brand_key="iep-medalla", form_type="contact",
                                        full_name="Test", email="family@example.com", phone="999999999"))
    assert calls["args"][0] == ["legacy@example.com"]
    assert calls["kwargs"]["reply_to"] == "legacy-reply@example.com"
    assert calls["kwargs"]["email_profile"] == "default"


@pytest.mark.parametrize("method", ["send_admin_notification", "send_user_confirmation"])
def test_disabled_brand_blocks_direct_email_send(monkeypatch, method):
    from app.brands import get_brand_registry
    monkeypatch.setattr(get_brand_registry().get("miedu-pe"), "notifications_enabled", False)
    service = EmailService(Settings(app_env="test", database_url="sqlite://", mail_enabled=True))
    def forbidden(*args, **kwargs):
        raise AssertionError("SMTP must not be called")
    monkeypatch.setattr(service, "_send", forbidden)
    getattr(service, method)(Lead(brand_key="miedu-pe"))


def test_disabled_notifications_do_not_require_smtp_credentials(monkeypatch):
    from app.brands import get_brand_registry
    brand = get_brand_registry().get("miedu-pe").model_copy(update={
        "email_profile": "missing_test_profile", "notifications_enabled": False,
    })
    registry = BrandRegistry(BrandRegistryFile(brands=[brand]))
    registry.validate_email_profiles(Settings(app_env="test", database_url="sqlite://", mail_enabled=True))


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


def test_smtp_starttls_uses_verified_default_context(monkeypatch):
    calls = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls.update(host=host, port=port, timeout=timeout)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def ehlo(self):
            pass

        def starttls(self, context):
            calls["context"] = context

        def login(self, username, password):
            calls["login"] = (username, password)

        def send_message(self, message):
            calls["to"] = message["To"]

    monkeypatch.setattr("app.services.email.smtplib.SMTP", FakeSMTP)
    settings = Settings(
        app_env="test",
        database_url="sqlite://",
        mail_enabled=True,
        mail_username="sandbox-user",
        mail_password="sandbox-password",
    )
    EmailService(settings)._send("family@example.com", "test", "text", "<p>text</p>")
    assert calls["context"].check_hostname is True
    assert calls["context"].verify_mode.name == "CERT_REQUIRED"
    assert calls["to"] == "family@example.com"
