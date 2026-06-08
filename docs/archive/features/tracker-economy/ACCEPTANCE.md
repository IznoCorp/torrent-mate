# ACCEPTANCE — tracker-economy (RP2)

Every criterion is an executable shell command with a documented expected
output. Run from the repo root with `personalscraper` installed
(`pip install -e ".[dev]"`).

---

## ACC-01 — Valid economy block loads; `target_ratio < min_ratio` rejected

Write the script below to `/tmp/acc01_te.py`, then run `python /tmp/acc01_te.py`.

```python
import pathlib, tempfile
from personalscraper.conf.loader import load_config_dir, ConfigValidationError

def _make(d, economy_json):
    import os; os.makedirs(d, exist_ok=True); d = pathlib.Path(d)
    tmp = str(d.parent)
    (d/"config.json5").write_text(
        f'{{"config_version":1,"overlays":["paths.json5","disks.json5","patterns.json5","tracker.json5"],'
        f'"paths":{{"torrent_complete_dir":"{tmp}/c","staging_dir":"{tmp}/s","data_dir":"{tmp}/dt"}}}}')
    (d/"paths.json5").write_text("{}")
    (d/"disks.json5").write_text(f'{{"disks":[{{"id":"a","path":"{tmp}/disk","categories":["movies"]}}]}}')
    (d/"patterns.json5").write_text('{"staging_dirs":[{"id":1,"name":"movies","file_type":"movie"},{"id":2,"name":"tvshows","file_type":"tvshow"},{"id":3,"name":"ebooks","file_type":"ebook"},{"id":4,"name":"audio","file_type":"audio"},{"id":5,"name":"apps","file_type":"app"},{"id":6,"name":"android","file_type":"app"},{"id":97,"name":"temp","file_type":null,"role":"ingest"},{"id":98,"name":"autres","file_type":"other"}]}')
    (d/"tracker.json5").write_text(f'{{"tracker":{{"providers":{{"c411":{{"enabled":false,{economy_json}}}}},"priority":["c411"],"max_total_results":50,"max_per_tracker":30,"timeout_per_tracker":15}}}}')
    return d

with tempfile.TemporaryDirectory() as tmp:
    cfg = load_config_dir(_make(f"{tmp}/ok", '"economy":{"target_ratio":2.0,"min_ratio":1.0,"min_seed_time":"72h","hit_and_run_grace":"0h"}'))
    assert cfg.tracker.providers["c411"].economy is not None
    print("ACC-01a OK — valid economy block loads")
    try:
        load_config_dir(_make(f"{tmp}/bad", '"economy":{"target_ratio":0.5,"min_ratio":1.0,"min_seed_time":"72h"}'))
        raise AssertionError("expected ConfigValidationError")
    except ConfigValidationError as e:
        assert "target_ratio" in str(e)
    print("ACC-01b OK — target_ratio < min_ratio raises ConfigValidationError")
```

**Expected output:**

```
ACC-01a OK — valid economy block loads
ACC-01b OK — target_ratio < min_ratio raises ConfigValidationError
```

---

## ACC-02 — `min_seed_time "72h"` → 259200 seconds

```bash
python - <<'EOF'
from personalscraper.conf.models.api_config import TrackerEconomyConfig
cfg = TrackerEconomyConfig(target_ratio=2.0, min_seed_time="72h")
assert cfg.min_seed_time == 259_200, f"expected 259200, got {cfg.min_seed_time}"
print("ACC-02 OK")
EOF
```

**Expected output:** `ACC-02 OK` (exit 0)

---

## ACC-03 — Enabled tracker with no passkey stays active; `resolve_optional_secret` returns `None`

```bash
python - <<'EOF'
from dataclasses import dataclass
from personalscraper.api._activation import resolve_active, resolve_optional_secret

@dataclass
class _P:
    enabled: bool = True

env = {"C411_API_KEY": "key123"}   # passkey intentionally absent
active = resolve_active({"c411": _P(enabled=True)}, "tracker", env=env)
assert "c411" in active, f"c411 must be active without passkey, got: {active}"
print("ACC-03a OK — enabled tracker active without passkey")

secret = resolve_optional_secret("c411", env=env)
assert secret == {"C411_PASSKEY": None}, f"expected None for absent passkey, got: {secret}"
print("ACC-03b OK — resolve_optional_secret returns None for absent passkey")
EOF
```

**Expected output:**

```
ACC-03a OK — enabled tracker active without passkey
ACC-03b OK — resolve_optional_secret returns None for absent passkey
```

---

## ACC-04 — `make check` green

```bash
make check
```

**Expected output:** exits 0 — ruff + mypy lint, full test suite (`NNNN passed`), module-size budget, typed-api guardrails all pass.

---

## ACC-05 — Smoke import

```bash
python -c "import personalscraper; print('ACC-05 OK')"
```

**Expected output:** `ACC-05 OK` (exit 0)
