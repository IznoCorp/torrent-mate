"""R170 — the layer answers the success code its operation DECLARES.

THE DEFECT IT HOLDS (B-379). `mocks/scenario.ts` computed every outcome as
`status: armed ? (asked.status ?? 200) : 200`, so the layer answered 200 to the
three operations whose contract declares something else — a 201 for
`grabSeasonForFollow`, a 202 for `requeueJourney` and `rescrapeJourney`. It was
measured, not reasoned: R158's first run read four season grabs and four
`status: 200` in `window.__mocks.answered()`, and every hold written on the
literal code was red for a reason that was not the act. A sentence saying the
layer « answers 201 » was false ON THE CODE while the payload beside it was
right, which is the shape nothing else here can see.

WHY IT IS ITS OWN RULE and not a hold inside R85. R85's subject is that the
layer answers the contract's ROUTES, deterministically; this one's is the CODE
a route answers with, which is a different end of the same contract and moves
for different reasons — an operation added with a 201, a scenario dial that
stops honouring a failure. It is also cheap enough for the contracts tier,
where a declared code belongs: a code is a NAME the contract chose, and a name
that moves on one side only is exactly what that tier reads.

WHAT IT HOLDS.

  the families    one operation per declared success family is really asked
                  for, and the layer answers the contract's own code for it —
                  201 for a creation, 202 for an ask the backend accepts, 200
                  otherwise. Read from `window.__mocks.answered()`, never from
                  the browser's request events: the seam replaces `fetch`, so
                  a mocked call fires none of them (`mocks/answered.ts`).
  the corpus      every operation the contract declares a NON-200 success for
                  is among the ones this rule asks for. It is the floor that
                  makes the holds above mean something: a contract that gains
                  a 201 tomorrow and a rule that goes on exercising three
                  operations would stay green over an operation nobody reads.
  the dial        a scenario that ASKS for a failure still gets exactly it,
                  and a scenario that asks only for a latency still gets the
                  declared success. The repair touches both branches of
                  `outcomeFor`, and a fix that answered the declared code even
                  to an armed failure would break every error state this
                  prototype draws.
  the record      what `answered()` reports is what the response really
                  carried. The record is written from the same outcome the
                  answer is built from, and a rule reading only the record
                  would be green over a layer that recorded one code and sent
                  another.

WHAT IT DOES NOT READ. Nothing about what a SURFACE does with a 201 or a 202:
the application reads `answer.ok`, so the three codes are indistinguishable to
it by design, and a hold about that would be a hold about `query-client.ts`.
Nor the codes of the 400-and-up band, which are the scenario's to name and are
already R85's.
"""
import asyncio
import json
import pathlib

from common import Journal, open_page

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "contract" / "openapi.json"

METHODS = ("get", "post", "put", "patch", "delete")

# The band a success lives in, and the code an operation answers when it
# declares nothing else. Named rather than typed twice, because the reader in
# `mocks/declared-status.ts` uses the same three numbers and a drift between
# them would make this rule agree with a broken layer.
FIRST_SUCCESS = 200
FIRST_REDIRECT = 300
PLAIN_SUCCESS = 200

# The status the dial hold asks for. Any 5xx would do; this one is what a
# server answers when a dependency will not, and it is R85's own choice.
FAILURE_STATUS = 503

# A latency small enough to cost nothing and large enough that asking for it is
# unambiguously a scenario override with no status in it.
LATENCY_MILLISECONDS = 10

# WHAT EACH OPERATION IS ASKED FOR WITH, by operationId. The subjects are real
# ones the seeds hold — a folder, a title, a provider identity — because a
# handler that answers for nothing at all would take the 404 branch of the seam
# and never reach the outcome this rule is about.
#
# ONE PER DECLARED FAMILY IS THE FLOOR, not the corpus: every operation the
# contract declares a non-200 success for is here, and the hold below refuses
# the day that stops being true.
ASKED_FOR = {
    "grabSeasonForFollow": (
        "POST", "/api/acquisition/follows/Silo/seasons/1/grab"),
    "requeueJourney": ("POST", "/api/acquisition/journeys/Silo/requeue"),
    "rescrapeJourney": ("POST", "/api/acquisition/journeys/Silo/rescrape"),
    # The 200 family's witness. A read, because the plain success is what every
    # read answers and a rule holding only mutations would say nothing about
    # the fifty-five operations that make up the rest of the contract.
    "readFollows": ("GET", "/api/acquisition/followed"),
}


def declared_success_codes():
    """Reads the contract's declared success code for every operation.

    Read in PYTHON, from the file, while the layer reads the same file in
    TypeScript. That is deliberate and it is the whole value of this rule: two
    independent readers of one artefact can disagree, and a rule that asked the
    layer what it thought the contract said would be asking the accused.

    Returns:
        `{operationId: the lowest declared 2xx}`, for every operation that
        declares one.
    """
    document = json.loads(CONTRACT.read_text(encoding="utf-8"))
    found = {}
    for entry in document["paths"].values():
        for method, operation in entry.items():
            if method not in METHODS:
                continue
            codes = [
                int(code) for code in operation.get("responses", {})
                if code.isdigit() and FIRST_SUCCESS <= int(code) < FIRST_REDIRECT
            ]
            if codes:
                found[operation["operationId"]] = min(codes)
    return found


async def ask(page, method, path):
    """Asks the layer for one path and returns the status the response carried.

    Args:
        page: The prototype's page.
        method: The method, upper case.
        path: The path, with its parameters already resolved.

    Returns:
        The response's own status.
    """
    return await page.evaluate(
        """async ([method, path]) => {
             const answer = await fetch(path, { method });
             return answer.status;
           }""",
        [method, path],
    )


async def answered_status(page, operation_id):
    """The status the layer RECORDED for the last call of one operation.

    Args:
        page: The prototype's page.
        operation_id: The operation, as the contract names it.

    Returns:
        The status of its last recorded call, or None when it was never asked.
    """
    return await page.evaluate(
        """(operationId) => {
             const calls = window.__mocks.answered()
               .filter((call) => call.operationId === operationId);
             return calls.length === 0 ? null : calls[calls.length - 1].status;
           }""",
        operation_id,
    )


async def main():
    """Drives the layer's declared codes and records every verdict."""
    from playwright.async_api import async_playwright

    journal = Journal("R170 — the layer answers the success code its operation declares")
    declared = declared_success_codes()
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

        # ── the corpus ──────────────────────────────────────────────────────
        # THE FLOOR FIRST, because every hold below it is about operations this
        # list names: a rule exercising three of four declared families is
        # green about the fourth, and nothing else in the suite would say so.
        non_plain = {
            operation for operation, code in declared.items()
            if code != PLAIN_SUCCESS
        }
        journal.check(
            "every operation declaring a non-200 success is asked for here",
            non_plain <= set(ASKED_FOR),
            f"{len(non_plain)} declared non-200, unread: "
            f"{sorted(non_plain - set(ASKED_FOR)) or 'none'}",
        )
        families = {declared.get(operation) for operation in ASKED_FOR}
        journal.check(
            "the three success families are all exercised",
            families == set(declared.values()),
            f"asked for {sorted(family for family in families if family)}, "
            f"the contract declares {sorted(set(declared.values()))}",
        )

        # ── the families ────────────────────────────────────────────────────
        await page.evaluate("() => window.__mocks.reset()")
        for operation_id, (method, path) in sorted(ASKED_FOR.items()):
            wanted = declared.get(operation_id)
            carried = await ask(page, method, path)
            recorded = await answered_status(page, operation_id)
            journal.check(
                f"{operation_id} answers the {wanted} its contract declares",
                carried == wanted,
                f"{method} {path} answered {carried}, the contract declares {wanted}",
            )
            # ── the record ──────────────────────────────────────────────────
            journal.check(
                f"{operation_id}'s recorded status is the one it answered",
                recorded == carried,
                f"answered() reports {recorded}, the response carried {carried}",
            )

        # ── the dial ────────────────────────────────────────────────────────
        # A LATENCY IS NOT A STATUS. `outcomeFor` treats a scenario naming no
        # status as armed, so this is the branch that would answer 200 again if
        # the repair had touched only the other one.
        await page.evaluate("() => window.__mocks.reset()")
        await page.evaluate(
            """(milliseconds) => window.__mocks.setOperationOutcome(
                 "grabSeasonForFollow", { latencyMilliseconds: milliseconds })""",
            LATENCY_MILLISECONDS,
        )
        method, path = ASKED_FOR["grabSeasonForFollow"]
        with_latency = await ask(page, method, path)
        journal.check(
            "a scenario asking only for a latency still answers the declared code",
            with_latency == declared["grabSeasonForFollow"],
            f"answered {with_latency}, the contract declares "
            f"{declared['grabSeasonForFollow']}",
        )

        await page.evaluate("() => window.__mocks.reset()")
        await page.evaluate(
            """(status) => window.__mocks.setOperationOutcome(
                 "grabSeasonForFollow", { status })""",
            FAILURE_STATUS,
        )
        refused = await ask(page, method, path)
        journal.check(
            "a scenario asking for a failure still gets exactly it",
            refused == FAILURE_STATUS,
            f"asked for {FAILURE_STATUS}, answered {refused}",
        )
        await page.evaluate("() => window.__mocks.reset()")

        await context.close()
        await browser.close()

    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())
