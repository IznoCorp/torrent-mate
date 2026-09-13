// THE ≡ PANEL — the harness's own control surface, and no part of the interface.
//
// It lists every named state and three dials — the data scenario, the surface
// phase, the TMDB account — and a tap drives the prototype there. It speaks the
// operator's language because the operator reads it by hand; no rule taps it.
// Its markup is the one it always had: it was moved here, not redrawn.
//
// The harness bar's other two controls live here too — the design-notes toggle
// and the button that opens this panel — and so does the welcome hint that
// points at the notes.
import { icons } from "../app/icons";
import { escapeHtml, render, svgIcon, toast } from "../engine/legacy.js";
import { registerVerb } from "../lib/verbs";

const currentState = () => window.__store.read().state;

/** Removes the panel, if one is up. */
export function closeHarnessPanel(): void {
  const element = document.querySelector(".hpanel");
  if (element) element.remove();
}

/** Draws the panel afresh, over whatever it replaces. */
function openHarnessPanel(): void {
  closeHarnessPanel();
  const current = currentState();
  const createElement = document.createElement("div");
  createElement.className = "hpanel";
  createElement.dataset.part = "harness/panel";
  createElement.innerHTML = `
      <div style="display:flex;align-items:center;gap:8px">
        <h4 style="flex:1">Harnais — hors application</h4>
        <button class="iconbtn" data-hclose="1" aria-label="Fermer">${svgIcon(icons.x)}</button>
      </div>
      <p>Ce panneau ne fait pas partie de l'interface. Il pilote les données et les états pour qu'on puisse tous les regarder — et pour que la sonde de parité les atteigne sans deviner. <code>window.__go("id")</code> fait la même chose sans clic.</p>
      <h4>Données</h4>
      <div class="row">
        <button data-hscen="real" aria-pressed="${current.scen === "real"}">État réel du 10 août</button>
        <button data-hscen="loaded" aria-pressed="${current.scen === "loaded"}">Scénario de charge</button>
      </div>
      <h4>Phase de la surface</h4>
      <div class="row">
        ${["ready", "loading", "error"].map((element) => `<button data-hphase="${element}" aria-pressed="${current.phase === element}">${element === "ready" ? "Prête" : element === "loading" ? "Chargement" : "Erreur"}</button>`).join("")}
      </div>
      <h4>Compte TMDB</h4>
      <div class="row">
        <button data-htmdb="1" aria-pressed="${current.tmdb}">Connecté</button>
        <button data-htmdb="0" aria-pressed="${!current.tmdb}">Non connecté</button>
      </div>
      <h4>${window.__etatsDetailles().length} états mesurables</h4>
      <div class="row states">
        ${window.__etatsDetailles().map(([id, lab]) => `<button data-hgo="${id}">${escapeHtml(lab)}<code>${id}</code></button>`).join("")}
      </div>`;
  document.querySelector("#device")?.appendChild(createElement);
}

/**
 * Wires the harness bar, the panel's five verbs and the welcome hint.
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
  const scenarioButton = document.querySelector<HTMLElement>("#scenBtn");
  if (scenarioButton)
    scenarioButton.onclick = () => {
      openHarnessPanel();
    };

  // The registry answers in capture, so a tap on the panel never reaches the
  // engine's delegation.
  registerVerb("hclose", () => closeHarnessPanel());
  registerVerb("hgo", (stateId) => {
    window.__go(stateId);
  });
  registerVerb("hscen", (scenario) => {
    window.__store.write({ scen: scenario });
    render();
    openHarnessPanel();
  });
  registerVerb("hphase", (phase) => {
    window.__store.write({ phase });
    render();
    openHarnessPanel();
  });
  registerVerb("htmdb", (connected) => {
    window.__store.write({ tmdb: connected === "1" });
    render();
    openHarnessPanel();
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
