#!/usr/bin/env python3
"""Interactive first-run setup wizard for email-agent.

Guides users through:
    1. Gmail OAuth2 credential verification
    2. Gmail OAuth2 authorization flow
    3. Ollama connection and model verification
    4. Initial config.yaml generation
    5. Gmail label creation from config categories

This script is run automatically by `python -m email_agent setup`.
It can also be run standalone: `uv run python scripts/first_run.py`

Exit codes:
    0 = Setup complete
    1 = Setup failed (user can retry)
    2 = OAuth error
    3 = Ollama error
    4 = Unexpected error
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

# Add project root to Python path so we can import email_agent
# This allows the script to be run standalone: uv run python scripts/first_run.py
_project_root = Path(__file__).parent.parent.resolve()
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Add src/ to path for direct email_agent imports
_src_dir = _project_root / "src"
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))


def _print_header(text: str) -> None:
    """Print a section header."""
    print()
    print("=" * 60)
    print(f"  {text}")
    print("=" * 60)


def _print_step(step: int, total: int, text: str) -> None:
    """Print a step indicator."""
    print(f"\n[Step {step}/{total}] {text}")


def _input_default(prompt: str, default: str) -> str:
    """Prompt with a default value."""
    result = input(f"{prompt} [{default}]: ").strip()
    return result if result else default


def _confirm(prompt: str) -> bool:
    """Ask for yes/no confirmation."""
    response = input(f"{prompt} (y/N): ").strip().lower()
    return response in ("y", "yes")


# ---------------------------------------------------------------------------
# Step 1: Gmail Credentials Check
# ---------------------------------------------------------------------------


def _check_gmail_credentials() -> tuple[bool, Path | None]:
    """Check if Gmail credentials.json exists.

    Returns:
        Tuple of (exists, credentials_path).
    """
    default_path = Path("credentials/credentials.json")
    cred_path_str = _input_default(
        "Path to Gmail OAuth credentials JSON file",
        str(default_path),
    )
    cred_path = Path(cred_path_str).resolve()

    if cred_path.exists():
        print(f"  Found: {cred_path}")
        # Validate basic JSON structure
        try:
            with open(cred_path) as f:
                data = json.load(f)
            if "installed" in data or "web" in data:
                print("  Valid credentials file.")
                return True, cred_path
            else:
                print("  ERROR: Invalid credentials format (missing 'installed' or 'web' key).")
                return False, None
        except json.JSONDecodeError as e:
            print(f"  ERROR: Invalid JSON: {e}")
            return False, None
    else:
        print(f"  Not found: {cred_path}")
        return False, None


_GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.labels",
    "https://www.googleapis.com/auth/gmail.compose",
]


def _run_gmail_auth(credentials_path: Path) -> tuple[bool, str]:
    """Run Gmail OAuth2 authorization flow.

    Returns:
        Tuple of (success, message).
    """
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow

        # Define required scopes
        print("\n  Opening browser for Google authorization...")
        print("  If a browser doesn't open, visit the URL shown in the console.")

        # Use installed app flow (opens browser automatically)
        flow = InstalledAppFlow.from_client_secrets_file(
            str(credentials_path),
            _GMAIL_SCOPES,
        )

        # Run local server for callback (will print URL if no browser)
        credentials = flow.run_local_server(port=0, open_browser=True)

        # Save token
        token_path = Path("credentials/token.json")
        token_path.parent.mkdir(parents=True, exist_ok=True)

        with open(token_path, "w") as f:
            f.write(credentials.to_json())

        print(f"\n  Token saved to: {token_path}")
        return True, "Authorization successful!"

    except Exception as e:
        return False, f"Authorization failed: {e}"


# ---------------------------------------------------------------------------
# Step 3: Ollama Verification
# ---------------------------------------------------------------------------


def _verify_ollama() -> tuple[bool, str]:
    """Verify Ollama connection and model availability.

    Returns:
        Tuple of (success, message).
    """
    try:
        import httpx

        print("\n  Checking Ollama connection...")

        # Check Ollama is running
        response = httpx.get("http://localhost:11434/api/tags", timeout=10)
        if response.status_code != 200:
            return False, f"Ollama returned status {response.status_code}"

        models = response.json().get("models", [])
        model_names = [m.get("name", "") for m in models]
        print(f"  Available models: {', '.join(model_names) or 'none'}")

        # Check for llama3.2:1b
        target_model = "llama3.2:1b"
        if any(target_model in name for name in model_names):
            return True, f"Model '{target_model}' is available."

        # Model not found — offer to pull
        print(f"\n  Model '{target_model}' not found.")
        if _confirm(f"  Download '{target_model}' now (requires internet)?"):
            import subprocess

            print(f"\n  Downloading {target_model}... This may take a few minutes.")
            result = subprocess.run(
                ["ollama", "pull", target_model],
                capture_output=False,
            )
            if result.returncode == 0:
                return True, f"Model '{target_model}' downloaded successfully."
            else:
                return False, f"Failed to download model (exit code {result.returncode})"

        return (
            False,
            f"Model '{target_model}' not available. Run 'ollama pull {target_model}' to download.",
        )

    except httpx.ConnectError:
        return False, "Cannot connect to Ollama. Is Ollama running? (Try: ollama serve)"
    except Exception as e:
        return False, f"Ollama check failed: {e}"


# ---------------------------------------------------------------------------
# Step 4: Generate config.yaml
# ---------------------------------------------------------------------------


def _generate_config(gmail_verified: bool) -> tuple[bool, Path]:
    """Generate initial config.yaml.

    Returns:
        Tuple of (success, config_path).
    """
    print("\n  Generating config.yaml...")

    # Get user input for config values
    categories_raw = _input_default(
        "Email categories (comma-separated)",
        "Work, Personal, Finance, Shopping, Travel",
    )
    categories = [c.strip() for c in categories_raw.split(",") if c.strip()]

    important_sender = _input_default(
        "Important sender email (press Enter for none)",
        "",
    )
    important_senders = [important_sender] if important_sender else []

    importance_threshold = _input_default(
        "Importance threshold",
        "medium",
    ).lower()
    if importance_threshold not in ("low", "medium", "high"):
        importance_threshold = "medium"

    # Build config dict
    config = {
        "gmail": {
            "credentials_path": "credentials/credentials.json",
            "token_path": "credentials/token.json",
        },
        "ollama": {
            "base_url": "http://localhost:11434",
            "model": "llama3.2:1b",
            "timeout": 120,
        },
        "agent": {
            "categories": categories,
            "important_senders": important_senders,
            "importance_threshold": importance_threshold,
            "max_emails_per_batch": 50,
            "email_age_limit_days": 7,
            "draft_reply_max_length": 500,
            "polling_interval": 60,
        },
    }

    # Write config.yaml
    config_path = Path("config.yaml")

    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    print(f"  Saved: {config_path}")
    return True, config_path


# ---------------------------------------------------------------------------
# Step 5: Create Gmail Labels
# ---------------------------------------------------------------------------


def _create_gmail_labels(categories: list[str]) -> tuple[bool, str]:
    """Create Gmail labels from config categories.

    Returns:
        Tuple of (success, message).
    """
    if not categories:
        return True, "No categories to create."

    try:
        from email_agent.config.settings import Settings
        from email_agent.gmail.auth import GmailAuth
        from email_agent.gmail.client import GmailClient
        from email_agent.gmail.labels import normalize_label_name

        print("\n  Connecting to Gmail...")

        settings = Settings()
        auth = GmailAuth(settings.gmail)
        credentials = auth.get_credentials()
        service = auth.build_service(credentials)
        client = GmailClient(service)

        print(f"  Creating {len(categories)} labels...")
        for category in categories:
            label_name = normalize_label_name(category)
            try:
                client.create_label(label_name)
                print(f"    Created: {label_name}")
            except Exception as e:
                print(f"    Skipped {label_name}: {e}")

        return True, f"Created {len(categories)} labels."

    except Exception as e:
        return False, f"Label creation skipped: {e}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    """Run the first-run setup wizard.

    Returns:
        Exit code (0=success, 1=setup failed, 2=OAuth error, 3=Ollama error, 4=unexpected).
    """
    print()
    print("#" * 60)
    print("#  Email Agent — First-Run Setup Wizard")
    print("#" * 60)
    print()
    print("This wizard will guide you through setting up email-agent.")
    print("Press Ctrl+C at any time to cancel.")

    total_steps = 5

    # Step 1: Credentials
    _print_step(1, total_steps, "Gmail Credentials")
    gmail_ok, cred_path = _check_gmail_credentials()
    if not gmail_ok:
        print("\n  ERROR: Gmail credentials not found.")
        print("  Please follow the Gmail setup guide first:")
        print("    See docs/gmail-setup.md for instructions.")
        print("  Then run this setup again: python -m email_agent setup")
        return 1

    # Step 2: Authorization
    _print_step(2, total_steps, "Gmail Authorization")
    auth_ok, auth_msg = _run_gmail_auth(cred_path)
    print(f"  {auth_msg}")
    if not auth_ok:
        print("\n  ERROR: Gmail authorization failed.")
        print("  You can retry by running: python -m email_agent setup")
        return 2

    # Step 3: Ollama
    _print_step(3, total_steps, "Ollama Verification")
    ollama_ok, ollama_msg = _verify_ollama()
    print(f"  {ollama_msg}")
    if not ollama_ok:
        print("\n  WARNING: Ollama is not properly configured.")
        print("  You can configure it later and retry the setup.")
        print("  The agent will still work but LLM features will be unavailable.")

    # Step 4: Config
    _print_step(4, total_steps, "Generate config.yaml")
    config_ok, config_path = _generate_config(gmail_ok)
    if not config_ok:
        print(f"\n  ERROR: Failed to generate config: {config_path}")
        return 1

    # Step 5: Labels
    _print_step(5, total_steps, "Create Gmail Labels")

    with open(config_path) as f:
        config_data = yaml.safe_load(f)
    categories = config_data.get("agent", {}).get("categories", [])
    if gmail_ok:
        _labels_ok, labels_msg = _create_gmail_labels(categories)
        print(f"  {labels_msg}")
    else:
        print("  Skipped (Gmail not connected).")

    # Summary
    _print_header("Setup Complete!")
    print("  Next steps:")
    print("  1. Edit config.yaml to customize categories and important senders")
    print("  2. Run: python -m email_agent --once --dry-run  (test run)")
    print("  3. Run: python -m email_agent                  (continuous mode)")
    print()
    print("  Documentation: docs/getting-started.md")
    print("  Usage: python -m email_agent --help")
    print()

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n\nSetup cancelled.")
        raise SystemExit(1) from None
    except Exception as exc:
        print(f"\nUnexpected error: {exc}")
        raise SystemExit(4) from exc
