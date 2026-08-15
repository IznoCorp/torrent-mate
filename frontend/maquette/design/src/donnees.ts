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

// Read-only reference data + pure rendering helpers the engine's own script
// publishes once, at definition time — well before any component's module
// evaluates (see coquille.tsx's boot-order comment). None of it is ever
// mutated after that publish, so a plain accessor is the right shape here,
// not a subscription: there is nothing for a component to miss by reading
// it straight, and useSyncExternalStore would just add a subscription with
// no writer ever calling it.
export type Referentiel = {
  RELEASES: Release[];
  RESOS: Resolution[];
  AUDIOS: [string, string][];
  icons: Record<string, string>;
  baseTitle: (title: string) => string;
};

declare global {
  interface Window {
    __referentiel: Referentiel;
  }
}

export function useReferentiel(): Referentiel {
  return window.__referentiel;
}
