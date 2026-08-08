/**
 * PlusSheet — « Veille et obligations », the « ⋮ » sheet in maquette grammar.
 *
 * At rest it matches the maquette's moreSheet(): a title, its meta line, two
 * `.sact` summary rows (radar = watcher, seed = obligations) carrying REAL
 * derived data, a `.kv` block, and the « Réglages → Config » footnote. Each
 * `.sact` row EXPANDS its full functional panel (WatcherPanel /
 * ObligationsPanel) — the S3 features stay reachable one tap deep, never
 * silently removed.
 *
 * Of the maquette's `.kv` rows, « Recherche automatique » is served (the grab
 * cron's live schedule). « Prochain passage » and « Ratio global » stay
 * OMITTED rather than faked (§13/§14): the cron registry mirrors the schedule
 * in prose only — no next-fire is computable from it — and `ratio_state` holds
 * no row, so any figure there would be invented.
 */

import { ArrowLeft } from "lucide-react";
import { useState, type ReactElement } from "react";

import { Link } from "react-router-dom";

import { GRAB_JOB_NAME, obligationStatus } from "@/components/acquisition/meta";
import { ObligationsPanel } from "@/components/acquisition/ObligationsPanel";
import { WatcherPanel } from "@/components/acquisition/WatcherPanel";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { useAcquisitionStatus, useObligations } from "@/hooks/useAcquisition";
import { useSchedulers } from "@/hooks/useSchedulers";
import { relativeTime } from "@/lib/format";

/* Maquette icon set `I` — radar and seed, verbatim paths (16 px via .sact svg). */
const ICON_RADAR = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
    <circle cx="12" cy="12" r="3" />
    <path d="M12 3a9 9 0 0 1 9 9" />
    <path d="M12 7.5a4.5 4.5 0 0 1 4.5 4.5" />
  </svg>
);
const ICON_SEED = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
    <path d="M12 20v-8" />
    <path d="M12 12a6 6 0 0 1 6-6h2a8 8 0 0 1-8 8z" />
    <path d="M12 14A5 5 0 0 0 7 9H5a7 7 0 0 0 7 7z" />
  </svg>
);

/** Props for {@link PlusSheet}. */
export interface PlusSheetProps {
  /** Whether the sheet is visible. */
  readonly open: boolean;
  /** Callback to close (or open) the sheet. */
  readonly onOpenChange: (open: boolean) => void;
}

/**
 * PlusSheet — secondary acquisition surface (Watcher + Obligations).
 *
 * Args:
 *   props: {@link PlusSheetProps} — open state + close callback.
 *
 * Returns:
 *   The sheet element.
 */
export function PlusSheet({
  open,
  onOpenChange,
}: PlusSheetProps): ReactElement {
  const status = useAcquisitionStatus();
  const obligations = useObligations();
  // The grab cron's live schedule — the maquette's « Recherche automatique »
  // row. Absent scheduler ⇒ the row does not render (never a guessed time).
  const schedulers = useSchedulers();
  const rawGrabSchedule = schedulers.data?.schedulers.find(
    (j) => j.name === GRAB_JOB_NAME,
  )?.schedule;
  const grabSchedule =
    rawGrabSchedule != null && rawGrabSchedule !== "" ? rawGrabSchedule : null;
  const [watcherOpen, setWatcherOpen] = useState(false);
  const [obligOpen, setObligOpen] = useState(false);

  // Honest summaries: derived from what the API actually serves, wording
  // from the maquette; absence stays visible (« état inconnu »), never faked.
  const watcherLine = status.isError
    ? "Veille — état inconnu"
    : status.data == null
      ? "Veille — chargement…"
      : `${status.data.watcher_enabled ? "Veille active" : "Veille arrêtée"}${
          status.data.last_successful_run_at != null
            ? ` · dernier passage ${relativeTime(status.data.last_successful_run_at)}`
            : ""
        }`;

  const items = obligations.data?.items ?? [];
  const pending = items.filter((i) => obligationStatus(i) === "pending").length;
  const breached = items.filter((i) => obligationStatus(i) === "breached").length;
  const obligLine = obligations.isError
    ? "Obligations de partage — état inconnu"
    : obligations.data == null
      ? "Obligations de partage — chargement…"
      : `Obligations de partage · ${String(pending)} en cours, ${String(breached)} non respectée${breached > 1 ? "s" : ""}`;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      {/* `mq`: the portal lands on <body>, outside the page's scope — the
          maquette classes need the scope re-applied here. */}
      <SheetContent side="right" className="mq px-4 pb-5" showCloseButton={false}>
        {/* Operator directive: EVERY back wears the search screen's
            « ‹ Retour » — never a cross. */}
        <div className="fichebar -mx-2">
          <button
            type="button"
            aria-label="Retour"
            className="fback"
            onClick={() => {
              onOpenChange(false);
            }}
          >
            <ArrowLeft aria-hidden="true" />
            Retour
          </button>
        </div>
        <SheetHeader className="p-0">
          <SheetTitle className="sheettitle">Veille et obligations</SheetTitle>
          <SheetDescription className="sheetmeta">
            Ce qu&apos;on surveille en fond — pas du travail quotidien.
          </SheetDescription>
        </SheetHeader>

        {/* Maquette .sact rows — each expands its full panel (summary at
            rest, function one tap deep). */}
        <div className="sheetacts">
          <button
            type="button"
            className="sact"
            aria-expanded={watcherOpen}
            onClick={() => {
              setWatcherOpen((v) => !v);
            }}
          >
            {ICON_RADAR}
            <span>{watcherLine}</span>
          </button>
          {watcherOpen && <WatcherPanel />}
          <button
            type="button"
            className="sact"
            aria-expanded={obligOpen}
            onClick={() => {
              setObligOpen((v) => !v);
            }}
          >
            {ICON_SEED}
            <span>{obligLine}</span>
          </button>
          {obligOpen && <ObligationsPanel />}
        </div>

        {/* Maquette .kv block — only the rows the API can honestly fill.
            « Recherche automatique » reads the grab cron's LIVE schedule
            (never a hardcoded time). Still omitted, for want of data rather
            than of intent: « Prochain passage » (the registry mirrors the
            cron in prose only, so no next-fire can be computed) and « Ratio
            global » (ratio_state is empty — inventing a figure there is
            exactly what §14 forbids). */}
        {(grabSchedule != null || status.data?.last_successful_run_at != null) && (
          <div>
            {grabSchedule != null && (
              <div className="kv">
                <span>Recherche automatique</span>
                <span>{grabSchedule}</span>
              </div>
            )}
            {status.data?.last_successful_run_at != null && (
              <div className="kv">
                <span>Dernier run réussi</span>
                <span>{relativeTime(status.data.last_successful_run_at)}</span>
              </div>
            )}
          </div>
        )}

        {/* Maquette footnote — where the ranking profiles went. */}
        <p className="mt-4 text-xs text-muted-foreground">
          Les profils de classement (ex-onglet « Réglages ») ont déménagé dans{" "}
          <Link className="font-semibold text-primary" to="/config?tab=classement">
            Config
          </Link>
          .
        </p>
      </SheetContent>
    </Sheet>
  );
}
