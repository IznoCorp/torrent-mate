"""Guard: every v1 use case taking an actor authorises it through ``@requires``.

Every public method of an ``AppServices`` field's class whose first parameter after
``self`` is annotated ``Actor`` carries :func:`~personalscraper.app.accounts.authorise.requires`,
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
from typing import Any

from personalscraper.app import services as services_module
from personalscraper.app.accounts.actor import Actor
from personalscraper.app.accounts.authorise import requires
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


def _service_classes() -> list[type]:
    """The classes of ``AppServices``' fields, ``X | None`` unwrapped.

    Returns:
        Each class once, in field order.
    """
    hints = typing.get_type_hints(AppServices, localns=_type_checking_names(services_module))
    classes: list[type] = []
    for hint in hints.values():
        args = typing.get_args(hint) if isinstance(hint, types.UnionType) else (hint,)
        for arg in args:
            if isinstance(arg, type) and arg is not type(None) and arg not in classes:
                classes.append(arg)
    return classes


def _takes_actor(method: Any) -> bool:
    """Whether a method's first parameter after ``self`` is annotated ``Actor``.

    Args:
        method: The function, as the class holds it.

    Returns:
        True when it takes an actor.
    """
    parameters = list(inspect.signature(method).parameters.values())
    return len(parameters) > 1 and parameters[1].annotation in (Actor, "Actor")


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
