"""Configuration loaded from environment variables."""
import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

# --- Reamaze API ---
REAMAZE_BRAND = os.environ.get("REAMAZE_BRAND", "hairbiolabs")
REAMAZE_LOGIN_EMAIL = os.environ.get("REAMAZE_LOGIN_EMAIL", "")
REAMAZE_API_TOKEN = os.environ.get("REAMAZE_API_TOKEN", "")

# --- Shopify (client credentials grant) ---
SHOPIFY_STORE_DOMAIN = os.environ.get("SHOPIFY_STORE_DOMAIN", "")
SHOPIFY_CLIENT_ID = os.environ.get("SHOPIFY_CLIENT_ID", "")
SHOPIFY_CLIENT_SECRET = os.environ.get("SHOPIFY_CLIENT_SECRET", "")

# --- Anthropic ---
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLASSIFY_MODEL = "claude-haiku-4-5-20251001"
GENERATE_MODEL = "claude-sonnet-4-6"

# --- Slack ---
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")

# --- Operational ---
TIMEZONE = ZoneInfo(os.environ.get("TIMEZONE", "America/Mexico_City"))
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"

# --- Brand ---
BRAND_NAME = "Hair Biolabs"
BRAND_DOMAIN = "hairbiolabs.com"
SUPPORT_EMAIL = "contacto@hairbiolabs.com"
REFUND_EMAIL = "info@hairbiolabs.com"

# --- Reamaze tags ---
PROCESSED_TAG = "ai-processed"
ERROR_TAG = "ai-error"
LEGAL_TAG = "ai-legal-review"

# --- Polling ---
LOOKBACK_MINUTES = 30

# --- Categories ---
CATEGORIES = [
    "order_status",
    "product_question",
    "return_refund",
    "complaint",
    "legal",
    "spam_other",
]

# --- Automated sender exclusion (from reamaze-slack-reporter) ---
CHANNEL_INBOX_EMAILS = {
    "contacto@hairbiolabs.com",
}

STAFF_EMAILS = {
    e.strip().lower()
    for e in os.environ.get("STAFF_EMAILS", "").split(",")
    if e.strip()
}

NOTIFICATION_SENDERS = {
    "no-reply@merchanto.org",
    "no-reply@klaviyo.com",
    "noreply@klaviyo.com",
    "support@appstle.com",
    "np@neilpatel.com",
    "mailer@shopify.com",
    "noreply@shopify.com",
    "hello@disputifier.com",
}

NOTIFICATION_DOMAINS = {
    "klaviyo.com",
    "shopify.com",
    "merchanto.org",
    "disputifier.com",
}


def validate() -> None:
    """Fail fast if any required env var is missing."""
    required = {
        "REAMAZE_LOGIN_EMAIL": REAMAZE_LOGIN_EMAIL,
        "REAMAZE_API_TOKEN": REAMAZE_API_TOKEN,
        "SHOPIFY_STORE_DOMAIN": SHOPIFY_STORE_DOMAIN,
        "SHOPIFY_CLIENT_ID": SHOPIFY_CLIENT_ID,
        "SHOPIFY_CLIENT_SECRET": SHOPIFY_CLIENT_SECRET,
        "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
        "SLACK_WEBHOOK_URL": SLACK_WEBHOOK_URL,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"Missing env vars: {', '.join(missing)}")
