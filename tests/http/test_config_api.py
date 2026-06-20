"""Tests for :mod:`kanbanmate.http.config_api`.

Uses FastAPI's TestClient over a real server-less test session.  The
ConfigService's path resolution is patched to point at a tmp_path clone.

Also includes the daemon-purity runtime test: import kanbanmate.daemon in an
isolated subprocess and assert 'fastapi' is not in sys.modules.
"""

from __future__ import annotations

import importlib.resources
import shutil
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="[ui] extra not installed")

from fastapi.testclient import TestClient  # noqa: E402 (after importorskip)

from kanbanmate.core.config_model import PipelineDraft  # noqa: E402
from kanbanmate.core.transitions_defaults import render_transitions_yaml  # noqa: E402


def _columns_template_path() -> Path:
    ref = importlib.resources.files("kanbanmate") / "assets" / "columns.yml.tmpl"
    with importlib.resources.as_file(ref) as p:
        return p


def _make_test_clone(tmp_path: Path) -> tuple[Path, Path]:
    """Return (transitions_path, columns_path) for a tmp clone."""
    config_dir = tmp_path / ".claude" / "kanban"
    config_dir.mkdir(parents=True)
    tp = config_dir / "transitions.yml"
    cp = config_dir / "columns.yml"
    tp.write_text(render_transitions_yaml("owner/repo"), encoding="utf-8")
    shutil.copy(_columns_template_path(), cp)
    return tp, cp


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Return a TestClient for the config API, pointing at a tmp clone."""
    import kanbanmate.http.config_api as api_mod
    from kanbanmate.app.config_service import ConfigService

    tp, cp = _make_test_clone(tmp_path)
    svc = ConfigService(transitions_path=tp, columns_path=cp)

    # Patch _get_service to return our injected service.
    monkeypatch.setattr(api_mod, "_get_service", lambda root=None: svc)

    return TestClient(api_mod.app)


# ---------------------------------------------------------------------------
# GET /api/health
# ---------------------------------------------------------------------------


def test_health(client: TestClient) -> None:
    """GET /api/health returns 200 and {"status": "ok"}."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# GET /api/config
# ---------------------------------------------------------------------------


def test_get_config(client: TestClient) -> None:
    """GET /api/config returns the current draft with 13 columns."""
    resp = client.get("/api/config")
    assert resp.status_code == 200
    body = resp.json()
    assert "definition" in body
    assert "binding" in body
    assert len(body["definition"]["columns"]) == 13


# ---------------------------------------------------------------------------
# POST /api/config/validate
# ---------------------------------------------------------------------------


def test_post_validate_clean(client: TestClient) -> None:
    """POST /api/config/validate with the shipped config returns ok=True."""
    draft = PipelineDraft.from_loaded(
        render_transitions_yaml("owner/repo"),
        _columns_template_path().read_text(encoding="utf-8"),
    )
    resp = client.post("/api/config/validate", json=asdict(draft))
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True


def test_post_validate_invalid(client: TestClient) -> None:
    """POST /api/config/validate with a bad permission_mode returns ok=False."""
    draft = PipelineDraft.from_loaded(
        render_transitions_yaml("owner/repo"),
        _columns_template_path().read_text(encoding="utf-8"),
    )
    # Inject an invalid permission_mode into the first transition.
    draft_dict = asdict(draft)
    if draft_dict["definition"]["transitions"]:
        draft_dict["definition"]["transitions"][0]["permission_mode"] = "bypassPermissions"
    resp = client.post("/api/config/validate", json=draft_dict)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["findings"]


# ---------------------------------------------------------------------------
# POST /api/config (validate-then-save)
# ---------------------------------------------------------------------------


def test_post_config_valid_saves(client: TestClient, tmp_path: Path) -> None:
    """POST /api/config with a valid draft returns 200 {"ok": true}."""
    draft = PipelineDraft.from_loaded(
        render_transitions_yaml("owner/repo"),
        _columns_template_path().read_text(encoding="utf-8"),
    )
    resp = client.post("/api/config", json=asdict(draft))
    assert resp.status_code == 200
    assert resp.json().get("ok") is True


def test_post_config_invalid_returns_422(client: TestClient) -> None:
    """POST /api/config with an invalid draft returns 422 and findings."""
    draft = PipelineDraft.from_loaded(
        render_transitions_yaml("owner/repo"),
        _columns_template_path().read_text(encoding="utf-8"),
    )
    draft_dict = asdict(draft)
    if draft_dict["definition"]["transitions"]:
        draft_dict["definition"]["transitions"][0]["permission_mode"] = "bypassPermissions"
    resp = client.post("/api/config", json=draft_dict)
    assert resp.status_code == 422
    body = resp.json()
    assert body.get("ok") is False
    assert body.get("findings")


def test_post_config_malformed_structure_returns_422(client: TestClient) -> None:
    """A structurally malformed body (column missing required keys) → 422 'Invalid draft structure'.

    Distinct from the validation-findings 422: _dict_to_draft raises when the
    JSON can't even construct the dataclasses (config_api.py:236-255).
    """
    bad = {
        "definition": {
            "columns": [{"key": "X"}],  # missing 'name' and 'column_class'
            "transitions": [],
            "defaults": {"concurrency_cap": 3, "move_rate_limit_per_hour": 10},
        },
        "binding": {"project": "owner/repo"},
    }
    resp = client.post("/api/config", json=bad)
    assert resp.status_code == 422
    assert "Invalid draft structure" in resp.json()["detail"]


def test_post_config_writes_to_disk(client: TestClient, tmp_path: Path) -> None:
    """POST /api/config with a modified valid draft persists the change to the clone file."""
    draft = PipelineDraft.from_loaded(
        render_transitions_yaml("owner/repo"),
        _columns_template_path().read_text(encoding="utf-8"),
    )
    draft_dict = asdict(draft)
    # Bump concurrency_cap to a distinctive value and POST it.
    draft_dict["definition"]["defaults"]["concurrency_cap"] = 7
    resp = client.post("/api/config", json=draft_dict)
    assert resp.status_code == 200
    # The fixture's clone lives under tmp_path/.claude/kanban (see _make_test_clone).
    transitions_text = (tmp_path / ".claude" / "kanban" / "transitions.yml").read_text(
        encoding="utf-8"
    )
    assert "concurrency_cap: 7" in transitions_text


# ---------------------------------------------------------------------------
# GET /api/config/render
# ---------------------------------------------------------------------------


def test_get_render(client: TestClient) -> None:
    """GET /api/config/render returns non-empty transitions and columns strings."""
    resp = client.get("/api/config/render")
    assert resp.status_code == 200
    body = resp.json()
    assert body["transitions"]
    assert body["columns"]
    assert "permission_mode" in body["transitions"]  # header present


# ---------------------------------------------------------------------------
# POST /api/config/resolve
# ---------------------------------------------------------------------------


def test_post_resolve_known_edge(client: TestClient) -> None:
    """POST /api/config/resolve for Backlog→Brainstorming returns matched=True, would_launch=True."""
    draft = PipelineDraft.from_loaded(
        render_transitions_yaml("owner/repo"),
        _columns_template_path().read_text(encoding="utf-8"),
    )
    payload = {"draft": asdict(draft), "from_col": "Backlog", "to_col": "Brainstorming"}
    resp = client.post("/api/config/resolve", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["matched"] is True
    assert body["would_launch"] is True


def test_post_resolve_unwhitelisted(client: TestClient) -> None:
    """POST /api/config/resolve for an un-whitelisted move returns matched=False."""
    draft = PipelineDraft.from_loaded(
        render_transitions_yaml("owner/repo"),
        _columns_template_path().read_text(encoding="utf-8"),
    )
    payload = {"draft": asdict(draft), "from_col": "Brainstorming", "to_col": "Merge"}
    resp = client.post("/api/config/resolve", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["matched"] is False


def test_post_resolve_invalid_draft_returns_422(client: TestClient) -> None:
    """A loader-rejected draft posted to /resolve returns 422, not an opaque 500."""
    draft = PipelineDraft.from_loaded(
        render_transitions_yaml("owner/repo"),
        _columns_template_path().read_text(encoding="utf-8"),
    )
    draft_dict = asdict(draft)
    # A banned permission_mode makes render→load_transitions raise ValueError
    # inside resolve(); the endpoint must map it to 422.
    if draft_dict["definition"]["transitions"]:
        draft_dict["definition"]["transitions"][0]["permission_mode"] = "bypassPermissions"
    payload = {"draft": draft_dict, "from_col": "Backlog", "to_col": "Brainstorming"}
    resp = client.post("/api/config/resolve", json=payload)
    assert resp.status_code == 422
    assert "Cannot resolve" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# GET /api/schema
# ---------------------------------------------------------------------------


def test_get_schema(client: TestClient) -> None:
    """GET /api/schema returns a JSON Schema with the expected top-level keys."""
    resp = client.get("/api/schema")
    assert resp.status_code == 200
    schema = resp.json()
    assert schema.get("title") == "PipelineDraft"
    assert "properties" in schema
    assert "definition" in schema["properties"]
    assert "binding" in schema["properties"]


# ---------------------------------------------------------------------------
# --root threading (app.state)
# ---------------------------------------------------------------------------


def test_get_service_honors_app_state_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """_get_service resolves the registry under app.state.kanban_root (CLI --root threading).

    Endpoints call _get_service() with no argument, so `kanban config serve --root`
    must reach it via app.state — otherwise the flag is silently dropped and every
    request reads the default ~/.kanban/ root.
    """
    import fastapi

    import kanbanmate.http.config_api as api_mod

    captured: dict[str, Path] = {}

    def fake_projects_path(root: Path) -> Path:
        captured["root"] = root
        return tmp_path / "projects.json"

    monkeypatch.setattr(api_mod, "_projects_path", fake_projects_path)
    monkeypatch.setattr(api_mod, "_load_registry", lambda p: {})
    custom = tmp_path / "custom-root"
    monkeypatch.setattr(api_mod.app.state, "kanban_root", custom, raising=False)

    # Empty registry → 503, but the resolved root must have threaded through first.
    with pytest.raises(fastapi.HTTPException):
        api_mod._get_service()
    assert captured["root"] == custom


# ---------------------------------------------------------------------------
# Daemon-purity test
# ---------------------------------------------------------------------------


def test_daemon_purity_no_fastapi_import() -> None:
    """import kanbanmate.daemon must NOT pull fastapi into sys.modules.

    The daemon hot-path is urllib-only (DESIGN §11.1, §15).  This test runs in
    an isolated subprocess so the test process's own [ui] install does not
    pollute the check.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import kanbanmate.daemon; "
                "assert 'fastapi' not in __import__('sys').modules, "
                "'fastapi was imported by kanbanmate.daemon'"
            ),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Daemon-purity test failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# Adversarial hardening regressions (helm-interface-hardening, 2026-06-19)
# ---------------------------------------------------------------------------


def _client_and_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[TestClient, Path, Path]:
    """Build a TestClient AND return the on-disk (transitions, columns) paths (for no-write asserts)."""
    import kanbanmate.http.config_api as api_mod
    from kanbanmate.app.config_service import ConfigService

    tp, cp = _make_test_clone(tmp_path)
    svc = ConfigService(transitions_path=tp, columns_path=cp)
    monkeypatch.setattr(api_mod, "_get_service", lambda root=None: svc)
    return TestClient(api_mod.app), tp, cp


def test_post_malformed_json_is_422_not_500(client: TestClient) -> None:
    """B: a non-JSON / malformed body is a clean 422 on every POST — never a 500 traceback."""
    for path in ("/api/config/validate", "/api/config", "/api/config/resolve"):
        r = client.post(path, content="{bad json", headers={"content-type": "application/json"})
        assert r.status_code == 422, f"{path}: got {r.status_code}"


def test_post_non_object_body_is_422(client: TestClient) -> None:
    """C: a JSON array / scalar / null body is 422 on every POST — never a 500 AttributeError."""
    for body in ("[]", '"x"', "null", "42"):
        for path in ("/api/config/validate", "/api/config", "/api/config/resolve"):
            r = client.post(path, content=body, headers={"content-type": "application/json"})
            assert r.status_code == 422, f"{path} body={body!r}: got {r.status_code}"


def test_post_config_empty_body_does_not_wipe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A: POST /api/config with {} is rejected (422) and the config files are UNCHANGED (no wipe)."""
    cl, tp, cp = _client_and_paths(tmp_path, monkeypatch)
    before_t, before_c = tp.read_text(encoding="utf-8"), cp.read_text(encoding="utf-8")
    r = cl.post("/api/config", json={})
    assert r.status_code == 422
    assert tp.read_text(encoding="utf-8") == before_t, "transitions.yml must be unchanged"
    assert cp.read_text(encoding="utf-8") == before_c, "columns.yml must be unchanged"


def test_post_config_missing_definition_or_binding_is_422(client: TestClient) -> None:
    """A: a body omitting 'definition' (or 'binding') is 422 (not a defaulted empty draft)."""
    assert client.post("/api/config", json={"binding": {"project": "x"}}).status_code == 422
    assert client.post("/api/config", json={"definition": {}}).status_code == 422


def test_post_config_empty_board_rejected_by_validator(client: TestClient) -> None:
    """A (V11): a present-but-EMPTY board (0 columns/transitions) is rejected ok:false, not written."""
    body = {
        "definition": {
            "columns": [],
            "transitions": [],
            "defaults": {"concurrency_cap": 3, "move_rate_limit_per_hour": 10},
        },
        "binding": {"project": "x"},
    }
    r = client.post("/api/config", json=body)
    assert r.status_code == 422
    msgs = " ".join(f["message"].lower() for f in r.json().get("findings", []))
    assert "at least one column" in msgs and "at least one transition" in msgs


def test_post_oversize_body_is_413(client: TestClient) -> None:
    """E: a Content-Length over the 1 MiB cap is rejected with 413 before the body is parsed."""
    big = "x" * (1024 * 1024 + 16)
    r = client.post(
        "/api/config/validate", content=big, headers={"content-type": "application/json"}
    )
    assert r.status_code == 413


def test_resolve_without_draft_is_422(client: TestClient) -> None:
    """G: resolve with no draft is a clean 422 (not a misleading matched:false verdict)."""
    r = client.post("/api/config/resolve", json={"from_col": "Review", "to_col": "Merge"})
    assert r.status_code == 422


def test_schema_from_to_col_allow_string_or_list(client: TestClient) -> None:
    """F: GET /api/schema declares from_col/to_col as str | list[str] (matches the model + GET output)."""
    schema = client.get("/api/schema").json()
    titem = schema["properties"]["definition"]["properties"]["transitions"]["items"]["properties"]
    assert "anyOf" in titem["from_col"], "from_col must allow string|array"
    assert "anyOf" in titem["to_col"], "to_col must allow string|array"


# ---------------------------------------------------------------------------
# GET /api/placeholders (bridge / helm PR 2)
# ---------------------------------------------------------------------------


def test_get_placeholders_returns_known_set(client: TestClient) -> None:
    """GET /api/placeholders exposes the canonical placeholder set."""
    resp = client.get("/api/placeholders")
    assert resp.status_code == 200
    names = {p["name"] for p in resp.json()["placeholders"]}
    assert {"code", "codename", "script_output"} <= names
    assert all(p["description"] for p in resp.json()["placeholders"])


# ---------------------------------------------------------------------------
# GET /api/profiles (bridge — read-only profile reference)
# ---------------------------------------------------------------------------


def test_get_profiles_returns_reference(client: TestClient) -> None:
    """GET /api/profiles exposes the code-defined profiles (read-only)."""
    resp = client.get("/api/profiles")
    assert resp.status_code == 200
    profs = {p["name"]: p for p in resp.json()["profiles"]}
    assert {"docs", "prepare", "dev", "check", "merge"} <= set(profs)
    # Each carries the engine-sourced mode + a non-empty allow list + a summary.
    assert profs["docs"]["mode"] == "auto"
    assert profs["docs"]["allow"]
    assert all(p["summary"] for p in profs.values())
    # Merge is the only profile whose deny-list lifts `gh pr merge`.
    assert "Bash(gh pr merge*)" not in profs["merge"]["deny"]
    assert "Bash(gh pr merge*)" in profs["dev"]["deny"]
