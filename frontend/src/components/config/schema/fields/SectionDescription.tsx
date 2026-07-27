/**
 * SectionDescription — a collapsible one-line summary for a schema section.
 */

import { useState, type ReactElement } from "react";

/**
 * SectionDescription — a section docstring truncated to its first sentence with
 * an "En savoir plus" toggle. Full Pydantic docstrings ("… Attributes: language:
 * …") are a wall of text; the first sentence is the useful summary and the
 * per-field help text covers the rest (F7).
 *
 * Args:
 *   text: The full section description string.
 *
 * Returns:
 *   The collapsible description element.
 */
export function SectionDescription({ text }: { text: string }): ReactElement {
  const [expanded, setExpanded] = useState(false);
  // Google-style docstrings put the one-line summary before the first blank
  // line ("… tunables.\n\nAttributes: …"), so the first line IS the summary.
  // (Splitting on ". " gets fooled by "e.g." abbreviations.) Cap a runaway
  // single line so it can never itself be a wall of text.
  const trimmed = text.trim();
  const firstLine = (trimmed.split("\n", 1)[0] ?? trimmed).trim();
  const CAP = 200;
  const summary =
    firstLine.length > CAP
      ? `${firstLine.slice(0, CAP).trimEnd()}…`
      : firstLine;
  const isLong = summary.length < trimmed.length;
  return (
    <div className="flex flex-col items-start gap-0.5">
      <p className="whitespace-pre-line text-xs text-muted-foreground">
        {expanded || !isLong ? trimmed : summary}
      </p>
      {isLong && (
        <button
          type="button"
          onClick={() => {
            setExpanded((v) => !v);
          }}
          className="text-xs font-medium text-primary hover:underline"
        >
          {expanded ? "Réduire" : "En savoir plus"}
        </button>
      )}
    </div>
  );
}
