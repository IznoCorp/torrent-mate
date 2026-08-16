// design/src/composants/feuille.tsx
// The bottom-sheet LAYER — the scrim behind it, the panel body, the handle one
// drags down to dismiss. It replaces the envelope's `#scrim`/`#sheet` cluster
// at IDENTICAL ids, tags and class chains (`div#scrim.scrim`,
// `div#sheet.sheet > div#sheetgrab.sheetgrab + div#sheetin.sheetin`), so the
// stylesheet applies unchanged and every probe that reads them by selector
// measures the React layer without knowing anything changed. Only the owner
// moved.
//
// It paints ABOVE a legacy `#screen` for the same reason it always did: the
// sheet is z-47 and a screen is z-45, and the React mount node (`#coquille`)
// creates no stacking context of its own, so the two z-indexes are compared
// in the SAME context even though the elements now live in different subtrees.
//
// The layer is mounted with the shell and rendered ALWAYS: closed is a class,
// not an absence — the CSS transition that carries the sheet in and out needs
// both states on the same element, and the legacy `#sheetin` likewise kept its
// content after closing.
import { useRef } from "react";
import { useEtat } from "../donnees";
import { PanneauContenu, type Descripteur } from "./panneau";

// How far the sheet must travel before the lift closes it — the legacy
// `SEUIL_FERMETURE`, unchanged.
const SEUIL_FERMETURE = 70;

type Glisse = { y: number; dy: number };

export function Feuille({
  fermer,
}: {
  // The layer's own closer, handed down rather than reached for on
  // `window.__panneau`: the shell owns the verb, this component only decides
  // WHEN a gesture amounts to a dismissal.
  fermer: (pop?: boolean) => void;
}) {
  const etat = useEtat();
  const ouvert = etat.panneauOuvert === true;
  // The last descriptor stays rendered while closed. The legacy layer kept
  // `#sheetin`'s markup after `closeSheet`, and the sheet slides out over
  // several frames — emptying it on close would blank the panel mid-exit.
  const descripteur = (etat.panneauDescripteur ?? null) as Descripteur | null;

  const feuille = useRef<HTMLDivElement | null>(null);
  const glisse = useRef<Glisse | null>(null);

  // The drag writes the DOM directly, through the ref, exactly as the legacy
  // handler did — and deliberately NOT through the store. `dragging` has to
  // land in the same task as the `pointerdown` that starts the gesture (it is
  // what kills the CSS transition; one frame late and the first move animates
  // instead of tracking the finger), and the transform is rewritten on every
  // move — a re-render per frame of the whole panel to move one element.
  function finGlisse(annule: boolean) {
    const enCours = glisse.current;
    if (!enCours) return;
    glisse.current = null;
    const noeud = feuille.current;
    if (noeud) {
      noeud.classList.remove("dragging");
      noeud.style.transform = "";
    }
    // The CSS transition carries the settle both ways: closing from here, or
    // springing back to `transform: none` when the lift was too short.
    if (!annule && enCours.dy > SEUIL_FERMETURE) fermer();
  }

  return (
    <>
      <div
        id="scrim"
        className={"scrim" + (ouvert ? " open" : "")}
        // The scrim is shared ground: the drawer and the dialog raise it
        // themselves and a tap on it closes whichever of the three is up. The
        // engine still owns that decision — reproduced here by calling the
        // verb it publishes, rather than by closing the sheet alone and
        // leaving the other two open.
        onClick={() => window.__fermerCouches?.()}
      />
      <div
        ref={feuille}
        id="sheet"
        className={"sheet" + (ouvert ? " open" : "")}
      >
        {/* The handle CAPTURES the pointer and claims its axis (`touch-action`
            comes from the stylesheet). Without the capture a real finger
            delivered `pointerdown`, two `pointermove`s and then
            `pointercancel`: the compositor took the vertical drag, the pointer
            stream died, `pointerup` never came, and the sheet — whose closing
            hangs off that lift — simply stayed open. Capture also keeps the
            events coming once the finger leaves a 22px strip, which happens
            within the first centimetre of a gesture that has to travel 70px. */}
        <div
          id="sheetgrab"
          className="sheetgrab"
          onPointerDown={(evenement) => {
            glisse.current = { y: evenement.clientY, dy: 0 };
            feuille.current?.classList.add("dragging");
            evenement.currentTarget.setPointerCapture(evenement.pointerId);
          }}
          onPointerMove={(evenement) => {
            const enCours = glisse.current;
            if (!enCours) return;
            enCours.dy = Math.max(0, evenement.clientY - enCours.y);
            const noeud = feuille.current;
            if (noeud) noeud.style.transform = `translateY(${enCours.dy}px)`;
          }}
          onPointerUp={() => finGlisse(false)}
          // A cancel is not a lift: it must put the sheet back where it was
          // rather than close it on a gesture the browser took away.
          onPointerCancel={() => finGlisse(true)}
        />
        <div id="sheetin" className="sheetin">
          {descripteur ? <PanneauContenu descripteur={descripteur} /> : null}
        </div>
      </div>
    </>
  );
}
