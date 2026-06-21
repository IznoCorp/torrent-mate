"""Pure body-region split/merge for marker-safe ticket description edits (tiller §6.1).

Reuses the delimiters and regexes from :mod:`kanbanmate.core.body_edit` (STATUS_BEGIN/END,
_MARKER_LINE, PRESERVED_MARKERS) to parse an issue body into disjoint protected regions +
operator-editable freeform prose. The merge re-assembles them so protected content is
NEVER altered by an operator edit — only the freeform prose changes.

Pure functional core — imports only :mod:`re` and :mod:`dataclasses`; no I/O (DESIGN §3.2).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from kanbanmate.core.body_edit import (
    PRESERVED_MARKERS,
    STATUS_BEGIN,
    STATUS_END,
    _STATUS_BLOCK,
)

# Heading that marks the start of the brainstorm section (appended by the brainstorm agent).
_BRAINSTORM_HEADING = "## Brainstorm"
# Match the brainstorm section: the heading + everything after it (greedy to end of string).
_BRAINSTORM_SECTION = re.compile(
    r"^## Brainstorm\b.*",
    re.MULTILINE | re.DOTALL,
)


@dataclass
class BodyRegions:
    """The decomposed regions of an issue body.

    Attributes:
        status_block: The full ``<!-- kanban:status:begin -->…end -->`` block, or ``None``.
        markers: Mapping of marker key → full ``**key**: value`` line for each PRESERVED_MARKERS key
            found in the body.
        brainstorm: The ``## Brainstorm`` section (heading + body), or ``None`` when absent.
        freeform: The operator-editable prose (everything not in the above regions).
    """

    status_block: str | None = None
    markers: dict[str, str] = field(default_factory=dict)
    brainstorm: str | None = None
    freeform: str = ""


def split_body_regions(body: str) -> BodyRegions:
    """Split *body* into protected regions + freeform prose.

    Protected regions (extracted verbatim, in order of priority):
    1. The status block (``STATUS_BEGIN``…``STATUS_END``).
    2. Each ``**key**: value`` marker line for keys in ``PRESERVED_MARKERS``.
    3. The ``## Brainstorm`` section (heading + all text after it).

    Everything else is ``freeform`` — the prose the operator may freely edit.

    The split is ORDER-PRESERVING and DISJOINT: no byte appears in more than one
    region, so ``merge_body_regions(split_body_regions(body), new_freeform=…)``
    never double-counts or drops content.

    Args:
        body: The raw GitHub issue body string.

    Returns:
        A :class:`BodyRegions` with the parsed regions.
    """
    regions = BodyRegions()
    work = body

    # 1. Extract status block (HTML comment delimiters — invisible in rendered body).
    m = _STATUS_BLOCK.search(work)
    if m:
        regions.status_block = m.group(0)
        work = work[: m.start()] + work[m.end() :]

    # 2. Extract brainstorm section (everything from ## Brainstorm to end-of-string).
    m = _BRAINSTORM_SECTION.search(work)
    if m:
        regions.brainstorm = m.group(0).rstrip()
        work = work[: m.start()].rstrip()

    # 3. Extract preserved marker lines one by one (in place).
    for key in PRESERVED_MARKERS:
        # Build a per-key pattern anchored at line start.
        pat = re.compile(rf"^\*\*{re.escape(key)}\*\*:[^\n]*$", re.MULTILINE)
        mm = pat.search(work)
        if mm:
            regions.markers[key] = mm.group(0)
            # Remove the matched line plus any surrounding blank lines it created.
            start = mm.start()
            end = mm.end()
            work = (work[:start].rstrip("\n") + "\n" + work[end:].lstrip("\n")).strip("\n")

    # 4. What remains is freeform prose.
    regions.freeform = work.strip()
    return regions


def merge_body_regions(regions: BodyRegions, *, new_freeform: str) -> str:
    """Re-assemble *regions* with *new_freeform* replacing the previous freeform prose.

    Assembly order (matches the canonical body layout):
    1. Status block at the very top (always-visible header).
    2. New freeform prose (the operator's edit).
    3. Preserved marker lines (one per line, blank-line separated block).
    4. Brainstorm section.

    *new_freeform* is de-fanged: any literal ``STATUS_BEGIN``/``STATUS_END`` delimiter is
    stripped so an operator cannot embed a fake status block that confuses the region parser
    on the next read.

    Args:
        regions: The :class:`BodyRegions` from :func:`split_body_regions`.
        new_freeform: The operator's edited prose (replaces ``regions.freeform``).

    Returns:
        The reassembled issue body string.
    """
    # De-fang: strip delimiter literals from the operator-supplied freeform.
    safe_freeform = new_freeform.replace(STATUS_BEGIN, "").replace(STATUS_END, "").strip()

    parts: list[str] = []
    if regions.status_block:
        parts.append(regions.status_block)
    if safe_freeform:
        parts.append(safe_freeform)
    if regions.markers:
        parts.append(
            "\n".join(regions.markers[k] for k in PRESERVED_MARKERS if k in regions.markers)
        )
    if regions.brainstorm:
        parts.append(regions.brainstorm)

    return "\n\n".join(p for p in parts if p)
