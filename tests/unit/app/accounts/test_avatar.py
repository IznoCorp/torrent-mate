"""``resolve_avatar``: an account's picture — its Plex avatar, else its Gravatar, else none."""

from __future__ import annotations

import hashlib

from personalscraper.app.accounts.avatar import GRAVATAR_SIZE, resolve_avatar
from personalscraper.app.accounts.model import PlexLink


def _link(plex_uuid: str = "4876c5a138575dce") -> PlexLink:
    """A Plex link with no kept token, as the owner's is today.

    Args:
        plex_uuid: plex.tv's uuid.

    Returns:
        The link.
    """
    return PlexLink(
        account_id="account-1",
        plex_id=1,
        plex_uuid=plex_uuid,
        plex_username="someone",
        server_access="owner",
        token_ciphertext=None,
        token_stored_at=None,
        linked_at=1.0,
        last_sign_in_at=None,
    )


class TestResolveAvatar:
    """The order: Plex, then Gravatar, then none."""

    def test_the_plex_picture_wins_over_the_gravatar(self) -> None:
        """A linked account with an e-mail is shown its plex.tv picture — no token needed."""
        assert resolve_avatar(_link(), "someone@example.org") == "https://plex.tv/users/4876c5a138575dce/avatar"

    def test_the_gravatar_when_there_is_no_plex_link(self) -> None:
        """An account with no link is shown the Gravatar of its e-mail, 404 when it has none."""
        digest = hashlib.sha256(b"someone@example.org").hexdigest()
        assert resolve_avatar(None, "someone@example.org") == (
            f"https://www.gravatar.com/avatar/{digest}?d=404&s={GRAVATAR_SIZE}"
        )

    def test_the_gravatar_hashes_the_trimmed_lower_cased_email(self) -> None:
        """Spaces around and capitals inside change nothing: Gravatar keys the normalised address."""
        digest = hashlib.sha256(b"someone@example.org").hexdigest()
        avatar = resolve_avatar(None, "  SomeOne@Example.ORG \t")
        assert avatar is not None
        assert f"/avatar/{digest}?" in avatar

    def test_the_email_itself_never_leaves(self) -> None:
        """Only the digest goes to Gravatar, never the address."""
        avatar = resolve_avatar(None, "someone@example.org")
        assert avatar is not None
        assert "someone" not in avatar
        assert "example.org" not in avatar

    def test_none_when_neither(self) -> None:
        """No link and no e-mail: no picture, and the interface draws the initial."""
        assert resolve_avatar(None, "   ") is None

    def test_the_plex_uuid_is_quoted_into_the_path(self) -> None:
        """A uuid is plex.tv's; whatever it holds stays one path segment."""
        assert resolve_avatar(_link("a/b c"), "") == "https://plex.tv/users/a%2Fb%20c/avatar"
