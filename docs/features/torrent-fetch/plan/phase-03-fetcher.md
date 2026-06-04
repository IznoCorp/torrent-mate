# Phase 3 — Fetcher module + public surface + docstring fix

## Gate

**Requires Phase 2 complete:**

```bash
python -c "from personalscraper.api.transport._http import HttpTransport; _ = HttpTransport.get_bytes; print('ok')"
```

Expected: `ok`

---

## Goal

1. **Create `api/tracker/_fetch.py`** — tracker-agnostic fetch boundary (D1):
   - `_is_magnet(url: str) -> bool` — scheme-based classifier (`magnet:`, case-insensitive).
   - `_canonical_info_hash(s: str) -> str` — 40-char hex → lowercase; 32-char base32 → decoded hex; else `ValueError`.
   - `fetch_torrent_source(url, transport, *, expected_info_hash=None) -> TorrentSource` — magnet shortcut (D8) OR binary GET + `from_file` validate + optional hash cross-check (D5/D7).
   - `resolve_source(result, transports, *, cross_check=True) -> TorrentSource` — route by `result.provider` (lowercase wire key, D6) over caller-supplied transport map; magnet short-circuit before transport lookup (D8).

2. **Fill `api/tracker/__init__.py`** — `__all__` exporting all 4 public symbols.

3. **Fix stale docstring** in `api/tracker/_base.py` — `TrackerResult.provider` example says `"LaCale"`/`"C411"`; wire value is lowercase `"lacale"`/`"c411"` (verified in DESIGN §3).

4. **Create `tests/unit/test_tracker_fetch.py`** — full adversarial suite.

---

## Files

- **Create:** `personalscraper/api/tracker/_fetch.py`
- **Modify:** `personalscraper/api/tracker/__init__.py` (currently empty)
- **Modify:** `personalscraper/api/tracker/_base.py` (docstring fix only)
- **Create:** `tests/unit/test_tracker_fetch.py`

---

## Tasks

### Task 3.1 — Fix stale docstring in `_base.py`

- [ ] Read `personalscraper/api/tracker/_base.py` to locate the `provider` field docstring.
- [ ] Update the example from `"LaCale"`/`"C411"` to `"lacale"`/`"c411"`, clarifying it is the lowercase wire value used as the key in `resolve_source`'s `transports` map.
- [ ] Verify: `python -c "from personalscraper.api.tracker._base import TrackerResult; print('ok')"`

---

### Task 3.2 — Create `api/tracker/_fetch.py`

The module has two public functions and two private helpers. Key design invariants:

- `_is_magnet`: `url.lower().startswith("magnet:")` — no regex needed.
- `_canonical_info_hash`: regex-match then lowercase (hex) or `base64.b32decode(s.upper()).hex()` (base32); raise `ValueError` for anything else.
- `fetch_torrent_source`: magnet → `TorrentSource.from_magnet(url)` immediately, no transport call. HTTP → `transport.get_bytes(url)`. **Error mapping** (the fetcher owns ALL `TorrentFetchError` surfacing — `HttpTransport` stays provider-agnostic, Phase 2): `ApiError(http_status in {401,403})` → re-raise as `TrackerAuthError` (other `ApiError` propagates as-is); a `ValueError` raised by `get_bytes` (empty/oversize body — agnostic, Phase 2) → wrap as `TorrentFetchError`. Then `TorrentSource.from_file(data)` + access `.info_hash`, which raises `ValueError` on non-bencode / missing `info` key → wrap as `TorrentFetchError` with URL + `data[:64]` preview. Finally, if `expected_info_hash` is truthy, canonicalize and compare, raise `TorrentFetchError("mismatch …")` on divergence; non-canonicalizable expected hash → skip silently.
- `resolve_source`: magnet check first (before transport lookup, D8); then `download_url is None` → `TorrentFetchError`; then `provider_key not in transports` → `TorrentFetchError` (embed available keys); else delegate to `fetch_torrent_source`.

Illustrative snippet — `_canonical_info_hash` core (the tricky bit):

```python
s = s.strip()
if re.fullmatch(r"[0-9a-fA-F]{40}", s):
    return s.lower()
if re.fullmatch(r"[A-Za-z2-7]{32}", s):
    return base64.b32decode(s.upper()).hex()
raise ValueError(f"Cannot canonicalize info_hash: {s!r}")
```

Use `TYPE_CHECKING` for `TrackerResult` and `HttpTransport` imports to avoid circular imports (same pattern as `api/torrent/_base.py`).

- [ ] Create `personalscraper/api/tracker/_fetch.py` with Google-style docstrings on all functions.
- [ ] Verify: `python -c "from personalscraper.api.tracker._fetch import fetch_torrent_source, resolve_source; print('ok')"`

---

### Task 3.3 — Fill `api/tracker/__init__.py`

- [ ] Replace the empty `__init__.py` with imports + `__all__` for `fetch_torrent_source`, `resolve_source`, `TrackerAuthError`, `TorrentFetchError`.
- [ ] Verify: `python -c "from personalscraper.api.tracker import fetch_torrent_source, resolve_source, TrackerAuthError, TorrentFetchError; print('ok')"`

---

### Task 3.4 — Write `tests/unit/test_tracker_fetch.py`

All tests use fake transports (`MagicMock` with `transport._policy.provider_name` set, `transport.get_bytes` configured via `return_value`/`side_effect`). No real network calls.

Include a local `_bencode`/`_make_torrent` helper (copy the pattern from `tests/unit/test_torrent_source.py` — do not import it; keep tests self-contained). `_make_torrent` returns `(raw_bytes, expected_info_hash_hex)`.

**Design reference for the file header:**
`Design: §5.2, §7 (D1/D5/D6/D7/D8) — standalone tracker-agnostic fetch boundary.`
`Contract: magnet bypass; 401/403 → TrackerAuthError; HTML-200 → TorrentFetchError; hash cross-check (uppercase/base32/mismatch/skip); resolve_source routing; missing provider/download_url errors.`

- [ ] Create the file with the following test cases (write real pytest code):

**TestIsMagnet:**

- `test_magnet_uri` — `"magnet:?xt=…"` → `True`.
- `test_uppercase_magnet` — `"MAGNET:?xt=…"` → `True`.
- `test_https_url` — `"https://c411.org/dl/x"` → `False`.
- `test_relative_url` — `"/api/download/abc"` → `False`.

**TestCanonicalInfoHash (D7):**

- `test_lowercase_hex_unchanged` — 40-char lowercase hex → same string.
- `test_uppercase_hex_lowercased` — 40-char uppercase → lowercased.
- `test_mixed_case_hex` — mixed-case 40-char hex → lowercased.
- `test_base32_decoded_to_hex` — 20 raw bytes → b32encode → `_canonical_info_hash` → matches `.hex()`.
- `test_invalid_raises_value_error` — `"not-a-hash"` → `ValueError`.
- `test_31_char_invalid` — 31 `"A"` chars → `ValueError`.

**TestFetchTorrentSourceMagnet (D8):**

- `test_magnet_returns_from_magnet_no_transport_call` — magnet URL → `TorrentSource` with `.magnet` set; `transport.get_bytes` never called.

**TestFetchTorrentSourceHttp (D5):**

- `test_valid_torrent_bytes_returned` — valid bencode bytes → `TorrentSource` with `.file_bytes` set.
- `test_html_200_raises_torrent_fetch_error` — `b"<html>…"` → `TorrentFetchError` with `"invalid"` in message.
- `test_json_error_page_raises_torrent_fetch_error` — `b'{"error":…}'` → `TorrentFetchError`.
- `test_bencode_without_info_key_raises_torrent_fetch_error` — bencoded dict with no `info` key → `TorrentFetchError`.
- `test_get_bytes_oversize_valueerror_becomes_torrent_fetch_error` — `transport.get_bytes` `side_effect=ValueError("download exceeds max_bytes=…")` → `TorrentFetchError` (the agnostic transport `ValueError` is mapped here, D5).
- `test_get_bytes_empty_valueerror_becomes_torrent_fetch_error` — `transport.get_bytes` `side_effect=ValueError("empty download body")` → `TorrentFetchError` (D5).

**TestFetchTorrentSourceAuthErrors (D4):**

- `test_401_raises_tracker_auth_error` — `ApiError(http_status=401)` from transport → `TrackerAuthError(http_status=401)`.
- `test_403_raises_tracker_auth_error` — `ApiError(http_status=403)` → `TrackerAuthError(http_status=403)`.
- `test_500_propagates_as_api_error_not_auth_error` — `ApiError(http_status=500)` → re-raised as `ApiError`, not `TrackerAuthError`.

**TestFetchTorrentSourceHashCrossCheck (D7):**

- `test_matching_lowercase_hex_passes` — valid torrent + correct lowercase hash → no raise.
- `test_uppercase_expected_hash_passes` — same hash uppercased → canonicalized before compare, no raise.
- `test_base32_expected_hash_passes` — same hash as base32 string → decoded and compared, no raise.
- `test_real_mismatch_raises_torrent_fetch_error` — deliberately wrong hash → `TorrentFetchError("mismatch")`.
- `test_empty_string_skips_cross_check` — `expected_info_hash=""` → no raise (C411 can return `""`).
- `test_none_skips_cross_check` — `expected_info_hash=None` → no raise (LaCale can return `None`).

**TestResolveSource (D6):**

- `test_routes_c411_to_correct_transport` — two-transport map; c411 transport called, lacale not.
- `test_routes_lacale_to_correct_transport` — relative `download_url`; lacale transport called.
- `test_missing_provider_raises_torrent_fetch_error_with_available_keys` — provider not in map → `TorrentFetchError` message contains both the missing key and the available keys.
- `test_missing_download_url_raises_torrent_fetch_error` — `download_url=None` → `TorrentFetchError("no download_url")`.
- `test_magnet_download_url_bypasses_transport` — magnet in `download_url` → transport never called.
- `test_cross_check_false_disables_hash_check` — deliberately wrong `info_hash` on `TrackerResult`; `cross_check=False` → no raise.
- `test_empty_transports_map_raises_torrent_fetch_error` — empty `{}` map → `TorrentFetchError` with `"available"` in message.

- [ ] Run: `pytest tests/unit/test_tracker_fetch.py -v` — 33 tests, all pass.

---

### Task 3.5 — Verify public import surface

```bash
python -c "
from personalscraper.api.tracker import (
    fetch_torrent_source, resolve_source, TrackerAuthError, TorrentFetchError
)
print('Public surface OK')
"
```

Expected: `Public surface OK`

---

### Task 3.6 — Commit

```bash
git add \
  personalscraper/api/tracker/_fetch.py \
  personalscraper/api/tracker/__init__.py \
  personalscraper/api/tracker/_base.py \
  tests/unit/test_tracker_fetch.py
git commit -m "feat(torrent-fetch): tracker fetch boundary — fetch_torrent_source + resolve_source"
```

---

## Gate exit checklist

- [ ] `python -c "from personalscraper.api.tracker import fetch_torrent_source, resolve_source, TrackerAuthError, TorrentFetchError"` → exit 0
- [ ] `pytest tests/unit/test_tracker_fetch.py` → 33 passed, 0 failed
- [ ] `pytest tests/unit/` → no regression in existing suite
- [ ] Commit SHA recorded
