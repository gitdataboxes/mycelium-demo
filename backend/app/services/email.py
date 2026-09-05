import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from app.config import settings

logger = logging.getLogger(__name__)


async def send_magic_link_email(to_email: str, token: str) -> None:
    url = f"{settings.base_url}/auth/verify?token={token}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Your Mycelium login link"
    msg["From"] = settings.smtp_from_email
    msg["To"] = to_email

    text = f"Click here to log in to Mycelium:\n\n{url}\n\nThis link expires in {settings.magic_link_ttl_minutes} minutes."
    html = f"""
    <h2>Mycelium</h2>
    <p>Click the link below to log in:</p>
    <p><a href="{url}">Log in to Mycelium</a></p>
    <p><small>This link expires in {settings.magic_link_ttl_minutes} minutes.</small></p>
    """

    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username or None,
            password=settings.smtp_password or None,
            use_tls=settings.smtp_use_tls,
        )
    except Exception:
        logger.exception("Failed to send magic link email to %s", to_email)
        # In dev, log the link so it's still usable
        logger.info("Magic link for %s: %s", to_email, url)
        raise


async def send_invite_email(to_email: str, voucher_name: str, token: str) -> None:
    url = f"{settings.base_url}/auth/verify?token={token}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{voucher_name} invited you to Mycelium"
    msg["From"] = settings.smtp_from_email
    msg["To"] = to_email

    text = f"{voucher_name} has vouched for you to join Mycelium.\n\nClick here to get started:\n\n{url}\n\nThis link expires in {settings.magic_link_ttl_minutes} minutes."
    html = f"""
    <h2>Welcome to Mycelium</h2>
    <p><strong>{voucher_name}</strong> has vouched for you to join the network.</p>
    <p><a href="{url}">Join Mycelium</a></p>
    <p><small>This link expires in {settings.magic_link_ttl_minutes} minutes.</small></p>
    """

    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username or None,
            password=settings.smtp_password or None,
            use_tls=settings.smtp_use_tls,
        )
    except Exception:
        logger.exception("Failed to send invite email to %s", to_email)
        logger.info("Invite link for %s: %s", to_email, url)
        raise
