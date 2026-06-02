# Phase 09 — Remove Lazy Inline `QBitClient` Fallbacks

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Replace the two lazy `if config.torrent.active: ... else: QBitClient(...)` blocks in `ingest/ingest.py` and `commands/pipeline.py` with reads of `ctx.torrent_client`. 1 commit.

**Tech Stack:** Python 3.11, `ast`, pytest

---

## Gate

- `_build_app_context()` boots the torrent client; `AppContext.torrent_client` field present.
- `make check` passes.

---

## Files

- Modify: `personalscraper/ingest/ingest.py`
- Modify: `personalscraper/commands/pipeline.py`
- Create: `tests/unit/test_no_inline_qbit_fallback.py`

---

## Steps

- [ ] **1. Confirm the two lazy sites exist**

```bash
cd /Users/izno/dev/PersonnalScaper && rg -t py "QBitClient\(" personalscraper/ingest/ingest.py personalscraper/commands/pipeline.py
```

Expected: 2 matches (one per file).

- [ ] **2. Write regression tests** in `tests/unit/test_no_inline_qbit_fallback.py`:

```python
"""Regression: no inline QBitClient() construction in ingest or pipeline."""
from __future__ import annotations
import ast
from pathlib import Path

def _has_inline_qbit(path: str) -> bool:
    tree = ast.parse(Path(path).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            name = f.id if isinstance(f, ast.Name) else getattr(f, "attr", "")
            if name == "QBitClient":
                return True
    return False

def test_ingest_no_inline_qbit():
    """ingest.py must not construct QBitClient inline (DESIGN D3)."""
    assert not _has_inline_qbit("personalscraper/ingest/ingest.py"), (
        "ingest.py still builds QBitClient inline — use ctx.torrent_client"
    )

def test_pipeline_no_inline_qbit():
    """pipeline.py must not construct QBitClient inline (DESIGN D3)."""
    assert not _has_inline_qbit("personalscraper/commands/pipeline.py"), (
        "pipeline.py still builds QBitClient inline — use ctx torrent_client"
    )
```

- [ ] **3. Run — confirm failures**

```bash
cd /Users/izno/dev/PersonnalScaper && pytest tests/unit/test_no_inline_qbit_fallback.py -q 2>&1 | tail -5
```

Expected: both fail (inline QBitClient still present).

- [ ] **4. Read the ingest.py lazy block** to understand context before editing

```bash
cd /Users/izno/dev/PersonnalScaper && sed -n '290,315p' personalscraper/ingest/ingest.py
```

- [ ] **5. Update `ingest/ingest.py`**

Determine how `ctx` (AppContext) is passed into the `run()` function. If the `run()` signature doesn't yet accept `ctx`, check the caller chain:

```bash
cd /Users/izno/dev/PersonnalScaper && rg -t py "ingest.run\b" personalscraper/ 2>&1 | head -10
```

Replace the lazy build block (approximately lines 294–309) with:

```python
    # Torrent client is boot-wired into AppContext (D3). None when not configured (D9).
    client = ctx.torrent_client
    if client is None:
        log.warning("ingest_no_torrent_client",
                    hint="Set torrent.active in torrent.json5 to enable torrent ingestion")
        report.error_count = 1
        report.details.append("No torrent client configured — set torrent.active in torrent.json5")
        return report
```

If `ctx` is not already a parameter of the `run()` function, add it:

```python
def run(config: ..., settings: ..., ctx: AppContext, ...) -> StepReport:
```

And update all callers accordingly (check `rg -t py "ingest.run(" personalscraper/`).

Remove now-unused imports in `ingest.py`:

```bash
cd /Users/izno/dev/PersonnalScaper && rg -t py "build_active_torrent_client\|from.*qbittorrent import.*QBitClient" personalscraper/ingest/ingest.py
```

Delete those lines.

- [ ] **6. Read the pipeline.py lazy block**

```bash
cd /Users/izno/dev/PersonnalScaper && sed -n '628,658p' personalscraper/commands/pipeline.py
```

- [ ] **7. Update `commands/pipeline.py`**

Replace the lazy build block (approximately lines 641–654) with:

```python
    # Torrent client boot-wired at AppContext level (D3/D9).
    # ctx.obj holds the legacy AppCtx; AppContext is accessed via per_step_boundary.
    # Read how torrent_client is currently threaded through and use that path.
    client = app_context.torrent_client  # adjust 'app_context' to actual variable name
    if client is None:
        console.print("[yellow]No torrent client configured.[/yellow]")
        raise typer.Exit(2)
```

The exact variable name depends on how `pipeline.py` accesses `AppContext`. Read the surrounding code first (step 6 above) to identify the correct attribute path. Remove the `TORRENT_CONNECT_ERRORS` try/except block that wrapped only the lazy build (keep the one that wraps `get_completed()`).

Remove now-unused imports at the top of the lazy block:

```bash
cd /Users/izno/dev/PersonnalScaper && rg -t py "build_active_torrent_client\|QBitClient" personalscraper/commands/pipeline.py | head -10
```

Delete those import lines.

- [ ] **8. Run regression tests**

```bash
cd /Users/izno/dev/PersonnalScaper && pytest tests/unit/test_no_inline_qbit_fallback.py -q 2>&1 | tail -5
```

Expected: both pass.

- [ ] **9. Run full suite**

```bash
cd /Users/izno/dev/PersonnalScaper && make test 2>&1 | tail -10
```

Expected: all pass; 0 collection ERRORs.

- [ ] **10. Verify no stale imports remain**

```bash
cd /Users/izno/dev/PersonnalScaper && rg -t py "QBitClient\(" personalscraper/ingest/ingest.py personalscraper/commands/pipeline.py
```

Expected: no matches (rc=1).

- [ ] **11. Full quality gate**

```bash
cd /Users/izno/dev/PersonnalScaper && make check 2>&1 | tail -10
```

Expected: exits 0.

- [ ] **12. Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add personalscraper/ingest/ingest.py personalscraper/commands/pipeline.py tests/unit/test_no_inline_qbit_fallback.py && git commit -m "refactor(torrent-write): replace lazy inline QBitClient fallbacks with ctx.torrent_client"
```
