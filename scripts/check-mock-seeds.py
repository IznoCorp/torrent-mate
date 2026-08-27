#!/usr/bin/env python3
"""Holds the correspondence between the maquette's mock seeds and its fixtures.

THE CLAUSE THIS GUARD EXISTS FOR, and it is L08's binding one: every shape the
mock layer serves is SEEDED FROM THE FIXTURE IT REPLACES. A mock returning
exactly what the current fixture returns makes L09 provable — wiring a surface
to it renders the same thing, so the oracle proves the wiring at zero
divergence. Invented mock data would forfeit that proof for nothing.

WHAT EACH ARM DOES NOT READ, asked before the arms were written and answered
here rather than left for a reader to reconstruct. A guard is green for two
reasons and only one of them is good.

  classification  Reads the engine's declared fixtures against the register,
                  both ways. It does NOT read what the seeds contain. It holds a
                  NAMED INVENTORY and never a count: a floor placed at today's
                  number is satisfied by construction on the day it is written
                  and can only ever catch a later decrease — the shape B-075
                  found five times over.

  correspondence  Re-derives every seed from `legacy.js` and compares it, byte
                  for byte, with the committed one. It does NOT read the
                  handlers, so a handler ignoring its seed passes here. It is
                  also the arm that goes red after `refresh-maquette-fixture.py`
                  rewrites `FOLLOWS` from the live database — which is wanted.

  lossless        Compares the multiset of LEAF VALUES on each side. A dropped
                  key takes its values with it; an altered value shows directly.
                  It does NOT see a projection that never ran — an unprojected
                  family moves no leaf and passes — and it does not see two keys
                  of the same type swapped. Both were live: two families shipped
                  unprojected while the builder reported success and lossless.
                  The arm below is what caught them.

  schema          Validates every seed against the contract schema of the
                  operation that names it. This is what sees an unprojected
                  family, a mistyped field and a regroup that did not happen. It
                  does NOT judge whether the CONTRACT is right — only that the
                  seed and the contract agree.

  provenance      Holds the four-way correspondence between the register, the
                  seed files and the contract's `x-seeded-from`. It does NOT
                  read a value; it reads that nothing is orphaned in either
                  direction.

  generated       Holds the generated contract types against the contract, by
                  structure. It does NOT prove byte-identity — that is
                  `make check-contract-types`, which needs the generator and
                  runs only where it is installed. This half runs everywhere,
                  which is where the two exemptions that rest on it are read.

  handlers        Refuses a data literal in a handler module — the one failure
                  every other arm here stays green over. It does NOT follow what
                  a handler RETURNS: with no literal to build from, a payload
                  has nowhere to come from but a seed or the request, and that
                  is what it holds rather than the return value itself.

Exit code: 0 when every arm run is clean, 1 otherwise.

Usage:
    python3 scripts/check-mock-seeds.py                 # every arm
    python3 scripts/check-mock-seeds.py --arm schema    # one of them
    python3 scripts/check-mock-seeds.py --list          # the inventory it holds
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAQUETTE = ROOT / "frontend" / "maquette"
REGISTER = MAQUETTE / "fixture-register.json"
CONTRACT = MAQUETTE / "contract" / "openapi.json"
SEEDS = MAQUETTE / "design" / "src" / "mocks" / "seeds"
BUILDER = ROOT / "scripts" / "build-mock-seeds.py"

METHODS = ("get", "post", "put", "patch", "delete")

# The floor under the module count the handlers arm reads. A reader that finds
# nothing and reports clean is the shape this whole guard is written against, so
# the arm refuses a tree it cannot recognise rather than passing over it.
MINIMUM_PAYLOAD_MODULES = 8


def builder():
    """Loads the seed builder as a module, so both read one implementation.

    Two copies of a projection are two places for one of them to drift, and the
    drift would be invisible: each copy would still be internally consistent.
    """
    specification = importlib.util.spec_from_file_location("mock_seed_builder", BUILDER)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def register() -> dict:
    """The classification of every fixture family."""
    return json.loads(REGISTER.read_text(encoding="utf-8"))["families"]


def contract() -> dict:
    """The maquette's own contract."""
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def operations(document: dict):
    """Yields `(operationId, operation)` for every operation the contract declares."""
    for path in document["paths"].values():
        for method, operation in path.items():
            if method in METHODS:
                yield operation["operationId"], operation



# The `answers` expression, and it is deliberately small: `Name` is a contract
# schema, a lowercase name is a primitive type, `X[]` is a list of X, and `{X}`
# is a map whose values are X. Anything richer would be a second schema language
# beside the contract's own, which is one more thing to keep in step.
def schema_of(expression: str) -> dict:
    """Turns one `answers` expression into the JSON Schema it denotes.

    Args:
        expression: The expression, as `fixture-projections.json` writes it.

    Returns:
        The schema.
    """
    text = expression.strip()
    if text.startswith("{") and text.endswith("}"):
        return {"type": "object", "additionalProperties": schema_of(text[1:-1])}
    if text.endswith("[]"):
        return {"type": "array", "items": schema_of(text[:-2])}
    if text[:1].islower():
        return {"type": text}
    return {"$ref": f"#/components/schemas/{text}"}



def strictly(schema: object) -> object:
    """Returns the schema with every declared object closed to unknown properties.

    WHY THE GUARD TIGHTENS WHAT THE CONTRACT DELIBERATELY LEAVES OPEN. A real
    contract stays open for forward compatibility: a client must tolerate a
    field it has not heard of. But a SEED carrying a field the contract does not
    declare means the contract is incomplete, and an open schema reports that as
    a pass. The closing happens here, in the reader, and never in the document.

    A schema that already says something about additional properties is left
    exactly as it is — `{X}` maps and `ProviderIds` are open on purpose.

    Args:
        schema: Any part of the contract.

    Returns:
        The same structure, with `additionalProperties: false` added wherever
        `properties` is declared and nothing was said about the rest.
    """
    if isinstance(schema, dict):
        tightened = {key: strictly(value) for key, value in schema.items()}
        if "properties" in tightened and "additionalProperties" not in tightened:
            tightened["additionalProperties"] = False
        return tightened
    if isinstance(schema, list):
        return [strictly(item) for item in schema]
    return schema


def arm_classification(module) -> int:
    """Refuse a fixture family the register does not name, and the reverse.

    Returns:
        The number of names out of step.
    """
    declared = set(register())
    found = set(module.fixtures())
    unclassified = sorted(found - declared)
    # A FAMILY THE REGISTER DECLARES `converted` IS EXPECTED TO BE ABSENT. L09
    # wires a surface and deletes the fixture it read (D5), so « the engine no
    # longer declares it » stops being a defect for that family and becomes the
    # record of a decision. It is NOT a way to silence the check: the entry
    # names the wave and the surface, and the count is printed either way, so a
    # family that vanished without anybody declaring it still fails.
    converted = {name for name, entry in register().items() if entry.get("converted")}
    vanished = sorted(declared - found - converted)
    unrecorded = sorted(converted & found)
    # THE CLASS IS HELD, and only the NAMES were. The counts live in the
    # register beside the classification, so a family moved from `served` to
    # `interface` has to be moved in two places by a hand that meant it —
    # visible in a diff instead of silent.
    counts: dict[str, int] = {}
    for entry in register().values():
        counts[entry["class"]] = counts.get(entry["class"], 0) + 1
    counts["total"] = len(declared)
    document = json.loads(REGISTER.read_text(encoding="utf-8"))
    recorded = document["$counts"]
    miscounted = recorded != counts
    # The literals inside ANONYMOUS functions are excluded from the inventory on
    # purpose, and the exclusion is a figure somebody compares rather than one
    # somebody printed: it could go from one to nine with every guard green.
    anonymous = int(module.subprocess.run(
        ["node", str(module.EXTRACTOR), "--anonymous"],
        capture_output=True, text=True, cwd=ROOT, check=True).stdout.strip())
    held = document.get("$anonymous", {}).get("count")
    if held != anonymous:
        miscounted = True
        print(f"    the register holds {held} anonymous literal(s) and the engine declares "
              f"{anonymous} — a family excluded from the inventory has appeared or gone",
              file=sys.stderr)
    print(f"  classification: {len(found)} fixture(s) in the engine, "
          f"{len(declared)} in the register, {len(converted)} converted, "
          f"{len(unclassified) + len(vanished) + len(unrecorded) + int(miscounted)} "
          f"out of step")
    for name in unrecorded:
        print(f"    {name}: the register calls it converted and the engine still "
              f"declares it — a fixture that outlived its own removal",
              file=sys.stderr)
    if miscounted:
        print(f"    the register's $counts says {recorded} and its families are {counts} — "
              f"a class was changed and the tally beside it was not",
              file=sys.stderr)
    for name in unclassified:
        print(f"    {name}: the engine declares it and the register does not "
              f"classify it", file=sys.stderr)
    for name in vanished:
        print(f"    {name}: the register classifies it and the engine no longer "
              f"declares it", file=sys.stderr)
    return len(unclassified) + len(vanished) + len(unrecorded) + int(miscounted)


def arm_correspondence(module) -> int:
    """Refuse a committed seed that differs from the fixture it was taken from.

    Returns:
        The number of seeds that have drifted.
    """
    built = module.build()
    drifted: list[str] = []
    compared = 0
    for path, text in built.items():
        target = Path(path)
        if not target.is_file():
            drifted.append(f"{target.name}: missing — the family is served and has no seed")
        elif target.read_text(encoding="utf-8") != text:
            drifted.append(f"{target.name}: differs from the fixture it was taken from. "
                           f"Rebuild with `python3 scripts/build-mock-seeds.py --write`")
        else:
            compared += 1
    # A CONVERTED FAMILY'S SEED IS STILL CLAIMED, and it can no longer be
    # re-derived: the engine's literal it came from is gone. Its file is
    # exempted from « no family claims it » BY NAME, from the register's own
    # declaration, and the count is printed — an arm that compared 43 where it
    # used to compare 46 must say so, or the shrinking is the silent kind.
    kept = {str(module.file_for(name)) for name in module.converted_families()}
    for existing in sorted(SEEDS.glob("*.json")):
        if str(existing) not in built and str(existing) not in kept:
            drifted.append(f"{existing.name}: no family claims it")
    print(f"  correspondence: {compared} seed(s) re-derived from legacy.js and "
          f"identical, {len(kept)} no longer re-derivable (converted — held by the "
          f"contract's schema and by the oracle instead), {len(drifted)} out of step")
    for entry in drifted:
        print(f"    {entry}", file=sys.stderr)
    return len(drifted)


def arm_lossless(module) -> int:
    """Refuse a projection that loses or invents a value.

    IT IS NOT INDEPENDENT OF THE BUILDER, and it said it was. It calls the same
    projection, in the same module — a derivation compared against the thing it
    was derived from. What it adds is that the comparison is REPORTED with its
    figures rather than only raising, and that it runs BEFORE the arm whose
    builder call would exit first. The independent reader of a projection is
    `schema`, which compares the result against a shape declared elsewhere.

    Returns:
        The number of families whose leaf values do not match.
    """
    declared = json.loads(module.PROJECTIONS.read_text(encoding="utf-8"))
    shorthands = declared["$shorthands"]
    broken: list[str] = []
    values = 0
    for name in module.seeded_families():
        plan = module.projection_for(name, declared["families"][name], shorthands)
        before = sorted(map(repr, module.leaves(module.fixture(name))))
        after = sorted(map(repr, module.leaves(module.seed_of(name, plan))))
        values += len(before)
        if before != after:
            broken.append(f"{name}: {len(before)} leaf value(s) in, {len(after)} out")
    print(f"  lossless: {values} leaf value(s) compared across "
          f"{len(module.seeded_families())} family(ies), {len(broken)} that do not match")
    for entry in broken:
        print(f"    {entry}", file=sys.stderr)
    return len(broken)


def arm_schema(module) -> int:
    """Refuse a seed that does not answer the contract schema naming it.

    THIS IS THE ARM THAT SEES AN UNPROJECTED FAMILY. The lossless arm cannot:
    a family whose keys were never renamed moves no leaf value, so it passes
    there. Two shipped that way while the builder reported success.

    Returns:
        The number of seeds that do not validate.
    """
    try:
        import jsonschema
    except ImportError:  # pragma: no cover — declared in pyproject's dev extras
        print("    jsonschema is not installed; it is declared in pyproject's dev "
              "extras and this arm cannot answer without it", file=sys.stderr)
        return 1

    document = contract()
    declared = json.loads(module.PROJECTIONS.read_text(encoding="utf-8"))["families"]
    failures: list[str] = []
    validated = 0
    # THE CONVERTED FAMILIES ARE VALIDATED TOO, and leaving them out was the
    # mistake this comment exists to stop somebody repeating. A converted
    # family's seed can no longer be re-derived from the engine — that arm says
    # so by name — and this one is what still holds it. Dropping it here would
    # have made « held by the contract's schema » a sentence the code did not
    # honour, on the very seeds that lost their other reader.
    for name in module.seeded_families() + module.converted_families():
        expression = declared.get(name, {}).get("answers")
        if not expression:
            failures.append(f"{name}: no `answers` declared, so nothing can be validated "
                            f"against it — which would read as a pass")
            continue
        seed = json.loads(module.file_for(name).read_text(encoding="utf-8"))
        schema = dict(schema_of(expression))
        schema["components"] = strictly(document["components"])
        try:
            jsonschema.validate(instance=seed, schema=schema,
                                cls=jsonschema.Draft202012Validator)
            validated += 1
        except jsonschema.ValidationError as error:
            where = "/".join(str(part) for part in error.absolute_path) or "<root>"
            failures.append(f"{name} does not answer {expression} at {where}: "
                            f"{error.message[:200]}")
        except jsonschema.SchemaError as error:  # pragma: no cover
            failures.append(f"the schema {expression} is itself invalid: "
                            f"{error.message[:200]}")
    print(f"  schema: {validated} seed(s) validated against the contract shape each "
          f"declares it answers — every declared object closed to unknown "
          f"properties, so an incomplete contract is a failure and not a pass — "
          f"{len(failures)} that do not answer")
    for entry in failures:
        print(f"    {entry}", file=sys.stderr)
    return len(failures)


def arm_provenance(module) -> int:
    """Hold the register, the seed files and the contract in step, all ways.

    Returns:
        The number of orphans, in either direction.
    """
    classified = register()
    served = {name for name, entry in classified.items()
              if entry["class"] in module.SEEDED_CLASSES}
    on_disk = {path.stem for path in SEEDS.glob("*.json")}
    expected = {module.file_for(name).stem for name in served}
    named = {family for _, operation in operations(contract())
             for family in operation.get("x-seeded-from", [])}

    problems: list[str] = []
    # EVERY OPERATION CARRIES EXACTLY ONE OF THE TWO, and that is what keeps
    # « nothing was invented here » apart from « nobody looked ». An
    # acknowledgement, a count derived from the request, a state token from the
    # contract's own enum: each says so in `x-unseeded`, in as many words.
    both, neither = [], []
    for operation_id, operation in operations(contract()):
        seeded = bool(operation.get("x-seeded-from"))
        unseeded = bool(operation.get("x-unseeded"))
        if seeded and unseeded:
            both.append(operation_id)
        elif not seeded and not unseeded:
            neither.append(operation_id)
    for operation_id in sorted(neither):
        problems.append(f"{operation_id}: carries neither x-seeded-from nor x-unseeded — "
                        f"nothing says whether its response is seeded or why it cannot be")
    for operation_id in sorted(both):
        problems.append(f"{operation_id}: carries both x-seeded-from and x-unseeded, which "
                        f"cannot both be true")
    for stem in sorted(on_disk - expected):
        problems.append(f"{stem}.json: a seed no served family claims")
    for stem in sorted(expected - on_disk):
        problems.append(f"{stem}.json: a served family with no seed")
    for name in sorted(served - named):
        problems.append(f"{name}: served, and no operation's x-seeded-from names it — "
                        f"a seed nothing will ever serve")
    for name in sorted(named - served):
        problems.append(f"{name}: named by an operation's x-seeded-from and not "
                        f"classified as served or asset")
    declared_operations = sum(1 for _ in operations(contract()))
    print(f"  provenance: {len(served)} served family(ies), {len(on_disk)} seed file(s), "
          f"{len(named)} named by an operation, {declared_operations} operation(s) each "
          f"declaring whether its response is seeded, {len(problems)} orphan(s)")
    for entry in problems:
        print(f"    {entry}", file=sys.stderr)
    return len(problems)



# What a handler module is allowed to hold besides an imported seed. Each is a
# CONTROL value — how the layer works — never a value the interface displays.
#
# The list is short on purpose. A handler carrying its own data is the one
# failure every other arm here stays green over: the seeds could be perfect,
# the contract perfect, the classification total, and a handler could still
# return a hand-typed object.
HANDLER_LITERAL_ALLOWANCES = (
    # HTTP methods and the contract's own path templates and operationIds.
    "operationId", "method", "template",
)


def arm_handlers(module) -> int:
    """Refuse a data literal in a handler module.

    WHAT IT READS. Every string and number literal in `mocks/handlers/*.ts`,
    with comments and imports removed, and it refuses any that is not one of:
    a path template the contract declares, an operationId it declares, an HTTP
    method, a property name some contract schema declares, or a number that is
    an HTTP status. Everything else is a value someone typed.

    WHAT IT DOES NOT READ. It does not follow what a handler RETURNS — a
    handler could import a seed and answer something else built from it, and
    this arm would not know. What it forbids is the raw material: with no
    literal to build from, a payload has nowhere to come from but a seed or the
    request.

    Args:
        module: The seed builder, for the paths it already knows.

    Returns:
        The number of literals no allowance covers.
    """
    # THE MODULES THAT BUILD A PAYLOAD, and it is a scope rather than a
    # convenience. `handlers/` answers the operations; `state.ts` assembles what
    # every read returns and was UNREAD — a hand-typed row added there passed
    # all six arms, which is the exact failure this arm exists for.
    #
    # WHAT IT DOES NOT READ, named rather than left silent: `index.ts` and
    # `router.ts` build responses and failure messages, never payloads, and
    # their prose is a tool's own English; `scenario.ts` holds the frozen clock
    # and the latencies, which R85 holds against the engine instead; `seeds/`
    # is data by definition; `contract-types.d.ts` is generated.
    layer = SEEDS.parent
    handlers = sorted(layer.glob("handlers/*.ts")) + sorted(layer.glob("handlers/*.tsx"))
    if (layer / "state.ts").is_file():
        handlers.append(layer / "state.ts")
    if len(handlers) < MINIMUM_PAYLOAD_MODULES:
        print(f"    mocks/ holds {len(handlers)} payload module(s), fewer than the "
              f"{MINIMUM_PAYLOAD_MODULES} this arm exists to read — a reader that finds "
              f"nothing and reports clean is the shape this whole guard is written "
              f"against", file=sys.stderr)
        return 1

    document = contract()
    allowed = set(document["paths"])
    allowed |= {operation_id for operation_id, _ in operations(document)}
    allowed |= {method.upper() for method in METHODS}
    # `typeof x === "object"` is the LANGUAGE, not a value. So is the header a
    # JSON response carries.
    allowed |= {"object", "string", "number", "boolean", "undefined",
                "content-type", "application/json"}
    # A handler naming a contract SCHEMA to borrow its type — `components
    # ["schemas"]["DecisionState"]` — is quoting the contract exactly as it does
    # when it writes an operationId. The section names come with them, because
    # the index expression cannot be written without them.
    allowed |= set(document["components"])
    allowed |= set(document["components"]["schemas"])

    # Every property name, every parameter name and every ENUM VALUE the
    # contract declares. An enum token is the contract's own vocabulary — it is
    # what `PipelineState` and `DecisionState` exist to say — so a handler
    # writing one is quoting the contract rather than inventing a datum.
    def collect(node: object) -> None:
        if isinstance(node, dict):
            allowed.update(node.get("properties", {}))
            allowed.update(node.get("enum", []))
            if node.get("in") in ("query", "path") and isinstance(node.get("name"), str):
                allowed.add(node["name"])
            for value in node.values():
                collect(value)
        elif isinstance(node, list):
            for value in node:
                collect(value)
    collect(document)

    # A LITERAL HOLDING A BACKSLASH IS STILL A LITERAL. The first pattern
    # excluded the escape character from the body, so `"a\\b"` matched nothing
    # and was never examined at all — invisible rather than allowed.
    strings = re.compile(
        r'"((?:[^"\\]|\\.)*)"' r"|'((?:[^'\\]|\\.)*)'" r"|`((?:[^`\\]|\\.)*)`")
    numbers = re.compile(r"(?<![\w.])(\d+)(?![\w.])")
    # THE STATUSES THE CONTRACT DECLARES, and not every number between 100 and
    # 599. That window let `{ ownedEpisodes: 247 }` through — a hand-typed count
    # inside the range, under the arm written to refuse displayed values.
    statuses = {int(code) for _, operation in operations(document)
                for code in operation.get("responses", {}) if code.isdigit()}

    offenders: list[str] = []
    examined = 0
    for path in handlers:
        source = path.read_text(encoding="utf-8")
        # Imports name seed FILES, and comments are prose. Neither is a payload.
        body = "\n".join(
            "" if line.lstrip().startswith(("import ", "//", "*", "/*")) else line
            for line in source.splitlines())
        # A value that is the initializer of an UPPER_SNAKE_CASE constant is a
        # DECLARED control value, which is what the rule asks for — the arm has
        # to be able to SEE that, or the rule would forbid what it demands. A
        # string qualifies as much as a number: the rule asks for a named
        # constant, not for a particular type of one.
        named = {int(value) for value in re.findall(r"\bconst [A-Z][A-Z_]* = (\d+)", body)}
        named_text = set(re.findall(r'\bconst [A-Z][A-Z_]*(?:: \w+)? = "([^"]*)"', body))
        for match in strings.finditer(body):
            value = next(group for group in match.groups() if group is not None)
            examined += 1
            # THE EMPTY STRING IS AN ABSENCE, not a value: it is what a default
            # and a comparison are written with. Where a payload ANSWERS one —
            # `readVersion` does, because the maquette is not a server and has
            # no version — the operation's `x-unseeded` is what has to justify
            # it, and the provenance arm holds that every operation carries one.
            if value == "" or value in allowed or value in named_text:
                continue
            offenders.append(f"{path.name}: the literal {value!r} is not a path, an "
                             f"operationId, a method, a contract property name, a token of a "
                             f"contract enum, or the initializer of a named constant")
        # A NUMBER INSIDE A STRING IS NOT A NUMBER. `"2026-08-10"` is one
        # declared value, and scanning the raw text read three magic numbers
        # out of it — the arm reporting its own blindness as a finding.
        outside_strings = strings.sub('""', body)
        for match in numbers.finditer(outside_strings):
            examined += 1
            number = int(match.group(1))
            # 0 and 1 are arithmetic — an index, an increment, a first element.
            # Neither is a value anyone reads off a screen.
            if number in (0, 1) or number in named or number in statuses:
                continue
            offenders.append(f"{path.name}: the number {number} is neither a status the "
                             f"contract declares, nor an index, nor the initializer of a "
                             f"named constant. A displayed value comes from a seed")
    print(f"  handlers: {len(handlers)} payload module(s), {examined} literal(s) read, "
          f"{len(offenders)} that no allowance covers")
    for entry in offenders:
        print(f"    {entry}", file=sys.stderr)
    return len(offenders)



def arm_generated(module) -> int:
    """Hold the generated contract types against the contract itself.

    WHY THIS EXISTS BESIDE `make check-contract-types`. That target regenerates
    the file and refuses any difference — the strongest proof there is, and it
    needs `node` and the generator, so it runs in `make check` on a machine that
    has both and in NO continuous-integration job. Meanwhile TWO guards grant
    that file an exemption ON THE GROUNDS THAT NOBODY WRITES IT, and both of
    them run on the runner where the proof does not.

    So the structural half runs everywhere: the file carries the generator's own
    banner, and it declares an entry for every operation the contract does and
    none the contract does not. It is weaker than byte-identity and it is not a
    substitute for it — a hand edit inside an operation's body would pass here
    and fail there. Both are named where the exemptions are granted.

    Args:
        module: The seed builder, for the paths it already knows.

    Returns:
        The number of ways the file and the contract disagree.
    """
    generated = SEEDS.parent / "contract-types.d.ts"
    if not generated.is_file():
        print(f"    {generated.name} is missing, and two guards exempt it from their "
              f"ceilings on the grounds that a generator writes it", file=sys.stderr)
        return 1
    text = generated.read_text(encoding="utf-8")
    problems: list[str] = []
    if "auto-generated by openapi-typescript" not in text:
        problems.append(f"{generated.name} does not carry the generator's banner, so nothing "
                        f"here says a generator wrote it")
    declared = {operation_id for operation_id, _ in operations(contract())}
    # The generator emits one member per operation inside `export interface
    # operations`, which is the last block of the file.
    block = text.split("export interface operations", 1)
    present = set()
    if len(block) == 2:
        present = set(re.findall(r"^    (\w+): \{", block[1], re.M))
    for missing in sorted(declared - present):
        problems.append(f"{missing} is an operation the contract declares and the generated "
                        f"types do not carry — the file is behind the contract")
    for extra in sorted(present - declared):
        problems.append(f"{extra} is in the generated types and the contract does not declare "
                        f"it — the file is ahead of the contract, or somebody wrote in it")
    print(f"  generated: {len(present)} operation(s) in the types against {len(declared)} in "
          f"the contract, {len(problems)} disagreement(s). Byte-identity is "
          f"`make check-contract-types`, which needs the generator and runs where it is")
    for entry in problems:
        print(f"    {entry}", file=sys.stderr)
    return len(problems)


ARMS = {
    "classification": arm_classification,
    "generated": arm_generated,
    "handlers": arm_handlers,
    "correspondence": arm_correspondence,
    "lossless": arm_lossless,
    "provenance": arm_provenance,
    "schema": arm_schema,
}


# The order the arms run in when all of them do. Cheapest and most fundamental
# first, so a failure names the smallest thing that is wrong.
ARM_ORDER = ("classification", "lossless", "correspondence", "schema", "provenance",
             "generated", "handlers")


EXTRACTOR = ROOT / "scripts" / "extract-maquette-fixtures.mjs"

# THE ARMS THAT READ THE ENGINE THROUGH THE TypeScript PARSER, and only those.
# `classification` runs the extractor directly; `lossless` and `correspondence`
# reach it through the builder. The other four read JSON and text — the
# contract, the seeds, the generated types, the handler modules — and need
# neither node nor an install.
#
# NAMED RATHER THAN COUNTED, and the distinction cost a correction: a first
# version of the skip below announced « the 7 arms that read the engine through
# its parser » beside `len(ARMS)`, which was false about four of them AND was a
# second copy of a list that already exists. Two written exemptions — the
# vocabulary arm's and the boundary guard's, both for `contract-types.d.ts` —
# rest on `generated` running wherever the guards do, and skipping it would
# have left them resting on a check that read nothing.
NEEDS_THE_PARSER = ("classification", "lossless", "correspondence")

# The extractor's own exit code for « there is no TypeScript install here ».
# Distinguished from every other failure ON PURPOSE: a syntax error in the
# extractor exits 1, an unknown flag exits 2, and collapsing those into « no
# install » would announce a confident WRONG reason while returning success —
# which is worse than failing, and is the shape B-046 records.
NO_TYPESCRIPT_INSTALL = 3


def typescript_install() -> str | None:
    """Returns the TypeScript install the extractor would parse through.

    ASKED OF THE EXTRACTOR, never re-derived here. The candidate paths are the
    extractor's own, and a second copy of them in this file would be a table
    that rots — the extractor is where they belong, so it is the extractor that
    is asked.

    Returns:
        The resolved install path when there is one, or None when the extractor
        answered `NO_TYPESCRIPT_INSTALL`.

    Raises:
        RuntimeError: When the extractor could not answer at all — it is
            missing, node is absent, it timed out, or it failed for any reason
            other than the absence of an install. That is not « cannot run
            here »; it is a broken instrument, and it must be loud.
    """
    try:
        run = subprocess.run(["node", str(EXTRACTOR), "--typescript-install"],
                             cwd=ROOT, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as failure:
        raise RuntimeError(f"the extractor could not be run: {failure!r}")
    if run.returncode == NO_TYPESCRIPT_INSTALL:
        return None
    if run.returncode != 0 or not run.stdout.strip():
        raise RuntimeError(
            f"the extractor answered {run.returncode} to --typescript-install "
            f"instead of 0 or {NO_TYPESCRIPT_INSTALL}: "
            f"{(run.stderr or run.stdout).strip()[-300:] or 'nothing at all'}")
    return run.stdout.strip()


def main() -> int:
    """Run the requested arms."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=sorted(ARMS), help="run one arm instead of all")
    parser.add_argument("--list", action="store_true",
                        help="print the inventory this guard holds, and refuse nothing")
    arguments = parser.parse_args()

    # A CLONE WITH NO npm INSTALL CANNOT RUN THE THREE ARMS THAT PARSE THE
    # ENGINE, and it must say which three rather than fall over. With no install
    # this guard used to answer a ten-line node traceback and a non-zero exit —
    # inside `make check`, two lines above
    # `openapi-drift: skipped (frontend/node_modules absent)` and
    # `contract-types: skipped (…)`, which handle exactly the same absence.
    #
    # THE SKIP IS NARROW AND LOUD. Narrow, because four arms need no parser at
    # all and two written exemptions rest on one of them. Loud, because a skip
    # that reads like a pass is the failure this repository counts in
    # `BUGS.md` § Guards green over what they do not read. And it is not
    # reachable where the gate matters: the one continuous-integration job that
    # runs this guard (`harness-contracts`, through `run.sh --contracts`)
    # installs `frontend/maquette/design` first.
    try:
        without_the_parser = typescript_install() is None
    except RuntimeError as broken:
        # A BROKEN INSTRUMENT IS NOT A SKIP. The guard exits non-zero and names
        # what failed, rather than printing a node traceback or — worse —
        # announcing « no TypeScript install » about an extractor that is
        # merely broken.
        print(f"check-mock-seeds: {broken}", file=sys.stderr)
        return 1

    if arguments.list:
        classified = register()
        for name in sorted(classified):
            entry = classified[name]
            print(f"  {name:34} {entry['class']}")
        print(f"  {len(classified)} family(ies)")
        return 0

    # The builder module is loaded EITHER WAY: importing it runs no node, and
    # the four arms below read their inputs through its constants. Only the
    # three arms that CALL the extractor are skipped.
    module = builder()

    print(f"check-mock-seeds: {SEEDS.relative_to(ROOT)}")
    # A DELIBERATE ORDER, not the alphabet. `correspondence` builds every seed,
    # and the builder REFUSES a lossy projection by exiting — so run
    # alphabetically, a lossy projection killed the process before `lossless`
    # could say a word, and that arm could only ever report under `--arm`.
    selected = [arguments.arm] if arguments.arm else ARM_ORDER
    if without_the_parser:
        skipped = [name for name in selected if name in NEEDS_THE_PARSER]
        selected = [name for name in selected if name not in NEEDS_THE_PARSER]
        if skipped:
            print(f"  SKIPPED, no TypeScript install: {', '.join(skipped)} — "
                  f"{len(skipped)} arm(s) that read the engine through its parser "
                  f"checked NOTHING. Run `npm ci` in frontend/maquette/design or "
                  f"in frontend. The {len(selected)} arm(s) below did run.")
    violations = sum(ARMS[name](module) for name in selected)
    if violations:
        print(f"check-mock-seeds: {violations} violation(s)")
        return 1
    print("check-mock-seeds: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
