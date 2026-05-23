"""macOS-specific I/O advisory hints for the media indexer.

Exposes two public functions:

* :func:`sequential_hint` — advises the OS to read a file descriptor
  sequentially via ``mmap + madvise(MADV_SEQUENTIAL)``.  Kept for callers
  that have not yet migrated; prefer :func:`disable_cache` for read-once paths.

* :func:`disable_cache` — issues ``fcntl(fd, F_NOCACHE, 1)`` on Darwin,
  which causes pages read through that fd to bypass the unified buffer cache
  entirely.  Correct choice for fingerprint head/tail reads where the bytes
  are hashed once and the result persisted to the indexer DB — the page cache
  contributes nothing after the read.

``F_RDADVISE`` vs ``F_NOCACHE`` on arm64
-----------------------------------------
``F_RDADVISE`` (decimal 35) is unusable from Python on arm64 macOS due to a
macOS ARM64 ABI constraint: ``fcntl(2)`` is declared with a variadic prototype
(``int fcntl(int, int, ...)``), and on the arm64 ABI the calling convention
for variadic vs fixed-arg functions differs at the register level.  Python's
``fcntl`` C-extension and ``ctypes`` both generate non-variadic call sequences,
causing the kernel to reject the call with ``ENOTTY`` (errno 25).

``F_NOCACHE`` (decimal 48) takes a single integer argument, not a variadic
struct pointer.  Python's ``fcntl.fcntl(fd, 48, 1)`` emits a non-variadic
call that matches the arm64 ABI for single-int arguments — this was confirmed
empirically on macOS 14.5 / arm64 (see ACC-12.B.1 in audit/12-ntfs-cache-
pressure.md).

Why ``os.posix_fadvise`` is NOT used
--------------------------------------
``os.posix_fadvise`` is a Linux-only extension; it is absent from macOS /
Darwin (CPython gates it on ``HAVE_POSIX_FADVISE`` which is not set on macOS).
See DESIGN §11.6.

``F_RDADVISE`` constant
-----------------------
The constant ``F_RDADVISE = 35`` is still exported by this module so that
callers and tests may reference it without importing ``<fcntl.h>`` constants
manually.  It is not used at runtime on Darwin Python due to the ABI
limitation described above.

On non-Darwin platforms all functions are documented no-ops — they never raise
:exc:`ImportError` and never raise at runtime.
"""

from __future__ import annotations

import mmap
import os
import platform

# F_RDADVISE is a macOS-only fcntl command code (decimal 35, from <sys/fcntl.h>).
# Exported as a module constant for reference; NOT used at runtime due to the
# arm64 variadic-ABI limitation (see module docstring).
F_RDADVISE: int = 35

# F_NOCACHE is a macOS-only fcntl command code (decimal 48, from <sys/fcntl.h>).
# When set to 1, pages read through the fd bypass the unified buffer cache.
# Unlike F_RDADVISE, F_NOCACHE takes a single int argument — compatible with
# the arm64 ABI through Python's fcntl.fcntl().
_F_NOCACHE: int = 48

# ---------------------------------------------------------------------------
# Platform detection — performed once at import time so the hot path (inside
# the scan loop) pays zero runtime overhead after each call.
# ---------------------------------------------------------------------------
_IS_DARWIN: bool = platform.system() == "Darwin"


def sequential_hint(fd: int, offset: int = 0, length: int = 0) -> None:
    """Advise the OS to read a file descriptor sequentially.

    On macOS (Darwin): maps the file into virtual memory and issues
    ``madvise(MADV_SEQUENTIAL)`` to advise the kernel to pre-fetch pages
    sequentially.  This primes the unified buffer cache before large
    sequential reads (fingerprinting head/tail chunks, full mediainfo
    parses), reducing seek amplification on spinning and macFUSE-mounted
    disks.

    Implementation note: ``fcntl(fd, F_RDADVISE, …)`` cannot be used from
    Python on arm64 macOS because ``fcntl(2)`` has a variadic prototype and
    the arm64 ABI uses a different register layout for variadic vs fixed-arg
    calls.  Python's ``fcntl`` C-extension emits a non-variadic call, which
    the kernel rejects with ``ENOTTY``.  ``mmap + madvise`` achieves the
    same prefetch effect without this restriction.

    On non-Darwin platforms: this function is a **no-op** — it returns
    immediately without any system call or import.  It will never raise
    :exc:`ImportError` and will never raise at runtime regardless of the
    host OS.

    Note: ``os.posix_fadvise`` is explicitly NOT used here because it is
    absent from Darwin (DESIGN §11.6).

    Args:
        fd: An open file descriptor (as returned by ``os.open`` or
            ``open(...).fileno()``).  Must refer to a regular readable file
            on Darwin; on non-Darwin the value is ignored entirely.
        offset: Byte offset within the file at which the advisory read
            should start.  Defaults to ``0`` (beginning of file).  The
            ``mmap`` window always covers the full file; this parameter
            is accepted for API compatibility with the ``F_RDADVISE``
            interface but is not used to restrict the mapped range.
        length: Number of bytes to advise.  Defaults to ``0`` (full file).
            Like ``offset``, accepted for API compatibility but not used
            to restrict the ``mmap`` size (mapping a partial file with
            ``mmap`` requires the exact size, which adds a ``stat`` call
            that would cost more than the hint saves for small files).

    Returns:
        ``None``.  The function is purely advisory and intentionally swallows
        any ``OSError`` raised by ``fstat``, ``mmap``, or ``madvise`` — the
        hint must never break the surrounding read.  Conditions that trigger
        a silent fall-through include: the fd is closed or invalid, the
        underlying file is not memory-mappable (sockets, pipes, fake fds
        used by ``pyfakefs``), or the kernel rejects the advice.  Callers
        therefore do not need to wrap this call in a ``try`` block.
    """
    if not _IS_DARWIN:
        # Non-Darwin: nothing to do.  posix_fadvise is not available on macOS,
        # and there is no portable equivalent that justifies a syscall here.
        return

    try:
        # Determine file size; some fake fds (e.g. pyfakefs) raise here.
        file_size = os.fstat(fd).st_size
        if file_size == 0:
            # mmap(2) rejects zero-length mappings; nothing to hint.
            return

        # Map the file read-only, advise MADV_SEQUENTIAL, then immediately unmap.
        # The mapping itself is lightweight (no physical I/O); the advice tells the
        # VM subsystem to read ahead aggressively on the next real page faults.
        mm = mmap.mmap(fd, file_size, access=mmap.ACCESS_READ)
        try:
            mm.madvise(mmap.MADV_SEQUENTIAL)
        finally:
            mm.close()
    except (OSError, ValueError):
        # The hint is purely advisory — never propagate failures to the
        # caller's read path.  ``ValueError`` covers the edge case where
        # ``mmap`` rejects a non-regular file with a value (rather than OS)
        # error, observed on some pyfakefs versions.
        return


def disable_cache(fd: int) -> None:
    """Disable UBC caching on this fd for read-once operations.

    Issues ``fcntl(fd, F_NOCACHE, 1)`` on Darwin.  Pages read through this fd
    bypass the unified buffer cache entirely — appropriate for fingerprint
    head/tail reads where the bytes are hashed once and the digest stored in
    the indexer DB.  The page cache contributes nothing after the read is done,
    so letting macOS populate it wastes RAM and competes with Plex / n8n
    working sets.

    Unlike ``F_RDADVISE`` (which has an arm64 variadic-ABI issue documented in
    the module docstring), ``F_NOCACHE`` takes a single int argument and works
    correctly through Python's ``fcntl`` extension on arm64 Darwin — verified
    empirically on macOS 14.5 (see ACC-12.B.1 in audit/12-ntfs-cache-
    pressure.md).

    On non-Darwin platforms this function is a **no-op** — it returns
    immediately without any system call.  It will never raise
    :exc:`ImportError` and will never raise at runtime regardless of the host
    OS.

    Args:
        fd: An open file descriptor (as returned by ``os.open``).  Must refer
            to a regular readable file on Darwin; on non-Darwin the value is
            ignored entirely.

    Returns:
        ``None``.  Silently swallows ``OSError`` and ``ValueError`` so that
        cache-bypass failure never breaks the surrounding read path.
    """
    if not _IS_DARWIN:
        return
    try:
        import fcntl as _fcntl

        _fcntl.fcntl(fd, _F_NOCACHE, 1)
    except (OSError, ValueError):
        # Advisory only — never propagate failures to the caller's read path.
        return
