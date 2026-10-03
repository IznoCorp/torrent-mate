// What Compte contributes to the bottom panel, in one import.
//
// `app/panel-contributions.ts` names ONE line per feature and never one per
// producer, so this feature gathers its own siblings here: the account menu,
// and « Comptes »' role-name and provisional-password blocks, whose kinds register what draws it as a
// SIDE EFFECT at module evaluation. It was only reached through
// `roster-panels.ts` — never by the boot, so R56 read it as never imported.
import "./panel-account";
import "./panel-role-name";
import "./panel-account-password";
