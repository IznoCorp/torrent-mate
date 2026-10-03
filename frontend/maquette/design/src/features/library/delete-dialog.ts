// THE LIBRARY'S DELETE DIALOG — what a removal says before anything is removed.
//
// THE DELETE ACTS BY PROVIDER IDENTITY (operator ruling Q5 A): each title the
// reader ticked is resolved to the identity it was drawn with, and that is what
// the layer is asked to delete. An identity two library rows hold — a DUPLICATE,
// « Doctor Who » twice under one TVDB id — is not deleted until it is settled
// (O-5 B): the dialog says so before anything is offered, and the server refuses
// it `media.ambiguous` all the same. Every figure counts MEDIA, not titles.
//
// EVERY FIGURE IS A SERVED ANSWER: how many rows a title names is the exact
// membership read, and an incomplete show's owned episodes are the incomplete
// shows' read. The dialog asks for both before it opens, so it never counts
// from a page of the listing. The removal itself is still the engine's. Whether a title is FOLLOWED is asked of
// the `followedTitles` door, because the library never imports acquisition.
import i18next from "i18next";
import { identityOfTitle, membershipByRefQuery, membershipQuery, type MediaRef, type Membership } from "../../lib/membership";
import { quietWhenCancelled, sharedQueryClient } from "../../lib/query-client";
import { dialog, followedTitles, stopFollow, toast, redraw } from "../../lib/shell-doors";
import { store } from "../../lib/store-access";
import { deleteLibraryItems, libraryIncompleteQuery } from "./queries";
import type { DialogDescriptor } from "../../ui/dialog/contract";
import type { IncompleteShow } from "./types";
import { followedAs } from "../../lib/titles";

/** A title the reader asked to remove, with the identity it was drawn with. */
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
  store.write({ selMode: false, selected: new Set() });
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

/**
 * How many library rows one title names.
 *
 * Args:
 *     title: The title a removal names.
 *
 * Returns:
 *     The rows it names, never fewer than one.
 */
export function mediaNamedBy(title: string): number {
  const held = sharedQueryClient?.getQueryData<Membership>(membershipQuery(title).queryKey);
  return Math.max(1, held?.rows ?? 1);
}

/** The incomplete show a title names, if the index knows one. */
function incompleteShow(title: string): IncompleteShow | undefined {
  return sharedQueryClient
    ?.getQueryData<IncompleteShow[]>(libraryIncompleteQuery.queryKey)
    ?.find((show) => show.title === title);
}

/** The video files a title stands for: an incomplete show's owned episodes, otherwise its media. */
function filesOf(title: string): number {
  const show = incompleteShow(title);
  return show ? show.owned : mediaNamedBy(title);
}

/** The total of one figure over several titles. */
function totalOf(titles: string[], figure: (title: string) => number): number {
  return titles.reduce((total, title) => total + figure(title), 0);
}

/**
 * Opens the delete dialog for one title or for a selection.
 *
 * Args:
 *     title: The one title removed, or null when a selection is.
 *     many: The selection's titles, when there is one.
 */
export async function openDeleteDialog(title: string | null, many?: string[]): Promise<void> {
  const titles = many && many.length > 0 ? many : [title ?? ""];
  // THE ANSWERS FIRST: a dialog whose whole purpose is to say exactly what
  // would go does not open on figures it has not read — nor at all when the
  // cache's reset cancels a read. The identities too: the layer deletes by them.
  let refs: (MediaRef | null)[];
  try {
    await Promise.all([
      sharedQueryClient?.ensureQueryData(libraryIncompleteQuery),
      ...titles.map((one) => sharedQueryClient?.ensureQueryData(membershipQuery(one))),
    ]);
    refs = await Promise.all(titles.map((one) => identityOfTitle(one)));
    await Promise.all(refs.map((ref) => (ref ? sharedQueryClient?.ensureQueryData(membershipByRefQuery(ref)) : null)));
  } catch (failure) {
    quietWhenCancelled(failure);
    return;
  }
  // WHAT CANNOT BE DELETED IS SAID BEFORE ANYTHING IS OFFERED: a title nothing
  // identifies, and an identity two library rows hold (O-5 B).
  const blocked = titles
    .map((one, index) => ({ title: one, ref: refs[index], rows: mediaNamedBy(one) }))
    .filter((one) => one.ref === null || one.rows > 1);
  if (blocked.length > 0) {
    openRefusedDialog(blocked);
    return;
  }
  const doomed = titles.map((one, index) => ({ title: one, ref: refs[index] as MediaRef }));
  const followingNow = followedTitles?.() ?? [];
  // THE ONE READING of « is it followed » (`followedAs`, B-676), the sheet's own.
  // An incomplete show is NOT followed: counting it as one made the dialog say
  // « est suivi » and offer « garder le suivi » of a follow that never existed.
  const followed = titles.filter((one) => followedAs(followingNow, one) !== undefined);
  const files = totalOf(titles, filesOf);
  const media = totalOf(titles, mediaNamedBy);
  // What the four rows above the fold account for, so « et N autres » names
  // media like every other figure in this dialog.
  const shown = totalOf(titles.slice(0, 4), mediaNamedBy);
  // A followed title that names two rows is two media coming back at the next
  // search.
  const followedMedia = totalOf(followed, mediaNamedBy);
  const size = say("size", { size: (files * 0.41).toFixed(1).replace(".", ",") });
  const heading =
    titles.length > 1
      ? say("headingMany", { media })
      : media > 1
        ? say("headingOneTitleMany", { title: titles[0], media })
        : say("headingOne", { title: titles[0] });

  const body: DialogDescriptor["body"] = [];
  if (titles.length > 1) {
    const entries = titles.slice(0, 4).map((one) => ({
      text: one,
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
 *     blocked: The titles that cannot go, each with its identity (null when
 *         nothing identifies it) and how many library rows hold it.
 */
function openRefusedDialog(blocked: { title: string; ref: MediaRef | null; rows: number }[]): void {
  dialog?.open({
    heading:
      blocked.length > 1 ? say("blockedHeadingMany", { count: blocked.length }) : say("blockedHeadingOne", { title: blocked[0].title }),
    body: [
      {
        type: "manifest",
        entries: blocked.map((one) => ({
          text: one.title,
          value: one.ref === null ? say("unidentified") : say("heldByRows", { count: one.rows }),
        })),
      },
      { type: "paragraph", runs: [{ text: say(blocked.some((one) => one.ref !== null) ? "ambiguousText" : "unidentifiedText") }] },
    ],
    actions: [{ text: say("close"), tone: "ghost", dismiss: true }],
  });
}
