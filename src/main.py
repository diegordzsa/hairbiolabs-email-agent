"""Email agent: classify incoming Reamaze conversations, generate drafts, notify Slack."""
import logging
import sys
import time
from typing import Any

import anthropic
import requests

from src import claude_client, config, reamaze_client, shopify_client, slack_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

RETRY_BACKOFF = 3
MAX_RETRIES = 2
RETRYABLE_ERRORS = (
    anthropic.APIConnectionError,
    anthropic.RateLimitError,
    anthropic.InternalServerError,
    requests.ConnectionError,
)


def process_conversation(slug: str) -> dict[str, Any]:
    """Fetch, classify, and draft a response for one conversation."""
    try:
        conv_data = reamaze_client.get_conversation_details(slug)
        logger.info("Processing %s from %s: %s", slug, conv_data["from_email"], conv_data["subject"])

        if not conv_data["body"]:
            logger.warning("No customer message body found in %s, skipping", slug)
            reamaze_client.add_tag(slug, config.PROCESSED_TAG)
            return {"success": True}

        classification = claude_client.classify(conv_data["subject"], conv_data["body"])

        if classification["category"] == "legal":
            reamaze_client.add_tag(slug, config.LEGAL_TAG)
            reamaze_client.add_tag(slug, config.PROCESSED_TAG)
            slack_client.notify_legal(conv_data, classification)
            logger.info("Marked %s as legal, skipped draft", slug)
            return {"success": True}

        if classification["category"] == "spam_other":
            reamaze_client.add_tag(slug, config.PROCESSED_TAG)
            logger.info("Marked %s as spam/other, skipped", slug)
            return {"success": True}

        customer_context = shopify_client.lookup_customer(conv_data["from_email"])

        reply_text = claude_client.generate_reply(conv_data, classification, customer_context)

        if config.DRY_RUN:
            logger.info("DRY RUN: Would create note for %s:\n%s", slug, reply_text[:500])
            reamaze_client.add_tag(slug, config.PROCESSED_TAG)
            return {"success": True}

        note = reamaze_client.create_internal_note(slug, reply_text)

        reamaze_client.add_tag(slug, config.PROCESSED_TAG)
        slack_client.notify_draft_ready(conv_data, note, classification)
        logger.info("Successfully processed %s", slug)
        return {"success": True}

    except RETRYABLE_ERRORS as e:
        logger.error("Retryable error processing %s: %s", slug, e)
        return {"success": False, "error": str(e), "retryable": True}
    except Exception as e:
        logger.exception("Fatal error processing %s: %s", slug, e)
        return {"success": False, "error": str(e), "retryable": False}


def main():
    try:
        config.validate()
    except RuntimeError as e:
        logger.error("Config validation failed: %s", e)
        sys.exit(1)

    logger.info("Email agent starting (dry_run=%s)", config.DRY_RUN)

    conversations = reamaze_client.list_unprocessed_conversations()
    if not conversations:
        logger.info("No unprocessed conversations")
        return

    logger.info("Processing %d conversations", len(conversations))

    success_count = 0
    error_count = 0

    for conv in conversations:
        slug = conv["slug"]
        attempt = 0

        while attempt < MAX_RETRIES:
            result = process_conversation(slug)
            if result["success"]:
                success_count += 1
                break
            elif result.get("retryable"):
                attempt += 1
                if attempt < MAX_RETRIES:
                    delay = RETRY_BACKOFF * (2 ** attempt)
                    logger.warning("Retrying %s in %ds (attempt %d/%d)", slug, delay, attempt, MAX_RETRIES)
                    time.sleep(delay)
                else:
                    error_count += 1
                    try:
                        reamaze_client.add_tag(slug, config.ERROR_TAG)
                        slack_client.notify_error(slug, result["error"])
                    except Exception:
                        logger.exception("Failed to tag/notify error for %s", slug)
            else:
                error_count += 1
                try:
                    reamaze_client.add_tag(slug, config.ERROR_TAG)
                    slack_client.notify_error(slug, result["error"])
                except Exception:
                    logger.exception("Failed to tag/notify error for %s", slug)
                break

    logger.info("Email agent finished: %d success, %d errors", success_count, error_count)


if __name__ == "__main__":
    main()
