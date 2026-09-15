#!/usr/bin/env python3
"""Holds the maquette's mock seeds against the register, the contract and the handlers.

THE CLAUSE THIS GUARD EXISTS FOR, and it is L08's binding one: every shape the
mock layer serves is SEEDED FROM THE FIXTURE IT REPLACES. A mock returning
exactly what the current fixture returns makes L09 provable — wiring a surface
to it renders the same thing, so the oracle proves the wiring at zero
divergence. Invented mock data would forfeit that proof for nothing.

WHAT EACH ARM DOES NOT READ, asked before the arms were written and answered
here rather than left for a reader to reconstruct. A guard is green for two
reasons and only one of them is good.

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
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAQUETTE = ROOT / "frontend" / "maquette"
REGISTER = MAQUETTE / "fixture-register.json"
CONTRACT = MAQUETTE / "contract" / "openapi.json"
SEEDS = MAQUETTE / "design" / "src" / "mocks" / "seeds"
PROJECTIONS = MAQUETTE / "fixture-projections.json"

# The classes whose families have a seed. `interface` and `unserved` do not:
# routing a label or a long-press delay through a mock would have the interface
# asking a server for its own words.
SEEDED_CLASSES = ("served", "asset")

METHODS = ("get", "post", "put", "patch", "delete")

# The floor under the module count the handlers arm reads. A reader that finds
# nothing and reports clean is the shape this whole guard is written against, so
# the arm refuses a tree it cannot recognise rather than passing over it.
MINIMUM_PAYLOAD_MODULES = 8


def register() -> dict:
    """The classification of every fixture family."""
    return json.loads(REGISTER.read_text(encoding="utf-8"))["families"]


def converted_families() -> list[str]:
    """The seeded families whose seed is committed rather than rebuilt, in order.

    Returns:
        Their names — every seeded family, since no fixture is rebuilt any more.
    """
    return sorted(name for name, entry in register().items()
                  if entry["class"] in SEEDED_CLASSES and entry.get("converted"))


def file_for(name: str) -> Path:
    """The seed file one family is written to, as `fixture-projections.json` names it.

    DECLARED, NEVER DERIVED FROM THE FAMILY NAME: the families carry the dead
    engine's spelling, and a seed file is named in English, in full.

    Args:
        name: The family.

    Returns:
        The seed file.

    Raises:
        SystemExit: When the family declares no file name.
    """
    chosen = json.loads(PROJECTIONS.read_text(encoding="utf-8"))["families"].get(name, {}).get("file")
    if not chosen:
        raise SystemExit(f"check-mock-seeds: {name} is served and {PROJECTIONS.name} declares no `file` for it")
    return SEEDS / (chosen + ".json")


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


def arm_schema() -> int:
    """Refuse a seed that does not answer the contract schema naming it.

    THIS IS THE ARM THAT SEES AN UNPROJECTED FAMILY: a family whose keys were
    never renamed fails its schema. Two shipped that way while the builder
    reported success.

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
    declared = json.loads(PROJECTIONS.read_text(encoding="utf-8"))["families"]
    failures: list[str] = []
    validated = 0
    # THE CONVERTED FAMILIES ARE VALIDATED TOO, and leaving them out was the
    # mistake this comment exists to stop somebody repeating. A converted
    # family's seed can no longer be re-derived from the engine — that arm says
    # so by name — and this one is what still holds it. Dropping it here would
    # have made « held by the contract's schema » a sentence the code did not
    # honour, on the very seeds that lost their other reader.
    for name in converted_families():
        expression = declared.get(name, {}).get("answers")
        if not expression:
            failures.append(f"{name}: no `answers` declared, so nothing can be validated "
                            f"against it — which would read as a pass")
            continue
        seed = json.loads(file_for(name).read_text(encoding="utf-8"))
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


def arm_provenance() -> int:
    """Hold the register, the seed files and the contract in step, all ways.

    Returns:
        The number of orphans, in either direction.
    """
    classified = register()
    served = {name for name, entry in classified.items()
              if entry["class"] in SEEDED_CLASSES}
    on_disk = {path.stem for path in SEEDS.glob("*.json")}
    expected = {file_for(name).stem for name in served}
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


def arm_handlers() -> int:
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
    # is data by definition; `contract/types.d.ts` is generated.
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



def arm_generated() -> int:
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

    Returns:
        The number of ways the file and the contract disagree.
    """
    generated = SEEDS.parent.parent / "contract" / "types.d.ts"
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
    "generated": arm_generated,
    "handlers": arm_handlers,
    "provenance": arm_provenance,
    "schema": arm_schema,
}


# The order the arms run in when all of them do. Cheapest and most fundamental
# first, so a failure names the smallest thing that is wrong.
ARM_ORDER = ("schema", "provenance", "generated", "handlers")


def main() -> int:
    """Run the requested arms."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=sorted(ARMS), help="run one arm instead of all")
    parser.add_argument("--list", action="store_true",
                        help="print the inventory this guard holds, and refuse nothing")
    arguments = parser.parse_args()

    if arguments.list:
        classified = register()
        for name in sorted(classified):
            entry = classified[name]
            print(f"  {name:34} {entry['class']}")
        print(f"  {len(classified)} family(ies)")
        return 0

    print(f"check-mock-seeds: {SEEDS.relative_to(ROOT)}")
    selected = [arguments.arm] if arguments.arm else ARM_ORDER
    violations = sum(ARMS[name]() for name in selected)
    if violations:
        print(f"check-mock-seeds: {violations} violation(s)")
        return 1
    print("check-mock-seeds: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
