// THE LIBRARY'S DELETE DIALOG — what a removal says before anything is removed.
//
// THE DELETE ACTS BY PROVIDER IDENTITY (operator ruling Q5 A): each row the
// reader swiped or ticked hands over the identity it was drawn with, and that is
// what the layer is asked to delete. A title is never taken back to an identity
// here: two media may share one (« RoboCop » 1987 and 2014), and the medium a
// title finds first is not the row's. An identity two library rows hold — a
// DUPLICATE, « Doctor Who » twice under one TVDB id — is not deleted until it is
// settled (O-5 B): the dialog says so before anything is offered, and the server
// refuses it `media.ambiguous` all the same. Every figure counts MEDIA, not titles.
//
// EVERY FIGURE IS A SERVED ANSWER: how many rows an identity names is the exact
// membership read by that identity, and an incomplete show's owned episodes are
// the incomplete shows' read. The dialog asks for both before it opens, so it never counts
// from a page of the listing. The removal itself is still the engine's. Whether a title is FOLLOWED is asked of
// the `followedTitles` door, because the library never imports acquisition.
import i18next from "i18next";
import { membershipByRefQuery, type MediaRef, type Membership } from "../../lib/membership";
import { HELD, quietWhenCancelled, sharedQueryClient } from "../../lib/query-client";
import { dialog, followedTitles, stopFollow, toast, redraw } from "../../lib/shell-doors";
import { store } from "../../lib/store-access";
import { deleteLibraryItems, libraryIncompleteQuery, type LibraryDeletion } from "./queries";
import { timeOfDay } from "../../lib/clock";
import type { DialogDescriptor } from "../../ui/dialog/contract";
import type { IncompleteShow } from "./types";
import { followedAs } from "../../lib/titles";

/** A medium the reader asked to remove: the title its row reads, and the identity it was drawn with. */
export type Doomed = { title: string; ref: MediaRef };

/**
 * Removes media from the library: the layer deletes, the selection ends, the
 * page redraws, and what each medium did is said.
 *
 * WHAT WENT IS SAID, AND WHAT STAYED IS SAID WHY (operator ruling R2,
 * 2026-10-05; § 8 « Rien en silence »). The layer answers medium by medium:
 * when everything went, the caller's sentence says so; when anything was kept
 * — a tracker still owed its seeding, its disk unplugged, a folder that would
 * not go — the dialog that follows names each kept medium and its reason, and
 * the media that went are counted against the ones asked.
 *
 * @param doomed The media removed, each by its identity.
 * @param went Says what went, and does what follows from it (a follow
 *     stopped), for the media that did; called only when every medium went or
 *     before the kept media are drawn.
 */
async function removeMedia(doomed: Doomed[], went: (gone: Doomed[]) => void): Promise<void> {
  const answer = await deleteLibraryItems?.(doomed);
  store.write({ selMode: false, selected: new Map() });
  redraw();
  if (answer === HELD) {
    toast?.show({ message: i18next.t("verbs.library.deleteHeld") });
    return;
  }
  // REFUSED: the layer's refusal is already said, and nothing went.
  if (answer === null || answer === undefined) return;
  const named = (one: Doomed, ref: MediaRef) => one.ref.provider === ref.provider && one.ref.providerId === ref.providerId;
  const gone = doomed.filter((one) => answer.some((medium) => medium.outcome === "deleted" && named(one, medium.ref)));
  const kept = answer.flatMap((medium) => {
    const one = doomed.find((candidate) => named(candidate, medium.ref));
    return medium.outcome === "kept" && one !== undefined ? [{ ...one, medium }] : [];
  });
  if (gone.length > 0) went(gone);
  if (kept.length > 0) openKeptDialog(kept, gone.length + kept.length);
}

/**
 * Why one medium was kept, in the interface's words.
 *
 * Args:
 *     medium: The layer's answer for it.
 *
 * Returns:
 *     The reason, with the date the seeding is owed until when the store knows it.
 */
function keptReason(medium: LibraryDeletion): string {
  if (medium.reason === "disk_unreachable") return say("keptDiskUnreachable");
  if (medium.reason === "seed_owed") {
    if (medium.owedUntil === null) return say("keptSeedOwedUndated");
    const until = new Date(medium.owedUntil * 1000);
    const day = new Intl.DateTimeFormat(i18next.language, { day: "numeric", month: "long" }).format(until);
    return say("keptSeedOwed", { day, time: timeOfDay(medium.owedUntil) });
  }
  return say("keptFailed");
}

/**
 * The dialog a deletion that kept media draws: each kept medium named with its
 * reason, and, for a request of several media, how many of them went.
 *
 * Args:
 *     kept: The media kept, each with the layer's answer for it.
 *     asked: How many media the layer answered for.
 */
function openKeptDialog(kept: (Doomed & { medium: LibraryDeletion })[], asked: number): void {
  const heading =
    kept.length < asked
      ? say("partlyHeading", { deleted: asked - kept.length, asked })
      : kept.length > 1
        ? say("keptHeadingMany", { count: kept.length })
        : say("keptHeadingOne", { title: kept[0].title });
  dialog?.open({
    heading,
    body: [
      { type: "manifest", entries: kept.map((one) => ({ text: one.title, value: keptReason(one.medium) })) },
      { type: "paragraph", runs: [{ text: say("keptText") }] },
    ],
    actions: [{ text: say("close"), tone: "ghost", dismiss: true }],
  });
}

/**
 * Reads one sentence of the dialog.
 *
 * Args:
 *     key: The sentence's key under `verbs.library.delete`.
 *     options: The values it interpolates.
 *
 * Returns:
 *     The sentence.
 */
function say(key: string, options?: Record<string, string | number>): string {
  return i18next.t(`verbs.library.delete.${key}`, options);
}

/**
 * Reads the sentence for a count, singular or plural.
 *
 * Args:
 *     count: The figure.
 *     one: The key read when the figure is one or less.
 *     many: The key read otherwise.
 *
 * Returns:
 *     The sentence carrying the figure.
 */
function counted(count: number, one: string, many: string): string {
  return say(count > 1 ? many : one, { count });
}

/** What the library answers about one identity, once it has been read. */
function membershipOf(ref: MediaRef): Membership | undefined {
  return sharedQueryClient?.getQueryData<Membership>(membershipByRefQuery(ref).queryKey);
}

/**
 * How many library rows one identity names — the served membership, never a
 * count of rows that share a title.
 *
 * Args:
 *     ref: The identity a removal names.
 *
 * Returns:
 *     The rows it names, never fewer than one.
 */
export function mediaNamedBy(ref: MediaRef): number {
  return Math.max(1, membershipOf(ref)?.rows ?? 1);
}

/** The incomplete show an identity names, if the index knows one. */
function incompleteShow(ref: MediaRef): IncompleteShow | undefined {
  return sharedQueryClient
    ?.getQueryData<IncompleteShow[]>(libraryIncompleteQuery.queryKey)
    ?.find((show) => String((show.ids as Record<string, string | number> | null)?.[ref.provider] ?? "") === ref.providerId);
}

/** The video files a medium stands for: an incomplete show's owned episodes, otherwise its media. */
function filesOf(one: Doomed): number {
  const show = incompleteShow(one.ref);
  return show ? show.owned : mediaNamedBy(one.ref);
}

/** How many media a removal names. */
function mediaOf(one: Doomed): number {
  return mediaNamedBy(one.ref);
}

/** The total of one figure over several media. */
function totalOf(doomed: Doomed[], figure: (one: Doomed) => number): number {
  return doomed.reduce((total, one) => total + figure(one), 0);
}

/**
 * Opens the delete dialog for one medium or for a selection.
 *
 * Args:
 *     doomed: The media removed, each with the title its row reads and the
 *         identity it was drawn with — one for a swipe, several for a selection.
 */
export async function openDeleteDialog(doomed: Doomed[]): Promise<void> {
  if (doomed.length === 0) return;
  const titles = doomed.map((one) => one.title);
  // THE ANSWERS FIRST: a dialog whose whole purpose is to say exactly what
  // would go does not open on figures it has not read — nor at all when the
  // cache's reset cancels a read.
  try {
    await Promise.all([
      sharedQueryClient?.ensureQueryData(libraryIncompleteQuery),
      ...doomed.map((one) => sharedQueryClient?.ensureQueryData(membershipByRefQuery(one.ref))),
    ]);
  } catch (failure) {
    quietWhenCancelled(failure);
    return;
  }
  // EVERY LIBRARY ENTRY IS IDENTIFIED (the operator, 2026-10-03): an identity
  // the library answers it does not hold is one it no longer holds — said as
  // the layer would refuse it, and nothing is offered.
  if (doomed.some((one) => membershipOf(one.ref)?.inLibrary === false)) {
    toast?.show({ message: i18next.t("refusals.media.not_found") });
    return;
  }
  // AN IDENTITY TWO LIBRARY ROWS HOLD IS SAID BEFORE ANYTHING IS OFFERED (O-5 B).
  const blocked = doomed.map((one) => ({ ...one, rows: mediaOf(one) })).filter((one) => one.rows > 1);
  if (blocked.length > 0) {
    openRefusedDialog(blocked);
    return;
  }
  const followingNow = followedTitles?.() ?? [];
  // THE ONE READING of « is it followed » (`followedAs`, B-676), the sheet's own.
  // An incomplete show is NOT followed: counting it as one made the dialog say
  // « est suivi » and offer « garder le suivi » of a follow that never existed.
  // The follow is the acquisition's, named by title — it is stopped, never deleted.
  const followedDoomed = doomed.filter((one) => followedAs(followingNow, one.title) !== undefined);
  const followed = followedDoomed.map((one) => one.title);
  const files = totalOf(doomed, filesOf);
  const media = totalOf(doomed, mediaOf);
  // What the four rows above the fold account for, so « et N autres » names
  // media like every other figure in this dialog.
  const shown = totalOf(doomed.slice(0, 4), mediaOf);
  // A followed medium that names two rows is two media coming back at the next
  // search.
  const followedMedia = totalOf(followedDoomed, mediaOf);
  const size = say("size", { size: (files * 0.41).toFixed(1).replace(".", ",") });
  const heading =
    titles.length > 1
      ? say("headingMany", { media })
      : media > 1
        ? say("headingOneTitleMany", { title: titles[0], media })
        : say("headingOne", { title: titles[0] });

  const body: DialogDescriptor["body"] = [];
  if (titles.length > 1) {
    const entries = doomed.slice(0, 4).map((one) => ({
      text: one.title,
      value: counted(filesOf(one), "fileOne", "fileMany"),
    }));
    if (titles.length > 4)
      entries.push({ text: counted(media - shown, "otherOne", "otherMany"), value: "" });
    body.push({ type: "manifest", entries });
  }
  body.push({ type: "paragraph", runs: [{ text: say("exactly") }] });
  body.push({
    type: "manifest",
    entries: [
      { text: say("videoFiles"), value: say("videoFilesValue", { files, size }) },
      { text: say("metadata"), value: say("metadataValue", { count: files * 3 }) },
      { text: say("libraryRows"), value: counted(media, "itemOne", "itemMany") },
      { text: say("plexEntry"), value: say("plexEntryValue", { count: media }) },
    ],
  });
  if (followed.length > 0)
    body.push({
      type: "warning",
      strong:
        followed.length === 1
          ? say("followedOne", { title: followed[0] })
          : say("followedMany", { count: followedMedia }),
      text: say("followedText"),
    });

  /* THE CONFIRMATION SAYS WHAT WAS DONE ITSELF, and carries no `data-toast`:
     the tap registry answers a verb in the CAPTURE phase and stops the click
     there, so a button carrying one never reached its own `onClick` and the
     removal it confirms never ran. */
  const removeSaying = (follow?: string, stop = false) => () =>
    removeMedia(doomed, (gone) => {
      // THE FOLLOW IS STOPPED, NOT ONLY SAID STOPPED (B-689): both confirmations
      // removed the same titles and differed only in their sentence, so the
      // follow lived on everywhere. It is stopped under ITS title (« Silo »), the
      // one `followedAs` reads, never the row's (« Silo (2023) »). Only for a
      // medium that WENT: a kept one is still there to follow.
      if (stop) for (const one of gone) {
        const followTitle = followedAs(followingNow, one.title);
        if (followTitle !== undefined) stopFollow?.(followTitle);
      }
      if (gone.length < doomed.length) return;
      const removed = titles.length > 1 ? say("doneMany", { count: titles.length }) : say("done", { title: titles[0] });
      toast?.show({ message: follow ? `${removed} ${follow}` : removed });
    });
  const actions: DialogDescriptor["actions"] = [];
  if (followed.length > 0) {
    actions.push({
      text: say("deleteAndStop"),
      tone: "danger",
      run: removeSaying(say("followStopped"), true),
    });
    actions.push({ text: say("deleteAndKeep"), run: removeSaying(say("followKept")) });
  } else {
    actions.push({ text: say("delete"), tone: "danger", run: removeSaying() });
  }
  actions.push({ text: say("cancel"), tone: "ghost", dismiss: true });
  dialog?.open({ heading, body, actions });
}

/**
 * The dialog a removal that cannot go draws — the ambiguous identity named, and
 * nothing offered but to close (operator ruling O-5 B, 2026-10-03).
 *
 * Args:
 *     blocked: The titles that cannot go, each with its identity and how many
 *         library rows hold it.
 */
function openRefusedDialog(blocked: { title: string; ref: MediaRef; rows: number }[]): void {
  dialog?.open({
    heading:
      blocked.length > 1 ? say("blockedHeadingMany", { count: blocked.length }) : say("blockedHeadingOne", { title: blocked[0].title }),
    body: [
      {
        type: "manifest",
        entries: blocked.map((one) => ({
          text: one.title,
          value: say("heldByRows", { count: one.rows }),
        })),
      },
      { type: "paragraph", runs: [{ text: say("ambiguousText") }] },
    ],
    actions: [{ text: say("close"), tone: "ghost", dismiss: true }],
  });
}
