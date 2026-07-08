"""Unit tests for config editor API Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from personalscraper.web.models.config import (
    ConfigSchemaResponse,
    ConfigStatusResponse,
    FileContent,
    FileInfo,
    FilesResponse,
    PutFileRequest,
    PutFileResponse,
    RestartResponse,
    SecretEntry,
    SecretsPutRequest,
    SecretsResponse,
    ValidateRequest,
    ValidateResponse,
)


class TestFileInfo:
    """Tests for ``FileInfo`` — single config file metadata."""

    def test_roundtrip(self) -> None:
        """Model validates and dumps correctly with all fields populated."""
        obj = FileInfo(
            name="master.json5",
            owned_keys=["paths", "web"],
            sha256="a1b2c3d4",
            mtime=1719000000.0,
            size=2048,
            shadowed_keys=["paths"],
        )
        d = obj.model_dump()
        assert d["name"] == "master.json5"
        assert d["owned_keys"] == ["paths", "web"]
        assert d["sha256"] == "a1b2c3d4"
        assert d["mtime"] == 1719000000.0
        assert d["size"] == 2048
        assert d["shadowed_keys"] == ["paths"]
        # Full roundtrip.
        assert FileInfo.model_validate(d) == obj

    def test_extra_forbidden(self) -> None:
        """Extra keys are rejected because ``model_config`` sets ``extra="forbid"``."""
        with pytest.raises(ValidationError):
            FileInfo.model_validate(
                {
                    "name": "master.json5",
                    "owned_keys": [],
                    "sha256": "a",
                    "mtime": 0.0,
                    "size": 0,
                    "shadowed_keys": [],
                    "unknown_field": 42,
                }
            )


class TestFilesResponse:
    """Tests for ``FilesResponse`` — file listing envelope."""

    def test_roundtrip(self) -> None:
        """Wraps a list of ``FileInfo`` and round-trips correctly."""
        fi = FileInfo(
            name="master.json5",
            owned_keys=["paths"],
            sha256="abc",
            mtime=1.0,
            size=10,
            shadowed_keys=[],
        )
        resp = FilesResponse(files=[fi])
        d = resp.model_dump()
        assert len(d["files"]) == 1
        assert d["files"][0]["name"] == "master.json5"
        assert FilesResponse.model_validate(d) == resp


class TestFileContent:
    """Tests for ``FileContent`` — single file parsed values."""

    def test_roundtrip(self) -> None:
        """Model validates and dumps correctly with nested values."""
        obj = FileContent(
            name="disks.json5",
            values={"disk_1": {"path": "/Volumes/Disk1"}},
            sha256="def456",
            shadowed_keys=[],
        )
        d = obj.model_dump()
        assert d["values"]["disk_1"]["path"] == "/Volumes/Disk1"
        assert FileContent.model_validate(d) == obj


class TestConfigSchemaResponse:
    """Tests for ``ConfigSchemaResponse`` — JSON Schema endpoint."""

    def test_field_is_json_schema_not_schema(self) -> None:
        """The JSON Schema field is named ``json_schema`` to avoid shadowing.

        ``BaseModel.model_json_schema`` is a classmethod on every Pydantic
        model, so naming a field ``schema`` would trigger a v2 shadow warning.
        """
        obj = ConfigSchemaResponse(
            json_schema={"type": "object", "properties": {}},
            ownership={"paths": "master.json5"},
            restart_impact={"paths": False},
        )
        assert obj.json_schema == {"type": "object", "properties": {}}
        # The field is named ``json_schema``, not ``schema`` — verify
        # it is present in model_fields (Pydantic v2) while ``schema``
        # is absent.
        assert "json_schema" in ConfigSchemaResponse.model_fields
        assert "schema" not in ConfigSchemaResponse.model_fields

    def test_roundtrip(self) -> None:
        """Full round-trip through ``model_validate`` and ``model_dump``."""
        obj = ConfigSchemaResponse(
            json_schema={"type": "object"},
            ownership={"paths": "master.json5", "web": "web.json5"},
            restart_impact={"paths": False, "web": True},
        )
        d = obj.model_dump()
        assert d["json_schema"] == {"type": "object"}
        assert d["ownership"]["paths"] == "master.json5"
        assert d["restart_impact"]["web"] is True
        assert ConfigSchemaResponse.model_validate(d) == obj


class TestPutFileRequest:
    """Tests for ``PutFileRequest`` — optimistic-concurrency write body."""

    def test_roundtrip(self) -> None:
        """Model validates and dumps correctly."""
        obj = PutFileRequest(
            values={"paths": {"staging_dir": "/tmp/staging"}},
            base_sha256="abc123",
        )
        d = obj.model_dump()
        assert d["base_sha256"] == "abc123"
        assert PutFileRequest.model_validate(d) == obj

    def test_extra_forbidden(self) -> None:
        """Extra keys are rejected."""
        with pytest.raises(ValidationError):
            PutFileRequest.model_validate({"values": {}, "base_sha256": "abc", "injected_field": "bad"})


class TestPutFileResponse:
    """Tests for ``PutFileResponse`` — write result body."""

    def test_roundtrip(self) -> None:
        """Model validates and dumps correctly."""
        obj = PutFileResponse(
            warnings=["key 'paths' was changed"],
            restart_required=True,
        )
        d = obj.model_dump()
        assert d["warnings"] == ["key 'paths' was changed"]
        assert d["restart_required"] is True
        assert PutFileResponse.model_validate(d) == obj

    def test_no_warnings_no_restart(self) -> None:
        """Clean write with no warnings and no restart required."""
        obj = PutFileResponse(warnings=[], restart_required=False)
        d = obj.model_dump()
        assert d == {"warnings": [], "restart_required": False}


class TestValidateRequest:
    """Tests for ``ValidateRequest`` — dry-run validation body."""

    def test_roundtrip(self) -> None:
        """Model validates and dumps correctly."""
        obj = ValidateRequest(
            file_name="master.json5",
            values={"paths": {"staging_dir": "/tmp"}},
        )
        d = obj.model_dump()
        assert d["file_name"] == "master.json5"
        assert ValidateRequest.model_validate(d) == obj


class TestValidateResponse:
    """Tests for ``ValidateResponse`` — validation result body."""

    def test_roundtrip(self) -> None:
        """Model validates and dumps correctly."""
        obj = ValidateResponse(warnings=["paths.staging_dir is not absolute"])
        d = obj.model_dump()
        assert d["warnings"] == ["paths.staging_dir is not absolute"]
        assert ValidateResponse.model_validate(d) == obj

    def test_empty_warnings(self) -> None:
        """Validation with zero warnings."""
        obj = ValidateResponse(warnings=[])
        assert obj.model_dump() == {"warnings": []}


class TestConfigStatusResponse:
    """Tests for ``ConfigStatusResponse`` — deployment status."""

    def test_roundtrip(self) -> None:
        """Model validates and dumps correctly."""
        obj = ConfigStatusResponse(
            role="prod",
            read_only=False,
            restart_required=True,
            restart_configured=True,
            stale_files=["master.json5"],
        )
        d = obj.model_dump()
        assert d["role"] == "prod"
        assert d["read_only"] is False
        assert d["restart_required"] is True
        assert d["restart_configured"] is True
        assert d["stale_files"] == ["master.json5"]
        assert ConfigStatusResponse.model_validate(d) == obj


class TestSecretEntry:
    """Tests for ``SecretEntry`` — catalogued secret metadata."""

    def test_roundtrip(self) -> None:
        """Model validates and dumps correctly."""
        obj = SecretEntry(
            key="TMDB_API_KEY",
            description="API key for TMDB v3",
            is_set=True,
        )
        d = obj.model_dump()
        assert d["key"] == "TMDB_API_KEY"
        assert d["description"] == "API key for TMDB v3"
        assert d["is_set"] is True
        assert SecretEntry.model_validate(d) == obj


class TestSecretsResponse:
    """Tests for ``SecretsResponse`` — secret listing envelope."""

    def test_roundtrip(self) -> None:
        """Wraps a list of ``SecretEntry`` and round-trips correctly."""
        entry = SecretEntry(key="KEY", description="desc", is_set=False)
        resp = SecretsResponse(secrets=[entry])
        d = resp.model_dump()
        assert len(d["secrets"]) == 1
        assert d["secrets"][0]["key"] == "KEY"
        assert SecretsResponse.model_validate(d) == resp


class TestSecretsPutRequest:
    """Tests for ``SecretsPutRequest`` — ``RootModel[dict[str, str]]``."""

    def test_accepts_string_dict(self) -> None:
        """Accepts a ``{str: str}`` mapping via init or ``model_validate``."""
        req = SecretsPutRequest({"TMDB_API_KEY": "abc123"})
        assert req.root == {"TMDB_API_KEY": "abc123"}
        assert req.model_dump() == {"TMDB_API_KEY": "abc123"}

    def test_roundtrip_via_validate(self) -> None:
        """``model_validate`` then ``model_dump`` preserves the dict."""
        data = {"KEY_A": "val_a", "KEY_B": "val_b"}
        req = SecretsPutRequest.model_validate(data)
        assert req.model_dump() == data

    def test_rejects_non_string_values(self) -> None:
        """Dict values must be strings — integers are rejected."""
        with pytest.raises(ValidationError):
            SecretsPutRequest.model_validate({"KEY": 123})

    def test_rejects_non_dict(self) -> None:
        """Root must be a dict — a list is rejected."""
        with pytest.raises(ValidationError):
            SecretsPutRequest.model_validate(["not", "a", "dict"])


class TestRestartResponse:
    """Tests for ``RestartResponse`` — restart acknowledgement."""

    def test_roundtrip(self) -> None:
        """Model validates and dumps correctly."""
        obj = RestartResponse(status="scheduled")
        d = obj.model_dump()
        assert d == {"status": "scheduled"}
        assert RestartResponse.model_validate(d) == obj
