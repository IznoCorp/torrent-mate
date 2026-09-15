// THE LIBRARY'S DELETE DIALOG — what a removal says before anything is removed.
//
// THE DELETE ACTS BY TITLE, the only key the contract offers, so one title can
// name two library rows (« Doctor Who », 2005 and 2023) and every figure the
// dialog prints counts MEDIA, not titles: a manifest whose whole purpose is to
// say exactly what would go cannot name half of it. The interface cannot delete
// one of the two — that needs an identifier the backend does not serve — but it
// can say the truth about what it is about to do.
//
// EVERY FIGURE IS A SERVED ANSWER: how many rows a title names is the exact
// membership read, and an incomplete show's owned episodes are the incomplete
// shows' read. The dialog asks for both before it opens, so it never counts
// from a page of the listing. The removal itself is still the engine's. Whether a title is FOLLOWED is asked of
// the `followedTitles` door, because the library never imports acquisition.
import i18next from "i18next";
import { membershipQuery, type Membership } from "../../lib/membership";
import { sharedQueryClient } from "../../lib/query-client";
import { dialog, followedTitles, toast } from "../../lib/shell-doors";
import { libraryIncompleteQuery } from "./queries";
import type { DialogDescriptor } from "../../ui/dialog/contract";
import type { IncompleteShow } from "./reference";

declare global {
  interface Window {
    /** The engine's removal: the layer deletes, the selection ends, the page redraws. */
    actionDelete: (titles: string[]) => void;
  }
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
    ?.find((show) => show.t === title);
}

/** The video files a title stands for: an incomplete show's owned episodes, otherwise its media. */
function filesOf(title: string): number {
  const show = incompleteShow(title);
  return show ? show.o : mediaNamedBy(title);
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
  // would go does not open on figures it has not read.
  await Promise.all([
    sharedQueryClient?.ensureQueryData(libraryIncompleteQuery),
    ...titles.map((one) => sharedQueryClient?.ensureQueryData(membershipQuery(one))),
  ]);
  const followingNow = followedTitles?.() ?? [];
  const followed = titles.filter(
    (one) => followingNow.includes(one) || incompleteShow(one) !== undefined,
  );
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
  body.push({ type: "dryRun", text: say("dryRun") });
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
  const removeSaying = (message: string) => () => {
    window.actionDelete(titles);
    toast?.show({ message });
  };
  const actions: DialogDescriptor["actions"] = [];
  if (followed.length > 0) {
    actions.push({
      text: say("deleteAndStop"),
      tone: "danger",
      run: removeSaying(say("doneStopped")),
    });
    actions.push({ text: say("deleteAndKeep"), run: removeSaying(say("doneKept")) });
  } else {
    actions.push({ text: say("delete"), tone: "danger", run: removeSaying(say("done")) });
  }
  actions.push({ text: say("cancel"), tone: "ghost", dismiss: true });
  dialog?.open({ heading, body, actions });
}
