// A maintenance command's panel — what a row of the Maintenance page raises.
//
// It lives with Maintenance because that is what makes it change: which
// commands exist, what each risks, and whether it can be run dry. The panel
// that draws it is a `ui/` primitive and knows none of that, so this file
// REGISTERS what produces the descriptor.
//
// A PRODUCER IS NOT A HOOK. It is called from the document-level click
// delegation (`data-maintact`) and from the addressed-panel table on a cold
// load at `?panel=action:<id>`, in a task that cannot await — so it reads the
// query cache synchronously (invariant 10) and never the engine's accessors.
//
// Descriptor is the legacy `openActionMaintenance`'s, transplanted rather than
// translated: same fields, same order, same `data-*` targets.
import i18next from "i18next";
import { registerProducer, type PanelCache, type PanelDescriptor } from "../../ui/panel/contract";
import { maintenanceActionsQuery } from "./queries";
import { riskLabel, riskPip } from "./risks";
import type { MaintenanceAction } from "./reference";

/**
 * Finds one maintenance command among those the layer answered.
 *
 * Args:
 *     identifier: The command's id, as the address and the row both spell it.
 *     cache: What the query cache holds.
 *
 * Returns:
 *     The command, or null when the layer has not answered or does not carry it.
 */
function actionOf(identifier: string, cache: PanelCache): MaintenanceAction | null {
  const actions = cache.held<MaintenanceAction[]>(maintenanceActionsQuery.queryKey);
  return actions?.find((action) => action.id === identifier) ?? null;
}

/**
 * Builds a maintenance command's descriptor.
 *
 * Args:
 *     identifier: The command's id.
 *     cache: What the query cache holds, read synchronously.
 *
 * Returns:
 *     The descriptor, or null for a command the layer does not carry — which is
 *     what the engine's own producer did by returning early on `!action`.
 */
function maintenancePanel(
  identifier: string,
  cache: PanelCache,
): PanelDescriptor | null {
  const action = actionOf(identifier, cache);
  if (action === null) return null;
  const translate = i18next.t.bind(i18next);
  const deletes = action.r === "destructive";
  // A DESTRUCTIVE COMMAND IS ALWAYS DRY at this point, whatever the page's
  // switch says: the note below is the whole reason, and the engine read it
  // the same way. The switch is ephemeral interface state and is read from the
  // store, which is where invariant 4 puts it.
  const dry = deletes ? true : Boolean(window.__store.read().state.maintBlanc);
  return {
    address: "action:" + identifier,
    title: action.l,
    subtitle: action.id,
    meta: action.d,
    puce: [riskPip(action.r), riskLabel(action.r)],
    blocs: [
      {
        type: "faits",
        lignes: [
          {
            c: translate("panels.maintenance.whatItDoes"),
            v: riskLabel(action.r),
            pipValue: riskPip(action.r),
          },
          {
            c: translate("panels.maintenance.duration"),
            v: translate(action.long
              ? "panels.maintenance.durationLong"
              : "panels.maintenance.durationImmediate"),
          },
          {
            c: translate("panels.maintenance.dryRun"),
            v: translate(action.blanc
              ? (dry ? "panels.maintenance.dryRunOn" : "panels.maintenance.dryRunOff")
              : "panels.maintenance.dryRunImpossible"),
          },
        ],
      },
      deletes
        ? { type: "note", text: translate("panels.maintenance.destructiveNote") }
        : null,
      {
        type: "actions",
        actions: [
          {
            text: translate(action.blanc
              ? "panels.maintenance.runDry"
              : "panels.maintenance.run"),
            ton: "solid",
            target: {
              toast: translate(action.blanc
                ? "panels.maintenance.launchedDry"
                : "panels.maintenance.launched", { action: action.l }),
            },
          },
          deletes
            ? {
                text: translate("panels.maintenance.runForReal"),
                desactive: true,
                infobulle: translate("panels.maintenance.runForRealHint"),
                mention: translate("panels.maintenance.runForRealMention"),
              }
            : null,
        ],
      },
    ],
  };
}

// Registered as this module evaluates, with what it needs to have landed and
// with the answer the addressed-panel table asks before opening a panel from an
// address anyone can type. `holds` is NOT `produce` answering: a producer
// answers for anything, which is right inside the application and wrong for a
// typed address — and answering it here is what lets the engine stop reading
// its own fixture to decide.
registerProducer("action", {
  produce: maintenancePanel,
  needs: [maintenanceActionsQuery],
  holds: (identifier, cache) => actionOf(identifier, cache) !== null,
});
