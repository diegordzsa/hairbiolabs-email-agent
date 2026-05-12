"""Tests for Reamaze message classification logic."""


def _make_msg(email: str, name: str = "", visibility: int = 0) -> dict:
    return {
        "visibility": visibility,
        "user": {"email": email, "name": name},
    }


STAFF_EMAILS = {"agent@hairbiolabs.com", "contacto@hairbiolabs.com"}
STAFF_NAMES = {"agent one"}


def test_internal_note_is_skipped():
    from src.reamaze_client import _classify_message
    msg = _make_msg("customer@example.com", visibility=1)
    assert _classify_message(msg, STAFF_EMAILS, STAFF_NAMES) == "skip"


def test_staff_personal_email_is_staff():
    from src.reamaze_client import _classify_message
    msg = _make_msg("agent@hairbiolabs.com", name="Agent One")
    assert _classify_message(msg, STAFF_EMAILS, STAFF_NAMES) == "staff"


def test_channel_inbox_with_staff_name_is_staff():
    from src.reamaze_client import _classify_message
    msg = _make_msg("contacto@hairbiolabs.com", name="Agent One")
    assert _classify_message(msg, STAFF_EMAILS, STAFF_NAMES) == "staff"


def test_channel_inbox_without_staff_name_is_notification():
    from src.reamaze_client import _classify_message
    msg = _make_msg("contacto@hairbiolabs.com", name="Unknown System")
    assert _classify_message(msg, STAFF_EMAILS, STAFF_NAMES) == "notification"


def test_notification_sender_is_notification():
    from src.reamaze_client import _classify_message
    msg = _make_msg("no-reply@klaviyo.com")
    assert _classify_message(msg, STAFF_EMAILS, STAFF_NAMES) == "notification"


def test_notification_domain_is_notification():
    from src.reamaze_client import _classify_message
    msg = _make_msg("anything@shopify.com")
    assert _classify_message(msg, STAFF_EMAILS, STAFF_NAMES) == "notification"


def test_real_customer_is_customer():
    from src.reamaze_client import _classify_message
    msg = _make_msg("john@gmail.com", name="John Doe")
    assert _classify_message(msg, STAFF_EMAILS, STAFF_NAMES) == "customer"


def test_empty_email_is_skipped():
    from src.reamaze_client import _classify_message
    msg = _make_msg("", name="No Email")
    assert _classify_message(msg, STAFF_EMAILS, STAFF_NAMES) == "skip"
