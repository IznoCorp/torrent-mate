"""Tests for the backend's two counting arms (14 and 15) of the no-French guard.

They measure a fixture tree, never the real one: the arms take the repository
root and the baseline file as parameters for exactly that.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import nofrench_backend as backend  # noqa: E402


def load_guard():
    """Imports the guard as a module, despite its hyphenated filename."""
    spec = importlib.util.spec_from_file_location("check_no_french", SCRIPTS / "check-no-french.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = load_guard()

FRENCH = "Téléchargement terminé"  # french-ok: the fixture's French text


def tree(tmp_path: Path, source: str) -> Path:
    """Writes one module under a fixture `personalscraper/` and returns the root."""
    package = tmp_path / "personalscraper"
    package.mkdir()
    (package / "mod.py").write_text(source, encoding="utf-8")
    return tmp_path


def baseline(tmp_path: Path, **figures: int) -> Path:
    """Writes a baseline file holding the given figures."""
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(figures), encoding="utf-8")
    return path


def run_french(root: Path, allowed: int) -> list[str]:
    """Runs arm 14 over a fixture against a baseline of `allowed`."""
    violations: list[str] = []
    guard.check_backend_french(violations, root=root, baseline_path=baseline(root, backend=allowed))
    return violations


def run_sinks(root: Path, allowed: int) -> list[str]:
    """Runs arm 15 over a fixture against a baseline of `allowed`."""
    violations: list[str] = []
    guard.check_backend_sinks(violations, root=root, baseline_path=baseline(root, backend_sinks=allowed))
    return violations


class TestBackendFrench:
    """Arm 14: the French literals of `personalscraper/`, under a ratchet."""

    def test_one_more_than_the_baseline_is_a_violation(self, tmp_path: Path) -> None:
        """A French literal beyond the baseline is refused."""
        root = tree(tmp_path, f'X = "{FRENCH}"\nY = "{FRENCH}"\n')
        assert len(backend.backend_french_literals(root)) == 2
        assert len(run_french(root, allowed=1)) == 1

    def test_at_the_baseline_is_counted_not_refused(self, tmp_path: Path) -> None:
        """The existing French is a counted debt, not a violation."""
        root = tree(tmp_path, f'X = "{FRENCH}"\n')
        assert run_french(root, allowed=1) == []

    def test_a_pragma_with_a_reason_licenses_the_line(self, tmp_path: Path) -> None:
        """`# french-ok: why` takes the literal out of the count."""
        root = tree(tmp_path, f'X = "{FRENCH}"  # french-ok: a title regex\n')
        assert backend.backend_french_literals(root) == []
        assert run_french(root, allowed=0) == []

    def test_a_bare_pragma_licenses_nothing(self, tmp_path: Path) -> None:
        """A pragma citing no reason leaves the literal counted, hence refused."""
        root = tree(tmp_path, f'X = "{FRENCH}"  # french-ok:\n')
        assert len(backend.backend_french_literals(root)) == 1
        assert len(run_french(root, allowed=0)) == 1

    def test_a_missing_baseline_is_a_violation(self, tmp_path: Path) -> None:
        """No baseline key means the scope would be free to grow."""
        root = tree(tmp_path, "X = 1\n")
        violations: list[str] = []
        guard.check_backend_french(violations, root=root, baseline_path=baseline(root))
        assert len(violations) == 1


class TestBackendSinks:
    """Arm 15: the user-text sinks not fed by `t()`, under a ratchet."""

    def sites(self, tmp_path: Path, source: str) -> list[tuple[Path, int, str]]:
        """Measures one fixture module."""
        return backend.backend_text_sinks(tree(tmp_path, source))

    def test_a_console_print_of_text_is_counted(self, tmp_path: Path) -> None:
        """`console.print("Done now")` is a sink with text."""
        assert len(self.sites(tmp_path, 'console.print("Done now")\n')) == 1

    def test_a_console_print_of_t_is_not_counted(self, tmp_path: Path) -> None:
        """`console.print(t("x.y"))` is carried by the layer."""
        assert self.sites(tmp_path, 'console.print(t("x.y"))\n') == []

    def test_t_code_and_named_parameters_are_not_counted(self, tmp_path: Path) -> None:
        """A `t_code(...)` or a `t(..., n=…)` call is a translated sink."""
        source = 'console.print(t_code(code))\nconsole.print(t("a.b", n=3))\n'
        assert self.sites(tmp_path, source) == []

    def test_an_echo_of_an_f_string_is_counted(self, tmp_path: Path) -> None:
        """`echo(f"{n} items")` is a sink with text."""
        assert len(self.sites(tmp_path, 'echo(f"{n} items")\n')) == 1

    def test_text_beside_a_translated_part_is_counted(self, tmp_path: Path) -> None:
        """Only the `t()` subtree is exempt; literal text around it still counts."""
        assert len(self.sites(tmp_path, 'typer.echo(t("a.b") + " and more")\n')) == 1

    def test_a_one_word_constant_is_not_text(self, tmp_path: Path) -> None:
        """A style, a key or a unit is not a sentence."""
        assert self.sites(tmp_path, 'console.print(table, style="bold")\n') == []

    def test_a_log_call_is_not_a_user_sink(self, tmp_path: Path) -> None:
        """Logs are developer text; a bare `print` and `logger.info` are not sinks."""
        assert self.sites(tmp_path, 'print("two words")\nlogger.info("two words")\n') == []

    def test_help_and_prompt_keywords_are_counted(self, tmp_path: Path) -> None:
        """A `help=` literal counts; a `help=t(...)` does not."""
        source = (
            'opt = typer.Option(help="Some help text")\n'
            'ok = typer.Option(help=t("a.b"))\n'
            'ask = typer.Option(prompt="Your name please")\n'
        )
        assert [kind for _, _, kind in self.sites(tmp_path, source)] == ["keyword", "keyword"]

    def test_a_command_docstring_counts_unless_help_is_given(self, tmp_path: Path) -> None:
        """A docstring serving as a command's help is a sink; `help=` replaces it."""
        source = (
            '@app.command()\ndef a():\n    """Does a thing."""\n'
            '@app.command(help=t("a.b"))\ndef b():\n    """Does b."""\n'
            'def c():\n    """Not a command."""\n'
        )
        assert [kind for _, _, kind in self.sites(tmp_path, source)] == ["docstring"]

    def test_one_more_than_the_baseline_is_a_violation(self, tmp_path: Path) -> None:
        """The ratchet refuses growth and tolerates the baseline."""
        root = tree(tmp_path, 'echo("two words")\necho("more words")\n')
        assert len(run_sinks(root, allowed=1)) == 1
        assert run_sinks(root, allowed=2) == []


class TestRegistration:
    """The two arms are in `ARMS` and the guard's self-description agrees."""

    def test_the_arms_are_registered_and_described(self) -> None:
        """The self-description arm holds the count against docstring and CLAUDE.md."""
        assert guard.check_backend_french in [arm for arm, _ in guard.ARMS]
        assert guard.check_backend_sinks in [arm for arm, _ in guard.ARMS]
        violations: list[str] = []
        guard.check_arm_count(violations)
        assert violations == []
