// Environment detection shared across the UI. Staging is identified by host (the prod and staging
// origins differ: km-staging.* / the loopback :8797). Kept in one place so the StagingBanner, the
// in-app logo, and the PWA identity all agree on what "staging" means.
export function isStaging() {
  if (typeof window === "undefined") return false;
  const host = window.location.hostname || "";
  return /staging/i.test(host) || window.location.port === "8797";
}

// The app/brand icon for the current environment: the dev (amber-liseret) variant on staging so the
// whole interface reads as DEV, the green production logo everywhere else.
export const BRAND_ICON = isStaging() ? "/icon-staging.svg" : "/icon.svg";
