// design/src/focus.ts
// FOCUS, WHEN A LAYER OPENS AND WHEN IT CLOSES.
//
// A layer that opens without taking focus leaves a keyboard on the page behind
// it: Tab walks a list the reader cannot see, Escape has nothing to close, and
// a screen reader keeps announcing a surface the interface has covered. A layer
// that closes without GIVING focus back is worse — the caret lands at the top
// of the document and the reader begins again.
//
// WHAT IT OBSERVES, AND WHY IT NEEDS NOTHING FROM THE ENGINE. Every layer in
// this prototype already announces itself: `setOpen(element, on)` toggles the
// `data-open` attribute on `#drawer`, `#screen`, `#dlg` and `#scrim`, and the
// React side (`components/sheet.tsx`, the five screens) emits the same
// attribute itself. So this module watches an attribute that exists rather than
// asking anyone to call it. Nothing in the engine changes; the contract is
// markup, which is what makes this survive the engine's removal.
//
// WHY `inert` AND NOT `aria-hidden`. `aria-hidden` hides a subtree from a
// screen reader and leaves every control in it TABBABLE — the reader tabs into
// something that is no longer announced, which is a worse state than either
// half alone. `inert` removes the subtree from the tab order AND from the
// accessibility tree, in one attribute the platform implements.
//
// THE BACKGROUND IS THE FRAME'S OTHER CHILDREN, never the layer's ancestors.
// Marking `document.body` inert would mark the layer too.

// The layer roots, most-recently-opened last. The order is the stacking order
// the engine already unwinds — drawer, then screen, then sheet — so the topmost
// open layer is the last one here that carries `data-open`.
const LAYERS = ["#drawer", "#screen", "#sheet", "#dlg"] as const;

// Where focus goes when a layer opens: the first control the reader would
// reach anyway. `[autofocus]` first, so a layer can name its own entry point.
const ENTRY =
  "[autofocus],button:not([disabled]),[href],input:not([disabled])," +
  "select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex='-1'])";

type Restore = { layer: Element; trigger: HTMLElement | null };

let stack: Restore[] = [];
let observer: MutationObserver | null = null;

function isOpen(node: Element): boolean {
  return node.hasAttribute("data-open");
}

function openLayers(): Element[] {
  return LAYERS.map((selector) => document.querySelector(selector))
    .filter((node): node is Element => Boolean(node) && isOpen(node as Element));
}

/**
 * Marks everything except the open layer as `inert`, or clears it.
 *
 * The siblings walked are the phone frame's children — the shell's header, the
 * main region, the tab bar and the other layers. An ancestor can never be
 * inert: it contains the layer.
 *
 * @param layer The layer that owns focus, or null to clear every mark.
 */
function setBackgroundInert(layer: Element | null): void {
  const frame = document.getElementById("device");
  if (!frame) return;
  for (const child of Array.from(frame.children)) {
    // The React mount node holds the sheet AND the screens; marking it whole
    // would mark the very layer that is open. Its children are walked instead.
    const nodes = child.id === "shell" ? Array.from(child.children) : [child];
    for (const node of nodes) {
      const contains = layer ? node === layer || node.contains(layer) : false;
      if (layer && !contains) node.setAttribute("inert", "");
      else node.removeAttribute("inert");
    }
  }
}

/**
 * Moves focus into a layer that has just opened.
 *
 * @param layer The layer's root.
 */
function focusInto(layer: Element): void {
  const target = layer.querySelector<HTMLElement>(ENTRY);
  if (target) {
    target.focus();
    return;
  }
  // A layer with no control of its own still has to receive focus, or the
  // reader stays behind it. `tabindex="-1"` makes the root focusable by script
  // without adding a stop to the tab order.
  const root = layer as HTMLElement;
  root.setAttribute("tabindex", "-1");
  root.focus();
}

/** Reconciles the focus stack with what the markup currently says is open. */
function reconcile(): void {
  const open = openLayers();
  const top = open.length ? open[open.length - 1] : null;
  const previous = stack.length ? stack[stack.length - 1] : null;

  if (top && previous?.layer === top) return;

  // Closing: unwind every entry whose layer is no longer open, giving focus
  // back to the trigger recorded when it opened.
  //
  // THE INERT MARK COMES OFF FIRST, and that ordering is the whole of it.
  // `focus()` on an element inside an `inert` subtree does nothing — silently,
  // with no error and no return value to check — and every trigger this
  // restores is in the background the layer had just made inert. Restoring
  // before clearing left the caret on `<body>` at every close, which is exactly
  // the defect the manager exists to prevent, reproduced by the manager.
  const unwinding = stack.length && !isOpen(stack[stack.length - 1].layer);
  if (unwinding && !top) setBackgroundInert(null);
  while (stack.length && !isOpen(stack[stack.length - 1].layer)) {
    const closed = stack.pop() as Restore;
    if (!open.length && closed.trigger?.isConnected) closed.trigger.focus();
  }

  if (!top) {
    setBackgroundInert(null);
    return;
  }
  if (!stack.some((entry) => entry.layer === top)) {
    const active = document.activeElement;
    stack.push({
      layer: top,
      // The trigger is recorded BEFORE focus moves. `document.body` is what
      // `activeElement` reports when nothing is focused, and giving focus back
      // to the body is the same as giving it back to nowhere.
      trigger:
        active instanceof HTMLElement && active !== document.body ? active : null,
    });
    setBackgroundInert(top);
    focusInto(top);
    return;
  }
  setBackgroundInert(top);
}

/**
 * Installs the layer focus manager. Idempotent — a second call is a no-op.
 *
 * Called once from the shell's boot, before the engine starts, so the first
 * layer an operator opens is already covered.
 */
export function installFocusManager(): void {
  if (observer) return;
  observer = new MutationObserver(reconcile);
  observer.observe(document.body, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: ["data-open"],
  });
  // THE SKIP LINK IS DRIVEN HERE, not left to the browser. `<a href="#port">`
  // should move focus to a target carrying `tabindex="-1"`, and measured, it
  // does not in this prototype: the router owns the URL and the hash never
  // reaches the document's default handling, so the link scrolled and the caret
  // stayed on `<body>` — a skip link that moves the view and not the focus is
  // the commonest way to ship one that does nothing.
  document.addEventListener("click", (event) => {
    const target = event.target as Element | null;
    const link = target?.closest?.('[data-part="shell/skip-link"]');
    if (!link) return;
    event.preventDefault();
    const main = document.getElementById("port");
    if (!main) return;
    main.focus();
    main.scrollTop = 0;
  });

  // `keydown` on the document, in the CAPTURE phase: a layer's own handler must
  // not be able to swallow the one key that closes it.
  document.addEventListener(
    "keydown",
    (event) => {
      if (event.key !== "Escape") return;
      if (!openLayers().length) return;
      event.preventDefault();
      // The verb the engine already publishes, and the ladder it already
      // unwinds — drawer, then screen, then sheet. Writing a second closer here
      // would give the interface two answers to one gesture.
      window.__closeLayers?.();
    },
    true,
  );
  reconcile();
}
