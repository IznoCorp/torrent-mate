// Writes `x-rights` on every operation of the contract, from `OPERATION_RIGHTS`.
//
// THE TABLE IS WHERE A RIGHT IS DECIDED, and its comments say why; the contract is
// where the backend and the mock layer read it. This script carries the one into the
// other, and `operation-rights.test.ts` refuses a contract that drifts from the table.
//
// IT EDITS THE TEXT, NEVER RE-SERIALISES IT. The contract is laid out the way
// Python's `json.dumps(indent=2, ensure_ascii=False)` lays it out, which
// `JSON.stringify` does not reproduce (it reorders integer-like keys), so each
// operation's `x-rights` line is replaced or inserted right after its `operationId`.
//
// Run with `npm run stamp-operation-rights`.
import { readFileSync, writeFileSync } from "node:fs";
import { OPERATION_RIGHTS } from "../src/mocks/operation-rights.ts";

const CONTRACT = new URL("../../../../contract/openapi.json", import.meta.url);

/**
 * Renders one value as the contract's layout does, at an indentation.
 *
 * @param asked What the operation asks for.
 * @param indent The indentation of the key's line.
 * @returns The JSON text, a list spread one member per line.
 */
function render(asked: unknown, indent: string): string {
  if (!Array.isArray(asked)) return JSON.stringify(asked);
  const members = asked.map((right) => `${indent}  ${JSON.stringify(right)}`).join(",\n");
  return `[\n${members}\n${indent}]`;
}

const lines = readFileSync(CONTRACT, "utf-8").split("\n");
const written: string[] = [];
const seen = new Set<string>();
for (let index = 0; index < lines.length; index += 1) {
  const line = lines[index];
  written.push(line);
  const found = /^(\s*)"operationId": "([^"]+)",$/.exec(line);
  if (found === null) continue;
  const [, indent, operationId] = found;
  if (!(operationId in OPERATION_RIGHTS)) {
    throw new Error(`${operationId} is in the contract and not in OPERATION_RIGHTS`);
  }
  seen.add(operationId);
  // An `x-rights` already written there is replaced, list members and all.
  if (lines[index + 1]?.startsWith(`${indent}"x-rights": `)) {
    index += 1;
    if (lines[index].endsWith("[")) {
      while (!lines[index].startsWith(`${indent}]`)) index += 1;
    }
  }
  written.push(`${indent}"x-rights": ${render(OPERATION_RIGHTS[operationId], indent)},`);
}
const absent = Object.keys(OPERATION_RIGHTS).filter((operationId) => !seen.has(operationId));
if (absent.length > 0) throw new Error(`not in the contract: ${absent.join(", ")}`);
writeFileSync(CONTRACT, written.join("\n"));
console.log(`stamp-operation-rights: ${seen.size} operations`);
