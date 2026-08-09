"""The staging write policy (A18) — asserted as a table, not as eleven edits."""

import inspect

import pytest
from fastapi.routing import APIRoute
from starlette.routing import Mount

from personalscraper.config import Settings
from tests.web._web_harness import make_web_app

# Families whose writes are OPEN on staging: their worst case is a repairable row.
_OPEN_PREFIXES = ("/api/acquisition", "/api/decisions")
# Families whose writes stay GUARDED: they move real files, or hold shared state.
_GUARDED_PREFIXES = ("/api/pipeline", "/api/maintenance", "/api/config", "/api/staging")

# Session routes: neither a domain write nor a dangerous one. Authentication
# must WORK on staging — guarding it would 403 the login endpoint and make the
# instance unreachable, so you could not even sign in to test. They are listed
# here so they are CLASSIFIED rather than invisible, and asserted unguarded
# below: a staging guard appearing on /api/auth would be a bug, not a hardening.
_SESSION_PREFIXES = ("/api/auth",)

_MUTATING = {"POST", "PATCH", "PUT", "DELETE"}

# Routes that LOOK mutating (they are POSTs, because they take a body) but write
# nothing at all. Each entry carries the sentence from its own docstring that
# says so — an exemption without a reason is how a real hole hides in a list.
_PURE_DESPITE_POST = {
    "/api/config/validate": "« Validate a candidate config file without writing to disk »",
    "/api/acquisition/ranking/preview": "« Read-only + pure: no DB, no filesystem, no torrent client »",
}


def _is_staging_guarded(route: APIRoute) -> bool:
    """Whether a route refuses writes on staging — by EITHER of the two mechanisms.

    This codebase expresses ONE policy in TWO shapes, and a test that knows only
    one of them reports a false hole (it did, on first run — see the ledger):

    - as a FastAPI dependency — ``Depends(require_not_staging)``: pipeline,
      maintenance, staging-media, and (until A18) acquisition / decisions;
    - inside the handler body — ``if _is_staging(): raise HTTPException(403)``:
      every ``/api/config`` write.

    The divergence itself is a standing finding (see the ledger): one policy
    should have one implementation. Until it is unified, this predicate must
    recognise both, or it lies in one direction or the other.

    Args:
        route: The route to inspect.

    Returns:
        ``True`` when the route is guarded by either mechanism.
    """
    for dep in route.dependant.dependencies:
        if "require_not_staging" in repr(dep.call):
            return True
    try:
        source = inspect.getsource(route.endpoint)
    except (OSError, TypeError):
        return False
    return "_is_staging()" in source or "is_staging_role()" in source


def _mutating_routes(app):
    """Yield ``(path, method, route)`` for every route that can change state.

    Recursively descends into nested routers (``APIRouter`` / ``Mount``
    instances wrapped as ``_IncludedRouter`` by Starlette) so that the
    policy table covers every route regardless of nesting depth.
    """
    _seen: set[int] = set()

    # Paths are expected already-absolute because Starlette flattens
    # included routers — test_every_mutating_route_is_classified fails
    # loudly if that ever stops being true.
    def _walk(routes):
        for route in routes:
            # Dedup by id — the same APIRoute can appear at multiple nesting
            # levels when Starlette flattens the tree.
            if isinstance(route, APIRoute):
                if id(route) not in _seen:
                    _seen.add(id(route))
                    if route.path in _PURE_DESPITE_POST:
                        continue
                    for method in route.methods & _MUTATING:
                        yield route.path, method, route
            elif isinstance(route, Mount):
                yield from _walk(route.routes)
            elif hasattr(route, "original_router"):
                # FastAPI's _IncludedRouter — wraps an APIRouter after
                # include_router().  Descend into its original_router.routes.
                yield from _walk(route.original_router.routes)
            elif hasattr(route, "routes"):
                # Generic fallback for any other wrapper with .routes.
                yield from _walk(route.routes)

    yield from _walk(app.routes)


@pytest.fixture
def app(test_config):
    """Build the full FastAPI application for route enumeration.

    Uses the synthetic test_config (temp paths), matching the pattern used
    by the existing web route tests.
    """
    settings = Settings(web_jwt_secret="testsecret", _env_file=None)  # type: ignore[call-arg]
    return make_web_app(test_config, settings)


def test_acquisition_and_decision_writes_are_open_on_staging(app):
    """A18 : ces écritures doivent PASSER sur staging (pire cas réparable à la main)."""
    still_guarded = [
        f"{method} {path}"
        for path, method, route in _mutating_routes(app)
        if path.startswith(_OPEN_PREFIXES) and _is_staging_guarded(route)
    ]
    assert still_guarded == [], f"encore gardées alors qu'A18 les ouvre : {still_guarded}"


def test_dangerous_writes_stay_guarded_on_staging(app):
    """A18 : celles-ci DOIVENT rester gardées — elles déplacent des fichiers ou tiennent l'état partagé."""
    unguarded = [
        f"{method} {path}"
        for path, method, route in _mutating_routes(app)
        if path.startswith(_GUARDED_PREFIXES) and not _is_staging_guarded(route)
    ]
    assert unguarded == [], f"écriture non gardée hors du périmètre A18 : {unguarded}"


def test_every_mutating_route_is_classified(app):
    """Aucune route mutante ne doit échapper aux deux tables de politique.

    Les deux assertions ci-dessus classent par préfixe. Une route qui ne tombe
    dans AUCUN des deux ensembles n'est vérifiée par personne — ni ouverte, ni
    gardée, simplement invisible. Ce test est ce qui empêche cet angle mort, et
    il couvre deux dérives d'un coup :

    - un chemin non absolu (si Starlette cessait d'aplatir les routes montées),
      qui ne commencerait par aucun préfixe connu ;
    - une famille d'API neuve montée sous un préfixe absent des deux tables.

    Le remède, dans les deux cas, est de mettre à jour les tables — jamais
    d'élargir ce test.
    """
    unclassified = [
        f"{method} {path}"
        for path, method, _route in _mutating_routes(app)
        if not path.startswith(_OPEN_PREFIXES + _GUARDED_PREFIXES + _SESSION_PREFIXES)
    ]
    assert unclassified == [], (
        "routes mutantes non classées — ni ouvertes ni gardées, donc vérifiées "
        f"par personne : {unclassified}. Mettez à jour _OPEN_PREFIXES, "
        "_GUARDED_PREFIXES ou _SESSION_PREFIXES."
    )


def test_session_routes_are_never_guarded_on_staging(app):
    """Se connecter à staging doit rester possible.

    Un garde staging sur /api/auth rendrait l'instance injoignable : on ne
    pourrait plus s'y authentifier pour tester quoi que ce soit. Ce test existe
    pour que ce durcissement bien intentionné échoue tout de suite.
    """
    guarded = [
        f"{method} {path}"
        for path, method, route in _mutating_routes(app)
        if path.startswith(_SESSION_PREFIXES) and _is_staging_guarded(route)
    ]
    assert guarded == [], f"l'authentification est gardée sur staging, l'instance devient injoignable : {guarded}"
