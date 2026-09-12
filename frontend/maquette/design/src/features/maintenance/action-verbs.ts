// A maintenance command's own verb — « Lancer » and « Lancer à blanc » (B-383).
//
// IT SAID A SENTENCE AND SENT NOTHING. The command panel's action carried
// `target: { toast: … }`, which draws an attribute the dying engine answers by
// showing a sentence and doing nothing else: the operator was told a command had
// been launched over a machine in which nothing had been asked. « Said, not
// done » is NE-DOIT-PAS-1.
//
// THE OPERATION ALREADY EXISTED. `runMaintenanceAction` is declared, its handler
// is written and it moves the layer's own pipeline state; nothing had ever
// called it. That is the whole defect, and it is why this file adds a verb
// rather than a contract.
//
// A BLANK RUN CHANGES NOTHING, AND THAT IS THE POINT. The layer answers a dry
// run with the pipeline state it already had, because « à blanc » means exactly
// that — so what proves this verb is not a state that moved but a call that
// LEFT, beside a state that did not. Both are read by the rule; neither is the
// sentence.
//
// A FILE OF ITS OWN beside the producer, never a growth of `panel-action.ts`: a
// verb is behaviour and a producer is a function from the cache to a descriptor.
import i18next from "i18next";
import type { QueryClient } from "@tanstack/react-query";
import { HELD, send } from "../../lib/query-client";
import { registerVerb } from "../../lib/verbs";

/** What the operation answers, as the contract declares it. */
type MaintenanceRun = {
  state: string;
  uid: string | null;
};

/** What the pipeline reads as when an ask waits for the one already running. */
const QUEUED = "queued";

/* THE COMMANDS IN FLIGHT, by identifier. A second press while the first is out
   is the same intention made again — answered with silence, never with a
   refusal, which would say « occupé » to a legitimate act (NE-DOIT-PAS-3). */
const inFlight = new Set<string>();

/**
 * Runs one maintenance command, for real or blank.
 *
 * WHAT IT SAYS COMES FROM WHAT CAME BACK. A command that arrives while the
 * machine is working is QUEUED and the interface says so in DOIT-4's own words;
 * one that starts now says that; a blank run says what a blank run is, which is
 * that nothing was changed. Offline is none of the three: `send` answers `HELD`
 * when the mutation waits for a network that is not there.
 *
 * Args:
 *     client: The cache the maintenance surfaces read.
 *     identifier: The command, by the id its row and its address both spell.
 *     dry: Whether it is the blank run — decided by the panel, which is where
 *         the switch and the destructive rule are both read, and carried here
 *         rather than recomputed: two readings of one question drift.
 */
async function runAction(
  client: QueryClient,
  identifier: string,
  dry: boolean,
): Promise<void> {
  const say = (key: string, values?: Record<string, unknown>) =>
    i18next.t(`verbs.maintenance.${key}`, values ?? {});
  if (inFlight.has(identifier)) return;
  inFlight.add(identifier);
  try {
    const answered = await send<MaintenanceRun>(
      "POST",
      `/api/maintenance/actions/${encodeURIComponent(identifier)}/run`,
      { dryRun: dry },
    );
    if (answered === HELD) {
      window.__toast?.show({ message: say(dry ? "dryHeld" : "held") });
      return;
    }
    const outcome = answered as MaintenanceRun | undefined;
    const messageKey = dry
      ? "dryDone"
      : outcome?.state === QUEUED
        ? "queued"
        : "started";
    window.__toast?.show({ message: say(messageKey) });
    // THE PIPELINE IS RE-READ, because that is where a real run becomes
    // visible: Arrivées draws the pipeline's own state, and an answer nobody
    // invalidates leaves it showing the machine as it was before the command.
    // A BLANK RUN RE-READS IT TOO — it moved nothing, and proving that on the
    // surface is worth exactly as much as proving the other.
    await client.refetchQueries({ queryKey: ["/api/pipeline/status"] });
    window.__panel?.redraw();
  } catch {
    window.__toast?.show({ message: say("refused") });
  } finally {
    inFlight.delete(identifier);
  }
}

/**
 * Declares the maintenance command's verb to the tap registry.
 *
 * Args:
 *     client: The cache the maintenance surfaces read.
 */
export function installMaintenanceVerbs(client: QueryClient): void {
  // THE DRY-NESS TRAVELS ON THE ELEMENT, beside the identifier. The panel
  // decides it — a destructive command is always blank whatever the page's
  // switch says — and a verb that recomputed it from the store would be a
  // second reading of one question, free to disagree with the button the
  // operator actually read.
  registerVerb("maintenance-run", (identifier, element) => {
    void runAction(client, identifier, element.dataset.dryRun === "true");
  });
}
