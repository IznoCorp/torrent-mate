// THE HARNESS BAR'S NOTES AND WORLD TOGGLES — the harness's own controls,
// and no part of the interface.
//
// The design-notes button is wired here, and so is the welcome hint that points
// at the notes. They speak the operator's language because the operator reads
// them by hand; no rule taps them.
import i18next from "../i18n";
import { redraw } from "../lib/shell-doors";

const currentState = () => window.__store.read().state;

/** Says a message through the frame's message door. */
const toast = (message: string) => window.__toast?.show({ message });

/**
 * Wires the harness bar's notes toggle and the welcome hint.
 *
 * Called once by the boot, right after the engine has started — the moment the
 * hint used to be scheduled from.
 */
export function installHarnessPanel(): void {
  const notesButton = document.querySelector<HTMLElement>("#notesBtn");
  if (notesButton)
    notesButton.onclick = () => {
      window.__store.write({ notes: !currentState().notes });
      document.documentElement.classList.toggle("notes", currentState().notes === true);
      notesButton.setAttribute("aria-pressed", String(currentState().notes));
      toast(currentState().notes ? "Notes de conception affichées." : "Notes masquées.");
    };

  /* B-572: the real/dense world switch. Runtime, not build-time — it moves
     `scen` the way a named state's own patch does, over whichever world the
     build opened on, real or dense. */
  const scenarioButton = document.querySelector<HTMLElement>("#scenarioBtn");
  const paintScenario = (dense: boolean) => {
    if (!scenarioButton) return;
    scenarioButton.setAttribute("aria-pressed", String(dense));
    const label = i18next.t(dense
      ? "harness.scenarioToggle.toReal"
      : "harness.scenarioToggle.toDense");
    scenarioButton.setAttribute("aria-label", label);
    scenarioButton.setAttribute("title", label);
  };
  if (scenarioButton) {
    paintScenario(currentState().scen === "loaded");
    scenarioButton.onclick = () => {
      const dense = currentState().scen !== "loaded";
      window.__store.write({ scen: dense ? "loaded" : "real" });
      paintScenario(dense);
      redraw();
      toast(i18next.t(dense
        ? "harness.scenarioToggle.toastDense"
        : "harness.scenarioToggle.toastReal"));
    };
  }

  /* The welcome hint disappears on first interaction: a bubble that
     returns over an open sheet is a nuisance, not help. */
  let hintShown = false;
  setTimeout(() => {
    // Never in measurement mode: the bubble would cover the last action of
    // the captured screen, and it is harness, not app.
    if (hintShown || document.documentElement.classList.contains("measuring"))
      return;
    hintShown = true;
    toast("Touchez le ⓘ en haut pour afficher les notes de conception.");
  }, 900);
  document.addEventListener(
    "pointerdown",
    () => {
      hintShown = true;
      /* THROUGH THE ONE SEAM, like every other dismissal. This site wrote the
         `show` class alone, which was survivable while the class was the
         whole of the state — it is not: `data-shown` is read by other rules,
         and the action button's visibility now reads whether a message is up.
         Left as it was, the first tap of a session cleared the hint visually
         and stranded the action button until the pending timer fired. */
      /* Asked of the layer rather than read off the document: what is on
         screen is the message host's fact, and a `textContent` read of a
         node the layer keeps rendered after it closes would answer yes about
         a message that had already gone. */
      const onScreen = window.__toast?.read();
      if (
        onScreen?.shown &&
        onScreen.message?.message?.includes("notes de conception")
      )
        window.__toast?.hide();
    },
    { capture: true },
  );
}
