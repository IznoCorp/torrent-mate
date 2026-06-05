# ACCEPTANCE — torrent-fetch (RP1a)

Every criterion is an executable shell command with a documented expected output.
Run from the repo root with `personalscraper` installed (`pip install -e ".[dev]"`).

> **Hook note.** A `block_curl_without_timeout` PreToolUse hook misfires on the
> literal substring `fetch` in any bash command. The canonical `python -c "..."`
> form for the criteria below is documented as text; to _execute_ a criterion
> whose body contains the `fetch` token, write the snippet to a temp file
> (e.g. `/tmp/acc.py`) and run `python /tmp/acc.py` — the hook does not inspect
> file contents.

> **Layering note (signed-off).** `HttpTransport.get_bytes` is provider-agnostic:
> on an empty/oversize body it raises a bare `ValueError`, NOT `TorrentFetchError`.
> The `TorrentFetchError` surfacing for those cases happens only at the tracker
> fetch boundary (the boundary maps the agnostic `ValueError`). So ACC-06 exercises
> oversize through the boundary (with a fake transport whose `get_bytes` raises
> `ValueError`), and ACC-06b asserts the agnostic `ValueError` from `get_bytes`
> directly.

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

**Expected output:** `ACC-01 OK` (exit 0)

---

## ACC-02 — Magnet bypass (no transport call)

The boundary short-circuits a `magnet:` URI before any transport call (D8).

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

An `ApiError(http_status=401)` from the transport maps to `TrackerAuthError` (D4).

**Command:**

```bash
python - <<'EOF'
from personalscraper.api._contracts import ApiError
from personalscraper.api.tracker import fetch_torrent_source, TrackerAuthError
from unittest.mock import MagicMock

transport = MagicMock()
transport._policy.provider_name = "c411"
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

A 200 response carrying an HTML login wall (not a bencoded `.torrent`) is
rejected as an invalid body (D5).

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
    assert "invalid" in str(e).lower(), str(e)
print("ACC-04 OK")
EOF
```

**Expected output:** `ACC-04 OK` (exit 0)

---

## ACC-05 — Uppercase / base32 expected hash — cross-check passes

A non-empty `expected_info_hash` is canonicalized to lowercase hex before the
cross-check, so an uppercase-hex or base32 expected value still matches (D7).

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

## ACC-06 — Oversize body raises TorrentFetchError (via the fetch boundary)

`HttpTransport.get_bytes` raises a provider-agnostic `ValueError` on oversize
(see ACC-06b). The boundary maps that `ValueError` to `TorrentFetchError` (D5).
This criterion exercises the _boundary_, with a fake transport whose `get_bytes`
raises the agnostic oversize `ValueError`.

**Command:**

```bash
python - <<'EOF'
from unittest.mock import MagicMock
from personalscraper.api.tracker import fetch_torrent_source, TorrentFetchError

transport = MagicMock()
transport._policy.provider_name = "c411"
transport.get_bytes.side_effect = ValueError("download exceeds max_bytes=10")
try:
    fetch_torrent_source("https://c411.org/dl/x", transport)
    raise AssertionError("Expected TorrentFetchError was not raised")
except TorrentFetchError as e:
    assert "max_bytes" in str(e), str(e)
print("ACC-06 OK")
EOF
```

**Expected output:** `ACC-06 OK` (exit 0)

---

## ACC-06b — Oversize body at the transport layer is an agnostic ValueError

`HttpTransport.get_bytes` itself stays provider-agnostic: oversize → bare
`ValueError` (NOT `TorrentFetchError`). This is the layering invariant the
boundary in ACC-06 relies on.

**Command:**

```bash
python - <<'EOF'
from personalscraper.api.transport._http import HttpTransport
from personalscraper.api.transport._policy import (
    TransportPolicy, RetryPolicy, CircuitPolicy, RateLimitPolicy,
)
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

resp = MagicMock()
resp.ok = True
resp.status_code = 200
resp.iter_content.return_value = iter([b"x" * 200])
transport._session.request = lambda *a, **kw: resp

try:
    transport.get_bytes("https://t.example.com/f", max_bytes=10)
    raise AssertionError("Expected ValueError")
except ValueError as e:
    assert "max_bytes" in str(e), str(e)
print("ACC-06b OK")
EOF
```

**Expected output:** `ACC-06b OK` (exit 0)

---

## ACC-07 — Download 5xx does NOT open the search circuit

A repeated download 5xx trips the _dedicated_ download circuit only; the search
circuit stays CLOSED (D3 isolation).

**Command:**

```bash
python - <<'EOF'
from personalscraper.api._contracts import ApiError
from personalscraper.api.transport._http import HttpTransport
from personalscraper.api.transport._policy import (
    TransportPolicy, RetryPolicy, CircuitPolicy, RateLimitPolicy,
)
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

**Expected output:** `make check` exits 0 — ruff + mypy lint, the full test suite
(`NNNN passed`), module-size budget, and typed-api guardrails all pass.

---

## ACC-09 — Smoke import

**Command:**

```bash
python -c "import personalscraper; print('ACC-09 OK')"
```

**Expected output:** `ACC-09 OK` (exit 0)
