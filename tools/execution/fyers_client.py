"""
tools/execution/fyers_client.py — Fyers API client initialisation and authentication.

Wraps the fyers-apiv3 Python SDK and handles:
- Initialising FyersModel with App ID and daily Access Token
- Optional automated token refresh via TOTP + PIN
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    from fyers_apiv3 import fyersModel
    _FYERS_AVAILABLE = True
except ImportError:
    _FYERS_AVAILABLE = False
    fyersModel = None


def is_fyers_available() -> bool:
    """Return True if fyers-apiv3 is installed."""
    return _FYERS_AVAILABLE


def get_fyers_client() -> Any:
    """Return an authenticated FyersModel client using credentials from settings.

    Returns:
        fyersModel.FyersModel instance or None if not configured/available.
    """
    if not _FYERS_AVAILABLE:
        logger.error("fyers-apiv3 is not installed. Install with: pip install fyers-apiv3")
        return None

    from config.settings import get_settings
    s = get_settings()

    client_id = s.fyers_client_id or os.environ.get("FYERS_CLIENT_ID", "")
    access_token = s.fyers_access_token or os.environ.get("FYERS_ACCESS_TOKEN", "")

    if not client_id or not access_token:
        # Check if auto-login is configured with TOTP
        if s.fyers_pin and s.fyers_totp_key and s.fyers_secret_key:
            logger.info("Attempting automated Fyers login via TOTP...")
            token = refresh_fyers_access_token()
            if token:
                access_token = token
                s.fyers_access_token = token

        if not client_id or not access_token:
            logger.warning(
                "Fyers credentials missing. Set FYERS_CLIENT_ID and FYERS_ACCESS_TOKEN in .env or Settings."
            )
            return None

    try:
        client = fyersModel.FyersModel(
            client_id=client_id,
            token=access_token,
            is_async=False,
            log_path="",
        )
        return client
    except Exception as exc:
        logger.error("Failed to initialise FyersModel: %s", exc)
        return None


def refresh_fyers_access_token() -> Optional[str]:
    """Automate Fyers access token generation using TOTP and PIN if configured."""
    try:
        import pyotp
        import requests
        from config.settings import get_settings

        s = get_settings()
        client_id = s.fyers_client_id or os.environ.get("FYERS_CLIENT_ID", "")
        secret_key = s.fyers_secret_key or os.environ.get("FYERS_SECRET_KEY", "")
        pin = s.fyers_pin or os.environ.get("FYERS_PIN", "")
        totp_key = s.fyers_totp_key or os.environ.get("FYERS_TOTP_KEY", "")

        if not (client_id and secret_key and pin and totp_key):
            logger.debug("Automated TOTP login prerequisites not fully provided.")
            return None

        # Generate 6-digit TOTP
        totp = pyotp.TOTP(totp_key).now()

        # Fyers OAuth flow with TOTP
        # Note: Fyers API v3 OAuth endpoints
        fy_id = client_id.split("-")[0] if "-" in client_id else client_id
        app_id = client_id.split("-")[1] if "-" in client_id else "100"

        # Request key
        otp_url = "https://api-t1.fyers.in/api/v3/send_login_otp_v3"
        resp = requests.post(otp_url, json={"fy_id": fy_id, "app_id": app_id}, timeout=10)
        otp_data = resp.json()

        if otp_data.get("s") != "ok":
            logger.warning("Fyers send_login_otp_v3 failed: %s", otp_data)
            return None

        request_key = otp_data.get("request_key")

        # Verify OTP
        verify_otp_url = "https://api-t1.fyers.in/api/v3/verify_otp"
        resp = requests.post(verify_otp_url, json={"request_key": request_key, "otp": totp}, timeout=10)
        verify_data = resp.json()

        if verify_data.get("s") != "ok":
            logger.warning("Fyers verify_otp failed: %s", verify_data)
            return None

        request_key_2 = verify_data.get("request_key")

        # Verify PIN
        verify_pin_url = "https://api-t1.fyers.in/api/v3/verify_pin_v2"
        resp = requests.post(
            verify_pin_url,
            json={"request_key": request_key_2, "identity_type": "pin", "identifier": pin},
            timeout=10,
        )
        pin_data = resp.json()

        if pin_data.get("s") != "ok":
            logger.warning("Fyers verify_pin_v2 failed: %s", pin_data)
            return None

        access_token = pin_data.get("data", {}).get("access_token")
        if access_token:
            logger.info("Successfully refreshed Fyers access token via TOTP!")
            return access_token

    except Exception as exc:
        logger.warning("Automated Fyers TOTP login failed: %s", exc)

    return None
