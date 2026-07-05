/**
 * Environment detection shared across the UI.
 *
 * Staging is identified by host: the prod and staging origins differ
 * (`tm-staging.iznogoudatall.xyz` / the loopback staging port `8711`). Kept in
 * one place so the {@link StagingBanner}, the in-app logo, and the PWA identity
 * all agree on what "staging" means. Mirrors KanbanMate's `web/src/lib/env.ts`.
 */

/**
 * Whether the app is running on the staging instance.
 *
 * Detection is host-based (never a build-time flag) so the SAME built bundle is
 * served on prod and staging — only the origin decides. Prod stays the default
 * when detection cannot run (SSR / no `window`).
 *
 * @returns ``true`` on the staging host or the loopback staging port.
 */
export function isStaging(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  const host = window.location.hostname || "";
  return /staging/i.test(host) || window.location.port === "8711";
}

/**
 * The brand/app icon for the current environment.
 *
 * The cyan-liseret staging variant on staging so the whole interface reads as
 * STAGING; the amber production mark everywhere else. The NAME stays
 * "TorrentMate" in both — prod and staging are told apart by the logo alone.
 */
export const BRAND_ICON: string = isStaging() ? "/icon-staging.svg" : "/icon.svg";
