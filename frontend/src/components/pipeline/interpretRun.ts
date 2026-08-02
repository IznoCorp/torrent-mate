/**
 * interpretRun — fold a run's ordered WS events into plain-French lines.
 *
 * The pipeline emits per-step lifecycle events (``StepStarted`` /
 * ``StepCompleted`` / ``StepErrored``) and per-item progress events
 * (``ItemProgressed``) on the bus; the web relay forwards each as an
 * {@link import("@/api/events").EventMessage} whose ``type`` is the event class
 * name and whose ``data`` is the serialized envelope payload (opaque
 * ``Record<string, unknown>``). This module turns that raw stream into a
 * human-readable, ordered list of interpreted lines shown by default on the
 * Pipeline page (webui-ux Phase 2.3), so the operator reads *what happened*
 * (folder scanned, items collected, moved to staging, cleaned, scraped /
 * awaiting a decision, trailers, dispatch destination) instead of raw JSON.
 *
 * The function is **pure** — same event list in, same lines out — and tolerant:
 * unknown event types / statuses are ignored (no line) rather than throwing, so
 * a new backend status never breaks the view. Event ``type`` is matched on the
 * canonical class name (``StepStarted``…) with an optional ``Pipeline`` prefix
 * stripped defensively.
 */

import type { EventMessage } from "@/api/events";

/** Semantic tone for an interpreted line (drives the row colour). */
export type LineTone = "info" | "success" | "warning" | "danger";

/**
 * One typed fragment of an interpreted line.
 *
 * Machine tokens (item / disk / provider / dest names) carry ``mono: true``
 * so the render site can set them in ``font-mono`` inside the French prose
 * (X5/PIPELINE-8) instead of flattening everything into one string.
 */
export interface LineSegment {
  /** The fragment text. */
  readonly text: string;
  /** ``true`` when the fragment is a machine token to render in mono. */
  readonly mono?: boolean;
}

/** One interpreted line of the run narrative. */
export interface InterpretedLine {
  /** The pipeline step this line belongs to (``"ingest"``, ``"scrape"``, …). */
  readonly step: string;
  /** The plain-French sentence (the joined segments). */
  readonly text: string;
  /** Semantic tone for display. */
  readonly tone: LineTone;
  /**
   * The typed fragments the sentence is built from. Absent on lines that
   * carry no machine token (step headers, persisted-summary lines from
   * ``summariseSteps``) — the render site then falls back to ``text``.
   */
  readonly segments?: readonly LineSegment[];
}

/** One part fed to {@link mkLine}: French prose, or a mono machine token. */
type SegmentPart = string | { readonly mono: string };

/**
 * Build an {@link InterpretedLine} from typed parts.
 *
 * Empty parts are dropped; ``text`` is the in-order join of every fragment,
 * so the flat sentence stays byte-identical to the pre-segment output.
 *
 * Args:
 *   step: The pipeline step the line belongs to.
 *   tone: The semantic tone.
 *   parts: Prose strings and ``{mono: token}`` machine fragments, in order.
 *
 * Returns:
 *   The interpreted line with both ``text`` and ``segments``.
 */
function mkLine(
  step: string,
  tone: LineTone,
  parts: readonly SegmentPart[],
): InterpretedLine {
  const segments: LineSegment[] = [];
  for (const part of parts) {
    if (typeof part === "string") {
      if (part !== "") segments.push({ text: part });
    } else if (part.mono !== "") {
      segments.push({ text: part.mono, mono: true });
    }
  }
  return {
    step,
    tone,
    text: segments.map((s) => s.text).join(""),
    segments,
  };
}

/** Human step names (French) for the step-lifecycle headers. */
const STEP_LABEL: Record<string, string> = {
  ingest: "Récupération des téléchargements",
  sort: "Tri vers la zone de préparation",
  clean: "Nettoyage des fichiers parasites",
  scrape: "Recherche des métadonnées",
  cleanup: "Suppression des dossiers vides",
  enforce: "Mise en conformité des noms",
  verify: "Vérification finale",
  trailers: "Bandes-annonces",
  dispatch: "Rangement vers le stockage",
};

/** Read a string field from an opaque payload, or ``""`` when absent/non-string. */
function str(data: Record<string, unknown>, key: string): string {
  const value = data[key];
  return typeof value === "string" ? value : "";
}

/** Read a nested string from ``data.details[key]``, or ``""``. */
function detail(data: Record<string, unknown>, key: string): string {
  const details = data.details;
  if (typeof details === "object" && details !== null) {
    const value = (details as Record<string, unknown>)[key];
    if (typeof value === "string") return value;
    if (typeof value === "number") return String(value);
  }
  return "";
}

/** Read a nested number from ``data.details[key]``, or ``undefined``. */
function detailNum(
  data: Record<string, unknown>,
  key: string,
): number | undefined {
  const details = data.details;
  if (typeof details === "object" && details !== null) {
    const value = (details as Record<string, unknown>)[key];
    if (typeof value === "number") return value;
  }
  return undefined;
}

/** The trailing path segment (basename), used to keep item/dest names short. */
function basename(path: string): string {
  if (path === "") return "";
  const parts = path.split("/").filter((p) => p.length > 0);
  return parts.at(-1) ?? path;
}

/** Normalise a wire ``type`` to its canonical event class name. */
function canonicalType(type: string): string {
  return type.startsWith("Pipeline") ? type.slice("Pipeline".length) : type;
}

/**
 * Interpret a ``StepStarted`` event.
 *
 * Args:
 *   data: The event payload.
 *
 * Returns:
 *   A step-header line, or ``null`` for an unknown step.
 */
function fromStepStarted(data: Record<string, unknown>): InterpretedLine | null {
  const step = str(data, "step");
  const label = STEP_LABEL[step];
  if (label === undefined) return null;
  return { step, text: `${label}…`, tone: "info" };
}

/**
 * Interpret a ``StepErrored`` event.
 *
 * Args:
 *   data: The event payload.
 *
 * Returns:
 *   A danger line naming the failed step, or ``null`` for an unknown step.
 */
function fromStepErrored(data: Record<string, unknown>): InterpretedLine | null {
  const step = str(data, "step");
  const label = STEP_LABEL[step];
  if (label === undefined) return null;
  const message = str(data, "error_message");
  const suffix = message !== "" ? ` : ${message}` : "";
  return {
    step,
    text: `${label} — échec de l'étape${suffix}`,
    tone: "danger",
  };
}

/**
 * Interpret one ``ItemProgressed`` event into a per-item line.
 *
 * The ``started`` status is intentionally dropped — it is noise (every item
 * emits one before its terminal status). Only meaningful terminal transitions
 * produce a line. An unknown ``step``/``status`` combination yields ``null``.
 *
 * Args:
 *   data: The event payload (carries ``step``, ``item``, ``status``, ``details``).
 *
 * Returns:
 *   The interpreted line, or ``null`` when the transition is not narrated.
 */
function fromItemProgressed(
  data: Record<string, unknown>,
): InterpretedLine | null {
  const step = str(data, "step");
  const status = str(data, "status");
  const item = basename(str(data, "item"));
  if (status === "started") return null;

  switch (step) {
    case "ingest":
      return ingestLine(step, status, item, data);
    case "sort":
      return sortLine(step, status, item, data);
    case "clean":
      return cleanLine(step, status, item);
    case "scrape":
      return scrapeLine(step, status, item, data);
    case "cleanup":
      return cleanupLine(step, status, item, data);
    case "enforce":
      return enforceLine(step, status, item);
    case "trailers":
      return trailersLine(step, status, item, data);
    case "dispatch":
      return dispatchLine(step, status, item, data);
    default:
      return null;
  }
}

/** ingest per-item line. */
function ingestLine(
  step: string,
  status: string,
  item: string,
  data: Record<string, unknown>,
): InterpretedLine | null {
  if (status === "copied") {
    const dest = basename(detail(data, "dest"));
    return mkLine(step, "success", [
      "Nouveau téléchargement collecté : ",
      { mono: item },
      ...(dest !== "" ? [" vers ", { mono: dest }] : []),
    ]);
  }
  if (status === "skipped") {
    return mkLine(step, "info", [
      `Ignoré (${detail(data, "reason")}) : `,
      { mono: item },
    ]);
  }
  if (status === "failed") {
    return mkLine(step, "danger", [
      "Échec de la copie : ",
      { mono: item },
      ` (${detail(data, "error")})`,
    ]);
  }
  return null;
}

/** sort per-item line. */
function sortLine(
  step: string,
  status: string,
  item: string,
  data: Record<string, unknown>,
): InterpretedLine | null {
  if (status === "moved") {
    const dest = basename(detail(data, "destination"));
    return mkLine(step, "success", [
      "Déplacé en préparation : ",
      { mono: item },
      ...(dest !== "" ? [" → ", { mono: dest }] : []),
    ]);
  }
  if (status === "skipped") {
    return mkLine(step, "info", [
      `Non trié (${detail(data, "reason")}) : `,
      { mono: item },
    ]);
  }
  if (status === "error") {
    return mkLine(step, "danger", [
      "Erreur de tri : ",
      { mono: item },
      ` (${detail(data, "error")})`,
    ]);
  }
  return null;
}

/** clean (junk-file removal) per-category line. */
function cleanLine(
  step: string,
  status: string,
  item: string,
): InterpretedLine | null {
  // "cleaned" is the real backend status; "recleaned" is tolerated dead input
  // (it is a structlog detail key the backend never emits as an item status).
  if (status === "cleaned" || status === "recleaned") {
    return mkLine(step, "success", ["Nettoyé : ", { mono: item }]);
  }
  if (status === "skipped") {
    return mkLine(step, "info", ["Rien à nettoyer : ", { mono: item }]);
  }
  return null;
}

/** scrape per-item line — the ambiguous/decision case is highlighted. */
function scrapeLine(
  step: string,
  status: string,
  item: string,
  data: Record<string, unknown>,
): InterpretedLine | null {
  if (status === "matched") {
    const provider = detail(data, "provider");
    const src: SegmentPart[] =
      provider !== "" ? [" (", { mono: provider }, ")"] : [];
    // §2 lists "posters récupérés" as a distinct visible state. The backend
    // emits status='matched' for BOTH a fresh scrape and an artwork-only
    // recovery (an item that already had its NFO but was missing artwork),
    // distinguished by details.action — surface them as different lines instead
    // of folding both into "Métadonnées trouvées".
    if (detail(data, "action") === "artwork_recovered") {
      return mkLine(step, "success", [
        "Posters récupérés : ",
        { mono: item },
        ...src,
      ]);
    }
    return mkLine(step, "success", [
      "Métadonnées trouvées : ",
      { mono: item },
      ...src,
    ]);
  }
  if (status === "queued_for_decision") {
    return mkLine(step, "warning", [
      "Ambigu — en attente d'une décision : ",
      { mono: item },
    ]);
  }
  if (status === "skipped_low_confidence") {
    return mkLine(step, "warning", [
      "Correspondance trop incertaine, laissé de côté : ",
      { mono: item },
    ]);
  }
  if (status === "skipped") {
    return mkLine(step, "info", ["Non scrapé : ", { mono: item }]);
  }
  if (status === "failed") {
    return mkLine(step, "danger", [
      "Échec du scraping : ",
      { mono: item },
      ` (${detail(data, "error")})`,
    ]);
  }
  return null;
}

/** cleanup (empty-dir removal) per-category line. */
function cleanupLine(
  step: string,
  status: string,
  item: string,
  data: Record<string, unknown>,
): InterpretedLine | null {
  if (status === "removed") {
    const n = detailNum(data, "removed");
    return mkLine(step, "success", [
      "Dossiers vides supprimés dans ",
      { mono: item },
      n !== undefined ? ` (${String(n)})` : "",
    ]);
  }
  if (status === "skipped") {
    return mkLine(step, "info", ["Aucun dossier vide : ", { mono: item }]);
  }
  return null;
}

/** enforce (name conformity) per-item line. */
function enforceLine(
  step: string,
  status: string,
  item: string,
): InterpretedLine | null {
  if (status === "fixed") {
    return mkLine(step, "success", ["Nom corrigé : ", { mono: item }]);
  }
  if (status === "skipped") {
    return mkLine(step, "info", ["Déjà conforme : ", { mono: item }]);
  }
  return null;
}

/** trailers per-item line. */
function trailersLine(
  step: string,
  status: string,
  item: string,
  data: Record<string, unknown>,
): InterpretedLine | null {
  // Step-level envelopes use item "<step>"; keep them terse.
  const name: SegmentPart[] =
    item === "<step>" || item === "" ? [] : [" : ", { mono: item }];
  if (status === "downloaded") {
    return mkLine(step, "success", ["Bande-annonce téléchargée", ...name]);
  }
  if (status === "already_present") {
    return mkLine(step, "info", ["Bande-annonce déjà présente", ...name]);
  }
  if (status === "no_trailer" || status === "unavailable") {
    return mkLine(step, "info", ["Aucune bande-annonce disponible", ...name]);
  }
  if (status === "bot_detected") {
    return mkLine(step, "warning", [
      "Bande-annonce indisponible (blocage anti-robot)",
      ...name,
    ]);
  }
  if (status === "skipped") {
    return mkLine(step, "info", [
      `Bande-annonce ignorée (${detail(data, "reason")})`,
    ]);
  }
  if (status === "failed" || status === "error") {
    return mkLine(step, "danger", [
      "Échec bande-annonce",
      ...name,
      ` (${detail(data, "reason")})`,
    ]);
  }
  return null;
}

/** dispatch per-item line — the destination disk/folder is the key info. */
function dispatchLine(
  step: string,
  status: string,
  item: string,
  data: Record<string, unknown>,
): InterpretedLine | null {
  const disk = detail(data, "disk");
  const dest = basename(detail(data, "dest"));
  const where: SegmentPart[] =
    disk !== ""
      ? [" sur ", { mono: disk }]
      : dest !== ""
        ? [" → ", { mono: dest }]
        : [];
  if (status === "moved") {
    return mkLine(step, "success", ["Rangé", ...where, " : ", { mono: item }]);
  }
  if (status === "replaced") {
    return mkLine(step, "success", [
      "Remplacé",
      ...where,
      " : ",
      { mono: item },
    ]);
  }
  if (status === "merged") {
    return mkLine(step, "success", [
      "Fusionné",
      ...where,
      " : ",
      { mono: item },
    ]);
  }
  if (status === "skipped") {
    return mkLine(step, "info", [
      `Non rangé (${detail(data, "reason")}) : `,
      { mono: item },
    ]);
  }
  if (status === "error") {
    return mkLine(step, "danger", [
      "Erreur de rangement : ",
      { mono: item },
      ` (${detail(data, "reason")})`,
    ]);
  }
  return null;
}

/**
 * Fold an ordered event list into interpreted French lines.
 *
 * Events are processed in the order given (the WS stream is already ordered by
 * the Redis-stream cursor). Non-narrated events (unknown types, ``started``
 * item transitions, unknown step/status) contribute no line, so the output is a
 * clean narrative rather than a raw dump.
 *
 * Args:
 *   events: The run's ordered WS events (already filtered to the run).
 *
 * Returns:
 *   The ordered interpreted lines. Empty when nothing is narratable yet.
 */
export function interpretRun(
  events: readonly EventMessage[],
): InterpretedLine[] {
  const lines: InterpretedLine[] = [];
  for (const event of events) {
    const type = canonicalType(event.type);
    let line: InterpretedLine | null = null;
    if (type === "StepStarted") {
      line = fromStepStarted(event.data);
    } else if (type === "StepErrored") {
      line = fromStepErrored(event.data);
    } else if (type === "ItemProgressed") {
      line = fromItemProgressed(event.data);
    }
    // StepCompleted carries only aggregate counts already implied by the
    // per-item lines; it adds no narrative line here.
    if (line !== null) {
      lines.push(line);
    }
  }
  return lines;
}
