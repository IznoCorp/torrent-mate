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
 * WHAT A FIXTURE FAMILY IS, and each clause is load-bearing:
 *
 *   1. declared `const`. A `let` is a variable the engine WRITES — `world`,
 *      `press`, `openCardDx` — and freezing its initial value as data would
 *      record a starting point as though it were a fact. Thirty of the
 *      engine's module-level declarations are exactly that.
 *   2. at MODULE level, or qualified by the function that encloses it (below).
 *   3. whose initializer is PURE — no call, no reference to another binding,
 *      only literal values and property keys. `SERVICES_PANNE = SERVICES.map(…)`
 *      is code that happens to produce data, and extracting it would freeze a
 *      derivation.
 *
 * THERE IS NO SIZE FLOOR, and there was one. A first version took literals of
 * three lines or more, which reads as a sensible filter and is not: it hid
 * `CADENCE_CRON` — the grab cadence, read off the live scheduler — and
 * `STRIP_LABELS`, a one-line array of five interface words. Both are fixtures;
 * neither is three lines. The hole was found by the contract naming a family
 * the register did not hold, which is the only reason it was found at all.
 *
 * A LITERAL DECLARED INSIDE A NAMED FUNCTION IS STILL REACHABLE, and it is not
 * a generalisation for its own sake. Most of them are a function's working
 * state; ONE is not — `openJourneySheet.steps`, a torrent's five stages, real
 * data drawn inline — and left out it would have to be copied into a seed by
 * hand: the one un-re-derivable corner the guard reading this tool exists to
 * forbid. They carry a QUALIFIED name, `enclosingFunction.name`, so the two
 * kinds can never be confused, and the register classifies each of them like
 * any other. Inside an ANONYMOUS function they are counted and not inventoried
 * — see `ANONYMOUS` below for why.
 *
 * Usage:
 *     node scripts/extract-maquette-fixtures.mjs --measure
 *     node scripts/extract-maquette-fixtures.mjs --list
 *     node scripts/extract-maquette-fixtures.mjs --all
 *     node scripts/extract-maquette-fixtures.mjs --anonymous
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

// THE PARSER LIVES IN ONE OF TWO INSTALLS, and naming only one made this tool
// unrunnable on the machine that matters. The continuous-integration job that
// runs the guard reading this file installs `frontend/maquette/design`, never
// `frontend` — a relative specifier does not fall back, so the tool failed
// there for a reason foreign to every change under test. That is the shape
// B-077 records, met from the other end.
//
// The maquette's own install is tried FIRST: this tool reads the maquette's
// engine, so the maquette's TypeScript is the one that should parse it.
const TYPESCRIPT_INSTALLS = [
  "../frontend/maquette/design/node_modules/typescript",
  "../frontend/node_modules/typescript",
];

const typescriptInstall = TYPESCRIPT_INSTALLS.find((install) => {
  try {
    require_.resolve(install);
    return true;
  } catch {
    return false;
  }
});

const NO_TYPESCRIPT =
  `no TypeScript install found. Tried: ${TYPESCRIPT_INSTALLS.join(", ")}. Run ` +
  "`npm ci` in frontend/maquette/design or in frontend.";

// ASKED BEFORE THE PARSER IS LOADED, because the parser is what is missing.
// `--typescript-install` answers « can this tool run here? » with the path it
// would use, or exit code 3 and the sentence above. It exists so that the ONE
// list of installs stays in this file: `scripts/check-mock-seeds.py` has to
// decide whether to run or to say it is skipping, and a second copy of these
// two paths over there is a table that rots — this repository has paid for
// that shape more than once. Exit 3 rather than 1: « cannot run here » is not
// « found a violation », and a caller must be able to tell them apart.
if (process.argv[2] === "--typescript-install") {
  if (typescriptInstall === undefined) {
    process.stderr.write(`${NO_TYPESCRIPT}\n`);
    process.exit(3);
  }
  process.stdout.write(`${typescriptInstall}\n`);
  process.exit(0);
}

const typescript = (() => {
  if (typescriptInstall === undefined) throw new Error(NO_TYPESCRIPT);
  return require_(typescriptInstall);
})();

const REPOSITORY_ROOT = resolve(import.meta.dirname, "..");
const ENGINE = resolve(
  REPOSITORY_ROOT,
  "frontend/maquette/design/src/engine/legacy.js",
);

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
  if (!isLiteralRoot(initializer)) return false;
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
  // THE ROOT IS WALKED TOO, and it was not. `forEachChild` starts at the
  // children, so a bare `const settle = afterUnwind` — an Identifier with no
  // children — was judged pure and then threw in `valueOf`, which is the two
  // halves of one reader disagreeing. It surfaced only when `--all` asked for
  // every family at once; `--family` had only ever been called on the ones
  // already known to be data.
  walk(initializer);
  return pure;
}

/**
 * Answers whether a node is a literal VALUE, rather than something evaluated.
 *
 * `isPureLiteral` asks what a value contains; this asks what it IS. Both are
 * needed: `1 + 2` contains only literals and is an expression.
 *
 * @param {import("typescript").Node} node The initializer.
 * @returns {boolean} True when `valueOf` can read it.
 */
function isLiteralRoot(node) {
  if (
    typescript.isArrayLiteralExpression(node) ||
    typescript.isObjectLiteralExpression(node) ||
    typescript.isStringLiteral(node) ||
    typescript.isNoSubstitutionTemplateLiteral(node) ||
    typescript.isNumericLiteral(node)
  ) {
    return true;
  }
  if (typescript.isPrefixUnaryExpression(node)) {
    return typescript.isNumericLiteral(node.operand);
  }
  return (
    node.kind === typescript.SyntaxKind.TrueKeyword ||
    node.kind === typescript.SyntaxKind.FalseKeyword ||
    node.kind === typescript.SyntaxKind.NullKeyword
  );
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

// What a literal inside an UNNAMED function is qualified by, and why those are
// then dropped from the inventory rather than named.
//
// A literal in an anonymous callback has no stable name to be inventoried
// under: the only thing distinguishing it is where it sits, and a name built
// from a line number is renamed by every edit above it — a register keyed on
// one would go red for a change that touched nothing it holds. They are working
// state of a callback, and they are COUNTED on every run so their exclusion is
// a figure rather than a silence.
//
// THE COUNT IS HELD, in `fixture-register.json`'s `$anonymous`: a figure printed
// and never compared can go from one to nine with every guard green.
const ANONYMOUS = "anonymous";

/**
 * Answers whether a declaration was written `const`.
 *
 * The flag lives on the declaration LIST, not on the declaration — `const a = 1,
 * b = 2` is one list of two — so the parent is what carries the answer.
 *
 * @param {import("typescript").VariableDeclaration} declaration The declaration.
 * @returns {boolean} True when its list is `const`.
 */
function isConstant(declaration) {
  const list = declaration.parent;
  if (!list || !typescript.isVariableDeclarationList(list)) return false;
  return (list.flags & typescript.NodeFlags.Const) !== 0;
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
      ? (node.name && typescript.isIdentifier(node.name) ? node.name.text : ANONYMOUS)
      : null;
    if (
      typescript.isVariableDeclaration(node) &&
      node.initializer &&
      typescript.isIdentifier(node.name) &&
      isConstant(node)
    ) {
      const start = lineOf(node.getStart(source));
      const end = lineOf(node.getEnd());
      const entry = {
        name: enclosing ? `${enclosing}.${node.name.text}` : node.name.text,
        kind: typescript.isArrayLiteralExpression(node.initializer)
          ? "array"
          : typescript.isObjectLiteralExpression(node.initializer)
            ? "object"
            : "scalar",
        lines: end - start + 1,
        start,
        end,
        entries: typescript.isArrayLiteralExpression(node.initializer)
          ? node.initializer.elements.length
          : typescript.isObjectLiteralExpression(node.initializer)
            ? node.initializer.properties.length
            : 1,
        node: node.initializer,
      };
      if (isPureLiteral(node.initializer)) {
        (enclosing ? nested : families).push(entry);
      }
    }
    typescript.forEachChild(node, (child) =>
      visit(child, enclosing ?? enclosure),
    );
  };
  visit(source, null);
  return {
    families,
    nested: nested.filter((entry) => !entry.name.startsWith(`${ANONYMOUS}.`)),
    anonymous: nested.filter((entry) => entry.name.startsWith(`${ANONYMOUS}.`)).length,
  };
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
const { families, nested, anonymous } = collect(ENGINE);

if (argument === "--measure") {
  const totalLines = readFileSync(ENGINE, "utf8").split("\n").length;
  const covered = families.reduce((sum, family) => sum + family.lines, 0);
  process.stdout.write(
    `${families.length} module-level fixture families over ${covered} lines ` +
      `of ${totalLines}\n`,
  );
  process.stdout.write(
    `${nested.length} pure literal(s) inside a NAMED function, qualified: ` +
      `${nested.map((entry) => `${entry.name} (line ${entry.start})`).join(", ")}\n`,
  );
  process.stdout.write(
    `${anonymous} more inside an anonymous one, not inventoried — a name built on a ` +
      `line number is renamed by every edit above it\n`,
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
} else if (argument === "--anonymous") {
  process.stdout.write(`${anonymous}\n`);
} else if (argument === "--all") {
  // Every family in ONE object, because the alternative is one process per
  // family: the guard that reads them made a hundred and forty node starts,
  // each re-parsing 35 198 lines, and took 66 s — against 31 s for the twelve
  // repository guards put together. A tier nobody can afford to run is a tier
  // nobody runs.
  const everything = {};
  for (const family of [...families, ...nested]) {
    // A COLLISION IS REFUSED, never resolved by whichever came last. Two inner
    // functions of one outer function may each declare the same name, and
    // overwriting one with the other would hand the guard a family whose
    // contents belong to a different declaration — silently, and with every
    // count still right.
    if (Object.hasOwn(everything, family.name)) {
      process.stderr.write(
        `extract-maquette-fixtures: two declarations answer to ${family.name}; a ` +
          "qualified name must name one thing\n",
      );
      process.exit(1);
    }
    everything[family.name] = valueOf(family.node);
  }
  process.stdout.write(canonical(everything));
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
    "usage: extract-maquette-fixtures.mjs --measure | --list | --all | "
      + "--anonymous | --family <NAME> | --typescript-install\n",
  );
  process.exit(2);
}
