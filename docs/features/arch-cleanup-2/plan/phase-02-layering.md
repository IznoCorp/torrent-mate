# Phase 2 — Layering: relocate shared primitives down

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> or `superpowers:executing-plans` to implement this phase step-by-step.

**Goal:** Remove the `core/` → `api/` and `conf/` → `api/` upward import inversions by relocating
`CircuitOpenError`, `ApiError`, `MediaType` into a new `core/_contracts.py`, and `Ranking*` config
models into a new `conf/models/_ranking.py`. Re-exports in `api/_contracts.py` and
`api/tracker/_ranking.py` preserve all 35+ existing downstream import paths unchanged.

**Architecture:** Create two new "neutral home" modules at the correct layer. Re-point the handful
of `core/`+`conf/` modules that currently import upward. Add `api/` re-exports so every downstream
importer keeps working without modification. Lock the invariant with an AST-based layering guard test.

**Tech Stack:** Python stdlib only for `core/_contracts.py` (no upward deps); Pydantic for
`conf/models/_ranking.py`; `ast` module for the layering guard test; pytest.

---

## Gate (pre-conditions from Phase 1)

Phase 2 may be implemented independently of Phase 1 (no shared state dependency), but if
Phase 1 was completed first, its gate must have passed:

```bash
make check   # must exit 0
python -c "from personalscraper.core.event_bus import Event; assert hasattr(Event, 'schema_version')"
# no output = ok (schema_version present)
```

---

## Files

| Action | Path                                                                 |
| ------ | -------------------------------------------------------------------- |
| Create | `personalscraper/core/_contracts.py`                                 |
| Create | `personalscraper/conf/models/_ranking.py`                            |
| Modify | `personalscraper/core/circuit.py` (lines ~35, ~332)                  |
| Modify | `personalscraper/conf/classifier.py` (line ~22)                      |
| Modify | `personalscraper/conf/models/api_config.py` (line ~11)               |
| Modify | `personalscraper/api/_contracts.py` (add re-exports at top)          |
| Modify | `personalscraper/api/tracker/_ranking.py` (add re-exports at bottom) |
| Create | `tests/architecture/test_layering.py`                                |

---

## Sub-phase 2.1 — Create `core/_contracts.py` and `conf/models/_ranking.py`

### Task 1: Write the failing layering guard test

- [ ] **Step 2.1.1: Check for any pre-existing layering test that might conflict**

```bash
rg -t py "core.*import\|conf.*import\|upward\|acyclic\|layer" tests/architecture/
# Examine output. If a test already asserts the false "no upward imports" invariant,
# update it rather than creating a new conflicting test.
```

- [ ] **Step 2.1.2: Write `tests/architecture/test_layering.py`**

```python
"""AST-based layering guard: core/ and conf/ must not import upward (arch-cleanup-2 Phase 2).

Enforces the architecture invariant from docs/reference/architecture.md:
core/ and conf/ are the lowest layers and must not import from api/, scraper/,
pipeline/, dispatch/, verify/, library/, indexer/, or trailers/.

Allow-listed exceptions (documented boundaries):
- personalscraper.logger — leaf utility, allow-listed in core/ and conf/
- core/app_context.py importing personalscraper.api.metadata.registry
  under TYPE_CHECKING — the AppContext boundary, already tested separately
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PACKAGE_ROOT = _REPO_ROOT / "personalscraper"

# Upward targets that core/ and conf/ must never import at runtime.
_FORBIDDEN_PREFIXES = (
    "personalscraper.api",
    "personalscraper.scraper",
    "personalscraper.pipeline",
    "personalscraper.dispatch",
    "personalscraper.verify",
    "personalscraper.library",
    "personalscraper.indexer",
    "personalscraper.trailers",
)

# Modules that are structural exceptions — checked independently elsewhere.
_ALLOWED_MODULES = {
    "personalscraper/core/app_context.py",  # TYPE_CHECKING registry import — AppContext boundary
}


def _is_type_checking_block(node: ast.AST, tree: ast.Module) -> bool:
    """Return True if ``node`` is nested inside an ``if TYPE_CHECKING:`` block."""
    for top in ast.walk(tree):
        if isinstance(top, ast.If):
            test = top.test
            is_tc = (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
                isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
            )
            if is_tc:
                # Walk body and orelse — if node is in this subtree it's guarded.
                for child in ast.walk(top):
                    if child is node:
                        return True
    return False


def _collect_violations(py_file: Path) -> list[str]:
    """Return list of violation strings for ``py_file``."""
    rel = py_file.relative_to(_REPO_ROOT).as_posix()
    if rel in _ALLOWED_MODULES:
        return []
    source = py_file.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(py_file))
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            # Determine the full module name being imported.
            if isinstance(node, ast.ImportFrom) and node.module:
                module = node.module
                # Reconstruct absolute path from relative imports.
                if node.level and node.level > 0:
                    # Relative import — resolve against the file's package.
                    pkg_parts = rel.replace(".py", "").replace("/", ".").split(".")
                    base = pkg_parts[: -(node.level)]
                    module = ".".join(base) + ("." + module if module else "")
            elif isinstance(node, ast.Import):
                module = node.names[0].name
            else:
                continue
            # Check against forbidden prefixes.
            for prefix in _FORBIDDEN_PREFIXES:
                if module == prefix or module.startswith(prefix + "."):
                    # Allow if guarded by TYPE_CHECKING.
                    if _is_type_checking_block(node, tree):
                        break
                    violations.append(
                        f"{rel}:{node.lineno}: imports {module!r}"
                    )
                    break
    return violations


def test_core_does_not_import_upward() -> None:
    """No module under core/ imports api/, scraper/, or any upper layer at runtime."""
    core_root = _PACKAGE_ROOT / "core"
    violations: list[str] = []
    for py_file in sorted(core_root.rglob("*.py")):
        violations.extend(_collect_violations(py_file))
    assert not violations, (
        "core/ has upward import leaks (fix by importing from core._contracts):\n"
        + "\n".join(violations)
    )


def test_conf_does_not_import_upward() -> None:
    """No module under conf/ imports api/, scraper/, or any upper layer at runtime."""
    conf_root = _PACKAGE_ROOT / "conf"
    violations: list[str] = []
    for py_file in sorted(conf_root.rglob("*.py")):
        violations.extend(_collect_violations(py_file))
    assert not violations, (
        "conf/ has upward import leaks (fix by importing from core._contracts "
        "or conf/models/_ranking.py):\n" + "\n".join(violations)
    )


def test_core_contracts_has_no_upward_deps() -> None:
    """core/_contracts.py imports nothing from personalscraper (only stdlib/enum)."""
    contracts_file = _PACKAGE_ROOT / "core" / "_contracts.py"
    assert contracts_file.exists(), "core/_contracts.py does not exist"
    source = contracts_file.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom) and node.module:
                module = node.module
            elif isinstance(node, ast.Import):
                module = node.names[0].name
            else:
                continue
            assert not module.startswith("personalscraper."), (
                f"core/_contracts.py:{node.lineno}: must not import "
                f"from personalscraper — found {module!r}. "
                "Only stdlib and enum are allowed."
            )
```

- [ ] **Step 2.1.3: Run the layering test — expect failures**

```bash
python -m pytest tests/architecture/test_layering.py -v
# EXPECT: FAILED — violations in core/circuit.py, conf/classifier.py, conf/models/api_config.py
```

### Task 2: Create `core/_contracts.py`

- [ ] **Step 2.1.4: Create `personalscraper/core/_contracts.py`**

This file may only import from stdlib and `enum`. It defines the canonical symbols
that currently live in `api/_contracts.py` but logically belong at the core layer.

```python
"""Core-layer primitive contracts: errors and media type.

These symbols are defined here (the lowest layer) and re-exported from
``personalscraper.api._contracts`` for backward compatibility. This module
may only import from the Python standard library and ``enum`` — no upward
dependencies on ``api/``, ``conf/``, or any sibling personalscraper package.

Implements arch-cleanup-2 Phase 2 (layering relocation).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MediaType(str, Enum):
    """Canonical media type used across all metadata- and tracker-family APIs.

    Inherits from ``str`` so existing equality checks (``media_type == "tv"``),
    dict keys, and JSON serialization keep working unchanged.

    The legacy library/dispatch/scraper layers historically used ``"tvshow"``
    instead of ``"tv"``; :meth:`from_legacy` is the single coercion entry
    point that maps both vocabularies into this enum.

    ``__str__`` returns the wire value (``"movie"`` / ``"tv"``) rather than
    the enum repr. This matches Python 3.11+ ``StrEnum`` semantics.
    """

    MOVIE = "movie"
    TV = "tv"

    def __str__(self) -> str:
        """Return the wire value (e.g. ``'movie'``)."""
        return self.value

    @classmethod
    def from_legacy(cls, value: str) -> "MediaType":
        """Coerce legacy ``'tvshow'`` strings to the canonical enum member.

        Args:
            value: A raw string like ``'movie'``, ``'tv'``, or ``'tvshow'``.

        Returns:
            The corresponding ``MediaType`` member.

        Raises:
            ValueError: If ``value`` cannot be mapped to a known member.
        """
        if value == "tvshow":
            return cls.TV
        return cls(value)


@dataclass
class ApiError(Exception):
    """Unified API error raised by every provider on transport or response failure.

    Uses ``@dataclass`` to match the existing definition in ``api/_contracts.py``
    and preserve the auto-generated ``__eq__`` that tests rely on.
    ``dataclasses`` is stdlib — no upward dependency introduced.

    Attributes:
        provider: Provider name (e.g. ``"TMDB"``, ``"TVDB"``).
        http_status: HTTP status code from the response.
        provider_code: Provider-specific error code, if any.
        message: Human-readable error message.
    """

    provider: str
    http_status: int
    provider_code: int = 0
    message: str = ""

    def __str__(self) -> str:
        """Return a concise error string."""
        code = f" provider_code={self.provider_code}" if self.provider_code else ""
        return f"{self.provider} API {self.http_status}{code}: {self.message}"


class CircuitOpenError(Exception):
    """Raised when a call is attempted on an OPEN circuit.

    Attributes:
        provider: Name of the unavailable provider.
        remaining_seconds: Seconds remaining until cooldown expires.
    """

    def __init__(self, provider: str, remaining_seconds: float) -> None:
        """Initialise CircuitOpenError.

        Args:
            provider: Name of the unavailable provider.
            remaining_seconds: Seconds until the circuit may transition to HALF_OPEN.
        """
        self.provider = provider
        self.remaining_seconds = remaining_seconds
        super().__init__(
            f"Circuit breaker OPEN for {provider} ({remaining_seconds:.0f}s remaining)"
        )
```

### Task 3: Create `conf/models/_ranking.py`

- [ ] **Step 2.1.5: Create `personalscraper/conf/models/_ranking.py`**

Copy the four Pydantic models from `api/tracker/_ranking.py` into their new home.
The models may import from `pydantic` and `personalscraper.api._units` (upward dep
on `api._units` is acceptable for a config model parsing byte sizes).

```python
"""Ranking config models — config-layer home (arch-cleanup-2 Phase 2, Option A).

These Pydantic models are parsed from config files (``api_config.json5``
``ranking`` section). They live here in ``conf/`` because they are
configuration-layer objects, not API-transport objects.

``personalscraper.api.tracker._ranking`` re-exports them for backward
compatibility with existing runtime consumers of the tracker package.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from personalscraper.api._units import ByteSize


class ThresholdEntry(BaseModel):
    """A size-or-count threshold with a score value.

    Attributes:
        at: Threshold value — int, float, or human-readable string like ``"1GB"``.
        score: Score awarded when the field meets this threshold.
    """

    at: int
    score: int

    @field_validator("at", mode="before")
    @classmethod
    def _parse_at(cls, v: object) -> int:
        """Coerce string byte-size values (e.g. ``'1GB'``) to integer bytes.

        Args:
            v: Raw value from config (str, ByteSize, or int-like).

        Returns:
            Integer byte count.
        """
        if isinstance(v, str):
            return ByteSize.parse(v).bytes
        if isinstance(v, ByteSize):
            return v.bytes
        return int(v)  # type: ignore[call-overload,no-any-return]


class RankingCriterion(BaseModel):
    """A single ranking criterion for scoring tracker results.

    Attributes:
        field: The field to score (e.g. ``"resolution"``, ``"seeders"``).
        weight: Multiplier applied to this criterion's score.
        values: Map of field value → score (for categorical fields).
        thresholds: Ordered thresholds for numeric fields.
        prefer: For threshold-based fields, whether higher or lower is better.
    """

    field: str
    weight: float = 1.0
    values: dict[str, int] | None = None
    thresholds: list[ThresholdEntry] | None = None
    prefer: Literal["higher", "lower"] | None = None


class RankingBonuses(BaseModel):
    """Bonus points for torrent properties.

    Attributes:
        freeleech: Bonus points for freeleech torrents.
        silverleech: Bonus points for silverleech (partial freeleech) torrents.
    """

    freeleech: int = 10
    silverleech: int = 5


class RankingConfig(BaseModel):
    """Full ranking configuration consumed by the ranking engine.

    Attributes:
        criteria: Ordered list of :class:`RankingCriterion` to evaluate.
        bonuses: Bonus point configuration.
        min_seeders: Minimum seeders required for a result to be considered.
    """

    criteria: list[RankingCriterion] = Field(default_factory=list)
    bonuses: RankingBonuses = Field(default_factory=RankingBonuses)
    min_seeders: int = 1
```

---

## Sub-phase 2.2 — Re-point `core/` and `conf/` importers; add `api/` re-exports

### Task 4: Fix the upward imports in `core/circuit.py`

- [ ] **Step 2.2.1: Update imports in `personalscraper/core/circuit.py`**

Lines ~35 and ~332 currently import from `personalscraper.api._contracts`. Change both to:

```python
# Before (line ~35):
from personalscraper.api._contracts import CircuitOpenError

# After:
from personalscraper.core._contracts import CircuitOpenError
```

```python
# Before (line ~332, local import inside a function/method):
from personalscraper.api._contracts import ApiError

# After:
from personalscraper.core._contracts import ApiError
```

Verify after editing:

```bash
rg -t py "from personalscraper.api._contracts import" personalscraper/core/circuit.py
# EXPECT: no output (zero matches)
```

### Task 5: Fix the upward import in `conf/classifier.py`

- [ ] **Step 2.2.2: Update import in `personalscraper/conf/classifier.py`**

Line ~22 currently imports `MediaType` from `api._contracts`. Change to:

```python
# Before:
from personalscraper.api._contracts import MediaType

# After:
from personalscraper.core._contracts import MediaType
```

Verify:

```bash
rg -t py "from personalscraper.api._contracts import" personalscraper/conf/classifier.py
# EXPECT: no output
```

### Task 6: Fix the upward import in `conf/models/api_config.py`

- [ ] **Step 2.2.3: Update import in `personalscraper/conf/models/api_config.py`**

Line ~11 currently imports `Ranking*` from `api.tracker._ranking`. Change to:

```python
# Before:
from personalscraper.api.tracker._ranking import RankingBonuses, RankingConfig, RankingCriterion, ThresholdEntry

# After:
from personalscraper.conf.models._ranking import RankingBonuses, RankingConfig, RankingCriterion, ThresholdEntry
```

Verify:

```bash
rg -t py "from personalscraper.api.tracker._ranking import" personalscraper/conf/
# EXPECT: no output
```

### Task 7: Add re-exports to `api/_contracts.py`

- [ ] **Step 2.2.4: Add re-exports at the top of `personalscraper/api/_contracts.py`**

The canonical definitions now live in `core._contracts`. The `api/_contracts.py` module
re-exports them so all 35 existing downstream importers keep working without change.

At the top of the file (after the module docstring and existing imports), add:

```python
# Re-export from the canonical core-layer home (arch-cleanup-2 Phase 2).
# All 35 downstream importers of personalscraper.api._contracts continue to work
# unchanged — the symbols are still accessible via this path.
from personalscraper.core._contracts import ApiError, CircuitOpenError, MediaType  # noqa: F401
```

Then remove the original class definitions of `MediaType`, `ApiError`, and
`CircuitOpenError` from `api/_contracts.py` (they are now defined in `core/_contracts.py`).

**Caution:** `api/_contracts.py` currently has `MediaType` as a `str`-`Enum` class and
`ApiError` as a `@dataclass`. The new `core/_contracts.py` definitions above use plain
`class ApiError(Exception)` with `__init__`. Before deleting from `api/_contracts.py`,
run `make test` to catch any test relying on `@dataclass` equality for `ApiError`.
If tests fail, add `__eq__` to `core._contracts.ApiError` matching the dataclass
behaviour, or keep `@dataclass` decoration on `ApiError` in `core._contracts.py`.

Verify re-export works:

```bash
python -c "from personalscraper.api._contracts import CircuitOpenError, ApiError, MediaType; print('ok')"
# EXPECT: ok
```

### Task 8: Add re-exports to `api/tracker/_ranking.py`

- [ ] **Step 2.2.5: Update `personalscraper/api/tracker/_ranking.py`**

Replace the four class _definitions_ with re-exports from `conf/models/_ranking.py`.
Keep the ranking _engine_ functions (`rank()`, etc.) that live in the same file — do not
move those.

At the top (after the module docstring), replace the class definitions with:

```python
# Re-export Ranking* config models from their canonical config-layer home
# (arch-cleanup-2 Phase 2, Option A). Runtime callers of
# personalscraper.api.tracker._ranking keep working unchanged.
from personalscraper.conf.models._ranking import (  # noqa: F401
    RankingBonuses,
    RankingConfig,
    RankingCriterion,
    ThresholdEntry,
)
```

Verify:

```bash
python -c "from personalscraper.api.tracker._ranking import RankingBonuses, RankingConfig, RankingCriterion, ThresholdEntry; print('ok')"
# EXPECT: ok
```

---

## Sub-phase 2.3 — Residual grep, run gate

### Task 9: Residual import grep

- [ ] **Step 2.3.1: Verify no core/ or conf/ module still imports upward**

```bash
rg -t py '^from personalscraper\.(api|scraper|pipeline|dispatch|verify|library|indexer|trailers)' \
    personalscraper/core/ personalscraper/conf/
# EXPECT: no output
# (app_context.py TYPE_CHECKING import is allowed — if it appears, verify it is
#  inside an `if TYPE_CHECKING:` block, not a runtime import)
```

- [ ] **Step 2.3.2: Verify all 35 api.\_contracts importers still resolve**

```bash
python -m pytest -x -q --tb=short 2>&1 | head -30
# EXPECT: collection completes without ERROR; tests pass
```

- [ ] **Step 2.3.3: Residual grep for old symbol anchors**

```bash
# Symbols moved out of api/_contracts.py — confirm only re-export lines remain
rg -t py "class MediaType\|class ApiError\|class CircuitOpenError" personalscraper/api/_contracts.py
# EXPECT: no output (definitions removed; re-import lines don't start with 'class')

# Symbols moved out of api/tracker/_ranking.py
rg -t py "class ThresholdEntry\|class RankingCriterion\|class RankingBonuses\|class RankingConfig" personalscraper/api/tracker/_ranking.py
# EXPECT: no output (definitions removed; re-import lines don't start with 'class')
```

- [ ] **Step 2.3.4: Run the layering guard test**

```bash
python -m pytest tests/architecture/test_layering.py -v
# EXPECT: all passed
```

- [ ] **Step 2.3.5: Run full gate**

```bash
make lint && make test && make check
# EXPECT: exit 0 for all three
```

- [ ] **Step 2.3.6: Commit**

```bash
git add personalscraper/core/_contracts.py \
        personalscraper/conf/models/_ranking.py \
        personalscraper/core/circuit.py \
        personalscraper/conf/classifier.py \
        personalscraper/conf/models/api_config.py \
        personalscraper/api/_contracts.py \
        personalscraper/api/tracker/_ranking.py \
        tests/architecture/test_layering.py
git commit -m "refactor(arch-cleanup-2): relocate CircuitOpenError/ApiError/MediaType/Ranking* down; add layering guard"
```

---

## Phase Gate

```bash
make lint && make test && make check
# EXPECT: exit 0

rg -t py '^from personalscraper\.(api|scraper|pipeline|dispatch|verify|library|indexer|trailers)' \
    personalscraper/core/ personalscraper/conf/ | rg -v 'app_context.py' | rg -v 'TYPE_CHECKING'
# EXPECT: no output (exit 1)

python -m pytest tests/architecture/test_layering.py -q
# EXPECT: passed

python3 scripts/check-module-size.py
# EXPECT: exit 0; only two WARN lines
```

---

## Acceptance Criteria (Phase 2 subset)

```bash
# ACC-07 — core/ and conf/ no longer import upward
rg -t py '^from personalscraper\.(api|scraper|pipeline|dispatch|verify|library|indexer|trailers)' \
    personalscraper/core/ personalscraper/conf/ | rg -v 'app_context.py' | rg -v 'TYPE_CHECKING'
# EXPECT: no output, exit 1

# ACC-08 — layering guard test passes
python -m pytest tests/architecture/test_layering.py -q
# EXPECT: exit 0; "passed" in output

# ACC-09 — api._contracts re-export keeps the legacy path working
python -c "from personalscraper.api._contracts import CircuitOpenError, ApiError, MediaType; print('ok')"
# EXPECT: exit 0; stdout: ok

# ACC-10 — Ranking* re-export keeps the legacy api path working
python -c "from personalscraper.api.tracker._ranking import RankingBonuses, RankingConfig, RankingCriterion, ThresholdEntry; print('ok')"
# EXPECT: exit 0; stdout: ok

# ACC-14 — module-size guardrail unchanged
python3 scripts/check-module-size.py
# EXPECT: exit 0; exactly two WARN lines (movie_service.py, library/scanner.py)

# ACC-17 — smoke import
python -c "import personalscraper; print('ok')"
# EXPECT: exit 0; stdout: ok
```
