// « Détection des nouveautés » — the « ⋮ » sheet of the Acquisition page.
//
// It says what it does: it checks whether the follows have something new, so that
// it gets searched for. It lives with Acquisitions because that is what makes it
// change — when the check last ran, and when it runs next.
//
// THE RATIO AND THE OBLIGATIONS ARE NOT HERE: they have their own page, the
// « Trackers » one, per tracker and per torrent, with its badge on the bar
// (§ 18). A global figure here would be a second answer to a question that
// page already answers — and a ratio averaged across trackers, which § 18 refuses.
//
// ITS TWO FACTS ARE A FIXTURE, and this producer does not pretend otherwise:
// the values stay declared, in one place, with the operation that will replace
// them named beside each.
//
// « Vérifier maintenant » is the trigger DOIT-6 names, and it is
// unchanged: a producer here offers exactly what it offered.
import { icons } from "../../lib/shell-doors";
import i18next from "i18next";
import { registerProducer, type PanelDescriptor } from "../../ui/panel/contract";


// WHAT THE LAYER WILL ANSWER, and does not yet. Each value carries the
// operation that replaces it, so that lot has a list rather than a search.
// They are VALUES the interface displays — a duration, a figure, a count —
// which is what separates them from the labels beside them in `fr.json`.
const WATCH_FACTS = {
  // → GET /api/v1/pipeline/history — when the watch last ran and when it runs next
  lastPass: "il y a 22 min", // french-ok: a rendered duration, the layer's value to answer
  nextPass: "dans 38 min", // french-ok: a rendered duration, the layer's value to answer
} as const;

/**
 * Builds the « ⋮ » sheet's descriptor.
 *
 * Returns:
 *     The descriptor. It never answers null: nothing here is read from the
 *     cache yet, which is the state this file's header records.
 */
function standbyPanel(): PanelDescriptor {
  const translate = i18next.t.bind(i18next);
  return {
    title: translate("panels.standby.title"),
    meta: translate("panels.standby.meta"),
    blocs: [
      {
        type: "faits",
        lignes: [
          { c: translate("panels.standby.lastPass"), v: WATCH_FACTS.lastPass },
          { c: translate("panels.standby.nextPass"), v: WATCH_FACTS.nextPass },
        ],
      },
      {
        type: "actions",
        actions: [
          {
            text: translate("panels.standby.runNow"),
            icone: icons.refresh,
            ton: "primary",
            // THE SAME VERB THE LEVERS SECTION EMITS, registered once in
            // `features/system/watch-run.ts`. This button used to carry a name
            // nothing answered: it said a sentence and asked the server for
            // nothing, which is what the register row about it is.
            target: { "watch-now": "" },
          },
        ],
      },
    ],
  };
}

registerProducer("more", { produce: standbyPanel });
