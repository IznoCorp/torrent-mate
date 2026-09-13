// The single door between a component and the store.
//
// Its IMPLEMENTATION is what the backend-binding mission will replace;
// components must never reach around it to the store or to the engine.
//
// It knows no domain and renders nothing, which is what puts it here rather
// than with a feature — and what keeps it out of the fan-in ceiling by that
// guard's own wording. It used to sit in the module that also held a hundred
// and eight reference members and thirty domain types, which is how seventeen
// of twenty-five modules came to import one file.
import { useSyncExternalStore } from "react";
import type { Store, StoreContent, UiState } from "../app/store";

/* THE STORE ITSELF, for code that is not a component — a verb, a host, a
   producer. The boot creates it and hands it here once; an ES export is a live
   binding, so a caller reads the filled value at call time. The harness
   publishes the same object as `window.__store`. */
export let store: Store;

/**
 * Hands the boot's store to every caller that is not a component.
 *
 * @param created The store the boot created.
 */
export function installStore(created: Store): void {
  store = created;
}

function subscribe(callback: () => void): () => void {
  const subscription = store.store.subscribe(callback);
  return () => subscription.unsubscribe();
}

export function useStoreContent<T>(select: (c: StoreContent) => T): T {
  // `version` bumps on every write INCLUDING in-place world mutations, so a
  // selector over a mutated-in-place object still re-reads: the snapshot the
  // comparison sees is the selected value, re-derived per notification.
  return useSyncExternalStore(subscribe, () => select(store.read()));
}

export const useUiState = (): UiState => useStoreContent((c) => c.state);

// The single write door, matching the read side above: a component patches
// the store through THIS function, never through `store.write`
// directly — the binding mission replaces this function's implementation
// (and only this one) when the real store arrives. `store.write`
// stays the actual primitive underneath because the still-legacy call sites
// have no hook to go through; a component reaching around this accessor is
// what would make that replacement touch component code too.
export function writeUiState(patch: Partial<UiState>): void {
  store.write(patch);
}
