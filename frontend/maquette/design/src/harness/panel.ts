// THE MAQUETTE'S TWO CONTROLS — the design notes and the real/dense world — and the
// welcome hint that points at them. The harness's own, and no part of the interface.
//
// THEY LIVE IN THE SIDE MENU, in a group of their own at its end. They used to float
// in a bar over the page and covered the maquette's own information. They are
// CONTRIBUTED to the drawer through `app/drawer-extras.ts` — this module is loaded by
// the maquette alone, so the product's drawer never carries them and never imports
// this file.
//
// They speak the operator's language because the operator reads them by hand; no
// rule taps the words, the rules address the two entries by id.
import i18next from "../i18n";
import { contributeDrawerGroup } from "../app/drawer-extras";
import { redraw } from "../lib/shell-doors";

const currentState = () => window.__store.read().state;

/** Says a message through the frame's message door. */
const toast = (message: string) => window.__toast?.show({ message });

// The icons are drawn from the bar's own: an information mark and a stack of discs.
const NOTES_ICON = '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>';
const WORLD_ICON =
  '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.66 3.58 3 8 3s8-1.34 8-3V5"/>'
  + '<path d="M4 11v6c0 1.66 3.58 3 8 3s8-1.34 8-3v-6"/>';

/**
 * Contributes the two controls to the side menu and wires the welcome hint.
 *
 * Called once by the boot, right after the engine has started — the moment the
 * hint used to be scheduled from.
 */
export function installHarnessPanel(): void {
  contributeDrawerGroup({
    part: "harness/menu",
    title: () => i18next.t("harness.menu.group"),
    entries: [
      {
        id: "notesBtn",
        icon: NOTES_ICON,
        label: () => i18next.t("harness.menu.notes"),
        pressed: () => currentState().notes === true,
        onPress: () => {
          window.__store.write({ notes: !currentState().notes });
          document.documentElement.classList.toggle("notes", currentState().notes === true);
          toast(i18next.t(currentState().notes ? "harness.menu.notesShown" : "harness.menu.notesHidden"));
        },
      },
      /* B-572: the real/dense world switch. Runtime, not build-time — it moves
         `scen` the way a named state's own patch does, over whichever world the
         build opened on, real or dense. Its label follows the current world. */
      {
        id: "scenarioBtn",
        icon: WORLD_ICON,
        label: () => i18next.t(currentState().scen === "loaded"
          ? "harness.scenarioToggle.toReal"
          : "harness.scenarioToggle.toDense"),
        pressed: () => currentState().scen === "loaded",
        onPress: () => {
          const dense = currentState().scen !== "loaded";
          window.__store.write({ scen: dense ? "loaded" : "real" });
          redraw();
          toast(i18next.t(dense
            ? "harness.scenarioToggle.toastDense"
            : "harness.scenarioToggle.toastReal"));
        },
      },
    ],
  });

  /* The welcome hint disappears on first interaction: a bubble that
     returns over an open sheet is a nuisance, not help. */
  let hintShown = false;
  setTimeout(() => {
    // Never in measurement mode: the bubble would cover the last action of
    // the captured screen, and it is harness, not app.
    if (hintShown || document.documentElement.classList.contains("measuring"))
      return;
    hintShown = true;
    toast(i18next.t("harness.menu.hint"));
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
        onScreen.message?.message === i18next.t("harness.menu.hint")
      )
        window.__toast?.hide();
    },
    { capture: true },
  );
}
