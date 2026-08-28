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
  the settle    `oracle.py`'s own rest signal WAITS for a request still in
                flight. Until this hold existed, that line could be deleted and
                every gate stayed green — including the oracle, which is the
                instrument the line changes.
  the stream    the event stream obeys `web-ui.md` § WebSocket Protocol: one
                hello and it is FIRST; a refused session is ACCEPTED and then
                closed `4401`, in that order, because closing before accept
                gives a browser an opaque `1006` and makes the client's
                terminal branch dead code in production; `?last_id=` replays
                with an EXCLUSIVE lower bound; a burst arrives in order; and
                the stream pushes NOTHING unless the driver makes it push,
                which is what keeps a named state measurable.
  the network   the seam answers from the table rather than leaving the page.
                It reads ONE route and the `fetch` seam alone: a handler
                reaching the network through another means — a script tag, an
                image, an event source — is outside what this reads, and the
                seam replaces `fetch` only.

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
import time

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

# How far past the declared wait a measurement may land and still be that wait.
# It covers the scheduler and one frame, and nothing more: the hold's subject is
# whether the layer waits the number it was TOLD, and a tolerance as wide as the
# latency cannot answer that.
JITTER_TOLERANCE_MILLISECONDS = 120

# The wait the oracle's own settle is measured against. Long enough that the
# settle's other steps — animations, image decoding, two frames — cannot account
# for it on any machine.
ORACLE_WAIT_MILLISECONDS = 700

# A configuration file the SEEDED settings really own. The listing is derived
# from the topics' own `fileNames`, so a name they do not carry never appears in
# it and the hold would be measuring its own typo.
CONFIGURATION_FILE = "paths"


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

        # FOUR MORE MUTATIONS, on four different subjects. The hold above reads
        # `deleteFollow` alone, and reading one of sixteen is how three routes
        # that changed nothing at all went unnoticed.
        for operation, mutate, read, changed in (
            (
                "runPipeline",
                ("/api/pipeline/run", "POST", None),
                ("/api/pipeline/run", "POST", None),
                lambda first, second: first["state"] != second["state"],
            ),
            (
                "updateConfigurationFile",
                (f"/api/config/files/{CONFIGURATION_FILE}", "PUT", {}),
                ("/api/config/files", "GET", None),
                lambda _first, second: any(entry["changed"] for entry in second),
            ),
            (
                "resolveDecision",
                (None, None, None),
                ("/api/decisions/", "GET", None),
                lambda _first, second: any(
                    "choice" in entry for entry in second["settled"]),
            ),
            (
                "discardStagedMedia",
                (None, None, None),
                ("/api/staging/media", "GET", None),
                lambda first, second: len(second["stuck"]) == len(first["stuck"]) - 1,
            ),
        ):
            await page.evaluate("() => window.__mocks.reset()")
            if operation == "resolveDecision":
                pending = json.loads((await body_of(page, "/api/decisions/"))["body"])
                one = pending["pending"][0]
                candidate = one["candidates"][0]
                first = pending["settled"]
                await body_of(
                    page,
                    f"/api/decisions/{one['folder']}/resolve",
                    json.dumps({
                        "method": "POST",
                        "body": json.dumps({
                            "provider": candidate["provider"],
                            "providerId": candidate["id"],
                        }),
                    }),
                )
            elif operation == "discardStagedMedia":
                staging = json.loads((await body_of(page, "/api/staging/media"))["body"])
                first = staging
                await body_of(
                    page,
                    f"/api/staging/media/{staging['stuck'][0]['title']}/discard",
                    json.dumps({"method": "POST"}),
                )
            else:
                path, method, payload = mutate
                options = {"method": method}
                if payload is not None:
                    options["body"] = json.dumps(payload)
                first = json.loads((await body_of(page, path, json.dumps(options)))["body"])
            path, method, _ = read
            options = json.dumps({"method": method} if method != "GET" else {})
            second = json.loads((await body_of(page, path, options))["body"])
            journal.check(
                f"{operation} changes what the next read returns",
                changed(first, second),
                f"read back after {operation}",
            )
        await page.evaluate("() => window.__mocks.reset()")

        # ── failure ─────────────────────────────────────────────────────────
        await page.evaluate(
            "(status) => window.__mocks.setOperationOutcome('readFollows', { status })",
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
            "(milliseconds) => window.__mocks.setOperationOutcome('readFollows', "
            "{ latencyMilliseconds: milliseconds })",
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
        # AGAINST THE DECLARED VALUE, not against each other. The tolerance was
        # the latency itself — 250 ms of slack on a 250 ms measurement — so a
        # layer holding `250 + random()*249` passed both halves while being
        # exactly the number drawn at random the layer says it never draws.
        overshoot = [elapsed - LATENCY_MILLISECONDS for elapsed in measured]
        journal.check(
            "and it is the DECLARED wait, never a jitter around it",
            all(0 <= extra <= JITTER_TOLERANCE_MILLISECONDS for extra in overshoot),
            f"overshoot {', '.join(f'{extra:.0f}' for extra in overshoot)} ms, "
            f"tolerance {JITTER_TOLERANCE_MILLISECONDS} ms",
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

        # ── the oracle's own settle waits for the layer ─────────────────────
        #
        # THE HOLD THAT MAKES THE ORACLE'S CHANGE BITE. `oracle.py`'s settle
        # asks the layer whether anything is in flight, and until this hold
        # existed that line could be deleted and every gate stayed green —
        # including the oracle, which is the instrument being modified. Nothing
        # fetches yet, so the signal resolves on the spot in normal use; here a
        # request is deliberately left in flight, and the settle must wait for
        # it. Delete the call and this falls.
        import importlib.util

        specification = importlib.util.spec_from_file_location(
            "recorded_oracle", ROOT / "oracle.py")
        recorded_oracle = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(recorded_oracle)

        await page.evaluate("() => window.__mocks.reset()")
        await page.evaluate(
            "(milliseconds) => window.__mocks.setOperationOutcome('readFollows', "
            "{ latencyMilliseconds: milliseconds })",
            ORACLE_WAIT_MILLISECONDS,
        )
        # Started and NOT awaited: the point is that it is still in flight when
        # the settle is asked.
        await page.evaluate("(path) => { fetch(path); }", probe)
        started = time.monotonic()
        await recorded_oracle.settle(page)
        waited = (time.monotonic() - started) * 1000
        journal.check(
            "the oracle's settle waits for a request still in flight",
            waited >= ORACLE_WAIT_MILLISECONDS,
            f"asked {ORACLE_WAIT_MILLISECONDS} ms, the settle took {waited:.0f} ms",
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

        # ── the stream ──────────────────────────────────────────────────────
        # DRIVEN THROUGH `window.__mocks.stream` AND READ AT THE CLIENT'S END.
        # A hold that asked the driver what it had emitted would be asking the
        # writer whether it wrote; what is measured here is what a socket
        # RECEIVED, which is the only end a real client has.
        observed = await page.evaluate(
            """async () => {
                 const stream = window.__mocks.stream;
                 stream.reset();
                 const seen = [];
                 const closed = [];
                 const socket = new WebSocket("/ws/events");
                 socket.addEventListener("message", (e) => seen.push(JSON.parse(e.data)));
                 socket.addEventListener("close", (e) => closed.push(e.code));
                 await new Promise((r) => setTimeout(r, 80));
                 const beforeAnyEmit = seen.length;
                 stream.emitBurst([
                   { type: "PipelineStarted" },
                   { type: "StepStarted" },
                   { type: "StepCompleted" },
                 ]);
                 // THE RELAY IS CONNECTED TOO, and it answers pings like any
                 // client should. A hold expecting exactly one pong was written
                 // when nothing else was listening, and it fell the moment the
                 // relay existed — in the full suite, not alone, because
                 // running this rule by itself boots the same relay. What is
                 // held is that EVERY open socket answered, which is the
                 // property, and it does not depend on how many there are.
                 const listening = stream.state().sockets;
                 stream.ping();
                 socket.send("pong");
                 await new Promise((r) => setTimeout(r, 40));
                 stream.drop(1006);
                 await new Promise((r) => setTimeout(r, 40));

                 // Reconnect having seen the FIRST of the three.
                 const replayed = [];
                 const second = new WebSocket("/ws/events?last_id=1-0");
                 second.addEventListener("message", (e) => replayed.push(JSON.parse(e.data)));
                 await new Promise((r) => setTimeout(r, 80));

                 // A refused session: accepted first, then closed 4401.
                 stream.refuse(true);
                 const order = [];
                 const third = new WebSocket("/ws/events");
                 third.addEventListener("open", () => order.push("open"));
                 third.addEventListener("close", (e) => order.push(`close:${e.code}`));
                 await new Promise((r) => setTimeout(r, 80));
                 stream.refuse(false);

                 return {
                   seen, closed, replayed, order, beforeAnyEmit,
                   pongs: stream.state().received, listening,
                   addresses: stream.connections(),
                 };
               }"""
        )

        journal.check(
            "one hello, and it arrives before anything else",
            observed["beforeAnyEmit"] == 1
            and observed["seen"][0]["type"] == "ws.hello"
            and len([one for one in observed["seen"] if one["type"] == "ws.hello"]) == 1,
            f"the socket saw {observed['beforeAnyEmit']} frame(s) before any emit, "
            f"opening with {observed['seen'][0]['type'] if observed['seen'] else 'nothing'!r}",
        )
        journal.check(
            "the stream pushes nothing the driver did not push",
            observed["beforeAnyEmit"] == 1,
            f"{observed['beforeAnyEmit'] - 1} unsolicited frame(s) arrived before the first emit",
        )
        burst = [one["type"] for one in observed["seen"] if one.get("id")]
        journal.check(
            "a burst arrives whole and in order",
            burst == ["PipelineStarted", "StepStarted", "StepCompleted"],
            f"received {burst}",
        )
        journal.check(
            "every open socket answers a ping, and the server records the frames",
            any(one["type"] == "ws.ping" for one in observed["seen"])
            and "pong" in observed["pongs"]
            and len(observed["pongs"]) == observed["listening"],
            f"ping seen: {any(one['type'] == 'ws.ping' for one in observed['seen'])}, "
            f"{len(observed['pongs'])} frame(s) recorded from "
            f"{observed['listening']} open socket(s): {observed['pongs']}",
        )
        replayed = [one["id"] for one in observed["replayed"] if one.get("id")]
        journal.check(
            "`last_id` replays with an EXCLUSIVE lower bound",
            replayed == ["2-0", "3-0"],
            f"reconnecting at 1-0 replayed {replayed}, and 1-0 among them would be "
            "one event delivered twice on every reconnect",
        )
        journal.check(
            "a refused session is ACCEPTED first, then closed 4401",
            observed["order"] == ["open", "close:4401"],
            f"the socket saw {observed['order']} — closing before accept gives a "
            "browser an opaque 1006 and the client's 4401 branch becomes unreachable",
        )
        journal.check(
            "a reconnect carries the cursor it left on",
            observed["addresses"][1].endswith("last_id=1-0"),
            f"the second connection asked for {observed['addresses'][1]!r}",
        )
        await page.evaluate("() => window.__mocks.reset()")

        await context.close()
        await browser.close()

    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
