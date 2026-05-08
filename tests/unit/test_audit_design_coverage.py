"""Unit tests for ``scripts/audit_design_coverage.py``.

Cover the GitHub anchor algorithm (DESIGN §3.2.1), Markdown heading parsing
with deduplication, and the two-direction audit (orphan sections + stale
references) including ``skip_audit`` lifecycle.
"""

from __future__ import annotations

import json
import unicodedata
from datetime import date
from pathlib import Path

import pytest
from audit_design_coverage import (
    Finding,
    audit,
    github_anchor,
    main,
    parse_anchors,
    strip_fenced_code,
)


class TestGithubAnchor:
    """Reference cases pinned by DESIGN §3.2.1."""

    @pytest.mark.parametrize(
        ("heading", "expected"),
        [
            ("Circuit Breaker — Open After 3 Failures", "circuit-breaker--open-after-3-failures"),
            ("Use `MediaType` enum", "use-mediatype-enum"),
            ("🔴 Critical Issues", "critical-issues"),
            ("Café (déjà vu)", "café-déjà-vu"),
            ("中文 标题", "中文-标题"),
            ("Function (deprecated)", "function-deprecated"),
            ("snake_case_name", "snake_case_name"),
        ],
    )
    def test_reference_cases(self, heading: str, expected: str) -> None:
        """Each documented reference heading produces the expected anchor."""
        assert github_anchor(heading) == expected

    def test_whitespace_only_returns_none(self) -> None:
        """A heading that reduces to whitespace alone yields no anchor."""
        assert github_anchor("   ") is None

    def test_punctuation_only_returns_none(self) -> None:
        """A heading made of stripped characters alone yields no anchor."""
        assert github_anchor("!!!???") is None

    def test_nfc_normalization(self) -> None:
        """NFD input produces the same anchor as NFC input (macOS Finder copies)."""
        nfc = "Café"
        nfd = unicodedata.normalize("NFD", nfc)
        assert nfc != nfd  # sanity — NFD truly differs in code points.
        assert github_anchor(nfd) == github_anchor(nfc)


class TestParseAnchors:
    """Markdown heading parsing with dedup."""

    def test_duplicate_headings_get_suffixes(self) -> None:
        """Two headings with the same anchor get ``-1`` on the second; ``-2`` on the third."""
        md = "## Title\n\n## Title\n\n## Title\n"
        assert parse_anchors(md) == ["title", "title-1", "title-2"]

    def test_empty_headings_skipped(self) -> None:
        """Headings reducing to nothing do not produce anchors."""
        md = "## \n## ###\n## Real\n"
        assert parse_anchors(md) == ["real"]

    def test_fenced_code_blocks_ignored(self) -> None:
        """``##`` lines inside fenced code blocks are not interpreted as headings."""
        md = "## Real Heading\n\n```\n## Not a heading\n```\n\n## Another\n"
        assert parse_anchors(md) == ["real-heading", "another"]

    def test_mixed_heading_levels(self) -> None:
        """Different heading levels share the dedup namespace, matching GitHub."""
        md = "# Title\n\n## Title\n\n### Title\n"
        assert parse_anchors(md) == ["title", "title-1", "title-2"]


class TestStripFencedCode:
    """Code-fence stripping helper."""

    def test_strips_fenced_block(self) -> None:
        """Lines between ``` markers are removed."""
        text = "alpha\n```\ninside\n```\nbravo\n"
        assert "inside" not in strip_fenced_code(text)
        assert "alpha" in strip_fenced_code(text)
        assert "bravo" in strip_fenced_code(text)

    def test_handles_indented_fence(self) -> None:
        """Fences with leading whitespace are still recognized."""
        text = "alpha\n  ```\nhidden\n  ```\nbravo\n"
        assert "hidden" not in strip_fenced_code(text)


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    """Build a minimal repo skeleton with map dir."""
    (tmp_path / "tests" / "feature_map").mkdir(parents=True)
    return tmp_path


def _write_design(repo: Path, rel: str, content: str) -> Path:
    """Write a design doc under ``repo/<rel>`` and return its path."""
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _write_map(repo: Path, codename: str, payload: dict) -> Path:
    """Write a map file under tests/feature_map/<codename>.json."""
    path = repo / "tests" / "feature_map" / f"{codename}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


class TestAuditOrphanSections:
    """Orphan-section detection."""

    def test_orphan_section_warning_default(self, fake_repo: Path) -> None:
        """Anchor in design doc with no tests → warning when not strict."""
        _write_design(
            fake_repo,
            "docs/features/sample/DESIGN.md",
            "## Goal\n\n## Implementation\n",
        )
        _write_map(
            fake_repo,
            "sample",
            {
                "feature": "sample",
                "design": "docs/features/sample/DESIGN.md",
                "sections": {"goal": {"tests": ["tests/integration/test_sample.py::test_goal"]}},
                "skip_audit": [],
            },
        )
        findings = audit(
            fake_repo / "tests" / "feature_map",
            fake_repo,
            strict=False,
            strict_skip=False,
            today=date(2026, 5, 8),
        )
        orphans = [f for f in findings if f.kind == "orphan-section"]
        assert len(orphans) == 1
        assert orphans[0].severity == "warning"
        assert "implementation" in orphans[0].message

    def test_orphan_section_error_strict(self, fake_repo: Path) -> None:
        """Same scenario under --strict promotes orphan to error."""
        _write_design(fake_repo, "docs/features/sample/DESIGN.md", "## Only Section\n")
        _write_map(
            fake_repo,
            "sample",
            {
                "feature": "sample",
                "design": "docs/features/sample/DESIGN.md",
                "sections": {},
                "skip_audit": [],
            },
        )
        findings = audit(
            fake_repo / "tests" / "feature_map",
            fake_repo,
            strict=True,
            strict_skip=False,
            today=date(2026, 5, 8),
        )
        assert any(f.severity == "error" and f.kind == "orphan-section" for f in findings)

    def test_skip_audit_suppresses_orphan(self, fake_repo: Path) -> None:
        """Anchors listed in skip_audit are not reported as orphans."""
        _write_design(fake_repo, "docs/features/sample/DESIGN.md", "## Purpose\n")
        _write_map(
            fake_repo,
            "sample",
            {
                "feature": "sample",
                "design": "docs/features/sample/DESIGN.md",
                "sections": {},
                "skip_audit": [
                    {"anchor": "purpose", "category": "documentation_only", "reason": "intent", "expires": "2099-01-01"}
                ],
            },
        )
        findings = audit(
            fake_repo / "tests" / "feature_map",
            fake_repo,
            strict=True,
            strict_skip=False,
            today=date(2026, 5, 8),
        )
        assert all(f.kind != "orphan-section" for f in findings)


class TestAuditStaleReferences:
    """Stale-reference detection (always error)."""

    def test_stale_reference_is_error(self, fake_repo: Path) -> None:
        """Anchor in map but not in design doc → error regardless of strict."""
        _write_design(fake_repo, "docs/features/sample/DESIGN.md", "## Live Section\n")
        _write_map(
            fake_repo,
            "sample",
            {
                "feature": "sample",
                "design": "docs/features/sample/DESIGN.md",
                "sections": {"removed-section": {"tests": ["tests/integration/test_x.py::test_y"]}},
                "skip_audit": [],
            },
        )
        findings = audit(
            fake_repo / "tests" / "feature_map",
            fake_repo,
            strict=False,
            strict_skip=False,
            today=date(2026, 5, 8),
        )
        stales = [f for f in findings if f.kind == "stale-reference"]
        assert len(stales) == 1
        assert stales[0].severity == "error"
        assert "removed-section" in stales[0].message

    def test_missing_design_file_is_error(self, fake_repo: Path) -> None:
        """Map referencing a non-existent design doc → error."""
        _write_map(
            fake_repo,
            "missing",
            {
                "feature": "missing",
                "design": "docs/features/ghost/DESIGN.md",
                "sections": {},
                "skip_audit": [],
            },
        )
        findings = audit(
            fake_repo / "tests" / "feature_map",
            fake_repo,
            strict=False,
            strict_skip=False,
            today=date(2026, 5, 8),
        )
        assert any(f.kind == "missing-design-file" and f.severity == "error" for f in findings)


class TestSkipAuditExpiry:
    """skip_audit expires lifecycle."""

    def test_expired_skip_warning_default(self, fake_repo: Path) -> None:
        """Past expires → warning by default."""
        _write_design(fake_repo, "docs/features/sample/DESIGN.md", "## Purpose\n")
        _write_map(
            fake_repo,
            "sample",
            {
                "feature": "sample",
                "design": "docs/features/sample/DESIGN.md",
                "sections": {},
                "skip_audit": [
                    {"anchor": "purpose", "category": "documentation_only", "reason": "intent", "expires": "2024-01-01"}
                ],
            },
        )
        findings = audit(
            fake_repo / "tests" / "feature_map",
            fake_repo,
            strict=False,
            strict_skip=False,
            today=date(2026, 5, 8),
        )
        expired = [f for f in findings if f.kind == "expired-skip"]
        assert len(expired) == 1
        assert expired[0].severity == "warning"

    def test_expired_skip_error_with_strict_skip(self, fake_repo: Path) -> None:
        """Past expires + --strict-skip → error."""
        _write_design(fake_repo, "docs/features/sample/DESIGN.md", "## Purpose\n")
        _write_map(
            fake_repo,
            "sample",
            {
                "feature": "sample",
                "design": "docs/features/sample/DESIGN.md",
                "sections": {},
                "skip_audit": [
                    {"anchor": "purpose", "category": "documentation_only", "reason": "intent", "expires": "2024-01-01"}
                ],
            },
        )
        findings = audit(
            fake_repo / "tests" / "feature_map",
            fake_repo,
            strict=False,
            strict_skip=True,
            today=date(2026, 5, 8),
        )
        assert any(f.kind == "expired-skip" and f.severity == "error" for f in findings)

    def test_invalid_expires_is_error(self, fake_repo: Path) -> None:
        """Non-ISO expires date → error."""
        _write_design(fake_repo, "docs/features/sample/DESIGN.md", "## Purpose\n")
        _write_map(
            fake_repo,
            "sample",
            {
                "feature": "sample",
                "design": "docs/features/sample/DESIGN.md",
                "sections": {},
                "skip_audit": [
                    {"anchor": "purpose", "category": "documentation_only", "reason": "intent", "expires": "next year"}
                ],
            },
        )
        findings = audit(
            fake_repo / "tests" / "feature_map",
            fake_repo,
            strict=False,
            strict_skip=False,
            today=date(2026, 5, 8),
        )
        assert any(f.kind == "invalid-expires" for f in findings)


class TestMainExitCode:
    """``main()`` exit-code contract."""

    def test_main_returns_0_when_clean(self, fake_repo: Path) -> None:
        """No findings → exit 0."""
        rc = main(["--repo-root", str(fake_repo), "--today", "2026-05-08"])
        assert rc == 0

    def test_main_returns_1_on_error(self, fake_repo: Path) -> None:
        """Stale reference (always error) → exit 1."""
        _write_design(fake_repo, "docs/features/sample/DESIGN.md", "## Real\n")
        _write_map(
            fake_repo,
            "sample",
            {
                "feature": "sample",
                "design": "docs/features/sample/DESIGN.md",
                "sections": {"phantom": {"tests": ["tests/integration/test.py::test_x"]}},
                "skip_audit": [],
            },
        )
        rc = main(["--repo-root", str(fake_repo), "--today", "2026-05-08"])
        assert rc == 1

    def test_main_returns_1_on_strict_orphan(self, fake_repo: Path) -> None:
        """Orphan + --strict → exit 1."""
        _write_design(fake_repo, "docs/features/sample/DESIGN.md", "## Untested\n")
        _write_map(
            fake_repo,
            "sample",
            {
                "feature": "sample",
                "design": "docs/features/sample/DESIGN.md",
                "sections": {},
                "skip_audit": [],
            },
        )
        rc = main(["--strict", "--repo-root", str(fake_repo), "--today", "2026-05-08"])
        assert rc == 1


class TestFindingDataclass:
    """Sanity check on the public ``Finding`` dataclass."""

    def test_finding_is_immutable(self) -> None:
        """Findings are frozen so tests can compare with equality."""
        f = Finding(severity="error", kind="stale-reference", message="x")
        with pytest.raises(Exception):  # dataclass FrozenInstanceError
            f.severity = "warning"  # type: ignore[misc]
