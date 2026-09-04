// The journey sheet — the TUNNEL as the operator sees it (§20).
//
// It lives with Acquisitions because a journey is one acquisition's own
// history: what was taken, when, and where it has got to. §20 says a blocked
// tunnel « reprend là où il s'est arrêté, par l'opérateur » — the verbs that do
// the resuming are **L21's**, and this producer offers exactly what it offered.
//
// ITS STEPS COME FROM THE LAYER, not from a literal inside the function. The
// engine's producer carried the five stages inline; the mock layer already
// answered them at `/api/acquisition/journeys/{infoHash}` and nothing called
// it. That fixture dies here, which is what D5 asks of every producer that
// moves.
//
// A PER-SUBJECT READ, so its need is a FUNCTION of the subject: a journey is
// read per medium and a boot cannot know which one will be asked for.
import i18next from "i18next";
import { registerProducer, type PanelCache, type PanelDescriptor, type PanelNeed } from "../../ui/panel/contract";
import { read } from "../../lib/query-client";

const icons = () => window.__referentiel.icons;

/** One stage of a journey, as the contract answers it. */
type Stage = { label: string; when: string; state: string };

/** Which pip says a stage's state. The three are the interface's drawing. */
const STAGE_PIP: Record<string, string> = {
  done: "success",
  now: "info",
  todo: "neutral",
};

// THE RELEASE THE JOURNEY IS ABOUT, and it is a fixture rather than an answer:
// the contract's `readJourney` returns the STAGES and nothing else, so there is
// nowhere to read it from. Recorded as a demand on the backend (D7) rather than
// dressed up — a journey names the release it followed, and the interface
// requires it.
const RELEASE = "Furious.S01E01.MULTi.1080p.WEB-DL";

/** The stages of one journey, as a query definition. */
function journeyQuery(subject: string): PanelNeed {
  return {
    queryKey: ["/api/acquisition/journeys", subject],
    queryFn: async () =>
      read<Stage[]>(`/api/acquisition/journeys/${encodeURIComponent(subject)}`),
  };
}

/**
 * Builds one journey's descriptor.
 *
 * Args:
 *     title: The medium the journey followed.
 *     cache: What the query cache holds.
 *
 * Returns:
 *     The descriptor, or null while the stages have not landed.
 */
function journeyPanel(title: string, cache: PanelCache): PanelDescriptor | null {
  const stages = cache.held<Stage[]>(journeyQuery(title).queryKey);
  if (stages === undefined) return null;
  const translate = i18next.t.bind(i18next);
  return {
    address: "journey:" + title,
    title,
    meta: [translate("panels.journey.metaBefore"), { m: RELEASE }],
    blocs: [
      {
        type: "faits",
        lignes: stages.map((stage) => ({
          c: stage.label,
          v: stage.when,
          pip: STAGE_PIP[stage.state] ?? "neutral",
          terne: stage.state === "todo",
        })),
      },
      { type: "note", text: translate("panels.journey.provenanceNote") },
      {
        type: "actions",
        actions: [
          {
            text: translate("panels.journey.seeSheet"),
            icone: icons().eye,
            target: { mediasheet: title },
          },
        ],
      },
    ],
  };
}

registerProducer("journey", {
  produce: journeyPanel,
  needs: (subject) => [journeyQuery(subject)],
});
