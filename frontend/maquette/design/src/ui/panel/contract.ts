// The panel's contract: what a producer may ask for, and how a block kind
// makes itself renderable.
//
// It holds no component and imports no feature, so both sides can depend on it
// without depending on each other — which is the whole point. The panel is the
// one surface in this interface that five domains reach into, and a renderer
// that had to KNOW those five domains would be a primitive that knows what a
// television season and a configuration setting are.
//
// THE BLOCK UNION IS OPEN, and that is a typing decision rather than a
// convenience. `PanelBlockMap` is an interface, so a feature ADDS its own kind
// to it by declaration merging — `declare module` — and the union derived from
// it stays a discriminated union: `block.type === "saisons"` still narrows to
// that kind's own fields, and a missing field is still a compile error. An
// open union spelled `{ type: string }` would have bought the same layering at
// the price of every generic block's typing.
//
// The `type` values and every field name are the PRODUCERS' own vocabulary —
// the legacy engine builds these objects — so they stay whatever the fragment
// writes.
import type { JSX } from "react";

// A `richText` segment: plain text, a mono/code aside (`{ m }`), or an
// emphasised aside (`{ e }`) — exactly the three shapes `richText` switches
// on in refonte.html.
export type Segment = string | { m: string } | { e: string };
export type RichTextValue = string | Segment[];

// An ACTION is `{ texte, icone, cible, ton, desactive, mention, infobulle }`
// — `target` is a map of DATA ATTRIBUTES, never a handler and never markup;
// the click delegation reads those attributes, exactly as it does for a
// card. The component that draws it adds NO `onClick` of its own for it.
export type Action = {
  text: string;
  icone?: string;
  target?: Record<string, string | number>;
  ton?: string;
  desactive?: boolean;
  mention?: string;
  infobulle?: string;
};

// A LIGNE of « faits » is `{ c, v, pip, pipValeur, terne }`: caption, value,
// a status dot on either side — one qualifies the step and the other the
// figure — and whether the value is still to come.
export type FactLine = {
  c: string;
  v: string;
  pip?: string;
  pipValue?: string;
  terne?: boolean;
};

/**
 * Every block kind a descriptor may declare.
 *
 * `ui/panel` declares the three that know no domain. A feature adds its own
 * by merging into this interface from its own file:
 *
 *     declare module "…/ui/panel/contract" {
 *       interface PanelBlockMap {
 *         saisons: { isFollowed: Follow; seasons: Season[] };
 *       }
 *     }
 *
 * Adding the kind to this map is only half of it — the other half is
 * `registerBlock`, which supplies what DRAWS it. A kind declared here with no
 * renderer registered is refused at render time, loudly, by `refuseBlock`.
 */
export interface PanelBlockMap {
  note: { text: RichTextValue };
  faits: { lignes: FactLine[] };
  actions: { actions: (Action | null | undefined)[]; secondary?: boolean };
}

// A BLOCK is `{ type, … }`, never HTML. Order matters and is the caller's.
export type PanelBlock = {
  [Kind in keyof PanelBlockMap]: { type: Kind } & PanelBlockMap[Kind];
}[keyof PanelBlockMap];

// THE DESCRIPTOR — facts, never markup. `title` is read unconditionally by
// `panneauHTML` (no guard around it), so it is required here, not optional
// as a first read of the legacy source might suggest.
export type PanelDescriptor = {
  // The panel's ADDRESS, as `<kind>:<subject>` — D1's second tier, where a
  // screen state travels in the query. Present on the panels whose subject is
  // stable and nameable, absent on the ones that are not: a menu has no
  // subject, and a panel keyed on a POSITION in a list the engine regenerates
  // would, after that list moved, reopen about something the operator never
  // asked for. Absent means transient — Back still closes it, it simply has no
  // URL, which is D1's third tier.
  address?: string;
  title: string;
  subtitle?: string;
  meta?: RichTextValue;
  puce?: [string, string] | null;
  poster?: { t: string; k?: string };
  avatar?: string;
  // A block may be ABSENT and say so in place: a caller writes
  // `setting.note ? { type: "note", … } : null` inline rather than assembling
  // the list conditionally, and `panneauBlocHTML` answered an empty string for
  // it. The same tolerance, expressed in the type instead of discovered at
  // render time.
  blocs?: (PanelBlock | null | undefined)[];
};

// What draws one block. The parameter is the OPEN union, so a registered
// renderer narrows on `type` exactly as the closed switch used to.
type BlockRenderer = (block: PanelBlock) => JSX.Element;

const renderers = new Map<string, BlockRenderer>();

/**
 * Declares what draws a block kind.
 *
 * Called at module evaluation by the module that owns the kind — `ui/panel`
 * for the three generic ones, a feature for its own. The shell imports those
 * feature modules at boot, before anything can open a panel.
 *
 * Args:
 *     kind: The block's `type` value, as a producer writes it.
 *     render: What draws it.
 */
export function registerBlock<Kind extends keyof PanelBlockMap>(
  kind: Kind,
  render: (block: { type: Kind } & PanelBlockMap[Kind]) => JSX.Element,
): void {
  // The registry ERASES the kind, so the stored signature is the open union
  // while every renderer accepts one arm of it. The widening is safe by
  // construction and by construction only: `BlockView` looks a renderer up BY
  // `block.type`, so the block it is handed is always the arm it was
  // registered for. TypeScript cannot see that — a `Map` forgets which key
  // produced which value — hence the step through `unknown`, which is the
  // narrowest way to say it and is not an `any`.
  renderers.set(kind as string, render as unknown as BlockRenderer);
}

/**
 * Finds what draws a block kind.
 *
 * Args:
 *     kind: The block's `type` value.

 * Returns:
 *     The registered renderer, or null when nothing has registered one.
 */
export function rendererFor(kind: string): BlockRenderer | null {
  return renderers.get(kind) ?? null;
}

/**
 * Refuses a block nothing can draw.
 *
 * Named, so the probe that exercises it (`window.__unknownPanel`, published
 * by the shell) raises the SAME error the renderer raises rather than a copy
 * of its message that can drift. Silence here would draw an empty panel and
 * blame the data — which is also what a forgotten `registerBlock` would look
 * like, and the reason this throws rather than rendering nothing.
 *
 * Args:
 *     block: The block whose kind nothing declared.

 * Raises:
 *     Error: Always. The message names the kind.
 */
export function refuseBlock(block: { type: string }): never {
  // ENGLISH, and deliberately not in `fr.json`: this is a tool message. It
  // reaches a developer console and the rule harness, never a reader of the
  // interface, so it is not a translatable string — the same reason
  // `console.error` calls in the shell are English.
  throw new Error("unknown panel block: " + block.type);
}
