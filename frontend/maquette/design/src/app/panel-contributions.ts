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
import "../features/account/panels";
import "../features/account/verbs";
import "../features/maintenance/panel-action";
import "../features/library/panel-sort";
import "../features/acquisition/panels";
// Acquisition contributes the verb `data-take` reads (B-309) and the candidates
// screen's verbs.
import "../features/acquisition/resolution-verbs";
// And « Abandonner », which opens its confirmation before anything is sent.
import "../features/acquisition/abandon-verb";
// And « Supprimer », a folder set aside deleted after its confirmation.
import "../features/acquisition/delete-set-aside-verb";
// And « Ce n'est pas un média », its choice of destinations and its verb.
import "../features/acquisition/not-media-verb";
// And the release picker contributes its own — `data-pick-release`, declared
// to the tap registry. It is named beside the take verb because the two
// used to be ONE attribute read by two branches, and telling them apart by
// their values is what B-309 cost; each wears its own name now.
import "../features/releases/verbs";
// And acquisition contributes verbs beside its panels: the follows' own act,
// which two surfaces emit, the deck's drop, the page's selectors and panel acts,
// and the add screen's act. Each declares itself to the tap registry at module
// evaluation, so naming them here is the whole wiring.
import "../features/acquisition/follow-verbs";
import "../features/acquisition/deck-verbs";
import "../features/acquisition/verbs";
import "../features/acquisition/todo-pill-verbs";
import "../features/acquisition/add-verbs";
// And the library's verbs: the lens, the category, the layout, the sort, the
// search's clear cross, the selection and the removals.
import "../features/library/verbs";
// And the cross-seed block the Trackers page's panel draws — its own index,
// since it is reached otherwise only one level further than the boot checks.
import "../features/trackers/panels";
// And the « Trackers » page's: its tab, a setting of the page.
import "../features/trackers/verbs";
// And Système's landing door: a block's door names the section it lands on.
import "../features/system/landing";
// And Configuration contributes verbs beside its panels: the rubric one,
// moved off the engine's own delegation with the branch that answered it
// (B-332), and the secrets' three — replacing a key, asking before cutting
// one, and cutting it (B-334, B-335). Maintenance contributes the second
// rubric verb, which is the same mechanism on the other page that has
// rubrics (B-361).
import "../features/settings/topic-verb";
import "../features/settings/secret-verbs";
import "../features/settings/verbs";
import "../features/maintenance/topic-verb";
