"""The design host serves the generated lots progress, behind v1's session.

WHAT IT PAYS FOR. `/dev/lots.json` is the generator's output, written outside
the repository at the path `TM_DEV_LOTS_OUT` names. The host serves it to a
session v1 accepts and to nobody else, and says 404 — never an empty document
standing for one — when it is not configured or not written yet.

WHAT MAKES IT NON-VACUOUS. `serve.py` runs as the process it is, over the
scratch design root and the stub v1 of `test_design_host_switches.py`; every
answer is read on the wire.
"""

from __future__ import annotations

import json
from pathlib import Path

from test_design_host_switches import ACCEPTED, ask, scratch_root, serving, stub_v1

ADDRESS = "/dev/lots.json"
COOKIE = f"tm_v1_session={ACCEPTED}"


def written(tmp_path: Path) -> Path:
    """Writes a generated document where the host will be told to read it.

    Args:
        tmp_path: The pytest scratch directory.

    Returns:
        The output path.
    """
    out = tmp_path / "data" / "dev-lots.json"
    out.parent.mkdir()
    out.write_text(json.dumps({"available": True, "generatedAt": 1, "lots": []}), encoding="utf-8")
    return out


def test_a_session_reads_the_generated_document(tmp_path: Path) -> None:
    """A session v1 accepts gets the file as JSON, never cached."""
    out = written(tmp_path)
    with (
        stub_v1() as (v1, _),
        serving(scratch_root(tmp_path, stale=False), TM_DESIGN_V1_URL=v1, TM_DEV_LOTS_OUT=str(out)) as port,
    ):
        status, headers, body = ask(port, ADDRESS, cookie=COOKIE)
    assert status == 200
    assert headers["content-type"].startswith("application/json")
    assert headers["cache-control"] == "no-store"
    assert json.loads(body) == {"available": True, "generatedAt": 1, "lots": []}


def test_no_session_reads_nothing(tmp_path: Path) -> None:
    """Without a session v1 accepts the answer is an empty 401, the document never sent."""
    out = written(tmp_path)
    with (
        stub_v1() as (v1, _),
        serving(scratch_root(tmp_path, stale=False), TM_DESIGN_V1_URL=v1, TM_DEV_LOTS_OUT=str(out)) as port,
    ):
        for cookie in (None, "tm_v1_session=refused"):
            status, _, body = ask(port, ADDRESS, cookie=cookie)
            assert (status, body) == (401, b"")


def test_an_unconfigured_or_unwritten_output_is_not_found(tmp_path: Path) -> None:
    """No path configured, or nothing written there yet: 404, to a session too."""
    root = scratch_root(tmp_path, stale=False)
    with stub_v1() as (v1, _), serving(root, TM_DESIGN_V1_URL=v1) as port:
        assert ask(port, ADDRESS, cookie=COOKIE)[0] == 404
    absent = tmp_path / "never-written.json"
    with stub_v1() as (v1, _), serving(root, TM_DESIGN_V1_URL=v1, TM_DEV_LOTS_OUT=str(absent)) as port:
        assert ask(port, ADDRESS, cookie=COOKIE)[0] == 404
