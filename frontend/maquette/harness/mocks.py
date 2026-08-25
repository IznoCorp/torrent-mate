"""R85 — the mock layer answers the contract, deterministically.

IT DRIVES THE LAYER AND NOT A SURFACE, and that is not a shortcut. L08 wires no
surface — the wiring is L09's — so there is nothing on screen to read, and a
rule that pretended otherwise would be measuring the fixtures the engine still
draws from. What it reads is `window.__mocks`, the layer's own driving surface,
the same arrangement `__go` and `__referentiel` already use.

WHAT THIS RULE HOLDS, and each hold answers one line of the lot's « Done when »:

  determinism   the same request twice returns byte-identical bodies, and the
                same request after a reset returns them again. The oracle is
                asked to depend on this layer at L09, and an oracle cannot
                depend on a payload that differs between two identical asks.
  the contract  every route the layer answers is an operation the contract
                declares, and every operation the contract declares has a
                route. A layer answering a path nobody declared is a path L09
                would wire to and no backend would ever serve.
  failure       a scenario that asks an operation to fail gets the declared
                status and a body carrying its real reason — never a bare code
                (NE-DOIT-PAS-4, NE-DOIT-PAS-5).
  latency       a declared latency is observed, and it is the SAME on two runs.
                Never a jitter: a mock that varies is a mock nothing can
                depend on.
  quiet         the signal the oracle's settle reads is false while a request
                is in flight and true after it. Without it, a wired surface at
                L09 would be measured mid-flight.
  the clock     the layer's frozen instant EQUALS the engine's `TODAY`. They
                are two copies — `mocks/` imports nothing from `engine/`,
                because the engine dies at L13 — and every date-derived state
                moves the moment they disagree.
  mutation      a mutation changes what the next read returns, and a reset puts
                the seeded state back byte for byte. L09's optimistic paths are
                written against a layer where both are true.
  the network   no handler reaches the real network. The seam answers from the
                table or fails naming the route; it never falls through.

WHAT IT DOES NOT READ. Nothing about how a SURFACE renders any of this — there
is no wired surface to read. It also does not prove the browser's own network
stack behaves, because the seam replaces it: caching, redirects and abort
signals are outside what an in-process seam can answer for, and that cost is
recorded in D-L08-2 rather than hidden here.
"""
import asyncio
import json
import pathlib
import re

from common import Journal, open_page

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "contract" / "openapi.json"
ENGINE = ROOT / "design" / "src" / "engine" / "legacy.js"

METHODS = ("get", "post", "put", "patch", "delete")

# How long a latency hold asks for. Long enough that a machine's own noise
# cannot account for it, short enough that two runs of this rule cost nothing.
LATENCY_MILLISECONDS = 250

# The status a failure hold asks for. Any 5xx would do; this one is what a
# server answers when a dependency will not.
FAILURE_STATUS = 503


def declared_operations():
    """Reads the contract's operations, as `{operationId: (METHOD, template)}`."""
    document = json.loads(CONTRACT.read_text(encoding="utf-8"))
    found = {}
    for template, entry in document["paths"].items():
        for method, operation in entry.items():
            if method in METHODS:
                found[operation["operationId"]] = (method.upper(), template)
    return found


def engine_clock():
    """Reads the engine's frozen clock out of its source.

    Read from the SOURCE and not from the running page on purpose: the two
    copies must agree in the tree, so that a change to one is caught by this
    rule rather than by a state that quietly renders a different day.
    """
    found = re.search(r'\bconst TODAY = "([^"]+)"', ENGINE.read_text(encoding="utf-8"))
    return found.group(1) if found else None


async def body_of(page, path, options="{}"):
    """Asks the layer for one path and returns its status and its raw body."""
    return await page.evaluate(
        """async ([path, options]) => {
             const answer = await fetch(path, JSON.parse(options));
             return { status: answer.status, body: await answer.text() };
           }""",
        [path, options],
    )


async def main():
    """Drives the mock layer and records every verdict."""
    from playwright.async_api import async_playwright

    journal = Journal("R85 — the mock layer answers the contract, deterministically")
    contract = declared_operations()
    errors = []

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        page.on("pageerror", lambda error: errors.append(str(error)))

        installed = await page.evaluate("() => Boolean(window.__mocks)")
        if not journal.check(
            "the layer is installed before anything renders",
            installed,
            "window.__mocks is published by the boot",
        ):
            journal.summary(errors)
            return

        # ── the contract ────────────────────────────────────────────────────
        answered = set(await page.evaluate("() => window.__mocks.routes()"))
        wanted = {f"{method} {template}" for method, template in contract.values()}
        journal.check(
            "every operation the contract declares has a route",
            wanted <= answered,
            f"{len(wanted)} declared, missing: {sorted(wanted - answered) or 'none'}",
        )
        journal.check(
            "the layer answers no route the contract does not declare",
            answered <= wanted,
            f"{len(answered)} answered, undeclared: {sorted(answered - wanted) or 'none'}",
        )

        # ── the clock ───────────────────────────────────────────────────────
        layer_clock = await page.evaluate("() => window.__mocks.scenario().now")
        journal.check(
            "the layer's frozen clock is the engine's",
            layer_clock == engine_clock(),
            f"layer {layer_clock!r}, engine {engine_clock()!r}",
        )

        # ── determinism ─────────────────────────────────────────────────────
        probe = "/api/acquisition/followed"
        first = await body_of(page, probe)
        second = await body_of(page, probe)
        journal.check(
            "the same request twice answers byte-identical bodies",
            first["body"] == second["body"] and first["status"] == 200,
            f"{len(first['body'])} bytes, status {first['status']}",
        )

        # ── mutation, and the reset ─────────────────────────────────────────
        before = json.loads(first["body"])
        await body_of(
            page,
            f"{probe}/{before[0]['title']}",
            json.dumps({"method": "DELETE"}),
        )
        after = json.loads((await body_of(page, probe))["body"])
        journal.check(
            "a mutation changes what the next read returns",
            len(after) == len(before) - 1,
            f"{len(before)} follows before, {len(after)} after a delete",
        )
        await page.evaluate("() => window.__mocks.reset()")
        restored = await body_of(page, probe)
        journal.check(
            "a reset puts the seeded state back, byte for byte",
            restored["body"] == first["body"],
            f"{len(restored['body'])} bytes",
        )

        # ── failure ─────────────────────────────────────────────────────────
        await page.evaluate(
            "(status) => window.__mocks.scenario().operations.readFollows = { status }",
            FAILURE_STATUS,
        )
        failed = await body_of(page, probe)
        journal.check(
            "a scenario that asks an operation to fail gets that status",
            failed["status"] == FAILURE_STATUS,
            f"asked {FAILURE_STATUS}, got {failed['status']}",
        )
        reason = json.loads(failed["body"]).get("detail", "")
        journal.check(
            "a failure carries its real reason, never a bare code",
            "readFollows" in reason,
            f"detail: {reason[:80]!r}",
        )
        await page.evaluate("() => window.__mocks.reset()")

        # ── an unclaimed route fails, naming itself ─────────────────────────
        unclaimed = await body_of(page, "/api/nothing-declares-this")
        journal.check(
            "a request no route claims fails and names the route",
            unclaimed["status"] == 404
            and "nothing-declares-this" in unclaimed["body"],
            f"status {unclaimed['status']}",
        )

        # ── latency, and the quiet signal ───────────────────────────────────
        await page.evaluate(
            "(milliseconds) => window.__mocks.scenario().operations.readFollows = "
            "{ latencyMilliseconds: milliseconds }",
            LATENCY_MILLISECONDS,
        )
        measured = []
        for _ in range(2):
            measured.append(
                await page.evaluate(
                    """async (path) => {
                         const started = performance.now();
                         await fetch(path);
                         return performance.now() - started;
                       }""",
                    probe,
                )
            )
        journal.check(
            "a declared latency is observed",
            all(elapsed >= LATENCY_MILLISECONDS for elapsed in measured),
            f"asked {LATENCY_MILLISECONDS} ms, measured "
            f"{', '.join(f'{elapsed:.0f}' for elapsed in measured)} ms",
        )
        journal.check(
            "and it is the same on two runs, never a jitter",
            abs(measured[0] - measured[1]) < LATENCY_MILLISECONDS,
            f"{abs(measured[0] - measured[1]):.0f} ms apart",
        )

        signal = await page.evaluate(
            """async (path) => {
                 const before = window.__mocks.inFlight();
                 const asked = fetch(path);
                 const during = window.__mocks.inFlight();
                 await window.__mocks.quiet();
                 const after = window.__mocks.inFlight();
                 await asked;
                 return { before, during, after };
               }""",
            probe,
        )
        journal.check(
            "the quiet signal counts a request in flight",
            signal["before"] == 0 and signal["during"] == 1,
            f"before {signal['before']}, during {signal['during']}",
        )
        journal.check(
            "and it settles once nothing is in flight",
            signal["after"] == 0,
            f"after {signal['after']}",
        )
        await page.evaluate("() => window.__mocks.reset()")

        # ── the network ─────────────────────────────────────────────────────
        # Anything the seam let through would leave the page, and the harness
        # host serves no `/api/...` — so a request reaching it would answer the
        # document rather than JSON. Both halves are read: the status, and that
        # the body is JSON rather than a page.
        answer = await body_of(page, "/api/system/services")
        journal.check(
            "no request reaches the real network",
            answer["status"] == 200 and answer["body"].lstrip().startswith("["),
            f"status {answer['status']}, body opens with "
            f"{answer['body'].lstrip()[:1]!r}",
        )

        await context.close()
        await browser.close()

    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
