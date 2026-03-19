"""Gmail OAuth2 authentication module.

Handles the OAuth2 flow for Gmail API access using the Google Auth
library. Supports token refresh and credential persistence.

Scopes:
    - https://www.googleapis.com/auth/gmail.readonly
    - https://www.googleapis.com/auth/gmail.labels
    - https://www.googleapis.com/auth/gmail.compose

See PLAN.md §8 for Gmail API integration details.
"""

from __future__ import annotations

from typing import cast

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from email_agent.config.settings import GmailSettings
from email_agent.exceptions.base import GmailAuthError

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.labels",
    "https://www.googleapis.com/auth/gmail.compose",
]


class GmailAuth:
    """OAuth2 authentication handler for Gmail API.

    Manages credential lifecycle: initial flow, token refresh,
    and persistent storage.

    Args:
        settings: Gmail configuration settings containing credentials_path
            and token_path.

    Example:
        auth = GmailAuth(settings)
        credentials = auth.get_credentials()
        service = auth.build_service(credentials)
    """

    def __init__(self, settings: GmailSettings) -> None:
        self._settings = settings
        self._credentials: Credentials | None = None

    def get_credentials(self) -> Credentials:
        """Run OAuth2 flow and return valid credentials.

        If a valid token exists on disk, load and refresh it.
        Otherwise, launch the local server OAuth2 flow.

        Returns:
            Valid OAuth2 credentials with refresh token.

        Raises:
            GmailAuthError: If authentication fails at any step.
        """
        creds = self._load_token()

        if creds and creds.valid:
            return creds

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                self._save_token(creds)
                return creds
            except Exception as exc:
                raise GmailAuthError(
                    "Token refresh failed; re-run setup to re-authenticate."
                ) from exc

        return self._run_oauth_flow()

    def _load_token(self) -> Credentials | None:
        """Load credentials from token file if it exists."""
        token_path = self._settings.token_path
        if not token_path.exists():
            return None
        try:
            creds: Credentials | None = Credentials.from_authorized_user_file(str(token_path))  # type: ignore[no-untyped-call]
            if creds is None:
                msg = f"Token file at {token_path} is invalid (returned None)"
                raise GmailAuthError(msg)
            return creds
        except GmailAuthError:
            raise
        except Exception as exc:
            raise GmailAuthError(f"Failed to load token from {token_path}: {exc}") from exc

    def _save_token(self, creds: Credentials) -> None:
        """Persist credentials to token file."""
        token_path = self._settings.token_path
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json())  # type: ignore[no-untyped-call]

    def _run_oauth_flow(self) -> Credentials:
        """Launch local server OAuth2 flow.

        Opens browser for user authorization.

        Returns:
            Credentials after successful authorization.

        Raises:
            GmailAuthError: If flow fails or credentials not obtained.
        """
        creds_path = self._settings.credentials_path
        if not creds_path.exists():
            raise GmailAuthError(
                f"Credentials file not found at {creds_path}. "
                "Run 'python -m email_agent setup' to configure."
            )

        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(creds_path),
                scopes=GMAIL_SCOPES,
            )
            creds = flow.run_local_server(port=0)
            self._save_token(creds)
            return cast(Credentials, creds)
        except Exception as exc:
            raise GmailAuthError(f"OAuth2 flow failed: {exc}") from exc

    def build_service(
        self,
        credentials: Credentials,
    ) -> object:
        """Build the Gmail API service object.

        Args:
            credentials: Valid OAuth2 credentials.

        Returns:
            Gmail API service object.
        """
        return build("gmail", "v1", credentials=credentials, cache_discovery=False)
