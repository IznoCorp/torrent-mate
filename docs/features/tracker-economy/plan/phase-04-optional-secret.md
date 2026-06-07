# Phase 4 — Optional-secret resolver + regression test

## Gate

**Requires Phase 3:**
`pytest tests/unit/test_tracker_economy_schema.py` → `11 passed`

---

## Goal

Add `PROVIDER_OPTIONAL_SECRETS` and `resolve_optional_secret()` to `api/_activation.py`, and add regression tests pinning the non-gating invariant: a missing passkey never deactivates a tracker.

## Files

- **Modify:** `personalscraper/api/_activation.py`
- **Modify:** `tests/unit/test_activation.py`

---

## Tasks

### Task 4.1 — Extend `_activation.py`

Open `personalscraper/api/_activation.py`. The file currently ends after `resolve_active()`. Append the following after the last line:

```python
# ---------------------------------------------------------------------------
# Optional secrets (non-gating) — tracker-economy RP2
# ---------------------------------------------------------------------------

PROVIDER_OPTIONAL_SECRETS: dict[str, list[str]] = {
    # Announce passkeys — never consulted by resolve_active(); a missing
    # passkey never deactivates a tracker. Consumers (Vague 5 Ratio C1,
    # Seed-Safety O2) decide what to do with a missing value.
    "lacale": ["LACALE_PASSKEY"],
    "c411": ["C411_PASSKEY"],
}


def resolve_optional_secret(
    provider: str,
    env: Mapping[str, str] = os.environ,
) -> dict[str, str | None]:
    """Resolve a provider's optional, non-activation-gating secrets from the environment.

    Unlike :data:`PROVIDER_CREDS` (consumed by :func:`resolve_active` to gate
    activation), an absent value here returns ``None`` and never deactivates
    the provider nor fails boot.

    Args:
        provider: Provider name (e.g. ``"lacale"``, ``"c411"``).
        env: Secret source (defaults to ``os.environ``; injectable for testing).

    Returns:
        Dict mapping each optional secret name to its value or ``None`` if
        absent. Empty dict for providers not in ``PROVIDER_OPTIONAL_SECRETS``.
    """
    keys = PROVIDER_OPTIONAL_SECRETS.get(provider, [])
    return {k: env.get(k) or None for k in keys}
```

- [ ] Verify:
      `python -c "from personalscraper.api._activation import resolve_optional_secret; print(resolve_optional_secret('c411', env={}))"` → `{'C411_PASSKEY': None}`

---

### Task 4.2 — Add tests to `test_activation.py`

Open `tests/unit/test_activation.py`. The file already imports `resolve_active` and defines `_FakeProvider`. Add the import extension and new test class at the bottom:

- [ ] Extend the existing import at the top of the file:

```python
from personalscraper.api._activation import (
    PROVIDER_CREDS,
    PROVIDER_OPTIONAL_SECRETS,
    resolve_active,
    resolve_optional_secret,
)
```

- [ ] **Append** at end of file:

```python
class TestResolveOptionalSecret:
    """resolve_optional_secret() — tracker-economy RP2."""

    def test_present_returns_value(self) -> None:
        """When the env var is set its value is returned."""
        assert resolve_optional_secret("c411", env={"C411_PASSKEY": "abc"}) == {"C411_PASSKEY": "abc"}

    def test_absent_returns_none(self) -> None:
        """When the env var is absent None is returned (non-gating)."""
        assert resolve_optional_secret("c411", env={}) == {"C411_PASSKEY": None}

    def test_unknown_provider_returns_empty_dict(self) -> None:
        """Provider not in PROVIDER_OPTIONAL_SECRETS → empty dict."""
        assert resolve_optional_secret("tmdb", env={}) == {}

    def test_lacale_passkey_absent(self) -> None:
        """lacale with no passkey → {'LACALE_PASSKEY': None}."""
        assert resolve_optional_secret("lacale", env={}) == {"LACALE_PASSKEY": None}

    def test_resolve_active_unaffected_by_missing_passkey(self) -> None:
        """NON-GATING PROOF: resolve_active() ignores PROVIDER_OPTIONAL_SECRETS.

        An enabled tracker with its API key present must be active even when
        its passkey is absent (DESIGN §Non-Goals, D3).
        """
        env = {"C411_API_KEY": "key_value"}  # passkey intentionally absent
        active = resolve_active({"c411": _FakeProvider(enabled=True)}, "tracker", env=env)
        assert "c411" in active, "c411 must be active without C411_PASSKEY"
        assert resolve_optional_secret("c411", env=env) == {"C411_PASSKEY": None}
```

- [ ] **Run:** `pytest tests/unit/test_activation.py -v` → all existing + 5 new tests pass

---

### Task 4.3 — Commit

```bash
git add personalscraper/api/_activation.py tests/unit/test_activation.py
git commit -m "feat(tracker-economy): PROVIDER_OPTIONAL_SECRETS + resolve_optional_secret (non-gating)"
```

---

## Gate exit checklist

- [ ] `resolve_optional_secret('c411', env={})` → `{'C411_PASSKEY': None}` (exit 0)
- [ ] `pytest tests/unit/test_activation.py` → all tests pass, 0 failed
- [ ] Commit SHA recorded
