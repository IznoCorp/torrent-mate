/**
 * DecisionRow — the card of a scrape decision, and a decision is a FOLDER.
 *
 * The scrape could not name what is inside it — that is the whole reason the
 * question exists — so what the operator is shown is the thing on disk, set in
 * the mono face and never cleaned up. Recognising it is the point.
 *
 * It is the interface's THIRD card shape, next to {@link MediaRow} (a list row
 * for a medium) and {@link MediaTile} (a gallery tile). It is not a variant of
 * either: it promises no bottom panel, because a decision has no actions of a
 * medium you own, and its poster is never a link, because there is no medium
 * here yet — the same reason a release candidate's is not. Derived from the
 * prototype's `decisionCardHTML`; rule R57, `frontend/maquette/harness/decision.py`.
 *
 * **It takes FACTS, never markup.** A settled decision shows the poster of the
 * medium it was tied to; a pending one shows the placeholder, because nothing
 * has been chosen and a guess drawn as a fact is what this interface exists to
 * avoid.
 */

import { type ReactElement } from "react";

import { Chip } from "@/components/ds/Chip";
import { MediaPoster } from "@/components/ds/MediaPoster";
import { Panel } from "@/components/ds/Panel";
import { posterThumb } from "@/lib/poster-thumb";

/** What a decision was tied to, once it was settled. */
export interface DecisionOutcome {
  /** The chosen medium's title, as the provider spells it. */
  readonly title: string;
  /** `tmdb` / `tvdb`, shown upper-cased. */
  readonly provider: string;
  /** The provider's id for that medium. */
  readonly providerId: number;
  /** How it was found, already said in French. */
  readonly how: string;
  /** The chosen medium's poster, when one is known. */
  readonly posterUrl?: string | null;
}

/** One chip: a tone and the words to show. */
export interface DecisionChip {
  readonly tone: string;
  readonly label: string;
  /** The sentence explaining what it means, on hover. */
  readonly hint?: string | undefined;
}

/** Props for {@link DecisionRow}. */
export interface DecisionRowProps {
  /** The folder, exactly as it is on disk. */
  readonly folder: string;
  /** The full path, for the tooltip — a folder name truncates, a path is long. */
  readonly path?: string;
  /** What the pipeline took it for. It reaches the placeholder as the letter
   *  it falls back on, so a folder with no chosen medium still says whether a
   *  film or a series was expected. */
  readonly kind: "movie" | "tvshow";
  /** Why it entered the queue. */
  readonly reason: DecisionChip;
  /** How it ended, when it did. A pending decision has none. */
  readonly outcome?: DecisionChip;
  /** When, already written out. */
  readonly when: string;
  /** How many candidates are waiting to be told apart. Said in words next to
   *  the date, because a bare number beside a status badge answers « 3 what ? ».
   *  Only meaningful while the decision is pending; a settled one's count is
   *  history. */
  readonly candidates?: number;
  /** The medium it was tied to, once settled. */
  readonly chosen?: DecisionOutcome;
  /** Opens the arbitration. Omit for a settled decision — §11 forbids a
   *  control that does nothing, and a greyed one is the same broken promise. */
  readonly onOpen?: () => void;
}

/** The card's inner content — folder, date, outcome, chips. */
function DecisionRowBody({
  folder,
  path,
  when,
  chosen,
  reason,
  outcome,
  candidates,
}: Pick<
  DecisionRowProps,
  "folder" | "path" | "when" | "chosen" | "reason" | "outcome" | "candidates"
>): ReactElement {
  return (
    <span className="block min-w-0 flex-1">
      <span
        data-testid="decision-folder"
        className="block truncate font-mono text-sm font-semibold"
        title={path ?? folder}
      >
        {folder}
      </span>
      <span className="mt-0.5 block truncate text-xs text-muted-foreground">
        {candidates != null
          ? `${when} · ${candidates === 0 ? "aucun candidat" : `${String(candidates)} candidat${candidates > 1 ? "s" : ""}`}`
          : when}
      </span>
      {chosen != null && (
        // What was chosen is the line one comes back to read, so it wraps
        // rather than truncating: on one line it lost its provider id and how
        // it was found, which is exactly what one comes back for.
        <span className="mt-0.5 line-clamp-2 block text-xs text-muted-foreground">
          {`${chosen.title} · ${chosen.provider.toUpperCase()} ${String(chosen.providerId)} · ${chosen.how}`}
        </span>
      )}
      <span className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1">
        <Chip tone={reason.tone} title={reason.hint}>
          {reason.label}
        </Chip>
        {outcome != null && (
          <Chip tone={outcome.tone} title={outcome.hint}>
            {outcome.label}
          </Chip>
        )}
      </span>
    </span>
  );
}

/**
 * Render one decision row.
 *
 * Args:
 *   props: See {@link DecisionRowProps}.
 *
 * Returns:
 *   The card element.
 */
export function DecisionRow({
  folder,
  path,
  kind,
  reason,
  outcome,
  when,
  candidates,
  chosen,
  onOpen,
}: DecisionRowProps): ReactElement {
  const body = (
    <DecisionRowBody
      folder={folder}
      {...(path != null ? { path } : {})}
      when={when}
      {...(candidates != null ? { candidates } : {})}
      {...(chosen != null ? { chosen } : {})}
      reason={reason}
      {...(outcome != null ? { outcome } : {})}
    />
  );

  return (
    <Panel data-testid="decision-card" data-nonmedia="decision" className="flex w-full flex-col p-[9px]">
      <div className="flex min-w-0 items-center gap-[10px]">
        {/* Never a button: a pending decision has no medium yet, and a settled
            one is still ABOUT the folder. */}
        <span className="shrink-0 leading-none">
          <MediaPoster
            title={chosen?.title ?? (kind === "movie" ? "Film" : "Série")}
            src={chosen != null ? posterThumb(chosen.posterUrl ?? null) : null}
            className="w-[38px]"
          />
        </span>
        {onOpen ? (
          <button
            type="button"
            className="flex min-w-0 flex-1 items-center gap-[10px] text-left"
            aria-label={folder}
            onClick={onOpen}
          >
            {body}
          </button>
        ) : (
          <div className="flex min-w-0 flex-1 items-center gap-[10px]">{body}</div>
        )}
      </div>
    </Panel>
  );
}
