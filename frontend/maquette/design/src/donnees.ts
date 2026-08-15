// design/src/donnees.ts
// The domain hooks are the single door between components and the store.
// Their IMPLEMENTATION is what the backend-binding mission will replace;
// components must never reach around them to the store or the engine.
import { useSyncExternalStore } from "react";
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
};

declare global {
  interface Window {
    __referentiel: Referentiel;
  }
}

export function useReferentiel(): Referentiel {
  return window.__referentiel;
}
