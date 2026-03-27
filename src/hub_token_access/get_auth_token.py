"""
Hub OAuth2 client credentials. Token endpoint: POST https://api.hub.perkinswill.com/oauth/token
Body: { "client_id": "...", "grant_type": "client_credentials", "client_secret": "..." }
Response: { "success": true, "value": "<token string>" }

Use get_hub_headers() for Hub file download (replaces HUB_AUTH_COOKIE).
Set HUB_CLIENT_ID and HUB_CLIENT_SECRET in .env.
"""
import requests
from typing import Dict, Optional

# Optional: use "Cookie" to send token as Cookie: authentication=<token> (legacy); "Bearer" for Authorization header
HUB_AUTH_HEADER_STYLE = "Bearer"


class PerkinsAuth:
    def __init__(self, client_id: str, client_secret: str):
        self.base_url = "https://api.hub.perkinswill.com"
        self.client_id = client_id
        self.client_secret = client_secret
        self._access_token = None

    def get_token(self) -> Dict:
        url = f"{self.base_url}/oauth/token"
        payload = {
            "client_id": self.client_id,
            "grant_type": "client_credentials",
            "client_secret": self.client_secret,
        }

        headers = {
            "Content-Type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()

        token_data = response.json()
        # Hub API returns { "success": true, "value": "<token>" } or { "value": { "access_token": "..." } }
        value = token_data.get("value")
        if isinstance(value, str):
            self._access_token = value
        elif isinstance(value, dict):
            self._access_token = value.get("access_token") or value.get("accessToken")
        else:
            self._access_token = (
                token_data.get("access_token")
                or token_data.get("accessToken")
            )
        return token_data

    @property
    def access_token(self):
        return self._access_token


def get_hub_access_token() -> Optional[str]:
    """Get Hub OAuth2 access token using HUB_CLIENT_ID and HUB_CLIENT_SECRET from config."""
    try:
        from src.config import HUB_CLIENT_ID, HUB_CLIENT_SECRET
    except ImportError:
        return None
    if not HUB_CLIENT_ID or not HUB_CLIENT_SECRET:
        return None
    try:
        auth = PerkinsAuth(HUB_CLIENT_ID, HUB_CLIENT_SECRET)
        auth.get_token()
        return auth.access_token
    except Exception:
        return None


def get_hub_headers() -> Dict[str, str]:
    """
    Return headers dict for Hub file download (files.hub.perkinswill.com).
    Uses OAuth2 token from HUB_CLIENT_ID / HUB_CLIENT_SECRET. Falls back to HUB_AUTH_COOKIE if set and no token.
    """
    import os
    token = get_hub_access_token()
    if token:
        style = os.getenv("HUB_AUTH_HEADER_STYLE", "Bearer").strip().lower()
        if style == "cookie":
            return {"Cookie": f"authentication={token}"}
        return {"Authorization": f"Bearer {token}"}
    try:
        from src.config import HUB_AUTH_COOKIE
        cookie = HUB_AUTH_COOKIE or ""
    except ImportError:
        cookie = os.getenv("HUB_AUTH_COOKIE", "")
    if cookie and "=" in cookie:
        return {"Cookie": cookie.strip()}
    if cookie:
        return {"Cookie": f"authentication={cookie.strip()}"}
    return {}
