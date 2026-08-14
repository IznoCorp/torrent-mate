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

const RACINE = "/Users/izno/dev/PersonalScraper/frontend";
const espree = await import(`${RACINE}/node_modules/espree/dist/espree.cjs`);
const eslintScope = (await import(`${RACINE}/node_modules/eslint-scope/dist/eslint-scope.cjs`)).default;

const CHEMIN = `${RACINE}/maquette/design/refonte.html`;

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
const NOMS_DE_MODULE = new Set(Object.keys(SINGLETONS));

/** Names that are already clear enough at two characters. */
const GARDER = new Set(["id"]);

/** Collections whose singular is not just « drop the s ». */
const SINGULIERS = {
  follows: "follow",
  suggestions: "suggestion",
  releases: "release",
  entries: "entry",
  candidates: "candidate",
  saisons: "saison",
  seasons: "season",
  states: "state",
  regions: "region",
  categories: "category",
  properties: "property",
  children: "child",
  values: "value",
  keys: "key",
  titres: "titre",
  titles: "title",
  episodes: "episode",
  items: "item",
  lignes: "ligne",
  bits: "bit",
  parts: "part",
  rows: "row",
  cards: "card",
  tiles: "tile",
};

const singulier = (nom) =>
  SINGULIERS[nom] ?? (nom.endsWith("s") && nom.length > 3 ? nom.slice(0, -1) : nom);

const ITERATEURS = new Set([
  "map", "filter", "find", "findIndex", "some", "every", "forEach", "flatMap", "sort", "reduce",
]);

const html = readFileSync(CHEMIN, "utf8");
const ouvre = html.indexOf("<script>");
const ferme = html.lastIndexOf("</script>");
const avant = html.slice(0, ouvre + "<script>".length);
const script = html.slice(ouvre + "<script>".length, ferme);
const apres = html.slice(ferme);

const ast = espree.parse(script, {
  ecmaVersion: "latest",
  sourceType: "script",
  loc: true,
  range: true,
});

// Parent links: the naming rules need to look upward, and espree sets none.
(function relier(noeud, parent) {
  if (!noeud || typeof noeud !== "object") return;
  if (Array.isArray(noeud)) {
    for (const x of noeud) relier(x, parent);
    return;
  }
  if (typeof noeud.type === "string") {
    Object.defineProperty(noeud, "parent", { value: parent, enumerable: false, writable: true });
    for (const [clef, valeur] of Object.entries(noeud)) relier(valeur, noeud);
  }
})(ast, null);

const portees = eslintScope.analyze(ast, { ecmaVersion: 2024, sourceType: "script" });
const texteDe = (noeud) => script.slice(noeud.range[0], noeud.range[1]);

/**
 * Chooses a name for a variable from what the surrounding code says.
 *
 * @param {object} variable an eslint-scope Variable
 * @param {object} portee its scope
 * @returns {string|null} the new name, or null to leave it alone
 */
function nommer(variable, portee) {
  const nom = variable.name;
  if (nom === "arguments" || GARDER.has(nom)) return null;
  if (portee.type === "module" || portee.block.type === "Program") {
    if (SINGLETONS[nom]) return SINGLETONS[nom];
  }
  if (SINGLETONS[nom] && nom !== "S" && nom !== "W" && nom !== "D") return SINGLETONS[nom];

  const def = variable.defs[0];
  if (!def) return null;
  const noeud = def.name;
  const genre = def.type;

  // A callback parameter is named by what it iterates.
  if (genre === "Parameter") {
    const fonction = def.node;
    const appel = fonction.parent;
    if (appel?.type === "CallExpression" && appel.callee?.type === "MemberExpression") {
      const methode = appel.callee.property?.name;
      if (ITERATEURS.has(methode)) {
        const rang = fonction.params.indexOf(noeud);
        if (rang === 1) return methode === "reduce" ? "element" : "index";
        if (rang === 2) return "collection";
        if (rang === 0) {
          if (methode === "reduce") return "accumulator";
          const receveur = appel.callee.object;
          const source =
            receveur.type === "MemberExpression" ? receveur.property?.name
            : receveur.type === "Identifier" ? receveur.name
            : receveur.type === "CallExpression" && receveur.callee?.type === "MemberExpression"
              ? receveur.callee.property?.name
              : null;
          if (source && /^[a-zA-Z_]/.test(source)) return singulier(source);
          return "element";
        }
      }
    }
    // An event handler's parameter.
    if (
      appel?.type === "CallExpression" &&
      appel.callee?.property?.name === "addEventListener"
    ) {
      return "event";
    }
    if (genre === "Parameter" && nom === "e") return "event";
    return null; // named by hand below, or left as is
  }

  if (genre === "Variable" && def.node?.init) {
    const init = def.node.init;
    if (init.type === "CallExpression") {
      const appelee = init.callee;
      const methode = appelee?.property?.name ?? appelee?.name;
      if (methode === "querySelector" || methode === "getElementById" || methode === "select") {
        return "element";
      }
      if (methode === "querySelectorAll") return "elements";
      if (methode === "getBoundingClientRect") return "rect";
      if (methode === "find") return "found";
      if (methode === "getComputedStyle") return "styles";
      if (methode && /^[a-z][\w]{2,}$/.test(methode)) return methode;
    }
    if (init.type === "MemberExpression" && init.property?.name) {
      const p = init.property.name;
      if (/^[a-z][\w]{2,}$/.test(p)) return p;
    }
  }
  return null;
}

/** Hand-authored names, keyed by `scopeLine:oldName`, for what rules cannot see. */
const AU_CAS_PAR_CAS = JSON.parse(
  readFileSync(
    "/private/tmp/claude-501/-Users-izno-dev-PersonalScraper/8b2afafb-4484-4e1e-b3e1-cee400fe2d5b/scratchpad/noms.json",
    "utf8",
  ),
);

const nomsFinaux = new Map();
const court = (nom) =>
  nom.length <= 2 || /^[A-Z$]{1,3}$/.test(nom) || NOMS_DE_MODULE.has(nom);
const edits = [];
const restants = [];
let renommees = 0;

for (const portee of portees.scopes) {
  const ligneBloc = portee.block.loc.start.line;
  // Names already taken in this scope, so a rename never shadows or collides.
  // Every name visible from this scope, taken at its FINAL value.
  //
  // Checking original names is not enough: outer scopes are renamed first, so
  // by the time an inner scope is examined its parent may already hold the
  // name about to be chosen. That is how `const el` and a nested `const f`
  // both became `element` — legal to the parser, and a temporal dead zone at
  // runtime the moment the inner one is declared after a use of the outer.
  const pris = new Set();
  const ajouter = (v) => pris.add(nomsFinaux.get(v) ?? v.name);
  (function sousArbre(courante) {
    for (const v of courante.variables) ajouter(v);
    for (const ref of courante.through) pris.add(ref.identifier.name);
    for (const enfant of courante.childScopes) sousArbre(enfant);
  })(portee);
  for (let haut = portee.upper; haut; haut = haut.upper) {
    for (const v of haut.variables) ajouter(v);
  }

  for (const variable of portee.variables) {
    if (!court(variable.name)) continue;
    const clef = `${ligneBloc}:${variable.name}`;
    let neuf = AU_CAS_PAR_CAS[clef] ?? nommer(variable, portee);
    if (!neuf || neuf === variable.name) {
      restants.push({
        clef,
        nom: variable.name,
        ligne: variable.defs[0]?.name.loc.start.line,
        source: texteDe(
          variable.defs[0]?.node?.parent?.type === "VariableDeclaration"
            ? variable.defs[0].node
            : (variable.defs[0]?.node ?? variable.defs[0].name),
        ).slice(0, 100),
      });
      continue;
    }
    // Collision-free: append a qualifier rather than shadow something.
    let candidat = neuf;
    let suffixe = 2;
    while (pris.has(candidat)) candidat = `${neuf}${suffixe++}`;
    pris.add(candidat);
    nomsFinaux.set(variable, candidat);

    // Shorthand is a trap: in `{ n, aired }` the identifier IS the property
    // key, so replacing it renames the KEY as well and every reader of
    // `.n` downstream silently gets undefined. Expanding to `n: number`
    // keeps the shape of the object and renames only the variable.
    const inscrire = (identifiant) => {
      const parent = identifiant.parent;
      // espree gives a shorthand property two DISTINCT nodes over the same
      // range, so identity is the wrong test — the range is the right one.
      const abrege =
        parent?.type === "Property" &&
        parent.shorthand === true &&
        parent.value?.range?.[0] === identifiant.range[0] &&
        parent.value?.range?.[1] === identifiant.range[1];
      edits.push([
        identifiant.range[0],
        identifiant.range[1],
        abrege ? `${identifiant.name}: ${candidat}` : candidat,
      ]);
    };
    for (const identifiant of variable.identifiers) inscrire(identifiant);
    for (const ref of variable.references) inscrire(ref.identifier);
    renommees += 1;
  }
}

// Deduplicate (a declaration is both an identifier and a reference) and apply
// from the end, so every range stays valid while editing.
const vus = new Set();
const uniques = edits.filter(([a, b]) => {
  const clef = `${a}:${b}`;
  if (vus.has(clef)) return false;
  vus.add(clef);
  return true;
});
uniques.sort((x, y) => y[0] - x[0]);

let sortie = script;
for (const [a, b, texte] of uniques) sortie = sortie.slice(0, a) + texte + sortie.slice(b);

if (process.argv.includes("--ecrire")) {
  writeFileSync(CHEMIN, avant + sortie + apres);
  console.log(`écrit · ${renommees} variables renommées, ${uniques.length} occurrences`);
} else {
  console.log(`à blanc · ${renommees} variables renommées, ${uniques.length} occurrences`);
  console.log(`${restants.length} sans nom dérivable :`);
  for (const r of restants) {
    console.log(`  ${r.clef.padEnd(12)} l.${String(r.ligne).padEnd(6)} ${r.source}`);
  }
}
