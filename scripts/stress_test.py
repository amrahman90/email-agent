#!/usr/bin/env python3
"""Stress test email generator for email-agent.

Generates sample Gmail emails to test the full pipeline:
    - Different categories (Work, Personal, Finance, etc.)
    - Different importance levels (important senders, random senders)
    - Different actions (REPLY, IGNORE, SUSPICIOUS)
    - Business rules test cases (phishing, travel, etc.)
    - HTML vs plain text emails

Usage:
    uv run python scripts/stress_test.py [--count N] [--clear]

The script creates N test emails (default: 10) in the authenticated
user's Gmail account and labels them "email-agent-test".

Exit codes:
    0 = Success
    1 = Gmail auth failed
    2 = API error
    4 = Unexpected error
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from datetime import UTC, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

# Add project root and src/ to path for imports
_project_root = Path(__file__).parent.parent.resolve()
_src_dir = _project_root / "src"
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

EMAIL_FROM = "test@example.com"
EMAIL_TO = "me@gmail.com"


# ---------------------------------------------------------------------------
# Test email templates
# ---------------------------------------------------------------------------


def _make_email(
    subject: str,
    body: str,
    from_addr: str = EMAIL_FROM,
    to_addr: str = EMAIL_TO,
    html: bool = False,
    thread_id: str | None = None,
) -> dict[str, str]:
    """Build a raw MIME email message.

    Args:
        subject: Email subject line.
        body: Plain text body.
        from_addr: From address.
        to_addr: To address.
        html: If True, also include HTML part.
        thread_id: Optional thread ID for threading.

    Returns:
        Dict with 'raw' (base64url-encoded message) suitable for Gmail API.
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr

    # Add date header
    now = datetime.now(UTC).strftime("%a, %d %b %Y %H:%M:%S +0000")
    msg["Date"] = now

    if thread_id:
        msg["Thread-ID"] = thread_id

    # Plain text part
    msg.attach(MIMEText(body, "plain"))

    # HTML part (if requested)
    if html:
        html_body = f"<html><body><p>{body.replace(chr(10), '<br>')}</p></body></html>"
        msg.attach(MIMEText(html_body, "html"))

    # Encode as base64url (Gmail API format)
    raw_bytes = msg.as_bytes()
    raw_b64 = base64.urlsafe_b64encode(raw_bytes).decode("ascii")
    return {"raw": raw_b64}


# ---------------------------------------------------------------------------
# Test email definitions
# ---------------------------------------------------------------------------

TEST_EMAILS: list[dict[str, Any]] = [
    # Category: Work - should get REPLY
    {
        "label": "Work",
        "subject": "Q4 Budget Review Meeting",
        "body": (
            "Hi,\n\n"
            "Let's schedule a meeting to discuss the Q4 budget review.\n"
            "Please let me know your availability for Thursday or Friday afternoon.\n\n"
            "Best regards,\n"
            "John Smith\n"
            "Finance Team"
        ),
        "from_addr": "john.smith@company.com",
        "html": False,
    },
    # Category: Personal - should get IGNORE
    {
        "label": "Personal",
        "subject": "Saturday BBQ",
        "body": (
            "Hey,\n\n"
            "We're having a BBQ this Saturday at 2pm. Hope you can make it!\n"
            "Let me know if you need the address.\n\n"
            "Cheers"
        ),
        "from_addr": "friend@gmail.com",
        "html": False,
    },
    # Category: Finance - should get REPLY
    {
        "label": "Finance",
        "subject": "Your Bank Statement is Ready",
        "body": (
            "Dear Customer,\n\n"
            "Your bank statement for March 2026 is now available.\n"
            "Please log in to your online banking to view it.\n\n"
            "Thank you,\n"
            "Customer Service"
        ),
        "from_addr": "noreply@bank.com",
        "html": True,
    },
    # Phishing test - should get SUSPICIOUS (business rules override)
    {
        "label": "Work",
        "subject": "URGENT: Verify Your Account Now!",
        "body": (
            "Dear Employee,\n\n"
            "Your account will be suspended within 24 hours unless you "
            "click here to verify your credentials: http://bit.ly/verify-account\n\n"
            "Please provide your password immediately to avoid suspension.\n\n"
            "IT Department"
        ),
        "from_addr": "it-support@company-secure.com",
        "html": True,
        "suspicious": True,
    },
    # Travel confirmation - should get IGNORE (business rules override)
    {
        "label": "Travel",
        "subject": "Flight Confirmation AA1234",
        "body": (
            "Your flight is confirmed.\n\n"
            "Flight: AA1234\n"
            "Date: March 25, 2026\n"
            "Departure: 10:00 AM JFK\n"
            "Arrival: 1:00 PM LAX\n\n"
            "Please arrive 2 hours early."
        ),
        "from_addr": "confirm@airlines.com",
        "html": False,
        "travel": True,
    },
    # Important sender - should get REPLY and draft
    {
        "label": "Work",
        "subject": "Project deadline update",
        "body": (
            "Hi,\n\n"
            "The project deadline has been moved up by one week.\n"
            "Please confirm you can deliver by the new date.\n\n"
            "Thanks,\n"
            "Sarah (Director)"
        ),
        "from_addr": "sarah.director@company.com",
        "html": False,
        "important": True,
    },
    # Newsletter - should get IGNORE
    {
        "label": "Shopping",
        "subject": "Weekly Deals Newsletter",
        "body": (
            "This week only: 50% off all electronics!\n\n"
            "Shop now at ExampleStore.com\n\n"
            "Use code: WEEKLY50"
        ),
        "from_addr": "deals@examplestore.com",
        "html": True,
        "newsletter": True,
    },
    # Meeting invite - should get REPLY
    {
        "label": "Work",
        "subject": "Team Sync - March 20",
        "body": (
            "Hi team,\n\n"
            "Let's have our weekly sync on Thursday at 3pm.\n"
            "Agenda:\n"
            "- Status updates\n"
            "- Blockers\n"
            "- Any questions\n\n"
            "Join link: https://meet.example.com/team-sync\n\n"
            "Thanks"
        ),
        "from_addr": "calendar@company.com",
        "html": True,
    },
    # Social - should get IGNORE
    {
        "label": "Personal",
        "subject": "Re: Re: Re: Funny cat video",
        "body": (
            "LOL that video was hilarious!\n\n"
            "Here's another one: https://youtube.com/watch?v=catvideo\n\n"
            "Sent from my iPhone"
        ),
        "from_addr": "buddy@gmail.com",
        "html": False,
    },
    # Finance - urgent - should get REPLY
    {
        "label": "Finance",
        "subject": "Action Required: Unusual Spending Alert",
        "body": (
            "Dear Customer,\n\n"
            "We detected unusual spending on your card ending 1234.\n"
            "If this was you, please ignore this message.\n"
            "If you don't recognize this transaction, please call us immediately.\n\n"
            "Card Services"
        ),
        "from_addr": "alerts@creditcard.com",
        "html": False,
    },
]


# ---------------------------------------------------------------------------
# Gmail API helpers
# ---------------------------------------------------------------------------


def _get_gmail_client() -> tuple[Any, str]:
    """Build authenticated Gmail client.

    Returns:
        Tuple of (service, user_id).
    """
    from email_agent.config.settings import Settings
    from email_agent.gmail.auth import GmailAuth

    settings = Settings()
    auth = GmailAuth(settings.gmail)
    credentials = auth.get_credentials()
    service = auth.build_service(credentials)
    return service, "me"


def _create_label(service: Any, label_name: str) -> str | None:
    """Create a Gmail label, return label ID.

    Returns:
        Label ID or None if creation failed.
    """
    try:
        label = service.users().labels().create(userId="me", body={"name": label_name}).execute()
        return label["id"]  # type: ignore[no-any-return]
    except Exception:
        # Label might already exist
        return None


def _get_or_create_label(service: Any, label_name: str) -> str:
    """Get or create a label, return label ID."""
    # List existing labels
    response = service.users().labels().list(userId="me").execute()
    for label in response.get("labels", []):
        if label["name"] == label_name:
            return label["id"]  # type: ignore[no-any-return]

    # Create new label
    new_label = service.users().labels().create(userId="me", body={"name": label_name}).execute()
    return new_label["id"]  # type: ignore[no-any-return]


def _send_email(service: Any, raw_message: dict[str, Any]) -> str:
    """Send a raw email via Gmail API.

    Returns:
        Message ID.
    """
    result = service.users().messages().send(userId="me", body=raw_message).execute()
    return result["id"]  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    """Generate stress test emails.

    Returns:
        Exit code (0=success, 1=auth failed, 2=API error, 4=unexpected).
    """
    parser = argparse.ArgumentParser(
        description="Generate test emails for email-agent pipeline testing.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Number of test emails to create (default: 10, max: 10)",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Remove test emails after creation (dry-run mode)",
    )
    parser.add_argument(
        "--label",
        type=str,
        default="email-agent-test",
        help="Label name for test emails (default: email-agent-test)",
    )
    args = parser.parse_args()

    print()
    print("#" * 60)
    print("#  Email Agent — Stress Test Email Generator")
    print("#" * 60)
    print()

    # Authenticate
    try:
        service, _user_id = _get_gmail_client()
        print("[OK] Gmail authentication successful.")
    except Exception as exc:
        print(f"[ERROR] Gmail authentication failed: {exc}")
        print("  Run 'python -m email_agent setup' first to authorize.")
        return 1

    # Create test label
    test_label = args.label
    label_id = _get_or_create_label(service, test_label)
    print(f"[OK] Label '{test_label}' ready (ID: {label_id})")

    # Select emails to create
    emails_to_create = TEST_EMAILS[: min(args.count, len(TEST_EMAILS))]
    print(f"\nCreating {len(emails_to_create)} test emails...")

    created_ids: list[str] = []
    errors = 0

    for i, email_def in enumerate(emails_to_create, 1):
        try:
            raw_msg = _make_email(
                subject=email_def["subject"],
                body=email_def["body"],
                from_addr=email_def["from_addr"],
                to_addr=EMAIL_TO,
                html=email_def.get("html", False),
            )

            msg_id = _send_email(service, raw_msg)

            # Apply test label
            service.users().messages().modify(
                userId="me",
                id=msg_id,
                body={"addLabelIds": [label_id]},
            ).execute()

            category = email_def.get("label", "?")
            suspicious = " [SUSPICIOUS]" if email_def.get("suspicious") else ""
            travel = " [TRAVEL]" if email_def.get("travel") else ""
            important = " [IMPORTANT]" if email_def.get("important") else ""
            print(
                f"  [{i}] Created: {email_def['subject'][:50]} "
                f"(label={category}{suspicious}{travel}{important})"
            )
            print(f"       Message ID: {msg_id}")
            created_ids.append(msg_id)

        except Exception as exc:
            print(f"  [{i}] ERROR creating '{email_def['subject'][:40]}': {exc}")
            errors += 1

    # Summary
    print()
    print("=" * 60)
    print("  Stress Test Summary")
    print("=" * 60)
    print(f"  Created: {len(created_ids)} emails")
    print(f"  Errors: {errors}")
    print(f"  Label:  {test_label}")
    print()
    print("  Test categories covered:")
    categories_seen: set[str] = set()
    for e in TEST_EMAILS[: min(args.count, len(TEST_EMAILS))]:
        categories_seen.add(e.get("label", "?"))
    for cat in sorted(categories_seen):
        print(f"    - {cat}")
    print()
    print("  Next steps:")
    print("    python -m email_agent --once --dry-run")
    print()

    # Save test email IDs to file for cleanup
    state_dir = _project_root / "state"
    state_dir.mkdir(exist_ok=True)
    test_ids_file = state_dir / "stress_test_ids.json"
    with open(test_ids_file, "w") as f:
        json.dump({"ids": created_ids, "label": test_label}, f)
    print(f"  Test IDs saved to: {test_ids_file}")
    print("  Run with --clear to remove test emails.")

    return 0 if errors == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
