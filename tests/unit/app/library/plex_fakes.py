"""Fakes of the deletion tests: a Plex server that records its calls, and a clock that sleeping advances."""

from __future__ import annotations

from pathlib import Path

from personalscraper.api.plex import PlexSection


class FakePlex:
    """Records every Plex call; scan states are replayed per section."""

    def __init__(
        self,
        sections: dict[str, str],
        *,
        scans: dict[str, list[bool | None]] | None = None,
        refresh_ok: bool = True,
        trash_ok: bool = True,
        bundles_ok: bool = True,
    ) -> None:
        """Name the sections by root and what each call answers.

        Args:
            sections: ``{section root: section key}``.
            scans: Per section key, the scan states read in turn (idle once exhausted).
            refresh_ok: What every partial scan answers.
            trash_ok: What every trash emptying answers.
            bundles_ok: What the bundle clean answers.
        """
        self._sections = sections
        self._scans = scans or {}
        self._refresh_ok = refresh_ok
        self._trash_ok = trash_ok
        self._bundles_ok = bundles_ok
        self.calls: list[tuple[str, str]] = []
        self.extra_locations: dict[str, list[str]] = {}

    def section_for(self, target: Path) -> PlexSection | None:
        """The section whose root prefixes *target*, with its root and its extra locations."""
        for root, key in self._sections.items():
            if str(target) == root or str(target).startswith(f"{root}/"):
                return PlexSection(key, key, [root, *self.extra_locations.get(key, [])])
        return None

    def refresh(self, target: Path) -> bool:
        """Record the partial scan."""
        self.calls.append(("refresh", str(target)))
        return self._refresh_ok

    def section_refreshing(self, section_key: str) -> bool | None:
        """Replay the next scan state (idle once exhausted)."""
        self.calls.append(("scan_state", section_key))
        states = self._scans.get(section_key, [])
        return states.pop(0) if states else False

    def empty_trash(self, section_key: str) -> bool:
        """Record the trash emptying."""
        self.calls.append(("empty_trash", section_key))
        return self._trash_ok

    def clean_bundles(self) -> bool:
        """Record the bundle clean."""
        self.calls.append(("clean_bundles", ""))
        return self._bundles_ok


class FakeTime:
    """A fake monotonic clock that sleeping advances."""

    def __init__(self) -> None:
        """Start at zero, nothing slept."""
        self.now = 0.0
        self.slept: list[float] = []

    def sleep(self, seconds: float) -> None:
        """Advance the clock."""
        self.slept.append(seconds)
        self.now += seconds

    def clock(self) -> float:
        """Read the clock."""
        return self.now
