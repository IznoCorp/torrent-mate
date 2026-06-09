# Phase 6 — ACCEPTANCE.md + `make check` gate

## Gate

**Requires Phase 5:**

```bash
make check
# Expected: exits 0
```

---

## Goal

Write `docs/features/tracker-wiring/ACCEPTANCE.md` with five executable
shell-command criteria (ACC-01 through ACC-05) that prove end-to-end boot
wiring through the real composition root, then record `make check` green as
the final criterion. Every criterion is a runnable command with documented
expected output — no prose.

---

## Files

- **Create:** `docs/features/tracker-wiring/ACCEPTANCE.md`

---

## Tasks

### Task 6.1 — Write ACCEPTANCE.md

- [ ] **Create** `docs/features/tracker-wiring/ACCEPTANCE.md` with the
      following content (write it verbatim — the commands are the acceptance
      criteria, do not paraphrase):

```markdown
# ACCEPTANCE — tracker-wiring (RP5a)

Every criterion is an executable shell command with a documented expected
output. Run from the repo root with `personalscraper` installed
(`pip install -e ".[dev]"`).

---

## ACC-01 — Valid tracker config boots; `tracker_registry` populated

Write the script below to `/tmp/acc01_tw.py`, then run `python /tmp/acc01_tw.py`.

\`\`\`python
import os, pathlib, tempfile, sys

def \_make_config_dir(d, api_key_env):
import os; os.makedirs(d, exist_ok=True); d = pathlib.Path(d)
tmp = str(d.parent)
(d/"config.json5").write_text(
f'{{"config_version":1,"overlays":["paths.json5","disks.json5",'
        f'"patterns.json5","tracker.json5"],'
        f'"paths":{{"torrent_complete_dir":"{tmp}/c","staging_dir":"{tmp}/s",'
        f'"data_dir":"{tmp}/dt"}}}}')
(d/"paths.json5").write_text("{}")
(d/"disks.json5").write_text(
f'{{"disks":[{{"id":"a","path":"{tmp}/disk","categories":["movies"]}}]}}')
(d/"patterns.json5").write_text(
'{"staging_dirs":['
'{"id":1,"name":"movies","file_type":"movie"},'
'{"id":2,"name":"tvshows","file_type":"tvshow"},'
'{"id":3,"name":"ebooks","file_type":"ebook"},'
'{"id":4,"name":"audio","file_type":"audio"},'
'{"id":5,"name":"apps","file_type":"app"},'
'{"id":6,"name":"android","file_type":"app"},'
'{"id":97,"name":"temp","file_type":null,"role":"ingest"},'
'{"id":98,"name":"autres","file_type":"other"}]}')
(d/"tracker.json5").write_text(
'{"tracker":{"providers":{"lacale":{"enabled":true}},'
'"priority":["lacale"],'
'"max_total_results":50,"max_per_tracker":30,"timeout_per_tracker":15}}')
return d

with tempfile.TemporaryDirectory() as tmp:
cfg_dir = \_make_config_dir(f"{tmp}/cfg", None)
env = dict(os.environ)
env["LACALE_API_KEY"] = "test_key_acc01"

    from personalscraper.conf.loader import load_config_dir
    from personalscraper.config import Settings
    from personalscraper.cli_helpers import _build_app_context
    from personalscraper.api.tracker._registry import TrackerRegistry

    config = load_config_dir(cfg_dir)
    settings = Settings()

    import unittest.mock as mock
    # Patch HttpTransport so no real network connection is made.
    with mock.patch("personalscraper.api.tracker._factory.HttpTransport"), \
         mock.patch("personalscraper.api.metadata.registry.ProviderRegistry"), \
         mock.patch.dict(os.environ, {"LACALE_API_KEY": "test_key_acc01"}):
        ctx = _build_app_context(config, settings)

    assert ctx.tracker_registry is not None, "tracker_registry must not be None"
    assert isinstance(ctx.tracker_registry, TrackerRegistry)
    assert "lacale" in ctx.tracker_registry._trackers, \
        f"expected lacale in trackers, got: {list(ctx.tracker_registry._trackers)}"
    print("ACC-01 OK — valid tracker config boots, tracker_registry populated with lacale")

\`\`\`

**Expected output:**
```

ACC-01 OK — valid tracker config boots, tracker_registry populated with lacale

```

---

## ACC-02 — Enabled tracker with absent API key → non-zero exit, names the tracker

Write the script below to `/tmp/acc02_tw.py`, then run `python /tmp/acc02_tw.py`.

\`\`\`python
import os, pathlib, tempfile, sys

def _make_config_dir(d):
    import os; os.makedirs(d, exist_ok=True); d = pathlib.Path(d)
    tmp = str(d.parent)
    (d/"config.json5").write_text(
        f'{{"config_version":1,"overlays":["paths.json5","disks.json5",'
        f'"patterns.json5","tracker.json5"],'
        f'"paths":{{"torrent_complete_dir":"{tmp}/c","staging_dir":"{tmp}/s",'
        f'"data_dir":"{tmp}/dt"}}}}')
    (d/"paths.json5").write_text("{}")
    (d/"disks.json5").write_text(
        f'{{"disks":[{{"id":"a","path":"{tmp}/disk","categories":["movies"]}}]}}')
    (d/"patterns.json5").write_text(
        '{"staging_dirs":['
        '{"id":1,"name":"movies","file_type":"movie"},'
        '{"id":2,"name":"tvshows","file_type":"tvshow"},'
        '{"id":3,"name":"ebooks","file_type":"ebook"},'
        '{"id":4,"name":"audio","file_type":"audio"},'
        '{"id":5,"name":"apps","file_type":"app"},'
        '{"id":6,"name":"android","file_type":"app"},'
        '{"id":97,"name":"temp","file_type":null,"role":"ingest"},'
        '{"id":98,"name":"autres","file_type":"other"}]}')
    (d/"tracker.json5").write_text(
        '{"tracker":{"providers":{"lacale":{"enabled":true}},'
        '"priority":["lacale"],'
        '"max_total_results":50,"max_per_tracker":30,"timeout_per_tracker":15}}')
    return d

with tempfile.TemporaryDirectory() as tmp:
    cfg_dir = _make_config_dir(f"{tmp}/cfg")
    # LACALE_API_KEY intentionally absent from env:
    clean_env = {k: v for k, v in os.environ.items() if k != "LACALE_API_KEY"}

    from personalscraper.conf.loader import load_config_dir
    from personalscraper.config import Settings
    from personalscraper.cli_helpers import _build_app_context
    from personalscraper.api.tracker._errors import TrackerConfigError

    config = load_config_dir(cfg_dir)
    settings = Settings()

    import unittest.mock as mock
    with mock.patch("personalscraper.api.metadata.registry.ProviderRegistry"), \
         mock.patch.dict(os.environ, clean_env, clear=True):
        try:
            _build_app_context(config, settings)
            print("ERROR: expected TrackerConfigError but got none", file=sys.stderr)
            sys.exit(1)
        except TrackerConfigError as e:
            assert any(i.code == "missing_credentials" for i in e.issues), \
                f"expected missing_credentials issue, got: {[i.code for i in e.issues]}"
            assert any("lacale" in (i.provider or "") for i in e.issues), \
                f"expected lacale in issues, got: {[i.provider for i in e.issues]}"
            assert any("LACALE_API_KEY" in i.message for i in e.issues), \
                f"expected LACALE_API_KEY named in message, got: {[i.message for i in e.issues]}"
            print("ACC-02 OK — missing API key raises TrackerConfigError naming the tracker and key")
\`\`\`

**Expected output:**
```

ACC-02 OK — missing API key raises TrackerConfigError naming the tracker and key

````

---

## ACC-03 — Default config (all trackers disabled) boots silently, registry empty

```bash
python - <<'EOF'
from personalscraper.conf.models.api_config import TrackerConfig, TrackerProviderConfig, RankingConfig
from personalscraper.api.tracker._factory import build_tracker_registry
from personalscraper.core.event_bus import EventBus
from personalscraper.api.transport._policy import CircuitPolicy
from unittest.mock import MagicMock

cfg = TrackerConfig(
    providers={"lacale": TrackerProviderConfig(enabled=False),
               "c411": TrackerProviderConfig(enabled=False)},
    priority=[],
)
registry = build_tracker_registry(
    cfg, RankingConfig(),
    settings=MagicMock(),
    event_bus=EventBus(),
    cb_policy=CircuitPolicy(failure_threshold=5, cooldown_seconds=1.0),
    env={},
)
assert registry._trackers == {}, f"expected empty registry, got {registry._trackers}"
print("ACC-03 OK — default all-disabled config boots silently, registry empty")
EOF
````

**Expected output:** `ACC-03 OK — default all-disabled config boots silently, registry empty` (exit 0)

---

## ACC-04 — `disabled_in_priority` warning: boots OK, only active tracker in registry

```bash
python - <<'EOF'
from personalscraper.conf.models.api_config import TrackerConfig, TrackerProviderConfig, RankingConfig
from personalscraper.api.tracker._factory import build_tracker_registry
from personalscraper.api.tracker._registry import TrackerRegistry
from personalscraper.core.event_bus import EventBus
from personalscraper.api.transport._policy import CircuitPolicy
from unittest.mock import MagicMock, patch

cfg = TrackerConfig(
    providers={
        "lacale": TrackerProviderConfig(enabled=True),
        "c411":   TrackerProviderConfig(enabled=False),
    },
    priority=["lacale", "c411"],   # c411 disabled but listed — warning case
)

class _Stub:
    provider_name = "lacale"
    @classmethod
    def policy(cls, k): return MagicMock()
    def __init__(self, t): self._transport = t
    def search(self, *a, **kw): return []

with patch("personalscraper.api.tracker._factory._TRACKER_CLASSES",
           {"lacale": "personalscraper.api.tracker._factory:_WILL_BE_PATCHED"}), \
     patch("personalscraper.api.tracker._factory._resolve_tracker_class",
           return_value=_Stub), \
     patch("personalscraper.api.tracker._factory.HttpTransport"):
    registry = build_tracker_registry(
        cfg, RankingConfig(),
        settings=MagicMock(),
        event_bus=EventBus(),
        cb_policy=CircuitPolicy(failure_threshold=5, cooldown_seconds=1.0),
        env={"LACALE_API_KEY": "key_acc04"},
    )

assert isinstance(registry, TrackerRegistry), "expected TrackerRegistry"
assert "lacale" in registry._trackers, "lacale must be active"
assert "c411" not in registry._trackers, "c411 is disabled, must not be built"
print("ACC-04 OK — disabled_in_priority boots OK, only active tracker in registry")
EOF
```

**Expected output:** `ACC-04 OK — disabled_in_priority boots OK, only active tracker in registry` (exit 0)

---

## ACC-05 — `make check` green (lint + mypy + tests + module-size)

```bash
make check
```

**Expected output:** exits 0 — ruff + mypy lint, full test suite (`NNNN passed`),
module-size budget, typed-api guardrails all pass. The 4 pre-existing
`TrackerRegistry` dict-ctor tests and all new tracker-wiring tests are included
in `NNNN passed`.

````

- [ ] Write `docs/features/tracker-wiring/ACCEPTANCE.md` with the content above.

---

### Task 6.2 — Re-exercise all criteria

Run each criterion in order and confirm the expected output:

- [ ] `python /tmp/acc01_tw.py` → `ACC-01 OK …`
- [ ] `python /tmp/acc02_tw.py` → `ACC-02 OK …`
- [ ] Run the ACC-03 heredoc → `ACC-03 OK …` (exit 0)
- [ ] Run the ACC-04 heredoc → `ACC-04 OK …` (exit 0)
- [ ] `make check` → exits 0

---

### Task 6.3 — Commit

```bash
git add docs/features/tracker-wiring/ACCEPTANCE.md
git commit -m "chore(tracker-wiring): phase 6 gate — ACCEPTANCE.md + make check green"
````

---

## Gate exit checklist

- [ ] All five ACC-NN criteria pass with the documented expected output
- [ ] `make check` → exits 0
- [ ] `python -c "import personalscraper"` → exit 0
- [ ] Commit SHA recorded
