#!/usr/bin/env python3
"""What the design host is serving — the branch, the commit, and the dirt.

THE DEFECT THIS ANSWERS. The drawer stated `0.98.23` and `build 58d0d4fd · à
jour` as literals, while the repository stood twenty patch versions further on
and « à jour » asserted a freshness nothing measured. A screen that says
nothing sends its reader to look; a screen that states a plausible answer stops
them looking, and that value was credible precisely because it had been a real
version of this repository once (B-079, B-080).

WHY IT IS A FILE OF ITS OWN. It came out of `serve.py`, which crossed the soft
module ceiling the moment this arrived. The split is on the SUBJECT and not on
the line count: `serve.py` answers « what document do I send? » and this answers
« what tree am I sending it from? ». They share nothing but the design root.

WHAT IT DOES NOT DO. It never refuses. `scripts/deploy.sh` refuses a dirty or
non-`main` tree because production must only ever serve `main`; the design host
exists to serve a BRANCH, which is what it is for. So this declares instead —
and where it cannot declare (no repository, no git, a command that hangs), it
answers None and the page says the identity is unavailable, with the reason.
Never a plausible value: that is the defect, one layer down.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

# HOW LONG THE HOST MAY SPEND ANSWERING « WHAT AM I SERVING? ». Three git
# invocations, each bounded: the answer is worth a moment and never worth a
# hung request, and a host that stops answering teaches its reader to stop
# asking — which is the failure this whole mechanism repairs.
IDENTITY_TIMEOUT = 5.0


def _git(root: Path, *arguments: str) -> str | None:
    """Runs one read-only git command in a tree's repository.

    Args:
        root: The directory to run in — the design root, or any tree.
        *arguments: The git arguments, without the program name.

    Returns:
        The command's trimmed output, or None when git is absent, the root is
        not a repository, the command fails, or it does not answer in time.
    """
    try:
        run = subprocess.run(
            ["git", *arguments], cwd=root, capture_output=True,
            text=True, timeout=IDENTITY_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return None
    if run.returncode != 0:
        return None
    return run.stdout.strip()


def served_identity(root: Path) -> dict[str, object] | None:
    """Returns what a host serving `root` is serving: branch, commit, dirt.

    COMPUTED ON EVERY REQUEST, never cached. The whole defect this answers is a
    screen asserting something that had stopped being true — a hard-coded
    version and a build sha the repository had left twenty patch versions
    behind — so an answer cached at boot would be the same defect with a
    shorter half-life. The host already rebuilds per request for exactly this
    reason; naming what it rebuilt costs three bounded git reads beside it.

    THE DESIGN HOST DECLARES WHERE PRODUCTION REFUSES, and that is deliberate.
    `deploy.sh` refuses a dirty or non-`main` tree because production must only
    ever serve `main`. This host exists to serve a branch — that is what it is
    for — so it does not refuse; it says which branch, at which commit, and
    whether the tree carries changes that commit does not.

    Args:
        root: The tree the host serves from.

    Returns:
        A mapping with `branch`, `commit` and `dirty`, or None when the root is
        not a git repository — in which case the page says so rather than
        showing a plausible value.
    """
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    commit = _git(root, "rev-parse", "--short", "HEAD")
    if not branch or not commit:
        return None
    # `--porcelain` over the whole tree, untracked files INCLUDED: a file that
    # is not in the index is still a file the build reads, and `serve.py`
    # rebuilds from `src/` whatever git thinks of it. An empty answer is the
    # only clean tree.
    status = _git(root, "status", "--porcelain")
    if status is None:
        return None
    return {"branch": branch, "commit": commit, "dirty": bool(status)}


# WHERE THE IDENTITY IS PUBLISHED ON THE PAGE. A classic inline script runs
# while the document parses; the shell's bundle is a module and runs after. So
# the value is in place before anything reads it, whatever else the build emits.
IDENTITY_MARKER = "</head>"


def with_served_identity(document: bytes, root: Path) -> bytes:
    """Publishes this host's identity on the document it is about to send.

    Args:
        document: The built document, as the build emitted it.
        root: The tree the host serves from.

    Returns:
        The same bytes with one inline script inserted before `</head>`, or
        unchanged when the document carries no head to insert into — a
        malformed document is not a reason to answer nothing.
    """
    identity = served_identity(root)
    if identity is None:
        # NOTHING is published rather than a hole: `lib/served-identity.ts`
        # reads the absence and says the identity is unavailable, with the
        # reason. A partial payload would render « undefined » on screen, which
        # reads as a value.
        return document
    published = json.dumps(identity, ensure_ascii=False).encode("utf-8")
    script = b"<script>window.__servedIdentity=" + published + b";</script>"
    marker = IDENTITY_MARKER.encode("utf-8")
    head, found, rest = document.partition(marker)
    if not found:
        return document
    return head + script + marker + rest
