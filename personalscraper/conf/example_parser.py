"""Parse config.example.json5 to extract (comment, key-path, default-value) triples.

Used by ``init-config`` to turn example comments into interactive prompts shown
to the user during first-time setup.

Approach — line-based (no third-party JSON5 AST parser required):
    The file is read line by line. A simple state machine tracks:

    - Object/array nesting depth to build dotted ``key_path`` strings
      (e.g. ``paths.torrent_complete_dir``, ``disks[0].id``).
    - Accumulated ``//`` line-comment and ``/* */`` block-comment text that
      immediately precedes a key:value line.
    - Key:value lines that emit a :class:`Prompt`.

    Array handling (per-element):
        Each array element emits its own Prompt using the key path
        ``parent_key[N]`` (zero-based index). Object elements within arrays
        emit Prompts per field (e.g. ``disks[0].id``). This gives the caller
        fine-grained control over each element during interactive prompting.

    Limitations (by design — fits the well-formed, human-edited example file):
    - String values containing ``{``, ``}``, ``[``, or ``]`` outside of JSON5
      string literals would confuse the depth counter; the example file avoids
      this pattern.
    - Inline ``/* */`` on the same line as a key is not treated as a block
      comment; the example file does not use this style.
    - Commented-out example blocks (``// { ... }``) are skipped correctly
      because those lines start with ``//`` and contain no bare ``key:`` token.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypedDict


class _StackFrame(TypedDict, total=False):
    """A single frame on the nesting stack during JSON5 parsing."""

    type: Literal["object", "array"]
    key: str
    index: int  # only present for array frames


@dataclass(frozen=True)
class Prompt:
    """A single interactive prompt extracted from a JSON5 example file.

    Each Prompt corresponds to one leaf key in the example file, paired with
    the ``//`` or ``/* */`` comment(s) that immediately precede it and the
    raw JSON5 literal that serves as the default value.

    Attributes:
        key_path: Dotted path to the key (e.g. ``"paths.torrent_complete_dir"``,
            ``"disks[0].id"``).
        comment: Accumulated comment text stripped of ``//`` or ``/* */``
            delimiters and leading/trailing whitespace. Multiple comment lines
            are joined with a single space.
        default_value: The raw JSON5 value literal as it appears in the source
            (e.g. ``'"hevc"'``, ``'true'``, ``'["fra", "eng"]'``).
    """

    key_path: str
    comment: str
    default_value: str


# ---------------------------------------------------------------------------
# Internal patterns
# ---------------------------------------------------------------------------

# Matches a JSON5 key:value line, capturing key and raw value.
# Key may be bare (unquoted) or quoted. Value is everything after ": " up to
# optional trailing comma.
# Examples:
#   preferred_codec: "hevc",
#   config_version: 1,
#   enabled: true,
#   data_dir: "./.data",
_KEY_VALUE_RE = re.compile(
    r"""
    ^                         # start of stripped line
    (?:"([^"]+)"|'([^']+)'|([a-zA-Z_][a-zA-Z0-9_]*))  # key (quoted or bare)
    \s*:\s*                   # colon separator
    (.+?)                     # value (non-greedy)
    ,?\s*$                    # optional trailing comma + whitespace
    """,
    re.VERBOSE,
)

# Matches a JSON5 object-open line: key: {
_OBJECT_OPEN_RE = re.compile(
    r"""
    ^
    (?:"([^"]+)"|'([^']+)'|([a-zA-Z_][a-zA-Z0-9_]*))
    \s*:\s*\{
    \s*$
    """,
    re.VERBOSE,
)

# Matches a JSON5 array-open line: key: [
_ARRAY_OPEN_RE = re.compile(
    r"""
    ^
    (?:"([^"]+)"|'([^']+)'|([a-zA-Z_][a-zA-Z0-9_]*))
    \s*:\s*\[
    \s*$
    """,
    re.VERBOSE,
)

# Matches a bare { opening an array element (object element in array)
_BARE_OBJECT_OPEN_RE = re.compile(r"^\{\s*$")

# Matches a bare closing brace (end of object or array element)
_CLOSE_BRACE_RE = re.compile(r"^[}\]],?\s*$")

# Matches a // comment line
_LINE_COMMENT_RE = re.compile(r"^//\s?(.*)")

# Matches /* block comment start
_BLOCK_COMMENT_START_RE = re.compile(r"^/\*\*?\s?(.*)")

# Matches block comment end */
_BLOCK_COMMENT_END_RE = re.compile(r"^(.*?)\*/\s*$")


def _extract_key(match: re.Match[str]) -> str:
    """Return the key name from a regex match with 3 key capture groups."""
    # Groups 1, 2, 3 correspond to double-quoted, single-quoted, bare key
    return match.group(1) or match.group(2) or match.group(3)


def parse_example(example_path: Path) -> list[Prompt]:
    """Read a JSON5 example file and extract one Prompt per leaf key.

    Reads the file line by line, accumulates consecutive ``//`` comments or
    ``/* */`` block comments into a buffer, and emits a :class:`Prompt` when
    a ``key: value`` line is encountered. The buffer is reset on blank lines
    and on any line that is neither a comment nor a key:value assignment.

    Array handling: each plain-scalar element in an array emits its own
    Prompt using the key path ``parent_key[N]`` (zero-based index). Object
    elements within arrays emit Prompts per field (e.g. ``disks[0].id``).

    Args:
        example_path: Absolute or relative path to the JSON5 example file.

    Returns:
        Ordered list of :class:`Prompt` instances, one per leaf key found
        in the file. Returns an empty list if the file has no key:value lines
        or if parsing encounters only structural/comment lines.

    Raises:
        OSError: If the file cannot be opened (e.g. does not exist).
    """
    prompts: list[Prompt] = []

    # Stack tracks the current nesting context.
    # Each entry is a _StackFrame with:
    #   "type": "object" | "array"
    #   "key":  the key that opened this scope (for building key_path)
    #   "index": int (arrays only) — current element index
    stack: list[_StackFrame] = []

    comment_buffer: list[str] = []
    in_block_comment = False

    def _current_prefix() -> str:
        """Build the dotted key_path prefix from the current stack."""
        parts: list[str] = []
        for frame in stack:
            frame_type = frame["type"]
            frame_key = frame["key"]
            if frame_type == "array":
                idx = frame["index"]
                parts.append(f"{frame_key}[{idx}]")
            else:
                if frame_key:
                    parts.append(str(frame_key))
        return ".".join(p for p in parts if p)

    def _reset_buffer() -> None:
        comment_buffer.clear()

    def _flush_comment() -> str:
        """Return accumulated comment text and reset the buffer."""
        text = " ".join(comment_buffer).strip()
        comment_buffer.clear()
        return text

    lines = example_path.read_text(encoding="utf-8").splitlines()

    for raw_line in lines:
        stripped = raw_line.strip()

        # ----------------------------------------------------------------
        # Block comment handling (/* ... */ spanning multiple lines)
        # ----------------------------------------------------------------
        if in_block_comment:
            end_m = _BLOCK_COMMENT_END_RE.match(stripped)
            if end_m:
                # End of block comment — accumulate trailing text if any
                tail = end_m.group(1).strip()
                if tail:
                    comment_buffer.append(tail)
                in_block_comment = False
            else:
                # Middle of block comment — accumulate the line
                line_text = stripped.lstrip("*").strip()
                if line_text:
                    comment_buffer.append(line_text)
            continue

        start_m = _BLOCK_COMMENT_START_RE.match(stripped)
        if start_m:
            head = start_m.group(1).strip()
            # Check if it closes on the same line
            end_m = _BLOCK_COMMENT_END_RE.match(head)
            if end_m:
                # Single-line block comment: /* text */
                text = end_m.group(1).strip()
                if text:
                    comment_buffer.append(text)
            else:
                if head:
                    comment_buffer.append(head)
                in_block_comment = True
            continue

        # ----------------------------------------------------------------
        # Line comment: // text
        # ----------------------------------------------------------------
        line_comment_m = _LINE_COMMENT_RE.match(stripped)
        if line_comment_m:
            text = line_comment_m.group(1).strip()
            if text:
                comment_buffer.append(text)
            # else: empty // line — keep buffer, don't reset
            continue

        # ----------------------------------------------------------------
        # Blank line → reset comment buffer
        # ----------------------------------------------------------------
        if not stripped:
            _reset_buffer()
            continue

        # ----------------------------------------------------------------
        # Closing brace/bracket — pop stack
        # ----------------------------------------------------------------
        if _CLOSE_BRACE_RE.match(stripped):
            if stack:
                popped = stack.pop()
                # If we closed an object that was an array element, increment
                # the parent array's index so the next element gets [N+1].
                if popped["type"] == "object" and stack and stack[-1]["type"] == "array":
                    stack[-1]["index"] = stack[-1]["index"] + 1
            _reset_buffer()
            continue

        # ----------------------------------------------------------------
        # Array element: bare { (object inside array)
        # ----------------------------------------------------------------
        if _BARE_OBJECT_OPEN_RE.match(stripped):
            # We are inside an array — push an object frame with no key.
            # The current array[index] from the parent frame is already used
            # in _current_prefix() so fields inside this object will be
            # labelled disks[N].field correctly.
            stack.append({"type": "object", "key": ""})
            _reset_buffer()
            continue

        # ----------------------------------------------------------------
        # key: { — nested object
        # ----------------------------------------------------------------
        obj_m = _OBJECT_OPEN_RE.match(stripped)
        if obj_m:
            key = _extract_key(obj_m)
            # Push object scope; comment buffer is for the object itself —
            # reset it since objects don't emit a leaf Prompt.
            stack.append({"type": "object", "key": key})
            _reset_buffer()
            continue

        # ----------------------------------------------------------------
        # key: [ — array
        # ----------------------------------------------------------------
        arr_m = _ARRAY_OPEN_RE.match(stripped)
        if arr_m:
            key = _extract_key(arr_m)
            stack.append({"type": "array", "key": key, "index": 0})
            _reset_buffer()
            continue

        # ----------------------------------------------------------------
        # Detect inline single-line array: key: [val, val, ...]
        # ----------------------------------------------------------------
        # This handles lines like: fallback_codecs: ["av1"],
        # We treat the whole array literal as the default_value for one Prompt.
        inline_arr_re = re.compile(
            r"""
            ^
            (?:"([^"]+)"|'([^']+)'|([a-zA-Z_][a-zA-Z0-9_]*))
            \s*:\s*
            (\[.*\])
            ,?\s*$
            """,
            re.VERBOSE,
        )
        inline_arr_m = inline_arr_re.match(stripped)
        if inline_arr_m:
            key = inline_arr_m.group(1) or inline_arr_m.group(2) or inline_arr_m.group(3)
            raw_value = inline_arr_m.group(4).strip()
            prefix = _current_prefix()
            full_path = f"{prefix}.{key}" if prefix else key
            comment = _flush_comment()
            prompts.append(Prompt(key_path=full_path, comment=comment, default_value=raw_value))
            continue

        # ----------------------------------------------------------------
        # key: value — leaf scalar
        # ----------------------------------------------------------------
        kv_m = _KEY_VALUE_RE.match(stripped)
        if kv_m:
            key = _extract_key(kv_m)
            raw_value = kv_m.group(4).strip()

            prefix = _current_prefix()
            full_path = f"{prefix}.{key}" if prefix else key

            comment = _flush_comment()
            prompts.append(Prompt(key_path=full_path, comment=comment, default_value=raw_value))
            continue

        # ----------------------------------------------------------------
        # Any other line (e.g. bare array element value, closing braces
        # already handled above) — reset comment buffer
        # ----------------------------------------------------------------
        _reset_buffer()

    return prompts
