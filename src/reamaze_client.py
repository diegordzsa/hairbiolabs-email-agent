"""Reamaze API client: fetch conversations, classify messages, create notes, manage tags."""
import logging
import time
from typing import Any, Optional

import requests
from dateutil import parser as date_parser

from src import config

logger = logging.getLogger(__name__)

BASE_URL = f"https://{config.REAMAZE_BRAND}.reamaze.io/api/v1"
AUTH = (config.REAMAZE_LOGIN_EMAIL, config.REAMAZE_API_TOKEN)
HEADERS = {"Accept": "application/json"}

_staff_emails: set[str] | None = None
_staff_names: set[str] | None = None


# ---------------------------------------------------------------------------
# Low-level HTTP helpers
# ---------------------------------------------------------------------------

def _get(path: str, params: dict | None = None, retries: int = 3) -> dict:
    url = f"{BASE_URL}{path}"
    for attempt in range(retries):
        r = requests.get(url, auth=AUTH, headers=HEADERS, params=params or {}, timeout=30)
        if r.status_code == 429:
            wait = 2 ** attempt
            logger.warning("Rate limited, sleeping %ds", wait)
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"Failed after {retries} retries: {url}")


def _put(path: str, json_body: dict, retries: int = 3) -> dict:
    url = f"{BASE_URL}{path}"
    for attempt in range(retries):
        r = requests.put(url, auth=AUTH, headers={**HEADERS, "Content-Type": "application/json"},
                         json=json_body, timeout=30)
        if r.status_code == 429:
            wait = 2 ** attempt
            logger.warning("Rate limited, sleeping %ds", wait)
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"Failed after {retries} retries: {url}")


def _post(path: str, json_body: dict, retries: int = 3) -> dict:
    url = f"{BASE_URL}{path}"
    for attempt in range(retries):
        r = requests.post(url, auth=AUTH, headers={**HEADERS, "Content-Type": "application/json"},
                          json=json_body, timeout=30)
        if r.status_code == 429:
            wait = 2 ** attempt
            logger.warning("Rate limited, sleeping %ds", wait)
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"Failed after {retries} retries: {url}")


def _paginate(path: str, key: str, params: dict | None = None, max_pages: int = 100) -> list[dict]:
    items: list[dict] = []
    base_params = dict(params or {})
    page = 1
    while True:
        base_params["page"] = page
        data = _get(path, params=base_params)
        batch = data.get(key, [])
        if not batch:
            break
        items.extend(batch)
        page_count = data.get("page_count", 1)
        if page >= page_count:
            break
        page += 1
        if page > max_pages:
            logger.warning("Hit page cap of %d, stopping pagination", max_pages)
            break
    return items


# ---------------------------------------------------------------------------
# Staff info & message classification
# ---------------------------------------------------------------------------

def _fetch_staff_info() -> tuple[set[str], set[str]]:
    emails: set[str] = set()
    names: set[str] = set()
    staff_list = _paginate("/staff", "staff", max_pages=20)
    for s in staff_list:
        if s.get("email"):
            emails.add(s["email"].lower())
        if s.get("name"):
            names.add(s["name"].lower())
    emails.update(e.lower() for e in config.CHANNEL_INBOX_EMAILS)
    logger.info("Loaded %d staff emails, %d staff names", len(emails), len(names))
    return emails, names


def _get_staff_info() -> tuple[set[str], set[str]]:
    global _staff_emails, _staff_names
    if _staff_emails is None:
        _staff_emails, _staff_names = _fetch_staff_info()
    return _staff_emails, _staff_names


def _msg_sender_email(msg: dict) -> str:
    user = msg.get("user") or {}
    return (user.get("email") or "").lower()


def _msg_sender_name(msg: dict) -> str:
    user = msg.get("user") or {}
    return (user.get("name") or "").lower()


def _is_notification_sender(email: str) -> bool:
    if not email:
        return False
    email_lower = email.lower()
    if email_lower in config.NOTIFICATION_SENDERS:
        return True
    domain = email_lower.split("@", 1)[-1] if "@" in email_lower else ""
    return domain in config.NOTIFICATION_DOMAINS


_channel_inbox_lower = {e.lower() for e in config.CHANNEL_INBOX_EMAILS}


def _classify_message(msg: dict, staff_emails: set[str], staff_names: set[str]) -> str:
    """Classify a message as 'staff', 'customer', 'notification', or 'skip'."""
    if msg.get("visibility") != 0:
        return "skip"

    email = _msg_sender_email(msg)
    if not email:
        return "skip"

    if email in staff_emails and email not in _channel_inbox_lower:
        return "staff"

    if email in _channel_inbox_lower:
        name = _msg_sender_name(msg)
        if name and name in staff_names:
            return "staff"
        return "notification"

    if _is_notification_sender(email):
        return "notification"

    return "customer"


# ---------------------------------------------------------------------------
# Conversation operations
# ---------------------------------------------------------------------------

def list_unprocessed_conversations(lookback_minutes: int | None = None) -> list[dict]:
    """Fetch unresolved conversations where the last message is from a real customer."""
    if lookback_minutes is None:
        lookback_minutes = config.LOOKBACK_MINUTES

    staff_emails, staff_names = _get_staff_info()

    conversations = _paginate("/conversations", "conversations",
                              params={"filter[status]": "unresolved"}, max_pages=10)
    logger.info("Fetched %d unresolved conversations", len(conversations))

    result: list[dict] = []
    for conv in conversations:
        tag_list = [t.lower() for t in (conv.get("tag_list") or [])]
        if config.PROCESSED_TAG in tag_list:
            continue

        messages = conv.get("message", []) if isinstance(conv.get("message"), list) else []
        if not messages:
            continue

        last_msg = messages[-1]
        if _classify_message(last_msg, staff_emails, staff_names) != "customer":
            continue

        result.append({
            "slug": conv["slug"],
            "subject": conv.get("subject", "(no subject)"),
        })

    logger.info("Found %d unprocessed customer conversations", len(result))
    return result


def get_conversation_details(slug: str) -> dict[str, Any]:
    """Fetch a conversation and extract the latest customer message."""
    data = _get(f"/conversations/{slug}")
    conv = data.get("conversation", data)

    staff_emails, staff_names = _get_staff_info()

    messages = conv.get("message", []) if isinstance(conv.get("message"), list) else []
    messages_full = _paginate(f"/conversations/{slug}/messages", "messages", max_pages=5)
    if messages_full:
        messages = messages_full
    messages.sort(key=lambda m: m.get("created_at", ""))

    customer_msg = None
    for msg in reversed(messages):
        if _classify_message(msg, staff_emails, staff_names) == "customer":
            customer_msg = msg
            break

    if customer_msg:
        user = customer_msg.get("user") or {}
        body = customer_msg.get("body", "")
        from_email = (user.get("email") or "").lower()
        from_name = user.get("name") or ""
        date = customer_msg.get("created_at", "")
    else:
        body = ""
        from_email = ""
        from_name = ""
        date = ""

    return {
        "slug": slug,
        "subject": conv.get("subject", "(no subject)"),
        "from_email": from_email,
        "from_name": from_name,
        "body": body,
        "date": date,
        "conversation_url": f"https://{config.REAMAZE_BRAND}.reamaze.io/admin/conversations/{slug}",
    }


def create_internal_note(slug: str, body: str) -> dict[str, Any]:
    """Create an internal note (AI draft) on a conversation. Not visible to the customer."""
    note_body = (
        "<strong>[AI DRAFT - Review before sending]</strong><br><br>"
        f"{body}<br><br>"
        "<hr><em>Generated by Hair Biolabs Email Agent. Do NOT send without review.</em>"
    )
    data = _post(f"/conversations/{slug}/messages", {
        "message": {
            "body": note_body,
            "visibility": 1,
        }
    })
    logger.info("Created internal note on conversation %s", slug)
    return data


def add_tag(slug: str, tag_name: str) -> None:
    """Add a tag to a conversation."""
    conv_data = _get(f"/conversations/{slug}")
    conv = conv_data.get("conversation", conv_data)
    existing_tags = list(conv.get("tag_list") or [])
    if tag_name not in existing_tags:
        existing_tags.append(tag_name)
        _put(f"/conversations/{slug}", {"conversation": {"tag_list": existing_tags}})
        logger.debug("Added tag '%s' to conversation %s", tag_name, slug)


def remove_tag(slug: str, tag_name: str) -> None:
    """Remove a tag from a conversation."""
    conv_data = _get(f"/conversations/{slug}")
    conv = conv_data.get("conversation", conv_data)
    existing_tags = list(conv.get("tag_list") or [])
    if tag_name in existing_tags:
        existing_tags.remove(tag_name)
        _put(f"/conversations/{slug}", {"conversation": {"tag_list": existing_tags}})
        logger.debug("Removed tag '%s' from conversation %s", tag_name, slug)


def reset_staff_cache() -> None:
    """Clear cached staff info. Called between runs if needed."""
    global _staff_emails, _staff_names
    _staff_emails = None
    _staff_names = None
