// Extract the operator-editable FREEFORM region from a ticket body: strip the kanban status block,
// the protected marker lines (roadmap/codename/design/plans), and the `## Brainstorm` section, so
// the editor shows only what the operator may change. The server re-merges the protected regions on
// save (PATCH /ticket/{n}/body), so we send back only this freeform.
export function extractFreeform(body) {
  if (!body) return "";
  const STATUS_BEGIN = "<!-- kanban:status:begin -->";
  const STATUS_END = "<!-- kanban:status:end -->";
  let text = body;
  const sbStart = text.indexOf(STATUS_BEGIN);
  const sbEnd = text.indexOf(STATUS_END);
  if (sbStart !== -1 && sbEnd !== -1) {
    text = text.slice(0, sbStart) + text.slice(sbEnd + STATUS_END.length);
  }
  // Only the known kanban marker keys — anchoring preserves the operator's own bold-prefixed prose.
  text = text.replace(/^\*\*(?:roadmap|codename|design|plans)\*\*:[^\n]*$/gm, "");
  const bsIdx = text.indexOf("## Brainstorm");
  if (bsIdx !== -1) text = text.slice(0, bsIdx);
  return text.trim();
}
