// design/src/donnees.ts
// The domain hooks are the single door between components and the store.
// Their IMPLEMENTATION is what the backend-binding mission will replace;
// components must never reach around them to the store or the engine.
import { useSyncExternalStore } from "react";
import type { Descripteur } from "./composants/panneau";
import type { Contenu, EtatUI } from "./magasin";

function sabonner(rappel: () => void): () => void {
  const subscription = window.__magasin.store.subscribe(rappel);
  return () => subscription.unsubscribe();
}

export function useContenu<T>(selection: (c: Contenu) => T): T {
  // `version` bumps on every write INCLUDING in-place world mutations, so a
  // selector over a mutated-in-place object still re-reads: the snapshot the
  // comparison sees is the selected value, re-derived per notification.
  return useSyncExternalStore(sabonner, () =>
    selection(window.__magasin.lire()),
  );
}

export const useEtat = (): EtatUI => useContenu((c) => c.etat);
export const useMonde = (): unknown => useContenu((c) => c.monde);

// The single write door, matching the read side above: a component patches
// the store through THIS function, never through `window.__magasin.ecrire`
// directly — the binding mission replaces this function's implementation
// (and only this one) when the real store arrives, exactly as it replaces
// `useReferentiel()`'s below. `window.__magasin.ecrire` stays the actual
// primitive underneath because the still-legacy call sites (refonte.html)
// have no hook to go through; a component reaching around this accessor is
// what would make that replacement touch component code too.
export function ecrireEtat(patch: Partial<EtatUI>): void {
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
export type ResultatRecherche = {
  t: string;
  y: string;
  k: "Film" | "Série";
  ov: string;
  owned: boolean;
  followed: boolean;
};

export type ResultatsRecherche = {
  total: number;
  shown: number;
  results: ResultatRecherche[];
};

// The card builder's own descriptor — a small, typed slice of what
// `cardHTML` accepts, limited to the fields a search-result row actually
// fills. `cardHTML` itself stays untyped JS (defined in refonte.html); this
// type exists only so a migrated screen calls it with the right shape.
export type DescripteurCarte = {
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
export type Fiche = Record<string, unknown>;

// One YouTube trailer reference, as `trailerIds` shapes one per title.
export type Trailer = {
  key: string;
  nom: string;
  langue: string;
};

// One editable setting, as `tousLesReglages()` flattens one — the legacy
// settings-panel row (see refonte.html's `REGLAGES`) merged with the
// enclosing rubric it belongs to. `brut` / `v` stay untyped: a setting's
// raw and current value can be a string, a number, or a nested structure
// (e.g. the `disks` array), and the source never declares which.
export type Reglage = {
  f: string;
  c: string;
  type: string;
  brut: unknown;
  n: string;
  v: unknown;
  note?: string;
  rubrique: Record<string, unknown>;
};

// Read-only reference data + pure rendering helpers the engine's own script
// publishes once, at definition time — well before any component's module
// evaluates (see coquille.tsx's boot-order comment). None of it is ever
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
// ground (see `ajout.tsx`'s "Voir mes suivis") can bring that ground up to
// date the same way every other legacy navigation control already does,
// since nothing subscribes the legacy side to the store automatically.
export type Referentiel = {
  RELEASES: Release[];
  RESOS: Resolution[];
  AUDIOS: [string, string][];
  icons: Record<string, string>;
  baseTitle: (title: string) => string;
  SEARCH: ResultatsRecherche;
  cardHTML: (descriptor: DescripteurCarte) => string;
  addVerb: (result: ResultatRecherche, index: number) => string;
  render: () => void;
  // Media-sheet data: hero banners, posters, cast portraits, trailers and
  // episode-status labels, plus the lookup/formatting helpers a sheet or a
  // season list reads them through — see refonte.html's `sheetFor` /
  // `saisonsDe` / `possedesDe` neighbourhood for the exact resolution rules
  // (title normalisation, year-suffix stripping) a re-implementation would
  // otherwise silently diverge from.
  HEROS: Record<string, string>;
  POSTERS: Record<string, string>;
  ACTEURS: Record<string, string>;
  trailerIds: Record<string, Trailer>;
  EP_LABEL: Record<string, string>;
  sheetFor: (titre: string) => Fiche | null;
  saisonsDe: (titre: string) => [number, number | null, number][];
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
  // type, and apply/open a pending edit. See refonte.html's `REGLAGES`
  // neighbourhood for the file/rubric structure `Reglage.rubrique` carries.
  tousLesReglages: () => Reglage[];
  reglageId: (reglage: Reglage) => string;
  // The value a field must DRAW: the pending edit when there is one, the
  // file's `brut` otherwise. The pending-edit overlay itself stays private to
  // the engine — this returns the value, never the map.
  valeurEnCours: (reglage: Reglage) => unknown;
  valeurSaisie: (reglage: Reglage, texte: string) => unknown;
  modifierReglage: (id: string, valeur: unknown) => void;
  ouvrirReglage: (id: string) => void;
};

// The shell's bottom-panel API — what a legacy producer calls instead of the
// dead `openSheet(html)`. `ouverte()` answers from the STORE, never from the
// DOM: a legacy caller asks mid-task ("is a layer up before I open a screen?")
// and the store is already right at that instant, whatever React has committed.
export type Panneau = {
  ouvrir: (descripteur: Descripteur) => void;
  // `pop` mirrors the legacy `closeSheet(pop)`: truthy means the history entry
  // is ALREADY being popped, so the layer must not unwind one of its own.
  fermer: (pop?: boolean) => void;
  ouverte: () => boolean;
};

declare global {
  interface Window {
    __referentiel: Referentiel;
    __panneau: Panneau;
    // The engine's own multi-layer closer, published by refonte.html: the
    // scrim covers the drawer, the dialog and the sheet alike, and a tap on it
    // closes whichever is up. Optional for the same reason
    // `__demarrerMoteur` is — a document served without the fragment must
    // fail visibly, not here.
    __fermerCouches?: () => void;
  }
}

export function useReferentiel(): Referentiel {
  return window.__referentiel;
}
