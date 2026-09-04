// « Veille et obligations » — the « ⋮ » sheet of the Acquisition page.
//
// Second rank, and it says so: what is consulted rather than watched. It lives
// with Acquisitions because that is what makes it change — when the watch last
// ran, what the ratio stands at, what is still owed to a tracker.
//
// ITS FOUR FACTS ARE A FIXTURE, and this producer does not pretend otherwise.
// `GET /api/acquisition/obligations`, `/stalled-grabs` and `/downloads` all
// ANSWER on the backend and are called by nothing — `product-intent-map.md`
// reads DOIT-13 « to draw » and hands the ratio surface to **L16**, which is
// the lot that wires them. Reading them here would be drawing §18 in this lot's
// clothes. So the four values stay declared, in one place, with the operations
// that will replace them named beside each.
//
// « Lancer la veille maintenant » is the trigger DOIT-6 names, and it is
// unchanged: a producer here offers exactly what it offered.
import i18next from "i18next";
import { registerProducer, type PanelDescriptor } from "../../ui/panel/contract";

const icons = () => window.__referentiel.icons;

// WHAT THE LAYER WILL ANSWER, and does not yet. Each value carries the
// operation that replaces it, so L16 has a list rather than a search. They are
// VALUES the interface displays — a duration, a figure, a count — which is what
// separates them from the labels beside them in `fr.json`.
const WATCH_FACTS = {
  // → GET /api/pipeline/history — when the watch last ran and when it runs next
  lastPass: "il y a 22 min", // french-ok: a rendered duration, the layer's value to answer
  nextPass: "dans 38 min", // french-ok: a rendered duration, the layer's value to answer
  // → GET /api/acquisition/downloads — the ratio across every tracker
  globalRatio: "2,41",
  // → GET /api/acquisition/obligations — what is still owed to a tracker
  obligations: "3 torrents", // french-ok: a rendered count, the layer's value to answer
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
          {
            c: translate("panels.standby.globalRatio"),
            v: WATCH_FACTS.globalRatio,
            pipValue: "success",
          },
          {
            c: translate("panels.standby.obligations"),
            v: WATCH_FACTS.obligations,
          },
        ],
      },
      {
        type: "actions",
        actions: [
          {
            text: translate("panels.standby.runNow"),
            icone: icons().refresh,
            ton: "primary",
            target: { standby: "1" },
          },
        ],
      },
    ],
  };
}

registerProducer("more", { produce: standbyPanel });
