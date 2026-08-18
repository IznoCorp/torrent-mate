// design/src/data.ts
// The domain hooks are the single door between components and the store.
// Their IMPLEMENTATION is what the backend-binding mission will replace;
// components must never reach around them to the store or the engine.
import { useSyncExternalStore } from "react";
import type { PanelDescriptor } from "./components/panel";
import type { StoreContent, UiState } from "./store";

function subscribe(callback: () => void): () => void {
  const subscription = window.__magasin.store.subscribe(callback);
  return () => subscription.unsubscribe();
}

export function useStoreContent<T>(select: (c: StoreContent) => T): T {
  // `version` bumps on every write INCLUDING in-place world mutations, so a
  // selector over a mutated-in-place object still re-reads: the snapshot the
  // comparison sees is the selected value, re-derived per notification.
  return useSyncExternalStore(subscribe, () => select(window.__magasin.lire()));
}

export const useUiState = (): UiState => useStoreContent((c) => c.etat);
export const useWorld = (): unknown => useStoreContent((c) => c.monde);

// The single write door, matching the read side above: a component patches
// the store through THIS function, never through `window.__magasin.ecrire`
// directly — the binding mission replaces this function's implementation
// (and only this one) when the real store arrives, exactly as it replaces
// `useReference()`'s below. `window.__magasin.ecrire` stays the actual
// primitive underneath because the still-legacy call sites (refonte.html)
// have no hook to go through; a component reaching around this accessor is
// what would make that replacement touch component code too.
export function writeUiState(patch: Partial<UiState>): void {
  window.__magasin.ecrire(patch);
}

export type Resolution = "720p" | "1080p" | "2160p";

export type Release = {
  n: string;
  res: string;
  src: string;
  lang: string;
  s: number;
  go: number;
  sc: number;
};

// A search hit, exactly as the mock `SEARCH` constant shapes one. `k` is the
// French kind label used throughout the legacy templates ("Film" / "Série"),
// not the English "movie"/"show" token `cardHTML` itself expects for a
// poster's aspect ratio — the two are deliberately different vocabularies at
// two different seams, and a migrated screen converts between them exactly
// where `openAddScreen` used to.
export type SearchResult = {
  t: string;
  y: string;
  k: "Film" | "Série"; // french-ok: a data VALUE — the label is read from fr.json at the render
  ov: string;
  owned: boolean;
  followed: boolean;
};

export type SearchResults = {
  total: number;
  shown: number;
  results: SearchResult[];
};

// The card builder's own descriptor — a small, typed slice of what
// `cardHTML` accepts, limited to the fields a search-result row actually
// fills. `cardHTML` itself stays untyped JS (defined in refonte.html); this
// type exists only so a migrated screen calls it with the right shape.
export type CardDescriptor = {
  t: string;
  k: "movie" | "show";
  s?: string;
  overview?: string;
  chip?: [string, string] | null;
  panel?: string;
};

// A media sheet, exactly as `FICHES_RAW` shapes one in refonte.html — a
// movie and a show share most fields but not all (a show carries `saisons`
// and `eps`, a movie carries `duree`), and the source stays untyped JS. A
// loose index type is the honest shape here rather than a speculative
// closed one: a component narrows the fields it actually reads.
export type MediaSheet = Record<string, unknown>;

// One YouTube trailer reference, as `trailerIds` shapes one per title.
export type Trailer = {
  key: string;
  nom: string;
  langue: string;
};

// One editable setting, as `tousLesReglages()` flattens one — the legacy
// settings-panel row (see refonte.html's `SETTINGS`) merged with the
// enclosing rubric it belongs to. `brut` / `v` stay untyped: a setting's
// raw and current value can be a string, a number, or a nested structure
// (e.g. the `disks` array), and the source never declares which.
export type Setting = {
  f: string;
  c: string;
  type: string;
  brut: unknown;
  n: string;
  v: unknown;
  note?: string;
  rubrique: Record<string, unknown>;
};

// One TVDB/TMDB candidate offered for a decision still awaiting arbitration,
// exactly as `DECISIONS_ATTENTE[].c` shapes one. `sans` marks a candidate
// with no poster at the provider (the placeholder is what says so on the
// card, never a truncating sentence); `resume` is the synopsis shown there.
export type DecisionCandidate = {
  t: string;
  y: number;
  p: string;
  id: number;
  s: number;
  sans?: boolean;
  resume?: string;
};

// The choice recorded once a decision resolves — the winning candidate's
// identity plus how it was reached: picked from the offered list, or found
// through a manual search override that bypassed that list. `via` keys
// `VIA_LABEL`.
export type DecisionChoice = {
  t: string;
  p: string;
  id: number;
  via: "pick" | "search_override";
};

// Fields common to a decision whichever side of resolution it is on — the
// folder's display name (`d`, always spelled `staging_path`-derived, never a
// medium title), its kind, the title/year the automatic pass landed on, and
// when the scrape ran. `motif` keys `MOTIF_LABEL` / `MOTIF_TON` /
// `REASON_DETAIL`.
type DecisionCommon = {
  d: string;
  k: "movie" | "show";
  t: string;
  y?: number;
  motif: string;
  quand: string;
};

// A folder still waiting on an operator's call, exactly as `DECISIONS_ATTENTE`
// shapes one. `c` is empty when the provider returned no candidate at all
// (see refonte.html's "Backrooms" row) — the other shape besides a populated
// list, never absent outright.
export type PendingDecision = DecisionCommon & { c: DecisionCandidate[] };

// A decision already settled, exactly as `DECISIONS_REGLEES` shapes one.
// `etat` keys `ETAT_DECISION` / `DECISION_STATE_DETAIL`. `choix` is present
// only for a "resolved" row — a "superseded" or "dismissed" row never
// recorded one, because no candidate was ever chosen.
export type SettledDecision = DecisionCommon & {
  etat: string;
  choix?: DecisionChoice;
};

// A queue card exactly as `BLOCKED` / `STUCK` / `STUCK_REEL` shape one — the
// source carries more fields (`s`, `chip`, `strip`, `noposter`…) than any one
// reader needs, so this stays the same loose index shape as `MediaSheet`
// rather than a speculative closed type: a caller narrows the fields it
// actually reads, starting with `t` to match against a decision's `d`.
export type QueueCard = Record<string, unknown>;

// A FOLLOW, as the world holds one: a title, its kind, its year, the status the
// acquisition engine last put it in, and — for a series — whether the show is
// still running. `fresh` is what pushes a newly-added follow to the top.
export type Follow = {
  t: string;
  k: string;
  y: number | string;
  st: string;
  serie?: string;
  fresh?: boolean;
  depuis?: string;
  recherches?: number;
};

// One GROUP of the grouped mode: its heading, its pip, and the statuses it
// gathers. A group holding several statuses keeps the chip on its cards,
// because its header cannot say which one each card carries.
export type FollowGroup = { l: string; pip: string; of: string[] };

// A library CATEGORY pill: its id, its name, the count it claims, and the
// engine's own category ids it stands for (`null` for « Tout »).
export type LibraryCategory = {
  id: string;
  l: string;
  c: number;
  of: string[] | null;
};

// A library ROW as the recent list holds one: a title and the line under it.
export type LibraryRow = { t: string; f: string };

// A show the index knows is INCOMPLETE: owned over announced, and the year
// that tells two shows of the same name apart.
export type IncompleteShow = { t: string; o: number; a: number; y: number };

// A card's FOOT, the only options `cardHTML` takes. `footAct` becomes the
// `data-act` attribute the document-level delegation reads, which is why it is
// a string and not a handler.
export type CardFoot = {
  foot?: string;
  footAct?: string;
  footSolid?: boolean;
  footTone?: string;
  footDone?: boolean;
};

// Read-only reference data + pure rendering helpers the engine's own script
// publishes once, at definition time — well before any component's module
// evaluates (see shell.tsx's boot-order comment). None of it is ever
// mutated after that publish, so a plain accessor is the right shape here,
// not a subscription: there is nothing for a component to miss by reading
// it straight, and useSyncExternalStore would just add a subscription with
// no writer ever calling it.
//
// `cardHTML` / `addVerb` are reused VERBATIM rather than re-implemented in
// JSX: a search-result card carries `data-panel="add:N"` / `data-fiche`
// attributes that the legacy document-level click delegation still reads
// to open the panel or the media sheet (the strangler seam a migrated
// screen leans on rather than replaces) — re-deriving that markup by hand
// would risk drifting the one thing that seam depends on being byte-exact.
// `render` is the legacy page redraw (`#view`, nav, deck, loaders, search
// bar) — exposed so a screen leaving a router-owned route back onto legacy
// ground (see `add.tsx`'s "Voir mes suivis") can bring that ground up to
// date the same way every other legacy navigation control already does,
// since nothing subscribes the legacy side to the store automatically.
//
// One row of a fact list, exactly as `listeFaitsHTML` reads one. `ton` is the
// operator's vocabulary (`success` / `alert` / `warning` / `info`) and the
// emitter maps it onto the stylesheet's; `cible` becomes the row's `data-*`
// attributes, which is what turns the row into the control.
export type Fact = {
  l: string;
  v?: string;
  s?: string;
  k?: string;
  ton?: string;
  etat?: string;
  cible?: Record<string, string>;
};

// One pipeline run, as `EXECUTIONS` shapes it: the question it answered, its
// verdict, its date and its result line.
export type PipelineRun = {
  q: string;
  ok: boolean;
  d: string;
  r: string;
};

// THE PIPELINE, as the page that carries its health reads it: the nine steps in
// the engine's own order, the trigger vocabulary said in words rather than in
// the engine's token, and the last run exactly as `pipeline_run` recorded it.
// A step's `faits` entry may carry nothing at all — that is the em dash the
// interface draws for « nothing to do », and it is not the same sentence as a
// step that looked and found everything already in order.
export type PipelineStep = { n: string; l: string; d: string };

export type PipelineFact = {
  n: string;
  r?: string;
  s?: string;
  bloque?: number;
};

export type Pipeline = {
  etapes: PipelineStep[];
  declencheurs: Record<string, string>;
  dernier: {
    uid: string;
    quand: string;
    duree: string;
    declencheur: string;
    issue: string;
    faits: PipelineFact[];
  };
};

// One maintenance RUBRIC — a heading and the sentence under it. The commands
// are grouped by what one wants to DO, never by the file they live in.
export type MaintenanceTopic = {
  id: string;
  t: string;
  s: string;
};

// One maintenance COMMAND. `g` is its rubric, `r` its risk (a key of `RISQUES`),
// `long` whether it can take a while, `blanc` whether it can run dry.
export type MaintenanceAction = {
  id: string;
  l: string;
  d: string;
  g: string;
  r: string;
  long?: boolean;
  blanc?: boolean;
};

// What a risk level is called and which pip colour says so. `t` is the
// operator's words; the mapping onto the chip vocabulary lives with the emitter.
export type Risk = { t: string; p: string };

// The deletion journal: how many destructive operations the library has been
// through, and the rows describing them.
export type DeletionJournal = { total: number; lignes: Fact[] };

// One settings RUBRIC — the heading one navigates BY WHAT ONE WANTS TO CHANGE,
// never by file, and the settings it holds.
export type SettingsTopic = {
  id: string;
  t: string;
  s: string;
  r: Setting[];
};

// One secret: what it is called, its key, and whether it is SET. Never its
// value — a value shown once is a value read by everything looking at the
// screen.
export type Secret = { k: string; l: string; def?: boolean };

// The settings screen's own mutable state, owned by the fragment and written by
// the document-level delegation: which rubric is open, the search text, the
// PENDING edits (a Map keyed by `reglageId`), and the three banners. A component
// READS it — it never replaces it — and re-reads on every store bump.
export type SettingsState = {
  modifs: Map<string, unknown>;
  rubrique: string | null;
  q: string;
  lectureSeule: boolean;
  redemarrage: boolean;
  conflit: boolean;
};

// The code-error summary the Système page draws as two rows.
export type CodeErrors = {
  total: number | string;
  sur: number | string;
  derniere: string;
  quoi: string;
  ou: string;
};

// EVERY MEMBER NAME BELOW IS THE SEAM: the engine publishes this object under
// these exact keys, so they stay whatever it publishes.
export type Reference = {
  RELEASES: Release[];
  RESOLUTIONS: Resolution[];
  AUDIOS: [string, string][];
  icons: Record<string, string>;
  baseTitle: (title: string) => string;
  SEARCH: SearchResults;
  // The SECOND parameter is the fragment's own, and it was missing here: a
  // card's foot is an option, not a property of the medium — `foot` is its
  // label, `footAct` the `data-act` the delegation reads, and the three others
  // decide how it looks and whether it is spent. A queue card is a looser shape
  // than a search result's descriptor (the engine's own world objects carry
  // more), so both are accepted, exactly as the fragment accepts them.
  cardHTML: (
    descriptor: CardDescriptor | QueueCard,
    options?: CardFoot,
  ) => string;
  addVerb: (result: SearchResult, index: number) => string;
  render: () => void;
  // Media-sheet data: hero banners, posters, cast portraits, trailers and
  // episode-status labels, plus the lookup/formatting helpers a sheet or a
  // season list reads them through — see refonte.html's `sheetFor` /
  // `seasonsOf` / `possedesDe` neighbourhood for the exact resolution rules
  // (title normalisation, year-suffix stripping) a re-implementation would
  // otherwise silently diverge from.
  HEROS: Record<string, string>;
  POSTERS: Record<string, string>;
  // What the Système page draws. `factRowsHTML` emits the
  // ROWS of a fact list without the `<ol class="flux">` around them, because a
  // component draws that element itself; `listeFaitsHTML` (still published, for
  // every page the fragment keeps) emits both. `skelCardsInner` / `surfErrInner`
  // are the same split for the two non-ready surfaces. The data below is
  // read-only reference, never engine state.
  listeFaitsHTML: (rows: Fact[]) => string;
  factRowsHTML: (rows: Fact[]) => string;
  // What the Arrivées page draws. `secHTML` is the section emitter the
  // acquisition page's five sections still share; a migrated page draws the `<section class="sec">` itself and
  // fills it with `secInner`, the same split as the empty and skeleton
  // surfaces. The EMPTY case (`count` of zero, or nothing inside) belongs to
  // the outer function, and a component reproduces it by drawing no section.
  secHTML: (pip: string, title: string, count: string, inner: string,
            note?: string) => string;
  secInner: (pip: string, title: string, count: string, inner: string,
             note?: string) => string;
  PIPELINE: Pipeline;
  // What the Acquisition page draws. The follow VOCABULARY — a fraction, a
  // status word, a grid badge — and the two functions that turn a cron
  // expression into a sentence. `GROUPS` is the grouped mode's own order, and
  // `URGENCY` the order a list sorts by; `ST_TONE` maps a status to its chip
  // tone. All of it is the page's language, not the engine's state.
  stFraction: (follow: Follow) => string | null;
  stLabel: (follow: Follow) => string;
  gridBadge: (follow: Follow) => { tone: string; text?: string } | null;
  cadenceFR: (cron: string) => string;
  nextSearchFR: (cron: string, now: Date) => string | null;
  ST_TONE: Record<string, string>;
  URGENCY: Record<string, number>;
  GROUPS: FollowGroup[];
  CADENCE_CRON: string;
  derivedFollows: () => Follow[];
  // The one account this server has, and the escaper the fragment's emitters
  // use — a page that hands a string of markup to one of them escapes exactly
  // what the legacy escaped.
  COMPTE: { nom: string; mail: string };
  escapeHtml: (text: string) => string;
  // The suggestion machinery. It stays the FRAGMENT's — the deck's gesture
  // mutates its own DOM and a replaced node cannot animate — and a migrated
  // page asks it to fill the containers React has just drawn.
  fillSug: () => void;
  sugFoot: () => void;
  mountDeck: () => void;
  deckHTML: () => string;
  // What the Médiathèque draws. `tileHTML` and `swipeHTML` are called VERBATIM
  // for the same reason as `cardHTML` — the rows they emit carry the `data-*`
  // the document-level delegation reads. `sousLigne` is the line under a tile's
  // title; `opts.index` is what selection mode addresses a tile by.
  tileHTML: (
    descriptor: CardDescriptor | QueueCard,
    subLine?: string,
    options?: {
      index?: number;
      // `null` and absent both mean « no badge » — `gridBadge` answers `null`,
      // and the fragment reads the option for truthiness.
      badge?: { tone: string; text?: string } | null;
      muted?: boolean;
    },
  ) => string;
  // THREE arguments, as the fragment declares it: the row, the actions revealed
  // on one side, and — for a follow that can be searched again — the action on
  // the other.
  swipeHTML: (inner: string, actions: string, other?: string) => string;
  CATS: LibraryCategory[];
  RECENT: LibraryRow[];
  INCOMPLETE: IncompleteShow[];
  SYNOPSIS: Record<string, string>;
  // The page size the count line and the infinite scroll both speak in.
  LIB_PAGE: number;
  libRowHTML: (item: LibraryRow | QueueCard, index: number) => string;
  libFiltered: () => (LibraryRow | QueueCard)[];
  // The selection bar lives in `#device` and stays the FRAGMENT's: a component
  // asks for a repaint after it draws, exactly where `fillLib` asked for one.
  paintSelBar: () => void;
  // How many titles the prototype really carries — the number the end mark
  // says out loud.
  libraryLoaded: () => number;
  // Every sort, in both directions, each with its own name — the table E-001
  // made two-dimensional. A rule reads the NAMES from here rather than
  // restating them.
  TRIS: Record<string, { normal: string; inverse: string }>;
  skelCards: (count: number) => string;
  skelCardsInner: (count: number) => string;
  surfErr: (subject: string) => string;
  surfErrInner: (subject: string) => string;
  SERVICES: Fact[];
  SERVICES_PANNE: Fact[];
  SCHEDULERS: Fact[];
  SCHEDULERS_DOWN: Fact[];
  EXECUTIONS: PipelineRun[];
  DISKS: Fact[];
  INDEX: Fact[];
  DEPENDENCIES: Fact[];
  ERRORS: CodeErrors;
  MAINT_TOPICS: MaintenanceTopic[];
  MAINT_ACTIONS: MaintenanceAction[];
  SETTINGS: SettingsTopic[];
  REG_ETAT: SettingsState;
  SECRETS: Secret[];
  emptyInner: (title: string, body: string) => string;
  chipHTML: (chip: [string, string] | null | undefined) => string;
  valeurCourante: (setting: Setting) => unknown;
  fileName: (file: string) => string;
  changedFiles: () => string[];
  RISQUES: Record<string, Risk>;
  JOURNAL: DeletionJournal;
  CAST: Record<string, string>;
  trailerIds: Record<string, Trailer>;
  EP_LABEL: Record<string, string>;
  sheetFor: (titre: string) => MediaSheet | null;
  seasonsOf: (titre: string) => [number, number | null, number][];
  possedesDe: (titre: string, saison: number) => Set<number> | null;
  plages: (nums: number[]) => string;
  initials: (nom: string) => string;
  // `dateFR` returns null on a falsy `iso`, exactly like `sheetFor` on an
  // unresolved title — a sheet's air dates are frequently unset (an
  // announced-but-unaired episode) and the caller decides what to show.
  dateFR: (iso: string) => string | null;
  AUJOURDHUI: string;
  svgIcon: (paths: string, strokeWidth?: number) => string;
  // Réglages (settings) panel actions — read the full setting list, derive
  // a setting's storage id, coerce a raw field input back to its stored
  // type, and apply/open a pending edit. See refonte.html's `SETTINGS`
  // neighbourhood for the file/rubric structure `Setting.rubrique` carries.
  tousLesReglages: () => Setting[];
  reglageId: (reglage: Setting) => string;
  // The value a field must DRAW: the pending edit when there is one, the
  // file's `brut` otherwise. The pending-edit overlay itself stays private to
  // the engine — this returns the value, never the map.
  valeurEnCours: (reglage: Setting) => unknown;
  typedValue: (reglage: Setting, texte: string) => unknown;
  modifierReglage: (id: string, valeur: unknown) => void;
  openSetting: (id: string) => void;
  // The arbitration flow — decisions the scrape could not make on its own,
  // spelled out for a folder rather than a medium. `DECISIONS_ATTENTE` /
  // `DECISIONS_REGLEES` are the mock's twelve rows of `scrape_decision` (ten
  // réglées, two en attente), split by whether an operator has answered yet.
  DECISIONS_ATTENTE: PendingDecision[];
  DECISIONS_REGLEES: SettledDecision[];
  MOTIF_LABEL: Record<string, string>;
  MOTIF_TON: Record<string, string>;
  REASON_DETAIL: Record<string, string>;
  // Unlike the other label maps here, each value is a [tone, label] pair —
  // the same shape a chip carries — not a bare string: `ETAT_DECISION`
  // supplies both the chip's tone and its text in one lookup.
  ETAT_DECISION: Record<string, [string, string]>;
  DECISION_STATE_DETAIL: Record<string, string>;
  VIA_LABEL: Record<string, string>;
  // `cible` is `state.resolveTarget`, which is `string | null` (see this
  // module's `UiState`-cast comment below); a target absent from
  // `DECISIONS_ATTENTE` — already resolved, or never a decision at all —
  // answers `null` rather than throwing.
  decisionEnAttente: (cible: string | null) => PendingDecision | null;
  // Thin arrows over `derived.blocked` / `derived.stuck`, published so the
  // FUNCTION REFERENCE stays stable across renders while the value each call
  // returns stays live — a component can pass these to a hook that expects a
  // stable selector without ever seeing a stale snapshot.
  derivedBlocked: () => QueueCard[];
  derivedStuck: () => QueueCard[];
  derivedMoving: () => QueueCard[];
  derivedSettled: () => QueueCard[];
  derivedTakeable: () => QueueCard[];
  derivedInflight: () => QueueCard[];
  derivedNotfound: () => QueueCard[];
  derivedDoneToday: () => QueueCard[];
  // Agreeing with the machine (`actionLeave`) or with a candidate
  // (`actionResoudre`, `choix` the chosen title when the operator picked
  // one) both remove the folder from wherever it is queued and hand it back
  // to the pipeline; `actionRecuperer` restarts a takeable item instead.
  // Each toasts and re-renders on success; `actionLeave` also reports
  // whether the folder was found at all.
  actionResoudre: (titre: string, choix?: string) => void;
  actionLeave: (titre: string) => boolean;
  actionRecuperer: (titre: string) => void;
  toast: (msg: string) => void;
  posterBox: (
    title: string,
    kind?: "movie" | "show",
    opts?: { exact?: boolean },
  ) => string;
};

// `etat.resolveTarget` (the folder currently open on the resolution screen)
// and `etat.relTitre` (the item a "Récupérer" gesture targets) are both
// `string | null` at runtime. `UiState` itself stays the loose
// `{ [key: string]: unknown }` shape (see store.ts) — a reader casts at the
// point of use, exactly as `add.tsx` already does for `resolveTarget`.

// The shell's bottom-panel API — what a legacy producer calls instead of the
// dead `openSheet(html)`. `ouverte()` answers from the STORE, never from the
// DOM: a legacy caller asks mid-task ("is a layer up before I open a screen?")
// and the store is already right at that instant, whatever React has committed.
// The three member names are the seam the fragment calls by.
export type Panel = {
  ouvrir: (descripteur: PanelDescriptor) => void;
  // `pop` mirrors the legacy `closeSheet(pop)`: truthy means the history entry
  // is ALREADY being popped, so the layer must not unwind one of its own.
  fermer: (pop?: boolean) => void;
  ouverte: () => boolean;
};

declare global {
  interface Window {
    __referentiel: Reference;
    __panneau: Panel;
    // The engine's own multi-layer closer, published by refonte.html: the
    // scrim covers the drawer, the dialog and the sheet alike, and a tap on it
    // closes whichever is up. Optional for the same reason
    // `__demarrerMoteur` is — a document served without the fragment must
    // fail visibly, not here.
    __fermerCouches?: () => void;
  }
}

export function useReference(): Reference {
  return window.__referentiel;
}
