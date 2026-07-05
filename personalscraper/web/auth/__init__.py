"""Authentication helpers for the TorrentMate web UI (tm-shell feature).

Pure functions — no FastAPI or request dependency.
See docs/features/tm-shell/DESIGN.md §4.4.
"""

from personalscraper.web.auth.passwords import hash_password, verify_password
from personalscraper.web.auth.tokens import create_session_token, decode_session_token

__all__ = [
    "create_session_token",
    "decode_session_token",
    "hash_password",
    "verify_password",
]
