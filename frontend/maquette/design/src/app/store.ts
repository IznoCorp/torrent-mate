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
export type StoreContent = { state: UiState; world: unknown; version: number };

// MEMBER NAMES ARE THE SEAM: the legacy fragment calls `read`, `write`,
// `adoptState`, `adoptWorld`, `touch` and reads `store` by those exact
// names, and `read().etat` is the alias its own `state` is refreshed from.
// They stay whatever the fragment says they are.
export type Store = {
  store: TanStackStore<StoreContent>;
  read(): StoreContent;
  write(patch: Partial<UiState>): void;
  adoptState(initial: UiState): void;
  adoptWorld(world: unknown): void;
  touch(): void;
};

export function createStore(): Store {
  const store = new TanStackStore<StoreContent>({
    state: { page: "acq" },
    world: null,
    version: 0,
  });
  return {
    store,
    read: () => store.state,
    write: (patch) =>
      store.setState((prev) => ({
        ...prev,
        state: { ...prev.state, ...patch },
        version: prev.version + 1,
      })),
    adoptState: (initial) =>
      store.setState((prev) => ({
        ...prev,
        state: initial,
        version: prev.version + 1,
      })),
    adoptWorld: (world) =>
      store.setState((prev) => ({ ...prev, world, version: prev.version + 1 })),
    touch: () =>
      store.setState((prev) => ({ ...prev, version: prev.version + 1 })),
  };
}
