// « Comptes »' own drawing: the small forms its panels and Profil carry (a role's
// name, a provisional password, one's own password) and their fields, and an
// account's row once an Admin cut its access. A CREATION is not one of them: it
// opens its own page, drawn by `ui/creation-form.tsx`.
//
// The fields take the settings editor's shape — a bordered box at the type
// scale's 16px, so a focused field never zooms iOS — without importing that
// feature (invariant 7).
import { cva } from "../../ui/cva";

/** A small form: its labels stacked, one field under each. */
export const accountForm = cva("flex flex-col gap-5 mt-6 [&_label]:flex [&_label]:flex-col [&_label]:gap-2 [&_label]:text-3 [&_label]:text-muted-foreground");

/** One field of the form. */
export const accountField = cva(
  "w-full min-w-0 rounded-3 border border-border bg-background text-foreground text-6 py-4 px-5 "
    + "[font-family:inherit] outline-none focus-visible:outline-2 focus-visible:outline-primary",
);

/**
 * An account row's body, by its access: a CUT account reads as set aside — its
 * words muted — beside the chip that names the cut (the operator, 2026-10-04).
 *
 * `account-body` is its identity and carries no style: a factory's anchor is the
 * first token of its base, and a base left empty is a factory no reader can pair.
 */
export const accountBody = cva("account-body", {
  variants: { cut: { true: "[&_.fn]:text-muted-foreground [&_.fr]:opacity-70", false: "" } },
  defaultVariants: { cut: false },
});

/**
 * One session of « Appareils connectés », by where it stands. THE STATE IS THE NAMED STATE'S
 * OWN: the current session is the device in hand and is never revocable; another one is at
 * rest, being ended (muted while the server is asked), held (ended once the network is back),
 * or refused (said under it, the session still live).
 *
 * `session-row` is its identity and carries no style: a factory's anchor is the first token of
 * its base.
 */
export const sessionRow = cva("session-row", {
  variants: {
    state: {
      current: "",
      rest: "",
      ending: "opacity-60",
      held: "opacity-70",
      refused: "",
    },
  },
  defaultVariants: { state: "rest" },
});

/**
 * One sign-in notice, by whether the account has read it: an unread one leads with a bar in
 * the accent and a heavier line, a read one is muted.
 *
 * `notice-row` is its identity and carries no style.
 */
export const noticeRow = cva("notice-row", {
  variants: {
    unread: {
      true: "[border-inline-start:3px_solid_var(--color-primary)] pl-4 font-semibold",
      false: "text-muted-foreground [border-inline-start:3px_solid_transparent] pl-4",
    },
  },
  defaultVariants: { unread: false },
});

/**
 * The block of sign-in notices, by where it stands. THE STATE IS THE NAMED STATE'S OWN: being
 * read, unread-and-failed (said with a retry), none to report, the list, the mark being written,
 * the mark refused (said, the notices still unread) or held (said; the network is down and the
 * mark leaves with the outbox, so it is not offered twice).
 *
 * `notices-block` is its identity and carries no style.
 */
export const noticesSection = cva("notices-block", {
  variants: {
    state: {
      loading: "",
      failed: "",
      empty: "",
      list: "",
      marking: "",
      "mark-failed": "",
      held: "",
    },
  },
  defaultVariants: { state: "list" },
});
