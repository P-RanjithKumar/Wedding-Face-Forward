"""
Private per-guest gallery keys (shared by the guest web server and the
desktop app's "Share Links" window).

A key is an HMAC-SHA256 of the person ID with a random per-install secret
stored next to the database (gallery_secret.key). Anyone with the key can
see that one guest's photos and nothing else. Deleting the secret file
invalidates every key.
"""

import base64
import hashlib
import hmac
import secrets
import threading
from typing import Optional

from .config import get_config

_secret: Optional[bytes] = None
_lock = threading.Lock()


def _get_secret() -> bytes:
    global _secret
    with _lock:
        if _secret is None:
            key_path = get_config().db_path.parent / "gallery_secret.key"
            if key_path.exists():
                _secret = bytes.fromhex(key_path.read_text(encoding="utf-8").strip())
            else:
                key_path.parent.mkdir(parents=True, exist_ok=True)
                _secret = secrets.token_bytes(32)
                key_path.write_text(_secret.hex(), encoding="utf-8")
        return _secret


def make_gallery_token(person_id: int) -> str:
    digest = hmac.new(_get_secret(), f"gallery:{person_id}".encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def token_is_valid(person_id: int, token: str) -> bool:
    return bool(token) and hmac.compare_digest(token, make_gallery_token(person_id))


def gallery_link(base_url: str, person_id: int) -> str:
    """Direct link that opens this guest's gallery on the guest page."""
    return f"{base_url.rstrip('/')}/?g={person_id}&k={make_gallery_token(person_id)}"
