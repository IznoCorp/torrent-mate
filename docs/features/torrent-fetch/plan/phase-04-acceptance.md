# Phase 4 — ACCEPTANCE.md + reference docs + `make check` gate

## Gate

**Requires Phase 3 complete:**

```bash
python -c "
from personalscraper.api.tracker import (
    fetch_torrent_source, resolve_source, TrackerAuthError, TorrentFetchError
)
print('ok')
"
```

Expected: `ok`

---

## Goal

1. **Create `docs/features/torrent-fetch/ACCEPTANCE.md`** — every ACC-NN criterion is an executable shell command with a documented expected output (mandatory project rule from `feature-lifecycle.md`).
2. **Touch `docs/reference/` as needed** — a short note in the tracker or architecture reference documenting the new fetch boundary.
3. **Run `make check`** — lint + test + module-size + typed-api guardrails — and fix any issues found.
4. **Smoke test** — `python -c "import personalscraper"`.
5. **Commit.**

---

## Files

- **Create:** `docs/features/torrent-fetch/ACCEPTANCE.md`
- **Modify (optional):** `docs/reference/architecture.md` — one-paragraph note on the fetch boundary (only if the architecture doc has a tracker section; skip if it would be out of place)
- No source code changes in this phase.

---

## Tasks

### Task 4.1 — Create `ACCEPTANCE.md`

- [ ] **Create** `docs/features/torrent-fetch/ACCEPTANCE.md`:

````markdown
# ACCEPTANCE — torrent-fetch (RP1a)

Every criterion is an executable shell command. Run from the repo root with
`personalscraper` installed (`pip install -e ".[dev]"`).

---

## ACC-01 — Public import surface

**Command:**

```bash
python -c "
from personalscraper.api.tracker import (
    fetch_torrent_source,
    resolve_source,
    TrackerAuthError,
    TorrentFetchError,
)
print('ACC-01 OK')
"
```
````

**Expected output:** `ACC-01 OK` (exit 0)

---

## ACC-02 — Magnet bypass (no transport call)

**Command:**

```bash
python - <<'EOF'
from unittest.mock import MagicMock
from personalscraper.api.tracker import fetch_torrent_source

transport = MagicMock()
magnet = "magnet:?xt=urn:btih:" + "a" * 40 + "&dn=test"
result = fetch_torrent_source(magnet, transport)
assert result.magnet == magnet, f"expected magnet, got {result!r}"
transport.get_bytes.assert_not_called()
print("ACC-02 OK")
EOF
```

**Expected output:** `ACC-02 OK` (exit 0)

---

## ACC-03 — 401 raises TrackerAuthError

**Command:**

```bash
python - <<'EOF'
from unittest.mock import MagicMock
from personalscraper.api._contracts import ApiError
from personalscraper.api.tracker import fetch_torrent_source, TrackerAuthError

transport = MagicMock()
transport.get_bytes.side_effect = ApiError(
    provider="c411", http_status=401, provider_code=0, message="Unauthorized"
)
try:
    fetch_torrent_source("https://c411.org/dl/x", transport)
    raise AssertionError("Expected TrackerAuthError was not raised")
except TrackerAuthError as e:
    assert e.http_status == 401, f"http_status={e.http_status}"
print("ACC-03 OK")
EOF
```

**Expected output:** `ACC-03 OK` (exit 0)

---

## ACC-04 — HTML-200 body raises TorrentFetchError

**Command:**

```bash
python - <<'EOF'
from unittest.mock import MagicMock
from personalscraper.api.tracker import fetch_torrent_source, TorrentFetchError

transport = MagicMock()
transport._policy.provider_name = "c411"
transport.get_bytes.return_value = b"<html><body>Login required</body></html>"
try:
    fetch_torrent_source("https://c411.org/dl/x", transport)
    raise AssertionError("Expected TorrentFetchError was not raised")
except TorrentFetchError as e:
    assert "invalid" in str(e).lower() or "not a bencoded" in str(e).lower(), str(e)
print("ACC-04 OK")
EOF
```

**Expected output:** `ACC-04 OK` (exit 0)

---

## ACC-05 — Uppercase / base32 expected hash — cross-check passes

**Command:**

```bash
python - <<'EOF'
import base64
import hashlib
from unittest.mock import MagicMock
from personalscraper.api.tracker import fetch_torrent_source

def _bencode(obj):
    if isinstance(obj, bytes):
        return str(len(obj)).encode() + b":" + obj
    if isinstance(obj, int):
        return b"i" + str(obj).encode() + b"e"
    if isinstance(obj, dict):
        out = b"d"
        for k in sorted(obj):
            out += _bencode(k) + _bencode(obj[k])
        return out + b"e"
    raise TypeError(type(obj))

info = {b"length": 1, b"name": b"f.mkv", b"piece length": 16384, b"pieces": b"\x00" * 20}
torrent = _bencode({b"announce": b"http://t.example.com", b"info": info})
info_hash = hashlib.sha1(_bencode(info)).hexdigest()
b32_hash = base64.b32encode(bytes.fromhex(info_hash)).decode()

transport = MagicMock()
transport._policy.provider_name = "c411"
transport.get_bytes.return_value = torrent

# uppercase hex must pass
r1 = fetch_torrent_source("https://c411.org/dl/x", transport, expected_info_hash=info_hash.upper())
assert r1.info_hash == info_hash, f"uppercase hex failed: {r1.info_hash}"

# base32 must pass
r2 = fetch_torrent_source("https://c411.org/dl/x", transport, expected_info_hash=b32_hash)
assert r2.info_hash == info_hash, f"base32 failed: {r2.info_hash}"

print("ACC-05 OK")
EOF
```

**Expected output:** `ACC-05 OK` (exit 0)

---

## ACC-06 — Oversize body raises TorrentFetchError

**Command:**

```bash
python - <<'EOF'
import pytest
from personalscraper.api.tracker._errors import TorrentFetchError
from personalscraper.api.transport._http import HttpTransport
from personalscraper.api.transport._policy import TransportPolicy, RetryPolicy, CircuitPolicy, RateLimitPolicy
from personalscraper.api.transport._auth import ApiKeyAuth
from personalscraper.core.event_bus import EventBus
from unittest.mock import MagicMock

policy = TransportPolicy(
    provider_name="test",
    base_url="https://t.example.com",
    auth=ApiKeyAuth(key="k", param="apikey", location="query"),
    retry=RetryPolicy(max_attempts=1),
    circuit=CircuitPolicy(failure_threshold=5, cooldown_seconds=300.0),
    rate_limit=RateLimitPolicy(requests_per_second=0.0),
)
transport = HttpTransport(policy, event_bus=EventBus())

big = b"x" * 200

resp = MagicMock()
resp.ok = True
resp.status_code = 200
resp.iter_content.return_value = iter([big])
transport._session.request = lambda *a, **kw: resp

try:
    transport.get_bytes("https://t.example.com/f", max_bytes=10)
    raise AssertionError("Expected TorrentFetchError")
except TorrentFetchError as e:
    assert "max_bytes" in str(e), str(e)
print("ACC-06 OK")
EOF
```

**Expected output:** `ACC-06 OK` (exit 0)

---

## ACC-07 — Download 5xx does NOT open the search circuit

**Command:**

```bash
python - <<'EOF'
from personalscraper.api._contracts import ApiError
from personalscraper.api.transport._http import HttpTransport
from personalscraper.api.transport._policy import TransportPolicy, RetryPolicy, CircuitPolicy, RateLimitPolicy
from personalscraper.api.transport._auth import ApiKeyAuth
from personalscraper.core.circuit import CircuitState
from personalscraper.core.event_bus import EventBus
from unittest.mock import MagicMock

policy = TransportPolicy(
    provider_name="c411",
    base_url="https://c411.org",
    auth=ApiKeyAuth(key="k", param="apikey", location="query"),
    retry=RetryPolicy(max_attempts=1),
    circuit=CircuitPolicy(failure_threshold=2, cooldown_seconds=300.0),
    rate_limit=RateLimitPolicy(requests_per_second=0.0),
)
transport = HttpTransport(policy, event_bus=EventBus())

def fail_500(method, url, **kw):
    resp = MagicMock()
    resp.ok = False
    resp.status_code = 500
    resp.reason = "Error"
    resp.json.side_effect = ValueError()
    resp.text = "error"
    return resp

transport._session.request = fail_500

for _ in range(2):
    try:
        transport.get_bytes("https://c411.org/dl/x")
    except ApiError:
        pass

assert transport._download_circuit.state == CircuitState.OPEN, "download circuit should be OPEN"
assert transport._circuit.state == CircuitState.CLOSED, "search circuit must remain CLOSED"
print("ACC-07 OK")
EOF
```

**Expected output:** `ACC-07 OK` (exit 0)

---

## ACC-08 — `make check` green

**Command:**

```bash
make check
```

**Expected output:** `make check` exits 0 — lint, tests, module-size, typed-api all pass.

---

## ACC-09 — Smoke import

**Command:**

```bash
python -c "import personalscraper; print('ACC-09 OK')"
```

**Expected output:** `ACC-09 OK` (exit 0)

````

- [ ] **Verify the file was written:**

```bash
ls -la docs/features/torrent-fetch/ACCEPTANCE.md
````

---

### Task 4.2 — Run all ACCEPTANCE criteria

Run each ACC command from the repo root in sequence. If any fails, fix the underlying code (no shortcuts) and re-run.

- [ ] ACC-01 through ACC-07 — run each `python - <<'EOF' ... EOF` block and confirm the `OK` line prints.
- [ ] ACC-08: `make check` → exit 0
- [ ] ACC-09: `python -c "import personalscraper"` → exit 0

---

### Task 4.3 — Optional: note in `docs/reference/architecture.md`

Read `docs/reference/architecture.md` to find the tracker section. If it describes tracker clients/capabilities, add a one-paragraph note after the existing tracker description:

```markdown
#### Fetch boundary (`api/tracker/_fetch.py`)

`fetch_torrent_source(url, transport)` and `resolve_source(result, transports)`
form the tracker-agnostic fetch boundary (RP1a). They turn a `TrackerResult`
into a `TorrentSource` by calling `HttpTransport.get_bytes` — which uses a
dedicated download circuit breaker and rate limiter so download failures never
affect the search circuit. Magnet links bypass the network entirely.
Exported from `personalscraper.api.tracker.__all__`.
```

Only add this if the architecture doc has an existing tracker section. If there is no suitable anchor, skip it (the design doc and ACCEPTANCE.md are self-contained).

---

### Task 4.4 — Commit

```bash
git add docs/features/torrent-fetch/ACCEPTANCE.md
# If you edited docs/reference/architecture.md:
# git add docs/reference/architecture.md
git commit -m "docs(torrent-fetch): ACCEPTANCE.md + make check gate"
```

---

## Gate exit checklist

- [ ] All ACC-01 through ACC-09 pass
- [ ] `make check` exits 0
- [ ] `python -c "import personalscraper"` exits 0
- [ ] Feature branch `feat/torrent-fetch` is clean (`git status`)
- [ ] Commit SHA recorded
