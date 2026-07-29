import json
import os
import threading
from pathlib import Path
from typing import Callable

import msal
import requests


AUTHORITY = "https://login.microsoftonline.com/consumers"
SCOPES = ["XboxLive.signin"]

TOKEN_FOLDER = Path(".tokens")
TOKEN_CACHE_FILE = TOKEN_FOLDER / "microsoft_cache.json"


class XboxAuthenticationError(Exception):
    """Raised when Microsoft or Xbox authentication fails."""


class XboxAuthenticator:
    def __init__(self, client_id: str) -> None:
        if not client_id:
            raise ValueError("MICROSOFT_CLIENT_ID is missing.")

        self.client_id = client_id
        self._lock = threading.Lock()

        TOKEN_FOLDER.mkdir(parents=True, exist_ok=True)

        self.cache = msal.SerializableTokenCache()
        self._load_cache()

        self.app = msal.PublicClientApplication(
            client_id=self.client_id,
            authority=AUTHORITY,
            token_cache=self.cache,
        )

    def _load_cache(self) -> None:
        if not TOKEN_CACHE_FILE.exists():
            return

        try:
            cache_text = TOKEN_CACHE_FILE.read_text(encoding="utf-8")
            self.cache.deserialize(cache_text)
        except (OSError, ValueError):
            print("Warning: Existing Microsoft token cache could not be read.")

    def _save_cache(self) -> None:
        if not self.cache.has_state_changed:
            return

        TOKEN_CACHE_FILE.write_text(
            self.cache.serialize(),
            encoding="utf-8",
        )

    def _get_microsoft_token_silently(self) -> str | None:
        accounts = self.app.get_accounts()

        if not accounts:
            return None

        result = self.app.acquire_token_silent(
            scopes=SCOPES,
            account=accounts[0],
        )

        self._save_cache()

        if result and "access_token" in result:
            return result["access_token"]

        return None

    def login(
        self,
        device_message_callback: Callable[[str], None] | None = None,
    ) -> dict[str, str]:
        """
        Authenticate with Microsoft and Xbox.

        If a cached Microsoft token is available, it will be used.
        Otherwise, device-code login will begin.
        """

        with self._lock:
            microsoft_token = self._get_microsoft_token_silently()

            if not microsoft_token:
                flow = self.app.initiate_device_flow(scopes=SCOPES)

                if "user_code" not in flow:
                    raise XboxAuthenticationError(
                        "Microsoft device login could not be started."
                    )

                message = flow.get(
                    "message",
                    "Open microsoft.com/devicelogin and enter the code shown.",
                )

                if device_message_callback:
                    device_message_callback(message)
                else:
                    print(message)

                result = self.app.acquire_token_by_device_flow(flow)
                self._save_cache()

                if "access_token" not in result:
                    error = result.get("error", "Unknown error")
                    description = result.get(
                        "error_description",
                        "No error description was returned.",
                    )

                    raise XboxAuthenticationError(
                        f"Microsoft login failed: {error}: {description}"
                    )

                microsoft_token = result["access_token"]

            xbox_user_token = self._get_xbox_user_token(microsoft_token)
            return self._get_xsts_token(xbox_user_token)

    def _get_xbox_user_token(self, microsoft_token: str) -> str:
        url = "https://user.auth.xboxlive.com/user/authenticate"

        headers = {
            "Content-Type": "application/json",
            "x-xbl-contract-version": "1",
        }

        payload = {
            "RelyingParty": "http://auth.xboxlive.com",
            "TokenType": "JWT",
            "Properties": {
                "AuthMethod": "RPS",
                "SiteName": "user.auth.xboxlive.com",
                "RpsTicket": f"d={microsoft_token}",
            },
        }

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30,
        )

        if not response.ok:
            raise XboxAuthenticationError(
                "Xbox User Token request failed "
                f"with status {response.status_code}."
            )

        token = response.json().get("Token")

        if not token:
            raise XboxAuthenticationError(
                "Xbox did not return a User Token."
            )

        return token

    def _get_xsts_token(self, xbox_user_token: str) -> dict[str, str]:
        url = "https://xsts.auth.xboxlive.com/xsts/authorize"

        headers = {
            "Content-Type": "application/json",
            "x-xbl-contract-version": "1",
        }

        payload = {
            "Properties": {
                "SandboxId": "RETAIL",
                "UserTokens": [xbox_user_token],
            },
            "RelyingParty": "http://xboxlive.com",
            "TokenType": "JWT",
        }

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30,
        )

        if not response.ok:
            error_message = self._describe_xsts_error(response)
            raise XboxAuthenticationError(error_message)

        data = response.json()
        claims = data.get("DisplayClaims", {}).get("xui", [])

        if not claims:
            raise XboxAuthenticationError(
                "Xbox account claims were not returned."
            )

        user = claims[0]

        xbox_data = {
            "token": data.get("Token", ""),
            "user_hash": user.get("uhs", ""),
            "xuid": user.get("xid", ""),
            "gamertag": user.get("gtg", ""),
        }

        if not xbox_data["token"]:
            raise XboxAuthenticationError("XSTS token was not returned.")

        if not xbox_data["user_hash"]:
            raise XboxAuthenticationError("Xbox user hash was not returned.")

        if not xbox_data["xuid"]:
            raise XboxAuthenticationError("Xbox XUID was not returned.")

        return xbox_data

    @staticmethod
    def _describe_xsts_error(response: requests.Response) -> str:
        try:
            data = response.json()
        except ValueError:
            return (
                "Xbox XSTS authentication failed "
                f"with status {response.status_code}."
            )

        xerr = str(data.get("XErr", ""))

        known_errors = {
            "2148916233": (
                "This Microsoft account does not have an Xbox profile."
            ),
            "2148916235": (
                "Xbox Live is not available in this account's region."
            ),
            "2148916236": (
                "This Xbox account requires adult verification."
            ),
            "2148916237": (
                "This Xbox account requires adult verification."
            ),
            "2148916238": (
                "This is a child account and family permission is required."
            ),
        }

        return known_errors.get(
            xerr,
            (
                "Xbox XSTS authentication failed "
                f"with status {response.status_code}. XErr: {xerr or 'Unknown'}"
            ),
        )

    def logout(self) -> None:
        self.cache = msal.SerializableTokenCache()

        if TOKEN_CACHE_FILE.exists():
            TOKEN_CACHE_FILE.unlink()