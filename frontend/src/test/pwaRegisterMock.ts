/**
 * Inert runtime stub for the `virtual:pwa-register/react` virtual module.
 *
 * Wired via `test.alias` in `vite.config.ts` so Vitest resolves the otherwise
 * build-only virtual module to this file instead of failing. It registers no
 * service worker, keeps `needRefresh` permanently false, and resolves
 * `updateServiceWorker` without reloading — everything jsdom cannot do.
 *
 * Tests that need to *drive* the registration/update flow (e.g.
 * `usePwa.test.tsx`) replace this stub with a controllable `vi.mock(
 * 'virtual:pwa-register/react', …)`; every other test that merely mounts the
 * shell (`App.test.tsx`) gets this harmless no-op.
 */

/** Subset of vite-plugin-pwa's `RegisterSWOptions` the app actually passes. */
export interface RegisterSWOptions {
  readonly immediate?: boolean;
  readonly onRegisteredSW?: (
    swScriptUrl: string,
    registration: ServiceWorkerRegistration | undefined,
  ) => void;
  readonly onNeedRefresh?: () => void;
  readonly onOfflineReady?: () => void;
  readonly onRegisterError?: (error: unknown) => void;
}

/** The reactive handle shape returned by the real `useRegisterSW`. */
export interface RegisterSWReturn {
  readonly needRefresh: readonly [boolean, (value: boolean) => void];
  readonly offlineReady: readonly [boolean, (value: boolean) => void];
  readonly updateServiceWorker: (reloadPage?: boolean) => Promise<void>;
}

/**
 * Inert `useRegisterSW` — mirrors the real hook's return shape but does nothing.
 *
 * Any {@link RegisterSWOptions} the caller passes are ignored (the parameter is
 * omitted; JS drops the extra argument), so no service worker is registered.
 *
 * Returns:
 *   A handle whose `needRefresh`/`offlineReady` stay false and whose
 *   `updateServiceWorker` resolves immediately.
 */
export function useRegisterSW(): RegisterSWReturn {
  return {
    needRefresh: [false, () => undefined],
    offlineReady: [false, () => undefined],
    updateServiceWorker: () => Promise.resolve(),
  };
}
