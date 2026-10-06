"""Guard: every v1 use case taking an actor authorises it through ``@requires``.

Every public method of an ``AppServices`` field's class whose first parameter after
``self`` is named ``actor`` (whatever its annotation) carries :func:`~personalscraper.app.accounts.authorise.requires`,
and the operation it names is a key of ``OPERATION_RIGHTS``. The services are found by
introspecting ``AppServices``' fields, so a new service is covered without being named here.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import types
import typing
from pathlib import Path
from typing import Any, Optional

import pytest

from personalscraper.app import services as services_module
from personalscraper.app.accounts.actor import Actor
from personalscraper.app.accounts.authorise import _ACTOR_PARAMETER, requires
from personalscraper.app.accounts.requirements import OPERATION_RIGHTS
from personalscraper.app.services import AppServices


def _type_checking_names(module: types.ModuleType) -> dict[str, Any]:
    """Import the names a module imports only under ``if TYPE_CHECKING:``.

    ``AppServices`` names some field types there (to break an import cycle), so its hints
    resolve only with them.

    Args:
        module: The module whose source is read.

    Returns:
        Each such name, bound to the object it imports.
    """
    tree = ast.parse(Path(inspect.getfile(module)).read_text(encoding="utf-8"))
    names: dict[str, Any] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.If) and isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING"):
            continue
        for statement in node.body:
            if isinstance(statement, ast.ImportFrom) and statement.module is not None:
                imported = importlib.import_module(statement.module)
                for alias in statement.names:
                    names[alias.asname or alias.name] = getattr(imported, alias.name)
    return names


def _service_classes(hints: dict[str, Any] | None = None) -> list[type]:
    """The classes of ``AppServices``' fields, ``X | None`` and ``Optional[X]`` unwrapped.

    Args:
        hints: The field hints to read; ``AppServices``' own, resolved, when omitted.

    Returns:
        Each class once, in field order.

    Raises:
        AssertionError: when a field resolves to no class (a generic, a union of several
            classes, ...): it would otherwise escape the guard in silence.
    """
    if hints is None:
        hints = typing.get_type_hints(AppServices, localns=_type_checking_names(services_module))
    classes: list[type] = []
    for field, hint in hints.items():
        is_union = typing.get_origin(hint) in (typing.Union, types.UnionType)
        members = [arg for arg in typing.get_args(hint) if arg is not type(None)] if is_union else [hint]
        if len(members) != 1 or not isinstance(members[0], type):
            raise AssertionError(f"AppServices.{field} ({hint!r}) resolves to no class: the guard cannot read it")
        if members[0] not in classes:
            classes.append(members[0])
    return classes


def _takes_actor(method: Any) -> bool:
    """Whether a method's first parameter after ``self`` is named ``actor``.

    The name, not the annotation, is the rule :func:`requires` applies, so ``Actor | None``,
    ``Optional[Actor]`` and no annotation at all are covered too.

    Args:
        method: The function, as the class holds it.

    Returns:
        True when it takes an actor.
    """
    parameters = list(inspect.signature(method).parameters.values())
    return len(parameters) > 1 and parameters[1].name == _ACTOR_PARAMETER


def _unauthorised(cls: type) -> list[str]:
    """The public actor-taking methods of a class that ``@requires`` does not guard.

    Args:
        cls: The service class.

    Returns:
        ``Class.method`` for each method that carries no ``@requires``, or names an
        operation ``OPERATION_RIGHTS`` does not hold.
    """
    flagged: list[str] = []
    for name, method in inspect.getmembers(cls, inspect.isfunction):
        if name.startswith("_") or not _takes_actor(method):
            continue
        if getattr(method, "__requires__", None) not in OPERATION_RIGHTS:
            flagged.append(f"{cls.__name__}.{name}")
    return flagged


def test_every_actor_taking_service_method_carries_requires() -> None:
    """No public use case of an ``AppServices`` service skips the authorisation of its actor."""
    classes = _service_classes()
    guarded = [
        name
        for cls in classes
        for name, method in inspect.getmembers(cls, inspect.isfunction)
        if not name.startswith("_") and _takes_actor(method)
    ]

    assert guarded, "the guard found no actor-taking method: its introspection is broken"
    assert [flagged for cls in classes for flagged in _unauthorised(cls)] == []


def test_a_planted_undecorated_actor_method_is_flagged() -> None:
    """POSITIVE control: an actor-taking method without ``@requires`` is caught; a decorated one is not."""

    class Planted:
        """A service with one guarded and one unguarded use case."""

        @requires("readAccount")
        def guarded(self, actor: Actor) -> None:
            """A use case authorised by ``@requires``."""

        def unguarded(self, actor: Actor) -> None:
            """A use case that forgot its authorisation."""

        def _private(self, actor: Actor) -> None:
            """A helper: never a use case."""

    assert _unauthorised(Planted) == ["Planted.unguarded"]


def test_a_planted_actor_parameter_is_flagged_whatever_its_annotation() -> None:
    """POSITIVE control: an undecorated ``actor`` parameter is caught when it is not annotated ``Actor``."""

    class Planted:
        """A service whose use cases annotate their actor loosely, or not at all."""

        def optional_union(self, actor: Actor | None) -> None:
            """Takes ``Actor | None``."""

        def optional_typing(self, actor: Actor | None) -> None:
            """Takes ``Optional[Actor]``."""

        def unannotated(self, actor) -> None:  # type: ignore[no-untyped-def]
            """Takes an unannotated actor."""

        def other_first_parameter(self, name: str, actor: Actor) -> None:
            """Takes its actor second: ``@requires`` would refuse it, so it is no use case."""

    assert _unauthorised(Planted) == [
        "Planted.optional_typing",
        "Planted.optional_union",
        "Planted.unannotated",
    ]


def test_a_planted_optional_service_field_is_seen() -> None:
    """POSITIVE control: a ``typing.Optional[X]`` field is unwrapped to its class, not dropped."""

    class PlantedService:
        """A service held by an optional field."""

    assert _service_classes({"planted": Optional[PlantedService]}) == [PlantedService]
    assert _service_classes({"planted": PlantedService | None}) == [PlantedService]


def test_a_field_resolving_to_no_class_fails_the_guard_by_name() -> None:
    """POSITIVE control: a generic field is never skipped in silence; the guard names it."""
    with pytest.raises(AssertionError, match="planted_generic"):
        _service_classes({"planted_generic": list[int]})
