import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from typing import Optional

from . import config, login_throttle, rag

logger = logging.getLogger(__name__)


def _send_email(to_address: str, subject: str, body: str) -> None:
    if not (config.SMTP_HOST and config.SMTP_USERNAME and config.SMTP_PASSWORD):
        logger.warning("SMTP not configured; skipping alert to %s", to_address)
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = config.SMTP_FROM_EMAIL
    msg["To"] = to_address

    context = ssl.create_default_context()

    try:
        if config.SMTP_PORT == 465:
            # Implicit TLS/SSL from the start of the connection.
            with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, context=context) as server:
                server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
                server.sendmail(config.SMTP_FROM_EMAIL, [to_address], msg.as_string())
        else:
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
                server.ehlo()
                if config.SMTP_USE_TLS:
                    server.starttls(context=context)
                    server.ehlo()
                server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
                server.sendmail(config.SMTP_FROM_EMAIL, [to_address], msg.as_string())
    except (smtplib.SMTPException, OSError):
        # Never let an alerting failure crash whatever triggered the alert
        # (e.g. the login-lockout path) — log it and move on.
        logger.exception("Failed to send alert email to %s", to_address)
        return

    logger.info("Alert email sent to %s", to_address)


def _describe_lockout_pattern(attempted_username: str) -> Optional[str]:
    """Best-effort AI risk read on this lockout's timing — e.g. 3 attempts
    within 8 seconds reads very differently from 3 attempts spread over
    several minutes. Returns None (never raises) if Gemini isn't configured
    or the call fails; send_lockout_alert() falls back to the plain
    non-AI message in that case, so the alert always still sends."""
    count, span = login_throttle.get_attempt_span(attempted_username)
    if count < 2:
        return None
    prompt = (
        f"A login account named '{attempted_username}' was just locked after {count} failed "
        f"password attempts within {span:.0f} seconds. In exactly 1-2 short sentences, plain "
        "English, tell a security admin whether this timing looks like an automated "
        "brute-force attempt or an ordinary human mistake (e.g. a forgotten password), and "
        "briefly why. No preamble, no markdown, no headers."
    )
    return rag.generate_short_text(prompt, max_tokens=150)


def send_lockout_alert(attempted_username: str) -> None:
    logger.warning("Sending lockout alert: attempted_username=%s", attempted_username)
    subject = "Athena security alert: login locked after 3 failed attempts"
    body = (
        "The Athena login page was locked after 3 failed login attempts.\n"
        f"Attempted username: {attempted_username}\n"
    )

    email_body = body
    ai_summary = _describe_lockout_pattern(attempted_username)
    if ai_summary:
        email_body += f"\nAI risk read: {ai_summary}\n"
        logger.info("AI summary generated for lockout alert: username=%s", attempted_username)
    else:
        logger.info("AI summary unavailable for lockout alert: username=%s", attempted_username)

    _send_email(config.ALERT_ADMIN_EMAIL, subject, email_body)

    if config.ALERT_MOBILE_GATEWAY_DOMAIN:
        # Plain body here, not email_body — SMS-via-email gateways often
        # truncate at ~160 chars, so keep this leg short regardless of how
        # long the AI summary turned out to be.
        sms_address = f"{config.ALERT_ADMIN_MOBILE}@{config.ALERT_MOBILE_GATEWAY_DOMAIN}"
        _send_email(sms_address, subject, body)
    else:
        logger.info("ALERT_MOBILE_GATEWAY_DOMAIN not set; skipping SMS alert.")
