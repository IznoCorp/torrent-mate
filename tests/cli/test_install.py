"""Tests for :mod:`kanbanmate.cli.install` — the host-tier installer (DESIGN §4.1/§5/§10).

Every test is fully isolated:

* ``tmp_path`` stands in for ``~/.kanban`` — no real runtime root is created.
* ``subprocess.run`` is replaced by a ``MagicMock`` — no real PM2 is invoked; the tests assert on
  the exact argv lists instead.
* the effective-uid probe is injected so the root-refusal path is exercised without privileges.

The assertions pin the security-critical invariants: directory mode ``0o700``, token mode ``0o600``,
the ``PAUSE`` sentinel absent by default, idempotence on a second call (no error, no clobber), and
the non-root guard.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from kanbanmate.cli import install as host_installer
from kanbanmate.cli.install import (
    PAUSE_FILENAME,
    PM2_APP_NAME,
    PM2_SERVE_APP_NAME,
    REAPER_LABEL,
    ROOT_MODE,
    TOKEN_FILENAME,
    TOKEN_MODE,
    RootPrivilegeError,
    host_install,
    host_uninstall,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _completed(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[Any]:
    """Build a :class:`subprocess.CompletedProcess` for the mock runner to return."""
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def _mode(path: Path) -> int:
    """Return the permission bits (``& 0o777``) of *path*."""
    return stat.S_IMODE(path.stat().st_mode)


def _non_root() -> int:
    """Stand-in ``geteuid`` returning a non-root uid so the guard passes."""
    return 1000


def _root() -> int:
    """Stand-in ``geteuid`` returning 0 so the root-refusal path triggers."""
    return 0


# ============================================================================
# host_install — filesystem skeleton
# ============================================================================


class TestHostInstallSkeleton:
    """The ``~/.kanban`` skeleton: modes, token seeding, and the PAUSE convention."""

    def test_creates_root_with_mode_700(self, tmp_path: Path) -> None:
        """The runtime root is created with owner-only permissions (DESIGN §10)."""
        root = tmp_path / "kanban"
        mock_runner = MagicMock(return_value=_completed())

        result = host_install(
            root,
            runner=mock_runner,
            ecosystem_path=tmp_path / "ecosystem.config.js",
            geteuid=_non_root,
        )

        assert result == root
        assert root.is_dir()
        assert _mode(root) == ROOT_MODE
        assert ROOT_MODE == 0o700

    def test_seeds_token_with_mode_600(self, tmp_path: Path) -> None:
        """The token skeleton is created with mode 0o600 and a non-secret placeholder body."""
        root = tmp_path / "kanban"
        mock_runner = MagicMock(return_value=_completed())

        host_install(
            root,
            runner=mock_runner,
            ecosystem_path=tmp_path / "ecosystem.config.js",
            geteuid=_non_root,
        )

        token = root / TOKEN_FILENAME
        assert token.is_file()
        assert _mode(token) == TOKEN_MODE
        assert TOKEN_MODE == 0o600
        # The placeholder must NOT contain a real-looking secret — it is a comment block.
        body = token.read_text(encoding="utf-8")
        assert body.lstrip().startswith("#")
        assert "Paste your personal access token" in body

    def test_pause_sentinel_absent_by_default(self, tmp_path: Path) -> None:
        """The kill-switch sentinel is NEVER created by the installer (DESIGN §10 / H5)."""
        root = tmp_path / "kanban"
        mock_runner = MagicMock(return_value=_completed())

        host_install(
            root,
            runner=mock_runner,
            ecosystem_path=tmp_path / "ecosystem.config.js",
            geteuid=_non_root,
        )

        assert not (root / PAUSE_FILENAME).exists()

    def test_writes_ecosystem_file(self, tmp_path: Path) -> None:
        """``ecosystem.config.js`` is written and describes the kanban app running ``run``."""
        root = tmp_path / "kanban"
        eco = tmp_path / "ecosystem.config.js"
        mock_runner = MagicMock(return_value=_completed())

        host_install(root, runner=mock_runner, ecosystem_path=eco, geteuid=_non_root)

        assert eco.is_file()
        body = eco.read_text(encoding="utf-8")
        assert f'name: "{PM2_APP_NAME}"' in body
        assert 'args: "run"' in body
        assert "autorestart: true" in body
        # MANDATORY: kanban is a Python console-script, so PM2 must exec it via its shebang.
        # Without interpreter:"none", PM2 runs it through Node and crashes on the Python source.
        assert 'interpreter: "none"' in body


# ============================================================================
# host_install — PM2 wiring
# ============================================================================


class TestHostInstallPm2:
    """PM2 subprocess wiring: correct argv, argv-list safety, and the run_pm2 gate."""

    def test_issues_pm2_start_save_startup(self, tmp_path: Path) -> None:
        """The three PM2 commands are issued with the right argv (start --only, save, startup)."""
        root = tmp_path / "kanban"
        eco = tmp_path / "ecosystem.config.js"
        mock_runner = MagicMock(return_value=_completed())

        host_install(root, runner=mock_runner, ecosystem_path=eco, geteuid=_non_root)

        mock_runner.assert_any_call(
            ["pm2", "start", str(eco), "--only", PM2_APP_NAME], capture_output=True, text=True
        )
        mock_runner.assert_any_call(["pm2", "save"], capture_output=True, text=True)
        mock_runner.assert_any_call(["pm2", "startup"], capture_output=True, text=True)

    def test_pm2_calls_use_argv_lists_no_shell(self, tmp_path: Path) -> None:
        """Every PM2 call passes an argv list and never sets shell=True (injection-safe)."""
        root = tmp_path / "kanban"
        mock_runner = MagicMock(return_value=_completed())

        host_install(
            root,
            runner=mock_runner,
            ecosystem_path=tmp_path / "ecosystem.config.js",
            geteuid=_non_root,
        )

        assert mock_runner.call_count == 3
        for call_args in mock_runner.call_args_list:
            args, kwargs = call_args
            assert isinstance(args[0], list)
            assert kwargs.get("shell") is not True

    def test_run_pm2_false_skips_subprocess(self, tmp_path: Path) -> None:
        """``run_pm2=False`` still writes the ecosystem file but issues no PM2 calls."""
        root = tmp_path / "kanban"
        eco = tmp_path / "ecosystem.config.js"
        mock_runner = MagicMock(return_value=_completed())

        host_install(root, run_pm2=False, runner=mock_runner, ecosystem_path=eco, geteuid=_non_root)

        assert eco.is_file()
        mock_runner.assert_not_called()

    def test_nonzero_pm2_exit_tolerated(self, tmp_path: Path) -> None:
        """A non-zero PM2 exit (e.g. already-configured startup) does not raise — idempotent."""
        root = tmp_path / "kanban"
        # Simulate `pm2 startup` reporting an already-installed boot hook (non-zero, no check).
        mock_runner = MagicMock(return_value=_completed(returncode=1, stderr="already configured"))

        # Must not raise.
        host_install(
            root,
            runner=mock_runner,
            ecosystem_path=tmp_path / "ecosystem.config.js",
            geteuid=_non_root,
        )


# ============================================================================
# host_install — idempotence
# ============================================================================


class TestHostInstallIdempotence:
    """A second invocation must not error and must not clobber operator state."""

    def test_second_call_does_not_error(self, tmp_path: Path) -> None:
        """Running install twice succeeds both times (no clobber, no exception)."""
        root = tmp_path / "kanban"
        eco = tmp_path / "ecosystem.config.js"
        mock_runner = MagicMock(return_value=_completed())

        host_install(root, runner=mock_runner, ecosystem_path=eco, geteuid=_non_root)
        host_install(root, runner=mock_runner, ecosystem_path=eco, geteuid=_non_root)

        assert root.is_dir()
        assert _mode(root) == ROOT_MODE
        assert _mode(root / TOKEN_FILENAME) == TOKEN_MODE

    def test_existing_token_is_not_clobbered(self, tmp_path: Path) -> None:
        """A pre-existing token (real PAT) is preserved verbatim on re-install."""
        root = tmp_path / "kanban"
        root.mkdir()
        token = root / TOKEN_FILENAME
        token.write_text("ghp_REAL_OPERATOR_TOKEN\n", encoding="utf-8")
        os.chmod(token, TOKEN_MODE)
        mock_runner = MagicMock(return_value=_completed())

        host_install(
            root,
            runner=mock_runner,
            ecosystem_path=tmp_path / "ecosystem.config.js",
            geteuid=_non_root,
        )

        # The operator's token content is untouched.
        assert token.read_text(encoding="utf-8") == "ghp_REAL_OPERATOR_TOKEN\n"


# ============================================================================
# host_install — non-root safety (DESIGN §10)
# ============================================================================


class TestHostInstallRootRefusal:
    """The installer must refuse to run as root and create nothing."""

    def test_refuses_as_root(self, tmp_path: Path) -> None:
        """``geteuid() == 0`` raises RootPrivilegeError before any filesystem work."""
        root = tmp_path / "kanban"
        mock_runner = MagicMock(return_value=_completed())

        with pytest.raises(RootPrivilegeError):
            host_install(
                root,
                runner=mock_runner,
                ecosystem_path=tmp_path / "ecosystem.config.js",
                geteuid=_root,
            )

        # Nothing created, no PM2 call made — the guard runs first.
        assert not root.exists()
        mock_runner.assert_not_called()


# ============================================================================
# host_install — kanban_command flag (§11.A)
# ============================================================================


class TestKanbanCommandFlag:
    """``--kanban-command`` bakes the supplied path into ``ecosystem.config.js`` ``script:``.

    Tests at the ``host_install`` level (the existing pattern — no CliRunner, no real CLI
    invocation).  The forwarding test proves the Typer option reaches ``host_install`` without
    touching the real ``claude`` binary.
    """

    def test_custom_absolute_path_baked_into_script_line(self, tmp_path: Path) -> None:
        """``kanban_command="/abs/pyenv/3.12.4/bin/kanban"`` → ``script: "/abs/..."``."""
        root = tmp_path / "kanban"
        eco = tmp_path / "ecosystem.config.js"
        mock_runner = MagicMock(return_value=_completed())

        host_install(
            root,
            run_pm2=False,
            runner=mock_runner,
            ecosystem_path=eco,
            kanban_command="/abs/pyenv/3.12.4/bin/kanban",
            geteuid=_non_root,
        )

        body = eco.read_text(encoding="utf-8")
        assert 'script: "/abs/pyenv/3.12.4/bin/kanban"' in body

    def test_default_kanban_command_keeps_bare_kanban(self, tmp_path: Path) -> None:
        """Default ``kanban_command="kanban"`` keeps ``script: "kanban"`` untouched."""
        root = tmp_path / "kanban"
        eco = tmp_path / "ecosystem.config.js"
        mock_runner = MagicMock(return_value=_completed())

        host_install(
            root,
            run_pm2=False,
            runner=mock_runner,
            ecosystem_path=eco,
            geteuid=_non_root,
        )

        body = eco.read_text(encoding="utf-8")
        assert 'script: "kanban"' in body

    def test_install_command_forwards_kanban_command_to_host_install(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The Typer ``install`` command passes ``--kanban-command`` through to ``host_install``.

        Uses a spy on ``host_installer.host_install`` and a stub on ``claude_install`` so the
        real ``claude`` binary is never invoked.  This proves the forwarding without driving
        the full CLI (no CliRunner).
        """
        from kanbanmate.cli import app as app_mod
        from kanbanmate.cli import install as install_mod

        spy = MagicMock(return_value=tmp_path / "kanban")
        monkeypatch.setattr(install_mod, "host_install", spy)
        monkeypatch.setattr(install_mod, "claude_install", MagicMock())

        app_mod.install(
            root=tmp_path / "kanban",
            pm2=False,
            repo=tmp_path,
            kanban_command="/abs/pyenv/3.12.4/bin/kanban",
        )

        spy.assert_called_once()
        _, kwargs = spy.call_args
        assert kwargs["kanban_command"] == "/abs/pyenv/3.12.4/bin/kanban"


# ============================================================================
# host_uninstall
# ============================================================================


class TestHostUninstall:
    """Teardown: PM2 delete, token preservation, and idempotence."""

    def test_issues_pm2_delete(self, tmp_path: Path) -> None:
        """Uninstall issues ``pm2 delete kanban`` with an argv list."""
        root = tmp_path / "kanban"
        # Use an empty LaunchAgents dir so the plist-removal step is a silent no-op
        # and we assert on the PM2 call in isolation.
        la_dir = tmp_path / "LaunchAgents"
        la_dir.mkdir()
        mock_runner = MagicMock(return_value=_completed())

        host_uninstall(root, runner=mock_runner, launch_agents_dir=la_dir, geteuid=_non_root)

        mock_runner.assert_any_call(["pm2", "delete", PM2_APP_NAME], capture_output=True, text=True)

    def test_leaves_token_by_default(self, tmp_path: Path) -> None:
        """By default the token is preserved (it may hold a real PAT)."""
        root = tmp_path / "kanban"
        root.mkdir()
        token = root / TOKEN_FILENAME
        token.write_text("ghp_KEEP_ME\n", encoding="utf-8")
        la_dir = tmp_path / "LaunchAgents"
        la_dir.mkdir()
        mock_runner = MagicMock(return_value=_completed())

        host_uninstall(root, runner=mock_runner, launch_agents_dir=la_dir, geteuid=_non_root)

        assert token.is_file()
        assert token.read_text(encoding="utf-8") == "ghp_KEEP_ME\n"

    def test_remove_token_when_requested(self, tmp_path: Path) -> None:
        """``remove_token=True`` deletes the token file."""
        root = tmp_path / "kanban"
        root.mkdir()
        token = root / TOKEN_FILENAME
        token.write_text("ghp_DELETE_ME\n", encoding="utf-8")
        la_dir = tmp_path / "LaunchAgents"
        la_dir.mkdir()
        mock_runner = MagicMock(return_value=_completed())

        host_uninstall(
            root,
            runner=mock_runner,
            remove_token=True,
            launch_agents_dir=la_dir,
            geteuid=_non_root,
        )

        assert not token.exists()

    def test_idempotent_when_token_absent(self, tmp_path: Path) -> None:
        """Removing an already-absent token does not raise (idempotent teardown)."""
        root = tmp_path / "kanban"
        root.mkdir()
        la_dir = tmp_path / "LaunchAgents"
        la_dir.mkdir()
        mock_runner = MagicMock(return_value=_completed())

        # No token file present — must not error even with remove_token=True.
        host_uninstall(
            root,
            runner=mock_runner,
            remove_token=True,
            launch_agents_dir=la_dir,
            geteuid=_non_root,
        )

    def test_run_pm2_false_skips_delete(self, tmp_path: Path) -> None:
        """``run_pm2=False`` performs host teardown only — no PM2 call (plist absent → no launchctl)."""
        root = tmp_path / "kanban"
        root.mkdir()
        la_dir = tmp_path / "LaunchAgents"
        la_dir.mkdir()
        mock_runner = MagicMock(return_value=_completed())

        host_uninstall(
            root,
            run_pm2=False,
            runner=mock_runner,
            launch_agents_dir=la_dir,
            geteuid=_non_root,
        )

        mock_runner.assert_not_called()

    def test_refuses_as_root(self, tmp_path: Path) -> None:
        """Uninstall refuses to run as root (DESIGN §10)."""
        root = tmp_path / "kanban"
        mock_runner = MagicMock(return_value=_completed())

        with pytest.raises(RootPrivilegeError):
            host_uninstall(root, runner=mock_runner, geteuid=_root)

        mock_runner.assert_not_called()


# ============================================================================
# host_uninstall — PoC reaper plist removal (DESIGN §11 cutover)
# ============================================================================


class TestHostUninstallReaperPlist:
    """Removal of the old PoC launchd reaper plist (DESIGN §11 cutover).

    The PoC installed a ``launchd`` plist to schedule the reaper sweep.  KanbanMate's
    daemon now has an in-process reaper (§8.3), so ``kanban uninstall`` cleans up the
    dead plist.  Every test uses an isolated ``tmp_path`` as *launch_agents_dir* so the
    real ``~/Library/LaunchAgents`` is never touched.
    """

    def test_removes_plist_when_present(self, tmp_path: Path) -> None:
        """Plist exists → ``launchctl unload`` + ``rm``; file is gone afterwards."""
        root = tmp_path / "kanban"
        root.mkdir()
        la_dir = tmp_path / "LaunchAgents"
        la_dir.mkdir()
        plist = la_dir / f"{REAPER_LABEL}.plist"
        plist.write_text("<plist>...</plist>")
        mock_runner = MagicMock(return_value=_completed())

        host_uninstall(
            root,
            runner=mock_runner,
            run_pm2=False,
            launch_agents_dir=la_dir,
            geteuid=_non_root,
        )

        # launchctl unload was issued for the correct plist path.
        mock_runner.assert_called_once_with(
            ["launchctl", "unload", str(plist)], capture_output=True, text=True
        )
        # The plist file itself is removed.
        assert not plist.exists()

    def test_skips_when_plist_absent(self, tmp_path: Path) -> None:
        """No plist present → no launchctl call, no error (idempotent)."""
        root = tmp_path / "kanban"
        root.mkdir()
        la_dir = tmp_path / "LaunchAgents"
        la_dir.mkdir()
        mock_runner = MagicMock(return_value=_completed())

        host_uninstall(
            root,
            runner=mock_runner,
            run_pm2=False,
            launch_agents_dir=la_dir,
            geteuid=_non_root,
        )

        # Neither pm2 nor launchctl was called — plist absent, pm2 skipped.
        mock_runner.assert_not_called()

    def test_launchctl_failure_tolerated_plist_still_removed(self, tmp_path: Path) -> None:
        """``launchctl unload`` exits non-zero → file is STILL removed (best-effort)."""
        root = tmp_path / "kanban"
        root.mkdir()
        la_dir = tmp_path / "LaunchAgents"
        la_dir.mkdir()
        plist = la_dir / f"{REAPER_LABEL}.plist"
        plist.write_text("<plist>...</plist>")
        # Simulate launchctl failing (plist was never loaded, or already gone).
        mock_runner = MagicMock(
            return_value=_completed(returncode=1, stderr="Could not find specified service")
        )

        host_uninstall(
            root,
            runner=mock_runner,
            run_pm2=False,
            launch_agents_dir=la_dir,
            geteuid=_non_root,
        )

        # launchctl was attempted despite the expected failure.
        mock_runner.assert_called_once_with(
            ["launchctl", "unload", str(plist)], capture_output=True, text=True
        )
        # File is removed regardless — the unload is best-effort, the rm is what matters.
        assert not plist.exists()

    def test_integration_with_pm2_delete(self, tmp_path: Path) -> None:
        """When both PM2 and the plist are present, both are torn down."""
        root = tmp_path / "kanban"
        root.mkdir()
        la_dir = tmp_path / "LaunchAgents"
        la_dir.mkdir()
        plist = la_dir / f"{REAPER_LABEL}.plist"
        plist.write_text("<plist>...</plist>")
        mock_runner = MagicMock(return_value=_completed())

        host_uninstall(
            root,
            runner=mock_runner,
            launch_agents_dir=la_dir,
            geteuid=_non_root,
        )

        # Both PM2 deletes (daemon + receiver) and launchctl unload were issued (the receiver
        # delete is a no-op when it was never installed, but uninstall always issues it — §8).
        mock_runner.assert_any_call(["pm2", "delete", PM2_APP_NAME], capture_output=True, text=True)
        mock_runner.assert_any_call(
            ["pm2", "delete", PM2_SERVE_APP_NAME], capture_output=True, text=True
        )
        mock_runner.assert_any_call(
            ["launchctl", "unload", str(plist)], capture_output=True, text=True
        )
        assert mock_runner.call_count == 3
        # Plist removed.
        assert not plist.exists()


# ============================================================================
# Module-level API contract
# ============================================================================


class TestModuleApi:
    """Smoke-checks on the module's public surface used by ``cli/app.py``."""

    def test_importable_without_side_effects(self) -> None:
        """Importing the module performs no I/O and exposes the expected callables."""
        assert callable(host_installer.host_install)
        assert callable(host_installer.host_uninstall)
        assert issubclass(host_installer.RootPrivilegeError, RuntimeError)
