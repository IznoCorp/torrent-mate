// Système's landing door (maquette-blocked § 1.3, ADAPTED): a block's door
// names the section where its cause is settled — « Voir les disques »
// (`data-dial="disks"`), « Voir les dépendances » (`data-dial="dependencies"`)
// — and the landing brings that section's heading into view and focuses it.
//
// THE TRACKERS DOOR'S SHAPE, for a page without tabs: no dial is stored, the
// page has none to keep; the section is found once the page has drawn it.
import { fillLandingDoor } from "../../lib/shell-doors";

// The page this door answers for.
const SYSTEM_PAGE = "sys";
// How long the landing watches the page once it is asked — its reads may still
// be answering — and how often.
const LOOK_FOR = 3000;
const LOOK_EVERY = 100;

// What says the reader took the page back: a finger, a wheel, a key.
const READER_MOVES = ["touchstart", "wheel", "keydown", "mousedown"] as const;

/**
 * Brings one section of Système into view once the page has drawn it, and
 * focuses its heading — and keeps it so while the page is still settling.
 *
 * THE PAGE REDRAWS AS ITS READS ANSWER: the heading's node may be replaced and
 * the sections above it grow, pushing it down. So the heading is looked up
 * again on every round, focused again when a redraw dropped the focus, and
 * centred again when it moved. A reader who touches the page meanwhile keeps
 * it: the landing stops at their first gesture — never at a change of offset,
 * which the browser's own scroll anchoring makes as the page grows.
 *
 * AND IT STOPS THE MOMENT THE PAGE IS LEFT: a Retour within its watch found
 * Système's heading still in the port for a frame, centred it, and the page
 * given back — « À traiter » — kept Système's offset instead of its own (R502,
 * the scroll kept after Retour).
 *
 * @param section The section's name, as its heading's `data-section` carries it.
 */
function landOnSection(section: string): void {
  const started = Date.now();
  // The address Système was landed on, once its section is drawn there.
  let address: string | undefined;
  let top: number | undefined;
  let taken = false;
  const take = () => {
    taken = true;
  };
  for (const move of READER_MOVES) document.addEventListener(move, take, { once: true, capture: true });
  const round = () => {
    if (address !== undefined && location.href !== address) taken = true;
    const heading = document.querySelector<HTMLElement>(`#view [data-section="${CSS.escape(section)}"]`);
    if (heading !== null) address ??= location.href;
    if (!taken && heading !== null) {
      if (document.activeElement === null || document.activeElement === document.body)
        heading.focus({ preventScroll: true });
      if (heading.getBoundingClientRect().top !== top) {
        heading.scrollIntoView({ block: "center", behavior: "instant" });
        top = heading.getBoundingClientRect().top;
      }
    }
    if (!taken && Date.now() - started < LOOK_FOR) window.setTimeout(round, LOOK_EVERY);
    else for (const move of READER_MOVES) document.removeEventListener(move, take, { capture: true });
  };
  window.setTimeout(round, 0);
}

fillLandingDoor((page, dial) => {
  if (page !== SYSTEM_PAGE || !dial) return;
  landOnSection(dial);
});
