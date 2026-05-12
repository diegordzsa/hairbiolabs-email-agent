"""Claude API client: classify emails with Haiku, generate replies with Sonnet."""
import json
import logging
from pathlib import Path
from typing import Any

import anthropic

from src import config

logger = logging.getLogger(__name__)

_client: anthropic.Anthropic | None = None
_policies: str | None = None

POLICIES_PATH = Path(__file__).parent.parent / "policies" / "hair_biolabs.md"


def _get_client() -> anthropic.Anthropic:
    global _client
    if not _client:
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def _load_policies() -> str:
    global _policies
    if not _policies:
        _policies = POLICIES_PATH.read_text(encoding="utf-8")
    return _policies


CLASSIFY_SYSTEM = """You are an email classifier for Hair Biolabs (hairbiolabs.com), a hair care and wellness brand.

Classify the incoming customer email into exactly ONE category:
- order_status: questions about order delivery, tracking, shipping status, where is my order
- product_question: questions about products, ingredients, usage, availability, the serum
- return_refund: return requests, refund requests, 120-day guarantee claims
- complaint: complaints, frustration, negative experiences, dissatisfaction
- legal: legal threats, mentions of lawyers, regulators, lawsuits, formal legal demands
- spam_other: marketing, spam, irrelevant, automated messages, newsletters

Respond ONLY with valid JSON:
{"category": "...", "confidence": 0.0-1.0, "language": "es|en|other", "summary": "one-line English summary"}"""

GENERATE_SYSTEM = """You are the customer service agent for Hair Biolabs (hairbiolabs.com), a hair care brand specializing in hair growth serums.

Rules:
- Detect the customer's language (Spanish or English) and reply in that SAME language
- Warm, professional, empathetic tone
- Sign off as "Equipo Hair Biolabs"
- Use the Hair Biolabs policies below for accuracy -- never promise beyond what policies allow
- For refund requests: explain the 120-day guarantee requirements (daily use, monthly photos). Direct them to email info@hairbiolabs.com with subject "Solicitud de Reembolso 120 Dias" and attach their 4 monthly photos
- For subscription cancellations: remind them of the 2-month minimum commitment and 5-day advance notice requirement. Direct to customer portal or contacto@hairbiolabs.com
- Include relevant order/tracking info when available from the Shopify context
- If no order context is available, ask the customer for their order number
- For damaged/wrong items, ask for photos
- Keep replies concise but complete
- Contact: contacto@hairbiolabs.com (general), info@hairbiolabs.com (refunds)

Hair Biolabs Policies:
{policies}"""


def classify(subject: str, body: str) -> dict[str, Any]:
    """Classify an email using Haiku. Returns {category, confidence, language, summary}."""
    client = _get_client()
    user_content = f"Subject: {subject}\n\nBody:\n{body[:3000]}"

    resp = client.messages.create(
        model=config.CLASSIFY_MODEL,
        max_tokens=200,
        system=CLASSIFY_SYSTEM,
        messages=[{"role": "user", "content": user_content}],
    )

    text = resp.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0].strip()
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        logger.error("Classification returned invalid JSON: %s", text)
        return {"category": "spam_other", "confidence": 0.0, "language": "unknown", "summary": "parse error"}

    logger.info("Classified as %s (%.0f%%): %s", result["category"], result["confidence"] * 100, result["summary"])
    return result


def generate_reply(
    email_data: dict[str, Any],
    classification: dict[str, Any],
    customer_context: dict[str, Any],
) -> str:
    """Generate a reply using Sonnet. Auto-detects language. Returns the reply text."""
    client = _get_client()
    policies = _load_policies()
    system = GENERATE_SYSTEM.format(policies=policies)

    context_parts = [
        f"Category: {classification['category']}",
        f"Detected language: {classification.get('language', 'unknown')}",
        f"Customer email: {email_data['from_email']}",
        f"Customer name: {email_data.get('from_name', 'unknown')}",
        f"Subject: {email_data['subject']}",
        f"\nOriginal message:\n{email_data['body'][:4000]}",
    ]

    if customer_context.get("found"):
        cust = customer_context["customer"]
        context_parts.append(f"\nShopify customer: {cust['name']} ({cust['email']})")
        context_parts.append(f"Total orders: {cust.get('orders_count', 0)}")

        for order in customer_context.get("orders", [])[:3]:
            items = ", ".join(f"{li['title']} x{li['quantity']}" for li in order["line_items"])
            tracking = ", ".join(order["tracking_numbers"]) if order["tracking_numbers"] else "none"
            context_parts.append(
                f"\nOrder {order['name']} ({order['created_at'][:10]}): "
                f"{order['financial_status']}, fulfillment: {order['fulfillment_status'] or 'unfulfilled'}, "
                f"total: ${order['total_price']} {order['currency']}\n"
                f"  Items: {items}\n"
                f"  Tracking: {tracking}"
            )
            if order["tracking_urls"]:
                context_parts.append(f"  Tracking URLs: {', '.join(order['tracking_urls'])}")
    else:
        context_parts.append("\nNo Shopify customer record found for this email.")

    user_content = "\n".join(context_parts)

    resp = client.messages.create(
        model=config.GENERATE_MODEL,
        max_tokens=1000,
        system=system,
        messages=[{"role": "user", "content": user_content}],
    )

    reply = resp.content[0].text.strip()
    logger.info("Generated reply (%d chars)", len(reply))
    return reply
