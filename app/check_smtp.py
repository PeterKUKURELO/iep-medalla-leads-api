from __future__ import annotations

import argparse
import smtplib
import sys
from collections.abc import Sequence

from app.config import Settings, get_settings
from app.services.smtp import SMTPTransport


def verify_smtp_profile(settings: Settings, profile_name: str) -> None:
    profile = settings.resolve_email_profile(profile_name)
    SMTPTransport(profile).verify_connection()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Valida configuracion, STARTTLS y autenticacion de un perfil SMTP sin enviar correos.",
    )
    parser.add_argument("--profile", required=True, help="Perfil SMTP, por ejemplo: miedu")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        settings = get_settings()
        profile = settings.resolve_email_profile(args.profile)
        SMTPTransport(profile).verify_connection()
    except (ValueError, OSError, smtplib.SMTPException) as exc:
        print(
            f"SMTP {args.profile}: ERROR ({type(exc).__name__}). Revisa configuracion, red y credenciales.",
            file=sys.stderr,
        )
        return 1
    print(
        f"SMTP {args.profile}: OK; host={profile.mail_host}; port={profile.mail_port}; "
        f"starttls={str(profile.mail_use_tls).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
