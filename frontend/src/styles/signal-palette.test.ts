/**
 * Guard: no two acquisition status chips may read as the same colour.
 *
 * The operator has flagged this twice. Ticket 24 moved « Non vérifié » off the
 * grey it shared with « En attente » onto an info-blue tint — which put it on
 * the very hue of « En cours d'acquisition ». The fix for that gave « En
 * attente de torrent » a teal, which left green / teal / blue reading as one
 * family — the second complaint. A name-uniqueness test (« one tone per
 * status ») never caught either: two DIFFERENT tone names can be the same
 * colour to the eye.
 *
 * So this test measures. It parses the real `--*` OKLCH declarations out of the
 * token stylesheet, converts them to CIE Lab and asserts a floor on the
 * CIEDE2000 distance of every pair. A JND is ≈ 2.3; the floor here is 15,
 * roughly 6× that — « different colours, no hesitation », which is what the
 * completeness matrix needs since a chip there carries only the episode number
 * and the colour IS the signal.
 */

/// <reference types="node" />

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

// Read the SHIPPED stylesheet, not a copy: a test that restated the values
// would pass while the app drifted. (`?raw` is not an option — vitest routes
// .css through its CSS transform, which strips the declarations.)
const CSS = readFileSync(
  join(process.cwd(), "src/styles/ps/tokens/colors.css"),
  "utf8",
);

/** Minimum CIEDE2000 distance any two status colours must keep. */
const MIN_DELTA_E = 15;

/** The status colours that share the completeness matrix and its legend. */
const STATUS_TOKENS = [
  "neutral-signal", // « Non vérifié » (the colourless ghost chip)
  "upcoming", //       « Annoncé »
  "waiting", //        « En attente de torrent »
  "warning", //        « À récupérer »
  "info", //           « En cours d'acquisition »
  "success", //        « En médiathèque »
] as const;

type Lab = readonly [number, number, number];

/**
 * Read one `--token: oklch(L C H)` declaration from the token stylesheet.
 *
 * Args:
 *   css: The stylesheet source.
 *   token: The custom-property name, without the leading dashes.
 *
 * Returns:
 *   The `[L, C, H]` triple of the FIRST (dark-theme) declaration.
 */
function readOklch(css: string, token: string): readonly [number, number, number] {
  const re = new RegExp(
    `--${token}:\\s*oklch\\(\\s*([\\d.]+)\\s+([\\d.]+)\\s+([\\d.]+)\\s*\\)`,
  );
  const m = re.exec(css);
  if (!m?.[1] || !m[2] || !m[3]) {
    throw new Error(`token --${token} not found as an oklch() triple`);
  }
  return [Number(m[1]), Number(m[2]), Number(m[3])];
}

/** Convert OKLCH to CIE Lab (D65), via OKLab and linear sRGB. */
function oklchToLab([L, C, H]: readonly [number, number, number]): Lab {
  const h = (H * Math.PI) / 180;
  const a = C * Math.cos(h);
  const bb = C * Math.sin(h);
  const l_ = (L + 0.3963377774 * a + 0.2158037573 * bb) ** 3;
  const m_ = (L - 0.1055613458 * a - 0.0638541728 * bb) ** 3;
  const s_ = (L - 0.0894841775 * a - 1.291485548 * bb) ** 3;
  const clamp = (u: number): number => Math.min(1, Math.max(0, u));
  const lin = [
    clamp(4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_),
    clamp(-1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_),
    clamp(-0.0041960863 * l_ - 0.7034186147 * m_ + 1.707614701 * s_),
  ] as const;
  const X = 0.4124564 * lin[0] + 0.3575761 * lin[1] + 0.1804375 * lin[2];
  const Y = 0.2126729 * lin[0] + 0.7151522 * lin[1] + 0.072175 * lin[2];
  const Z = 0.0193339 * lin[0] + 0.119192 * lin[1] + 0.9503041 * lin[2];
  const f = (t: number): number =>
    t > 216 / 24389 ? Math.cbrt(t) : (841 / 108) * t + 4 / 29;
  const fx = f(X / 0.95047);
  const fy = f(Y);
  const fz = f(Z / 1.08883);
  return [116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)];
}

/** CIEDE2000 colour difference between two Lab colours. */
function ciede2000(lab1: Lab, lab2: Lab): number {
  const [L1, a1, b1] = lab1;
  const [L2, a2, b2] = lab2;
  const rad = (d: number): number => (d * Math.PI) / 180;
  const C1 = Math.hypot(a1, b1);
  const C2 = Math.hypot(a2, b2);
  const Cb = (C1 + C2) / 2;
  const G = 0.5 * (1 - Math.sqrt(Cb ** 7 / (Cb ** 7 + 25 ** 7 || 1)));
  const a1p = (1 + G) * a1;
  const a2p = (1 + G) * a2;
  const C1p = Math.hypot(a1p, b1);
  const C2p = Math.hypot(a2p, b2);
  const hp = (a: number, b: number): number =>
    a === 0 && b === 0 ? 0 : ((Math.atan2(b, a) * 180) / Math.PI + 360) % 360;
  const h1p = hp(a1p, b1);
  const h2p = hp(a2p, b2);
  const dLp = L2 - L1;
  const dCp = C2p - C1p;
  let dhp = 0;
  if (C1p * C2p !== 0) {
    dhp = h2p - h1p;
    if (dhp > 180) dhp -= 360;
    else if (dhp < -180) dhp += 360;
  }
  const dHp = 2 * Math.sqrt(C1p * C2p) * Math.sin(rad(dhp) / 2);
  const Lbp = (L1 + L2) / 2;
  const Cbp = (C1p + C2p) / 2;
  let hbp = h1p + h2p;
  if (C1p * C2p !== 0) {
    hbp = Math.abs(h1p - h2p) <= 180 ? hbp / 2 : (hbp + (hbp < 360 ? 360 : -360)) / 2;
  }
  const T =
    1 -
    0.17 * Math.cos(rad(hbp - 30)) +
    0.24 * Math.cos(rad(2 * hbp)) +
    0.32 * Math.cos(rad(3 * hbp + 6)) -
    0.2 * Math.cos(rad(4 * hbp - 63));
  const Rc = 2 * Math.sqrt(Cbp ** 7 / (Cbp ** 7 + 25 ** 7 || 1));
  const Sl = 1 + (0.015 * (Lbp - 50) ** 2) / Math.sqrt(20 + (Lbp - 50) ** 2);
  const Sc = 1 + 0.045 * Cbp;
  const Sh = 1 + 0.015 * Cbp * T;
  const Rt = -Math.sin(rad(2 * (30 * Math.exp(-(((hbp - 275) / 25) ** 2))))) * Rc;
  return Math.sqrt(
    (dLp / Sl) ** 2 +
      (dCp / Sc) ** 2 +
      (dHp / Sh) ** 2 +
      Rt * (dCp / Sc) * (dHp / Sh),
  );
}

describe("acquisition status palette — perceptual separation", () => {
  it.each(
    STATUS_TOKENS.flatMap((a, i) =>
      STATUS_TOKENS.slice(i + 1).map((b) => [a, b] as const),
    ),
  )("keeps --%s and --%s visibly apart", (a, b) => {
    const d = ciede2000(oklchToLab(readOklch(CSS, a)), oklchToLab(readOklch(CSS, b)));
    expect(
      d,
      `--${a} vs --${b}: ΔE00 ${d.toFixed(1)} — below the ${String(MIN_DELTA_E)} floor, ` +
        "these two statuses would read as the same colour",
    ).toBeGreaterThanOrEqual(MIN_DELTA_E);
  });

  it("keeps the three states the operator flagged far apart", () => {
    // « En attente de torrent » / « En cours d'acquisition » / « En médiathèque »
    // were teal / blue / green — one family. They now sit in three different
    // regions of the hue circle.
    const de = (a: string, b: string): number =>
      ciede2000(oklchToLab(readOklch(CSS, a)), oklchToLab(readOklch(CSS, b)));
    expect(de("waiting", "info")).toBeGreaterThan(40);
    expect(de("waiting", "success")).toBeGreaterThan(40);
    expect(de("info", "success")).toBeGreaterThan(30);
  });

  it("keeps « En attente » clear of the danger hue", () => {
    // A waiting chip must never read as an error: rose, not red.
    const d = ciede2000(oklchToLab(readOklch(CSS, "waiting")), oklchToLab(readOklch(CSS, "danger")));
    expect(d).toBeGreaterThan(MIN_DELTA_E);
  });
});
