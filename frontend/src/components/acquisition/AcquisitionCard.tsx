/**
 * AcquisitionCard — the single card grammar of the Acquisition page.
 *
 * Every list (Maintenant's five sections, Suivis' liste and groupé modes) renders
 * through this component, so the spec's transverse rules are enforced once rather
 * than re-derived per surface:
 *
 * - **R1** — the « ··· » lives INSIDE the card, in flow. It used to be
 *   `position: absolute` on the swipe wrapper while the *card* is what translates,
 *   so it stayed put and landed on top of « Retirer ».
 * - **R2** — `strip` and `footer` are full-width own lines, never siblings of the
 *   title row in a `row` flex, which squeezed the journey strip into a narrow
 *   column and overlapped its labels.
 * - **R3** — the title line accepts nothing but the title (§12). Everything that
 *   qualifies the media goes on the meta line, the only one that wraps.
 * - **§11** — the poster is a button only when `onPoster` is given, and the
 *   body is a button only when `onOpen` is given. For an item with no detail
 *   sheet or no media sheet, the corresponding element is not a disabled
 *   button, it is not a button at all: §11 forbids a dead link, and a greyed
 *   control is the same broken promise.
 */

import { type ReactElement, type ReactNode } from "react";

import { MediaPoster } from "@/components/ds/MediaPoster";

/** Props for {@link AcquisitionCard}. */
export interface AcquisitionCardProps {
  /** The media title — alone on its line (R3). */
  readonly title: string;
  /** Poster URL, or `null` for the initial-letter placeholder. */
  readonly posterUrl: string | null;
  /** One-line qualifier; truncates. */
  readonly subtitle?: string;
  /** Why this item needs a decision; wraps to two lines and never truncates (§12). */
  readonly reason?: string;
  /** The meta line — fraction, status chip, tags. */
  readonly meta?: ReactNode;
  /** Tap on the body → the detail sheet. Omit when the card has no detail sheet
   *  — exactly the same rationale as {@link onPoster}: a button that does nothing
   *  is a dead control (§11). */
  readonly onOpen?: () => void;
  /** Tap on the poster → the media sheet. Omit when the media has no sheet (§11). */
  readonly onPoster?: () => void;
  /** Desktop-only actions menu, rendered inside the card (R1). */
  readonly menu?: ReactNode;
  /** Full-width own line under the top row (R2) — the journey strip. */
  readonly strip?: ReactNode;
  /** Full-width action row under the strip. */
  readonly footer?: ReactNode;
}

/** Props for the inner body — extracted so button/div share one copy. */
interface CardBodyProps {
  readonly title: string;
  // `| undefined` is required, not decorative: exactOptionalPropertyTypes is on,
  // so an optional prop and a prop explicitly passed as undefined are different
  // types, and the card spreads its own optionals straight through to here.
  readonly subtitle?: string | undefined;
  readonly reason?: string | undefined;
  readonly meta?: ReactNode | undefined;
}

/** The card's inner content — title line, subtitle, reason, meta. */
function AcquisitionCardBody({
  title,
  subtitle,
  reason,
  meta,
}: CardBodyProps): ReactElement {
  return (
    <span className="block min-w-0 flex-1">
      <span data-testid="acq-card-title" className="block truncate text-sm font-medium">
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
      {meta != null && (
        <span className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1">{meta}</span>
      )}
    </span>
  );
}

/**
 * Render one acquisition card.
 *
 * Args:
 *   props: See {@link AcquisitionCardProps}.
 *
 * Returns:
 *   The card element.
 */
export function AcquisitionCard({
  title,
  posterUrl,
  subtitle,
  reason,
  meta,
  onOpen,
  onPoster,
  menu,
  strip,
  footer,
}: AcquisitionCardProps): ReactElement {
  const poster = <MediaPoster title={title} src={posterUrl} className="w-[38px]" />;

  return (
    <div
      data-testid="acq-card"
      className="flex w-full flex-col rounded-lg border border-border bg-card p-[9px]"
    >
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
            title="Média non identifié — pas de fiche disponible."
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
            <AcquisitionCardBody
              title={title}
              subtitle={subtitle}
              reason={reason}
              meta={meta}
            />
          </button>
        ) : (
          <div className="flex min-w-0 flex-1 items-center gap-[10px]">
            <AcquisitionCardBody
              title={title}
              subtitle={subtitle}
              reason={reason}
              meta={meta}
            />
          </div>
        )}

        {menu}
      </div>

      {strip}
      {footer}
    </div>
  );
}
