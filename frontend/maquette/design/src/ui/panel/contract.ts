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

// ─── WHO PRODUCES A DESCRIPTOR ───────────────────────────────────────────────
//
// The half above says what a descriptor may CONTAIN and who draws each block.
// This half says who BUILDS one, and it is the same shape for the same reason:
// a producer belongs with what makes it change (invariant 10), and the panel
// must be able to open one without knowing which domain answered.
//
// A PRODUCER IS NOT A HOOK AND NOT A COMPONENT. It is called from a click
// delegation, in the middle of a task that cannot await — invariant 10's own
// words, « a function from the cache to a descriptor ».

/**
 * What a producer may ask the query cache for.
 *
 * STRUCTURAL, AND DELIBERATELY SO. This file may not import a feature and
 * carries a domain-word ceiling of zero: a `QueryClient` type would pull the
 * caching library into a primitive that draws, and a query KEY spelled out
 * here would name a domain. `held` takes an opaque key and answers what is
 * cached under it — this file learns nothing about either side.
 */
export type PanelCache = {
  held: <Result>(key: readonly unknown[]) => Result | undefined;
};

/**
 * What builds one panel's descriptor.
 *
 * Answering `null` opens nothing, and it is the honest reply for a subject the
 * cache does not hold yet — the reply the engine's own producers already give
 * by returning early. A producer that guessed instead would draw a panel about
 * a medium nobody has fetched.
 */
export type PanelProducer = (
  subject: string,
  cache: PanelCache,
) => PanelDescriptor | null;

/**
 * A read a producer needs to have LANDED before it can answer.
 *
 * WHY A PRODUCER DECLARES THIS AT ALL, and it was measured rather than
 * foreseen: a producer reads the cache synchronously, and nothing fills a cache
 * for a surface no component has mounted. The account menu is raised from the
 * header on every page and its query belongs to the account PAGE, so the first
 * reading of it was `undefined` on every page but one — the producer answered
 * `null`, correctly, and the menu opened nowhere.
 *
 * The engine's answer to the same problem is `app/engine-data.ts`: ONE list, in
 * `app/`, of what it reads with no component to ask for it. A producer that has
 * moved into its feature declares its own instead, beside itself, which is what
 * lets that list empty entry by entry rather than grow one per conversion.
 *
 * STRUCTURAL, like `PanelCache`: a key and a function that answers. This file
 * learns neither the caching library nor the address.
 */
export type PanelNeed = {
  queryKey: readonly unknown[];
  queryFn: () => Promise<unknown>;
};

/**
 * Everything a feature declares about one panel kind.
 *
 * ONE OBJECT RATHER THAN A GROWING ARGUMENT LIST, because the three answers are
 * about one subject and a positional third argument is a positional fourth
 * waiting to happen.
 *
 * `holds` is separate from `produce` ANSWERING, and the addressed-panel table
 * is why: a producer answers for anything, which is right for a door inside the
 * application and wrong for a door anyone can type into the address bar. The
 * table asks « does this interface hold this subject » before it opens
 * anything, and that question is the FEATURE's knowledge — the engine answered
 * it from its own fixture, which is precisely what keeps a fixture alive after
 * its producer has left.
 */
export type PanelRegistration = {
  produce: PanelProducer;
  /**
   * What must have landed. A LIST when the answer is the same whatever panel is
   * opened, and a FUNCTION OF THE SUBJECT when it is not — a journey is read
   * per medium, and a boot cannot know which one will be asked for. The
   * function form is therefore invisible to the boot's prefill, by
   * construction, and is resolved when a panel is actually asked for.
   */
  needs?: readonly PanelNeed[] | ((subject: string) => readonly PanelNeed[]);
  holds?: (subject: string, cache: PanelCache) => boolean;
};

const producers = new Map<string, PanelProducer>();
const needs = new Map<
  string, readonly PanelNeed[] | ((subject: string) => readonly PanelNeed[])
>();
const holders = new Map<string, (subject: string, cache: PanelCache) => boolean>();

/**
 * Declares what produces a panel kind.
 *
 * Called at module evaluation by the feature that owns the kind, exactly as
 * `registerBlock` is. The shell imports those feature modules at boot, before
 * anything can open a panel.
 *
 * Args:
 *     kind: The panel's kind, as the delegation asks for it.
 *     produce: What builds its descriptor.
 */
export function registerProducer(
  kind: string,
  registration: PanelRegistration,
): void {
  producers.set(kind, registration.produce);
  if (registration.needs !== undefined) needs.set(kind, registration.needs);
  if (registration.holds) holders.set(kind, registration.holds);
}

/**
 * Finds what answers « does this interface hold this subject » for a kind.
 *
 * Args:
 *     kind: The panel's kind.

 * Returns:
 *     The declared answer, or null when the kind declares none — in which case
 *     the caller decides, and the addressed-panel table refuses rather than
 *     guessing.
 */
export function holderFor(
  kind: string,
): ((subject: string, cache: PanelCache) => boolean) | null {
  return holders.get(kind) ?? null;
}

/**
 * Every read the registered producers need to have landed.
 *
 * Answered as one list rather than per kind, because the caller is a boot and a
 * reset — both of which ask for all of it at once — and a per-kind door would
 * invite asking at open time, which is the one moment a producer cannot await.
 *
 * Returns:
 *     The needs, in registration order, with no attempt to remove duplicates:
 *     the cache deduplicates by key, which is the layer that knows how.
 */
export function producerNeeds(): readonly PanelNeed[] {
  // THE LIST FORM ONLY. A need that depends on the subject cannot be asked for
  // at boot without inventing a subject, and a panel about an invented subject
  // is worse than a panel that waits.
  return [...needs.values()].filter(Array.isArray).flat() as PanelNeed[];
}

/**
 * What one kind needs to have landed for one subject.
 *
 * Args:
 *     kind: The panel's kind.
 *     subject: The subject asked for.

 * Returns:
 *     The reads to ask for, resolved.
 */
export function needsFor(kind: string, subject: string): readonly PanelNeed[] {
  const declared = needs.get(kind);
  if (declared === undefined) return [];
  return typeof declared === "function" ? declared(subject) : declared;
}

/**
 * Finds what produces a panel kind.
 *
 * Args:
 *     kind: The panel's kind.

 * Returns:
 *     The registered producer, or null when nothing has registered one.
 */
export function producerFor(kind: string): PanelProducer | null {
  return producers.get(kind) ?? null;
}

/**
 * Names every kind a producer has been registered for.
 *
 * Published for the rule that reads the seam from outside. A rule that had to
 * import this module to ask would be a rule coupled to how the module is
 * built, which is the arrangement `__store` and `__panel` already refuse.
 *
 * Returns:
 *     The kinds, sorted, so a reading is comparable with the one before it.
 */
export function registeredProducers(): string[] {
  return [...producers.keys()].sort();
}

/**
 * Refuses a panel kind nothing produces.
 *
 * `refuseBlock`'s reasoning, one level up and word for word: silence here
 * would open an empty panel and blame the data, which is also what a forgotten
 * `registerProducer` looks like. That is why this throws rather than opening
 * nothing — the two are indistinguishable from the outside, and only one of
 * them is a defect.
 *
 * Args:
 *     kind: The kind nothing registered.

 * Raises:
 *     Error: Always. The message names the kind.
 */
export function refuseProducer(kind: string): never {
  // ENGLISH, and deliberately not in `fr.json`, for the reason `refuseBlock`
  // gives: a tool message reaches a developer console and the rule harness,
  // never a reader of the interface.
  throw new Error("unknown panel producer: " + kind);
}
