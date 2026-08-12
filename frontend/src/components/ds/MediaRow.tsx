/**
 * MediaRow — the ONE list card of the interface.
 *
 * It draws a medium as a row: poster on the left, facts on the right, an
 * optional journey strip and an optional action beneath. Every list renders
 * through it, so the transverse rules are enforced once rather than re-derived
 * per surface:
 *
 * - **R1** — a card's actions live in its detail sheet and its swipe panes,
 *   never in a control floating over the surface that translates.
 * - **R2** — the strip and the action are full-width own lines, never siblings
 *   of the title row in a `row` flex, which squeezed the journey strip into a
 *   narrow column and overlapped its labels.
 * - **R3** — the title line accepts nothing but the title (§12). Everything
 *   that qualifies the medium goes on the facts line, the only one that wraps.
 * - **§11** — the poster is a button only when `onPoster` is given, and the
 *   body is a button only when `onOpen` is given. For an item with no detail
 *   sheet or no media sheet the corresponding element is not a disabled
 *   button, it is not a button at all: §11 forbids a dead link, and a greyed
 *   control is the same broken promise.
 *
 * **It takes FACTS, never markup.** It was called `AcquisitionCard`, it lived
 * under `acquisition/` although nothing about it is acquisition-specific, and
 * its meta line was a `ReactNode` a caller filled in — which made the card an
 * envelope, and an envelope guarantees nothing about what it carries. Three
 * surfaces were already assembling that line by hand, each deciding its own
 * order and its own spacing. A view wanting something the facts below cannot
 * express is describing a fact this card does not know about yet: the fix is
 * to add the fact, never to pass ready-made markup.
 */

import { type ReactElement } from "react";
import { Link } from "react-router-dom";

import { JourneyStrip } from "@/components/acquisition/JourneyStrip";
import type { Stage } from "@/components/acquisition/JourneyStrip";
import { TONE_CHIP_CLASS } from "@/components/acquisition/meta";
import { Chip } from "@/components/ds/Chip";
import { MediaPoster } from "@/components/ds/MediaPoster";
import { Panel } from "@/components/ds/Panel";
import { posterThumb } from "@/lib/poster-thumb";

/**
 * One item of the facts line, as a FACT rather than as markup.
 *
 * The order is the caller's, because it is the order the operator reads: how
 * much is owned, then what state it is in, then what annotates that state.
 *
 * - `fraction` — how much of a medium is held, in the mono face.
 * - `chip` — a dotted status chip.
 * - `gauge` — a live measurement in the tone of its state (a percentage).
 * - `note` — a muted aside: an ETA, an elapsed time, a count.
 * - `alert` — the same, when what it says is a failure.
 * - `release` — the release name actually grabbed, mono and truncating: it is
 *   what tells a soundtrack apart from the film of the same name.
 * - `fresh` — what has just arrived.
 */
export type MediaFact =
  | { readonly kind: "fraction"; readonly text: string }
  | { readonly kind: "chip"; readonly tone: string; readonly text: string; readonly hint?: string | undefined }
  | { readonly kind: "gauge"; readonly tone: string; readonly text: string }
  | { readonly kind: "note"; readonly text: string }
  | { readonly kind: "alert"; readonly text: string }
  | { readonly kind: "release"; readonly text: string; readonly hint?: string | undefined }
  | { readonly kind: "fresh" };

/** The action drawn full-width under the card, when a section exists for it. */
export interface MediaRowAction {
  /** The verb, exactly as the section's own heading phrases it. */
  readonly label: string;
  /** Where it goes. An action without a destination is not an action (R2). */
  readonly href: string;
  /** `danger` for an action that answers something blocking. */
  readonly tone?: "danger";
}

/** Props for {@link MediaRow}. */
export interface MediaRowProps {
  /** The media title — alone on its line (R3). */
  readonly title: string;
  /** Poster URL, or `null` for the initial-letter placeholder. */
  readonly posterUrl: string | null;
  /** One-line qualifier; truncates. */
  readonly subtitle?: string;
  /** Why this item needs a decision; wraps to two lines and never truncates (§12). */
  readonly reason?: string;
  /** The facts line, in the caller's order. */
  readonly facts?: readonly MediaFact[];
  /** Tap on the body → the detail sheet. Omit when the card has no detail sheet
   *  — exactly the same rationale as {@link onPoster}: a button that does nothing
   *  is a dead control (§11). */
  readonly onOpen?: () => void;
  /** Tap on the poster → the media sheet. Omit when the media has no sheet (§11). */
  readonly onPoster?: () => void;
  /** Tooltip on a non-linked poster. The default fits an UNIDENTIFIED item; a
   *  surface whose item is identified but merely unlinkable here must not let
   *  the card claim « non identifié » about it — that claim would be false. */
  readonly posterHint?: string | undefined;
  /** Where the medium is in its journey — drawn full-width under the top row
   *  (R2). Omitted entirely when the stage cannot be established: « inconnue »
   *  is not « pas faite » (§14.3). */
  readonly journey?: { readonly stage: Stage; readonly blocked?: boolean };
  /** The inline shortcut, when a section exists FOR that action. */
  readonly action?: MediaRowAction;
}

/** Props for the inner body — extracted so button/div share one copy. */
interface CardBodyProps {
  readonly title: string;
  // `| undefined` is required, not decorative: exactOptionalPropertyTypes is on,
  // so an optional prop and a prop explicitly passed as undefined are different
  // types, and the card spreads its own optionals straight through to here.
  readonly subtitle?: string | undefined;
  readonly reason?: string | undefined;
  readonly facts?: readonly MediaFact[] | undefined;
}

/** Renders one fact of the facts line. */
function factHTML(fact: MediaFact, index: number): ReactElement | null {
  switch (fact.kind) {
    case "fraction":
      return (
        <span key={index} className="font-mono text-xs text-muted-foreground tabular-nums">
          {fact.text}
        </span>
      );
    case "chip":
      return (
        <Chip key={index} tone={fact.tone} title={fact.hint}>
          {fact.text}
        </Chip>
      );
    case "gauge":
      return (
        <span
          key={index}
          className={`rounded px-1.5 py-px text-xs font-medium tabular-nums ${TONE_CHIP_CLASS[fact.tone] ?? "bg-muted text-muted-foreground"}`}
        >
          {fact.text}
        </span>
      );
    case "note":
      return (
        <span key={index} className="text-xs text-muted-foreground">
          {fact.text}
        </span>
      );
    case "alert":
      return (
        <span key={index} className="text-xs text-danger">
          {fact.text}
        </span>
      );
    case "release":
      return (
        <span
          key={index}
          className="min-w-0 truncate font-mono text-[length:var(--text-2xs)] text-muted-foreground"
          {...(fact.hint != null ? { title: fact.hint } : {})}
        >
          {fact.text}
        </span>
      );
    case "fresh":
      return (
        <span key={index} data-testid="chip-nouveau" className="freshtag">
          Nouveau
        </span>
      );
    default:
      return null;
  }
}

/** The card's inner content — title line, subtitle, reason, facts. */
function MediaRowBody({
  title,
  subtitle,
  reason,
  facts,
}: CardBodyProps): ReactElement {
  return (
    <span className="block min-w-0 flex-1">
      <span data-testid="acq-card-title" className="block truncate text-sm font-semibold">
        {title}
      </span>
      {subtitle != null && (
        <span className="mt-0.5 block truncate text-xs text-muted-foreground">{subtitle}</span>
      )}
      {reason != null && (
        <span className="mt-0.5 line-clamp-2 block text-xs text-muted-foreground">
          {reason}
        </span>
      )}
      {facts != null && facts.length > 0 && (
        <span className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1">
          {facts.map(factHTML)}
        </span>
      )}
    </span>
  );
}

/**
 * Render one media row.
 *
 * Args:
 *   props: See {@link MediaRowProps}.
 *
 * Returns:
 *   The card element.
 */
export function MediaRow({
  title,
  posterUrl,
  subtitle,
  reason,
  facts,
  onOpen,
  onPoster,
  posterHint,
  journey,
  action,
}: MediaRowProps): ReactElement {
  const poster = (
    <MediaPoster title={title} src={posterThumb(posterUrl)} className="w-[38px]" />
  );

  return (
    <Panel data-testid="acq-card" className="flex w-full flex-col p-[9px]">
      <div data-testid="acq-card-top" className="flex min-w-0 items-center gap-[10px]">
        {onPoster ? (
          <button
            type="button"
            className="shrink-0 leading-none"
            aria-label={`Fiche de ${title}`}
            onClick={onPoster}
          >
            {poster}
          </button>
        ) : (
          <span
            className="shrink-0 leading-none"
            title={posterHint ?? "Média non identifié — pas de fiche disponible."}
          >
            {poster}
          </span>
        )}

        {onOpen ? (
          <button
            type="button"
            className="flex min-w-0 flex-1 items-center gap-[10px] text-left"
            aria-label={title}
            onClick={onOpen}
          >
            <MediaRowBody
              title={title}
              subtitle={subtitle}
              reason={reason}
              facts={facts}
            />
          </button>
        ) : (
          <div className="flex min-w-0 flex-1 items-center gap-[10px]">
            <MediaRowBody
              title={title}
              subtitle={subtitle}
              reason={reason}
              facts={facts}
            />
          </div>
        )}
      </div>

      {journey != null && (
        <JourneyStrip stage={journey.stage} blocked={journey.blocked ?? false} />
      )}
      {action != null && (
        <Link
          to={action.href}
          className={
            action.tone === "danger"
              ? "mt-[10px] block w-full rounded-md border border-danger/40 bg-danger/10 py-2 text-center text-sm font-medium text-danger hover:bg-danger/20"
              : "mt-[10px] block w-full rounded-md border border-border py-2 text-center text-sm font-medium hover:bg-muted"
          }
        >
          {action.label}
        </Link>
      )}
    </Panel>
  );
}
