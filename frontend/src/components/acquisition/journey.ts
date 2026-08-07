/**
 * journey — pure §14.3 derivations over a stored acquisition journey.
 *
 * Their own module: these answer « which stage was reached » and « which
 * journey belongs to this wanted row », and both answers must stay
 * panel-independent (§13). Typing the stage as {@link Stage} rather than
 * string means an impossible value fails `tsc`, not a rendering.
 */

import type { JourneyItem } from "@/api/acquisition";

import type { Stage } from "./JourneyStrip";

/**
 * Build a unique key for matching a wanted/en-vol item to a journey row.
 *
 * ``WantedItem`` has no ``info_hash``, so we match by title + season + episode
 * + kind — sufficient for the « En vol » section where a given episode is
 * rarely grabbed twice simultaneously.  Journey ``kind`` is more specific
 * (``"episode"`` vs ``"show"``) so we normalise it.
 */
export function journeyMatchKey(
  title: string,
  kind: string,
  season: number | null,
  episode: number | null,
): string {
  // Journey kind is "episode"/"movie"/null; wanted kind is "show"/"movie".
  // Normalise "episode" → "show" so a show follow matches its episode journeys.
  const normalised = kind === "episode" ? "show" : kind;
  return `${title}||${normalised}||${String(season ?? "")}||${String(episode ?? "")}`;
}

/**
 * Derive the journey stage from the per-stage timestamps.
 *
 * Returns the ``Stage`` literal for the latest reached station, or ``null``
 * when the stage cannot be established — for instance a ``reconstructed_at``
 * row with gaps (§14.3: absent timestamp on a rebuilt row means « unknown »,
 * not « not reached »), or no matching journey at all.
 *
 * Args:
 *   j: The matching journey row, or ``undefined``.
 *
 * Returns:
 *   The stage, or ``null`` when the strip must be omitted.
 */
export function deriveStage(j: JourneyItem | undefined): Stage | null {
  if (j == null) return null;

  const { grabbed_at, ingested_at, scraped_at, dispatched_at, reconstructed_at } = j;

  // Find the latest reached station (top-down: dispatched → scraped → ingested → grabbed).
  let stage: Stage;
  if (dispatched_at != null) stage = "range";
  else if (scraped_at != null) stage = "scrape";
  else if (ingested_at != null) stage = "ingere";
  else if (grabbed_at != null) stage = "telech";
  else stage = "pris";

  // §14.3: on a rebuilt row, an absent intermediate timestamp means UNKNOWN.
  // If any station BEFORE the latest is missing, we cannot draw a confident path.
  if (reconstructed_at != null) {
    const expected = [grabbed_at, ingested_at, scraped_at, dispatched_at];
    const stageIdx = ["pris", "telech", "ingere", "scrape", "range"].indexOf(stage);
    // Every timestamp up to and including the latest must be present.
    for (let i = 1; i <= stageIdx; i++) {
      if (expected[i - 1] == null) return null;
    }
  }

  return stage;
}
