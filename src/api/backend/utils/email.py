"""
Email utility for sending alerts via SMTP.
"""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Optional, Sequence


class EmailConfigError(RuntimeError):
    pass


def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name, default)
    return value if value not in ("", None) else default


def send_alert_email(
    *,
    subject: str,
    body_text: str,
    to_email: str,
    reply_to: Optional[str] = None,
    bcc: Optional[Sequence[str]] = None,
) -> None:
    host = _get_env("SMTP_HOST")
    port = int(_get_env("SMTP_PORT", "587") or "587")
    user = _get_env("SMTP_USER")
    password = _get_env("SMTP_PASS")
    sender_email = _get_env("SMTP_FROM") or user
    sender_name = _get_env("SMTP_FROM_NAME", "ProjectFlow")
    use_tls = (_get_env("SMTP_USE_TLS", "true") or "true").lower() == "true"

    if not host or not sender_email:
        raise EmailConfigError("SMTP_HOST and SMTP_FROM (or SMTP_USER) must be set")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{sender_name} <{sender_email}>"
    msg["To"] = to_email
    if reply_to:
        msg["Reply-To"] = reply_to
    if bcc:
        msg["Bcc"] = ", ".join(bcc)
    msg.set_content(body_text)

    if user and password:
        auth = (user, password)
    else:
        auth = None

    if use_tls:
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            if auth:
                server.login(*auth)
            server.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.ehlo()
            if auth:
                server.login(*auth)
            server.send_message(msg)
