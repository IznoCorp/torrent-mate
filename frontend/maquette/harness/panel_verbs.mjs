/**
 * Report every `data-*` verb a panel action emits, and how it was written.
 *
 * A PANEL ACTION IS `{ text, icone, target, … }` AND `target` IS A MAP OF DATA
 * ATTRIBUTES. `ui/panel` draws those attributes onto the button and attaches no
 * handler of its own, by contract — the tap is answered by a document-level
 * delegation somewhere else. So the keys of that map are the only thing on the
 * emitting side that says which verb the button carries, and this reader
 * collects them.
 *
 * WHY A PARSER AND NOT A REGEX, and it was measured rather than assumed. A
 * first reading of `target: { … }` by regular expression over the same corpus
 * answered `add` for `target: { act: `add:${position}` }` — a template
 * literal's own text read as a key — and `panels.maintenance.launchedDry` for a
 * map whose value is a translated call spanning three lines. Both are keys that
 * exist nowhere. « Which names does this object literal declare » has a node
 * kind for an answer, and the same argument `bare_elements.mjs` and
 * `rename.mjs` each make for their own subject.
 *
 * THE DIALOG'S ACTIONS ARE A DIFFERENT SHAPE AND ARE REPORTED AS SUCH. A
 * `DialogAction` carries a `target` too, but the dialog spreads those keys
 * VERBATIM (they are written `data-…` already) and attaches its own `onClick`
 * that runs the action's `run` closure. Its verbs are therefore answered by the
 * component that draws them, which is exactly what a panel action's are not.
 * Each map is reported with the sibling names of the action holding it and with
 * whether its own keys carry the `data-` prefix, so the side that reads this
 * classifies rather than guessing — and prints how many it set aside.
 *
 * A COMPUTED KEY NAMES NO LITERAL. `target: { [name]: value }` is reported as
 * computed and counted, never half-read, exactly as the markup guard's other
 * arms skip a computed emission rather than inventing what it evaluates to.
 *
 * A `target` IS NOT ALWAYS SPELLED AS AN OBJECT LITERAL, and the first version
 * of this reader saw only the ones that were. The sort panel writes
 * `target: (reversed ? { setsort, reversed } : { setsort }) as Record<…>` — two
 * shapes rather than one with an undefined field, deliberately, because an
 * undefined value would still emit the attribute. A reader that matched only a
 * bare object literal skipped that whole map and reported one fewer verb with
 * no sign that it had, which is the short count this guard exists to refuse. So
 * parentheses, `as` assertions, conditionals and `??` / `||` are unwrapped and
 * EVERY branch that is an object literal is read. What unwrapping cannot reach
 * — a `target` handed a variable or a call — is counted as unresolved and
 * printed, never passed over in silence.
 */
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const typescript = require(process.argv[2]);
const files = process.argv.slice(3);

/** The name of the property whose object literal holds the verbs. */
const TARGET = "target";

/**
 * The declared name of one property, or null when it is computed or a spread.
 */
function nameOf(property) {
  if (typescript.isSpreadAssignment(property)) return null;
  const name = property.name;
  if (name === undefined) return null;
  if (typescript.isIdentifier(name)) return name.text;
  if (typescript.isStringLiteral(name)) return name.text;
  return null;
}

/**
 * Every object literal one `target` expression can evaluate to.
 *
 * Returns an empty list for an expression this reader cannot resolve — a
 * variable, a call — which the caller counts rather than passing over.
 */
function literalsOf(expression) {
  if (typescript.isParenthesizedExpression(expression)
      || typescript.isAsExpression(expression)
      || typescript.isSatisfiesExpression(expression)
      || typescript.isNonNullExpression(expression)) {
    return literalsOf(expression.expression);
  }
  if (typescript.isConditionalExpression(expression)) {
    return [...literalsOf(expression.whenTrue), ...literalsOf(expression.whenFalse)];
  }
  if (typescript.isBinaryExpression(expression)
      && (expression.operatorToken.kind === typescript.SyntaxKind.QuestionQuestionToken
        || expression.operatorToken.kind === typescript.SyntaxKind.BarBarToken)) {
    return [...literalsOf(expression.left), ...literalsOf(expression.right)];
  }
  return typescript.isObjectLiteralExpression(expression) ? [expression] : [];
}

const maps = [];
let computed = 0;
let unresolved = 0;

for (const file of files) {
  const source = readFileSync(file, "utf8");
  const tree = typescript.createSourceFile(
    file, source, typescript.ScriptTarget.Latest, true,
    typescript.ScriptKind.TSX,
  );

  const walk = (node) => {
    if (typescript.isPropertyAssignment(node) && nameOf(node) === TARGET) {
      const { line } = tree.getLineAndCharacterOfPosition(node.getStart(tree));
      const literals = literalsOf(node.initializer);
      if (literals.length === 0) unresolved += 1;
      // The ACTION holding this map, when the map sits in an object literal.
      // Its other property names say which surface's action this is — the
      // dialog's `run` / `dismiss` / `tone` against the panel's `ton`,
      // `icone`, `mention`. Read here because the tree is here; classified on
      // the other side, where the reason can be printed.
      const holder = node.parent;
      const siblings = typescript.isObjectLiteralExpression(holder)
        ? holder.properties
          .map(nameOf)
          .filter((name) => name !== null && name !== TARGET)
        : [];
      for (const literal of literals) {
        const verbs = [];
        for (const property of literal.properties) {
          const name = nameOf(property);
          if (name === null) { computed += 1; continue; }
          verbs.push(name);
        }
        maps.push({ file, line: line + 1, verbs, siblings });
      }
    }
    typescript.forEachChild(node, walk);
  };
  walk(tree);
}

process.stdout.write(JSON.stringify({ maps, computed, unresolved }));
