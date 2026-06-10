# ACCEPTANCE — RP4: acquire-events (0.26.0 → 0.27.0)

Every criterion is an executable shell command. Run from the repo root with
the `feat/acquire-events` branch checked out and `pip install -e ".[dev]"`
done.

---

## ACC-01 — Registry count = 33

**Criterion:** After importing `personalscraper.events`, the
`_EVENT_CLASS_REGISTRY` contains exactly 33 production event classes.

```bash
python -c "
import personalscraper.events
from personalscraper.core.event_bus import _EVENT_CLASS_REGISTRY
assert len(_EVENT_CLASS_REGISTRY) == 33, \
    f'Expected 33, got {len(_EVENT_CLASS_REGISTRY)}: {sorted(_EVENT_CLASS_REGISTRY)}'
print('ACC-01 PASS: registry =', len(_EVENT_CLASS_REGISTRY))
"
```

**Expected output:** `ACC-01 PASS: registry = 33`

---

## ACC-02 — Envelope round-trip for all 10 acquisition events

**Criterion:** Every acquisition event survives `event_to_envelope` →
`json.dumps` → `json.loads` → `event_from_envelope` and reconstructs to an
equal instance (including nested `MediaRef` fields).

```bash
pytest tests/acquire/test_acquire_events.py::test_acquire_events_envelope_roundtrip \
  -v --tb=short
```

**Expected output:** 10 PASSED (one per event class: SeriesFollowed,
SeriesUnfollowed, WantedEnqueued, WantedAbandoned, GrabSucceeded, GrabFailed,
SeedObligationRecorded, SeedObligationBreached, SeedObligationSatisfied,
RatioMeasured). No FAILED, no ERROR.

---

## ACC-03 — Muted subscriber: no send when disabled, one send when enabled

**Criterion:** `AcquisitionTelegramSubscriber` with `enabled=False` never calls
`notifier.send`; with `enabled=True` calls it exactly once per emit (mocked notifier).

```bash
pytest tests/subscribers/test_acquire_subscriber.py \
  -k "disabled_does_not_send or enabled_sends_once" \
  -v --tb=short
```

**Expected output:** 20 PASSED (10 disabled + 10 enabled parametrized variants).
No FAILED, no ERROR.

---

## ACC-04 — Full quality gate

**Criterion:** `make check` exits 0 (lint + mypy + all tests pass, module-size
budget respected).

```bash
make check
```

**Expected output:** `6540 passed, 3 skipped, 2 xfailed` (0 failed, 0 errors).
`check-module-size: 1 finding(s)` (pre-existing 975-line `movie_service.py` warning).
`cli-coverage-report: OK — 0 ❌ on critical commands`. Exit code 0.
