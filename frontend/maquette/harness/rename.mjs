/**
 * Rename every short identifier in the prototype's script, per scope.
 *
 * Why a parser and not a regex: the same short name is declared in many scopes
 * with many meanings — `t` is a title in one function, a trimmed query in
 * another, a touch point in a third — so a global replace preserves behaviour
 * while lying about meaning. And the file embeds ~14 MB of base64 in which any
 * hand-rolled tokenizer desynchronises: a previous attempt renamed 715
 * occurrences and silently missed `posterBox`, leaving the file half-renamed.
 *
 * Scope analysis gives the exact character range of a variable's declaration
 * and of every reference to it. Nothing else is ever touched: not a string, not
 * a comment, not an identically-spelled variable in a neighbouring function.
 *
 * A name is chosen from what the code itself says: the collection a callback
 * iterates, the call an initialiser makes, the position of a parameter. Where
 * judgement is needed — the module-scope singletons — the table is explicit.
 */
import { readFileSync, writeFileSync } from "node:fs";

const ROOT = "/Users/izno/dev/PersonalScraper/frontend";
const espree = await import(`${ROOT}/node_modules/espree/dist/espree.cjs`);
const eslintScope = (await import(`${ROOT}/node_modules/eslint-scope/dist/eslint-scope.cjs`)).default;

const FRAGMENT = `${ROOT}/maquette/design/refonte.html`;

/** The module-scope singletons, where only judgement can name them. */
const SINGLETONS = {
  S: "state",
  W: "world",
  D: "derived",
  I: "icons",
  P: "profile",
  $: "select",
  YT: "trailerIds",
  LIB: "LIBRARY",
  NAV: "NAVIGATION",
  // Helpers whose names say nothing about what they do. Three letters is not
  // short enough for the length rule to catch, and long enough to look
  // deliberate — which is how they survived every previous pass.
  esc: "escapeHtml",
  svg: "svgIcon",
  fiche: "sheetFor",
  set: "applyState",
  ini: "initialsOf",
  clef: "normalisedKey",
  seed: "seedWorld",
  _av: "beforeReset",
};

/** Names that are module-scope and must be renamed whatever their length. */
const MODULE_NAMES = new Set(Object.keys(SINGLETONS));

/** Names that are already clear enough at two characters. */
const KEEP = new Set(["id"]);

/**
 * Collections whose singular is not just « drop the s ».
 *
 * The KEYS are the legacy script's own collection names, French ones included
 * (`seasons`, `titres`, `lignes`) — they are what this tool READS, data about
 * its subject. The VALUES are the names it WRITES, and those are English.
 */
const SINGULARS = {
  follows: "follow",
  suggestions: "suggestion",
  releases: "release",
  entries: "entry",
  candidates: "candidate",
  seasons: "season",
  seasons: "season",
  states: "state",
  regions: "region",
  categories: "category",
  properties: "property",
  children: "child",
  values: "value",
  keys: "key",
  titres: "title",
  titles: "title",
  episodes: "episode",
  items: "item",
  lignes: "line",
  bits: "bit",
  parts: "part",
  rows: "row",
  cards: "card",
  tiles: "tile",
};

const singular = (name) =>
  SINGULARS[name] ?? (name.endsWith("s") && name.length > 3 ? name.slice(0, -1) : name);

const ITERATORS = new Set([
  "map", "filter", "find", "findIndex", "some", "every", "forEach", "flatMap", "sort", "reduce",
]);

const html = readFileSync(FRAGMENT, "utf8");
const opens = html.indexOf("<script>");
const closes = html.lastIndexOf("</script>");
const before = html.slice(0, opens + "<script>".length);
const script = html.slice(opens + "<script>".length, closes);
const after = html.slice(closes);

const ast = espree.parse(script, {
  ecmaVersion: "latest",
  sourceType: "script",
  loc: true,
  range: true,
});

// Parent links: the naming rules need to look upward, and espree sets none.
(function link(node, parent) {
  if (!node || typeof node !== "object") return;
  if (Array.isArray(node)) {
    for (const x of node) link(x, parent);
    return;
  }
  if (typeof node.type === "string") {
    Object.defineProperty(node, "parent", { value: parent, enumerable: false, writable: true });
    for (const [key, value] of Object.entries(node)) link(value, node);
  }
})(ast, null);

const scopes = eslintScope.analyze(ast, { ecmaVersion: 2024, sourceType: "script" });
const textOf = (node) => script.slice(node.range[0], node.range[1]);

/**
 * Chooses a name for a variable from what the surrounding code says.
 *
 * @param {object} variable an eslint-scope Variable
 * @param {object} scope its scope
 * @returns {string|null} the new name, or null to leave it alone
 */
function nameFor(variable, scope) {
  const name = variable.name;
  if (name === "arguments" || KEEP.has(name)) return null;
  if (scope.type === "module" || scope.block.type === "Program") {
    if (SINGLETONS[name]) return SINGLETONS[name];
  }
  if (SINGLETONS[name] && name !== "S" && name !== "W" && name !== "D") return SINGLETONS[name];

  const def = variable.defs[0];
  if (!def) return null;
  const node = def.name;
  const kind = def.type;

  // A callback parameter is named by what it iterates.
  if (kind === "Parameter") {
    const fn = def.node;
    const call = fn.parent;
    if (call?.type === "CallExpression" && call.callee?.type === "MemberExpression") {
      const method = call.callee.property?.name;
      if (ITERATORS.has(method)) {
        const position = fn.params.indexOf(node);
        if (position === 1) return method === "reduce" ? "element" : "index";
        if (position === 2) return "collection";
        if (position === 0) {
          if (method === "reduce") return "accumulator";
          const receiver = call.callee.object;
          const source =
            receiver.type === "MemberExpression" ? receiver.property?.name
            : receiver.type === "Identifier" ? receiver.name
            : receiver.type === "CallExpression" && receiver.callee?.type === "MemberExpression"
              ? receiver.callee.property?.name
              : null;
          if (source && /^[a-zA-Z_]/.test(source)) return singular(source);
          return "element";
        }
      }
    }
    // An event handler's parameter.
    if (
      call?.type === "CallExpression" &&
      call.callee?.property?.name === "addEventListener"
    ) {
      return "event";
    }
    if (kind === "Parameter" && name === "e") return "event";
    return null; // named by hand below, or left as is
  }

  if (kind === "Variable" && def.node?.init) {
    const init = def.node.init;
    if (init.type === "CallExpression") {
      const callee = init.callee;
      const method = callee?.property?.name ?? callee?.name;
      if (method === "querySelector" || method === "getElementById" || method === "select") {
        return "element";
      }
      if (method === "querySelectorAll") return "elements";
      if (method === "getBoundingClientRect") return "rect";
      if (method === "find") return "found";
      if (method === "getComputedStyle") return "styles";
      if (method && /^[a-z][\w]{2,}$/.test(method)) return method;
    }
    if (init.type === "MemberExpression" && init.property?.name) {
      const p = init.property.name;
      if (/^[a-z][\w]{2,}$/.test(p)) return p;
    }
  }
  return null;
}

/**
 * Hand-authored names, keyed by `scopeLine:oldName`, for what the rules cannot
 * see. Passed as `--names <file>`; without it the rules decide alone and every
 * name they cannot derive is listed at the end instead.
 *
 * It used to be read from an absolute path inside a session's scratch
 * directory, which stopped existing with the session: the script then could not
 * run at all, and a tool that throws on its first line teaches nothing about
 * the code it was written to read.
 */
const namesArgument = process.argv.indexOf("--names");
const BY_HAND =
  namesArgument >= 0 && process.argv[namesArgument + 1]
    ? JSON.parse(readFileSync(process.argv[namesArgument + 1], "utf8"))
    : {};

const finalNames = new Map();
const isShort = (name) =>
  name.length <= 2 || /^[A-Z$]{1,3}$/.test(name) || MODULE_NAMES.has(name);
const edits = [];
const unnamed = [];
let renamedCount = 0;

for (const scope of scopes.scopes) {
  const blockLine = scope.block.loc.start.line;
  // Names already taken in this scope, so a rename never shadows or collides.
  // Every name visible from this scope, taken at its FINAL value.
  //
  // Checking original names is not enough: outer scopes are renamed first, so
  // by the time an inner scope is examined its parent may already hold the
  // name about to be chosen. That is how `const el` and a nested `const f`
  // both became `element` — legal to the parser, and a temporal dead zone at
  // runtime the moment the inner one is declared after a use of the outer.
  const taken = new Set();
  const add = (v) => taken.add(finalNames.get(v) ?? v.name);
  (function subtree(current) {
    for (const v of current.variables) add(v);
    for (const ref of current.through) taken.add(ref.identifier.name);
    for (const child of current.childScopes) subtree(child);
  })(scope);
  for (let up = scope.upper; up; up = up.upper) {
    for (const v of up.variables) add(v);
  }

  for (const variable of scope.variables) {
    if (!isShort(variable.name)) continue;
    const key = `${blockLine}:${variable.name}`;
    let chosen = BY_HAND[key] ?? nameFor(variable, scope);
    if (!chosen || chosen === variable.name) {
      unnamed.push({
        key,
        name: variable.name,
        line: variable.defs[0]?.name.loc.start.line,
        source: textOf(
          variable.defs[0]?.node?.parent?.type === "VariableDeclaration"
            ? variable.defs[0].node
            : (variable.defs[0]?.node ?? variable.defs[0].name),
        ).slice(0, 100),
      });
      continue;
    }
    // Collision-free: append a qualifier rather than shadow something.
    let candidate = chosen;
    let suffix = 2;
    while (taken.has(candidate)) candidate = `${chosen}${suffix++}`;
    taken.add(candidate);
    finalNames.set(variable, candidate);

    // Shorthand is a trap: in `{ n, aired }` the identifier IS the property
    // key, so replacing it renames the KEY as well and every reader of
    // `.n` downstream silently gets undefined. Expanding to `n: number`
    // keeps the shape of the object and renames only the variable.
    const record = (identifier) => {
      const parent = identifier.parent;
      // espree gives a shorthand property two DISTINCT nodes over the same
      // range, so identity is the wrong test — the range is the right one.
      const shorthand =
        parent?.type === "Property" &&
        parent.shorthand === true &&
        parent.value?.range?.[0] === identifier.range[0] &&
        parent.value?.range?.[1] === identifier.range[1];
      edits.push([
        identifier.range[0],
        identifier.range[1],
        shorthand ? `${identifier.name}: ${candidate}` : candidate,
      ]);
    };
    for (const identifier of variable.identifiers) record(identifier);
    for (const ref of variable.references) record(ref.identifier);
    renamedCount += 1;
  }
}

// Deduplicate (a declaration is both an identifier and a reference) and apply
// from the end, so every range stays valid while editing.
const seen = new Set();
const unique = edits.filter(([a, b]) => {
  const key = `${a}:${b}`;
  if (seen.has(key)) return false;
  seen.add(key);
  return true;
});
unique.sort((x, y) => y[0] - x[0]);

let output = script;
for (const [a, b, text] of unique) output = output.slice(0, a) + text + output.slice(b);

if (process.argv.includes("--write")) {
  writeFileSync(FRAGMENT, before + output + after);
  console.log(`written · ${renamedCount} variables renamed, ${unique.length} occurrences`);
} else {
  console.log(`dry run · ${renamedCount} variables renamed, ${unique.length} occurrences`);
  console.log(`${unnamed.length} with no derivable name:`);
  for (const r of unnamed) {
    console.log(`  ${r.key.padEnd(12)} l.${String(r.line).padEnd(6)} ${r.source}`);
  }
}
