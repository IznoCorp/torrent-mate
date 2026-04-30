"""Static and smoke tests for the three launchd plist templates (Phase 8.3).

Two levels of validation:

1. **Static (Linux-safe)**: each plist is parsed via :func:`plistlib.loads` and
   asserted for the required keys (``Label``, ``ProgramArguments``,
   ``StandardOutPath``, ``StandardErrorPath``, ``StartCalendarInterval``).
   Runs on every CI platform.

2. **macOS smoke** (``@pytest.mark.darwin_only``): calls
   ``launchctl bootstrap gui/<uid> <plist>`` then
   ``launchctl bootout gui/<uid> <plist>`` to verify the plist is accepted by
   the running launchd.  Skipped automatically on Linux/Windows runners
   via :func:`tests.conftest.pytest_collection_modifyitems`.

Test strategy:
    All static tests are parametrised over the three plist paths so that adding
    a fourth plist in the future only requires extending the ``PLIST_PATHS``
    tuple — no new test functions needed.
"""

import os
import plistlib
import subprocess
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Plist paths
# ---------------------------------------------------------------------------

_LAUNCHD_DIR = Path(__file__).parent.parent.parent / "docs" / "reference" / "launchd"

_QUICK_PLIST = _LAUNCHD_DIR / "personalscraper-index-quick.plist"
_ROTATE_PLIST = _LAUNCHD_DIR / "personalscraper-index-rotate.plist"
_ENRICH_PLIST = _LAUNCHD_DIR / "personalscraper-index-enrich.plist"

PLIST_PATHS = (
    pytest.param(_QUICK_PLIST, id="quick"),
    pytest.param(_ROTATE_PLIST, id="rotate"),
    pytest.param(_ENRICH_PLIST, id="enrich"),
)

# Required top-level keys for all plists (DESIGN §14).
_REQUIRED_KEYS = frozenset(
    {
        "Label",
        "ProgramArguments",
        "StandardOutPath",
        "StandardErrorPath",
        "StartCalendarInterval",
    }
)

# Expected Label values per plist.
_EXPECTED_LABELS = {
    _QUICK_PLIST: "com.personalscraper.index-quick",
    _ROTATE_PLIST: "com.personalscraper.index-rotate",
    _ENRICH_PLIST: "com.personalscraper.index-enrich",
}


# ---------------------------------------------------------------------------
# Static validation tests (Linux-safe)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("plist_path", PLIST_PATHS)
def test_plist_file_exists(plist_path: Path) -> None:
    """Each plist template must exist under docs/reference/launchd/.

    Args:
        plist_path: Absolute path to the plist file under test.
    """
    assert plist_path.is_file(), f"plist not found: {plist_path}"


@pytest.mark.parametrize("plist_path", PLIST_PATHS)
def test_plist_parses_as_valid_xml(plist_path: Path) -> None:
    """plistlib.loads must succeed without raising for all three plists.

    Args:
        plist_path: Absolute path to the plist file under test.
    """
    raw = plist_path.read_bytes()
    parsed = plistlib.loads(raw)
    assert isinstance(parsed, dict), f"expected a dict from plistlib.loads, got {type(parsed)}"


@pytest.mark.parametrize("plist_path", PLIST_PATHS)
def test_plist_required_keys_present(plist_path: Path) -> None:
    """All required keys must be present in the parsed plist dict.

    Required keys: Label, ProgramArguments, StandardOutPath, StandardErrorPath,
    StartCalendarInterval.

    Args:
        plist_path: Absolute path to the plist file under test.
    """
    parsed: dict = plistlib.loads(plist_path.read_bytes())
    missing = _REQUIRED_KEYS - parsed.keys()
    assert not missing, f"{plist_path.name} is missing required keys: {missing}"


@pytest.mark.parametrize("plist_path", PLIST_PATHS)
def test_plist_label_matches_convention(plist_path: Path) -> None:
    """Label must follow the com.personalscraper.index-<name> convention.

    Args:
        plist_path: Absolute path to the plist file under test.
    """
    parsed: dict = plistlib.loads(plist_path.read_bytes())
    expected = _EXPECTED_LABELS[plist_path]
    assert parsed["Label"] == expected, f"{plist_path.name}: expected Label '{expected}', got '{parsed['Label']}'"


@pytest.mark.parametrize("plist_path", PLIST_PATHS)
def test_plist_program_arguments_is_list(plist_path: Path) -> None:
    """ProgramArguments must be a non-empty list of strings.

    Args:
        plist_path: Absolute path to the plist file under test.
    """
    parsed: dict = plistlib.loads(plist_path.read_bytes())
    args = parsed["ProgramArguments"]
    assert isinstance(args, list), f"{plist_path.name}: ProgramArguments must be a list"
    assert len(args) >= 1, f"{plist_path.name}: ProgramArguments is empty"
    for arg in args:
        assert isinstance(arg, str), f"{plist_path.name}: ProgramArguments element {arg!r} is not a str"


@pytest.mark.parametrize("plist_path", PLIST_PATHS)
def test_plist_run_at_load_is_false(plist_path: Path) -> None:
    """RunAtLoad must be False (or absent) — plists are opt-in only.

    Args:
        plist_path: Absolute path to the plist file under test.
    """
    parsed: dict = plistlib.loads(plist_path.read_bytes())
    # RunAtLoad defaults to False when absent, so both absent and explicit False are correct.
    run_at_load = parsed.get("RunAtLoad", False)
    assert run_at_load is False, (
        f"{plist_path.name}: RunAtLoad must be False (opt-in plists must not run on agent load)"
    )


@pytest.mark.parametrize("plist_path", PLIST_PATHS)
def test_plist_start_calendar_interval_is_dict_or_list(plist_path: Path) -> None:
    """StartCalendarInterval must be a dict (single schedule) or list of dicts.

    Args:
        plist_path: Absolute path to the plist file under test.
    """
    parsed: dict = plistlib.loads(plist_path.read_bytes())
    sci = parsed["StartCalendarInterval"]
    assert isinstance(sci, (dict, list)), (
        f"{plist_path.name}: StartCalendarInterval must be dict or list, got {type(sci)}"
    )


def test_quick_plist_scheduled_at_0330() -> None:
    """Quick plist must fire at Hour=3, Minute=30 (DESIGN §14).

    No args — specific to the quick plist schedule.
    """
    parsed: dict = plistlib.loads(_QUICK_PLIST.read_bytes())
    sci = parsed["StartCalendarInterval"]
    assert isinstance(sci, dict), "quick plist StartCalendarInterval must be a dict"
    assert sci.get("Hour") == 3, f"expected Hour=3, got {sci.get('Hour')}"
    assert sci.get("Minute") == 30, f"expected Minute=30, got {sci.get('Minute')}"


def test_enrich_plist_scheduled_weekly_sunday() -> None:
    """Enrich plist must fire on Weekday=0 (Sunday), Hour=4, Minute=0 (DESIGN §14).

    No args — specific to the enrich plist schedule.
    """
    parsed: dict = plistlib.loads(_ENRICH_PLIST.read_bytes())
    sci = parsed["StartCalendarInterval"]
    assert isinstance(sci, dict), "enrich plist StartCalendarInterval must be a dict"
    assert sci.get("Weekday") == 0, f"expected Weekday=0 (Sunday), got {sci.get('Weekday')}"
    assert sci.get("Hour") == 4, f"expected Hour=4, got {sci.get('Hour')}"
    assert sci.get("Minute") == 0, f"expected Minute=0, got {sci.get('Minute')}"


def test_rotate_shell_wrapper_exists() -> None:
    """index-rotate.sh must exist alongside the rotate plist.

    The rotate plist delegates disk selection to this script; the plist alone
    cannot express the Mon/Tue/… rotation logic.
    """
    wrapper = _LAUNCHD_DIR / "index-rotate.sh"
    assert wrapper.is_file(), f"rotate shell wrapper not found: {wrapper}"


def test_rotate_shell_wrapper_is_executable() -> None:
    """index-rotate.sh must have the executable bit set.

    The plist calls it via /bin/bash, but the file should be self-executable
    for direct manual invocation.
    """
    wrapper = _LAUNCHD_DIR / "index-rotate.sh"
    assert os.access(wrapper, os.X_OK), f"{wrapper} must be executable (chmod +x)"


def test_rotate_shell_wrapper_references_correct_modes() -> None:
    """index-rotate.sh must reference --mode full for Mon-Thu and --mode quick for fallback.

    Validates the rotation logic is in the script without executing it.
    """
    wrapper = _LAUNCHD_DIR / "index-rotate.sh"
    content = wrapper.read_text()
    assert "--mode full" in content, "rotate wrapper must use --mode full for disk days"
    assert "--mode quick" in content, "rotate wrapper must use --mode quick as fallback"
    # Must reference disk label substitution.
    assert "--disk" in content, "rotate wrapper must pass --disk argument"


# ---------------------------------------------------------------------------
# macOS smoke tests — skipped on Linux/Windows
# ---------------------------------------------------------------------------


@pytest.mark.darwin_only
@pytest.mark.parametrize("plist_path", PLIST_PATHS)
def test_plist_launchctl_bootstrap_and_bootout(plist_path: Path, tmp_path: Path) -> None:
    """Smoke test: launchctl bootstrap + bootout must succeed on macOS.

    Creates a copy of the plist with a unique label (to avoid collisions with
    any real installed agent) and points StandardOutPath / StandardErrorPath at
    temporary files.  Bootstraps, then immediately boots out.

    Args:
        plist_path: Absolute path to the plist template under test.
        tmp_path: Pytest temporary directory for log paths and modified plist.
    """
    # Build a uniquely-labelled copy to avoid label collisions.
    raw = plist_path.read_bytes()
    parsed: dict = plistlib.loads(raw)

    # Patch the label to avoid colliding with a real installed agent.
    parsed["Label"] = parsed["Label"] + ".test"

    # Redirect logs to tmp_path so no real __logit__/ is needed.
    parsed["StandardOutPath"] = str(tmp_path / "out.log")
    parsed["StandardErrorPath"] = str(tmp_path / "err.log")

    # Patch ProgramArguments: replace the binary with /bin/true for the smoke test.
    parsed["ProgramArguments"] = ["/bin/true"]

    # Write the patched plist.
    patched_plist = tmp_path / plist_path.name
    patched_plist.write_bytes(plistlib.dumps(parsed))

    uid = str(os.getuid())
    domain = f"gui/{uid}"

    try:
        result = subprocess.run(
            ["launchctl", "bootstrap", domain, str(patched_plist)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, (
            f"launchctl bootstrap failed for {plist_path.name}:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
    finally:
        # Always attempt bootout to keep the system clean, even if bootstrap failed.
        subprocess.run(
            ["launchctl", "bootout", domain, str(patched_plist)],
            capture_output=True,
            timeout=10,
        )
