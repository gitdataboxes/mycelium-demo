import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from uuid import UUID

import aiosmtplib
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
from app.services.matching import MatchCandidate, run_matching

logger = logging.getLogger(__name__)


def _format_match_text(match: MatchCandidate, viewer_node_id: UUID) -> tuple[str, str]:
    """Format a single match for the digest. Returns (text_line, html_block)."""
    if match.node_a_id == viewer_node_id:
        other_content = match.attr_b_content
        own_content = match.attr_a_content
        own_dir = match.attr_a_direction
    else:
        other_content = match.attr_a_content
        own_content = match.attr_b_content
        own_dir = match.attr_b_direction

    if own_dir == "output":
        connector = "You offer"
        other_verb = "is looking for"
    else:
        connector = "You're looking for"
        other_verb = "offers"

    text_line = f"  - {connector}: \"{own_content}\" — someone {other_verb}: \"{other_content}\""
    html_block = f"""
    <div style="margin-bottom: 16px; padding: 12px; background: #f9fafb; border-radius: 8px;">
      <p style="margin: 0 0 4px 0; font-size: 14px; color: #374151;">
        <strong>{connector}:</strong> &ldquo;{own_content}&rdquo;
      </p>
      <p style="margin: 0; font-size: 14px; color: #6b7280;">
        Someone {other_verb}: &ldquo;{other_content}&rdquo;
      </p>
      <p style="margin: 8px 0 0 0;">
        <a href="{settings.base_url}/matches?a={match.attr_a_id}&b={match.attr_b_id}"
           style="font-size: 13px; color: #111827; text-decoration: underline;">
          View details &rarr;
        </a>
      </p>
    </div>
    """
    return text_line, html_block


async def send_digest(
    db: AsyncSession, node_id: UUID, email: str, matches: list[MatchCandidate]
) -> None:
    """Send a digest email to a single user."""
    text_lines = []
    html_blocks = []

    for m in matches:
        t, h = _format_match_text(m, node_id)
        text_lines.append(t)
        html_blocks.append(h)

    text_body = (
        "Mycelium found some connections for you:\n\n"
        + "\n".join(text_lines)
        + "\n\nLog in to explore: " + settings.base_url
    )

    html_body = f"""
    <div style="max-width: 560px; margin: 0 auto; font-family: -apple-system, sans-serif;">
      <h2 style="margin-bottom: 4px;">Mycelium</h2>
      <p style="color: #6b7280; margin-top: 0;">We found {len(matches)} connection{"s" if len(matches) != 1 else ""} for you.</p>
      {"".join(html_blocks)}
      <p style="margin-top: 24px; font-size: 13px; color: #9ca3af;">
        You're receiving this because you're a member of a Mycelium network.
      </p>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Mycelium: {len(matches)} new connection{'s' if len(matches) != 1 else ''}"
    msg["From"] = settings.smtp_from_email
    msg["To"] = email
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username or None,
            password=settings.smtp_password or None,
            use_tls=settings.smtp_use_tls,
        )
        logger.info("Sent digest to %s with %d matches", email, len(matches))
    except Exception:
        logger.exception("Failed to send digest to %s", email)


async def run_digest(db: AsyncSession) -> int:
    """Run the full matching + digest pipeline. Returns number of digests sent."""
    matches_by_node = await run_matching(db)

    if not matches_by_node:
        logger.info("No matches found, no digests to send")
        return 0

    sent = 0
    for node_id, matches in matches_by_node.items():
        result = await db.execute(
            select(User).where(User.node_id == node_id, User.is_active == True)
        )
        user = result.scalar_one_or_none()
        if user is None:
            continue

        await send_digest(db, node_id, user.email, matches)
        sent += 1

    logger.info("Digest run complete: %d emails sent", sent)
    return sent
