"""Two web-UI invariants CLAUDE.md states and nothing enforced.

Both are written in `CLAUDE.md` §Web-UI Environments as things « enforced by
tests ». Neither had one. An adversarial review added a guarded-but-UNTYPED
mutating route and a per-route `Depends(require_session)` to a router that
already had the perimeter, ran the whole web suite — 1 129 tests — and nothing
said anything.

They are asserted here the way `test_staging_write_policy.py` asserts its own:
enumerate every route, classify each, and refuse the unclassified. A table, not
eleven edits.
"""

import inspect

import pytest
from fastapi.routing import APIRoute
from pydantic import BaseModel
from starlette.routing import Mount

from personalscraper.config import Settings
from personalscraper.web.app import create_app
from tests.web._web_harness import make_web_app

_MUTATING = {"POST", "PATCH", "PUT", "DELETE"}

# Mutating routes that legitimately return no model. Each says why, because an
# exemption without a reason is how a real hole hides in a list.
_UNTYPED_BY_DESIGN: dict[str, str] = {
    "/api/auth/login": "sets a cookie and returns a bare acknowledgement",
    "/api/auth/logout": "clears the cookie; there is nothing to describe",
}

# Routers whose own dependency carries the session, because they sit OUTSIDE
# the single perimeter by design: authentication has to work before a session
# exists, so `guarded_api` cannot cover it.
_OUTSIDE_THE_PERIMETER = ("/api/auth",)


def _describes_a_shape(model) -> bool:
    """Whether a response model actually describes anything.

    FastAPI INFERS the model from the return annotation, so a handler written
    `-> dict[str, object]` counts as « typed » to FastAPI while describing
    nothing at all: the OpenAPI gets a free-form object and `schema.d.ts` gets
    `Record<string, unknown>`. The invariant says PYDANTIC, and that is the
    distinction worth asserting — a bare dict is the shape of an untyped route
    wearing an annotation.

    Args:
        model: The route's resolved `response_model`, possibly None.

    Returns:
        True when the model is a Pydantic model, or a container of one.
    """
    if model is None:
        return False
    for candidate in (model, *getattr(model, "__args__", ())):
        if isinstance(candidate, type) and issubclass(candidate, BaseModel):
            return True
    return False


def _routes(app):
    """Yields every APIRoute of the app, nested routers included."""
    seen: set[int] = set()

    def walk(routes):
        for route in routes:
            if isinstance(route, APIRoute):
                if id(route) not in seen:
                    seen.add(id(route))
                    yield route
            elif isinstance(route, Mount):
                yield from walk(route.routes)
            elif hasattr(route, "original_router"):
                yield from walk(route.original_router.routes)
            elif hasattr(route, "routes"):
                yield from walk(route.routes)

    yield from walk(app.routes)


@pytest.fixture
def app(test_config):
    """Builds the full application, for route enumeration."""
    settings = Settings(web_jwt_secret="testsecret", _env_file=None)  # type: ignore[call-arg]
    return make_web_app(test_config, settings)


class TestEveryMutatingRouteIsTyped:
    """The invariant « Every mutating web endpoint is typed » (Pydantic model).

    Stated in CLAUDE.md §Web-UI, and enforced by nothing until this file.
    """

    def test_no_mutating_route_answers_an_undescribed_shape(self, app) -> None:
        """A route with no `response_model` describes nothing in the OpenAPI.

        And the OpenAPI is what `schema.d.ts` is generated from, so an untyped
        route is a hole the frontend cannot see: it gets `unknown`, or nothing
        at all, and every consumer guesses. The drift check only demands that
        the schema be REGENERATED after a change — never that a route describe
        itself in the first place.
        """
        untyped = [
            f"{sorted(route.methods & _MUTATING)[0]} {route.path}"
            for route in _routes(app)
            if route.methods & _MUTATING
            and route.path not in _UNTYPED_BY_DESIGN
            # A 204 answers NO BODY by definition, so there is nothing for a
            # model to describe. Exempting it is the rule, not a fudge.
            and route.status_code != 204
            and not _describes_a_shape(route.response_model)
        ]

        assert untyped == [], (
            "these mutating routes answer a shape the OpenAPI cannot describe — "
            "give them a `response_model`, or name them in `_UNTYPED_BY_DESIGN` "
            f"with the reason: {untyped}"
        )

    def test_every_declared_exemption_still_exists(self, app) -> None:
        """An exemption outliving its route is a licence nobody granted."""
        paths = {route.path for route in _routes(app)}

        stale = sorted(set(_UNTYPED_BY_DESIGN) - paths)

        assert stale == [], f"declared untyped-by-design, but gone: {stale}"


class TestTheAuthPerimeterIsSingle:
    """The invariant « the web auth perimeter is the SINGLE guarded_api ».

    Stated in CLAUDE.md §Web-UI, and enforced by nothing until this file.
    """

    def test_no_route_carries_its_own_session_dependency(self, app) -> None:
        """A second perimeter is worse than none — it looks like belt and braces.

        What it actually does is make the real perimeter untestable — remove
        `guarded_api` and the routes carrying their own guard stay closed, so
        the hole opens silently everywhere else while the suite stays green.
        """
        offenders = []
        for route in _routes(app):
            if route.path.startswith(_OUTSIDE_THE_PERIMETER):
                continue
            for dependency in route.dependant.dependencies:
                if "require_session" in repr(dependency.call):
                    offenders.append(f"{sorted(route.methods)[0]} {route.path}")
                    break

        assert offenders == [], (
            "these routes carry their own `Depends(require_session)` — the "
            "perimeter is `guarded_api` and only `guarded_api`, so a second "
            f"guard hides the first one failing: {offenders}"
        )

    def test_the_perimeter_actually_covers_the_api(self, app) -> None:
        """And the single perimeter must really be on, or this test is theatre!

        Asserting « nobody has their own guard » is satisfied trivially by a
        state where NOTHING is guarded. The perimeter's presence is what makes
        the absence of a second one meaningful.
        """
        api = [r for r in _routes(app) if r.path.startswith("/api/") and not r.path.startswith(_OUTSIDE_THE_PERIMETER)]
        assert api, "no /api routes found — the enumeration is broken"

        # `create_app` is the real factory; `make_web_app` is the test
        # harness that calls it, and reading the wrapper proved nothing.
        source = inspect.getsource(create_app)
        assert "guarded_api" in source, (
            "`create_app` no longer mentions `guarded_api` — the single "
            "perimeter is gone, and the test above would pass over an OPEN api"
        )
