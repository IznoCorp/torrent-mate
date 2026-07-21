r"""AST guard: local artwork-presence glob/regex logic must live only in core/artwork_naming.py.

Enforces the architecture invariant from DESIGN §5 T4 / §9 (conformity fix F5):
``personalscraper.core.artwork_naming`` is the ONE owner of artwork-presence
detection. Every other layer must consult ``artwork_status`` /
``artwork_inventory`` / ``media_completeness`` rather than re-implementing its own
"is there a poster on disk?" scan. Six divergent presence checks used to disagree
about reality (items « sans poster » with their posters on disk; INDEXER-03: the
two scan modes wrote divergent ``artwork_json``); this guard prevents a seventh
local detector from silently reintroducing the split.

Detection heuristic (mirrors the AST-scan style of ``test_layering.py``). A module
is a *local artwork detector* when it combines BOTH signals in the same file:

1. an **artwork literal** — a non-docstring string constant that is either
   - a concrete artwork **filename** (``poster.jpg``, ``folder.png``,
     ``{Title}-poster.jpg``, ``season01-poster.jpg`` — kind + image extension), or
   - a filename **suffix token** (``-poster``, ``-fanart`` … as used in a
     suffix tuple), or
   - a **regex source** that matches artwork files (a kind token + an image
     extension + regex metacharacters, e.g. ``r"(?:^|.+-)poster\\.(?:jpe?g|png)$"``);
2. a **detection call** — directory enumeration (``glob`` / ``rglob`` /
   ``scandir`` / ``listdir`` / ``iterdir`` / ``walk``) or ``re.*`` compilation/
   matching, i.e. the machinery a local scan would use to sweep a folder.

The heuristic is tuned to catch a NEW local detector while NOT flagging the
legitimate sites that merely *format* artwork names, validate *structure*, or
delegate presence to the canonical owner. Error-message strings
(``"poster.jpg not found"``) and dict-key accesses (``artwork.get("poster")``)
deliberately do NOT trip it — they carry no filename/suffix/regex literal.

The canonical owner (:data:`_CANONICAL_OWNER`) is excluded from the scan — it is
the module everyone else must delegate to. Every other detector must appear in
the pinned :data:`_ALLOWLIST` with a one-line rationale, so a new offender cannot
hide: an unlisted detector fails :func:`test_layering_artwork_no_local_glob_outside_core`,
and a migrated-away allowlist entry fails
:func:`test_layering_artwork_allowlist_has_no_stale_entries`.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PACKAGE_ROOT = _REPO_ROOT / "personalscraper"

#: The ONE canonical artwork-presence owner (DESIGN §5 T4). Excluded from the
#: scan — this is the module every other layer must delegate to.
_CANONICAL_OWNER = "personalscraper/core/artwork_naming.py"

#: Artwork kinds recognised by the canonical owner (kept in sync with
#: ``core.artwork_naming.ARTWORK_KIND_RES``).
_ARTWORK_KINDS = (
    "poster",
    "fanart",
    "landscape",
    "folder",
    "banner",
    "clearlogo",
    "clearart",
    "discart",
    "characterart",
)
_KINDS_ALT = "|".join(_ARTWORK_KINDS)

#: (a) Concrete artwork FILENAME literal — a kind token followed by an image
#: extension at end-of-string, preceded by start/non-alnum. Matches
#: ``"poster.jpg"``, ``"-poster.jpg"``, ``"{Title}-poster.jpg"``,
#: ``"*poster.png"`` and the ``r"...poster\.jpg"`` regex-source spelling (the
#: optional backslash tolerates an escaped dot). Does NOT match a trailing-text
#: message like ``"poster.jpg not found"`` (anchored ``$``) nor ``"composter.jpg"``
#: (non-alnum prefix required).
_ARTWORK_FILENAME_RE = re.compile(rf"(?i)(?:^|[^a-z0-9])(?:{_KINDS_ALT})\\?\.(?:jpe?g|png)$")

#: (b) Artwork filename SUFFIX token — ``"-poster"`` / ``"-fanart"`` … as used in
#: a suffix tuple (``structure_validator._ARTWORK_SUFFIXES``). Deliberately
#: requires a leading dash so a bare dict-key ``"poster"`` is NOT a hit.
_ARTWORK_SUFFIX_RE = re.compile(rf"(?i)^-(?:{_KINDS_ALT})$")

#: (c) Regex-SOURCE recognisers — a literal is treated as an artwork-matching
#: regex when it carries a kind token, an image-extension token AND a regex
#: metacharacter. This catches a new detector that compiles its own pattern
#: (``re.compile(r"...poster\.(?:jpe?g|png)$")``) without flagging plain prose.
_KIND_TOKEN_RE = re.compile(rf"(?i)(?:{_KINDS_ALT})")
_IMAGE_EXT_RE = re.compile(r"(?i)jpe?g|png")
_REGEX_METACHARS = ("\\.", "(?:", "(?P", "[", "$", "^", "\\d", ".+", ".*")

#: Directory-enumeration method names — how a local scan sweeps a folder.
_ENUM_ATTRS = frozenset({"glob", "rglob", "scandir", "listdir", "iterdir", "walk"})
#: ``re.<func>`` calls (receiver named ``re``) — the regex machinery.
_RE_FUNCS = frozenset({"compile", "match", "search", "fullmatch", "finditer", "findall"})

#: PINNED ALLOWLIST — repo-relative path → one-line rationale. Each entry is a
#: CURRENT local artwork detector that is legitimately NOT the canonical owner.
#: The set is pinned exactly: a new unlisted detector fails the scan, and a stale
#: entry (migrated onto the canonical owner) fails the no-stale-entries test.
_ALLOWLIST: dict[str, str] = {
    # `_ARTWORK_SUFFIXES` filename-suffix tuple drives STRUCTURE validation
    # (duplicate-artwork removal + orphan season-poster cleanup), not item-level
    # presence; item presence is owned by core.artwork_naming (P5.4).
    "personalscraper/enforce/structure_validator.py": (
        "structure/dedup via -kind suffix tuple, not presence detection"
    ),
    # `seasonNN-poster.jpg` is a per-SEASON fact (SeasonRecord.has_poster) that
    # core.artwork_naming deliberately EXCLUDES from item-level detection; the
    # item-level artwork_json is delegated to artwork_inventory (INDEXER-03).
    "personalscraper/indexer/scanner/_modes/_item_stage.py": (
        "season-poster (per-season) presence; item-level artwork_json delegated to core"
    ),
    # NamingPatterns holds artwork FILENAME formatting templates (the strings the
    # scraper WRITES); formatting, not on-disk presence. The season-dir re.compile
    # is unrelated to artwork presence.
    "personalscraper/naming_patterns.py": (
        "artwork filename formatting templates + season-dir regex, not presence detection"
    ),
}


def _looks_like_artwork_regex_source(text: str) -> bool:
    r"""Return True if ``text`` reads as a regex that matches artwork files.

    A literal qualifies when it carries an artwork kind token, an image-extension
    token AND at least one regex metacharacter (recogniser (c)). The metacharacter
    requirement keeps plain prose (``"poster.jpg not found"``) from matching while
    catching a hand-rolled pattern such as ``r"(?:^|.+-)poster\\.(?:jpe?g|png)$"``.

    Args:
        text: The string constant to classify.

    Returns:
        ``True`` iff ``text`` looks like an artwork-matching regex source.
    """
    return (
        bool(_KIND_TOKEN_RE.search(text))
        and bool(_IMAGE_EXT_RE.search(text))
        and any(meta in text for meta in _REGEX_METACHARS)
    )


def _is_artwork_literal(text: str) -> bool:
    """Return True if ``text`` is an artwork filename / suffix / regex-source literal.

    Union of recognisers (a) filename, (b) suffix token and (c) regex source
    described in this module's docstring.

    Args:
        text: The string constant to classify.

    Returns:
        ``True`` iff ``text`` carries artwork-presence detection intent.
    """
    return (
        bool(_ARTWORK_FILENAME_RE.search(text))
        or bool(_ARTWORK_SUFFIX_RE.match(text))
        or _looks_like_artwork_regex_source(text)
    )


def _docstring_constant_ids(tree: ast.Module) -> set[int]:
    """Return the ``id()`` of every docstring constant node in ``tree``.

    Docstrings routinely mention ``poster.jpg`` etc. in prose; excluding them
    keeps the guard focused on executable artwork-detection logic.

    Args:
        tree: The parsed module AST.

    Returns:
        A set of ``id()`` values for the leading string-constant of each module,
        class and function body.
    """
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                ids.add(id(body[0].value))
    return ids


@dataclass(frozen=True)
class _DetectorEvidence:
    """Evidence that a module is (or is not) a local artwork detector.

    Attributes:
        literals: ``(lineno, value)`` for each artwork literal found (non-docstring).
        detection_calls: ``(lineno, name)`` for each enumeration / ``re.*`` call.
    """

    literals: tuple[tuple[int, str], ...]
    detection_calls: tuple[tuple[int, str], ...]

    @property
    def is_local_detector(self) -> bool:
        """Whether both signals are present (an artwork literal AND a detection call)."""
        return bool(self.literals) and bool(self.detection_calls)

    def describe(self) -> str:
        """Return a compact human-readable summary of the evidence."""
        lit = "; ".join(f"L{ln}:{val!r}" for ln, val in self.literals[:3])
        calls = sorted({name for _, name in self.detection_calls})
        return f"literals=[{lit}] calls={calls}"


def _scan_source(source: str, rel: str) -> _DetectorEvidence:
    """Scan ``source`` (attributed to ``rel``) for local artwork-detection evidence.

    Pure function: parses the given text and collects the two heuristic signals.
    Decoupled from the filesystem so the guard can be self-pinned with synthetic
    positive/negative sources without writing probe files into the package tree.

    Args:
        source: Python source code to analyse.
        rel: Repo-relative POSIX path (used only for parse diagnostics).

    Returns:
        The :class:`_DetectorEvidence` for ``source``.
    """
    tree = ast.parse(source, filename=rel)
    doc_ids = _docstring_constant_ids(tree)
    literals: list[tuple[int, str]] = []
    detection: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in doc_ids:
            if _is_artwork_literal(node.value):
                literals.append((node.lineno, node.value))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            if attr in _ENUM_ATTRS:
                detection.append((node.lineno, attr))
            elif attr in _RE_FUNCS and isinstance(node.func.value, ast.Name) and node.func.value.id == "re":
                detection.append((node.lineno, f"re.{attr}"))
    return _DetectorEvidence(literals=tuple(literals), detection_calls=tuple(detection))


def _scan_file(py_file: Path) -> _DetectorEvidence:
    """Filesystem wrapper around :func:`_scan_source`."""
    rel = py_file.relative_to(_REPO_ROOT).as_posix()
    return _scan_source(py_file.read_text(encoding="utf-8"), rel)


def _current_offenders() -> dict[str, _DetectorEvidence]:
    """Return every module under ``personalscraper/`` (except the canonical owner) that is a local detector."""
    offenders: dict[str, _DetectorEvidence] = {}
    for py_file in sorted(_PACKAGE_ROOT.rglob("*.py")):
        rel = py_file.relative_to(_REPO_ROOT).as_posix()
        if rel == _CANONICAL_OWNER:
            continue
        try:
            evidence = _scan_file(py_file)
        except (OSError, UnicodeDecodeError, SyntaxError):  # pragma: no cover - defensive
            continue
        if evidence.is_local_detector:
            offenders[rel] = evidence
    return offenders


# ---------------------------------------------------------------------------
# Real-tree guard
# ---------------------------------------------------------------------------


def test_layering_artwork_no_local_glob_outside_core() -> None:
    """No unlisted module implements local artwork-presence glob/regex logic.

    Any module (outside the canonical owner and the pinned allowlist) that
    combines an artwork literal with a detection call is a new local detector and
    must be migrated onto ``core.artwork_naming`` — or, if legitimately not a
    presence check, consciously added to :data:`_ALLOWLIST` with a rationale.
    """
    offenders = _current_offenders()
    unexpected = {rel: ev for rel, ev in offenders.items() if rel not in _ALLOWLIST}
    assert not unexpected, (
        "New local artwork-presence detector(s) found outside core/artwork_naming.py.\n"
        "Delegate presence to core.artwork_naming (artwork_status / artwork_inventory / "
        "media_completeness), or pin the site in _ALLOWLIST with a rationale:\n"
        + "\n".join(f"  {rel}: {ev.describe()}" for rel, ev in sorted(unexpected.items()))
    )


def test_layering_artwork_allowlist_has_no_stale_entries() -> None:
    """Every pinned allowlist entry is still a current local detector.

    If a site was migrated onto the canonical owner, its allowlist entry becomes
    stale and must be removed — this keeps the pin honest and prevents a future
    offender from hiding behind an obsolete exemption.
    """
    offenders = _current_offenders()
    stale = sorted(rel for rel in _ALLOWLIST if rel not in offenders)
    assert not stale, "Stale _ALLOWLIST entries (no longer local artwork detectors — remove them):\n" + "\n".join(
        f"  {rel}" for rel in stale
    )


def test_layering_artwork_allowlist_paths_exist() -> None:
    """Every pinned allowlist path resolves to a real file (guards against typos)."""
    missing = sorted(rel for rel in _ALLOWLIST if not (_REPO_ROOT / rel).is_file())
    assert not missing, "Allowlisted path(s) do not exist:\n" + "\n".join(f"  {rel}" for rel in missing)


# ---------------------------------------------------------------------------
# Self-pin control tests
#
# The real-tree tests above could pass vacuously if the heuristic rotted into a
# no-op. The synthetic-source controls below feed known-bad and known-good inputs
# through the SAME ``_scan_source`` engine so the guard is proven non-vacuous: it
# must flag the bad cases and exempt the good ones.
# ---------------------------------------------------------------------------

_SYNTHETIC_REL = "personalscraper/_synthetic_probe.py"


def test_layering_artwork_synthetic_filename_glob_is_flagged() -> None:
    """POSITIVE control: a ``poster.jpg`` glob IS a local detector (non-vacuous anchor).

    This is the exact shape the task's trip-proof injects. If ``_scan_source``
    were broken into an always-empty stub, this assertion would fail.
    """
    source = 'from pathlib import Path\ndef has_poster(d: Path) -> bool:\n    return bool(list(d.glob("poster.jpg")))\n'
    evidence = _scan_source(source, _SYNTHETIC_REL)
    assert evidence.is_local_detector, "guard failed to flag a local poster.jpg glob (vacuous guard!)"
    assert any("poster.jpg" in val for _, val in evidence.literals)


def test_layering_artwork_synthetic_suffix_tuple_is_flagged() -> None:
    """POSITIVE control: a ``-poster`` suffix tuple + ``iterdir`` IS a local detector."""
    source = (
        "from pathlib import Path\n"
        '_SUFFIXES = ("-poster", "-fanart")\n'
        "def detect(d: Path) -> bool:\n"
        "    return any(f.stem.endswith(_SUFFIXES) for f in d.iterdir())\n"
    )
    evidence = _scan_source(source, _SYNTHETIC_REL)
    assert evidence.is_local_detector, "guard failed to flag a -poster suffix detector (vacuous guard!)"


def test_layering_artwork_synthetic_regex_detector_is_flagged() -> None:
    r"""POSITIVE control: a compiled ``poster\.(jpe?g|png)`` regex + ``scandir`` IS a local detector."""
    source = (
        "import os, re\n"
        '_RE = re.compile(r"(?:^|.+-)poster\\.(?:jpe?g|png)$")\n'
        "def detect(d):\n"
        "    return any(_RE.match(e.name) for e in os.scandir(d))\n"
    )
    evidence = _scan_source(source, _SYNTHETIC_REL)
    assert evidence.is_local_detector, "guard failed to flag a compiled artwork regex detector (vacuous guard!)"


def test_layering_artwork_delegating_consumer_is_not_flagged() -> None:
    """NEGATIVE control: a module that delegates to ``artwork_status`` is NOT a detector.

    It enumerates the directory for OTHER concerns (episodes) but carries no
    artwork literal — presence comes from the canonical owner.
    """
    source = (
        "from pathlib import Path\n"
        "from personalscraper.core.artwork_naming import artwork_status\n"
        "def summarise(d: Path) -> bool:\n"
        "    videos = [f for f in d.iterdir() if f.suffix == '.mkv']\n"
        "    return artwork_status(d).poster and bool(videos)\n"
    )
    evidence = _scan_source(source, _SYNTHETIC_REL)
    assert not evidence.is_local_detector, f"delegating consumer wrongly flagged: {evidence.describe()}"


def test_layering_artwork_error_message_literal_is_not_flagged() -> None:
    """NEGATIVE control: an error-message string naming a filename is NOT a detector.

    ``"poster.jpg not found"`` carries trailing prose, so it is not an artwork
    filename literal even though it enumerates the directory.
    """
    source = (
        "from pathlib import Path\n"
        "def check(d: Path) -> str:\n"
        "    files = list(d.iterdir())\n"
        '    return "poster.jpg not found" if not files else "ok"\n'
    )
    evidence = _scan_source(source, _SYNTHETIC_REL)
    assert not evidence.is_local_detector, f"error-message literal wrongly flagged: {evidence.describe()}"


def test_layering_artwork_dict_key_access_is_not_flagged() -> None:
    """NEGATIVE control: reading a bare ``"poster"`` key from artwork_json is NOT a detector."""
    source = (
        "import json\n"
        "from pathlib import Path\n"
        "def from_row(d: Path, raw: str) -> bool:\n"
        "    for _ in d.iterdir():\n"
        "        pass\n"
        '    return bool(json.loads(raw).get("poster"))\n'
    )
    evidence = _scan_source(source, _SYNTHETIC_REL)
    assert not evidence.is_local_detector, f"dict-key access wrongly flagged: {evidence.describe()}"


def test_layering_artwork_canonical_owner_would_be_flagged() -> None:
    """SANITY: the canonical owner ITSELF trips the heuristic (recogniser is real, not vacuous).

    ``core.artwork_naming`` is the one module exempted from the scan, yet its
    regex table + ``iterdir`` make it a textbook local detector. Asserting the
    heuristic recognises the REAL canonical detection code proves the guard is
    anchored to production reality — if the recognisers ever stopped matching
    genuine artwork logic, this fails.
    """
    owner = _REPO_ROOT / _CANONICAL_OWNER
    assert owner.is_file(), f"canonical owner {_CANONICAL_OWNER} does not exist"
    evidence = _scan_file(owner)
    assert evidence.is_local_detector, (
        "heuristic no longer recognises core/artwork_naming.py as a detector — "
        "the recognisers may have rotted (vacuous guard!)"
    )
