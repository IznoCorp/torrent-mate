"""R91 — one event refreshes exactly what it should, and nothing else.

THIS IS L10'S FIRST « DONE WHEN » CLAUSE, made measurable. « Exactly what it
should and nothing else » is a sentence about the QUERY CACHE, so it is measured
against the query cache: what every entry held before the event, and what every
entry holds after it.

WHY IT DOES NOT READ THE MAP'S SOURCE, and this is the whole reason the rule
costs a browser. A map that reads correctly can still fan out wider than it
says: a prefix key one element too short covers siblings nobody listed. It
compiles. Its types agree. `["/api/staging/media"]` and
`["/api/staging/media", scenario]` are both valid `QueryKey`s and only one of
them is right — and which one is right is a JUDGEMENT about the data, not
something a type can hold. L09 paid for that shape three times in one wave
(B-124, B-125, B-136): a name that compiles and reads the wrong thing.

BOTH DIRECTIONS, FROM ONE COMPARISON. A too-wide invalidation and a missing one
are the same measurement read two ways — the set that moved against the set that
should have. A rule holding only « the right thing refreshed » is green over an
invalidation that refreshes the right thing AND everything else, which is the
defect that would quietly undo L09.

WHAT IT HOLDS:

  per rule      one event of each rule's type list, and the set of cache
                entries that moved is EXACTLY the set the rule declares.
  the unclaimed an event no rule names moves NOTHING, and is counted. An event
                nobody handles is not an error; an event nobody can count is how
                a map silently stops covering its subject.
  the burst     several events in one turn refresh the union of what each would,
                and nothing beyond it. A replay arrives as a burst, and
                production dropped events buried in one from three separate
                hooks (FRONTEND-DATA-03).
  the width     an event about one scenario's staging refreshes the OTHER
                scenario's staging too — which is this map's one deliberately
                wide key, held so that its width is a decision on the record
                rather than an accident nobody measured.

WHAT IT DOES NOT READ, said before what it does:

  - It does not read whether a surface RE-RENDERS. Invalidation is what this lot
    owns; what a component does with a fresh cache entry is L09's, and the
    oracle holds it.
  - It does not read the transport. A drop, a backoff and a replay walked for
    real are R93's.
  - It does not read the DRAWN conditions. R92 reads those.
  - It does not read whether the map is COMPLETE against the backend's forty
    event classes. That is a source question and it is
    `scripts/check-live-relay.py --arm map-completeness`'s, which costs no
    browser at all.
  - AND IT DOES NOT READ WHETHER A RULE REFRESHES THE RIGHT THING. It holds the
    IMPLEMENTATION against the DECLARATION: the keys it expects are read from
    each feature's `live.ts`, so a rule that declares the wrong key and
    invalidates that same wrong key passes. Measured, not assumed — pointing
    `ItemProgressed` at the pipeline status instead of staging leaves every
    per-rule hold green. What catches THAT is the map's key coverage
    (`check-live-relay.py --arm map-completeness`: every key a feature's
    `queries.ts` declares is named by a rule or exempted) and the `because` line
    a reviewer reads. Stated here rather than left to be discovered, because a
    rule whose limit is not written down is read as proving more than it does.
"""
import asyncio
import json
import pathlib
import re
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PHONE, Journal, open_page

ROOT = pathlib.Path(__file__).resolve().parent.parent
FEATURES = ROOT / "design" / "src" / "features"

# An event no rule in any feature's table names. It must move nothing, and it
# must be COUNTED — the two halves of « an unclaimed event is a decision, not a
# silence ». Deliberately not a real backend class name: a class the backend
# emits is one a map may legitimately claim tomorrow.
UNCLAIMED_TYPE = "NoRuleClaimsThisEvent"


def rule_objects(source):
    """Yields each `{ … }` literal of a rules array, brace-matched."""
    depth, start = 0, None
    for index, character in enumerate(source):
        if character == "{":
            if depth == 0:
                start = index
            depth += 1
        elif character == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                yield source[start:index + 1]
                start = None


def declared_rules():
    """Reads every feature's live rules out of its source.

    READ FROM THE SOURCE, NEVER FROM THE PAGE. Asking the running application
    what it thinks its rules are and then checking it obeys them is a rule that
    holds a program against itself: it would stay green over a table that had
    lost half its entries. The source is the statement; the browser is the
    measurement.

    Returns:
        A list of (feature, types, keys, because), one per declared rule.
    """
    found = []
    for path in sorted(FEATURES.glob("*/live.ts")):
        feature = path.parent.name
        source = path.read_text(encoding="utf-8")
        # THE EXEMPTIONS ARE NOT RULES, and this reader used to think they were.
        # They gained a `keys` list at phase 8 — the addresses a feature reads
        # that no event refreshes — and their shape then matched this pattern
        # exactly. R91 read three exemptions as rules with EMPTY type lists and
        # crashed on the first of them. The crash is the good outcome: the same
        # defect in `check-live-relay.py` printed a confident number that was
        # wrong instead, and only a reader comparing it against the tree would
        # ever have caught it.
        marker = re.search(r"^export const \w+LiveExemptions", source, re.MULTILINE)
        rules_only = source[:marker.start()] if marker else source
        # The key constants first, so a rule naming one can be resolved.
        constants = dict(re.findall(
            r"^(?:export )?const (\w+) = (\[[^\]]*\]);", source, re.MULTILINE))
        # EACH RULE OBJECT IS READ AS A UNIT, `types` and `keys` found inside it
        # in any order. The pattern used to require them adjacent and in that
        # order, and a non-greedy `.*?` does not FAIL on a violation — it walks
        # into the NEXT rule and pairs one rule's types with another's keys.
        # `check-live-relay.py` was repaired for this and its comment claimed
        # this reader had been too. It had not.
        for block in rule_objects(rules_only):
            found_types = re.search(r"types:\s*\[(.*?)\]", block, re.DOTALL)
            found_keys = re.search(r"keys:\s*\[(.*?)\]", block, re.DOTALL)
            if found_types is None or found_keys is None:
                continue
            types = re.findall(r'"([^"]+)"', found_types.group(1))
            # A RULE WITH A PREDICATE DECLARES THE PAYLOAD IT IS ABOUT. Emitting
            # an empty one against a predicate makes every such rule read as
            # « declared and nothing moved » — a measurement about this rule
            # rather than about the map. A predicate with no sample is refused
            # below, because an untestable rule is worse than an absent one.
            found_sample = re.search(r"sample:\s*\{(.*?)\}", block, re.DOTALL)
            sample = dict(re.findall(r'(\w+):\s*"([^"]*)"',
                                     found_sample.group(1))) if found_sample else {}
            has_predicate = re.search(r"^\s*when:", block, re.MULTILINE) is not None
            keys = [json.loads(constants[name].replace("'", '"'))
                    for name in re.findall(r"\b([A-Z_][A-Z0-9_]*_KEY)\b",
                                           found_keys.group(1))
                    if name in constants]
            if has_predicate and not sample:
                found.append((feature, types, keys, "MISSING SAMPLE"))
                continue
            found.append((feature, types, keys, sample))
    return found


# HOW AN INVALIDATION IS OBSERVED, and the first version of this rule got it
# wrong in a way worth recording. It compared each entry's
# `dataUpdatedAt/isInvalidated` before and after — and `isInvalidated` IS STICKY
# on a query nobody observes: it flips true on the first invalidation and stays,
# so every event after the first read as « nothing moved ». The rule reported
# ten violations against a map that was working.
#
# The cache announces its own invalidations. Subscribing says exactly which
# queries were invalidated by THIS event, once per event, with no state to
# compare and nothing sticky to reset.
WATCH = """
  () => {
    window.__fanout = [];
    window.__queries.getQueryCache().subscribe((event) => {
      if (event.type === "updated" && event.action?.type === "invalidate")
        window.__fanout.push(JSON.stringify(event.query.queryKey));
    });
    window.__fanoutSince = () => {
      const seen = [...new Set(window.__fanout)];
      window.__fanout = [];
      return seen;
    };
    // EVERY MEASUREMENT STARTS FROM A FRESH CACHE, and this is the second
    // stickiness this rule had to learn about. An invalidation is not
    // observable TWICE IN A ROW on a query nobody observes: the first marks it
    // invalidated, and the second is a no-op that emits no event at all. So the
    // rule's first working version measured the first event correctly and read
    // « nothing moved » for the nine after it — over a map that was working.
    //
    // Re-writing each entry with the data it already holds dispatches a success
    // and clears the flag, changing no content. It is the same principle the
    // engine states by its own name: driving is not a journey, and a
    // measurement must not depend on how many ran before it.
    window.__fanoutRefresh = () => {
      for (const entry of window.__queries.getQueryCache().getAll())
        // `setQueryData` RETURNS EARLY ON `undefined` — it never builds or
        // dispatches anything — so an entry whose read errored or is still
        // pending stays invalidated for ever and can never be observed to move
        // again. It would go silent mid-run, and going silent is always safe
        // under a subset check. A placeholder is written instead.
        window.__queries.setQueryData(
          entry.queryKey,
          entry.state.data === undefined ? { refreshed: true } : entry.state.data);
      window.__fanout = [];
    };
  }
"""


async def moved_by(page, event_type, sample):
    """Emits one event and returns which cache entries were invalidated."""
    return await page.evaluate(
        """async ({ type, sample }) => {
             window.__fanoutRefresh();
             const total = window.__queries.getQueryCache().getAll().length;
             window.__mocks.stream.emit(type, sample);
             await window.__mocks.quiet();
             return { total, moved: window.__fanoutSince() };
           }""",
        {"type": event_type, "sample": sample})


async def warm(page, keys):
    """Fills the cache, so « nothing moved » is a reading and not an empty set.

    THE SEED LIST IS DERIVED FROM THE MAP, never written out here. A corpus
    enumerated by hand is one of the forms this repository has already paid for:
    it goes stale the moment a rule names a key nobody added to the list, and
    the hold then reports « nothing moved » about a map that is working. Every
    key any rule declares gets an entry, and one that already has one is left
    alone — overwriting a key the open surface OBSERVES hands its component a
    shape it cannot render and unmounts the observer.

    Args:
        page: The page.
        keys: Every key any declared rule names.

    Returns:
        How many entries the cache holds afterwards.
    """
    return await page.evaluate(
        """async ({ keys }) => {
             window.__go("arr-loaded");
             await window.__mocks.quiet();
             await new Promise((r) => setTimeout(r, 200));
             // A RAW `fetch` MAKES NO CACHE ENTRY, and the first version of
             // this warm-up used six of them: the cache held only what the open
             // surface had asked for, and the « every scenario refreshes » hold
             // measured one entry where it needed two. Entries are seeded
             // through the cache itself.
             // SEEDED ONLY WHERE NOTHING IS WATCHING. Writing a placeholder
             // under a key the OPEN surface observes hands its component a
             // shape it cannot render, unmounts the observer, and leaves every
             // entry in the cache unobserved — which is what made the whole
             // measurement sticky. The keys below are ones this surface does
             // not read.
             const held = new Set(window.__queries.getQueryCache().getAll()
               .map((entry) => JSON.stringify(entry.queryKey)));
             const seed = (key) => {
               if (!held.has(JSON.stringify(key)))
                 window.__queries.setQueryData(key, { seeded: true });
             };
             for (const key of keys) seed(key);
             // A SIBLING UNDER EVERY DECLARED KEY. Without one, an
             // over-refresh is measurable BETWEEN address families and never
             // WITHIN one — and the narrowest keys in the map are exactly the
             // ones where within matters: the media sheet's own comment calls
             // an event about one title refreshing another's sheet the defect
             // to avoid, and there was never a second sheet to over-refresh.
             // SEEDED UNDER THE ADDRESS, not under the key. A sibling under a
             // declared key is by construction inside that key's prefix, so it
             // could never be an over-refresh — it only doubled the entries
             // that legitimately move and loosened the burst floor. Under the
             // ADDRESS it is armed for the day a rule declares a narrower key
             // than the address, which is exactly the media sheet's filed
             // demand.
             for (const key of keys) seed([key[0], "__sibling"]);
             // Two extra scenarios under staging's own address, so « every
             // scenario refreshes » has more than one to refresh.
             seed(["/api/staging/media", "dense"]);
             seed(["/api/staging/media", "sparse"]);
             seed(["/api/library/items", "", "", "recent", false]);
             await window.__mocks.quiet();
             return window.__queries.getQueryCache().getAll().length;
           }""",
        {"keys": keys})


def covers(moved, keys):
    """Says whether the entries that moved are EXACTLY those under `keys`.

    BOTH DIRECTIONS, AND THE FIRST VERSION ONLY COMPUTED ONE. It walked `moved`
    and asked whether each entry was declared — the « nothing else » half — and
    never walked the declared keys to ask whether each had moved. The docstring
    claimed both from the day it was written. Measured: changing
    `live-updates.ts` to invalidate `rule.keys.slice(0, 1)` silently stops
    refreshing five addresses across four features, and all 57 holds stayed
    green, because the only guard on the missing direction was « something
    moved » — satisfied by any single key of the union.

    THE SEPARATORS ARE PINNED. `json.dumps` writes `", "` between elements and
    escapes non-ASCII; `JSON.stringify` writes `","` and does neither. Every key
    in the map has one element today, so the difference has never shown — the
    day a two-element key lands (the media sheet's narrow key is a filed
    demand), the prefix would match nothing and this rule would report a false
    violation against a correct map.
    """
    wanted = {
        json.dumps(key, separators=(",", ":"), ensure_ascii=False)[:-1]
        for key in keys
    }
    # THE BOUNDARY IS EXPLICIT. A prefix ending in a string carries its closing
    # quote and is self-terminating; one ending in a NUMBER does not, so
    # `["/api/media","tvdb",12345` would match `…,123456]` — another title's
    # sheet reading as covered, which is the very case the media table names as
    # the one to avoid. The day the narrow key lands, this is where it bites.
    def under(entry, prefix):
        return entry == f"{prefix}]" or entry.startswith(f"{prefix},")

    for entry in moved:
        if not any(under(entry, prefix) for prefix in wanted):
            return False, f"{entry} moved and no rule key covers it"
    for prefix in sorted(wanted):
        if not any(under(entry, prefix) for entry in moved):
            return False, (f"{prefix}] is declared and nothing under it moved — "
                           "a rule that refreshes a SUBSET of what it declares "
                           "leaves the rest stale for the life of the process")
    return True, ""


async def hold(journal):
    """Emits one event per rule and reads the cache on both sides."""
    rules = declared_rules()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser, **PHONE)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # THE CORPUS IS PRINTED AND FLOORED. A rule that read no `live.ts` at
        # all would emit nothing, compare nothing and report no violation —
        # which is the shape this repository has paid for forty times.
        journal.check(
            "there are rules to hold at all",
            len(rules) > 0,
            f"{len(rules)} rule(s) declared across "
            f"{len({feature for feature, *_ in rules})} feature(s)")
        if not rules:
            await browser.close()
            return

        await page.evaluate(WATCH.strip())
        declared_keys = [key for _, _, rule_keys, _ in rules for key in rule_keys]
        entries = await warm(page, declared_keys)
        held = await page.evaluate(
            """() => window.__queries.getQueryCache().getAll()
                 .map((entry) => JSON.stringify(entry.queryKey))""")
        unmeasured = sorted({
            json.dumps(key, separators=(",", ":"), ensure_ascii=False)[:-1]
            for key in declared_keys
            if not any(one.startswith(
                json.dumps(key, separators=(",", ":"), ensure_ascii=False)[:-1])
                for one in held)
        })
        # THE FLOOR IS THE DECLARED KEYS, not a number. It used to be
        # `entries >= len(rules)` — a count of cache entries against a count of
        # rules, two quantities with no relation: seven declared keys could have
        # failed to seed and the floor would still have passed, and a key with
        # no entry is a key this rule cannot measure at all.
        journal.check(
            "every declared key has an entry to move",
            not unmeasured,
            f"{entries} cache entr(ies), and {len(unmeasured)} declared key(s) "
            f"have none: {unmeasured} — a key with no entry is a rule this "
            "measurement silently skips")

        # ONE EVENT FIRES EVERY RULE THAT NAMES IT, so what it must refresh is
        # the UNION of their keys — never one rule's. R91's own first version
        # compared against a single rule and failed `PipelineEnded` twice, which
        # is two rules on one event, deliberately: what they refresh differs and
        # so does why. A rule that cannot describe its subject is not measuring
        # it.
        journal.check(
            "every rule with a predicate declares the payload it is about",
            not any(sample == "MISSING SAMPLE" for _, _, _, sample in rules),
            "a `when:` with no `sample:` cannot be driven — this rule would emit "
            "an empty payload, the predicate would refuse, and the key would "
            "read as declared-and-unmoved")

        # ONE EMIT PER RULE, WITH THAT RULE'S OWN SAMPLE. Merging every rule's
        # sample into one payload per type made the verdict depend on SOURCE
        # ORDER — last writer wins — and it made a predicate's deletion
        # invisible: one payload happening to satisfy two predicates covers both
        # keys whether or not either predicate is still there.
        by_rule = []
        for feature, types, keys, sample in rules:
            for event_type in types:
                by_rule.append((feature, event_type, keys,
                                sample if isinstance(sample, dict) else {}))

        for feature, event_type, keys, payload in sorted(
                by_rule, key=lambda one: (one[1], one[0])):
            named = feature
            seen = await moved_by(page, event_type, payload)
            # A RULE'S OWN KEYS ARE A SUBSET of what its event moves, because
            # other rules on the same type fire too. What is held per rule is
            # the direction that belongs to it: everything IT declares moved.
            _, complaint = covers(seen["moved"], keys)
            missing = [prefix for prefix in {
                json.dumps(key, separators=(",", ":"), ensure_ascii=False)[:-1]
                for key in keys}
                if not any(entry == f"{prefix}]" or entry.startswith(f"{prefix},")
                           for entry in seen["moved"])]
            journal.check(
                f"{named}: {event_type} refreshes everything it declares",
                not missing,
                f"{missing} declared and nothing under them moved, out of "
                f"{seen['moved']} — a rule that refreshes a SUBSET of what it "
                "declares leaves the rest stale for the life of the process")
            journal.check(
                f"{named}: {event_type} refreshes something",
                len(seen["moved"]) > 0,
                f"{len(seen['moved'])} of {seen['total']} cache entr(ies) "
                "refreshed — a rule that refreshes nothing is a rule that is "
                "not wired")

        # AND « NOTHING ELSE », WHICH IS A QUESTION ABOUT THE TYPE. Per rule it
        # cannot be asked — every other rule on the same type fires too, so a
        # rule's own keys are a subset by construction. The union is where the
        # over-wide direction lives, and losing it when the per-rule holds
        # arrived would have left half the contract clause unmeasured.
        union: dict[str, list] = {}
        for _, event_type, keys, payload in by_rule:
            wanted, sample = union.setdefault(event_type, [[], {}])
            wanted.extend(keys)
            sample.update(payload)
        for event_type, (keys, payload) in sorted(union.items()):
            seen = await moved_by(page, event_type, payload)
            exact, complaint = covers(seen["moved"], keys)
            journal.check(
                f"{event_type} refreshes nothing beyond what its rules declare",
                exact,
                complaint or f"moved {seen['moved']} against "
                f"{[json.dumps(k) for k in keys]}")

        # AN UNCLAIMED EVENT MOVES NOTHING, AND IS COUNTED.
        unclaimed = await page.evaluate(
            """async ({ type }) => {
                 window.__fanoutRefresh();
                 const countBefore = window.__relay.unmatchedCount();
                 window.__mocks.stream.emit(type, {});
                 await window.__mocks.quiet();
                 return {
                   still: window.__fanoutSince().length === 0,
                   counted: window.__relay.unmatchedCount() - countBefore,
                   last: window.__relay.unmatched().slice(-1)[0],
                 };
               }""",
            {"type": UNCLAIMED_TYPE})
        journal.check(
            "an event no rule claims moves nothing",
            unclaimed["still"], "a cache entry moved for an unclaimed event")
        journal.check(
            "and it is counted, by name",
            unclaimed["counted"] == 1 and unclaimed["last"] == UNCLAIMED_TYPE,
            f"the unmatched list grew by {unclaimed['counted']} and ends with "
            f"{unclaimed['last']!r} — an event nobody can count is how a map "
            "silently stops covering its subject")

        # A BURST REFRESHES THE UNION, AND NOTHING BEYOND IT.
        journal.check(
            "every declared rule names at least one event",
            all(types for _, types, _, _ in rules),
            f"{sum(1 for _, types, _, _ in rules if not types)} rule(s) name no "
            "event — a rule with an empty type list is read by nothing and "
            "refreshes nothing")
        burst_types = [types[0] for _, types, _, _ in rules if types]
        burst_payload = {}
        for _, _, _, sample in rules:
            if isinstance(sample, dict):
                burst_payload.update(sample)
        burst_keys = [key for _, _, keys, _ in rules for key in keys]
        burst = await page.evaluate(
            """async ({ types, payload }) => {
                 window.__fanoutRefresh();
                 window.__mocks.stream.emitBurst(
                   types.map((type) => ({ type, data: payload })));
                 await window.__mocks.quiet();
                 return window.__fanoutSince();
               }""",
            {"types": burst_types, "payload": burst_payload})
        exact, complaint = covers(burst, burst_keys)
        distinct = len({json.dumps(key, separators=(",", ":"), ensure_ascii=False)
                        for key in burst_keys})
        journal.check(
            "a burst refreshes the union of its rules, and nothing beyond it",
            exact and len(burst) >= distinct,
            complaint or f"a burst of {len(burst_types)} moved {len(burst)} "
            f"entr(ies) against {distinct} distinct declared key(s): {burst} — "
            "floored at « something moved », this hold passed over a relay that "
            "kept only the newest frame of a burst, which is the defect it "
            "names (FRONTEND-DATA-03)")

        # THE ONE DELIBERATELY WIDE KEY, held so its width is on the record.
        wide = await page.evaluate(
            """async () => {
                 window.__fanoutRefresh();
                 window.__mocks.stream.emit("ItemProgressed", { status: "moved" });
                 await window.__mocks.quiet();
                 return window.__fanoutSince().filter(
                   (key) => key.startsWith('["/api/staging/media"'));
               }""")
        journal.check(
            "staging's key is wide ON PURPOSE: every scenario refreshes",
            len(wide) >= 4,
            f"{len(wide)} staging entr(ies) refreshed, against the four the "
            "warm-up seeds — a threshold of two was reached for free by the "
            "surface's own entries, so it passed even if both seeds failed. "
            "A key naming one "
            "scenario would leave the other stale until the process ended, and "
            "`staleTime: Infinity` means that is forever (B-154)")

        await page.evaluate("()=>{ window.__relay.reset(); window.__mocks.reset(); }")
        await context.close()
        await browser.close()
    journal.summary(errors)


def main():
    journal = Journal("R91 — one event refreshes exactly what it should")
    asyncio.run(hold(journal))


if __name__ == "__main__":
    main()
