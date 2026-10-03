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
import { quietWhenCancelled, sharedQueryClient } from "../../lib/query-client";
import { dialog, followedTitles, stopFollow, toast, redraw } from "../../lib/shell-doors";
import { store } from "../../lib/store-access";
import { deleteLibraryItems, libraryIncompleteQuery } from "./queries";
import type { DialogDescriptor } from "../../ui/dialog/contract";
import type { IncompleteShow } from "./types";
import { followedAs } from "../../lib/titles";

/** A medium the reader asked to remove: the title its row reads, and the identity it was drawn with. */
export type Doomed = { title: string; ref: MediaRef };

/**
 * Removes media from the library: the layer deletes, the selection ends, the
 * page redraws, and the removal is said.
 *
 * The confirmation that calls it says what was done in its own words right
 * after, and that message replaces this one — so this one is what a caller
 * with nothing more precise to say is left with.
 *
 * @param doomed The media removed, each by its identity.
 */
function removeMedia(doomed: Doomed[]): void {
  const titles = doomed.map((one) => one.title);
  deleteLibraryItems?.(doomed);
  store.write({ selMode: false, selected: new Map() });
  redraw();
  toast?.show({
    message: i18next.t(titles.length > 1 ? "verbs.library.deletedMany" : "verbs.library.deletedOne", {
      count: titles.length,
    }),
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
  const removed = titles.length > 1 ? say("doneMany", { count: titles.length }) : say("done", { title: titles[0] });
  const removeSaying = (follow?: string, stop = false) => () => {
    removeMedia(doomed);
    // THE FOLLOW IS STOPPED, NOT ONLY SAID STOPPED (B-689): both confirmations
    // removed the same titles and differed only in their sentence, so the
    // follow lived on everywhere. It is stopped under ITS title (« Silo »), the
    // one `followedAs` reads, never the row's (« Silo (2023) »).
    if (stop) for (const one of followed) {
      const followTitle = followedAs(followingNow, one);
      if (followTitle !== undefined) stopFollow?.(followTitle);
    }
    toast?.show({ message: follow ? `${removed} ${follow}` : removed });
  };
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
