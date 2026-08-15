// The single owner of the mutable state. The legacy engine receives this
// through the boot handshake and keeps a synchronous read alias; React reads
// through the domain hooks. `version` exists because the simulated WORLD is
// mutated in place by the engine's actions — a bump is how a change that did
// not replace any reference still reaches every subscriber.
import { Store } from "@tanstack/store";

export type EtatUI = { page: string; [cle: string]: unknown };
export type Contenu = { etat: EtatUI; monde: unknown; version: number };

export type Magasin = {
  store: Store<Contenu>;
  lire(): Contenu;
  ecrire(patch: Partial<EtatUI>): void;
  adopterEtat(initial: EtatUI): void;
  adopterMonde(monde: unknown): void;
  toucher(): void;
};

export function creerMagasin(): Magasin {
  const store = new Store<Contenu>({
    etat: { page: "acq" },
    monde: null,
    version: 0,
  });
  return {
    store,
    lire: () => store.state,
    ecrire: (patch) =>
      store.setState((prev) => ({
        ...prev,
        etat: { ...prev.etat, ...patch },
        version: prev.version + 1,
      })),
    adopterEtat: (initial) =>
      store.setState((prev) => ({
        ...prev,
        etat: initial,
        version: prev.version + 1,
      })),
    adopterMonde: (monde) =>
      store.setState((prev) => ({ ...prev, monde, version: prev.version + 1 })),
    toucher: () =>
      store.setState((prev) => ({ ...prev, version: prev.version + 1 })),
  };
}
