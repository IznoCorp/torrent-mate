# Phase 4 — Subscribers + frontend labels + ACCEPTANCE + full gate

**Gate**: Phase 3 complete — download events fire from `reconcile_wanted`, `event_bus` plumbed through all callers, `DownloadStarted`/`DownloadProgressed`/`DownloadCompleted` importable from `personalscraper.acquire.events`.

## Scope

Telegram subscriber for `DownloadCompleted` (13th in `AcquisitionTelegramSubscriber`), frontend `eventTypeLabel` entries for the three new event types (French labels + vitest), `ACCEPTANCE.md` with executable shell-command criteria, and the full quality gate (`make lint`, `make test`, smoke test, migration verification).

---

## Sub-phase 4.1: Telegram DownloadCompleted subscriber

**Commit**: `feat(seed-caps): add Telegram subscriber for DownloadCompleted event`

### Files
- **Modify**: `personalscraper/subscribers/acquire.py` — subscribe + handler
- **Create**: `tests/subscribers/test_acquire_download_events.py`

### Implementation

**Import**: Add `DownloadCompleted` to the existing import from `personalscraper.acquire.events`.

**Subscription**: In `AcquisitionTelegramSubscriber.__init__`, add to `self._tokens` (D8 — Telegram only gets `DownloadCompleted`, not Started/Progressed):

```python
bus.subscribe(DownloadCompleted, self._on_download_completed),
```

**Handler** (follow the pattern of `_on_grab_succeeded`):

```python
def _on_download_completed(self, event: DownloadCompleted) -> None:
    """Handle DownloadCompleted — notify via Telegram (O4/D8)."""
    message = (
        f"\u2705 Téléchargement terminé : {event.title}\n"
        f"_provider: {event.provider} · {event.kind}_"
    )
    self._log_and_maybe_send(event, message)
```

### Tests

In `tests/subscribers/test_acquire_download_events.py`:
- `test_handler_formats_correct_message` — mock notifier, call handler, verify message contains French text and title
- `test_started_not_subscribed` — verify no `_on_download_started` or `_on_download_progressed` methods exist (D8 anti-spam)

### Gate
```bash
pytest tests/subscribers/test_acquire_download_events.py -v   # all pass
```

---

## Sub-phase 4.2: Frontend eventTypeLabel entries

**Commit**: `feat(seed-caps): add French labels for download events in eventTypeLabel`

### Files
- **Modify**: `frontend/src/components/dashboard/eventRow.utils.ts` — add 3 entries to `EVENT_TYPE_LABEL`
- **Modify**: Vitest test file for `eventRow.utils` — add label assertions

### Implementation

In `EVENT_TYPE_LABEL` (around line 52), add:

```ts
DownloadStarted: "Téléchargement démarré",
DownloadProgressed: "Téléchargement en cours",
DownloadCompleted: "Téléchargement terminé",
```

For `DownloadProgressed`, the render component (EventRow/RecentEventsTable) appends the threshold percentage at display time (e.g. `"Téléchargement en cours (50 %)"`). The label map stores only the base text.

### Vitest

```ts
describe("download event labels", () => {
  it("renders DownloadStarted with French label", () => {
    expect(eventTypeLabel("DownloadStarted")).toBe("Téléchargement démarré");
  });
  it("renders DownloadProgressed with French label", () => {
    expect(eventTypeLabel("DownloadProgressed")).toBe("Téléchargement en cours");
  });
  it("renders DownloadCompleted with French label", () => {
    expect(eventTypeLabel("DownloadCompleted")).toBe("Téléchargement terminé");
  });
});
```

### Gate
```bash
cd frontend && npx vitest run --reporter=verbose 2>/dev/null || npm test
cd frontend && npx eslint src/components/dashboard/eventRow.utils.ts
cd frontend && npx tsc --noEmit
```

---

## Sub-phase 4.3: ACCEPTANCE.md + full gate

**Commit**: `chore(seed-caps): add ACCEPTANCE.md + phase 4 gate`

### Files
- **Create**: `docs/features/seed-caps/ACCEPTANCE.md`

### ACCEPTANCE.md

Create with 12 executable shell-command criteria per SH-16 rule:

| # | Criterion | Command |
|---|-----------|---------|
| ACC-01 | BandwidthConfig loads with defaults (all None) | `python -c "from personalscraper.conf.loader import load_config; ..."` |
| ACC-02 | ByteSize coercion ("5MB" → 5_000_000) | `python -c "from personalscraper.conf.models.acquire import BandwidthConfig; ..."` |
| ACC-03 | Zero values rejected | `python -c "... BandwidthConfig(per_torrent_down=0) ..."` expect ValueError |
| ACC-04 | Migration 014 schema valid | `python -c "import sqlite3; conn=sqlite3.connect(':memory:'); conn.executescript(open('...').read()); ..."` |
| ACC-05 | DownloadMarksStore CRUD + prune | `python -c "... store.upsert(...); store.get(...); store.prune_stale(...)"` |
| ACC-06 | DownloadStarted importable + constructable | `python -c "from personalscraper.acquire.events import DownloadStarted; ..."` |
| ACC-07 | reconcile_wanted new signature (client_items + event_bus, no client_hashes) | `python -c "import inspect; ..."` |
| ACC-08 | No stale reconcile_wanted callers | `rg 'reconcile_wanted(' --type py ... \| grep -v client_items` |
| ACC-09 | Frontend French labels present | `grep -E 'DownloadStarted\|...' frontend/.../eventRow.utils.ts \| grep Téléchargement` |
| ACC-10 | make lint zero errors | `make lint` |
| ACC-11 | make test zero failures | `make test` |
| ACC-12 | Import smoke test | `python -c "import personalscraper"` |

Each criterion documents expected output (PASS/FAIL with specific message). See `docs/reference/feature-lifecycle.md` for the full ACCEPTANCE convention.

### Full Gate

```bash
# 1. Quality gates
make lint                                           # zero errors
make test                                           # all tests pass, 0 failed/errors
make check                                          # lint + test + module-size + typed-api

# 2. No stale signature
rg "client_hashes" --type py personalscraper/acquire/reconcile.py && echo "STALE" || echo "OK"

# 3. Smoke test
python -c "import personalscraper"                  # OK

# 4. Migration idempotency (already verified by test suite)
```

---

## Phase 4 Gate (PR-ready)

```bash
make lint                             # zero errors
make test                             # all 6000+ tests pass, 0 failed/errors
make check                            # full gate
rg "client_hashes" --type py personalscraper/acquire/reconcile.py && echo "STALE" || echo "OK"
python -c "import personalscraper"    # smoke test
```

**After this gate**: feature is ready for `/implement:feature-pr` (push + PR + CI poll).
