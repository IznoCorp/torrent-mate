"""Every operation v1 serves is the contract's operation, checked field by field (DESIGN C.8, instrument 3).

The judge of every served v1 operation. An operation the contract declares and v1
does not serve yet is the register's business (``docs/reference/frontend-backend-demands-v1.md``),
never a failure here; an operation v1 serves is held to the contract strictly:

- ``address``   the same ``operationId``, method and path (parameter names included);
- ``status``    the same success statuses (X3);
- ``response``  each success body's property names and required set equal the contract's,
                at every depth (X2);
- ``enum``      every enum met on the way equal, member for member (X4);
- ``request``   the request body's presence, its required flag, its properties and
                required set equal the contract's;
- ``parameter`` the same path, query and header parameters, each equally required, each
                schema compared as the bodies are (its enum under ``enum``);
- ``refusal``   the refusal statuses equal the contract's: none missing, none it does not
                declare (DESIGN C.4: a lot never answers a status its operation does not declare);
- ``problem``   each refusal answers the contract's ``Problem``: the same property names,
                at least its required ones, and only refusal codes the contract declares (the
                contract's set is the whole interface's; v1's grows lot by lot);
- ``right``     the operation's ``OPERATION_RIGHTS`` entry asks what the contract's
                ``x-rights`` asks, the ruled overrides applied; an override stands only
                over a session act (``x-rights: null``).

Types are not compared: a JSON type comparison across a hand-written contract and a
generated document reports every nullable optional, and nullability is read off neither.

The served document is the committed ``frontend/openapi-v1.json``; one test proves it
equals what ``create_v1_app`` serves, so the parametrisation covers every served operation.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Final, Literal

import pytest
from fastapi import APIRouter, FastAPI

from personalscraper.app.accounts.rights import Requirement, Right, SignedIn, holds
from personalscraper.http_v1.app import _without_validation_answers, include_v1_router
from personalscraper.http_v1.contract import PROBLEM_RESPONSES, ContractModel
from personalscraper.http_v1.rights import OPERATION_RIGHTS
from tests.http_v1.test_rights_table import _OVERRIDES, _requirement

_REPO_ROOT: Final = Path(__file__).resolve().parents[2]
_CONTRACT: Final = _REPO_ROOT / "frontend" / "maquette" / "contract" / "openapi.json"
_SERVED: Final = _REPO_ROOT / "frontend" / "openapi-v1.json"
_METHODS: Final = ("get", "post", "put", "patch", "delete")
_NULL: Final = {"type": "null"}


@dataclass(frozen=True)
class Violation:
    """One way a served operation departs from the contract.

    Attributes:
        operation_id: The served operation.
        kind: Which check failed (the module docstring lists them).
        detail: Where, and what each side says.
    """

    operation_id: str
    kind: str
    detail: str


@dataclass(frozen=True)
class _Operation:
    """One operation of a document.

    Attributes:
        method: The HTTP method, upper case.
        path: The path below the document's root.
        body: The operation object.
    """

    method: str
    path: str
    body: dict[str, Any]


def _operations(document: dict[str, Any]) -> dict[str, _Operation]:
    """Read a document's operations, keyed by ``operationId``.

    Args:
        document: One OpenAPI document.

    Returns:
        ``operationId`` → the operation.
    """
    found: dict[str, _Operation] = {}
    for path, item in document.get("paths", {}).items():
        for method, operation in item.items():
            if method in _METHODS and isinstance(operation, dict) and "operationId" in operation:
                found[operation["operationId"]] = _Operation(method.upper(), path, operation)
    return found


class _SchemaDiff:
    """Compares one contract schema against one served schema, recording every difference."""

    def __init__(self, contract: dict[str, Any], served: dict[str, Any], operation_id: str) -> None:
        """Keep both documents, for their references.

        Args:
            contract: The contract document.
            served: The served document.
            operation_id: The operation the violations are recorded against.
        """
        self.contract = contract
        self.served = served
        self.operation_id = operation_id
        self.violations: list[Violation] = []
        self._seen: set[tuple[str, str]] = set()

    def _record(self, kind: str, detail: str) -> None:
        """Record one violation.

        Args:
            kind: The check that failed.
            detail: Where, and what each side says.
        """
        self.violations.append(Violation(self.operation_id, kind, detail))

    @staticmethod
    def _resolve(document: dict[str, Any], node: Any) -> tuple[Any, str]:
        """Follow a node's ``$ref`` chain.

        Args:
            document: The document the node belongs to.
            node: A schema, possibly a reference.

        Returns:
            The schema it designates, and the last reference followed (``""`` when none).
        """
        reference = ""
        while isinstance(node, dict) and isinstance(node.get("$ref"), str):
            reference = node["$ref"]
            target: Any = document
            for part in reference.removeprefix("#/").split("/"):
                target = target.get(part, {}) if isinstance(target, dict) else {}
            node = target
        return node, reference

    @classmethod
    def _normal(cls, document: dict[str, Any], node: Any) -> tuple[Any, str]:
        """Resolve a node and drop its nullability, which neither side's shape is judged on.

        Args:
            document: The document the node belongs to.
            node: A schema.

        Returns:
            The resolved schema, a union of one non-null member collapsed into it, and the
            last reference followed.
        """
        node, reference = cls._resolve(document, node)
        while isinstance(node, dict):
            for keyword in ("anyOf", "oneOf"):
                if keyword in node:
                    members = [member for member in node[keyword] if member != _NULL]
                    if len(members) == 1:
                        node, inner = cls._resolve(document, members[0])
                        reference = inner or reference
                        break
            else:
                return node, reference
        return node, reference

    def compare(self, contract_node: Any, served_node: Any, where: str, kind: str) -> None:
        """Compare two schemas, recursively.

        Args:
            contract_node: The contract's schema.
            served_node: The served schema.
            where: The dotted location, for the record.
            kind: The kind a shape difference is recorded under (``response`` or ``request``).
        """
        wanted, wanted_ref = self._normal(self.contract, contract_node)
        have, have_ref = self._normal(self.served, served_node)
        if wanted_ref and have_ref:
            if (wanted_ref, have_ref) in self._seen:
                return
            self._seen.add((wanted_ref, have_ref))
        if not isinstance(wanted, dict) or not isinstance(have, dict):
            if wanted != have:
                self._record(kind, f"{where}: the contract says {wanted!r}, v1 says {have!r}")
            return
        if "enum" in wanted or "enum" in have:
            missing = sorted(map(str, set(wanted.get("enum", [])) - set(have.get("enum", []))))
            extra = sorted(map(str, set(have.get("enum", [])) - set(wanted.get("enum", []))))
            if missing or extra:
                self._record("enum", f"{where}: v1 lacks {missing}, v1 adds {extra}")
        self._compare_object(wanted, have, where, kind)
        for keyword in ("items", "additionalProperties"):
            if isinstance(wanted.get(keyword), dict) or isinstance(have.get(keyword), dict):
                self.compare(
                    wanted.get(keyword), have.get(keyword), f"{where}{'[]' if keyword == 'items' else '{}'}", kind
                )
        for keyword in ("anyOf", "oneOf", "allOf"):
            if keyword in wanted or keyword in have:
                wanted_members, have_members = wanted.get(keyword, []), have.get(keyword, [])
                if len(wanted_members) != len(have_members):
                    self._record(
                        kind, f"{where}: {keyword} of {len(wanted_members)} in the contract, {len(have_members)} in v1"
                    )
                    continue
                for index, (one, other) in enumerate(zip(wanted_members, have_members, strict=True)):
                    self.compare(one, other, f"{where}<{keyword}{index}>", kind)

    def _compare_object(self, wanted: dict[str, Any], have: dict[str, Any], where: str, kind: str) -> None:
        """Compare two object schemas' property names and required sets, then each property.

        Args:
            wanted: The contract's resolved schema.
            have: The served resolved schema.
            where: The dotted location.
            kind: The kind a difference is recorded under.
        """
        if "properties" not in wanted and "properties" not in have:
            return
        wanted_names, have_names = set(wanted.get("properties", {})), set(have.get("properties", {}))
        if wanted_names != have_names:
            self._record(
                kind,
                f"{where}: v1 lacks {sorted(wanted_names - have_names)}, v1 adds {sorted(have_names - wanted_names)}",
            )
        wanted_required, have_required = set(wanted.get("required", [])), set(have.get("required", []))
        if wanted_required != have_required:
            self._record(
                kind,
                f"{where}: required {sorted(wanted_required)} in the contract, {sorted(have_required)} in v1",
            )
        for name in sorted(wanted_names & have_names):
            self.compare(wanted["properties"][name], have["properties"][name], f"{where}.{name}", kind)


def _json_schema(document: dict[str, Any], carrier: Any) -> Any:
    """The ``application/json`` schema of a response or a request body.

    Args:
        document: The document the carrier belongs to.
        carrier: A response or a request body object, possibly a reference.

    Returns:
        Its JSON schema, or ``None`` when it carries no JSON body.
    """
    carrier, _ = _SchemaDiff._resolve(document, carrier)
    if not isinstance(carrier, dict):
        return None
    return carrier.get("content", {}).get("application/json", {}).get("schema")


def _parameters(operation: dict[str, Any]) -> set[tuple[str, str, bool]]:
    """An operation's parameters as ``(in, name, required)``.

    Args:
        operation: One operation.

    Returns:
        Its parameters.
    """
    return {
        (parameter["in"], parameter["name"], bool(parameter.get("required", False)))
        for parameter in operation.get("parameters", [])
    }


def _parameter_schemas(document: dict[str, Any], operation: dict[str, Any]) -> dict[tuple[str, str], Any]:
    """An operation's parameter schemas, keyed by ``(in, name)``.

    Args:
        document: The document the operation belongs to.
        operation: One operation.

    Returns:
        Each parameter's schema (``None`` when it declares none).
    """
    schemas: dict[tuple[str, str], Any] = {}
    for parameter in operation.get("parameters", []):
        parameter, _ = _SchemaDiff._resolve(document, parameter)
        schemas[(parameter["in"], parameter["name"])] = parameter.get("schema")
    return schemas


def _expected_right(
    operation_id: str, operation: dict[str, Any], overrides: Mapping[str, Requirement]
) -> Requirement | None:
    """What the contract's ``x-rights`` asks, the ruled overrides applied.

    Args:
        operation_id: The operation.
        operation: The contract's operation.
        overrides: The ruled corrections to the contract's ``null``.

    Returns:
        The requirement, or ``None`` when the contract stamps no ``x-rights`` on it.
    """
    if operation_id in overrides:
        return overrides[operation_id]
    if "x-rights" not in operation:
        return None
    return _requirement(operation["x-rights"])


def check_operation(
    contract: dict[str, Any],
    served: dict[str, Any],
    rights: Mapping[str, Requirement],
    operation_id: str,
    overrides: Mapping[str, Requirement] = _OVERRIDES,
) -> list[Violation]:
    """Check one served operation against the contract.

    Args:
        contract: The contract document (paths below ``/api/v1``).
        served: The served v1 document (paths below its mount, ``/api/v1``).
        rights: The rights table the perimeter applies.
        operation_id: The served operation to check.
        overrides: The ruled corrections to the contract's ``null`` (a session act).

    Returns:
        Every violation found; empty when the operation conforms.
    """
    have = _operations(served)[operation_id]
    wanted_by_id = _operations(contract)
    if operation_id not in wanted_by_id:
        return [Violation(operation_id, "address", "the contract declares no such operationId")]
    wanted = wanted_by_id[operation_id]
    schema_diff = _SchemaDiff(contract, served, operation_id)
    record = schema_diff._record

    if (wanted.method, wanted.path) != (have.method, have.path):
        record("address", f"{wanted.method} {wanted.path} in the contract, {have.method} {have.path} in v1")
    if _parameters(wanted.body) != _parameters(have.body):
        record(
            "parameter", f"{sorted(_parameters(wanted.body))} in the contract, {sorted(_parameters(have.body))} in v1"
        )
    wanted_schemas, have_schemas = _parameter_schemas(contract, wanted.body), _parameter_schemas(served, have.body)
    for location in sorted(wanted_schemas.keys() & have_schemas.keys()):
        schema_diff.compare(wanted_schemas[location], have_schemas[location], " ".join(location), "parameter")

    wanted_answers, have_answers = wanted.body.get("responses", {}), have.body.get("responses", {})
    wanted_success = {code for code in wanted_answers if code.startswith("2")}
    have_success = {code for code in have_answers if code.startswith("2")}
    if wanted_success != have_success:
        record("status", f"success {sorted(wanted_success)} in the contract, {sorted(have_success)} in v1")
    for code in sorted(wanted_success & have_success):
        schema_diff.compare(
            _json_schema(contract, wanted_answers[code]), _json_schema(served, have_answers[code]), code, "response"
        )

    wanted_request, have_request = wanted.body.get("requestBody"), have.body.get("requestBody")
    if (wanted_request is None) != (have_request is None):
        record("request", f"a body in the contract: {wanted_request is not None}, in v1: {have_request is not None}")
    elif wanted_request is not None and have_request is not None:
        wanted_request, _ = _SchemaDiff._resolve(contract, wanted_request)
        have_request, _ = _SchemaDiff._resolve(served, have_request)
        if bool(wanted_request.get("required")) != bool(have_request.get("required")):
            record("request", "the body is required in one document and optional in the other")
        schema_diff.compare(
            _json_schema(contract, wanted_request), _json_schema(served, have_request), "body", "request"
        )

    wanted_refusals = {code for code in wanted_answers if not code.startswith("2")}
    have_refusals = {code for code in have_answers if not code.startswith("2")}
    if wanted_refusals != have_refusals:
        record(
            "refusal",
            f"v1 lacks {sorted(wanted_refusals - have_refusals)}, v1 adds {sorted(have_refusals - wanted_refusals)}",
        )
    problem, _ = _SchemaDiff._resolve(contract, contract["components"]["schemas"]["Problem"])
    for code in sorted(have_refusals):
        answered, _ = _SchemaDiff._normal(served, _json_schema(served, have_answers[code]))
        _check_problem(schema_diff, problem, answered, code)

    expected = _expected_right(operation_id, wanted.body, overrides)
    if operation_id in overrides and wanted.body.get("x-rights") is not None:
        # An override corrects a session act (null); applied over a right, it would silence it.
        record(
            "right",
            f"{operation_id}: an override replaces the contract's x-rights {wanted.body['x-rights']!r}, "
            "which is no longer a session act",
        )
    elif expected is None:
        record("right", "the contract stamps no x-rights on the operation")
    elif rights.get(operation_id) != expected:
        record("right", f"the contract asks {expected!r}, OPERATION_RIGHTS asks {rights.get(operation_id)!r}")
    return schema_diff.violations


def _check_problem(schema_diff: _SchemaDiff, problem: dict[str, Any], answered: Any, code: str) -> None:
    """Check one refusal's body against the contract's ``Problem``.

    Args:
        schema_diff: The operation's schema_diff, which records the violations.
        problem: The contract's resolved ``Problem``.
        answered: The served refusal's resolved schema.
        code: The refusal status, for the record.
    """
    if not isinstance(answered, dict):
        schema_diff._record("problem", f"{code}: v1 answers no JSON Problem")
        return
    wanted_names, have_names = set(problem.get("properties", {})), set(answered.get("properties", {}))
    if wanted_names != have_names:
        schema_diff._record(
            "problem",
            f"{code}: v1 lacks {sorted(wanted_names - have_names)}, v1 adds {sorted(have_names - wanted_names)}",
        )
    unmet = set(problem.get("required", [])) - set(answered.get("required", []))
    if unmet:
        schema_diff._record("problem", f"{code}: v1 does not require {sorted(unmet)}")
    if "code" in wanted_names & have_names:
        wanted_codes, _ = _SchemaDiff._normal(schema_diff.contract, problem["properties"]["code"])
        have_codes, _ = _SchemaDiff._normal(schema_diff.served, answered["properties"]["code"])
        undeclared = set(have_codes.get("enum", [])) - set(wanted_codes.get("enum", []))
        if undeclared or "enum" not in have_codes:
            schema_diff._record(
                "problem", f"{code}: v1 answers refusal codes the contract does not declare: {sorted(undeclared)}"
            )


def _contract() -> dict[str, Any]:
    """Read the contract.

    Returns:
        The contract document.
    """
    document: dict[str, Any] = json.loads(_CONTRACT.read_text(encoding="utf-8"))
    return document


def _served() -> dict[str, Any]:
    """Read the committed served document.

    Returns:
        ``frontend/openapi-v1.json``.
    """
    document: dict[str, Any] = json.loads(_SERVED.read_text(encoding="utf-8"))
    return document


def test_committed_document_is_the_served_one(make_v1_app: Callable[..., FastAPI]) -> None:
    """``frontend/openapi-v1.json`` is what ``create_v1_app`` serves: the cases below cover every served operation."""
    assert json.loads(json.dumps(make_v1_app().openapi())) == _served()


@pytest.mark.parametrize("operation_id", sorted(_operations(_served())) if _SERVED.is_file() else [])
def test_served_operation_conforms(operation_id: str) -> None:
    """A served operation is the contract's, in every checked respect."""
    assert check_operation(_contract(), _served(), OPERATION_RIGHTS, operation_id) == []


# ---------------------------------------------------------------------------
# The planted drifts: each one, alone on a throw-away application, fails the check.
# ---------------------------------------------------------------------------


class _Version(ContractModel):
    """The contract's ``readVersion`` answer, faithful."""

    version: str
    commit: str


class _RenamedVersion(ContractModel):
    """``readVersion``'s answer with one property renamed."""

    version: str
    build_commit: str


class _WiderVersion(ContractModel):
    """``readVersion``'s answer with one optional property the contract does not declare."""

    version: str
    commit: str
    branch: str | None = None


class _RoleKind(StrEnum):
    """The contract's role kinds."""

    ADMIN = "admin"
    ORDINARY = "ordinary"


class _Role(ContractModel):
    """The contract's ``Role``, faithful."""

    id: str
    name: str
    kind: _RoleKind
    rights: list[Right]
    default_for: list[Literal["plexHome", "plexGuest", "local"]] | None = None


class _RoleDraft(ContractModel):
    """``createRole``'s body, faithful."""

    name: str
    rights: list[Right]


class _ShortState(StrEnum):
    """The pipeline's states, one member (``stopping``) missing."""

    IDLE = "idle"
    RUNNING = "running"
    QUEUED = "queued"
    PAUSED = "paused"


class _PauseAnswer(ContractModel):
    """``pausePipeline``'s answer over the short enum."""

    state: _ShortState


class _OptionalWatcher(ContractModel):
    """``setWatcher``'s body with its required property made optional."""

    enabled: bool = False


class _WatcherAnswer(ContractModel):
    """``setWatcher``'s answer, faithful."""

    watcher_enabled: bool


def _refusals(operation_id: str) -> dict[int | str, dict[str, Any]]:
    """The refusal statuses the contract declares on one operation, each answering ``Problem``.

    Args:
        operation_id: The contract operation.

    Returns:
        A ``responses`` mapping for a planted route.
    """
    declared = _operations(_contract())[operation_id].body["responses"]
    return {int(code): PROBLEM_RESPONSES[400] for code in declared if not code.startswith("2")}


def _planted(router: APIRouter) -> dict[str, Any]:
    """Serve one planted router on a throw-away application and read its document.

    Args:
        router: The planted routes.

    Returns:
        The application's OpenAPI document, as JSON would carry it.
    """
    app = FastAPI(title="planted")
    # As create_v1_app does: v1 declares no 422, which it never answers.
    app.openapi = _without_validation_answers(app.openapi)  # type: ignore[method-assign]
    include_v1_router(app, router)
    document: dict[str, Any] = json.loads(json.dumps(app.openapi()))
    return document


def _kinds(served: dict[str, Any], operation_id: str, rights: Mapping[str, Requirement] = OPERATION_RIGHTS) -> set[str]:
    """The kinds of violation the check finds on one planted operation.

    Args:
        served: The planted document.
        operation_id: The planted operation.
        rights: The rights table to check against.

    Returns:
        The violated checks' kinds.
    """
    return {violation.kind for violation in check_operation(_contract(), served, rights, operation_id)}


def _version_router(
    model: type[ContractModel] = _Version, path: str = "/version", drop: int | None = None
) -> APIRouter:
    """A planted ``readVersion``.

    Args:
        model: Its answer's model.
        path: Its path.
        drop: A refusal status left out of its ``responses``.

    Returns:
        The router.
    """
    router = APIRouter()
    responses = {code: answer for code, answer in _refusals("readVersion").items() if code != drop}

    @router.get(path, operation_id="readVersion", response_model=model, responses=responses)
    def _read_version() -> Any:
        """The planted route; never called."""

    return router


def test_faithful_plant_passes() -> None:
    """The control: a planted ``readVersion`` written from the contract shows no violation."""
    assert check_operation(_contract(), _planted(_version_router()), OPERATION_RIGHTS, "readVersion") == []


def test_detects_a_renamed_response_property() -> None:
    """``commit`` served as ``buildCommit`` fails the response check."""
    assert _kinds(_planted(_version_router(_RenamedVersion)), "readVersion") == {"response"}


def test_detects_an_added_response_property() -> None:
    """An optional ``branch`` the contract does not declare fails the response check (names, not required)."""
    assert _kinds(_planted(_version_router(_WiderVersion)), "readVersion") == {"response"}


def test_detects_a_wrong_success_status() -> None:
    """``createRole`` answering 200 where the contract answers 201 fails the status check."""
    router = APIRouter()

    @router.post(
        "/roles", operation_id="createRole", status_code=200, response_model=_Role, responses=_refusals("createRole")
    )
    def _create_role(draft: _RoleDraft) -> Any:
        """The planted route; never called."""

    assert _kinds(_planted(router), "createRole") == {"status"}


def test_detects_a_missing_enum_member() -> None:
    """``pausePipeline`` answering a state enum without ``stopping`` fails the enum check."""
    router = APIRouter()

    @router.post(
        "/pipeline/pause",
        operation_id="pausePipeline",
        response_model=_PauseAnswer,
        responses=_refusals("pausePipeline"),
    )
    def _pause() -> Any:
        """The planted route; never called."""

    assert _kinds(_planted(router), "pausePipeline") == {"enum"}


def test_detects_a_missing_required_body_property() -> None:
    """``setWatcher`` whose body does not require ``enabled`` fails the request check."""
    router = APIRouter()

    @router.post(
        "/pipeline/watcher", operation_id="setWatcher", response_model=_WatcherAnswer, responses=_refusals("setWatcher")
    )
    def _set_watcher(body: _OptionalWatcher) -> Any:
        """The planted route; never called."""

    assert _kinds(_planted(router), "setWatcher") == {"request"}


def test_detects_an_undeclared_refusal_status() -> None:
    """A ``readVersion`` that does not declare the contract's 503 fails the refusal check."""
    assert _kinds(_planted(_version_router(drop=503)), "readVersion") == {"refusal"}


def test_detects_a_right_differing_from_the_contract() -> None:
    """A rights table asking ``library.read`` of ``readVersion`` (a session act) fails the right check."""
    rights = {**OPERATION_RIGHTS, "readVersion": holds(Right.LIBRARY_READ)}

    assert _kinds(_planted(_version_router()), "readVersion", rights) == {"right"}


def test_detects_an_override_over_a_contract_right() -> None:
    """An override on an operation the contract stamps a right on fails the right check, naming the operation.

    An override corrects a session act (``null``); once the contract asks a right, the
    override would silence it.
    """
    contract = _contract()
    contract["paths"]["/version"]["get"]["x-rights"] = Right.SYSTEM_VIEW.value
    override = {**_OVERRIDES, "readVersion": SignedIn()}
    rights = {**OPERATION_RIGHTS, "readVersion": SignedIn()}

    violations = check_operation(contract, _planted(_version_router()), rights, "readVersion", override)

    assert {violation.kind for violation in violations} == {"right"}
    assert any("readVersion" in violation.detail for violation in violations)


#: The contract's ``searchProviderById`` sources, faithful, and with ``imdb`` missing.
_Provider = Literal["tmdb", "tvdb", "imdb"]
_ShortProvider = Literal["tmdb", "tvdb"]


def _search_by_id_router(short: bool) -> APIRouter:
    """A planted ``searchProviderById``.

    Args:
        short: Whether its ``provider`` query parameter lacks ``imdb``.

    Returns:
        The router.
    """
    router = APIRouter()
    route = router.get(
        "/acquisition/search/by-id", operation_id="searchProviderById", responses=_refusals("searchProviderById")
    )
    if short:

        @route
        def _search_short(provider: _ShortProvider, id: str) -> Any:  # noqa: A002 - the contract's name
            """The planted route; never called."""

    else:

        @route
        def _search(provider: _Provider, id: str) -> Any:  # noqa: A002 - the contract's name
            """The planted route; never called."""

    return router


def test_detects_a_wrong_query_parameter_enum() -> None:
    """``searchProviderById`` whose ``provider`` query parameter lacks ``imdb`` fails the enum check.

    The plant answers no response model, so only the enum kind is asserted; the control
    with the contract's three members shows it comes from the parameter.
    """
    faithful = _planted(_search_by_id_router(short=False))
    short = _planted(_search_by_id_router(short=True))

    assert "enum" not in _kinds(faithful, "searchProviderById")
    enums = [v for v in check_operation(_contract(), short, OPERATION_RIGHTS, "searchProviderById") if v.kind == "enum"]
    assert len(enums) == 1
    assert "query provider" in enums[0].detail and "imdb" in enums[0].detail


def test_detects_a_wrong_path() -> None:
    """``readVersion`` served at another path fails the address check."""
    assert _kinds(_planted(_version_router(path="/versions")), "readVersion") == {"address"}
