// WHAT A DIALOG IS, AS FACTS. `ui/panel/contract.ts` is the precedent and the
// posture is the same: a producer describes what it wants said and offered, and
// the markup is the component's. The two producers this replaces handed
// `openDlg` an HTML STRING — several hundred characters of template, with the
// escaping done by hand at every interpolation.

/** One run of a paragraph. `strong` is the `<b>` the copy leans on. */
export type DialogRun = { text: string; strong?: boolean };

export type DialogBlock =
  | { type: "paragraph"; runs: DialogRun[] }
  /* THE SIMULATION NOTICE. « rien ne sera supprimé tant que vous n'aurez pas
     validé que cette liste dit vrai » — it is what makes a destructive
     confirmation honest, so it is a block of its own and not a paragraph
     someone styled. */
  | { type: "dryRun"; text: string }
  /* EXACTLY WHAT WOULD BE TOUCHED, line by line, with its figure. */
  | { type: "manifest"; entries: { text: string; value: string }[] }
  | { type: "warning"; strong: string; text: string };

export type DialogAction = {
  text: string;
  tone?: "danger" | "ghost";
  /** The `data-*` the document-level delegation reads. It moves at L19. */
  target?: Record<string, string>;
  /** What the act IS, where the producer keeps it as a closure. */
  run?: () => void;
  /** Closes and does nothing else. */
  dismiss?: boolean;
};

export type DialogDescriptor = {
  /** The dialog's NAME. It reads its own heading; there is no second copy. */
  heading: string;
  body: DialogBlock[];
  actions: DialogAction[];
};

/**
 * Refuses a block nobody declared.
 *
 * A dispatcher that draws nothing for an unknown kind is a dispatcher that
 * ships a blank dialog, and a blank confirmation is worse than none. It raises
 * instead, and the refusal is provable from OUTSIDE — `window.__unknownDialog`
 * calls this as a plain function, exactly as `window.__unknownPanel` does for
 * the panel.
 *
 * Args:
 *     block: Whatever arrived.
 *
 * Raises:
 *     Error: Always.
 */
export function refuseDialogBlock(block: { type: string }): never {
  throw new Error(`dialog: no block draws « ${block.type} »`);
}
