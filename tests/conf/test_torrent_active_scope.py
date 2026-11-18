"""``TorrentConfig.active_scope`` resolves the scope of the active client only."""

from pathlib import Path

from personalscraper.conf.models.api_config import TorrentClientEntry, TorrentConfig, TorrentScope

_SCOPE = TorrentScope(category="tm-preprod", download_root=Path("/srv/preprod"))


def test_active_client_with_scope_returns_the_scope() -> None:
    """The active client's scope is returned, not another client's."""
    cfg = TorrentConfig(
        active="qbit",
        clients={"qbit": TorrentClientEntry(scope=_SCOPE), "other": TorrentClientEntry()},
    )
    assert cfg.active_scope() == _SCOPE


def test_active_client_without_scope_returns_none() -> None:
    """No scope configured means the whole client, as today."""
    cfg = TorrentConfig(active="qbit", clients={"qbit": TorrentClientEntry()})
    assert cfg.active_scope() is None


def test_active_naming_no_entry_returns_none() -> None:
    """An ``active`` that names no configured client yields no scope."""
    cfg = TorrentConfig(active="ghost", clients={"qbit": TorrentClientEntry(scope=_SCOPE)})
    assert cfg.active_scope() is None
    assert TorrentConfig().active_scope() is None
