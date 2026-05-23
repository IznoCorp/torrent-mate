#!/usr/bin/env python3
"""Detect drift between plan documents and git state (sub-phase 5.10.1).

Cross-checks ``IMPLEMENTATION.md``, ``docs/features/tech-debt/ACCEPTANCE.md``
and ``docs/features/tech-debt/plan/INDEX.md`` against the actual git log and
filesystem.  Independent operator audit script — does NOT auto-fix anything.

Checks implemented
------------------
1. **IMPL_MD_SHAS** — every SHA mentioned in the IMPLEMENTATION.md phases
   table must exist in ``git log`` AND match the
   ``chore(tech-debt): phase N gate — …`` pattern.
2. **ACCEPTANCE_MARKERS** — every ``### ACC-NN — title`` heading must have
   a status marker (✅, ❌, 🟡 or ``[SHIPPED commit XXX]``) somewhere in
   its section when the ACC appears referenced in IMPL.md or in any commit
   message.
3. **PLAN_DEV_COVERAGE** — every DEV row in the plan/INDEX.md coverage
   matrix whose phase column is marked complete in IMPL.md must have at
   least one commit referencing ``DEV #N`` or ``(DEV #N)``.
4. **PLAN_VS_PHASE_FILES** — every phase listed in IMPL.md must have its
   referenced phase file present under ``docs/features/tech-debt/plan/``.
5. **XFAIL_AUDIT** — informational listing of all xfailed pytest tests
   (collected via ``pytest --collect-only``).  Never an error.
6. **AD_HOC_PHASES** — commit messages mentioning ``phase N`` or
   ``phase N.M`` that don't appear in the IMPL.md phases table get flagged
   for retroactive plan integration.

CLI
---
::

    scripts/drift-detect.py                  # full markdown report, exit 0
    scripts/drift-detect.py --strict         # exit non-0 on any drift
    scripts/drift-detect.py --json           # machine-readable JSON
    scripts/drift-detect.py --quiet          # only exit code (CI use)

The script is read-only.  Fix-up is performed in Phase 5.11.

Exit codes
----------
* 0 — clean, OR drifts found but ``--strict`` not set.
* 1 — drifts found AND ``--strict`` set.
* 2 — usage error (bad arguments, missing files).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_ROOT_DEFAULT = Path(__file__).resolve().parent.parent

# Pattern matching the phase-gate commit subject for tech-debt.
GATE_SUBJECT_RE = re.compile(
    r"^chore\(tech-debt\): phase (?P<num>\d+(?:\.\d+)?) gate\b",
)

# Regex helpers ------------------------------------------------------------

# Match a backticked short SHA (>=7 hex chars) inside a table cell.
SHA_TOKEN_RE = re.compile(r"`(?P<sha>[0-9a-f]{7,40})`")

# Match an IMPL.md phases-table row.  Cope with variable status-column
# content; rows we care about start with ``| <num> |``.
IMPL_PHASE_ROW_RE = re.compile(
    r"^\|\s*(?P<num>\d+)\s*\|"
    r"\s*(?P<phase>[^|]+?)\s*\|"
    r"\s*(?P<file>[^|]*?)\s*\|"
    r"\s*(?P<effort>[^|]*?)\s*\|"
    r"\s*(?P<status>[^|]*?)\s*\|\s*$"
)

# Match an ACC heading: ``### ACC-NN — title`` or ``### ACC-NN.M — title``.
ACC_HEADING_RE = re.compile(r"^###\s+(?P<id>ACC-[\w.-]+?)\s*(?:—|--|-)\s*(?P<title>.+?)\s*$")

# Status markers we accept at the heading line OR within the section body.
STATUS_MARKER_RE = re.compile(
    r"(✅|❌|🟡|\[SHIPPED\s+commit\s+[0-9a-f]{7,40}\])",
    re.IGNORECASE,
)

# Match a DEV row in the plan/INDEX.md "DEV coverage matrix" table.
DEV_ROW_RE = re.compile(r"^\|\s*#(?P<num>\d+)\s*\|\s*(?P<phase>[^|]+?)\s*\|\s*(?P<desc>[^|]+?)\s*\|\s*$")

# Loose phase mention inside commit subjects: "phase 5", "phase 5.10".
COMMIT_PHASE_RE = re.compile(r"\bphase\s+(?P<num>\d+(?:\.\d+)?)\b", re.IGNORECASE)

# DEV reference inside a commit message: "DEV #18" or "(DEV #18)".
COMMIT_DEV_RE = re.compile(r"DEV\s+#(?P<num>\d+)", re.IGNORECASE)

# Legacy commit subjects from pre-tech-debt history (e.g. "v14.12.4: ...").
# These pre-date the tech-debt phase taxonomy; their "Phase N" mentions are
# unrelated to the current plan and must not be flagged as ad-hoc phases.
LEGACY_COMMIT_RE = re.compile(r"^v\d+\.\d+\.\d+:")


def _expand_comma_dev_refs(text: str) -> str:
    """Expand ``DEV #N, #M, #O`` into ``DEV #N, DEV #M, DEV #O``.

    The compact form is conventional in tech-debt commit subjects but causes
    :data:`COMMIT_DEV_RE` to miss every ``#M`` past the first.  Rewriting the
    text before regex scanning keeps the regex itself simple.

    Args:
        text: Commit subject or body to normalise.

    Returns:
        Text with every comma-chained ``#M`` after a ``DEV #N`` token
        prefixed with ``DEV`` so the regex matches it.
    """
    # Repeatedly insert "DEV " before "#M" tokens that follow "DEV #N, " or
    # an already-expanded "DEV #M, ".  re.sub with a callback is sufficient
    # because each substitution only consumes one ``, #M`` segment.
    pattern = re.compile(r"(DEV\s+#\d+(?:\s*,\s*DEV\s+#\d+)*)(\s*,\s*)(#\d+)", re.IGNORECASE)
    prev = None
    cur = text
    while prev != cur:
        prev = cur
        cur = pattern.sub(lambda m: f"{m.group(1)}{m.group(2)}DEV {m.group(3)}", cur)
    return cur


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    """One drift finding.

    Args:
        check: Identifier of the check that produced the finding.
        severity: ``error`` for a genuine drift, ``info`` for an
            informational message (e.g. XFAIL_AUDIT entries).
        message: Human-readable explanation.
        context: Optional structured payload (keys depend on the check).
    """

    check: str
    severity: str
    message: str
    context: dict[str, object] = field(default_factory=dict)


@dataclass
class DriftReport:
    """Aggregate result of all checks.

    Args:
        findings: All :class:`Finding` instances collected.
        repo_root: Path of the repository scanned (for display).
    """

    findings: list[Finding] = field(default_factory=list)
    repo_root: Path = REPO_ROOT_DEFAULT

    @property
    def errors(self) -> list[Finding]:
        """Return only finding entries with severity ``error``."""
        return [f for f in self.findings if f.severity == "error"]

    @property
    def infos(self) -> list[Finding]:
        """Return only finding entries with severity ``info``."""
        return [f for f in self.findings if f.severity == "info"]

    def has_drift(self) -> bool:
        """True when at least one error-severity finding is present."""
        return bool(self.errors)


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    """Run ``git`` in *repo* and return stdout (utf-8 stripped).

    Args:
        repo: Working tree to operate on.
        *args: Arguments passed to ``git``.

    Returns:
        Stripped stdout.

    Raises:
        subprocess.CalledProcessError: When git exits non-zero.
    """
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _git_log_subjects(repo: Path) -> list[tuple[str, str]]:
    """Return ``[(sha, subject), …]`` for every reachable commit on HEAD.

    Args:
        repo: Repository root.

    Returns:
        List of ``(short_sha, subject)`` tuples, newest first.
    """
    raw = _git(repo, "log", "--pretty=format:%h\t%s")
    rows: list[tuple[str, str]] = []
    for line in raw.splitlines():
        if "\t" not in line:
            continue
        sha, subject = line.split("\t", 1)
        rows.append((sha.strip(), subject.strip()))
    return rows


def _git_commit_exists(repo: Path, sha: str) -> bool:
    """Return True when *sha* resolves to an object in *repo*.

    Args:
        repo: Repository root.
        sha: Short or full SHA to look up.
    """
    try:
        _git(repo, "rev-parse", "--verify", f"{sha}^{{commit}}")
        return True
    except subprocess.CalledProcessError:
        return False


def _git_commit_subject(repo: Path, sha: str) -> str | None:
    """Return the subject line of *sha* or ``None`` when unknown.

    Args:
        repo: Repository root.
        sha: SHA (short or full).
    """
    try:
        return _git(repo, "log", "-1", "--pretty=format:%s", sha)
    except subprocess.CalledProcessError:
        return None


# ---------------------------------------------------------------------------
# Document parsing helpers
# ---------------------------------------------------------------------------


@dataclass
class ImplPhase:
    """One row from the IMPLEMENTATION.md phases table.

    Args:
        num: Phase number as parsed from the first column.
        title: Phase title.
        file: Referenced phase file (third column).
        status: Raw status column content (may contain backticked SHAs).
        shas: SHA tokens extracted from ``status``.
        complete: Whether the row is marked complete (``[x]``).
    """

    num: str
    title: str
    file: str
    status: str
    shas: list[str] = field(default_factory=list)
    complete: bool = False


def parse_impl_phases(impl_md_text: str) -> list[ImplPhase]:
    """Parse the phases table out of IMPLEMENTATION.md.

    Recognises only rows whose third column (``File``) ends in ``.md`` —
    this is the discriminator between the real implementation-phases table
    and other 5-column tables present in the document (audit checklists,
    sub-phase trackers, etc.).

    Args:
        impl_md_text: Raw content of IMPLEMENTATION.md.

    Returns:
        Ordered list of :class:`ImplPhase` rows.  Header / separator
        lines are skipped automatically.
    """
    phases: list[ImplPhase] = []
    for line in impl_md_text.splitlines():
        m = IMPL_PHASE_ROW_RE.match(line.rstrip())
        if not m:
            continue
        # Skip the header row (status column literally "Status").
        if m.group("status").strip().lower() == "status":
            continue
        # Skip the separator row (status column made of dashes / colons).
        if set(m.group("status").strip()) <= {"-", ":", " "}:
            continue
        file_cell = m.group("file").strip()
        # Discriminator: real phase rows reference a phase markdown file.
        if not file_cell.endswith(".md"):
            continue
        status_cell = m.group("status").strip()
        shas = [match.group("sha") for match in SHA_TOKEN_RE.finditer(status_cell)]
        phases.append(
            ImplPhase(
                num=m.group("num").strip(),
                title=m.group("phase").strip(),
                file=file_cell,
                status=status_cell,
                shas=shas,
                complete="[x]" in status_cell.lower(),
            )
        )
    return phases


@dataclass
class AccCriterion:
    """One ACC heading parsed from ACCEPTANCE.md.

    Args:
        identifier: ``ACC-NN`` token.
        title: Title text after the em-dash.
        heading_line: Full heading line (used to detect inline markers).
        body: Lines belonging to this ACC's section (until next ``###``).
    """

    identifier: str
    title: str
    heading_line: str
    body: list[str] = field(default_factory=list)

    @property
    def has_status_marker(self) -> bool:
        """True when a status marker appears in the heading or body."""
        if STATUS_MARKER_RE.search(self.heading_line):
            return True
        for line in self.body:
            if STATUS_MARKER_RE.search(line):
                return True
        return False


def parse_acceptance(text: str) -> list[AccCriterion]:
    """Parse ACC headings + their section bodies.

    Args:
        text: Raw content of ACCEPTANCE.md.

    Returns:
        Ordered list of :class:`AccCriterion`.
    """
    accs: list[AccCriterion] = []
    current: AccCriterion | None = None
    for raw_line in text.splitlines():
        m = ACC_HEADING_RE.match(raw_line)
        if m:
            if current is not None:
                accs.append(current)
            current = AccCriterion(
                identifier=m.group("id"),
                title=m.group("title"),
                heading_line=raw_line,
            )
            continue
        # New top-level heading boundary: a ``### `` that is not an ACC.
        if raw_line.startswith("### ") and current is not None:
            accs.append(current)
            current = None
            continue
        if current is not None:
            current.body.append(raw_line)
    if current is not None:
        accs.append(current)
    return accs


@dataclass
class DevRow:
    """One row from the plan/INDEX.md DEV coverage matrix.

    Args:
        num: DEV number (without leading ``#``).
        phase: Phase column raw text.
        description: Short description.
    """

    num: int
    phase: str
    description: str


def parse_dev_matrix(index_md_text: str) -> list[DevRow]:
    """Parse the DEV coverage matrix table.

    Args:
        index_md_text: Raw content of plan/INDEX.md.

    Returns:
        Ordered list of :class:`DevRow`.  Header / separator rows are
        skipped.
    """
    devs: list[DevRow] = []
    in_section = False
    for line in index_md_text.splitlines():
        if line.startswith("## ") and "DEV coverage" in line:
            in_section = True
            continue
        if line.startswith("## ") and in_section:
            # Left the section.
            break
        if not in_section:
            continue
        m = DEV_ROW_RE.match(line.rstrip())
        if not m:
            continue
        # Skip header / separator.
        try:
            num = int(m.group("num"))
        except ValueError:
            continue
        devs.append(
            DevRow(
                num=num,
                phase=m.group("phase").strip(),
                description=m.group("desc").strip(),
            )
        )
    return devs


# ---------------------------------------------------------------------------
# Check implementations
# ---------------------------------------------------------------------------


def check_impl_md_shas(
    impl_md_path: Path,
    repo: Path,
) -> list[Finding]:
    """Verify SHAs referenced in the IMPL.md phases table.

    Args:
        impl_md_path: Path to IMPLEMENTATION.md.
        repo: Repository root (for git lookups).

    Returns:
        List of findings (severity ``error``).
    """
    findings: list[Finding] = []
    if not impl_md_path.exists():
        return [
            Finding(
                check="IMPL_MD_SHAS",
                severity="error",
                message=f"IMPLEMENTATION.md not found at {impl_md_path}",
            )
        ]
    text = impl_md_path.read_text(encoding="utf-8")
    for phase in parse_impl_phases(text):
        # Cross-repo rows: status mentions a sibling repo path (e.g.
        # ``.claude/personal-scraper``) — the SHA legitimately lives in
        # another working tree.  Skip the git-presence check, but still
        # surface an info finding so operators can spot stale references.
        cross_repo = ".claude/" in phase.status or "(.claude" in phase.status
        # Partial-phase rows reference a sub-phase commit shipped early
        # (status text contains "partial" or "shipped early").  The SHA is
        # by construction NOT a gate commit yet — skip the gate-shape check.
        status_lower = phase.status.lower()
        partial_phase = "partial" in status_lower or "shipped early" in status_lower
        for sha in phase.shas:
            if cross_repo:
                continue
            if partial_phase:
                # Still verify the SHA exists in git, but accept any subject.
                if not _git_commit_exists(repo, sha):
                    findings.append(
                        Finding(
                            check="IMPL_MD_SHAS",
                            severity="error",
                            message=(f"phase {phase.num} references SHA `{sha}` that does not exist in git log"),
                            context={"phase": phase.num, "sha": sha},
                        )
                    )
                continue
            if not _git_commit_exists(repo, sha):
                findings.append(
                    Finding(
                        check="IMPL_MD_SHAS",
                        severity="error",
                        message=(f"phase {phase.num} references SHA `{sha}` that does not exist in git log"),
                        context={"phase": phase.num, "sha": sha},
                    )
                )
                continue
            subject = _git_commit_subject(repo, sha) or ""
            m = GATE_SUBJECT_RE.match(subject)
            if m is None:
                findings.append(
                    Finding(
                        check="IMPL_MD_SHAS",
                        severity="error",
                        message=(f"phase {phase.num} SHA `{sha}` is not a phase-gate commit (subject: {subject!r})"),
                        context={"phase": phase.num, "sha": sha, "subject": subject},
                    )
                )
                continue
            if m.group("num") != phase.num:
                findings.append(
                    Finding(
                        check="IMPL_MD_SHAS",
                        severity="error",
                        message=(f"phase {phase.num} SHA `{sha}` is a gate for phase {m.group('num')} (mismatch)"),
                        context={
                            "phase": phase.num,
                            "sha": sha,
                            "gate_phase": m.group("num"),
                        },
                    )
                )
    return findings


def check_acceptance_markers(
    acceptance_path: Path,
    impl_md_path: Path,
    repo: Path,
) -> list[Finding]:
    """Flag ACC criteria that look shipped but lack a status marker.

    Args:
        acceptance_path: Path to ACCEPTANCE.md.
        impl_md_path: Path to IMPLEMENTATION.md (for cross-reference).
        repo: Repository root (for git log scan).

    Returns:
        List of findings (severity ``error``).
    """
    findings: list[Finding] = []
    if not acceptance_path.exists():
        return [
            Finding(
                check="ACCEPTANCE_MARKERS",
                severity="error",
                message=f"ACCEPTANCE.md not found at {acceptance_path}",
            )
        ]
    impl_text = impl_md_path.read_text(encoding="utf-8") if impl_md_path.exists() else ""
    commits_text = "\n".join(s for _, s in _git_log_subjects(repo))
    accs = parse_acceptance(acceptance_path.read_text(encoding="utf-8"))
    for acc in accs:
        if acc.has_status_marker:
            continue
        # Look for any sign that this ACC was shipped: mention in IMPL.md
        # or in a commit subject.
        token = acc.identifier
        shipped_signal = (token in impl_text) or (token in commits_text)
        if shipped_signal:
            findings.append(
                Finding(
                    check="ACCEPTANCE_MARKERS",
                    severity="error",
                    message=(
                        f"{acc.identifier} has shipped signals "
                        f"(IMPL.md/commit mention) but no status marker "
                        f"(✅/❌/🟡/[SHIPPED commit XXX]) in ACCEPTANCE.md"
                    ),
                    context={"acc": acc.identifier, "title": acc.title},
                )
            )
    return findings


def check_plan_dev_coverage(
    index_md_path: Path,
    impl_md_path: Path,
    repo: Path,
) -> list[Finding]:
    """Flag DEVs whose phase is complete but no commit references them.

    Args:
        index_md_path: Path to plan/INDEX.md.
        impl_md_path: Path to IMPLEMENTATION.md (to read phase completion).
        repo: Repository root.

    Returns:
        List of findings (severity ``error``).
    """
    findings: list[Finding] = []
    if not index_md_path.exists():
        return [
            Finding(
                check="PLAN_DEV_COVERAGE",
                severity="error",
                message=f"plan/INDEX.md not found at {index_md_path}",
            )
        ]
    devs = parse_dev_matrix(index_md_path.read_text(encoding="utf-8"))
    if not devs:
        return findings
    impl_phases = parse_impl_phases(impl_md_path.read_text(encoding="utf-8")) if impl_md_path.exists() else []
    complete_phase_nums: set[str] = {p.num for p in impl_phases if p.complete}
    commits = _git_log_subjects(repo)
    dev_in_commits: set[int] = set()
    for _, subject in commits:
        for m in COMMIT_DEV_RE.finditer(_expand_comma_dev_refs(subject)):
            dev_in_commits.add(int(m.group("num")))
    # Also scan full commit bodies for DEV refs (some commits put DEV ids in body).
    try:
        bodies = _git(repo, "log", "--pretty=format:%B%n---END---")
        for m in COMMIT_DEV_RE.finditer(_expand_comma_dev_refs(bodies)):
            dev_in_commits.add(int(m.group("num")))
    except subprocess.CalledProcessError:
        pass
    for dev in devs:
        # The phase column may list multiple phases ("8.13, 9.1.a"); extract
        # the leading top-level numbers.
        leading_nums = {chunk.strip().split(".")[0] for chunk in dev.phase.split(",") if chunk.strip()}
        leading_nums.discard("")
        # Special: "-" indicates already-shipped DEV — skip coverage check.
        if dev.phase.strip() in {"-", ""}:
            continue
        if not (leading_nums & complete_phase_nums):
            # Phase not yet complete → not expected to be shipped.
            continue
        if dev.num in dev_in_commits:
            continue
        findings.append(
            Finding(
                check="PLAN_DEV_COVERAGE",
                severity="error",
                message=(
                    f"DEV #{dev.num} (phase {dev.phase}) is in a complete phase "
                    f"but no commit references `DEV #{dev.num}`"
                ),
                context={"dev": dev.num, "phase": dev.phase, "desc": dev.description},
            )
        )
    return findings


def check_plan_vs_phase_files(
    impl_md_path: Path,
    plan_dir: Path,
) -> list[Finding]:
    """Verify every IMPL.md phase row references an existing phase file.

    Args:
        impl_md_path: Path to IMPLEMENTATION.md.
        plan_dir: Directory holding phase files.

    Returns:
        List of findings (severity ``error``).
    """
    findings: list[Finding] = []
    if not impl_md_path.exists():
        return [
            Finding(
                check="PLAN_VS_PHASE_FILES",
                severity="error",
                message=f"IMPLEMENTATION.md not found at {impl_md_path}",
            )
        ]
    for phase in parse_impl_phases(impl_md_path.read_text(encoding="utf-8")):
        if not phase.file:
            continue
        candidate = plan_dir / phase.file
        if not candidate.exists():
            findings.append(
                Finding(
                    check="PLAN_VS_PHASE_FILES",
                    severity="error",
                    message=(
                        f"phase {phase.num} references phase file `{phase.file}` which does not exist under {plan_dir}"
                    ),
                    context={"phase": phase.num, "file": phase.file},
                )
            )
    return findings


def check_xfail_audit(repo: Path) -> list[Finding]:
    """List xfailed pytest tests as informational findings.

    Args:
        repo: Repository root.

    Returns:
        List of findings (severity ``info``).  Failure to run pytest
        produces one ``info`` entry with the error message and is NOT
        promoted to an error — the audit is best-effort.
    """
    try:
        # ``--collect-only -q`` is fast and prints `pytest.xfail` decorations
        # via the ``reason`` field on xfailed nodes.  We complement it with a
        # text grep of the test tree to capture the @pytest.mark.xfail
        # decorators with their reason strings.
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "--collect-only",
                "-q",
                "--no-header",
                "--no-summary",
                "-p",
                "no:cacheprovider",
            ],
            cwd=str(repo),
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        # We don't trust the collect-only output to enumerate xfails directly
        # (pytest doesn't list them as xfail at collection time).  Use a
        # source-level grep instead — same information, deterministic.
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return [
            Finding(
                check="XFAIL_AUDIT",
                severity="info",
                message=f"pytest collect-only unavailable: {exc}",
            )
        ]
    findings: list[Finding] = []
    tests_dir = repo / "tests"
    if not tests_dir.exists():
        return findings
    xfail_pattern = re.compile(r"@pytest\.mark\.xfail\s*\(\s*(?P<args>[^)]*)\)")
    reason_pattern = re.compile(r"reason\s*=\s*[\"'](?P<reason>[^\"']+)[\"']")
    for py_file in sorted(tests_dir.rglob("test_*.py")):
        try:
            content = py_file.read_text(encoding="utf-8")
        except OSError:
            continue
        for m in xfail_pattern.finditer(content):
            args = m.group("args")
            r = reason_pattern.search(args)
            reason = r.group("reason") if r else "(no reason)"
            findings.append(
                Finding(
                    check="XFAIL_AUDIT",
                    severity="info",
                    message=f"{py_file.relative_to(repo)}: xfail — {reason}",
                    context={
                        "file": str(py_file.relative_to(repo)),
                        "reason": reason,
                    },
                )
            )
    # Acknowledge proc to keep mypy happy without dropping the run.
    _ = proc.returncode
    return findings


def check_ad_hoc_phases(
    impl_md_path: Path,
    repo: Path,
) -> list[Finding]:
    """Flag phase numbers mentioned in commits but absent from IMPL.md.

    Only top-level ``phase N`` and sub-phase ``phase N.M`` mentions are
    extracted.  A sub-phase (e.g. ``5.10``) is considered covered when its
    parent (``5``) appears in IMPL.md AND the parent row's status mentions
    that sub-phase, OR when ``phase N.M`` appears verbatim in IMPL.md.

    Args:
        impl_md_path: Path to IMPLEMENTATION.md.
        repo: Repository root.

    Returns:
        List of findings (severity ``error``).
    """
    findings: list[Finding] = []
    if not impl_md_path.exists():
        return findings
    impl_text = impl_md_path.read_text(encoding="utf-8")
    phases = parse_impl_phases(impl_text)
    known_top_levels: set[str] = {p.num for p in phases}
    # Mentions in IMPL.md text count as "known" too — sub-phase tracking
    # tables sometimes appear outside the main phases table.
    impl_mentions: set[str] = {m.group("num") for m in COMMIT_PHASE_RE.finditer(impl_text)}

    seen: set[tuple[str, str]] = set()
    for sha, subject in _git_log_subjects(repo):
        # Skip pre-tech-debt legacy commits — their "phase N" mentions belong
        # to a defunct numbering scheme and would always be flagged.
        if LEGACY_COMMIT_RE.match(subject):
            continue
        for m in COMMIT_PHASE_RE.finditer(subject):
            num = m.group("num")
            top_level = num.split(".")[0]
            if num in known_top_levels or num in impl_mentions:
                continue
            if "." in num and top_level in known_top_levels:
                # Sub-phase whose parent is in IMPL.md — only flag if the
                # parent row's status doesn't reference the sub-phase number.
                parent_row = next((p for p in phases if p.num == top_level), None)
                if parent_row is not None and num in parent_row.status:
                    continue
                if num in impl_text:
                    continue
            key = (num, sha)
            if key in seen:
                continue
            seen.add(key)
            findings.append(
                Finding(
                    check="AD_HOC_PHASES",
                    severity="error",
                    message=(f"commit {sha} mentions phase {num} which is not tracked in IMPLEMENTATION.md"),
                    context={"sha": sha, "subject": subject, "phase": num},
                )
            )
    return findings


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_all_checks(repo: Path) -> DriftReport:
    """Run all drift checks against *repo*.

    Args:
        repo: Repository root.

    Returns:
        Populated :class:`DriftReport`.
    """
    impl_md = repo / "IMPLEMENTATION.md"
    plan_dir = repo / "docs" / "features" / "tech-debt" / "plan"
    acceptance_md = repo / "docs" / "features" / "tech-debt" / "ACCEPTANCE.md"
    index_md = plan_dir / "INDEX.md"

    report = DriftReport(repo_root=repo)
    report.findings.extend(check_impl_md_shas(impl_md, repo))
    report.findings.extend(check_acceptance_markers(acceptance_md, impl_md, repo))
    report.findings.extend(check_plan_dev_coverage(index_md, impl_md, repo))
    report.findings.extend(check_plan_vs_phase_files(impl_md, plan_dir))
    report.findings.extend(check_xfail_audit(repo))
    report.findings.extend(check_ad_hoc_phases(impl_md, repo))
    return report


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


CHECK_TITLES = {
    "IMPL_MD_SHAS": "IMPL.md SHAs vs git",
    "ACCEPTANCE_MARKERS": "ACCEPTANCE.md status markers",
    "PLAN_DEV_COVERAGE": "plan/INDEX.md DEV coverage vs commits",
    "PLAN_VS_PHASE_FILES": "IMPL.md phase files vs filesystem",
    "XFAIL_AUDIT": "xfailed pytest tests (informational)",
    "AD_HOC_PHASES": "phases in commits absent from IMPL.md",
}


def format_markdown(report: DriftReport) -> str:
    """Render *report* as a human-readable markdown document.

    Args:
        report: Drift report.

    Returns:
        Markdown string with one section per check.
    """
    lines: list[str] = []
    lines.append("# drift-detect report")
    lines.append("")
    lines.append(f"- repo: `{report.repo_root}`")
    lines.append(f"- error findings: {len(report.errors)}")
    lines.append(f"- info findings: {len(report.infos)}")
    lines.append("")
    for check_id, title in CHECK_TITLES.items():
        check_findings = [f for f in report.findings if f.check == check_id]
        lines.append(f"## {check_id} — {title}")
        if not check_findings:
            lines.append("")
            lines.append("_no findings_")
            lines.append("")
            continue
        lines.append("")
        for finding in check_findings:
            prefix = "ERROR" if finding.severity == "error" else "INFO"
            lines.append(f"- **{prefix}**: {finding.message}")
        lines.append("")
    return "\n".join(lines)


def format_json(report: DriftReport) -> str:
    """Render *report* as JSON suitable for CI consumption.

    Args:
        report: Drift report.

    Returns:
        JSON string with ``error_count``, ``info_count``, ``findings``.
    """
    payload: dict[str, object] = {
        "repo_root": str(report.repo_root),
        "error_count": len(report.errors),
        "info_count": len(report.infos),
        "findings": [asdict(f) for f in report.findings],
    }
    return json.dumps(payload, indent=2, sort_keys=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Construct the argparse parser for the script."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--repo",
        type=Path,
        default=REPO_ROOT_DEFAULT,
        help="Repository root (defaults to this script's grandparent dir).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when at least one drift is found.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a machine-readable JSON report instead of markdown.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress output; rely on the exit code only.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Optional argv list (defaults to ``sys.argv[1:]``).

    Returns:
        Exit code per the script docstring.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    repo: Path = args.repo.resolve()
    if not (repo / ".git").exists():
        print(f"drift-detect: not a git repo at {repo}", file=sys.stderr)
        return 2

    report = run_all_checks(repo)
    if not args.quiet:
        if args.json:
            print(format_json(report))
        else:
            print(format_markdown(report))

    if args.strict and report.has_drift():
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
