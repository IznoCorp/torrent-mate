// WHAT THE FEATURES CONTRIBUTE TO THE PANEL, named at boot.
//
// Each import below runs a module for its SIDE EFFECT: it declares a block kind
// to the panel's contract and registers what draws it, or registers what
// PRODUCES a descriptor. Nothing else imports them — a panel is opened through
// `window.__panel`, never by a component holding a reference — so the boot is
// where they have to be named, and `app/` naming what a feature contributes at
// boot is exactly its job (invariant 10's own exception for the tables whose
// job is to name pages).
//
// IT IS A FILE OF ITS OWN, and the reason is a ceiling rather than taste.
// `app/shell.tsx` stands one line under a 400-line hard block a converting lot
// may only move DOWNWARD, and this list gains an entry per feature converted —
// three today, eight by the end. A list that grows inside the shell is a list
// that spends the shell's last line on its second entry.
//
// ONE LINE PER FEATURE, never one per producer: a feature's own module imports
// its siblings, so a feature that ends up with four panels appears here once.
//
// The shell imports THIS file at boot, before anything can open a panel.
import "../features/media/panel-seasons";
// And what the episode popover SAYS — the frame places it, the feature says it.
import "../features/media/popover-episode";
import "../features/settings/panels";
import "../features/account/panel-account";
import "../features/maintenance/panel-action";
import "../features/library/panel-sort";
import "../features/acquisition/panels";
// Arrivals contributes no PANEL — it contributes the verb `data-take` reads
// (B-309), and the boot is where a side effect is named whatever it is.
import "../features/arrivals/verbs";
