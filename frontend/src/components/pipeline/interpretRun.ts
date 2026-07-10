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

/** One interpreted line of the run narrative. */
export interface InterpretedLine {
  /** The pipeline step this line belongs to (``"ingest"``, ``"scrape"``, …). */
  readonly step: string;
  /** The plain-French sentence. */
  readonly text: string;
  /** Semantic tone for display. */
  readonly tone: LineTone;
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
    const where = dest !== "" ? ` vers ${dest}` : "";
    return { step, text: `Nouveau téléchargement collecté : ${item}${where}`, tone: "success" };
  }
  if (status === "skipped") {
    return { step, text: `Ignoré (${detail(data, "reason")}) : ${item}`, tone: "info" };
  }
  if (status === "failed") {
    return { step, text: `Échec de la copie : ${item} (${detail(data, "error")})`, tone: "danger" };
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
    const where = dest !== "" ? ` → ${dest}` : "";
    return { step, text: `Déplacé en préparation : ${item}${where}`, tone: "success" };
  }
  if (status === "skipped") {
    return { step, text: `Non trié (${detail(data, "reason")}) : ${item}`, tone: "info" };
  }
  if (status === "error") {
    return { step, text: `Erreur de tri : ${item} (${detail(data, "error")})`, tone: "danger" };
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
    return { step, text: `Nettoyé : ${item}`, tone: "success" };
  }
  if (status === "skipped") {
    return { step, text: `Rien à nettoyer : ${item}`, tone: "info" };
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
    const src = provider !== "" ? ` (${provider})` : "";
    return { step, text: `Métadonnées trouvées : ${item}${src}`, tone: "success" };
  }
  if (status === "queued_for_decision") {
    return {
      step,
      text: `Ambigu — en attente d'une décision : ${item}`,
      tone: "warning",
    };
  }
  if (status === "skipped_low_confidence") {
    return {
      step,
      text: `Correspondance trop incertaine, laissé de côté : ${item}`,
      tone: "warning",
    };
  }
  if (status === "skipped") {
    return { step, text: `Non scrapé : ${item}`, tone: "info" };
  }
  if (status === "failed") {
    return { step, text: `Échec du scraping : ${item} (${detail(data, "error")})`, tone: "danger" };
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
    const count = n !== undefined ? ` (${String(n)})` : "";
    return { step, text: `Dossiers vides supprimés dans ${item}${count}`, tone: "success" };
  }
  if (status === "skipped") {
    return { step, text: `Aucun dossier vide : ${item}`, tone: "info" };
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
    return { step, text: `Nom corrigé : ${item}`, tone: "success" };
  }
  if (status === "skipped") {
    return { step, text: `Déjà conforme : ${item}`, tone: "info" };
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
  const name = item === "<step>" || item === "" ? "" : ` : ${item}`;
  if (status === "downloaded") {
    return { step, text: `Bande-annonce téléchargée${name}`, tone: "success" };
  }
  if (status === "already_present") {
    return { step, text: `Bande-annonce déjà présente${name}`, tone: "info" };
  }
  if (status === "no_trailer" || status === "unavailable") {
    return { step, text: `Aucune bande-annonce disponible${name}`, tone: "info" };
  }
  if (status === "bot_detected") {
    return { step, text: `Bande-annonce indisponible (blocage anti-robot)${name}`, tone: "warning" };
  }
  if (status === "skipped") {
    return { step, text: `Bande-annonce ignorée (${detail(data, "reason")})`, tone: "info" };
  }
  if (status === "failed" || status === "error") {
    return { step, text: `Échec bande-annonce${name} (${detail(data, "reason")})`, tone: "danger" };
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
  const where = disk !== "" ? ` sur ${disk}` : dest !== "" ? ` → ${dest}` : "";
  if (status === "moved") {
    return { step, text: `Rangé${where} : ${item}`, tone: "success" };
  }
  if (status === "replaced") {
    return { step, text: `Remplacé${where} : ${item}`, tone: "success" };
  }
  if (status === "merged") {
    return { step, text: `Fusionné${where} : ${item}`, tone: "success" };
  }
  if (status === "skipped") {
    return { step, text: `Non rangé (${detail(data, "reason")}) : ${item}`, tone: "info" };
  }
  if (status === "error") {
    return { step, text: `Erreur de rangement : ${item} (${detail(data, "reason")})`, tone: "danger" };
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
