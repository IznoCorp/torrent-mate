# Shell Mobile — Phase 0: Parity Tooling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the machinery that makes "the app matches the prototype" a measurable, blocking build condition — before a single page is rebuilt.

**Architecture:** The prototype `frontend/maquette/refonte.html` is the design reference. Phase 0 adds four guards around it: a **CSS extractor** that generates `frontend/src/styles/ps/app-surface.css` from the prototype's application CSS block (never retyped by hand), a **drift guard** that fails when the generated file is edited, a **class-coverage guard** that fails on dead CSS or on any class the allowlist does not cover, and a **parity probe** that measures the prototype against a locally built app and diffs geometry plus a fixed computed-style subset. All four run in `make check-frontend` and in CI.

**Tech Stack:** Python 3.11 (scripts + pytest), Playwright for Python (headless Chromium), Vite 7 / React 19 / TypeScript (the app), vitest (frontend unit tests), GNU Make, GitHub Actions.

## Global Constraints

- **The prototype is the source.** A design change starts in `frontend/maquette/refonte.html`; the code follows. A divergence between the app and the prototype is a defect **in the app**, unless the prototype was amended first with the reason written down. Recorded as **§15** of `docs/reference/product-intent.md` and in the root `CLAUDE.md`.
- **CSS is extracted, never retyped.** Editing `frontend/src/styles/ps/app-surface.css` by hand is the defect, not a shortcut.
- **Scope class is `.tm`.** Every exported rule is emitted under it. The previous mission's `.mq` scope (`frontend/src/styles/ps/maquette-acquisition.css`) stays untouched in this phase.
- **Allowlist, never blocklist.** `frontend/maquette/regions.json` → `exportedSelectors` is the only thing exported. A prototype-only helper can never silently reach production.
- **Probe emulation is fixed:** viewport 390 × 844, `deviceScaleFactor: 2`, `isMobile: true`, `hasTouch: true`. Assert `document.documentElement.clientWidth === 390` before measuring.
- **Never bind a local server to 8710 or 8711** — the reverse proxy routes production and staging there. Use 8899 for the prototype and Vite's own preview port for the app.
- **Search safety:** every `rg` invocation carries a type or glob filter (`--type py`, `-g '*.py'`). Without one it scans a 14 GB fixture tree and exhausts RAM.
- **Network safety:** every `curl` / `wget` carries `--connect-timeout 10 --max-time 30`.
- **Comment language:** every comment in `frontend/maquette/` and in the scripts this plan creates is written **in English**, with no reference to a work session, a phase number, or a dated decision. Interface copy quoted inside a comment stays in French, because that is what the screen says.
- **Commits** follow Conventional Commits with `(shell-mobile)` as scope. No AI attribution (`Co-Authored-By`, `Claude`, `Anthropic`) — a pre-commit hook rejects it.
- **Version bump on every PR** (standing operator rule).

---

## File Structure

| File                                           | Responsibility                                                                                                                                                                                           |
| ---------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `scripts/extract-maquette-css.py`              | **Create.** Reads the prototype, lifts its application CSS block, keeps only allowlisted selectors, scopes them under `.tm`, writes the generated stylesheet. Also runs in `--check` mode (drift guard). |
| `scripts/check-maquette-classes.py`            | **Create.** Classifies every class defined in the prototype's application CSS block as app / harness / transient / dead. Fails on dead CSS or on a class missing from the allowlist.                     |
| `scripts/parity-probe.py`                      | **Create.** Walks `regions.json` in two headless contexts — the prototype and a local production build — and diffs geometry plus a fixed computed-style subset.                                          |
| `frontend/src/styles/ps/app-surface.css`       | **Generated.** Never hand-edited. Imported by `frontend/src/styles/ps/styles.css`.                                                                                                                       |
| `frontend/src/styles/ps/styles.css`            | **Modify.** Add the import of the generated stylesheet.                                                                                                                                                  |
| `tests/scripts/test_extract_maquette_css.py`   | **Create.** Unit tests for the extractor, on small fixture HTML — never on the 10 MB prototype.                                                                                                          |
| `tests/scripts/test_check_maquette_classes.py` | **Create.** Unit tests for the class-coverage guard.                                                                                                                                                     |
| `tests/scripts/test_parity_probe.py`           | **Create.** Unit tests for the probe's pure parts (diffing, allowlist matching); the browser run is exercised by the make target, not by pytest.                                                         |
| `Makefile`                                     | **Modify.** Wire the three guards into `check-frontend`.                                                                                                                                                 |
| `.github/workflows/ci.yml`                     | **Modify.** Install Playwright's Chromium and run the guards.                                                                                                                                            |
| `pyproject.toml`                               | **Modify.** Declare `playwright` in the dev extra.                                                                                                                                                       |
| `docs/reference/web-ui.md`                     | **Modify.** Document the four guards and how to run them locally.                                                                                                                                        |

**Read before starting:**

- `docs/superpowers/specs/2026-08-10-refonte-mobile-quatre-pages-design.md` — §7 is the parity methodology and is the part that matters.
- `frontend/maquette/README.md` — the prototype's contract, the 47 named states, the rule set, and the traps already paid for.
- `frontend/maquette/regions.json` — the extraction contract and the measurement map.

---

### Task 1: The CSS extractor

Generates `frontend/src/styles/ps/app-surface.css` from the prototype. This is the task the whole phase rests on: everything downstream assumes the shipped CSS is a mechanical projection of the prototype.

**Files:**

- Create: `scripts/extract-maquette-css.py`
- Create: `tests/scripts/test_extract_maquette_css.py`

**Interfaces:**

- Consumes: `frontend/maquette/refonte.html` (the prototype), `frontend/maquette/regions.json` (`scope`, `exportedSelectors`, `target`).
- Produces:
  - `extract(html: str, exported: set[str], scope: str) -> str` — pure function, returns the generated stylesheet text.
  - `_application_block(html: str) -> str` — returns the application CSS block, comments intact.
  - `_scope_selector(selector: str, scope: str) -> str` — returns the selector prefixed with the scope class.
  - `_is_exported(selector: str, exported: set[str]) -> bool` — True when every class the selector mentions is allowlisted.
  - CLI: `python scripts/extract-maquette-css.py [--check] [--source PATH] [--regions PATH] [--out PATH]`. Exit 0 on success; exit 1 in `--check` mode when the on-disk file differs from what would be generated.

- [ ] **Step 1: Write the failing test**

Create `tests/scripts/test_extract_maquette_css.py`:

```python
"""Tests for the maquette CSS extractor.

The extractor is what makes « the CSS is generated, never retyped » true. These
tests run on small fixture stylesheets, never on the real prototype: a test that
needs a 10 MB file to say something is a test nobody runs.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "extract-maquette-css.py"

sys.path.insert(0, str(ROOT / "scripts"))


def _load():
    """Imports the hyphenated script as a module."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("extract_maquette_css", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FIXTURE = """<div class="stage"></div>
<style>
  /* ═══════════════════════════════════════════════════════════
     BLOCK 1 — PROTOTYPE HARNESS. NEVER EXTRACTED INTO THE APP.
     ═══════════════════════════════════════════════════════════ */
  .stage {
    display: grid;
  }

  /* ═══════════════════════════════════════════════════════════
     BLOCK 2 — APPLICATION CSS. THIS IS WHAT GETS TRANSPLANTED.
     ═══════════════════════════════════════════════════════════ */
  :root {
    --mq-only: 1px;
  }

  .card {
    border-radius: 8px;
  }

  .card .title,
  .tile {
    font-size: 13px;
  }

  .harness-only {
    color: red;
  }

  @media (min-width: 640px) {
    .card {
      padding: 10px;
    }
  }

  @keyframes heroin {
    from {
      opacity: 0;
    }
  }
</style>
"""

EXPORTED = {".card", ".title", ".tile"}


def test_script_exists() -> None:
    """The extractor exists at the documented path."""
    assert SCRIPT.is_file()


def test_only_the_application_block_is_extracted() -> None:
    """Harness rules never reach the generated stylesheet."""
    out = _load().extract(FIXTURE, EXPORTED, ".tm")
    assert ".stage" not in out


def test_selectors_are_scoped() -> None:
    """Every exported selector is emitted under the scope class."""
    out = _load().extract(FIXTURE, EXPORTED, ".tm")
    assert ".tm .card {" in out


def test_selector_lists_are_scoped_member_by_member() -> None:
    """A comma-separated list gets each member scoped, not just the first."""
    out = _load().extract(FIXTURE, EXPORTED, ".tm")
    assert ".tm .card .title" in out
    assert ".tm .tile" in out


def test_non_allowlisted_selectors_are_dropped() -> None:
    """A class absent from the allowlist is not exported."""
    out = _load().extract(FIXTURE, EXPORTED, ".tm")
    assert "harness-only" not in out


def test_media_queries_are_preserved_and_their_rules_scoped() -> None:
    """An at-rule keeps its condition; the rules inside it are still scoped."""
    out = _load().extract(FIXTURE, EXPORTED, ".tm")
    assert "@media (min-width: 640px)" in out
    assert ".tm .card {\n    padding: 10px;" in out


def test_keyframes_are_emitted_unscoped() -> None:
    """Keyframe selectors are percentages, not elements: scoping them breaks them."""
    out = _load().extract(FIXTURE, EXPORTED, ".tm")
    assert "@keyframes heroin" in out
    assert ".tm from" not in out


def test_root_rules_are_dropped() -> None:
    """The app owns its tokens; the prototype's :root would override the theme."""
    out = _load().extract(FIXTURE, EXPORTED, ".tm")
    assert "--mq-only" not in out


def test_output_carries_a_generated_banner() -> None:
    """The file says it is generated, so nobody edits it by hand in good faith."""
    out = _load().extract(FIXTURE, EXPORTED, ".tm")
    assert "GENERATED" in out.splitlines()[0].upper()


def test_check_mode_passes_when_the_file_is_current(tmp_path: Path) -> None:
    """--check exits 0 when the on-disk file equals what would be generated."""
    module = _load()
    source = tmp_path / "proto.html"
    source.write_text(FIXTURE, encoding="utf-8")
    regions = tmp_path / "regions.json"
    regions.write_text(
        '{"scope": ".tm", "exportedSelectors": [".card", ".title", ".tile"]}',
        encoding="utf-8",
    )
    out = tmp_path / "app-surface.css"
    out.write_text(module.extract(FIXTURE, EXPORTED, ".tm"), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check", "--source", str(source),
         "--regions", str(regions), "--out", str(out)],
        capture_output=True, text=True, check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_check_mode_fails_when_the_file_was_hand_edited(tmp_path: Path) -> None:
    """--check exits 1 on drift: a hand edit is the defect this guard exists for."""
    module = _load()
    source = tmp_path / "proto.html"
    source.write_text(FIXTURE, encoding="utf-8")
    regions = tmp_path / "regions.json"
    regions.write_text(
        '{"scope": ".tm", "exportedSelectors": [".card", ".title", ".tile"]}',
        encoding="utf-8",
    )
    out = tmp_path / "app-surface.css"
    out.write_text(
        module.extract(FIXTURE, EXPORTED, ".tm") + "\n.tm .card { color: hotpink; }\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check", "--source", str(source),
         "--regions", str(regions), "--out", str(out)],
        capture_output=True, text=True, check=False,
    )

    assert result.returncode == 1
    assert "drift" in (result.stdout + result.stderr).lower()


def test_writing_mode_creates_the_file(tmp_path: Path) -> None:
    """Without --check the script writes the generated stylesheet."""
    source = tmp_path / "proto.html"
    source.write_text(FIXTURE, encoding="utf-8")
    regions = tmp_path / "regions.json"
    regions.write_text(
        '{"scope": ".tm", "exportedSelectors": [".card", ".title", ".tile"]}',
        encoding="utf-8",
    )
    out = tmp_path / "nested" / "app-surface.css"

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--source", str(source),
         "--regions", str(regions), "--out", str(out)],
        capture_output=True, text=True, check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert out.is_file()
    assert ".tm .card" in out.read_text(encoding="utf-8")


def test_missing_application_block_is_a_hard_failure(tmp_path: Path) -> None:
    """A prototype that lost its harness/app separation must not extract silently."""
    module = _load()
    with pytest.raises(SystemExit):
        module.extract("<style>.card { color: red; }</style>", EXPORTED, ".tm")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/scripts/test_extract_maquette_css.py -v`
Expected: FAIL — every test errors on `assert SCRIPT.is_file()` or on the import, because `scripts/extract-maquette-css.py` does not exist yet.

- [ ] **Step 3: Write the extractor**

Create `scripts/extract-maquette-css.py`:

```python
#!/usr/bin/env python3
"""Generates the application stylesheet from the design prototype.

The prototype at ``frontend/maquette/refonte.html`` is the design reference. Its
`<style>` element is physically split in two: a harness block that never leaves
the prototype, and an application block that is what ships. This script lifts the
second, keeps only what the allowlist declares, scopes every selector under the
app's scope class, and writes the result.

Editing the generated file by hand is the defect, not a shortcut: run this script
instead. ``--check`` re-runs the generation and fails on any difference, so the
guard is a build condition rather than a convention.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "frontend" / "maquette" / "refonte.html"
DEFAULT_REGIONS = ROOT / "frontend" / "maquette" / "regions.json"
DEFAULT_OUT = ROOT / "frontend" / "src" / "styles" / "ps" / "app-surface.css"

#: Marker of the application block. Slicing starts at the OPENER of the comment
#: that carries it: cutting on the marker itself leaves an orphan comment closer,
#: and the header's own prose then parses as selectors.
BLOCK_MARKER = "BLOCK 2"

BANNER = """/* GENERATED FILE — DO NOT EDIT.
 *
 * Produced by scripts/extract-maquette-css.py from
 * frontend/maquette/refonte.html, the design reference.
 *
 * To change a pixel, change the prototype and re-run the script. A hand edit
 * here is reverted by the drift guard in `make check-frontend`.
 */
"""


def _application_block(html: str) -> str:
    """Returns the prototype's application CSS block.

    Raises SystemExit when the marker is absent: a prototype that lost its
    harness/app separation must fail loudly rather than export the harness.
    """
    marker = html.find(BLOCK_MARKER)
    if marker < 0:
        sys.exit(
            f"{BLOCK_MARKER} not found in the prototype: it lost its "
            "harness/application separation."
        )
    start = html.rfind("/*", 0, marker)
    if start < 0:
        start = marker
    end = html.find("</style>", start)
    if end < 0:
        sys.exit("The prototype's <style> element is not closed.")
    return html[start:end]


def _classes(selector: str) -> list[str]:
    """Returns every class mentioned by a selector, dotted."""
    return ["." + name for name in re.findall(r"\.([A-Za-z][\w-]*)", selector)]


def _is_exported(selector: str, exported: set[str]) -> bool:
    """True when every class the selector mentions is allowlisted.

    A selector with no class at all (a bare element, or `:root`) is never
    exported: the app owns its element defaults and its tokens.
    """
    names = _classes(selector)
    return bool(names) and all(name in exported for name in names)


def _scope_selector(selector: str, scope: str) -> str:
    """Prefixes a selector with the scope class."""
    return f"{scope} {selector.strip()}"


def _emit_rule(selector_list: str, body: str, exported: set[str], scope: str,
               indent: str) -> str:
    """Renders one style rule, dropping the selectors that are not allowlisted."""
    kept = [
        _scope_selector(part, scope)
        for part in selector_list.split(",")
        if _is_exported(part, exported)
    ]
    if not kept:
        return ""
    joined = ",\n".join(indent + sel for sel in kept)
    return f"{joined} {{{body}}}\n\n"


def _split_top_level(css: str) -> list[tuple[str, str]]:
    """Splits a stylesheet into (prelude, body) pairs at brace depth zero.

    Comments and strings are removed beforehand, so a brace inside either of them
    cannot desynchronise the split.
    """
    out: list[tuple[str, str]] = []
    depth = 0
    prelude_start = 0
    body_start = 0
    for i, ch in enumerate(css):
        if ch == "{":
            if depth == 0:
                body_start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                out.append((css[prelude_start:body_start], css[body_start + 1 : i]))
                prelude_start = i + 1
    return out


def _strip_noise(css: str) -> str:
    """Removes comments and string literals, which must not be parsed as syntax."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return re.sub(r"\"[^\"]*\"|'[^']*'", '""', css)


def extract(html: str, exported: set[str], scope: str) -> str:
    """Returns the generated stylesheet for a prototype's application block."""
    css = _strip_noise(_application_block(html))
    parts = [BANNER]

    for prelude, body in _split_top_level(css):
        prelude = prelude.strip()
        if prelude.startswith("@keyframes"):
            # Keyframe selectors are percentages, not elements: scoping them
            # would break the animation outright.
            parts.append(f"{prelude} {{{body}}}\n\n")
            continue
        if prelude.startswith("@"):
            inner = "".join(
                _emit_rule(sel, inner_body, exported, scope, "    ")
                for sel, inner_body in _split_top_level(body)
            )
            if inner.strip():
                parts.append(f"{prelude} {{\n{inner}}}\n\n")
            continue
        parts.append(_emit_rule(prelude, body, exported, scope, ""))

    return "".join(parts).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="fail when the generated file differs from the prototype")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--regions", type=Path, default=DEFAULT_REGIONS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    regions = json.loads(args.regions.read_text(encoding="utf-8"))
    generated = extract(
        args.source.read_text(encoding="utf-8"),
        set(regions["exportedSelectors"]),
        regions.get("scope", ".tm"),
    )

    if args.check:
        current = args.out.read_text(encoding="utf-8") if args.out.is_file() else ""
        if current != generated:
            print(
                f"DRIFT: {args.out} does not match what the prototype generates.\n"
                "The prototype is the source. Run:\n"
                "    python scripts/extract-maquette-css.py\n"
                "and commit the regenerated file.",
                file=sys.stderr,
            )
            return 1
        print(f"OK - {args.out.name} matches the prototype.")
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(generated, encoding="utf-8")
    print(f"Wrote {args.out} ({len(generated.splitlines())} lines).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/scripts/test_extract_maquette_css.py -v`
Expected: PASS — 11 passed.

- [ ] **Step 5: Generate the real stylesheet and eyeball its shape**

Run:

```bash
python scripts/extract-maquette-css.py
wc -l frontend/src/styles/ps/app-surface.css
head -20 frontend/src/styles/ps/app-surface.css
grep -c "^\.tm " frontend/src/styles/ps/app-surface.css
```

Expected: the file exists, starts with the generated banner, and contains several hundred `.tm `-prefixed rules. If it contains fewer than 100, the allowlist or the block marker is wrong — stop and investigate rather than committing a half-empty stylesheet.

- [ ] **Step 6: Prove no keyframe name collides with the app's**

Run:

```bash
grep -oE "@keyframes +[A-Za-z][\w-]*" frontend/src/styles/ps/app-surface.css | sort -u
rg "@keyframes" -g '*.css' -g '*.tsx' frontend/src --glob '!**/app-surface.css'
```

Expected: the two lists share no name. Keyframe names are global; a collision would silently rebind an existing animation. If one collides, rename it **in the prototype** (never in the generated file) and re-run the extraction.

- [ ] **Step 7: Import the generated stylesheet**

Modify `frontend/src/styles/ps/styles.css` — add the import next to the existing ones:

```css
@import "./app-surface.css";
```

- [ ] **Step 8: Verify the app still builds and its tests pass**

Run: `cd frontend && npm run typecheck && npm run test -- --run && npm run build`
Expected: all pass. The new stylesheet is scoped under `.tm`, which no element carries yet, so it cannot change a single shipped pixel. If anything moves, a selector escaped the scope — investigate before continuing.

- [ ] **Step 9: Commit**

```bash
git add scripts/extract-maquette-css.py tests/scripts/test_extract_maquette_css.py \
        frontend/src/styles/ps/app-surface.css frontend/src/styles/ps/styles.css
git commit -m "feat(shell-mobile): generate the app stylesheet from the design prototype

The prototype is the design reference, so its CSS is EXTRACTED rather than
mirrored by hand. The previous mission mirrored it, and every detail resembled
while the whole diverged.

The extractor keeps only what regions.json allowlists, scopes each selector
under .tm, preserves at-rules and leaves keyframes unscoped — their selectors
are percentages, not elements. :root rules are dropped: the app owns its tokens
and the prototype's would override the theme.

Slicing starts at the OPENER of the block comment, not at the marker string:
cutting on the marker leaves an orphan comment closer and the header's own prose
then parses as selectors."
```

---

### Task 2: The drift guard, wired into the build

An extractor nobody re-runs is a convention. This task makes a hand edit fail the build.

**Files:**

- Modify: `Makefile` (target `check-frontend`)
- Modify: `docs/reference/web-ui.md`

**Interfaces:**

- Consumes: `scripts/extract-maquette-css.py --check` from Task 1.
- Produces: `make check-frontend` fails when `app-surface.css` differs from what the prototype generates.

- [ ] **Step 1: Prove the guard fails on a hand edit, by hand**

Run:

```bash
echo ".tm .card { color: hotpink; }" >> frontend/src/styles/ps/app-surface.css
python scripts/extract-maquette-css.py --check; echo "exit=$?"
```

Expected: exit=1, with the DRIFT message naming the file and the command to run.

- [ ] **Step 2: Restore the file**

Run:

```bash
python scripts/extract-maquette-css.py
git diff --stat frontend/src/styles/ps/app-surface.css
```

Expected: no diff — regeneration restores it exactly.

- [ ] **Step 3: Wire the guard into the build**

Modify `Makefile`, in the `check-frontend` target, **before** the typecheck step (a stale stylesheet should be reported before a slower compile):

```makefile
check-frontend:
	@echo "Checking the generated stylesheet matches the design prototype..."
	python scripts/extract-maquette-css.py --check
	@echo "Running frontend typecheck..."
	cd frontend && npm run typecheck
```

- [ ] **Step 4: Run the build gate**

Run: `make check-frontend`
Expected: the new line prints `OK - app-surface.css matches the prototype.` and the rest of the target runs as before.

- [ ] **Step 5: Document how to run it**

Modify `docs/reference/web-ui.md` — add a section:

```markdown
## Design prototype and parity guards

`frontend/maquette/refonte.html` is the design reference for the web UI (§15 of
`docs/reference/product-intent.md`). Any design change starts there.

| Guard            | Command                                          | Fails when                                                                        |
| ---------------- | ------------------------------------------------ | --------------------------------------------------------------------------------- |
| Stylesheet drift | `python scripts/extract-maquette-css.py --check` | `app-surface.css` was hand-edited, or the prototype changed without regenerating  |
| Class coverage   | `python scripts/check-maquette-classes.py`       | a class in the prototype's application CSS is dead, or missing from the allowlist |
| Parity probe     | `python scripts/parity-probe.py`                 | a measured region diverges between the prototype and a local build                |

To change a pixel: edit the prototype, run
`python scripts/extract-maquette-css.py`, and commit the regenerated file.
Editing `frontend/src/styles/ps/app-surface.css` by hand is the defect, not a
shortcut — the drift guard reverts the argument.
```

- [ ] **Step 6: Commit**

```bash
git add Makefile docs/reference/web-ui.md
git commit -m "feat(shell-mobile): a hand-edited stylesheet now fails the build

An extractor nobody re-runs is a convention, not a guard. check-frontend now
refuses a generated file that does not match the prototype, and says which
command fixes it. Placed before the typecheck so a stale stylesheet is reported
before the slower compile."
```

---

### Task 3: The class-coverage guard

The allowlist is the only thing exported, so a class missing from it is silently absent from the app — a defect that only becomes visible once the screen is already wrong. This guard classifies every class in the prototype's application CSS and fails on anything uncovered or dead.

**Files:**

- Create: `scripts/check-maquette-classes.py`
- Create: `tests/scripts/test_check_maquette_classes.py`
- Modify: `Makefile` (target `check-frontend`)
- Modify: `pyproject.toml` (dev extra)

**Interfaces:**

- Consumes: `frontend/maquette/refonte.html`, `frontend/maquette/regions.json`, a headless Chromium via Playwright, and the prototype served over HTTP on port 8899.
- Produces: `python scripts/check-maquette-classes.py` — exit 0 when every class is classified and covered; exit 1 otherwise, listing the offenders.

**Reference implementation:** `frontend/maquette/harness/export.py` already does exactly this. This task promotes it into `scripts/`, with tests and a serving step it can own.

- [ ] **Step 1: Declare Playwright as a dev dependency**

Modify `pyproject.toml` — add to the `dev` optional dependencies list:

```toml
    "playwright>=1.47",
```

Run:

```bash
pip install -e ".[dev]"
python -m playwright install chromium
python -c "import playwright; print('playwright', playwright.__version__)"
```

Expected: the import succeeds and Chromium is installed. Until this step, the guard cannot run in CI.

- [ ] **Step 2: Write the failing test**

Create `tests/scripts/test_check_maquette_classes.py`:

```python
"""Tests for the class-coverage guard.

The pure parts are tested here; the browser pass is exercised by `make
check-frontend`, because a test that needs Chromium is a test that gets skipped.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check-maquette-classes.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_maquette_classes", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FIXTURE = """<style>
  /* BLOCK 1 — PROTOTYPE HARNESS. */
  .stage { display: grid; }

  /* ══ BLOCK 2 — APPLICATION CSS. ══ */
  /* A comment naming .not-a-class must not be parsed as a rule. */
  .card { border-radius: 8px; }
  .card .title { font-size: 13px; }
  @media (min-width: 640px) { .tile { padding: 2px; } }
</style>
"""


def test_script_exists() -> None:
    """The guard exists at the documented path."""
    assert SCRIPT.is_file()


def test_classes_come_from_rules_not_from_comments() -> None:
    """A class name mentioned in a comment is prose, not a rule."""
    found = _load().classes_in_application_block(FIXTURE)
    assert {"card", "title", "tile"} <= found
    assert "not-a-class" not in found


def test_harness_classes_are_not_collected() -> None:
    """Only the application block is inspected."""
    assert "stage" not in _load().classes_in_application_block(FIXTURE)


def test_missing_block_marker_is_a_hard_failure() -> None:
    """A prototype without its separation must fail rather than pass silently."""
    module = _load()
    try:
        module.classes_in_application_block("<style>.card { color: red; }</style>")
    except SystemExit:
        return
    raise AssertionError("a missing block marker must exit, not return")


def test_verdict_lists_dead_and_uncovered_classes() -> None:
    """The verdict names what is wrong, not merely that something is."""
    module = _load()
    problems = module.verdict(
        declared={"card", "title", "ghost"},
        rendered={"card"},
        written={"title"},
        harness=set(),
        allowlist={".card"},
    )
    assert any("ghost" in p for p in problems)   # defined, never used anywhere
    assert any(".title" in p for p in problems)  # used, but outside the allowlist


def test_verdict_is_empty_when_everything_is_covered() -> None:
    """A clean prototype produces no complaint."""
    module = _load()
    assert module.verdict(
        declared={"card", "title"},
        rendered={"card"},
        written={"title"},
        harness=set(),
        allowlist={".card", ".title"},
    ) == []
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `pytest tests/scripts/test_check_maquette_classes.py -v`
Expected: FAIL — the script does not exist.

- [ ] **Step 4: Write the guard**

Create `scripts/check-maquette-classes.py`. Start from `frontend/maquette/harness/export.py`, which already implements the browser pass, and restructure it so the pure parts are importable:

```python
#!/usr/bin/env python3
"""Fails when the design prototype's CSS would leave something behind.

`regions.json` carries an allowlist: the extractor exports only what it lists. A
class defined in the application CSS block but absent from both the allowlist and
the harness list would be silently missing from the app — the most expensive
defect possible, because it only becomes visible once the screen is already wrong.

Every class is classified by what it actually does:

  app      — at least one element carries it, outside the prototype chrome
  harness  — seen only in the harness (state panel, notes, phone frame)
  written  — never present in a frozen state, but written by the code
             (transient classes: armed gesture, loading, selection)
  DEAD     — defined in CSS, never carried, never written by the code

« DEAD » is a failure: dead CSS in the prototype becomes dead CSS in the app and,
worse, suggests a class exists when it does not.
"""

from __future__ import annotations

import asyncio
import http.server
import json
import re
import socketserver
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAQUETTE = ROOT / "frontend" / "maquette"
SOURCE = MAQUETTE / "refonte.html"
REGIONS = MAQUETTE / "regions.json"

#: Never 8710 or 8711: the reverse proxy routes production and staging there.
PORT = 8899

BLOCK_MARKER = "BLOCK 2"
CHROME = ".hpanel,.hbtn,.note,.states"
KNOWN_HARNESS = {"hpanel", "states", "notes", "stage", "device", "note", "hbtn"}


def classes_in_application_block(html: str) -> set[str]:
    """Returns the classes defined by a CSS rule in the application block."""
    marker = html.find(BLOCK_MARKER)
    if marker < 0:
        sys.exit(
            f"{BLOCK_MARKER} not found in the prototype: it lost its "
            "harness/application separation."
        )
    start = html.rfind("/*", 0, marker)
    css = html[start if start >= 0 else marker : html.find("</style>", marker)]
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"\"[^\"]*\"|'[^']*'", '""', css)
    out: set[str] = set()
    for match in re.finditer(r"([^{}]+)\{", css):
        selector = match.group(1)
        if "@" in selector and "media" in selector:
            continue
        out.update(re.findall(r"\.([A-Za-z][\w-]*)", selector))
    return out


def verdict(*, declared: set[str], rendered: set[str], written: set[str],
            harness: set[str], allowlist: set[str]) -> list[str]:
    """Returns one message per problem; an empty list means the prototype is clean."""
    problems: list[str] = []
    dead = sorted(declared - rendered - written - harness - KNOWN_HARNESS)
    if dead:
        problems.append(f"{len(dead)} dead CSS rule(s): {', '.join(dead)}")
    shipped = {"." + name for name in (rendered | written)}
    missing = sorted(shipped - allowlist)
    if missing:
        problems.append(
            f"{len(missing)} class(es) outside the allowlist: {', '.join(missing)}"
        )
    return problems


def _serve(directory: Path) -> socketserver.TCPServer:
    """Serves the prototype locally; Chromium will not load it from file://."""
    handler = lambda *a, **kw: http.server.SimpleHTTPRequestHandler(  # noqa: E731
        *a, directory=str(directory), **kw
    )
    server = socketserver.TCPServer(("127.0.0.1", PORT), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _wrapper(html: str) -> str:
    """Wraps the prototype so it owns a viewport meta.

    Without one, Chromium falls back to the legacy 980px layout viewport and
    every measurement is wrong.
    """
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,'
        'maximum-scale=1,user-scalable=no"></head><body>' + html + "</body></html>"
    )


async def _classify(classes: list[str]) -> tuple[set[str], set[str]]:
    """Drives every named state and reports which classes are actually carried."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2, is_mobile=True, has_touch=True,
        )
        page = await context.new_page()
        await page.goto(f"http://127.0.0.1:{PORT}/_probe.html", wait_until="load")
        await page.evaluate("()=>window.__measure(true)")
        app: set[str] = set()
        harness: set[str] = set()
        for state in await page.evaluate("()=>window.__states()"):
            await page.evaluate("(id)=>window.__go(id)", state)
            await page.wait_for_timeout(170)
            found = await page.evaluate(
                """([classes, chrome])=>{const a=[],h=[];
                  for (const c of classes) for (const el of document.getElementsByClassName(c)) {
                    if (el.closest(chrome) || el.classList.contains('stage')
                        || el.classList.contains('device')) h.push(c);
                    else a.push(c);
                  }
                  return {a:[...new Set(a)], h:[...new Set(h)]};}""",
                [classes, CHROME],
            )
            app |= set(found["a"])
            harness |= set(found["h"])
        await browser.close()
    return app, harness - app


def main() -> int:
    html = SOURCE.read_text(encoding="utf-8")
    regions = json.loads(REGIONS.read_text(encoding="utf-8"))
    declared = classes_in_application_block(html)

    probe = MAQUETTE / "_probe.html"
    probe.write_text(_wrapper(html), encoding="utf-8")
    server = _serve(MAQUETTE)
    try:
        rendered, harness = asyncio.run(_classify(sorted(declared)))
    finally:
        server.shutdown()
        probe.unlink(missing_ok=True)

    # The harness is written by the code too: without this subtraction it would
    # land in « written », hence in the export allowlist.
    source_after_css = html[html.find("</style>") :]
    rest = declared - rendered - harness - KNOWN_HARNESS
    written = {
        name for name in rest
        if re.search(r"[\"'` ]" + re.escape(name) + r"[\"'` ]", source_after_css)
    }

    problems = verdict(
        declared=declared, rendered=rendered, written=written,
        harness=harness, allowlist=set(regions["exportedSelectors"]),
    )

    print(f"Classification of the {len(declared)} application CSS classes")
    print(f"  app       {len(rendered):4d}")
    print(f"  written   {len(written):4d}")
    print(f"  harness   {len(harness):4d}")
    if problems:
        for problem in problems:
            print("■", problem)
        print("FAILURE - extraction would leave CSS behind.")
        return 1
    print("OK - every class is classified, and the allowlist covers them all.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/scripts/test_check_maquette_classes.py -v`
Expected: PASS — 6 passed.

- [ ] **Step 6: Run the guard against the real prototype**

Run: `python scripts/check-maquette-classes.py`
Expected: `OK - every class is classified, and the allowlist covers them all.` If it reports classes outside the allowlist, add them to `regions.json` → `exportedSelectors` (sorted) and re-run. If it reports dead rules, delete them **from the prototype** — dead CSS in the prototype becomes dead CSS in the app.

- [ ] **Step 7: Prove the guard bites**

Run:

```bash
python - <<'EOF'
import json, pathlib
p = pathlib.Path("frontend/maquette/regions.json")
d = json.loads(p.read_text())
d["exportedSelectors"] = [s for s in d["exportedSelectors"] if s != ".card"]
p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n")
EOF
python scripts/check-maquette-classes.py; echo "exit=$?"
git checkout frontend/maquette/regions.json
```

Expected: exit=1 with `.card` named as outside the allowlist, then the file is restored. A guard that has never bitten proves nothing.

- [ ] **Step 8: Wire it into the build**

Modify `Makefile`, in `check-frontend`, right after the drift guard:

```makefile
	@echo "Checking every prototype class is classified and covered..."
	python scripts/check-maquette-classes.py
```

- [ ] **Step 9: Run the build gate**

Run: `make check-frontend`
Expected: both guards pass, then typecheck, lint, tests and build run as before.

- [ ] **Step 10: Commit**

```bash
git add scripts/check-maquette-classes.py tests/scripts/test_check_maquette_classes.py \
        Makefile pyproject.toml frontend/maquette/regions.json
git commit -m "feat(shell-mobile): fail the build when prototype CSS would be left behind

The allowlist is the only thing exported, so a class missing from it is silently
absent from the app — visible only once the screen is already wrong. The guard
classifies every class by what it actually does across all named states, and
fails on dead rules as well as on uncovered ones.

Dead CSS is a failure and not a warning: it becomes dead CSS in the app and,
worse, suggests a class exists when it does not."
```

---

### Task 4: The state-driver contract

The probe iterates `regions.json` → for each region, the states it is visible in → `__go(state)` → measure. If the two lists drift apart, the probe silently measures less than it claims. This task makes that impossible.

**Files:**

- Create: `tests/scripts/test_maquette_states.py`

**Interfaces:**

- Consumes: `frontend/maquette/refonte.html`, `frontend/maquette/regions.json`.
- Produces: a pytest that fails when `regions.json` → `states` and the prototype's `window.__states()` disagree, and when a region names a state that does not exist.

- [ ] **Step 1: Write the failing test**

Create `tests/scripts/test_maquette_states.py`:

```python
"""The prototype's state list and the measurement map must not drift apart.

The probe reaches a region by driving the prototype into a named state. If the
map names a state the prototype no longer has, the probe measures less than it
claims — and says nothing.

The state ids are read from the prototype's source rather than from a browser:
this test must run in the ordinary test suite, not only where Chromium is
installed.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAQUETTE = ROOT / "frontend" / "maquette"


def _declared_state_ids() -> list[str]:
    """Returns the state ids declared in the prototype's STATES table."""
    html = MAQUETTE / "refonte.html"
    source = html.read_text(encoding="utf-8")
    start = source.find("STATE ENUMERATION")
    assert start > 0, "the prototype lost its state enumeration"
    end = source.find("window.__measure", start)
    return re.findall(r'\[\s*"([a-z0-9-]+)"\s*,', source[start:end])


def test_regions_states_match_the_prototype() -> None:
    """regions.json lists exactly the states the prototype declares."""
    regions = json.loads((MAQUETTE / "regions.json").read_text(encoding="utf-8"))
    assert sorted(regions["states"]) == sorted(_declared_state_ids())


def test_every_region_names_states_that_exist() -> None:
    """A region cannot be reached through a state the prototype does not have."""
    regions = json.loads((MAQUETTE / "regions.json").read_text(encoding="utf-8"))
    known = set(regions["states"])
    unknown: list[str] = []
    for name, region in regions["regions"].items():
        for state in region.get("states", []):
            if state not in known:
                unknown.append(f"{name} → {state}")
    assert unknown == [], f"regions naming unknown states: {unknown}"


def test_every_state_is_reachable_from_at_least_one_region_or_declared_orphan() -> None:
    """A state nothing measures is either useless or an unnoticed gap.

    Orphans are allowed but must be deliberate: a state that no region names is
    listed here so the exemption is a decision rather than an oversight.
    """
    regions = json.loads((MAQUETTE / "regions.json").read_text(encoding="utf-8"))
    used = {s for r in regions["regions"].values() for s in r.get("states", [])}
    orphans = sorted(set(regions["states"]) - used)
    declared_orphans = set(regions.get("unmeasuredStates", []))
    assert set(orphans) <= declared_orphans, (
        "states no region measures and no exemption declares: "
        f"{sorted(set(orphans) - declared_orphans)}"
    )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/scripts/test_maquette_states.py -v`
Expected: the first two may already pass; the third FAILS, because `unmeasuredStates` does not exist in `regions.json` yet and several states are measured by no region.

- [ ] **Step 3: Declare the unmeasured states**

Run this to list them, then add the list to `regions.json` under `unmeasuredStates`, sorted:

```bash
python - <<'EOF'
import json, pathlib
p = pathlib.Path("frontend/maquette/regions.json")
d = json.loads(p.read_text())
used = {s for r in d["regions"].values() for s in r.get("states", [])}
orphans = sorted(set(d["states"]) - used)
d["unmeasuredStates"] = orphans
d["$unmeasuredStatesNote"] = (
    "States that no region measures. Listed so the exemption is a decision "
    "rather than an oversight: each is either a loading or error phase whose "
    "geometry is covered by its ready-state sibling, or a surface still drawn "
    "but not yet rebuilt. Moving a state out of this list is how coverage grows."
)
p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n")
print(len(orphans), "unmeasured states declared")
EOF
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/scripts/test_maquette_states.py -v`
Expected: PASS — 3 passed.

- [ ] **Step 5: Prove the first test bites**

Run:

```bash
python - <<'EOF'
import json, pathlib
p = pathlib.Path("frontend/maquette/regions.json")
d = json.loads(p.read_text()); d["states"].append("state-that-does-not-exist")
p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n")
EOF
pytest tests/scripts/test_maquette_states.py -v; echo "exit=$?"
git checkout frontend/maquette/regions.json
```

Expected: `test_regions_states_match_the_prototype` FAILS, then the file is restored.

- [ ] **Step 6: Commit**

```bash
git add tests/scripts/test_maquette_states.py frontend/maquette/regions.json
git commit -m "test(shell-mobile): the state list and the measurement map cannot drift apart

The probe reaches a region by driving the prototype into a named state. A map
naming a state the prototype no longer has measures less than it claims, and says
nothing about it.

States that no region measures are now listed explicitly, so « not measured » is
a decision rather than an oversight — and moving one out of that list is how
coverage grows."
```

---

### Task 5: The parity probe

Measures the prototype against a locally built app and diffs geometry plus a fixed computed-style subset. This is the guard the whole rebuild leans on: without it, "conformant" is an opinion.

**Files:**

- Create: `scripts/parity-probe.py`
- Create: `tests/scripts/test_parity_probe.py`

**Interfaces:**

- Consumes: `frontend/maquette/regions.json` (`regions`, `probe.viewport`, `probe.computedStyleSubset`, `probe.allowlist`), a locally served prototype on 8899, and a locally served production build of the app.
- Produces:
  - `diff_region(a: dict, b: dict, subset: list[str], tolerance: float) -> list[str]` — pure; returns one message per difference.
  - `is_allowed(region: str, prop: str, allowlist: list[dict]) -> bool` — pure; True when a divergence carries a justified allowlist entry.
  - CLI: `python scripts/parity-probe.py [--app-url URL] [--only REGION]`. Exit 0 when every measured region matches; exit 1 otherwise, listing region, property, and the two values.

**Note on the gate in this phase.** No page has been rebuilt yet, so the probe cannot compare page regions. What it _can_ compare — and what this phase's gate is — are the **shell regions**, whose truth flows the other way: the prototype transplanted them from `layout/TopBar.tsx` and `layout/BottomTabBar.tsx`. If the probe reports a divergence there, the prototype is wrong and must be corrected, which is exactly the direction §7.2 bis defines. Page regions are added to the measured set as their phase lands.

- [ ] **Step 1: Write the failing test**

Create `tests/scripts/test_parity_probe.py`:

```python
"""Tests for the parity probe's pure parts.

The browser pass is exercised by `make check-frontend`. What is tested here is
the part that decides whether two measurements differ — because a diff that is
too lenient turns the whole probe into decoration.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "parity-probe.py"

SUBSET = ["font-size", "padding", "border-radius"]


def _load():
    spec = importlib.util.spec_from_file_location("parity_probe", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_script_exists() -> None:
    """The probe exists at the documented path."""
    assert SCRIPT.is_file()


def test_identical_measurements_produce_no_difference() -> None:
    """Two identical regions are conformant."""
    module = _load()
    m = {"rect": {"width": 100.0, "height": 44.0},
         "style": {"font-size": "13.5px", "padding": "0px", "border-radius": "8px"}}
    assert module.diff_region(m, dict(m), SUBSET, 0.5) == []


def test_a_style_difference_is_reported_with_both_values() -> None:
    """A message names the property AND the two values, or it cannot be acted on."""
    module = _load()
    a = {"rect": {"width": 100.0, "height": 44.0}, "style": {"font-size": "13.5px"}}
    b = {"rect": {"width": 100.0, "height": 44.0}, "style": {"font-size": "14px"}}
    messages = module.diff_region(a, b, ["font-size"], 0.5)
    assert len(messages) == 1
    assert "font-size" in messages[0]
    assert "13.5px" in messages[0] and "14px" in messages[0]


def test_geometry_within_tolerance_is_conformant() -> None:
    """Sub-pixel rounding is not a divergence."""
    module = _load()
    a = {"rect": {"width": 100.0, "height": 44.0}, "style": {}}
    b = {"rect": {"width": 100.3, "height": 44.0}, "style": {}}
    assert module.diff_region(a, b, [], 0.5) == []


def test_geometry_beyond_tolerance_is_reported() -> None:
    """A real geometric difference is not rounded away."""
    module = _load()
    a = {"rect": {"width": 100.0, "height": 44.0}, "style": {}}
    b = {"rect": {"width": 104.0, "height": 44.0}, "style": {}}
    messages = module.diff_region(a, b, [], 0.5)
    assert len(messages) == 1
    assert "width" in messages[0]


def test_a_missing_region_is_a_difference_not_a_skip() -> None:
    """A region absent from one side is the loudest possible divergence."""
    module = _load()
    messages = module.diff_region(None, {"rect": {}, "style": {}}, [], 0.5)
    assert messages and "missing" in messages[0].lower()


def test_allowlist_entry_requires_a_justification() -> None:
    """An accepted divergence without a written reason is not accepted."""
    module = _load()
    assert module.is_allowed("shell/bottombar", "position",
                             [{"region": "shell/bottombar", "property": "position",
                               "justification": "declared harness deviation"}])
    assert not module.is_allowed("shell/bottombar", "position",
                                 [{"region": "shell/bottombar", "property": "position"}])


def test_allowlist_does_not_leak_across_regions() -> None:
    """An exemption granted to one region does not cover its neighbour."""
    module = _load()
    entries = [{"region": "shell/bottombar", "property": "position",
                "justification": "declared harness deviation"}]
    assert not module.is_allowed("shell/topbar", "position", entries)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/scripts/test_parity_probe.py -v`
Expected: FAIL — the script does not exist.

- [ ] **Step 3: Write the probe**

Create `scripts/parity-probe.py`:

```python
#!/usr/bin/env python3
"""Measures the app against the design prototype, region by region.

Two headless contexts, identical emulation: the prototype on one side, a local
production build of the app on the other. For each region declared in
regions.json, the probe drives the prototype into a state where the region is
visible, measures its bounding box and a fixed subset of computed styles, and
compares the two.

A divergence is a defect in the app, unless the prototype was amended first. An
accepted divergence lives in regions.json → probe.allowlist and must carry a
written justification: an exemption nobody had to explain is an exemption that
outlives its reason.
"""

from __future__ import annotations

import argparse
import asyncio
import http.server
import json
import socketserver
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAQUETTE = ROOT / "frontend" / "maquette"
REGIONS = MAQUETTE / "regions.json"

#: Never 8710 or 8711: the reverse proxy routes production and staging there.
PROTOTYPE_PORT = 8899
DEFAULT_APP_URL = "http://127.0.0.1:4173"

#: Sub-pixel rounding differs between two layout passes; a real difference does
#: not hide under half a pixel.
TOLERANCE = 0.5


def diff_region(a: dict | None, b: dict | None, subset: list[str],
                tolerance: float) -> list[str]:
    """Returns one message per difference between two measurements."""
    if a is None or b is None:
        which = "prototype" if a is None else "app"
        return [f"region missing on the {which} side"]

    messages: list[str] = []
    for key, left in (a.get("rect") or {}).items():
        right = (b.get("rect") or {}).get(key)
        if right is None:
            messages.append(f"rect.{key}: missing on the app side")
        elif abs(float(left) - float(right)) > tolerance:
            messages.append(f"rect.{key}: prototype {left} vs app {right}")

    for prop in subset:
        left = (a.get("style") or {}).get(prop)
        right = (b.get("style") or {}).get(prop)
        if left != right:
            messages.append(f"{prop}: prototype {left} vs app {right}")

    return messages


def is_allowed(region: str, prop: str, allowlist: list[dict]) -> bool:
    """True when a divergence carries a justified allowlist entry."""
    for entry in allowlist:
        if (entry.get("region") == region
                and entry.get("property") == prop
                and str(entry.get("justification", "")).strip()):
            return True
    return False


def _serve(directory: Path, port: int) -> socketserver.TCPServer:
    handler = lambda *a, **kw: http.server.SimpleHTTPRequestHandler(  # noqa: E731
        *a, directory=str(directory), **kw
    )
    server = socketserver.TCPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _wrapper(html: str) -> str:
    """Wraps the prototype so it owns a viewport meta.

    Without one, Chromium falls back to the legacy 980px layout viewport and
    every measurement is wrong.
    """
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,'
        'maximum-scale=1,user-scalable=no"></head><body>' + html + "</body></html>"
    )


MEASURE = """([selector, subset])=>{
  const el = document.querySelector(selector);
  if (!el) return null;
  const r = el.getBoundingClientRect();
  const s = getComputedStyle(el);
  const style = {};
  for (const prop of subset) style[prop] = s.getPropertyValue(prop);
  return {rect: {width: r.width, height: r.height}, style};
}"""


async def _run(app_url: str, only: str | None) -> int:
    from playwright.async_api import async_playwright

    regions = json.loads(REGIONS.read_text(encoding="utf-8"))
    probe = regions["probe"]
    subset = probe["computedStyleSubset"]
    allowlist = probe.get("allowlist", [])
    viewport = probe["viewport"]

    wrapper = MAQUETTE / "_probe.html"
    wrapper.write_text(_wrapper((MAQUETTE / "refonte.html").read_text(encoding="utf-8")),
                       encoding="utf-8")
    server = _serve(MAQUETTE, PROTOTYPE_PORT)

    failures: list[str] = []
    measured = 0
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            options = {
                "viewport": {"width": viewport["width"], "height": viewport["height"]},
                "device_scale_factor": viewport["deviceScaleFactor"],
                "is_mobile": viewport["isMobile"],
                "has_touch": viewport["hasTouch"],
            }
            proto_page = await (await browser.new_context(**options)).new_page()
            app_page = await (await browser.new_context(**options)).new_page()

            await proto_page.goto(
                f"http://127.0.0.1:{PROTOTYPE_PORT}/_probe.html", wait_until="load")
            await proto_page.evaluate("()=>window.__measure(true)")
            await app_page.goto(app_url, wait_until="load")

            for page, name in ((proto_page, "prototype"), (app_page, "app")):
                width = await page.evaluate("()=>document.documentElement.clientWidth")
                if width != viewport["width"]:
                    print(f"{name}: layout viewport is {width}px, expected "
                          f"{viewport['width']}px — every measurement would be wrong.",
                          file=sys.stderr)
                    return 1

            for name, region in regions["regions"].items():
                if only and only not in name:
                    continue
                states = region.get("states") or []
                if not states:
                    continue
                await proto_page.evaluate("(id)=>window.__go(id)", states[0])
                await proto_page.wait_for_timeout(220)
                left = await proto_page.evaluate(MEASURE, [region["selector"], subset])
                right = await app_page.evaluate(MEASURE, [region["selector"], subset])
                if left is None and right is None:
                    continue  # not yet built on either side: a later phase adds it
                measured += 1
                for message in diff_region(left, right, subset, TOLERANCE):
                    prop = message.split(":")[0]
                    if is_allowed(name, prop, allowlist):
                        continue
                    failures.append(f"{name} · {message}")

            await browser.close()
    finally:
        server.shutdown()
        wrapper.unlink(missing_ok=True)

    print(f"Parity probe — {measured} region(s) measured")
    if failures:
        for failure in failures:
            print("■", failure)
        print(f"FAILURE - {len(failures)} divergence(s). The prototype is the "
              "reference: fix the app, or amend the prototype first and say why.")
        return 1
    print("OK - every measured region matches the prototype.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-url", default=DEFAULT_APP_URL,
                        help="URL of a locally served production build")
    parser.add_argument("--only", help="measure only the regions whose name contains this")
    args = parser.parse_args()
    return asyncio.run(_run(args.app_url, args.only))


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/scripts/test_parity_probe.py -v`
Expected: PASS — 8 passed.

- [ ] **Step 5: Run the probe against a real build**

Run, in two terminals:

```bash
# terminal 1
cd frontend && npm run build && npm run preview
# terminal 2 — note the port printed by `npm run preview`, usually 4173
python scripts/parity-probe.py --app-url http://127.0.0.1:4173
```

Expected: the probe prints how many regions it measured. Regions whose selector exists on neither side are skipped as "not yet built", which is correct in this phase — only the shell is expected to match.

- [ ] **Step 6: Drive the shell regions to zero**

Run: `python scripts/parity-probe.py --only shell/`
Expected: `OK - every measured region matches the prototype.`

If a shell region diverges: **the prototype is wrong**, not the app. The shell's truth flows the other way — `layout/TopBar.tsx` and `layout/BottomTabBar.tsx` are authoritative for it. Correct `frontend/maquette/refonte.html`, re-run `python scripts/extract-maquette-css.py`, and re-run the probe. If the divergence is deliberate and cannot be removed (the bottom bar's `position` is one such case, because the prototype embeds a phone frame inside a wide page), add an entry to `regions.json` → `probe.allowlist` **with a written justification** — the probe rejects an entry that carries none.

- [ ] **Step 7: Prove the probe bites**

Run:

```bash
python - <<'EOF'
import json, pathlib
p = pathlib.Path("frontend/maquette/regions.json")
d = json.loads(p.read_text())
d["probe"]["computedStyleSubset"] = list(d["probe"]["computedStyleSubset"]) + ["z-index"]
p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n")
EOF
python scripts/parity-probe.py --only shell/; echo "exit=$?"
git checkout frontend/maquette/regions.json
```

Expected: either the probe still passes (the two sides genuinely agree on `z-index` too — good), or it fails naming `z-index` with both values. Either outcome proves the subset is actually read and compared rather than ignored. A probe that cannot be made to fail proves nothing.

- [ ] **Step 8: Commit**

```bash
git add scripts/parity-probe.py tests/scripts/test_parity_probe.py
git commit -m "feat(shell-mobile): measure the app against the design prototype

Two headless contexts, identical emulation, region by region: bounding box plus a
fixed computed-style subset. Without this, « conformant » is an opinion.

A region absent from one side is reported, never skipped — a probe that quietly
measures nothing is worse than no probe. An accepted divergence must carry a
written justification: an exemption nobody had to explain is an exemption that
outlives its reason.

In this phase only the shell is expected to match, and its truth flows the other
way: the components are authoritative, so a divergence there means the prototype
needs correcting. Page regions join the measured set as their phase lands."
```

---

### Task 6: CI wiring and the phase gate

The guards must run where nobody can forget them.

**Files:**

- Modify: `.github/workflows/ci.yml`
- Modify: `Makefile` (target `check-frontend`)
- Modify: `IMPLEMENTATION.md`

**Interfaces:**

- Consumes: all three scripts from Tasks 1, 3 and 5.
- Produces: a CI job that installs Chromium, builds the app, and runs the three guards; and a `make check-frontend` that does the same locally.

- [ ] **Step 1: Add the probe to the local gate**

Modify `Makefile`, in `check-frontend`, after the build step (the probe needs a built app):

```makefile
	@echo "Running the parity probe against the built app..."
	cd frontend && (npm run preview -- --port 4173 &) && sleep 4
	python scripts/parity-probe.py --app-url http://127.0.0.1:4173 --only shell/
	@pkill -f "vite preview" || true
```

- [ ] **Step 2: Run the local gate end to end**

Run: `make check-frontend`
Expected: drift guard OK, class-coverage OK, typecheck, lint, tests, build, then `OK - every measured region matches the prototype.` If the preview server is slow to start on your machine, raise the `sleep` — a flaky gate is a gate people disable.

- [ ] **Step 3: Read the CI workflow before editing it**

Run: `grep -n "frontend\|node-version\|python-version" .github/workflows/ci.yml`
Expected: you can see which job builds the frontend and which Python version the workflow uses. Add to that job rather than creating a second one that installs everything twice.

- [ ] **Step 4: Wire the guards into CI**

Modify `.github/workflows/ci.yml` — in the job that already sets up Node and the frontend, after `npm ci`:

```yaml
- name: Install Chromium for the parity guards
  run: |
    pip install -e ".[dev]"
    python -m playwright install --with-deps chromium

- name: Check the generated stylesheet matches the prototype
  run: python scripts/extract-maquette-css.py --check

- name: Check every prototype class is classified and covered
  run: python scripts/check-maquette-classes.py

- name: Build the app and run the parity probe
  run: |
    cd frontend && npm run build && (npm run preview -- --port 4173 &) && sleep 5
    cd .. && python scripts/parity-probe.py --app-url http://127.0.0.1:4173 --only shell/
```

- [ ] **Step 5: Push and watch CI**

Run:

```bash
git add .github/workflows/ci.yml Makefile
git commit -m "ci(shell-mobile): run the parity guards where nobody can forget them"
git push
gh pr checks --watch
```

Expected: the job passes. If it fails in 3–4 seconds with no log, that is a spending-limit failure and not a code failure — check the billing state before debugging.

- [ ] **Step 6: Record the phase gate**

Modify `IMPLEMENTATION.md` at the repository root — replace its contents with the current tracker:

```markdown
# Current feature: shell-mobile

**Spec:** `docs/superpowers/specs/2026-08-10-refonte-mobile-quatre-pages-design.md`
**Design reference:** `frontend/maquette/refonte.html` (§15 of the constitution)
**Branch:** `feat/shell-mobile`
**Integration:** all phases target the integration branch; `main` is touched once,
at the end, after everything has been validated together.

| Phase | Delivers                                                                  | Status      |
| ----- | ------------------------------------------------------------------------- | ----------- |
| 0     | Parity tooling: extractor, drift guard, class-coverage guard, probe, CI   | done        |
| 1     | Scope rename, primitives extracted to `ds/`, `PageHeader` off mobile      | not started |
| 2     | Arrivées + reception into Système; old routes demoted to redirects        | not started |
| 3     | Médiathèque, read-only                                                    | not started |
| 4     | Media sheet: visual header, single back control, YouTube trailer, seasons | not started |
| 5     | Delete, dry-run enforced                                                  | not started |
| 6     | Découvrir: three formats, TMDB account, background pool                   | not started |

**Next action:** write the plan for phase 1 from §4 of the spec.

## Phase 0 gate

- `python scripts/extract-maquette-css.py --check` → OK
- `python scripts/check-maquette-classes.py` → OK
- `python scripts/parity-probe.py --only shell/` → OK, on a local build
- `make check-frontend` → passes end to end
- CI runs all three on every push
- Nothing in the app changed: the generated stylesheet is scoped under `.tm`,
  which no element carries yet.
```

- [ ] **Step 7: Bump the version**

Run:

```bash
python scripts/check_version_bump.py --help 2>/dev/null | head -5 || true
grep -n "^version" pyproject.toml
```

Then raise the patch component in `pyproject.toml`, since this phase adds tooling without changing behaviour.

- [ ] **Step 8: Commit**

```bash
git add IMPLEMENTATION.md pyproject.toml
git commit -m "chore(shell-mobile): phase 0 gate — parity tooling in place

The prototype is the design reference and the build now enforces it: the
stylesheet is generated from it, a hand edit fails, an uncovered or dead class
fails, and the shell is measured against it on every push.

Nothing in the app changed. The generated stylesheet is scoped under .tm, which
no element carries yet — which is precisely the gate: the machinery is proven
before a single page is rebuilt."
```

---

## Self-Review

**1. Spec coverage.** Phase 0's row in §8.2 asks for: prototype committed (already done before this plan), extraction script (Task 1), `regions.json` (already exists; extended in Tasks 3 and 4), fixtures (the prototype carries its own real data — §7.5's "one fixture set" is satisfied by `regions.json` + the prototype, so no separate fixture file is created), probe wired into `make check` and CI (Tasks 5 and 6), and the gate "the probe reports zero on Acquisition as it ships today" — implemented as the shell-region gate in Task 5 Step 6, with the direction-of-truth caveat spelled out, because §7.2 bis makes the components authoritative for the shell. §7.1 bis's three binding lessons are honoured: the probe uses rects plus computed styles rather than screenshots, each guard prints what it measured, and every guard has a step that proves it bites (Task 2 Step 1, Task 3 Step 7, Task 4 Step 5, Task 5 Step 7).

**2. Placeholder scan.** No "TBD", no "add error handling", no "similar to Task N". Every code step carries the code. Two steps ask the implementer to read before editing (Task 6 Step 3) or to investigate a suspicious result (Task 1 Step 5) — those are instructions to look, not placeholders for work left undefined.

**3. Type consistency.** `extract(html, exported, scope)`, `_application_block(html)`, `_scope_selector(selector, scope)`, `_is_exported(selector, exported)` are defined in Task 1 and referenced nowhere else with different names. `classes_in_application_block(html)` and `verdict(declared, rendered, written, harness, allowlist)` are defined in Task 3 and used by its own tests with those exact keyword names. `diff_region(a, b, subset, tolerance)` and `is_allowed(region, prop, allowlist)` are defined in Task 5 and used by its tests with the same signatures. `regions.json` gains two keys — `unmeasuredStates` (Task 4) and `probe.allowlist` entries carrying `justification` (Task 5) — both read only by the code that defines them.

**One gap deliberately left open, and named:** `frontend/src/styles/ps/maquette-acquisition.css` (the previous mission's hand-mirrored stylesheet, scoped `.mq`) is untouched by this phase. Phase 1 is where `.mq` becomes `.tm` and that file is superseded by the generated one; doing it here would change shipped pixels during a phase whose whole point is that nothing moves.
