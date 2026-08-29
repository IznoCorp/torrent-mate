/**
 * Report every JSX element that paints and carries no class of its own.
 *
 * Why a parser and not a regex: an attribute list spans lines, a `className`
 * can be a template literal, a conditional or a spread, and an element can be
 * written inside a template string that a text reader sees as prose. The
 * question « does this element carry a class? » has a node kind for an answer
 * and nothing else gives it reliably — which is the same argument
 * `rename.mjs` makes for its own subject.
 *
 * WHAT COUNTS AS PAINTING. Only the tags whose user-agent appearance is wrong
 * on a dark surface when nothing dresses them: a control, a field, a link, an
 * image. A `<div>` or a `<span>` with no class paints nothing at all and is
 * not a candidate — counting them would produce a list nobody could read and
 * a ratchet nobody could hold.
 *
 * A SPREAD COUNTS AS A CLASS. `{...props}` may carry `className`, and this
 * reader cannot know. Refusing it would report defects that are not ones; the
 * count of elements skipped for that reason is printed, so the blind spot is
 * a number rather than a sentence.
 */
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const typescript = require(process.argv[2]);
const files = process.argv.slice(3);

/** The tags the user agent paints, and paints wrongly when left undressed. */
const PAINTED = new Set(["button", "input", "select", "textarea", "a", "img"]);

const findings = [];
let elements = 0;
let spreads = 0;

for (const file of files) {
  const source = readFileSync(file, "utf8");
  const tree = typescript.createSourceFile(
    file, source, typescript.ScriptTarget.Latest, true,
    typescript.ScriptKind.TSX,
  );

  const walk = (node) => {
    const opening =
      typescript.isJsxOpeningElement(node) || typescript.isJsxSelfClosingElement(node)
        ? node
        : null;
    if (opening && typescript.isIdentifier(opening.tagName)
        && PAINTED.has(opening.tagName.text)) {
      elements += 1;
      let dressed = false;
      let spread = false;
      for (const attribute of opening.attributes.properties) {
        if (typescript.isJsxSpreadAttribute(attribute)) { spread = true; continue; }
        const name = attribute.name && attribute.name.text;
        if (name === "className" || name === "class") dressed = true;
      }
      if (spread) spreads += 1;
      if (!dressed && !spread) {
        const { line } = tree.getLineAndCharacterOfPosition(opening.getStart(tree));
        findings.push({ file, line: line + 1, tag: opening.tagName.text });
      }
    }
    typescript.forEachChild(node, walk);
  };
  walk(tree);
}

process.stdout.write(JSON.stringify({ elements, spreads, findings }));
