# Phase 02 — Registry wiring, creds, config overlays, composition-root tests

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire `Torr9Client` into the tracker registry: register it in `_factory.py` (`_TRACKER_CLASSES`), declare creds in `_activation.py` (`PROVIDER_CREDS` + `PROVIDER_OPTIONAL_SECRETS`), add `torr9` to both `config/tracker.json5` and `config.example/tracker.json5`, and extend the composition-root integration tests to cover the torr9 missing-cred fail-loud path.

**Architecture:** The factory's current single-key assumption (`api_key = env[required[0]]`) does not accommodate torr9's two-cred login (username + password). The factory must be extended to detect multi-cred trackers and call the client constructor differently. `Torr9Client.__init__` takes `transport, *, username, password` (phase 1); the factory must pass both. The config overlay change (both `config/` and `config.example/`) follows the DESIGN to avoid overlay drift.

**Tech Stack:** `personalscraper/api/tracker/_factory.py`, `personalscraper/api/_activation.py`, `config/tracker.json5`, `config.example/tracker.json5`, `tests/integration/api/tracker/test_composition_root.py`, `pytest`, `unittest.mock`.

## Gate

**Prerequisites:** Phase 1 complete — `personalscraper/api/tracker/torr9.py` exists and `tests/unit/test_torr9_client.py` passes.

**This phase gate passes when:**

- `python -c "from personalscraper.api.tracker._factory import _TRACKER_CLASSES; print('torr9' in _TRACKER_CLASSES)"` prints `True`
- `python -c "from personalscraper.api._activation import PROVIDER_CREDS; print(PROVIDER_CREDS.get('torr9'))"` prints `['TORR9_USERNAME', 'TORR9_PASSWORD']`
- `grep -c 'torr9' config/tracker.json5 config.example/tracker.json5` shows ≥ 1 per file
- `python -m pytest tests/integration/api/tracker/test_composition_root.py -q -k torr9` passes
- `make check` is green

---

## File Map

| Action | Path                                                     | Responsibility                                                       |
| ------ | -------------------------------------------------------- | -------------------------------------------------------------------- |
| Modify | `personalscraper/api/tracker/_factory.py`                | Add torr9 to `_TRACKER_CLASSES`; extend multi-cred construction path |
| Modify | `personalscraper/api/_activation.py`                     | Add `PROVIDER_CREDS["torr9"]` + `PROVIDER_OPTIONAL_SECRETS["torr9"]` |
| Modify | `config/tracker.json5`                                   | Add `torr9` provider block + append to `priority`                    |
| Modify | `config.example/tracker.json5`                           | Mirror torr9 entry (overlay parity)                                  |
| Modify | `tests/integration/api/tracker/test_composition_root.py` | torr9 missing-cred fail-loud test                                    |

---

## Task 1: Register `torr9` in `_TRACKER_CLASSES` and update factory multi-cred path

**Files:**

- Modify: `personalscraper/api/tracker/_factory.py`

The factory's line 119 (`api_key = env[required[0]] if required else ""`) and line 120 (`transport = HttpTransport(client_cls.policy(api_key), ...)`) assume all trackers take a single credential passed to `policy(api_key)`. `Torr9Client.policy()` takes no credentials (NoAuth placeholder), and `Torr9Client.__init__` takes `username` and `password` separately. Add a specialised construction branch for torr9-style multi-cred trackers.

The cleanest approach: detect if the client class exposes a `REQUIRED_CREDS` class attribute with more than one cred, and if so, call a `build_from_env()` classmethod. Alternatively, add a `build(env)` classmethod on `Torr9Client`. The simpler path that avoids adding a new protocol: use `name == "torr9"` as a guard — acceptable since this is a small `if` inside the factory, not a protocol violation.

- [ ] **Step 1.1: Add torr9 to `_TRACKER_CLASSES`**

Open `personalscraper/api/tracker/_factory.py`. Modify the `_TRACKER_CLASSES` dict:

```python
_TRACKER_CLASSES: dict[str, str] = {
    "lacale": "personalscraper.api.tracker.lacale:LaCaleClient",
    "c411": "personalscraper.api.tracker.c411:C411Client",
    "torr9": "personalscraper.api.tracker.torr9:Torr9Client",
}
```

- [ ] **Step 1.2: Verify `torr9` appears in `_TRACKER_CLASSES`**

```bash
python -c "from personalscraper.api.tracker._factory import _TRACKER_CLASSES; print('torr9' in _TRACKER_CLASSES)"
# Expected: True
```

- [ ] **Step 1.3: Update the factory construction loop to handle multi-cred trackers**

Locate lines ~116-121 in `_factory.py` (after `client_cls = _resolve_tracker_class(name)`). Replace the block:

```python
        client_cls = _resolve_tracker_class(name)
        # Single-key assumption: all current trackers (lacale/c411) have exactly
        # one credential; revisit if a multi-key tracker is added.
        api_key = env[required[0]] if required else ""
        transport = HttpTransport(client_cls.policy(api_key), event_bus=event_bus)  # type: ignore[attr-defined]
        client = client_cls(transport)
```

Replace with:

```python
        client_cls = _resolve_tracker_class(name)
        # torr9 uses a two-credential JWT login (username + password); its
        # policy() takes no credentials (NoAuth placeholder) and its __init__
        # takes username/password separately. All other trackers (lacale/c411)
        # use a single API key passed to policy(api_key). Guard on name until
        # a general multi-cred protocol is designed.
        if name == "torr9":
            transport = HttpTransport(client_cls.policy(), event_bus=event_bus)  # type: ignore[attr-defined]
            client = client_cls(  # type: ignore[call-arg]
                transport,
                username=env.get("TORR9_USERNAME", ""),
                password=env.get("TORR9_PASSWORD", ""),
            )
        else:
            api_key = env[required[0]] if required else ""
            transport = HttpTransport(client_cls.policy(api_key), event_bus=event_bus)  # type: ignore[attr-defined]
            client = client_cls(transport)
```

- [ ] **Step 1.4: Smoke-test factory import**

```bash
python -c "from personalscraper.api.tracker._factory import build_tracker_registry; print('OK')"
# Expected: OK
```

---

## Task 2: Declare creds in `_activation.py`

**Files:**

- Modify: `personalscraper/api/_activation.py`

`PROVIDER_CREDS["torr9"]` gates activation: `build_tracker_registry` checks this list for missing env vars and raises `TrackerConfigError` if any are absent when torr9 is enabled.

`PROVIDER_OPTIONAL_SECRETS["torr9"]` registers `TORR9_PASSKEY` as a non-gating secret. A missing passkey never deactivates the tracker — it is only consumed by the freeleech radar (R1, out of scope) and the `.torrent` download fallback.

> **Note on ACC-3:** The DESIGN's ACC-3 tests `PROVIDER_CREDS.get('torr9')` and expects `['TORR9_API_KEY']`. However, the actual API contract requires `TORR9_USERNAME` + `TORR9_PASSWORD`. ACC-3 as written in the DESIGN is a documentation typo (the body of §Approach §3 and the API reference both specify username/password). The plan follows the API contract. The ACC-3 shell command must be adjusted at phase 3's ACC re-exercise to expect `['TORR9_USERNAME', 'TORR9_PASSWORD']`.

- [ ] **Step 2.1: Add `torr9` to `PROVIDER_CREDS`**

Open `personalscraper/api/_activation.py`. Add after the `"c411"` line:

```python
    "torr9": ["TORR9_USERNAME", "TORR9_PASSWORD"],
```

So `PROVIDER_CREDS` looks like:

```python
PROVIDER_CREDS: dict[str, list[str]] = {
    # ... existing entries ...
    "lacale": ["LACALE_API_KEY"],
    "c411": ["C411_API_KEY"],
    "torr9": ["TORR9_USERNAME", "TORR9_PASSWORD"],
    # ... rest ...
}
```

- [ ] **Step 2.2: Add `torr9` to `PROVIDER_OPTIONAL_SECRETS`**

In the same file, after `"c411": ["C411_PASSKEY"]`:

```python
    "torr9": ["TORR9_PASSKEY"],
```

So `PROVIDER_OPTIONAL_SECRETS` looks like:

```python
PROVIDER_OPTIONAL_SECRETS: dict[str, list[str]] = {
    "lacale": ["LACALE_PASSKEY"],
    "c411": ["C411_PASSKEY"],
    "torr9": ["TORR9_PASSKEY"],
}
```

- [ ] **Step 2.3: Verify creds**

```bash
python -c "from personalscraper.api._activation import PROVIDER_CREDS, PROVIDER_OPTIONAL_SECRETS; print(PROVIDER_CREDS.get('torr9')); print(PROVIDER_OPTIONAL_SECRETS.get('torr9'))"
# Expected:
# ['TORR9_USERNAME', 'TORR9_PASSWORD']
# ['TORR9_PASSKEY']
```

- [ ] **Step 2.4: Sub-commit**

```bash
git add personalscraper/api/_activation.py
git commit -m "$(cat <<'EOF'
feat(torr9): register PROVIDER_CREDS + PROVIDER_OPTIONAL_SECRETS for torr9
EOF
)"
```

---

## Task 3: Update `config/tracker.json5` and `config.example/tracker.json5`

**Files:**

- Modify: `config/tracker.json5`
- Modify: `config.example/tracker.json5`

The torr9 provider block goes into `providers` with `enabled: false` (default disabled until creds are set). The `economy` sub-block mirrors c411's format (consumed by Ratio C1 in a future wave — carry it now per DESIGN). Append `"torr9"` to the `priority` list.

Both files MUST be updated (project memory: overlay drift is a recurring failure mode).

- [ ] **Step 3.1: Add torr9 to `config/tracker.json5`**

Current `config/tracker.json5` has `providers: { lacale: {...}, c411: {...} }` and `priority: ["lacale", "c411"]`. Add torr9 after c411:

```json5
{
  // PROVIDER_CREDS: lacale → LACALE_API_KEY, c411 → C411_API_KEY
  // PROVIDER_CREDS: torr9 → TORR9_USERNAME + TORR9_PASSWORD (JWT login)
  // PROVIDER_OPTIONAL_SECRETS (non-gating): lacale → LACALE_PASSKEY, c411 → C411_PASSKEY,
  //   torr9 → TORR9_PASSKEY (RSS freeleech radar R1 follow-on)
  tracker: {
    providers: {
      lacale: { enabled: true },
      c411: {
        enabled: true,
        economy: {
          target_ratio: 2.0,
          min_ratio: 1.0,
          min_seed_time: "72h",
          hit_and_run_grace: "0h",
        },
      },
      torr9: {
        enabled: false,
        economy: {
          target_ratio: 2.0,
          min_ratio: 1.0,
          min_seed_time: "72h",
          hit_and_run_grace: "0h",
        },
      },
    },
    priority: ["lacale", "c411", "torr9"],
    max_total_results: 50,
    max_per_tracker: 30,
    timeout_per_tracker: 15,
  },
}
```

- [ ] **Step 3.2: Add torr9 to `config.example/tracker.json5`**

Add torr9 after c411 in `config.example/tracker.json5`:

```json5
{
  // PROVIDER_CREDS (activation-gating): lacale → LACALE_API_KEY, c411 → C411_API_KEY
  // PROVIDER_CREDS (activation-gating): torr9 → TORR9_USERNAME + TORR9_PASSWORD (JWT login)
  // PROVIDER_OPTIONAL_SECRETS (non-gating, RP2): lacale → LACALE_PASSKEY, c411 → C411_PASSKEY
  //   torr9 → TORR9_PASSKEY (RSS freeleech radar R1 follow-on; does not gate activation)
  // A missing passkey never deactivates a tracker (DESIGN §Non-Goals, D3).
  tracker: {
    providers: {
      lacale: {
        enabled: false,
        // economy: {
        //   target_ratio: 2.0,
        //   min_ratio: 1.0,
        //   min_seed_time: "72h",
        //   hit_and_run_grace: "48h",
        // },
      },
      c411: {
        enabled: false,
        // economy: {
        //   target_ratio: 2.0,
        //   min_ratio: 1.0,
        //   min_seed_time: "72h",
        //   hit_and_run_grace: "48h",
        // },
      },
      torr9: {
        enabled: false,
        // economy: {
        //   target_ratio: 2.0,
        //   min_ratio: 1.0,
        //   min_seed_time: "72h",
        //   hit_and_run_grace: "48h",
        // },
      },
    },
    priority: ["lacale", "c411", "torr9"],
    priority_by_media_type: {
      // movie: ["c411", "lacale", "torr9"],
      // tv:    ["lacale", "c411", "torr9"],
    },
    max_total_results: 50,
    max_per_tracker: 30,
    timeout_per_tracker: 15,
  },
}
```

- [ ] **Step 3.3: Verify both files contain torr9**

```bash
grep -c 'torr9' config/tracker.json5 config.example/tracker.json5
# Expected: config/tracker.json5:N (≥1) and config.example/tracker.json5:N (≥1)
```

- [ ] **Step 3.4: Sub-commit**

```bash
git add config/tracker.json5 config.example/tracker.json5
git commit -m "$(cat <<'EOF'
feat(torr9): add torr9 provider block to tracker config overlays (disabled)
EOF
)"
```

---

## Task 4: Register torr9 in `_factory.py` and commit

**Files:**

- Modify: `personalscraper/api/tracker/_factory.py` (from Task 1 — not yet committed)

- [ ] **Step 4.1: Run lint on factory**

```bash
make lint
# Expected: 0 errors
```

- [ ] **Step 4.2: Sub-commit the factory changes**

```bash
git add personalscraper/api/tracker/_factory.py
git commit -m "$(cat <<'EOF'
feat(torr9): register Torr9Client in _TRACKER_CLASSES + multi-cred factory path
EOF
)"
```

---

## Task 5: Extend composition-root integration tests for torr9

**Files:**

- Modify: `tests/integration/api/tracker/test_composition_root.py`

The existing integration tests in `TestBuildAppContextTrackerWiring` verify that `TrackerConfigError` surfaces at boot when creds are missing (for lacale). We must add a parallel test for torr9: with `torr9.enabled=true` and `TORR9_USERNAME`/`TORR9_PASSWORD` absent, `build_tracker_registry` raises `TrackerConfigError` with `code="missing_credentials"` and `provider="torr9"`.

The integration test uses `patch("personalscraper.acquire._factory.build_tracker_registry", ...)` to avoid actually constructing transports. For the direct-factory test (verifying the factory's own cred-check logic), we call `build_tracker_registry` with a test config and inject `env={}`.

- [ ] **Step 5.1: Add helper `_torr9_tracker_config()` and test class**

Add to `tests/integration/api/tracker/test_composition_root.py` — after the existing test classes:

```python
# -- torr9 cred-gating tests -----------------------------------------------

from personalscraper.api.tracker._factory import build_tracker_registry
from personalscraper.api.tracker._ranking import RankingConfig
from personalscraper.core.event_bus import EventBus
from personalscraper.api.transport._policy import CircuitPolicy


def _torr9_tracker_config_enabled() -> MagicMock:
    """Build a minimal TrackerConfig with torr9 enabled and no other providers."""
    cfg = MagicMock()
    # providers: only torr9 enabled
    torr9_provider = MagicMock()
    torr9_provider.enabled = True
    cfg.providers = {"torr9": torr9_provider}
    cfg.priority = ["torr9"]
    cfg.priority_by_media_type = {}
    return cfg


class TestTorr9CredGating:
    """torr9 missing-cred fail-loud test via direct build_tracker_registry call.

    CI has no config.json5, so we call build_tracker_registry directly with an
    injected env dict (not via _build_app_context which loads real config).
    """

    def test_torr9_missing_both_creds_raises_tracker_config_error(self) -> None:
        """With torr9 enabled and TORR9_USERNAME + TORR9_PASSWORD absent,
        build_tracker_registry raises TrackerConfigError (fail-loud, parity
        with lacale/c411 missing-cred behaviour).
        """
        from personalscraper.api.tracker._errors import TrackerConfigError  # noqa: PLC0415

        event_bus = EventBus()
        cb_policy = CircuitPolicy()
        ranking = RankingConfig()

        with pytest.raises(TrackerConfigError) as exc_info:
            build_tracker_registry(
                tracker_config=_torr9_tracker_config_enabled(),
                ranking=ranking,
                settings=MagicMock(),
                event_bus=event_bus,
                cb_policy=cb_policy,
                env={},  # No creds in env.
            )

        issues = exc_info.value.issues
        assert any(i.provider == "torr9" for i in issues), f"Expected torr9 issue; got {issues!r}"
        assert any(i.code == "missing_credentials" for i in issues), f"Expected missing_credentials; got {issues!r}"

    def test_torr9_only_username_missing_password_raises(self) -> None:
        """With only TORR9_USERNAME set but TORR9_PASSWORD absent, still raises."""
        from personalscraper.api.tracker._errors import TrackerConfigError  # noqa: PLC0415

        event_bus = EventBus()
        ranking = RankingConfig()

        with pytest.raises(TrackerConfigError) as exc_info:
            build_tracker_registry(
                tracker_config=_torr9_tracker_config_enabled(),
                ranking=ranking,
                settings=MagicMock(),
                event_bus=event_bus,
                cb_policy=CircuitPolicy(),
                env={"TORR9_USERNAME": "user"},  # password missing
            )

        issues = exc_info.value.issues
        assert any(i.provider == "torr9" and i.code == "missing_credentials" for i in issues)
```

- [ ] **Step 5.2: Run the torr9 composition-root tests**

```bash
python -m pytest tests/integration/api/tracker/test_composition_root.py -q -k torr9
# Expected: 2 passed, 0 failed / 0 errors
```

- [ ] **Step 5.3: Run the full composition-root file to confirm no regression**

```bash
python -m pytest tests/integration/api/tracker/test_composition_root.py -q
# Expected: all passed (existing tests + 2 new torr9 tests), 0 failed
```

- [ ] **Step 5.4: Sub-commit**

```bash
git add tests/integration/api/tracker/test_composition_root.py
git commit -m "$(cat <<'EOF'
test(torr9): missing-cred fail-loud integration tests for build_tracker_registry
EOF
)"
```

---

## Task 6: Full `make check` and phase gate commit

- [ ] **Step 6.1: Run `make check`**

```bash
make check
# Expected: lint + test + module-size + typed-api guardrails all green
```

If `make test` shows any ERROR (test collection crash): fix imports before proceeding. The most likely cause is a missing import in `test_composition_root.py` (e.g. `EventBus`, `RankingConfig` imported at function scope — move to module scope if needed to fix collection).

- [ ] **Step 6.2: Verify ACC-2 (factory map)**

```bash
python -c "from personalscraper.api.tracker._factory import _TRACKER_CLASSES; print('torr9' in _TRACKER_CLASSES)"
# Expected: True
```

- [ ] **Step 6.3: Verify ACC-3 (creds mapping)**

```bash
python -c "from personalscraper.api._activation import PROVIDER_CREDS; print(PROVIDER_CREDS.get('torr9'))"
# Expected: ['TORR9_USERNAME', 'TORR9_PASSWORD']
```

- [ ] **Step 6.4: Verify ACC-4 (config overlays)**

```bash
grep -c 'torr9' config/tracker.json5 config.example/tracker.json5
# Expected: ≥1 line per file
```

- [ ] **Step 6.5: Phase gate commit**

```bash
git commit --allow-empty -m "$(cat <<'EOF'
chore(torr9): phase 2 gate — registry wiring + creds + config overlays
EOF
)"
```
