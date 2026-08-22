// design/src/components/sheet.tsx
// The bottom-sheet LAYER — the scrim behind it, the panel body, the handle one
// drags down to dismiss. It replaces the envelope's `#scrim`/`#sheet` cluster
// at IDENTICAL ids, tags and class chains (`div#scrim.scrim`,
// `div#sheet.sheet > div#sheetgrab.sheetgrab + div#sheetin.sheetin`), so the
// stylesheet applies unchanged and every probe that reads them by selector
// measures the React layer without knowing anything changed. Only the owner
// moved.
//
// It paints ABOVE a legacy `#screen` for the same reason it always did: the
// sheet is z-47 and a screen is z-45, and the React mount node (`#shell`)
// creates no stacking context of its own, so the two z-indexes are compared
// in the SAME context even though the elements now live in different subtrees.
//
// The layer is mounted with the shell and rendered ALWAYS: closed is a class,
// not an absence — the CSS transition that carries the sheet in and out needs
// both states on the same element, and the legacy `#sheetin` likewise kept its
// content after closing.
import { useLayoutEffect, useRef } from "react";
import { useUiState } from "../data";
import { PanelContent, type PanelDescriptor } from "./panel";

// How far the sheet must travel before the lift closes it — the legacy
// `SEUIL_FERMETURE`, unchanged.
const CLOSE_THRESHOLD = 70;

type Drag = { y: number; dy: number };

export function Sheet({
  close,
}: {
  // The layer's own closer, handed down rather than reached for on
  // `window.__panel`: the shell owns the verb, this component only decides
  // WHEN a gesture amounts to a dismissal.
  close: (pop?: boolean) => void;
}) {
  const state = useUiState();
  const open = state.panelOpen === true;
  // The last descriptor stays rendered while closed. The legacy layer kept
  // `#sheetin`'s markup after `closeSheet`, and the sheet slides out over
  // several frames — emptying it on close would blank the panel mid-exit.
  const descriptor = (state.panelDescriptor ??
    null) as PanelDescriptor | null;

  const sheetRef = useRef<HTMLDivElement | null>(null);
  const innerRef = useRef<HTMLDivElement | null>(null);
  const dragRef = useRef<Drag | null>(null);

  // A panel opens at its TOP. The legacy layer got that for free — replacing
  // `#sheetin`'s innerHTML reset its scroll — and the persistent node does
  // not: a long panel left scrolled down would hand its offset to the next
  // one, which then opens in its own middle. Keyed on the DESCRIPTOR's
  // identity, so it fires once per open (a new descriptor object) and not on
  // the unrelated store writes that re-render this layer. Before the paint,
  // not after, so the offset is never briefly visible.
  useLayoutEffect(() => {
    if (innerRef.current) innerRef.current.scrollTop = 0;
  }, [descriptor]);

  // The drag writes the DOM directly, through the ref, exactly as the legacy
  // handler did — and deliberately NOT through the store. `dragging` has to
  // land in the same task as the `pointerdown` that starts the gesture (it is
  // what kills the CSS transition; one frame late and the first move animates
  // instead of tracking the finger), and the transform is rewritten on every
  // move — a re-render per frame of the whole panel to move one element.
  function endDrag(cancelled: boolean) {
    const current = dragRef.current;
    if (!current) return;
    dragRef.current = null;
    const node = sheetRef.current;
    if (node) {
      node.classList.remove("dragging");
      node.style.transform = "";
    }
    // The CSS transition carries the settle both ways: closing from here, or
    // springing back to `transform: none` when the lift was too short.
    if (!cancelled && current.dy > CLOSE_THRESHOLD) close();
  }

  return (
    <>
      <div
        id="scrim"
        data-part="scrim"
        aria-hidden="true"
        data-open={open || undefined}
        className={"scrim" + (open ? " open" : "")}
        // The scrim is shared ground: the drawer and the dialog raise it
        // themselves and a tap on it closes whichever of the three is up. The
        // engine still owns that decision — reproduced here by calling the
        // verb it publishes, rather than by closing the sheet alone and
        // leaving the other two open.
        onClick={() => window.__closeLayers?.()}
      />
      {/* A MODAL DIALOG, and only while it is open. The layer is rendered
          always — closed is a class, not an absence — so a permanent
          `role="dialog"` would leave a nameless dialog in the tree at all
          times, which an assistive technology announces and a reader cannot
          reach. The role appears with the descriptor that names it. */}
      <div
        ref={sheetRef}
        id="sheet"
        data-part="sheet"
        data-open={open || undefined}
        role={open ? "dialog" : undefined}
        aria-modal={open ? true : undefined}
        aria-label={open ? descriptor?.title : undefined}
        className={"sheet" + (open ? " open" : "")}
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
          onPointerDown={(event) => {
            dragRef.current = { y: event.clientY, dy: 0 };
            sheetRef.current?.classList.add("dragging");
            event.currentTarget.setPointerCapture(event.pointerId);
          }}
          onPointerMove={(event) => {
            const current = dragRef.current;
            if (!current) return;
            current.dy = Math.max(0, event.clientY - current.y);
            const node = sheetRef.current;
            if (node) node.style.transform = `translateY(${current.dy}px)`;
          }}
          onPointerUp={() => endDrag(false)}
          // A cancel is not a lift: it must put the sheet back where it was
          // rather than close it on a gesture the browser took away.
          onPointerCancel={() => endDrag(true)}
        />
        <div ref={innerRef} id="sheetin" className="sheetin" data-part="sheet/viewport">
          {descriptor ? <PanelContent descriptor={descriptor} /> : null}
        </div>
      </div>
    </>
  );
}
