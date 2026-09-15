"""The pre-push hook runs the documentation tests alone on a docs-only push.

WHAT IT PAID FOR. Every push ran the whole suite — minutes — including the
pushes that changed nothing but prose: a register row, a phase amendment, a
resume. When every file between the remote's ref and the pushed head is under
`docs/` or ends in `.md`, step 5 is the test modules that read documentation
and the documentation guards, by name; anything else keeps the whole suite.

AND A FAILING CHECK'S OUTPUT IS KEPT. `run_check` ran the command silently,
then ran it AGAIN to show why it failed — the suite twice, and a flake's
evidence replaced by a second run that may pass.

HOW IT IS READ. The real hook runs inside a scratch git repository, with a stub
`python` that journals its arguments, fed the ref lines git feeds a hook.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRE_PUSH = ROOT / "scripts" / "pre-push"
FULL_SUITE = "-m pytest -v -n auto"
ZEROS = "0" * 40


def _git(repository: Path, *arguments: str) -> str:
    """Run git in the scratch repository, with no hook and a fixed identity.

    Args:
        repository: The scratch repository.
        *arguments: The git subcommand and its arguments.

    Returns:
        The command's standard output, stripped.
    """
    return subprocess.run(
        [
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "user.name=test",
            "-c",
            "user.email=test@example.com",
            "-C",
            str(repository),
            *arguments,
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _commit(repository: Path, files: dict[str, str], message: str) -> str:
    """Write files and commit them.

    Args:
        repository: The scratch repository.
        files: Relative path to content.
        message: The commit message.

    Returns:
        The new commit's sha.
    """
    for relative, content in files.items():
        path = repository / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git(repository, "add", "-A")
    _git(repository, "commit", "-q", "-m", message)
    return _git(repository, "rev-parse", "HEAD")


def _run_hook(
    tmp_path: Path, ref_line: str, pytest_fails: bool = False
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    """Run the real hook in the scratch repository with a journaling stub `python`.

    Args:
        tmp_path: The test's directory; the repository is `repository/` under it.
        ref_line: What git feeds the hook on standard input.
        pytest_fails: Whether the stub fails its pytest invocations, printing a
            numbered piece of evidence each time.

    Returns:
        The completed process and the stub's journal, one line per invocation.
    """
    binaries = tmp_path / "bin"
    binaries.mkdir(exist_ok=True)
    journal = tmp_path / "journal.txt"
    journal.write_text("", encoding="utf-8")
    failing = "1" if pytest_fails else "0"
    stub = binaries / "python"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        f'echo "$*" >> "{journal}"\n'
        f'if [ "{failing}" = 1 ] && [ "$2" = pytest ]; then\n'
        f'  echo "EVIDENCE-$(grep -c -- "-m pytest" "{journal}")"; exit 1\n'
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{binaries}{os.pathsep}{environment['PATH']}"
    result = subprocess.run(
        [str(PRE_PUSH)],
        cwd=tmp_path / "repository",
        env=environment,
        input=ref_line,
        capture_output=True,
        text=True,
        check=False,
    )
    return result, journal.read_text(encoding="utf-8").splitlines()


def _repository(tmp_path: Path) -> tuple[str, str, str]:
    """Build a history: a base, a docs-only commit, then a commit touching code.

    Args:
        tmp_path: The test's directory.

    Returns:
        The base sha, the docs-only sha and the code sha.
    """
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init", "-q")
    base = _commit(repository, {"module.py": "x = 1\n", "docs/guide.md": "one\n"}, "base")
    docs = _commit(repository, {"docs/guide.md": "two\n", "BUGS.md": "row\n"}, "docs")
    code = _commit(repository, {"module.py": "x = 2\n", "docs/guide.md": "three\n"}, "code")
    return base, docs, code


def _pytest_calls(journal: list[str]) -> list[str]:
    """Keep the journal's pytest invocations.

    Args:
        journal: The stub's journal, one line per invocation.

    Returns:
        The lines that invoked pytest.
    """
    return [line for line in journal if line.startswith("-m pytest")]


def test_a_docs_only_push_runs_the_documentation_tests_and_guards_alone(tmp_path: Path) -> None:
    """Only docs changed between the remote's ref and the head: no full suite."""
    base, docs, _ = _repository(tmp_path)
    result, journal = _run_hook(tmp_path, f"refs/heads/topic {docs} refs/heads/topic {base}\n")

    assert result.returncode == 0, result.stdout + result.stderr
    calls = _pytest_calls(journal)
    assert len(calls) == 1 and calls[0] != FULL_SUITE, journal
    assert "tests/scripts/test_check_bug_register.py" in calls[0], calls
    assert "scripts/check-docs-cited-paths.py" in journal, journal


def test_a_push_touching_code_keeps_the_full_suite(tmp_path: Path) -> None:
    """THE CONTROL: one code file in the range and the whole suite runs, no docs guard."""
    base, _, code = _repository(tmp_path)
    result, journal = _run_hook(tmp_path, f"refs/heads/topic {code} refs/heads/topic {base}\n")

    assert result.returncode == 0, result.stdout + result.stderr
    assert _pytest_calls(journal) == [FULL_SUITE], journal
    assert "scripts/check-docs-cited-paths.py" not in journal, journal


def test_a_new_branch_keeps_the_full_suite(tmp_path: Path) -> None:
    """A remote ref of zeros names no range to read, so nothing is known to be docs."""
    _, docs, _ = _repository(tmp_path)
    _, journal = _run_hook(tmp_path, f"refs/heads/topic {docs} refs/heads/topic {ZEROS}\n")

    assert _pytest_calls(journal) == [FULL_SUITE], journal


def test_a_failing_check_runs_once_and_shows_its_own_output(tmp_path: Path) -> None:
    """The evidence printed is the failing run's, and the suite ran once."""
    base, _, code = _repository(tmp_path)
    result, journal = _run_hook(tmp_path, f"refs/heads/topic {code} refs/heads/topic {base}\n", pytest_fails=True)

    assert result.returncode == 1, result.stdout
    assert len(_pytest_calls(journal)) == 1, journal
    assert "EVIDENCE-1" in result.stdout, result.stdout
