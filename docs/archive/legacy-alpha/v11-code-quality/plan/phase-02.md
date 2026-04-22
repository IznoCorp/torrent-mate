# Phase 2: CLI Config Error Decorator

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `@handle_cli_errors` decorator that catches pydantic `ValidationError` and `FileNotFoundError`, displaying user-friendly messages instead of raw tracebacks.

**Architecture:** A decorator applied to all 7 CLI commands. A `_format_validation()` helper extracts field-level errors from pydantic into a one-liner.

**Tech Stack:** Python, typer, pydantic, pytest, CliRunner

---

## Task 1: Write failing tests for config error handling

**Files:**

- Modify: `tests/test_cli.py`

- [ ] **Step 1: Add test for invalid config value**

Add to `tests/test_cli.py`:

```python
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.cli.release_lock")
def test_invalid_config_shows_friendly_error(mock_release, mock_lock):
    """Invalid config value should show 'Configuration error', not a pydantic traceback."""
    from pydantic import ValidationError

    with patch(
        "personalscraper.cli.get_settings",
        side_effect=ValidationError.from_exception_data(
            title="Settings",
            line_errors=[
                {
                    "type": "int_parsing",
                    "loc": ("qbit_port",),
                    "msg": "Input should be a valid integer",
                    "input": "abc",
                }
            ],
        ),
    ):
        result = runner.invoke(app, ["ingest"])
        assert result.exit_code == 1
        assert "Configuration error" in result.output
        assert "qbit_port" in result.output
        # Must NOT contain raw pydantic traceback
        assert "ValidationError" not in result.output
```

- [ ] **Step 2: Add test for missing .env file**

```python
@patch("personalscraper.cli.acquire_lock", return_value=True)
@patch("personalscraper.cli.release_lock")
def test_missing_env_file_shows_friendly_error(mock_release, mock_lock):
    """Missing .env file should show 'Missing file', not a raw traceback."""
    with patch(
        "personalscraper.cli.get_settings",
        side_effect=FileNotFoundError(".env file not found"),
    ):
        result = runner.invoke(app, ["ingest"])
        assert result.exit_code == 1
        assert "Missing file" in result.output
```

- [ ] **Step 3: Add test that decorator does not interfere with normal flow**

```python
@patch(_PATCH_CLI_RUN_INGEST, return_value=_mock_report)
@patch("personalscraper.cli.release_lock")
@patch("personalscraper.cli.acquire_lock", return_value=True)
def test_decorator_does_not_affect_normal_flow(mock_lock, mock_release, mock_run):
    """Normal command execution should be unaffected by the decorator."""
    result = runner.invoke(app, ["ingest"])
    assert result.exit_code == 0
    assert "2 OK" in result.output
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `python -m pytest tests/test_cli.py::test_invalid_config_shows_friendly_error tests/test_cli.py::test_missing_env_file_shows_friendly_error -v`

Expected: FAIL — `ValidationError` propagates as raw traceback, "Configuration error" not in output.

- [ ] **Step 5: Commit test stubs**

```bash
git add tests/test_cli.py
git commit -m "v11.2.1: Add failing tests for CLI config error handling"
```

## Task 2: Implement handle_cli_errors decorator

**Files:**

- Modify: `personalscraper/cli.py`

- [ ] **Step 1: Add \_format_validation helper and decorator**

Add after the `state` dict (line 28) in `personalscraper/cli.py`:

```python
import functools

from pydantic import ValidationError


def _format_validation(exc: ValidationError) -> str:
    """Format pydantic ValidationError as a user-friendly one-liner.

    Extracts field names and error messages from pydantic's structured
    errors, joining them with semicolons.

    Args:
        exc: The pydantic ValidationError to format.

    Returns:
        Formatted string like "QBIT_PORT: Input should be a valid integer".
    """
    parts = []
    for err in exc.errors():
        field = " → ".join(str(loc) for loc in err["loc"])
        parts.append(f"{field}: {err['msg']}")
    return "; ".join(parts)


def handle_cli_errors(func):
    """Catch configuration and file errors, display user-friendly messages.

    Wraps CLI commands to intercept pydantic ValidationError (from
    get_settings()) and FileNotFoundError, showing clear messages
    instead of raw tracebacks.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as exc:
            state["console"].print(
                f"[red]Configuration error:[/red] {_format_validation(exc)}"
            )
            raise typer.Exit(1)
        except FileNotFoundError as exc:
            state["console"].print(f"[red]Missing file:[/red] {exc}")
            raise typer.Exit(1)
    return wrapper
```

- [ ] **Step 2: Apply decorator to all 7 commands**

Add `@handle_cli_errors` to each command function, directly below the `@app.command()` decorator:

```python
@app.command()
@handle_cli_errors
def ingest(...):
    ...

@app.command()
@handle_cli_errors
def sort(...):
    ...

@app.command()
@handle_cli_errors
def scrape(...):
    ...

@app.command()
@handle_cli_errors
def verify(...):
    ...

@app.command()
@handle_cli_errors
def dispatch(...):
    ...

@app.command()
@handle_cli_errors
def process(...):
    ...

@app.command()
@handle_cli_errors
def run(...):
    ...
```

- [ ] **Step 3: Run the new tests**

Run: `python -m pytest tests/test_cli.py::test_invalid_config_shows_friendly_error tests/test_cli.py::test_missing_env_file_shows_friendly_error tests/test_cli.py::test_decorator_does_not_affect_normal_flow -v`

Expected: PASS

- [ ] **Step 4: Run full CLI test suite**

Run: `python -m pytest tests/test_cli.py -v`

Expected: All tests pass

- [ ] **Step 5: Run full test suite for regressions**

Run: `python -m pytest tests/ -x -q`

Expected: 994+ passed, 0 failed

- [ ] **Step 6: Commit**

```bash
git add personalscraper/cli.py
git commit -m "v11.2.2: Add @handle_cli_errors decorator for user-friendly config errors"
```

## Task 3: Update IMPLEMENTATION.md

- [ ] **Step 1: Update V11 Phase 2 entry**

Mark Phase 2 as complete in `docs/IMPLEMENTATION.md`.

- [ ] **Step 2: Commit**

```bash
git add -f docs/IMPLEMENTATION.md
git commit -m "v11.2.3: Update IMPLEMENTATION.md — Phase 2 complete"
```
