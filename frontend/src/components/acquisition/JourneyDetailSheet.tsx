/**
 * JourneyDetailSheet — one acquisition's journey, per item (§3).
 *
 * §3 dissolved the « Parcours » tab into « the journey strip on the card plus
 * a per-item detail » — this is that detail, and what makes the old panel's
 * honesty rules survive its deletion:
 *
 * - §14.2 — a DISPATCHED media went through ingest, sort and scrape: that is
 *   the workflow, not a guess. On a FINISHED journey an undated stage still
 *   HAPPENED; only its instant is missing. The stage shows as done without a
 *   date — never « inconnue », which reads as loss, and never an invented
 *   date, which is the lie §13 forbids. Less information, never false
 *   information.
 * - An ESTIMATED instant says so: « ≈ » on the date and a tooltip naming the
 *   computation. An announced estimate is information; the same estimate,
 *   silent, would be a false measurement (§13).
 * - A completed stage with a known run deep-links to that run (F3).
 * - The release ACTUALLY grabbed is named, with its absence admitted — never
 *   a media title standing in for it.
 */

import { type ReactElement } from "react";
import { Link } from "react-router-dom";

import type { JourneyItem } from "@/api/acquisition";
import { Badge } from "@/components/ui/badge";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

import { relativeTime } from "./meta";

/** The four stored stages, in workflow order. */
const STAGES = [
  { key: "grabbed_at", label: "Récupéré", runKey: "grab_run_uid", estimateKey: "grabbed" },
  { key: "ingested_at", label: "Ingéré", runKey: "ingest_run_uid", estimateKey: "ingested" },
  { key: "scraped_at", label: "Scrapé", runKey: "scrape_run_uid", estimateKey: "scraped" },
  { key: "dispatched_at", label: "Rangé", runKey: "dispatch_run_uid", estimateKey: "dispatched" },
] as const;

/** Props for {@link JourneyDetailSheet}. */
export interface JourneyDetailSheetProps {
  readonly journey: JourneyItem;
  readonly title: string;
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
}

/**
 * Render the journey detail bottom sheet.
 *
 * Args:
 *   props: See {@link JourneyDetailSheetProps}.
 *
 * Returns:
 *   The sheet element.
 */
export function JourneyDetailSheet({
  journey,
  title,
  open,
  onOpenChange,
}: JourneyDetailSheetProps): ReactElement {
  const terminal = journey.dispatched_at != null;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="bottom"
        className="mq flex max-h-[86%] flex-col gap-3 overflow-y-auto rounded-t-2xl border-t border-border"
        showCloseButton={false}
      >
        <div className="sheetgrab" aria-hidden="true" />
        <SheetHeader>
          <SheetTitle className="text-lg font-semibold">{title}</SheetTitle>
          {/* The release ACTUALLY grabbed — admitted absent, never substituted. */}
          <p
            data-testid="journey-release"
            className="min-w-0 truncate font-mono text-xs text-muted-foreground"
            title={journey.release_name ?? undefined}
          >
            {journey.release_name ?? "Nom de release non enregistré"}
          </p>
        </SheetHeader>

        <ol data-testid="journey-stages" className="flex flex-col gap-2 px-4 pb-4">
          {STAGES.map((stage) => {
            const at = journey[stage.key];
            const done = at != null;
            const runUid = journey[stage.runKey];
            // §14.2 — on a terminal journey, an undated stage HAPPENED.
            const reached = done || terminal;
            const estimated = (journey.estimated_stages ?? "")
              .split(",")
              .includes(stage.estimateKey);

            const chip = (
              <Badge tone={reached ? "success" : "muted"}>
                {stage.label}
                {done ? ` · ${estimated ? "≈ " : ""}${relativeTime(at)}` : ""}
              </Badge>
            );
            const body = estimated ? (
              <span title="Instant estimé : cette étape a bien eu lieu, mais son horodatage n'a été retrouvé dans aucune source. La valeur est répartie entre la récupération et le rangement.">
                {chip}
              </span>
            ) : (
              chip
            );

            return (
              <li key={stage.key} className="flex items-center gap-2">
                {done && runUid != null ? (
                  <Link
                    to={`/pipeline?run=${encodeURIComponent(runUid)}`}
                    title="Voir le run qui a effectué cette étape"
                  >
                    {body}
                  </Link>
                ) : (
                  body
                )}
                {!done && reached && (
                  <span className="text-xs text-muted-foreground">
                    faite — instant non retrouvé
                  </span>
                )}
              </li>
            );
          })}
        </ol>
      </SheetContent>
    </Sheet>
  );
}
