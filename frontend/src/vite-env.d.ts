/// <reference types="vite/client" />
/// <reference types="vite-plugin-pwa/client" />
/// <reference types="vite-plugin-pwa/react" />

/**
 * Build-time git SHA baked into the bundle by Vite's `define` (see
 * `vite.config.ts`). The deploy script exports `TM_BUILD_COMMIT` before
 * `npm run build`; local/dev builds and Vitest fall back to the literal
 * `"dev"`, which `usePwa` treats as "unstamped" (never forces an update).
 */
declare const __BUILD_COMMIT__: string;
