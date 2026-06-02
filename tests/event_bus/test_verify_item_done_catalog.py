"""VerifyItemDone must resolve from the eager catalog WITHOUT importing verify.run.

Runs in a subprocess so the test session's prior imports cannot mask the gap.
"""

import subprocess
import sys


def test_verify_item_done_resolves_from_catalog_only():
    """VerifyItemDone resolves from the eager catalog without importing verify.run."""
    # Import ONLY the catalog (personalscraper.events) — NOT verify.run / verify.events.
    # The fix is that the catalog eager-registers every producer, so VerifyItemDone
    # must be in _EVENT_CLASS_REGISTRY (exactly what event_from_envelope looks up).
    # Do NOT import the producer to build the event — that would register it as a
    # side effect and mask the gap. Get the class from the catalog-populated registry,
    # then round-trip through the real serializer.
    code = (
        "import personalscraper.events  # catalog ONLY\n"
        "from personalscraper.core.event_bus import ("
        "_EVENT_CLASS_REGISTRY, event_to_envelope, event_from_envelope)\n"
        "assert 'VerifyItemDone' in _EVENT_CLASS_REGISTRY, 'catalog did not eager-register VerifyItemDone'\n"
        "cls = _EVENT_CLASS_REGISTRY['VerifyItemDone']\n"
        "env = event_to_envelope(cls(item='X (2020)', status='valid',"
        " errors=[], checks_passed=5, checks_total=5))\n"
        "assert type(event_from_envelope(env)).__name__ == 'VerifyItemDone'\n"
        "print('OK')\n"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, f"resolution failed:\n{proc.stderr}"
    assert "OK" in proc.stdout
