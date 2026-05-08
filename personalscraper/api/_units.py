"""Comparable, parseable disk-size custom type.

Implements DESIGN S3.2: ByteSize with parse() for human-readable size strings
like "1GB", "500MiB", and direct integer construction.
"""

import re
from dataclasses import dataclass

_SIZE_RE = re.compile(r"^\s*([\d.]+)\s*([KMGTP]i?B|B)?\s*$", re.IGNORECASE)
_DEC = {"B": 1, "KB": 10**3, "MB": 10**6, "GB": 10**9, "TB": 10**12, "PB": 10**15}
_BIN = {"B": 1, "KIB": 2**10, "MIB": 2**20, "GIB": 2**30, "TIB": 2**40, "PIB": 2**50}


@dataclass(frozen=True, order=True)
class ByteSize:
    """Comparable, parseable disk-size value in bytes.

    Attributes:
        bytes: The size in bytes as an integer.
    """

    bytes: int

    @classmethod
    def parse(cls, value: "int | float | str | ByteSize") -> "ByteSize":
        """Parse a size from an integer, float, or human-readable string.

        Args:
            value: An int (bytes), float (bytes), ByteSize (returned as-is),
                   or string like "1GB", "500MiB", "1.5TB".

        Returns:
            A ByteSize instance.

        Raises:
            ValueError: If the string cannot be parsed as a size literal.
        """
        if isinstance(value, ByteSize):
            return value
        if isinstance(value, (int, float)):
            return cls(int(value))
        m = _SIZE_RE.match(value)
        if not m:
            raise ValueError(f"Invalid size literal: {value!r}")
        num = float(m.group(1))
        unit = (m.group(2) or "B").upper()
        table = _BIN if "I" in unit else _DEC
        return cls(int(num * table[unit]))

    def __int__(self) -> int:
        return self.bytes
