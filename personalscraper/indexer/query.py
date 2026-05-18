"""Indexer flex-attr query parser (DESIGN §13, §13.1).

Tokenises a query string into :class:`Token` objects, looks each field up in
:data:`FIELD_REGISTRY`, composes a single ``WHERE`` clause via ``AND``
conjunction, and executes it against the indexer SQLite database.

Public API
----------
- :data:`FIELD_REGISTRY` — maps every recognised field to its :class:`FieldSpec`.
- :class:`QueryError` — raised for unknown fields, invalid operators, syntax errors.
- :func:`execute` — tokenise → compile → execute SQL → return rows.
- :func:`find_items_without_trailer` — named query: items with no ``trailer_found`` attribute.

Token syntax
------------
- ``field:value``       — equality or LIKE (depending on field type).
- ``field:value*``      — prefix match (LIKE 'value%').
- ``-field:value``      — negation.
- ``field:>=N``         — numeric comparison (≥, ≤, >, <).
- ``"quoted phrase"``   — bare title fragment with exact LIKE matching (no auto-%).
- bare term             — title fragment (auto-wrapped with % for LIKE).
- ``-bare_key``         — bare-key flex-attr presence negation.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from personalscraper.indexer.schema import MediaItemRow

# ---------------------------------------------------------------------------
# QueryError — raised by the query parser for unknown fields / syntax errors
# ---------------------------------------------------------------------------


class QueryError(ValueError):
    """Raised by :func:`execute` when the query string is invalid.

    Args:
        message: Human-readable error description, e.g.
            ``"unknown field 'foo'; recognised fields: kind, title, year, ..."``.
    """

    def __init__(self, message: str) -> None:
        """Initialize with an actionable error message."""
        super().__init__(message)


# ---------------------------------------------------------------------------
# FieldType — governs how a field's value is coerced and what operators apply
# ---------------------------------------------------------------------------


class FieldType(Enum):
    """Declares the coercion strategy and allowed operators for a field.

    Attributes:
        STR: String equality (or LIKE for title).
        INT: Integer with optional comparison operator (=, >=, <=, >, <).
        EXISTS_VIDEO_CODEC: EXISTS sub-query on media_stream.codec for video streams.
        EXISTS_AUDIO_LANG: EXISTS sub-query on media_stream.lang for audio streams.
        EXISTS_RELEASE_QUALITY: EXISTS sub-query on media_release.quality.
        DISK_JOIN: JOIN on disk.label.
        FLEX: Flex-attribute (item_attribute table); equality and presence only.
    """

    STR = auto()
    INT = auto()
    EXISTS_VIDEO_CODEC = auto()
    EXISTS_AUDIO_LANG = auto()
    EXISTS_RELEASE_QUALITY = auto()
    DISK_JOIN = auto()
    FLEX = auto()


# ---------------------------------------------------------------------------
# FieldSpec — one entry in FIELD_REGISTRY
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FieldSpec:
    """Describes how to resolve a query field to SQL.

    Args:
        column: SQLite column expression (e.g. ``'media_item.kind'``), or ``None``
            for complex EXISTS fields that handle their own SQL generation.
        field_type: Coercion + operator strategy for this field.
        allowed_values: If non-empty, ``QueryError`` is raised when the supplied
            value is not in this set (e.g. ``nfo_status`` must be one of three).
    """

    column: str | None
    field_type: FieldType
    allowed_values: frozenset[str] = frozenset()


# ---------------------------------------------------------------------------
# FIELD_REGISTRY — maps each recognised field name to its FieldSpec
# ---------------------------------------------------------------------------

FIELD_REGISTRY: dict[str, FieldSpec] = {
    "kind": FieldSpec(column="media_item.kind", field_type=FieldType.STR),
    "title": FieldSpec(column="media_item.title", field_type=FieldType.STR),
    "year": FieldSpec(column="media_item.year", field_type=FieldType.INT),
    "disk": FieldSpec(column="disk.label", field_type=FieldType.DISK_JOIN),
    "category": FieldSpec(column="media_item.category_id", field_type=FieldType.STR),
    # provider-ids feature : legacy flat ID columns replaced by JSON path.
    "tmdb_id": FieldSpec(
        column="json_extract(media_item.external_ids_json, '$.tmdb.series_id')",
        field_type=FieldType.STR,
    ),
    "imdb_id": FieldSpec(
        column="json_extract(media_item.external_ids_json, '$.imdb.series_id')",
        field_type=FieldType.STR,
    ),
    "tvdb_id": FieldSpec(
        column="json_extract(media_item.external_ids_json, '$.tvdb.series_id')",
        field_type=FieldType.STR,
    ),
    "nfo": FieldSpec(
        column="media_item.nfo_status",
        field_type=FieldType.STR,
        allowed_values=frozenset({"missing", "invalid", "valid"}),
    ),
    "codec": FieldSpec(column=None, field_type=FieldType.EXISTS_VIDEO_CODEC),
    "lang": FieldSpec(column=None, field_type=FieldType.EXISTS_AUDIO_LANG),
    "quality": FieldSpec(column=None, field_type=FieldType.EXISTS_RELEASE_QUALITY),
}

# Sorted list of recognised field names for error messages.
_KNOWN_FIELDS: list[str] = sorted(FIELD_REGISTRY)


# ---------------------------------------------------------------------------
# Token — result of the tokeniser
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Token:
    """One parsed token from the query string.

    Args:
        field: Field name, e.g. ``'year'`` or ``'codec'``; ``None`` for bare title terms.
        value: String value as it appears in the query (before coercion).
        operator: Comparison operator string: ``'='``, ``'>='``, ``'<='``, ``'>'``,
            ``'<'``; always ``'='`` for non-INT fields.
        negate: True when the token was prefixed with ``-``.
        prefix: True when the value ends with ``*`` (stripped before storage here).
        bare_key: True when a bare ``-field`` (no colon) was given; implies presence-
            negation on a flex attribute. Only set when ``field`` is not ``None`` and
            ``value`` is ``None``.
    """

    field: str | None
    value: str | None
    operator: str = "="
    negate: bool = False
    prefix: bool = False
    bare_key: bool = False


# ---------------------------------------------------------------------------
# Tokeniser
# ---------------------------------------------------------------------------

# Matches the components of a single token:
#   Group 1 (negate):     optional leading dash
#   Group 2 (field):      optional word characters before colon (field name)
#   Group 3 (colon):      literal colon (present only when a field name was found)
#   Group 4 (operator):   optional comparison operator (>=, <=, >, <)
#   Group 5 (value):      the value — either "quoted phrase" or bare token*
_TOKEN_RE = re.compile(
    r"""
    (-)?                        # optional negation prefix
    ([A-Za-z_][A-Za-z0-9_]*)?  # optional field name
    (:)?                        # optional colon separator
    (>=|<=|>|<)?                # optional numeric comparison operator
    (?:
        "([^"]*)"               # quoted phrase (group 5a)
        |
        ([^\s"]*)               # bare value, may end with * (group 5b)
    )
    """,
    re.VERBOSE,
)


def _tokenise(query_str: str) -> list[Token]:
    """Split *query_str* into a list of :class:`Token` objects.

    Handles: ``field:value``, ``field:value*``, ``-field:value``,
    ``field:>=N``, ``"quoted phrase"``, bare terms, ``-bare_key``.

    Args:
        query_str: Raw query string from the user.

    Returns:
        Ordered list of :class:`Token` instances; empty list for empty input.

    Raises:
        QueryError: For unrecoverable syntax errors (e.g. a colon with no field name
            where one is required, or an operator on a quoted value).
    """
    tokens: list[Token] = []
    # Walk over non-whitespace chunks; quoted phrases can contain spaces so we
    # scan character-by-character rather than splitting on whitespace.
    pos = 0
    s = query_str.strip()
    while pos < len(s):
        # Skip leading whitespace.
        while pos < len(s) and s[pos].isspace():
            pos += 1
        if pos >= len(s):
            break

        # --- Quoted phrase (bare title fragment in quotes) ---
        if s[pos] == '"':
            end = s.find('"', pos + 1)
            if end == -1:
                raise QueryError(f"Unclosed quote in query: {s[pos:]!r}")
            phrase = s[pos + 1 : end]
            tokens.append(Token(field=None, value=phrase, operator="=", negate=False, prefix=False))
            pos = end + 1
            continue

        # --- Regular token: read up to next whitespace ---
        end = pos
        while end < len(s) and not s[end].isspace():
            # A quote inside a token ends the token (e.g. field:"val ue")
            if s[end] == '"':
                break
            end += 1

        chunk = s[pos:end]
        pos = end

        if not chunk:
            continue

        tok = _parse_chunk(chunk)
        tokens.append(tok)

    return tokens


def _parse_chunk(chunk: str) -> Token:
    """Parse a single non-whitespace chunk into a :class:`Token`.

    Args:
        chunk: A single whitespace-delimited chunk from the query string,
            e.g. ``'year:>=2020'``, ``'-nfo:valid'``, ``'hevc'``, ``'-trailer_found'``.

    Returns:
        A :class:`Token` representing this chunk.

    Raises:
        QueryError: On unrecoverable syntax errors.
    """
    negate = chunk.startswith("-")
    if negate:
        chunk = chunk[1:]

    # Bare key (no colon): e.g. ``hevc`` or ``-trailer_found``.
    if ":" not in chunk:
        # A bare negated key is a flex-attr presence check.
        if negate:
            return Token(field=chunk, value=None, negate=True, bare_key=True)
        # A bare positive term is a title fragment.
        prefix = chunk.endswith("*")
        value = chunk.rstrip("*") if prefix else chunk
        return Token(field=None, value=value, negate=False, prefix=prefix)

    field, rest = chunk.split(":", 1)
    if not field:
        raise QueryError(f"Token {chunk!r} has a colon but no field name.")

    # Extract optional comparison operator.
    operator = "="
    for op in (">=", "<=", ">", "<"):
        if rest.startswith(op):
            operator = op
            rest = rest[len(op) :]
            break

    # Handle quoted value within field:value context (field:"val ue" collapsed earlier).
    if rest.startswith('"') and rest.endswith('"') and len(rest) >= 2:
        value = rest[1:-1]
        return Token(field=field, value=value, operator=operator, negate=negate, prefix=False)

    prefix = rest.endswith("*")
    value = rest.rstrip("*") if prefix else rest

    return Token(field=field, value=value, operator=operator, negate=negate, prefix=prefix)


# ---------------------------------------------------------------------------
# SQL fragment composer
# ---------------------------------------------------------------------------

# Base SELECT for all queries — we always JOIN disk and path to support disk: filter.
# The JOIN to path+disk is LEFT JOIN so items with no associated path (edge cases)
# still appear when the query does not filter on disk.
_BASE_SELECT = (
    "SELECT DISTINCT "
    "media_item.id, media_item.kind, media_item.title, media_item.title_sort, "
    "media_item.original_title, media_item.year, media_item.category_id, "
    "media_item.external_ids_json, media_item.ratings_json, media_item.canonical_provider, "
    "media_item.nfo_status, media_item.artwork_json, "
    "media_item.date_created, media_item.date_modified, "
    "media_item.date_metadata_refreshed, media_item.is_locked, media_item.preferred_lang "
    "FROM media_item "
    "LEFT JOIN media_release ON media_release.item_id = media_item.id "
    "LEFT JOIN media_file ON media_file.release_id = media_release.id "
    "LEFT JOIN path ON path.id = media_file.path_id "
    "LEFT JOIN disk ON disk.id = path.disk_id"
)


def _compile_token(
    token: Token,
    params: list[Any],
) -> str:
    """Compile one :class:`Token` into a SQL WHERE fragment.

    Appends bind parameters to *params* in place and returns the fragment string.

    Args:
        token: The parsed token to compile.
        params: Mutable list; positional bind parameters are appended here.

    Returns:
        A SQL boolean expression suitable for use in a WHERE clause.

    Raises:
        QueryError: For unknown fields, invalid operators, disallowed values, or
            numeric comparisons on untyped flex attributes.
    """
    # Bare title fragment (no field).
    if token.field is None:
        assert token.value is not None
        like_val = f"%{token.value}%"
        params.append(like_val)
        frag = "media_item.title LIKE ?"
        return f"NOT ({frag})" if token.negate else frag

    field = token.field

    # Bare-key flex-attr presence negation: -trailer_found
    if token.bare_key:
        assert token.negate
        params.append(field)
        return "NOT EXISTS (SELECT 1 FROM item_attribute ia_bk WHERE ia_bk.item_id = media_item.id AND ia_bk.key = ?)"

    # Look up field in registry.
    if field not in FIELD_REGISTRY:
        # Treat as flex-attr equality / prefix / presence.
        return _compile_flex_token(field, token, params)

    spec = FIELD_REGISTRY[field]
    value = token.value
    assert value is not None, f"Token for known field {field!r} has no value — should not happen."

    # Validate allowed_values constraint.
    if spec.allowed_values and value not in spec.allowed_values:
        allowed = ", ".join(sorted(spec.allowed_values))
        raise QueryError(f"Field '{field}' only accepts values: {allowed}; got {value!r}.")

    # --- STR fields ---
    if spec.field_type == FieldType.STR:
        if token.operator != "=":
            raise QueryError(
                f"Field '{field}' is a string field; comparison operator '{token.operator}' is not allowed."
            )
        col = spec.column
        assert col is not None
        if field == "title":
            # Title: auto-wrap with % unless the token was a quoted phrase.
            if token.prefix:
                like_val = f"{value}%"
            else:
                like_val = f"%{value}%"
            params.append(like_val)
            frag = f"{col} LIKE ?"
        else:
            params.append(value)
            frag = f"{col} = ?"
        return f"NOT ({frag})" if token.negate else frag

    # --- INT fields ---
    if spec.field_type == FieldType.INT:
        try:
            int_val = int(value)
        except ValueError:
            raise QueryError(f"Field '{field}' is an integer field; got non-integer value {value!r}.")
        params.append(int_val)
        col = spec.column
        assert col is not None
        frag = f"{col} {token.operator} ?"
        return f"NOT ({frag})" if token.negate else frag

    # --- DISK_JOIN ---
    if spec.field_type == FieldType.DISK_JOIN:
        if token.operator != "=":
            raise QueryError(
                f"Field '{field}' is a string field; comparison operator '{token.operator}' is not allowed."
            )
        params.append(value)
        # The disk table is already LEFT JOINed in _BASE_SELECT.
        frag = "disk.label = ?"
        return f"NOT ({frag})" if token.negate else frag

    # --- EXISTS fields (codec, lang, quality) ---
    if spec.field_type == FieldType.EXISTS_VIDEO_CODEC:
        if token.operator != "=":
            raise QueryError(f"Field 'codec' only supports equality; got operator '{token.operator}'.")
        params.append(value)
        frag = (
            "EXISTS ("
            "SELECT 1 FROM media_stream s_codec "
            "JOIN media_file f_codec ON s_codec.file_id = f_codec.id "
            "JOIN media_release r_codec ON f_codec.release_id = r_codec.id "
            "WHERE r_codec.item_id = media_item.id "
            "AND s_codec.kind = 'video' AND s_codec.codec = ?"
            ")"
        )
        return f"NOT {frag}" if token.negate else frag

    if spec.field_type == FieldType.EXISTS_AUDIO_LANG:
        if token.operator != "=":
            raise QueryError(f"Field 'lang' only supports equality; got operator '{token.operator}'.")
        params.append(value)
        frag = (
            "EXISTS ("
            "SELECT 1 FROM media_stream s_lang "
            "JOIN media_file f_lang ON s_lang.file_id = f_lang.id "
            "JOIN media_release r_lang ON f_lang.release_id = r_lang.id "
            "WHERE r_lang.item_id = media_item.id "
            "AND s_lang.kind = 'audio' AND s_lang.lang = ?"
            ")"
        )
        return f"NOT {frag}" if token.negate else frag

    if spec.field_type == FieldType.EXISTS_RELEASE_QUALITY:
        if token.operator != "=":
            raise QueryError(f"Field 'quality' only supports equality; got operator '{token.operator}'.")
        params.append(value)
        frag = (
            "EXISTS (SELECT 1 FROM media_release mr_qual WHERE mr_qual.item_id = media_item.id AND mr_qual.quality = ?)"
        )
        return f"NOT {frag}" if token.negate else frag

    # Should never reach here — all FieldType variants handled above.
    raise QueryError(f"Unhandled field type for '{field}': {spec.field_type!r}.")  # pragma: no cover


def _compile_flex_token(field: str, token: Token, params: list[Any]) -> str:
    """Compile a token whose field is not in :data:`FIELD_REGISTRY` as a flex-attr lookup.

    Per DESIGN §13.1:
    - Equality: ``EXISTS (... key=? AND value=?)``
    - Prefix: not supported on flex attrs (text-only storage) → ``QueryError``.
    - Numeric comparison: not supported on untyped flex attrs → ``QueryError``.
    - Presence (bare key or ``field:*``): ``EXISTS (... key=?)`` with no value check.

    Args:
        field: The unrecognised field name (becomes the ``key`` in ``item_attribute``).
        token: Full parsed token.
        params: Mutable list; bind parameters appended in place.

    Returns:
        A SQL boolean expression.

    Raises:
        QueryError: For numeric comparisons or prefix matches on flex attrs.
    """
    if token.operator != "=":
        raise QueryError(
            f"Flex attribute '{field}' has no declared type; "
            f"can only test equality and presence (got operator '{token.operator}')."
        )

    value = token.value

    # Presence test: value is None (bare key), '*' alone, or empty value with prefix flag
    # (field:* tokenises as value='' prefix=True).
    if value is None or value == "*" or (token.prefix and value == ""):
        params.append(field)
        frag = "EXISTS (SELECT 1 FROM item_attribute ia_pres WHERE ia_pres.item_id = media_item.id AND ia_pres.key = ?)"
        return f"NOT {frag}" if token.negate else frag

    # Prefix match on flex attr (non-empty value with *) is unsupported.
    if token.prefix:
        raise QueryError(f"Flex attribute '{field}' does not support prefix match ('*'); only equality is allowed.")

    # Equality.
    params.extend([field, value])
    frag = (
        "EXISTS ("
        "SELECT 1 FROM item_attribute ia_eq "
        "WHERE ia_eq.item_id = media_item.id AND ia_eq.key = ? AND ia_eq.value = ?"
        ")"
    )
    return f"NOT {frag}" if token.negate else frag


def _build_sql(tokens: list[Token], limit: int) -> tuple[str, list[Any]]:
    """Compile a list of tokens into a full SQL SELECT statement.

    Each token contributes one WHERE fragment; fragments are joined with AND.
    When no tokens produce a WHERE clause the statement has no WHERE at all.

    Args:
        tokens: Parsed and validated list of :class:`Token` objects.
        limit: Maximum number of rows to return (LIMIT clause).

    Returns:
        A tuple of ``(sql_string, bind_params)``.

    Raises:
        QueryError: Propagated from :func:`_compile_token`.
    """
    params: list[Any] = []
    fragments: list[str] = []

    for tok in tokens:
        frag = _compile_token(tok, params)
        fragments.append(frag)

    where_clause = ""
    if fragments:
        where_clause = " WHERE " + " AND ".join(fragments)

    sql = f"{_BASE_SELECT}{where_clause} ORDER BY media_item.title_sort LIMIT ?"
    params.append(limit)
    return sql, params


# ---------------------------------------------------------------------------
# Row helper
# ---------------------------------------------------------------------------


def _row_to_media_item(row: sqlite3.Row) -> MediaItemRow:
    """Convert a ``sqlite3.Row`` that contains the ``media_item`` columns to a dataclass.

    Args:
        row: A row fetched with ``conn.row_factory = sqlite3.Row``.  Must
            expose the standard ``media_item`` column set.

    Returns:
        Populated :class:`~personalscraper.indexer.schema.MediaItemRow` instance.
    """
    return MediaItemRow(
        id=row["id"],
        kind=row["kind"],
        title=row["title"],
        title_sort=row["title_sort"],
        original_title=row["original_title"],
        year=row["year"],
        category_id=row["category_id"],
        external_ids_json=row["external_ids_json"],
        ratings_json=row["ratings_json"],
        canonical_provider=row["canonical_provider"],
        nfo_status=row["nfo_status"],
        artwork_json=row["artwork_json"],
        date_created=row["date_created"],
        date_modified=row["date_modified"],
        date_metadata_refreshed=row["date_metadata_refreshed"],
        is_locked=row["is_locked"],
        preferred_lang=row["preferred_lang"],
    )


# ---------------------------------------------------------------------------
# Public API — execute()
# ---------------------------------------------------------------------------


def execute(
    conn: sqlite3.Connection,
    query_str: str,
    limit: int = 50,
) -> list[MediaItemRow]:
    """Tokenise *query_str*, compile a WHERE clause, and return matching items.

    Implements the full flex-attr query parser: tokeniser → FIELD_REGISTRY lookup
    → SQL fragment composition → parameter binding → fetchall.

    Args:
        conn: Open, read-capable SQLite connection to the indexer database.
        query_str: Query string in the flex-attr syntax, e.g.
            ``'year:>=2020 disk:Disk1 -nfo:valid'``.
        limit: Maximum number of rows to return (default 50).

    Returns:
        List of :class:`~personalscraper.indexer.schema.MediaItemRow` instances,
        ordered by ``title_sort``, capped at *limit*.

    Raises:
        QueryError: When the query string contains an unknown field, disallowed
            value, unsupported operator on an untyped flex attr, or syntax error.
    """
    query_str = query_str.strip()

    # Validate unknown *known-looking* fields before tokenising to give a better
    # error message.  (We do this inside _compile_token but surface it early here.)
    tokens = _tokenise(query_str)

    # Detect unknown *native* fields: fields with colons that look like registry fields
    # but aren't — these get routed to flex-attr, which is fine per the spec.
    # The only hard error is an invalid operator on a flex attr (handled in _compile_flex_token).

    sql, params = _build_sql(tokens, limit)

    prev_factory = conn.row_factory
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.row_factory = prev_factory

    return [_row_to_media_item(row) for row in rows]


# ---------------------------------------------------------------------------
# Named queries
# ---------------------------------------------------------------------------


def find_items_without_trailer(conn: sqlite3.Connection) -> list[MediaItemRow]:
    """Return all media items that have no ``trailer_found`` attribute.

    Implemented via :data:`FIELD_REGISTRY` using the flex-attr presence-negation
    path (``-trailer_found``), which compiles to:
    ``NOT EXISTS (SELECT 1 FROM item_attribute WHERE item_id=media_item.id AND key='trailer_found')``.

    Args:
        conn: Open, read-capable SQLite connection to the indexer database.

    Returns:
        List of :class:`~personalscraper.indexer.schema.MediaItemRow` instances
        for every media item lacking a ``trailer_found`` attribute.  The list
        is ordered by ``media_item.title_sort`` for deterministic output.
    """
    return execute(conn, "-trailer_found", limit=10_000)
