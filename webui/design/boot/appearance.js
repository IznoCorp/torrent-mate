// The saved appearance is applied before the first paint: the default
// (no data-theme attribute) paints dark, « light » forces light, and
// « system » follows the OS preference. The drawer's control writes the
// same key this reads, through `app/appearance.ts`. It sits INSIDE the
// pwa markers on purpose: the login gate borrows this whole block, and an
// operator who chose an appearance is owed it on the gate too — not only
// past it.
//
// B-245: THE TWO ENDS TESTED DIFFERENT WORDS. This script read « clair »
// and « systeme » while the application had been writing « light » and
// « system » since the English rename — so NO value it could store
// matched either literal, and the flash this script exists to prevent
// happened on every reload for every reader who had ever touched the
// control. A `data-*` contract has three ends and moves in one step; this
// one's third end is `localStorage`, and it was left behind.
(function () {
  try {
    var mode = localStorage.getItem("tm-apparence") || "system";
    var light =
      mode === "light" ||
      (mode === "system" &&
        matchMedia("(prefers-color-scheme: light)").matches);
    if (light)
      document.documentElement.setAttribute("data-theme", "light");
    // THE PINNED MENU'S WIDTH, for the same reason: a desktop that folded it opens folded
    // (`app/rail.ts`, DECIDED 2).
    if (localStorage.getItem("tm-rail") === "collapsed")
      document.documentElement.setAttribute("data-rail", "collapsed");
  } catch (error) {}
})();
