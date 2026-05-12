"""Slack webhook notifications: draft ready, legal alert, error."""
import logging
from typing import Any

import requests

from src import config

logger = logging.getLogger(__name__)


def _post(payload: dict[str, Any]) -> None:
    if not config.SLACK_WEBHOOK_URL:
        logger.warning("SLACK_WEBHOOK_URL not set, skipping notification")
        return
    resp = requests.post(config.SLACK_WEBHOOK_URL, json=payload, timeout=10)
    if resp.status_code != 200:
        logger.error("Slack webhook failed (%d): %s", resp.status_code, resp.text)


def notify_draft_ready(
    conv_data: dict[str, Any],
    note_result: dict[str, Any],
    classification: dict[str, Any],
) -> None:
    subject = conv_data.get("subject", "(no subject)")
    from_email = conv_data.get("from_email", "unknown")
    category = classification.get("category", "unknown")
    confidence = classification.get("confidence", 0)
    summary = classification.get("summary", "")
    reamaze_link = conv_data.get("conversation_url", "")

    _post({"text": (
        f"*AI Draft ready for review*\n"
        f"From: {from_email}\n"
        f"Subject: {subject}\n"
        f"Category: {category} ({confidence:.0%})\n"
        f"Summary: {summary}\n"
        f"<{reamaze_link}|Open in Reamaze>\n"
        f"_The AI draft is saved as an internal note. Review and send manually._"
    )})


def notify_legal(conv_data: dict[str, Any], classification: dict[str, Any]) -> None:
    subject = conv_data.get("subject", "(no subject)")
    from_email = conv_data.get("from_email", "unknown")
    summary = classification.get("summary", "")
    reamaze_link = conv_data.get("conversation_url", "")

    _post({"text": (
        f":warning: *LEGAL -- no draft created*\n"
        f"From: {from_email}\n"
        f"Subject: {subject}\n"
        f"Summary: {summary}\n"
        f"<{reamaze_link}|Open in Reamaze>\n"
        f"This conversation was flagged as legal. Review manually."
    )})


def notify_error(slug: str, error: str) -> None:
    reamaze_link = f"https://{config.REAMAZE_BRAND}.reamaze.io/admin/conversations/{slug}"

    _post({"text": (
        f":x: *Conversation processing error*\n"
        f"Conversation: {slug}\n"
        f"Error: {error[:500]}\n"
        f"<{reamaze_link}|Open in Reamaze>"
    )})
