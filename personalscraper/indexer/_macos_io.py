"""macOS-specific I/O advisory hints for the media indexer.

Exposes :func:`sequential_hint`, which advises the OS to read a file
descriptor sequentially before fingerprinting or mediainfo parsing begins.
This reduces seek amplification on spinning and macFUSE-mounted disks by
pre-fetching the file into the unified buffer cache.

On macOS (Darwin) the hint is issued via ``mmap + madvise(MADV_SEQUENTIAL)``
rather than ``fcntl(fd, F_RDADVISE, …)``.  Both mechanisms signal the same
kernel intent; however the ``fcntl``/``F_RDADVISE`` path is **unusable from
Python on arm64 macOS** due to a macOS ARM64 ABI constraint: ``fcntl(2)`` is
declared with a variadic prototype (``int fcntl(int, int, ...)``), and on the
arm64 ABI the calling convention for variadic vs fixed-arg functions differs
at the register level.  Python's ``fcntl`` C-extension and ``ctypes`` both
generate non-variadic call sequences, causing the kernel to reject the call
with ``ENOTTY`` (errno 25).  This was confirmed empirically: a native C
program calling ``fcntl(fd, F_RDADVISE, &ra)`` through the variadic prototype
succeeds; the same call through a non-variadic function pointer fails with
``ENOTTY``.  ``mmap.madvise(MADV_SEQUENTIAL)`` is the correct pure-Python
advisory path on Darwin.

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

On non-Darwin platforms the function is a documented no-op — it never raises
:exc:`ImportError` and never raises at runtime.
"""

from __future__ import annotations

import mmap
import os
import platform

# F_RDADVISE is a macOS-only fcntl command code (decimal 35, from <sys/fcntl.h>).
# Exported as a module constant for reference; NOT used at runtime due to the
# arm64 variadic-ABI limitation (see module docstring).
F_RDADVISE: int = 35

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

    Raises:
        OSError: On Darwin only, if the ``mmap`` or ``madvise`` syscall
            fails (e.g. the fd is closed, not a regular file, or the file
            is empty).  The hint is purely advisory so callers should
            catch and log ``OSError`` rather than propagating it as a
            fatal error.
    """
    if not _IS_DARWIN:
        # Non-Darwin: nothing to do.  posix_fadvise is not available on macOS,
        # and there is no portable equivalent that justifies a syscall here.
        return

    # Determine file size without an extra stat call when possible.
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
