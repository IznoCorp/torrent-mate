// The single owner of the mutable state. The legacy engine receives this
// through the boot handshake and keeps a synchronous read alias; React reads
// through the domain hooks. `version` exists because the simulated WORLD is
// mutated in place by the engine's actions — a bump is how a change that did
// not replace any reference still reaches every subscriber.
//
// The library's own `Store` is imported under an alias: the type this module
// exports IS the store as the rest of the code speaks of it, and the vendor
// class is only the container it holds.
import { Store as TanStackStore } from "@tanstack/store";

export type UiState = { page: string; [key: string]: unknown };
export type StoreContent = { etat: UiState; monde: unknown; version: number };

// MEMBER NAMES ARE THE SEAM: the legacy fragment calls `lire`, `ecrire`,
// `adopterEtat`, `adopterMonde`, `toucher` and reads `store` by those exact
// names, and `lire().etat` is the alias its own `state` is refreshed from.
// They stay whatever the fragment says they are.
export type Store = {
  store: TanStackStore<StoreContent>;
  lire(): StoreContent;
  ecrire(patch: Partial<UiState>): void;
  adopterEtat(initial: UiState): void;
  adopterMonde(world: unknown): void;
  toucher(): void;
};

export function createStore(): Store {
  const store = new TanStackStore<StoreContent>({
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
