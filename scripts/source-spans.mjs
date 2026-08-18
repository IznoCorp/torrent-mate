/**
 * Prints the spans a renamer must NOT touch in a TypeScript/JSX source.
 *
 * Three kinds of text look like code and are not: a string literal, the text
 * between two JSX tags, and a regular-expression literal. Each one cost this
 * repository a corruption. A sentence between a `<p>` and its closing tag
 * carries no quote, so a quote-aware scanner reads it as code; and a regex
 * literal holding an APOSTROPHE — this interface is written in French, so its
 * patterns are full of them — opens a string that never closes, after which
 * every literal in the file is read as code.
 *
 * No heuristic separates them reliably — prose between `}` and `{` also
 * describes `} export function Name(): Thing {`. The compiler's parser does,
 * and it is already a dependency of this frontend.
 *
 * Usage: node scripts/source-spans.mjs <file>
 * Output: one `kind start end` triple per line — `protected` or `comment`.
 */
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const require_ = createRequire(import.meta.url);
const ts = require_("../frontend/node_modules/typescript");

const file = process.argv[2];
const text = readFileSync(file, "utf8");
const source = ts.createSourceFile(
  file, text, ts.ScriptTarget.Latest, true,
  /\.(tsx|jsx)$/.test(file) ? ts.ScriptKind.TSX : ts.ScriptKind.TS);

// A template's fixed pieces are protected; its `${…}` interpolations are code
// and are where most of this engine's markup reads its state, so the head,
// middle and tail spans are emitted one by one rather than the whole literal.
const PROTECTED = new Set([
  ts.SyntaxKind.JsxText,
  ts.SyntaxKind.StringLiteral,
  ts.SyntaxKind.NoSubstitutionTemplateLiteral,
  ts.SyntaxKind.TemplateHead,
  ts.SyntaxKind.TemplateMiddle,
  ts.SyntaxKind.TemplateTail,
  ts.SyntaxKind.RegularExpressionLiteral,
]);

const out = [];
const walk = (node) => {
  if (PROTECTED.has(node.kind)) out.push(["protected", node.getStart(source), node.getEnd()]);
  ts.forEachChild(node, walk);
};
walk(source);

// Comments carry backticked mentions of identifiers, which DO move with a
// rename, so they are reported apart rather than protected outright.
//
// They are read off the syntax tree, never from a standalone scanner: a
// scanner with no parser behind it cannot tell `/` dividing from `/` opening a
// pattern, and the one tried here silently stopped reporting comments a third
// of the way through the file — the very failure this tool exists to prevent.
// The walk goes down to TOKENS, and reads both trivia kinds: a comment on its
// own line leads the token after it, while one sharing a line with the code
// before it trails that token, and reading only the first kind left exactly
// those uncaught.
const seen = new Set();
const comments = (node) => {
  for (const [get, at] of [[ts.getLeadingCommentRanges, node.getFullStart()],
                           [ts.getTrailingCommentRanges, node.getEnd()]]) {
    for (const range of get(text, at) ?? []) {
      const key = `${range.pos}:${range.end}`;
      if (!seen.has(key)) { seen.add(key); out.push(["comment", range.pos, range.end]); }
    }
  }
  for (const child of node.getChildren(source)) comments(child);
};
comments(source);
for (const range of ts.getTrailingCommentRanges(text, source.getEnd()) ?? []) {
  out.push(["comment", range.pos, range.end]);
}

for (const [k, a, b] of out.sort((x, y) => x[1] - y[1])) console.log(`${k} ${a} ${b}`);
