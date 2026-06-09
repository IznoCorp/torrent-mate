# ACCEPTANCE — RP5c: acquire/ lobe + single injection handle

Each criterion is an executable shell command. Run from the repo root
(venv active, `pip install -e ".[dev]"` done).

## ACC-1 — Package importable

```bash
python -c "import personalscraper.acquire; from personalscraper.acquire.context import AcquireContext; print('ACC-1 OK')"
```

Expected output:

```
ACC-1 OK
```

## ACC-2 — Single handle on AppContext; no stray `tracker_registry` field

```bash
python -c "
import dataclasses
from personalscraper.core.app_context import AppContext
f = {x.name for x in dataclasses.fields(AppContext)}
assert 'acquire' in f, f\"'acquire' missing — got {f}\"
assert 'tracker_registry' not in f, f\"'tracker_registry' still present — got {f}\"
print('ACC-2 OK')
"
```

Expected output:

```
ACC-2 OK
```

## ACC-3 — Boot builds AcquireContext with tracker_registry present

```bash
python -c "
from unittest.mock import MagicMock, patch
from personalscraper.cli_helpers import _build_app_context

config = MagicMock()
config.thresholds.circuit_breaker_threshold = 5
config.thresholds.circuit_breaker_cooldown = 30.0
config.providers = {}
config.torrent.active = ''
settings = MagicMock()

with patch('personalscraper.acquire._factory.build_tracker_registry') as mock_btr:
    mock_btr.return_value = MagicMock()
    with patch('personalscraper.api.metadata.registry.ProviderRegistry'):
        ctx = _build_app_context(config, settings)

assert ctx.acquire is not None, 'ctx.acquire is None'
assert ctx.acquire.tracker_registry is not None, 'tracker_registry is None'
print('ACC-3 OK')
"
```

Expected output:

```
ACC-3 OK
```

## ACC-4 — Layering guard active and non-vacuous

```bash
python -m pytest tests/architecture/test_layering.py -q
```

Expected output (12 passed, 0 failed):

```
............                                                             [100%]
12 passed in 0.27s
```

All three acquire-specific tests pass:

- `test_acquire_does_not_import_triage` — verifies `acquire/` has no real triage imports
- `test_acquire_triage_import_is_flagged` — positive control: a synthetic triage import under `acquire/` IS flagged
- `test_acquire_downward_import_is_not_flagged` — negative control: a downward import (`api/`, `core/`) is NOT flagged

## ACC-5 — Full gate

```bash
make check
```

Expected: `NNNN passed`, 0 failed, 0 errors. This runs lint (ruff + mypy) + full test suite
(~6263+ tests) + module-size check + typed-api guardrails. The full `make check` is executed
as the Phase 05 gate (sub-phase 5.3), not repeated here.

### Verified (2026-06-09)

| Criterion | Command                                          | Observed                         | Status  |
| --------- | ------------------------------------------------ | -------------------------------- | ------- |
| ACC-1     | `python -c "import personalscraper.acquire; …"`  | `ACC-1 OK`                       | ✅ PASS |
| ACC-2     | `python -c "import dataclasses; … AppContext …"` | `ACC-2 OK`                       | ✅ PASS |
| ACC-3     | `python -c "… _build_app_context …"`             | `ACC-3 OK`                       | ✅ PASS |
| ACC-4     | `pytest tests/architecture/test_layering.py -q`  | `12 passed in 0.27s`             | ✅ PASS |
| ACC-5     | `make check`                                     | documented; run at sub-phase 5.3 | 📋 GATE |
