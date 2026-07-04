/**
 * ``usePwa`` — the app's PWA lifecycle hook (tm-shell §5.4).
 *
 * One hook owning the two PWA concerns the DESIGN mandates, mounted **once**
 * (see ``App.tsx``'s ``PwaLayer``) and its state fanned out to the presentational
 * {@link UpdateToast} / {@link InstallBanner}:
 *
 * **Auto-update (all installs converge, no stale clients).**
 * Wraps ``vite-plugin-pwa``'s ``useRegisterSW``. The service worker is asked to
 * check for a new build on load, on every ``visibilitychange`` back to visible,
 * and every 15 min. Independently, ``GET /api/version`` is polled every 5 min
 * (only while the tab is visible and the session is authenticated) and its
 * ``build_commit`` compared to the baked {@link __BUILD_COMMIT__}; any mismatch
 * forces an extra ``registration.update()``. A fresh SW (7.1 bakes
 * ``skipWaiting`` + ``clients.claim``) flips ``needRefresh`` → the toast informs
 * and {@link PwaState.applyUpdate} reloads onto it (guarded to a single reload).
 *
 * **Install proposal.** ``beforeinstallprompt`` is captured (Android/desktop) so
 * an in-app button can trigger the native prompt; iOS Safari (no such event) is
 * detected so the UI can show the manual *Partager → écran d'accueil* path. A
 * dismissal is remembered in ``localStorage`` so the app stops nagging.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { useQuery } from "@tanstack/react-query";
import { useRegisterSW } from "virtual:pwa-register/react";

import { getVersion } from "@/api/client";
import { telemetryKeys } from "@/hooks/useHealth";

/** ``localStorage`` key remembering the user dismissed the install prompt. */
export const INSTALL_DISMISSED_STORAGE_KEY = "torrentmate:install_dismissed";

/** SW update-check cadence, in ms (DESIGN §5.4: every 15 min). */
const SW_UPDATE_INTERVAL_MS = 15 * 60 * 1000;

/** ``/api/version`` poll cadence, in ms (DESIGN §5.4: ~5 min, visible only). */
const VERSION_POLL_INTERVAL_MS = 5 * 60 * 1000;

/** Sentinel commit for an unstamped build — never used to force an update. */
const DEV_COMMIT = "dev";

/**
 * The ``beforeinstallprompt`` event — Chromium-only, absent from ``lib.dom``.
 *
 * Attributes:
 *   platforms: The platforms the prompt can target.
 *   userChoice: Resolves once the user accepts or dismisses the native prompt.
 *   prompt: Shows the browser's install prompt (usable once).
 */
interface BeforeInstallPromptEvent extends Event {
  readonly platforms: readonly string[];
  readonly userChoice: Promise<{
    readonly outcome: "accepted" | "dismissed";
    readonly platform: string;
  }>;
  prompt: () => Promise<void>;
}

/** ``Navigator`` augmented with Safari's non-standard ``standalone`` flag. */
interface IosNavigator extends Navigator {
  readonly standalone?: boolean;
}

/** Options for {@link usePwa}. */
export interface UsePwaOptions {
  /**
   * Whether to poll ``/api/version``. Gate this on the authenticated session:
   * the endpoint is auth-guarded, so polling it while logged out only yields
   * 401 noise (and would trip the global redirect on the login page).
   */
  readonly versionPollEnabled: boolean;
  /**
   * The build commit to compare the server against. Defaults to the
   * Vite-baked {@link __BUILD_COMMIT__}; overridable so tests can exercise the
   * mismatch path without a real build stamp.
   */
  readonly bakedCommit?: string;
}

/** The reactive PWA state consumed by the update/install UI. */
export interface PwaState {
  /** ``true`` once a new service worker is installed and waiting. */
  readonly needRefresh: boolean;
  /** Activate the waiting SW and reload the page (single-shot, no loop). */
  readonly applyUpdate: () => void;
  /** ``true`` when the native install prompt is available and not dismissed. */
  readonly canInstall: boolean;
  /** Show the captured native install prompt (Android/desktop). */
  readonly promptInstall: () => Promise<void>;
  /** ``true`` for iOS Safari (tab, not installed): show the manual instruction. */
  readonly isIosInstall: boolean;
  /** Remember the user dismissed the install proposal (both platforms). */
  readonly dismissInstall: () => void;
}

/**
 * Decide whether a baked/served commit pair should force a SW update check.
 *
 * Args:
 *   baked: The commit compiled into this bundle ({@link __BUILD_COMMIT__}).
 *   served: The commit reported by ``/api/version`` (``undefined`` before the
 *     first poll resolves).
 *
 * Returns:
 *   ``true`` only when both commits are real, stamped, and differ — i.e. the
 *   server has been redeployed since this bundle was built. Any ``"dev"`` /
 *   empty / equal case yields ``false``.
 */
export function shouldForceUpdate(
  baked: string,
  served: string | undefined,
): boolean {
  if (
    baked === DEV_COMMIT ||
    served === undefined ||
    served === "" ||
    served === DEV_COMMIT
  ) {
    return false;
  }
  return baked !== served;
}

/** ``true`` when running as an installed standalone PWA (either platform). */
function isStandalone(): boolean {
  // `matchMedia` is typed as always present, but jsdom (and some older
  // WebViews) omit it — read it through an optional-typed view so the runtime
  // guard is honest rather than an "unnecessary" optional chain.
  const matchMedia = (
    window as unknown as {
      matchMedia?: (query: string) => MediaQueryList;
    }
  ).matchMedia;
  const displayStandalone =
    matchMedia?.("(display-mode: standalone)").matches ?? false;
  const nav = window.navigator as IosNavigator;
  return displayStandalone || nav.standalone === true;
}

/** ``true`` for iOS Safari in a normal tab (install = manual Share sheet). */
function detectIosSafari(): boolean {
  const nav = window.navigator as IosNavigator;
  if (!/iP(?:hone|ad|od)/.test(nav.userAgent)) {
    return false;
  }
  return !isStandalone();
}

/** Read the persisted install-dismissed flag, tolerating blocked storage. */
function readInstallDismissed(): boolean {
  try {
    return window.localStorage.getItem(INSTALL_DISMISSED_STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

/** Persist the install-dismissed flag, tolerating blocked storage. */
function writeInstallDismissed(): void {
  try {
    window.localStorage.setItem(INSTALL_DISMISSED_STORAGE_KEY, "1");
  } catch {
    // Storage blocked (private mode / quota) — the banner simply reappears next
    // load; not worth surfacing.
  }
}

/**
 * Manage the PWA update + install lifecycle.
 *
 * Args:
 *   options: See {@link UsePwaOptions}.
 *
 * Returns:
 *   The reactive {@link PwaState}. Mount this hook exactly once at the app root.
 */
export function usePwa(options: UsePwaOptions): PwaState {
  const { versionPollEnabled, bakedCommit = __BUILD_COMMIT__ } = options;

  // Handle to the live SW registration, captured on register; used to trigger
  // update checks from the periodic timer and the version-mismatch path.
  const registrationRef = useRef<ServiceWorkerRegistration | null>(null);

  const {
    needRefresh: [needRefresh],
    updateServiceWorker,
  } = useRegisterSW({
    onRegisteredSW: (_swScriptUrl, registration) => {
      if (registration === undefined) {
        return;
      }
      registrationRef.current = registration;
      // On-load check: ask the browser right away whether a newer SW exists.
      void registration.update();
    },
  });

  // Periodic + visibility-driven update checks (DESIGN §5.4). The on-load check
  // lives in `onRegisteredSW`; here we cover the 15 min cadence and every
  // return-to-foreground so a long-lived tab converges without a manual reload.
  useEffect(() => {
    const triggerUpdate = (): void => {
      void registrationRef.current?.update();
    };
    const onVisibilityChange = (): void => {
      if (document.visibilityState === "visible") {
        triggerUpdate();
      }
    };
    const interval = window.setInterval(triggerUpdate, SW_UPDATE_INTERVAL_MS);
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, []);

  // A single reload only: `updateServiceWorker(true)` reloads on the SW's
  // `controllerchange`; guard against a double invocation ever looping.
  const reloadedRef = useRef(false);
  const applyUpdate = useCallback((): void => {
    if (reloadedRef.current) {
      return;
    }
    reloadedRef.current = true;
    void updateServiceWorker(true);
  }, [updateServiceWorker]);

  // Secondary update trigger: poll `/api/version` and force a SW update check
  // when the served commit no longer matches the one baked into this bundle.
  const versionQuery = useQuery({
    queryKey: telemetryKeys.version,
    queryFn: getVersion,
    enabled: versionPollEnabled,
    // `refetchIntervalInBackground` defaults to false, so the poll naturally
    // pauses while the tab is hidden — "every 5 min while visible".
    refetchInterval: VERSION_POLL_INTERVAL_MS,
  });
  const servedCommit = versionQuery.data?.build_commit;
  useEffect(() => {
    if (shouldForceUpdate(bakedCommit, servedCommit)) {
      void registrationRef.current?.update();
    }
  }, [bakedCommit, servedCommit]);

  // Install proposal: capture `beforeinstallprompt` for the in-app button, and
  // detect iOS Safari (which never fires it) for the manual instruction.
  const promptEventRef = useRef<BeforeInstallPromptEvent | null>(null);
  const [canPrompt, setCanPrompt] = useState(false);
  const [dismissed, setDismissed] = useState<boolean>(() =>
    readInstallDismissed(),
  );
  const [iosInstall] = useState<boolean>(() => detectIosSafari());

  useEffect(() => {
    const onBeforeInstallPrompt = (event: Event): void => {
      // Suppress Chrome's default mini-infobar; the app surfaces its own banner.
      event.preventDefault();
      promptEventRef.current = event as BeforeInstallPromptEvent;
      setCanPrompt(true);
    };
    const onAppInstalled = (): void => {
      promptEventRef.current = null;
      setCanPrompt(false);
    };
    window.addEventListener("beforeinstallprompt", onBeforeInstallPrompt);
    window.addEventListener("appinstalled", onAppInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onBeforeInstallPrompt);
      window.removeEventListener("appinstalled", onAppInstalled);
    };
  }, []);

  const promptInstall = useCallback(async (): Promise<void> => {
    const event = promptEventRef.current;
    if (event === null) {
      return;
    }
    // The captured event is single-use — clear it and hide the button whatever
    // the user chooses (a re-prompt needs a fresh `beforeinstallprompt`).
    promptEventRef.current = null;
    setCanPrompt(false);
    await event.prompt();
  }, []);

  const dismissInstall = useCallback((): void => {
    writeInstallDismissed();
    setDismissed(true);
    setCanPrompt(false);
    promptEventRef.current = null;
  }, []);

  return {
    needRefresh,
    applyUpdate,
    canInstall: canPrompt && !dismissed,
    promptInstall,
    isIosInstall: iosInstall && !dismissed,
    dismissInstall,
  };
}
