"""An account's picture, resolved at read: its Plex avatar, else its Gravatar, else none.

Computed rather than stored. Both sources are addresses built from facts the account
already holds — its Plex link's uuid, its e-mail — so the answer follows a link, an
unlink or an e-mail change the moment it happens, with no write to keep in step and no
network call: the browser fetches the picture, the server never does. The ``avatar``
column of ``account`` is not read (B-695: nothing in v1 writes it).

- **Plex**: ``https://plex.tv/users/<uuid>/avatar`` answers without a token — a redirect
  to the user's picture on ``assets.plex.tv`` — so it works for an account whose Plex
  token is not kept, the owner's included.
- **Gravatar**: keyed by the SHA-256 of the trimmed, lower-cased e-mail; the e-mail
  itself never leaves. ``d=404`` makes an e-mail with no Gravatar answer no image, and
  the interface then draws the initial, as it does when a picture fails to load.
"""

from __future__ import annotations

import hashlib
from typing import Final
from urllib.parse import quote

from personalscraper.app.accounts.repository import PlexLinkRow

#: The Gravatar edge asked for, in pixels: the account panel's 42 px avatar on a 3x screen.
GRAVATAR_SIZE: Final[int] = 128

_PLEX_AVATAR: Final[str] = "https://plex.tv/users/{uuid}/avatar"
_GRAVATAR: Final[str] = "https://www.gravatar.com/avatar/{digest}?d=404&s={size}"


def resolve_avatar(link: PlexLinkRow | None, email: str) -> str | None:
    """The address of an account's picture.

    Args:
        link: The account's Plex link, or ``None``.
        email: The account's e-mail.

    Returns:
        Its plex.tv avatar when it has a Plex link; else the Gravatar of its e-mail when
        it has one; else ``None``.
    """
    if link is not None:
        return _PLEX_AVATAR.format(uuid=quote(link.plex_uuid, safe=""))
    normalised = email.strip().lower()
    if not normalised:
        return None
    digest = hashlib.sha256(normalised.encode()).hexdigest()
    return _GRAVATAR.format(digest=digest, size=GRAVATAR_SIZE)
