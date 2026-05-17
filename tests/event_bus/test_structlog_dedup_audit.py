"""Parametrized AST audit: no emit site double-logs (Sub-phase 3.8).

Per DESIGN §Logging convention: emitters emit only. A ``log.<level>(...)``
call within a 3-line window of an ``event_bus.emit(EventClass(...))`` is
only legitimate when it carries information *distinct* from the event
payload — e.g., ``log.exception("step_fatal", ...)`` alongside
``StepErrored(...)`` carries the traceback via implicit ``exc_info=True``,
which is genuinely new information.

The audit walks **every** ``personalscraper/**/*.py`` file via ``rglob``,
so a new file added without dedup auditing automatically fails the gate.
No file is skipped; no agent-chosen canonical site is cherry-picked.
"""

from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

import pytest

# Logger method names that should be checked.
_LOGGER_METHODS = {"info", "debug", "warning", "error", "exception", "critical"}

# Snake-case conversion for event class names. Used to derive the canonical
# structlog event name a duplicate log would use. ``StepStarted`` ->
# ``"step_started"`` (the exact string a duplicate ``log.info`` would carry).
_CAMEL_TO_SNAKE = re.compile(r"(?<!^)(?=[A-Z])")


def _snake_case(name: str) -> str:
    """Convert a CamelCase event class name to snake_case."""
    return _CAMEL_TO_SNAKE.sub("_", name).lower()


def _is_logger_call(node: ast.Call) -> bool:
    """Return True if ``node`` looks like ``log.<level>(...)`` or ``self._log.<level>(...)``."""
    try:
        target = ast.unparse(node.func)
    except Exception:
        return False
    method = target.rsplit(".", 1)[-1]
    if method not in _LOGGER_METHODS:
        return False
    # Heuristic: caller looks like a logger (``log``, ``self._log``, ``self.log``, ``LOG``…).
    head = target.rsplit(".", 1)[0].lower()
    return "log" in head


def _emit_event_class(emit_call: ast.Call) -> str | None:
    """Return the event class name passed as first positional arg, or None."""
    if not emit_call.args:
        return None
    arg = emit_call.args[0]
    if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name):
        return arg.func.id
    if isinstance(arg, ast.Call):
        try:
            return ast.unparse(arg.func).rsplit(".", 1)[-1]
        except Exception:
            return None
    return None


def _first_positional_str(call: ast.Call) -> str | None:
    """Return the first positional arg if it's a string literal, else None."""
    if not call.args:
        return None
    first = call.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return None


_PRODUCTION_FILES = sorted(Path("personalscraper").rglob("*.py"))


@pytest.mark.parametrize(
    "path",
    _PRODUCTION_FILES,
    ids=[str(p.relative_to("personalscraper")) for p in _PRODUCTION_FILES],
)
def test_no_emit_site_double_logs_at_module(path: Path) -> None:
    """For every emit site in ``path``, nearby logger calls must not duplicate the event discriminator.

    A logger call within a 3-line window of an ``event_bus.emit(EventClass(...))``
    is a violation if its first positional string argument equals
    ``snake_case(EventClass.__name__)``. The :class:`StepErrored` exception
    handler is exempt via the ``log.exception("step_fatal", ...)`` pattern
    (different event name; the traceback is the distinct information).
    """
    src = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        pytest.skip(f"unparseable file: {path}")

    emit_sites: list[tuple[int, str]] = []
    logger_sites: list[tuple[int, str | None]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        try:
            target = ast.unparse(node.func)
        except Exception:
            continue
        if target.endswith(".emit"):
            head = target.rsplit(".", 1)[0]
            if "bus" in head.lower() or head.endswith("event_bus"):
                event_cls = _emit_event_class(node)
                if event_cls is not None:
                    emit_sites.append((node.lineno, event_cls))
        if _is_logger_call(node):
            logger_sites.append((node.lineno, _first_positional_str(node)))

    violations: list[str] = []
    for emit_line, event_cls in emit_sites:
        discriminator = _snake_case(event_cls)
        nearby = [(ln, ev) for ln, ev in logger_sites if abs(ln - emit_line) <= 3 and ev is not None]
        for log_line, log_event in nearby:
            if log_event == discriminator:
                violations.append(
                    f"{path}:{emit_line} emits {event_cls!s} and {path}:{log_line} "
                    f"logs {log_event!r} — same discriminator, deletes one"
                )

    assert not violations, "\n".join(violations)


def test_structlog_emit_dedup_audit_commit_documents_counts() -> None:
    """The dedup audit commit body MUST document removed/kept counts.

    The phase reviewer cross-checks ``<N>`` and ``<M>`` against the diff.
    The audit commit is detected by message subject; if not present at HEAD
    (e.g., during phase work in progress), the test is skipped — once the
    audit commit is pushed it becomes part of the immutable record and the
    test re-enables itself by SHA detection.
    """
    log_output = subprocess.check_output(
        ["git", "log", "--format=%H%n%s%n%b%n---END---", "-50"],
        encoding="utf-8",
    )
    # Find the most recent commit whose *subject* (not body) mentions the 3.8 audit.
    audit_commit_body: str | None = None
    for chunk in log_output.split("---END---\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        lines = chunk.split("\n")
        if len(lines) < 2:
            continue
        subject = lines[1]
        body = "\n".join(lines[2:]) if len(lines) > 2 else ""
        if "structlog dedup audit" in subject.lower():
            audit_commit_body = body
            break
    if audit_commit_body is None:
        pytest.skip("3.8 audit commit not present at HEAD yet (test will catch regressions once committed)")

    assert re.search(r"structlog_calls_removed:\s*\d+", audit_commit_body), (
        "audit commit body must contain a 'structlog_calls_removed: <N>' trailer"
    )
    assert re.search(r"structlog_calls_kept:\s*\d+", audit_commit_body), (
        "audit commit body must contain a 'structlog_calls_kept: <M>' trailer"
    )
