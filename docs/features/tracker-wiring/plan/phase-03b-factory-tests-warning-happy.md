# Phase 3b — Factory unit tests: warning case, severity split, happy path

## Gate

**Requires Phase 3a:**

```bash
python -m pytest tests/unit/test_tracker_factory.py -q
# Expected: all passed, 0 failed
```

---

## Goal

Append the remaining test classes to `tests/unit/test_tracker_factory.py`:
the `disabled_in_priority` warning case, the severity-split proof (error
raises / warning does not), the happy-path (2 credentialed trackers → registry
with 2 entries), and the regression guard (pre-existing dict-ctor tests still
pass). All tests are non-vacuous.

---

## Files

- **Modify:** `tests/unit/test_tracker_factory.py`

---

## Tasks

### Task 3b.1 — Append warning, severity-split, and happy-path tests

Open `tests/unit/test_tracker_factory.py`. Append the following classes **at
the end of the file** (after `TestAllDisabled`):

```python
# ---------------------------------------------------------------------------
# Warning: disabled_in_priority (non-fatal, only when ≥1 active)
# ---------------------------------------------------------------------------

class TestDisabledInPriority:
    def test_disabled_in_priority_does_not_raise(self) -> None:
        """disabled_in_priority is a warning; boot must succeed."""
        cfg = TrackerConfig(
            providers={
                "lacale": TrackerProviderConfig(enabled=True),
                "c411": TrackerProviderConfig(enabled=False),
            },
            priority=["lacale", "c411"],
        )

        with patch("personalscraper.api.tracker._factory._TRACKER_CLASSES",
                   {"lacale": "tests.unit.test_tracker_factory:_StubSearchable",
                    "c411": "tests.unit.test_tracker_factory:_StubSearchable"}), \
             patch("personalscraper.api.tracker._factory.HttpTransport"):
            registry = build_tracker_registry(
                cfg, _ranking(), settings=_settings(),
                event_bus=EventBus(), cb_policy=_policy(),
                env=_env("LACALE_API_KEY"),
            )

        assert isinstance(registry, TrackerRegistry)
        assert "lacale" in registry._trackers
        assert "c411" not in registry._trackers

    def test_disabled_in_priority_only_active_tracker_built(self) -> None:
        """Only the enabled tracker is present in the returned registry."""
        cfg = TrackerConfig(
            providers={
                "lacale": TrackerProviderConfig(enabled=True),
                "c411": TrackerProviderConfig(enabled=False),
            },
            priority=["lacale", "c411"],
        )

        with patch("personalscraper.api.tracker._factory._TRACKER_CLASSES",
                   {"lacale": "tests.unit.test_tracker_factory:_StubSearchable"}), \
             patch("personalscraper.api.tracker._factory.HttpTransport"):
            registry = build_tracker_registry(
                cfg, _ranking(), settings=_settings(),
                event_bus=EventBus(), cb_policy=_policy(),
                env=_env("LACALE_API_KEY"),
            )

        assert list(registry._trackers) == ["lacale"]


# ---------------------------------------------------------------------------
# Severity split: error raises, warning does not
# ---------------------------------------------------------------------------

class TestSeveritySplit:
    def test_error_severity_raises_tracker_config_error(self) -> None:
        """Missing key → error severity → TrackerConfigError raised."""
        cfg = _cfg({"lacale": True}, priority=["lacale"])

        with pytest.raises(TrackerConfigError):
            build_tracker_registry(
                cfg, _ranking(), settings=_settings(),
                event_bus=EventBus(), cb_policy=_policy(), env={},
            )

    def test_warning_severity_does_not_raise(self) -> None:
        """disabled_in_priority → warning severity → no exception."""
        cfg = TrackerConfig(
            providers={
                "lacale": TrackerProviderConfig(enabled=True),
                "c411": TrackerProviderConfig(enabled=False),
            },
            priority=["lacale", "c411"],
        )

        with patch("personalscraper.api.tracker._factory._TRACKER_CLASSES",
                   {"lacale": "tests.unit.test_tracker_factory:_StubSearchable"}), \
             patch("personalscraper.api.tracker._factory.HttpTransport"):
            # Must not raise:
            registry = build_tracker_registry(
                cfg, _ranking(), settings=_settings(),
                event_bus=EventBus(), cb_policy=_policy(),
                env=_env("LACALE_API_KEY"),
            )

        assert isinstance(registry, TrackerRegistry)


# ---------------------------------------------------------------------------
# Happy path: 2 enabled + credentialed trackers
# ---------------------------------------------------------------------------

class TestHappyPath:
    def test_two_credentialed_trackers_returns_registry_with_both(self) -> None:
        """2 enabled+credentialed trackers → TrackerRegistry with 2 entries."""
        cfg = _cfg({"lacale": True, "c411": True}, priority=["lacale", "c411"])

        with patch("personalscraper.api.tracker._factory._TRACKER_CLASSES",
                   {"lacale": "tests.unit.test_tracker_factory:_StubSearchable",
                    "c411": "tests.unit.test_tracker_factory:_StubSearchable"}), \
             patch("personalscraper.api.tracker._factory.HttpTransport"):
            registry = build_tracker_registry(
                cfg, _ranking(), settings=_settings(),
                event_bus=EventBus(), cb_policy=_policy(),
                env=_env("LACALE_API_KEY", "C411_API_KEY"),
            )

        assert isinstance(registry, TrackerRegistry)
        assert len(registry._trackers) == 2
        assert "lacale" in registry._trackers
        assert "c411" in registry._trackers


# ---------------------------------------------------------------------------
# Regression guard: pre-existing dict-ctor tests still compile
# ---------------------------------------------------------------------------

class TestDictCtorRegressionGuard:
    def test_tracker_registry_dict_ctor_unchanged(self) -> None:
        """TrackerRegistry.__init__ signature unchanged — factory layered above it."""
        stub = MagicMock()
        stub.search = MagicMock(return_value=[])
        r = TrackerRegistry(
            trackers={"lacale": stub},
            priority=["lacale"],
            ranking=RankingConfig(),
            priority_by_media_type={"movie": ["lacale"]},
        )
        assert r._priority == ["lacale"]
        assert r._priority_by_media_type == {"movie": ["lacale"]}
```

- [ ] Apply the append above.

- [ ] **Run the full test file:**

  ```bash
  python -m pytest tests/unit/test_tracker_factory.py -v
  # Expected: all tests pass, 0 failed
  ```

- [ ] **Run pre-existing registry tests (regression guard):**
  ```bash
  python -m pytest tests/unit/test_tracker_registry_priority_by_media_type.py \
                   tests/unit/test_tracker_registry_except_scope.py -v
  # Expected: all pass
  ```

---

### Task 3b.2 — Commit

```bash
git add tests/unit/test_tracker_factory.py
git commit -m "test(tracker-wiring): factory unit tests — warning, severity split, happy path"
```

---

## Gate exit checklist

- [ ] `pytest tests/unit/test_tracker_factory.py` → all passed, 0 failed
- [ ] Pre-existing registry tests still pass (regression guard)
- [ ] Commit SHA recorded
