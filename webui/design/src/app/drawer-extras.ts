// THE DRAWER'S ONE SEAM FOR A GROUP IT DOES NOT OWN.
//
// The side menu draws the product's navigation, the appearance and the served
// identity, and nothing else. A build that wants one more group at its end — the
// maquette's own controls, which manipulate the prototype and are no part of the
// product — CONTRIBUTES it here, and the drawer draws what was contributed.
//
// THE DIRECTION IS THE POINT. The drawer imports this module and never the
// contributor: `src/harness/` is loaded by the maquette alone (`shell.tsx`, behind
// `__MOCKS_BUILT_IN__`), so a build that drops the harness contributes nothing,
// and the drawer is the product's drawer, byte for byte. A drawer that imported
// the harness would have shipped the maquette's controls with the app.
/** One tappable entry of a contributed group. */
export interface DrawerExtraEntry {
  /** The element's id — what a rule and the contributor's own code address it by. */
  id: string;
  /** The contents of a 24×24 `<svg>`, as `<Icon paths={…} />` takes them. */
  icon: string;
  /** The entry's word, read on every draw so a label that follows a state follows it. */
  label: () => string;
  /** Whether the entry is pressed, when it is a toggle; absent for a plain action. */
  pressed?: () => boolean;
  /** What a tap does. The drawer stays open: the contributor redraws what changed. */
  onPress: () => void;
}

/** A titled group of entries, drawn after everything the drawer owns. */
export interface DrawerExtraGroup {
  /** The group's `data-part`. */
  part: string;
  /** The group's heading, read on every draw. */
  title: () => string;
  entries: DrawerExtraEntry[];
}

const groups: DrawerExtraGroup[] = [];

/**
 * Adds a group at the end of the drawer.
 *
 * Args:
 *     group: The group to draw.
 *
 * Returns:
 *     The function that takes it away again.
 */
export function contributeDrawerGroup(group: DrawerExtraGroup): () => void {
  groups.push(group);
  return () => {
    const at = groups.indexOf(group);
    if (at >= 0) groups.splice(at, 1);
  };
}

/**
 * The groups contributed so far, in the order they were contributed.
 *
 * Returns:
 *     The groups; empty when nothing contributed one — the product's own drawer.
 */
export function drawerExtraGroups(): readonly DrawerExtraGroup[] {
  return groups;
}
