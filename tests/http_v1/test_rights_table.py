"""``OPERATION_RIGHTS`` names every contract operation, and asks what the contract's ``x-rights`` asks.

The source was the maquette's ``mocks/operation-rights.ts`` while the contract declared
no per-operation right (gap G-2); once one contract operation carries ``x-rights``, the
contract is read instead. This table replaces v0's
``tests/unit/web/routes/test_staging_write_policy.py`` as the policy table.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from _repo_paths import CONTRACT, DESIGN_SRC

from personalscraper.app.accounts.rights import AnyOf, Public, Requirement, Right, SignedIn, holds
from personalscraper.http_v1.rights import OPERATION_RIGHTS, OWN_SCOPED, PENDING_OPERATIONS

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONTRACT = CONTRACT
_MAQUETTE_TABLE = DESIGN_SRC / "mocks" / "operation-rights.ts"
_WRITE_METHODS = frozenset({"post", "put", "patch", "delete"})

#: The ruled corrections to the source's ``null`` (DESIGN C.6): the sign-in
#: operations ask no session; the account's own writes (notification choices and
#: devices, its password, its seen mark on a closed tunnel) are refused on a
#: read-only instance (2026-10-03: no right, but a write).
_OVERRIDES: dict[str, Requirement] = {
    "signIn": Public(),
    "signInWithPlex": Public(),
    "startPlexSignIn": Public(),
    "updateNotificationPreference": SignedIn(write=True),
    "registerPushDevice": SignedIn(write=True),
    "changeOwnPassword": SignedIn(write=True),
    "dismissClosure": SignedIn(write=True),
}

_ENTRY = re.compile(r'^  (\w+): (null|"[^"]+"|\[[^\]]*\]|[A-Z_]+),', re.MULTILINE)
_CONSTANT = re.compile(r"^const ([A-Z_]+): readonly Right\[\] = (\[[^\]]*\]);", re.MULTILINE)
_OWN_SCOPED = re.compile(r"OWN_SCOPED: ReadonlySet<string> = new Set\((\[[^\]]*\])\)", re.MULTILINE)


def _contract_operations() -> dict[str, dict[str, Any]]:
    """Read every operation of the contract, keyed by operationId.

    Returns:
        ``operationId`` → ``{"method": …, "operation": …}``.
    """
    document = json.loads(_CONTRACT.read_text(encoding="utf-8"))
    operations: dict[str, dict[str, Any]] = {}
    for item in document["paths"].values():
        for method, operation in item.items():
            if isinstance(operation, dict) and "operationId" in operation:
                operations[operation["operationId"]] = {"method": method, "operation": operation}
    return operations


def _requirement(asked: None | str | list[str]) -> Requirement:
    """Translate one table value into a requirement.

    Args:
        asked: ``None`` (a session act), a right, or a list (any of).

    Returns:
        The requirement.
    """
    if asked is None:
        return SignedIn()
    if isinstance(asked, str):
        return holds(Right(asked))
    return AnyOf(frozenset(Right(right) for right in asked))


def _maquette_table() -> dict[str, Requirement]:
    """Parse the maquette's ``OPERATION_RIGHTS``, its constants resolved.

    Returns:
        ``operationId`` → requirement, before the ruled overrides.
    """
    source = _MAQUETTE_TABLE.read_text(encoding="utf-8")
    constants = {name: json.loads(value) for name, value in _CONSTANT.findall(source)}
    table: dict[str, Requirement] = {}
    for operation_id, raw in _ENTRY.findall(source):
        value = constants[raw] if raw in constants else json.loads(raw)
        table[operation_id] = _requirement(value)
    return table


def _expected_table() -> dict[str, Requirement]:
    """The table v1 must hold: the contract's ``x-rights`` once any carries one, else the maquette's.

    Returns:
        ``operationId`` → requirement, the ruled overrides applied.
    """
    operations = _contract_operations()
    if any("x-rights" in entry["operation"] for entry in operations.values()):
        expected = {op: _requirement(entry["operation"].get("x-rights")) for op, entry in operations.items()}
    else:
        expected = _maquette_table()
    expected.update(_OVERRIDES)
    return expected


def test_keys_are_the_contract_operations_and_the_pending_ones() -> None:
    """Every contract operation is named, and nothing else but the pending ones."""
    assert set(OPERATION_RIGHTS) == set(_contract_operations()) | PENDING_OPERATIONS
    assert not PENDING_OPERATIONS & set(_contract_operations()), "a pending operation reached the contract"


def test_the_maquette_table_parses_whole() -> None:
    """The parser reads every maquette entry (a silent regex miss would empty the comparison)."""
    assert set(_maquette_table()) == set(_contract_operations())


def test_overrides_correct_a_null() -> None:
    """A ruled override replaces a session act (``null``), never a right."""
    maquette = _maquette_table()

    assert all(maquette[operation_id] == SignedIn() for operation_id in _OVERRIDES)


@pytest.mark.parametrize("operation_id", sorted(_expected_table()))
def test_entry_equals_the_source(operation_id: str) -> None:
    """Each entry asks exactly what its source asks."""
    assert OPERATION_RIGHTS[operation_id] == _expected_table()[operation_id]


def test_sign_in_start_is_public() -> None:
    """``startPlexSignIn`` asks no session, and no operation is pending since gap G-4 closed."""
    assert PENDING_OPERATIONS == frozenset()
    assert OPERATION_RIGHTS["startPlexSignIn"] == Public()


def test_a_write_names_exactly_one_right() -> None:
    """A write names one right, so a ceiling subtracts it by name; own-or-any piloting excepted."""
    pilot = frozenset({Right.ACQUISITION_PILOT_OWN, Right.ACQUISITION_PILOT_ANY})
    offenders = [
        operation_id
        for operation_id, entry in _contract_operations().items()
        if entry["method"] in _WRITE_METHODS
        and isinstance(OPERATION_RIGHTS[operation_id], AnyOf)
        and len(OPERATION_RIGHTS[operation_id].rights) > 1  # type: ignore[union-attr]
        and OPERATION_RIGHTS[operation_id].rights != pilot  # type: ignore[union-attr]
    ]

    assert offenders == []


def test_own_scoped_equals_the_maquette() -> None:
    """The operations whose target decides « own or any » are the maquette's seven."""
    match = _OWN_SCOPED.search(_MAQUETTE_TABLE.read_text(encoding="utf-8"))
    assert match is not None

    # The TypeScript list ends with a trailing comma, which JSON refuses.
    assert frozenset(json.loads(re.sub(r",\s*\]", "]", match.group(1)))) == OWN_SCOPED
    assert len(OWN_SCOPED) == 7


def test_right_is_the_contract_enum() -> None:
    """``Right`` holds the contract's rights, member for member: a retired right is no member."""
    document = json.loads(_CONTRACT.read_text(encoding="utf-8"))

    assert sorted(Right) == sorted(document["components"]["schemas"]["Right"]["enum"])
