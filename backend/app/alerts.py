import logging
import smtplib
import ssl
from email.mime.text import MIMEText

from . import config

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


def send_lockout_alert(attempted_username: str) -> None:
    logger.warning("Sending lockout alert: attempted_username=%s", attempted_username)
    subject = "Athena security alert: login locked after 3 failed attempts"
    body = (
        "The Athena login page was locked after 3 failed login attempts.\n"
        f"Attempted username: {attempted_username}\n"
    )

    _send_email(config.ALERT_ADMIN_EMAIL, subject, body)

    if config.ALERT_MOBILE_GATEWAY_DOMAIN:
        sms_address = f"{config.ALERT_ADMIN_MOBILE}@{config.ALERT_MOBILE_GATEWAY_DOMAIN}"
        _send_email(sms_address, subject, body)
    else:
        logger.info("ALERT_MOBILE_GATEWAY_DOMAIN not set; skipping SMS alert.")
