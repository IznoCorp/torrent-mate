/**
 * Reads the maquette engine's fixture literals with the TypeScript parser.
 *
 * WHY A PARSER AND NOT A REGULAR EXPRESSION, and it is written down twice
 * already in this repository. `scripts/source-spans.mjs` exists because « no
 * heuristic separates them reliably », and `scripts/refresh-maquette-fixture.py`
 * says in as many words that a regular expression cannot find the end of one of
 * these objects, with the three shapes that proved it. These literals hold
 * French interface copy full of apostrophes, nested objects and template
 * pieces: a bracket counter that does not follow quotes reads the first
 * apostrophe as a string opening and every brace after it is counted in the
 * wrong nesting. That is not a hypothetical — it is B-075's second instance,
 * found inside the reader of the rule that wave was writing at that moment.
 *
 * WHAT A FIXTURE FAMILY IS, and the definition is narrow on purpose:
 *
 *   1. a `const NAME = [...]` or `const NAME = {...}` at MODULE level, and
 *   2. whose initializer is PURE — no call, no reference to another binding,
 *      only literal values and property keys.
 *
 * Both halves are load-bearing. `SERVICES_PANNE = SERVICES.map(...)` is code
 * that happens to produce data, and extracting it would freeze a derivation.
 *
 * A LITERAL DECLARED INSIDE A FUNCTION IS STILL REACHABLE, and that is not a
 * generalisation for its own sake. Two of them exist — the journey sheet's five
 * stages and one tone mapping — and the first is real state a contract has to
 * serve. Left out, it would have to be copied into a seed by hand, which is
 * precisely the un-re-derivable corner the guard reading this tool exists to
 * forbid. They carry a QUALIFIED name, `enclosingFunction.name`, so the two
 * kinds can never be confused and so the register can hold every one of them.
 *
 * Usage:
 *     node scripts/extract-maquette-fixtures.mjs --measure
 *     node scripts/extract-maquette-fixtures.mjs --list
 *     node scripts/extract-maquette-fixtures.mjs --family LIBRARY
 *     node scripts/extract-maquette-fixtures.mjs --family openJourneySheet.steps
 *
 * `--family` prints canonical JSON: keys in SOURCE order, two-space indent, a
 * closing newline. Source order rather than sorted, because the fixture's own
 * order is information — a list of disks is drawn in the order it is written —
 * and a serializer that reorders would make the committed seed disagree with
 * what the interface shows for a reason nobody could see in a diff.
 */
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";

const require_ = createRequire(import.meta.url);
const typescript = require_("../frontend/node_modules/typescript");

const REPOSITORY_ROOT = resolve(import.meta.dirname, "..");
const ENGINE = resolve(
  REPOSITORY_ROOT,
  "frontend/maquette/design/src/engine/legacy.js",
);

// A literal shorter than this is a one-line detail, not a data family. The
// threshold is the one the measurement in the design was taken with; it is
// stated here so the two cannot drift apart silently.
const MINIMUM_LINES = 3;

/**
 * Answers whether an initializer holds literal values and nothing else.
 *
 * A property KEY that happens to be an identifier is not a reference — `{ t: 1 }`
 * names no binding — so the walk has to tell a key from a value rather than
 * refusing every identifier it meets.
 *
 * @param {import("typescript").Node} initializer The node to judge.
 * @returns {boolean} True when nothing in it is evaluated.
 */
function isPureLiteral(initializer) {
  let pure = true;
  const walk = (node) => {
    if (!pure) return;
    if (
      typescript.isCallExpression(node) ||
      typescript.isNewExpression(node) ||
      typescript.isTaggedTemplateExpression(node) ||
      typescript.isTemplateExpression(node) ||
      typescript.isFunctionExpression(node) ||
      typescript.isArrowFunction(node) ||
      typescript.isSpreadElement(node) ||
      typescript.isSpreadAssignment(node) ||
      typescript.isComputedPropertyName(node) ||
      typescript.isShorthandPropertyAssignment(node) ||
      typescript.isGetAccessor(node)
    ) {
      pure = false;
      return;
    }
    if (typescript.isIdentifier(node)) {
      const parent = node.parent;
      const isPropertyKey =
        (typescript.isPropertyAssignment(parent) && parent.name === node) ||
        (typescript.isPropertyAccessExpression(parent) && parent.name === node);
      if (!isPropertyKey) {
        pure = false;
        return;
      }
    }
    typescript.forEachChild(node, walk);
  };
  typescript.forEachChild(initializer, walk);
  return pure;
}

/**
 * Turns a literal node into the plain JavaScript value it denotes.
 *
 * Anything this function does not recognise THROWS, naming the syntax kind. A
 * silent fallback is how a fixture value becomes `null` in a seed nobody reads
 * closely, and the seed is the thing this whole lot rests on.
 *
 * @param {import("typescript").Node} node The literal to read.
 * @returns {unknown} The value.
 */
function valueOf(node) {
  if (typescript.isStringLiteral(node) || typescript.isNoSubstitutionTemplateLiteral(node)) {
    return node.text;
  }
  if (typescript.isNumericLiteral(node)) return Number(node.text);
  if (node.kind === typescript.SyntaxKind.TrueKeyword) return true;
  if (node.kind === typescript.SyntaxKind.FalseKeyword) return false;
  if (node.kind === typescript.SyntaxKind.NullKeyword) return null;
  if (typescript.isPrefixUnaryExpression(node)) {
    const sign = node.operator === typescript.SyntaxKind.MinusToken ? -1 : 1;
    const inner = valueOf(node.operand);
    if (typeof inner !== "number") {
      throw new Error(`unary operator applied to a non-number at ${position(node)}`);
    }
    return sign * inner;
  }
  if (typescript.isArrayLiteralExpression(node)) {
    return node.elements.map((element) => valueOf(element));
  }
  if (typescript.isObjectLiteralExpression(node)) {
    const value = {};
    for (const property of node.properties) {
      if (!typescript.isPropertyAssignment(property)) {
        throw new Error(
          `unsupported property kind ${typescript.SyntaxKind[property.kind]} at ${position(property)}`,
        );
      }
      value[keyOf(property.name)] = valueOf(property.initializer);
    }
    return value;
  }
  throw new Error(
    `unsupported literal kind ${typescript.SyntaxKind[node.kind]} at ${position(node)}`,
  );
}

/**
 * Reads a property key, whatever of the three forms it wears.
 *
 * @param {import("typescript").PropertyName} name The key node.
 * @returns {string} The key as a string.
 */
function keyOf(name) {
  if (typescript.isIdentifier(name)) return name.text;
  if (typescript.isStringLiteral(name)) return name.text;
  if (typescript.isNumericLiteral(name)) return name.text;
  throw new Error(
    `unsupported property key kind ${typescript.SyntaxKind[name.kind]} at ${position(name)}`,
  );
}

/** @type {import("typescript").SourceFile} */
let source;

/**
 * Formats a node's position as `line:column`, for a message that can be acted on.
 *
 * @param {import("typescript").Node} node The node.
 * @returns {string} The position.
 */
function position(node) {
  const place = source.getLineAndCharacterOfPosition(node.getStart(source));
  return `${place.line + 1}:${place.character + 1}`;
}

/**
 * Walks the engine and collects every fixture family it declares.
 *
 * @param {string} path The engine's path.
 * @returns {{families: object[], nested: object[]}} Module-level families, and
 *   the pure literals declared inside a function — reported, never merged.
 */
function collect(path) {
  const text = readFileSync(path, "utf8");
  source = typescript.createSourceFile(
    path,
    text,
    typescript.ScriptTarget.Latest,
    true,
    typescript.ScriptKind.JS,
  );
  const families = [];
  const nested = [];
  const lineOf = (offset) => source.getLineAndCharacterOfPosition(offset).line + 1;

  const visit = (node, enclosing) => {
    const opensAFunction =
      typescript.isFunctionDeclaration(node) ||
      typescript.isFunctionExpression(node) ||
      typescript.isArrowFunction(node) ||
      typescript.isMethodDeclaration(node) ||
      typescript.isGetAccessor(node) ||
      typescript.isSetAccessor(node);
    // The name a nested literal is qualified BY. An anonymous function gives
    // `anonymous@<line>` rather than nothing: a qualified name that collapses
    // to the bare one for an unnamed enclosure would put a nested literal in
    // the module-level namespace, which is the confusion the qualification is
    // there to prevent.
    const enclosure = opensAFunction
      ? (node.name && typescript.isIdentifier(node.name)
          ? node.name.text
          : `anonymous@${lineOf(node.getStart(source))}`)
      : null;
    if (
      typescript.isVariableDeclaration(node) &&
      node.initializer &&
      typescript.isIdentifier(node.name) &&
      (typescript.isArrayLiteralExpression(node.initializer) ||
        typescript.isObjectLiteralExpression(node.initializer))
    ) {
      const start = lineOf(node.getStart(source));
      const end = lineOf(node.getEnd());
      const entry = {
        name: enclosing ? `${enclosing}.${node.name.text}` : node.name.text,
        kind: typescript.isArrayLiteralExpression(node.initializer) ? "array" : "object",
        lines: end - start + 1,
        start,
        end,
        entries: typescript.isArrayLiteralExpression(node.initializer)
          ? node.initializer.elements.length
          : node.initializer.properties.length,
        node: node.initializer,
      };
      if (entry.lines >= MINIMUM_LINES && isPureLiteral(node.initializer)) {
        (enclosing ? nested : families).push(entry);
      }
    }
    typescript.forEachChild(node, (child) =>
      visit(child, enclosing ?? enclosure),
    );
  };
  visit(source, null);
  return { families, nested };
}

/**
 * Serializes a value the one way this repository will ever serialize it.
 *
 * @param {unknown} value The value.
 * @returns {string} Canonical JSON, with its closing newline.
 */
function canonical(value) {
  return `${JSON.stringify(value, null, 2)}\n`;
}

const argument = process.argv[2];
const { families, nested } = collect(ENGINE);

if (argument === "--measure") {
  const totalLines = readFileSync(ENGINE, "utf8").split("\n").length;
  const covered = families.reduce((sum, family) => sum + family.lines, 0);
  process.stdout.write(
    `${families.length} module-level fixture families over ${covered} lines ` +
      `of ${totalLines}\n`,
  );
  process.stdout.write(
    `${nested.length} pure literal(s) declared inside a function, qualified: ` +
      `${nested.map((entry) => `${entry.name} (line ${entry.start})`).join(", ")}\n`,
  );
  for (const family of [...families].sort((a, b) => b.lines - a.lines)) {
    process.stdout.write(
      `  ${family.name.padEnd(24)} ${family.kind.padEnd(6)} ` +
        `${String(family.lines).padStart(6)} lines ` +
        `${String(family.entries).padStart(5)} entries  line ${family.start}\n`,
    );
  }
} else if (argument === "--list") {
  for (const family of families) process.stdout.write(`${family.name}\n`);
  for (const entry of nested) process.stdout.write(`${entry.name}\n`);
} else if (argument === "--family") {
  const wanted = process.argv[3];
  const family = [...families, ...nested].find(
    (candidate) => candidate.name === wanted,
  );
  if (!family) {
    process.stderr.write(
      `extract-maquette-fixtures: no fixture family named ${wanted}\n`,
    );
    process.exit(1);
  }
  process.stdout.write(canonical(valueOf(family.node)));
} else {
  process.stderr.write(
    "usage: extract-maquette-fixtures.mjs --measure | --list | --family <NAME>\n",
  );
  process.exit(2);
}
