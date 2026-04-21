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

    Limitations (by design — fits the well-formed, human-edited example file):
    - String values containing ``{``, ``}``, ``[``, or ``]`` would confuse the
      depth counter; the example file does not have such values.
    - Inline ``/* */`` on the same line as a key is not detected as a block
      comment; the example file does not do this.
    - Array elements that are plain scalars (not objects) each emit one Prompt.
      Array elements that are objects emit Prompts per field within that object.
"""

from dataclasses import dataclass
from pathlib import Path


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
            delimiters and leading/trailing whitespace.
        default_value: The raw JSON5 value literal as it appears in the source
            (e.g. ``'"hevc"'``, ``'true'``, ``'["fra", "eng"]'``).
    """

    key_path: str
    comment: str
    default_value: str


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
    # Stub — full implementation in sub-phase 3.3.
    return []
