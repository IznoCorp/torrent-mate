// THE ADDRESSED PANELS — a panel named in the address reopens.
//
// An ADDRESSED panel reopens on a cold load — otherwise its address would be
// decoration, written but never read. Every entry of the table answers TWO
// questions: how to open the panel, and whether the subject is one this
// interface HOLDS.
//
// THREE WAYS A VALUE IS REFUSED, and all three land the reader on the page with
// a clean address rather than on a panel nobody serves: a value that is not
// `<kind>:<subject>`, a kind the table does not carry, and a subject nobody
// holds. The last is why `resolves` exists at all — the producers answer for
// anything, which is right for the door inside the application and wrong for a
// door anyone can type.
//
// Split on the FIRST colon only, because a subject carries its own: a setting is
// addressed `<file>:<key>`, and a title like « Dexter: Resurrection » would
// otherwise name a medium that does not exist.
import { addressSeam } from "../lib/addresses";
import { queueLists } from "../lib/queue";
import { panel } from "../lib/shell-doors";
import { walk } from "./page-switch";

/* WHETHER THIS INTERFACE HOLDS A MEDIUM, handed in by the engine, which still
   answers it from the follows and from the library and incomplete fixtures it
   carries. The membership is EXACT: a title that only has a sheet is not a
   follow. It is asked for here rather than read from the query cache because
   the library listing in the cache is PAGED, so the cache would answer for the
   pages a surface happened to load and refuse the rest. */
let knownMedium: (title: string) => boolean = () => false;

/**
 * Installs the answer to « does this interface hold that medium ».
 *
 * Args:
 *     answer: The membership test, by exact title.
 */
export function installKnownMedium(answer: (title: string) => boolean): void {
  knownMedium = answer;
}

type Opener = {
  open: (subject: string) => void;
  resolves: (subject: string) => boolean;
};

const REOPEN: Readonly<Record<string, Opener | undefined>> = {
  /* The producer is the feature's. `resolves` asks whether this interface holds
     the medium at all, which is a question about the library and the queue
     rather than about the follow read — and the panel answers for ANY title by
     construction, which is the shape a typed address must be refused by. */
  follow: {
    open: (subject) => panel.produce("follow", subject),
    resolves: (subject) => knownMedium(subject),
  },
  journey: {
    open: (subject) => panel.produce("journey", subject),
    /* A journey is reached from the follow panel's own action, which carries
       the medium's title, and from nowhere else. So it answers for a medium
       this interface holds, plus the acquisitions in flight — which are what a
       journey describes. The layer answers the same stages for any info hash,
       so a `holds` built on that read would say yes to everything. */
    resolves: (subject) =>
      knownMedium(subject) ||
      (queueLists?.().inFlight ?? []).some((entry) => entry.t === subject),
  },
  setting: {
    /* The feature produces the panel and answers whether it holds the subject. */
    open: (subject) => panel.produce("setting", subject),
    resolves: (subject) => panel.holds("setting", subject),
  },
  action: {
    /* Both halves are the feature's: it produces the panel, and it answers
       whether it HOLDS the subject. */
    open: (subject) => panel.produce("action", subject),
    resolves: (subject) => panel.holds("action", subject),
  },
};

/**
 * Opens the panel an address names, when the interface holds its subject.
 *
 * ONE reader for `panel=`, and it is one because it is asked from two places:
 * the boot, on a cold load, and a FORWARD back onto a layer entry. Two readers
 * of one parameter are two answers waiting to differ, and the second of them
 * was missing entirely — a Forward re-entered the panel's own entry with nothing
 * open, so the address named a panel the interface was not showing.
 *
 * Args:
 *     search: The query string the value is read from.
 *     onCurrentEntry: True when the entry recording this panel already exists
 *         and is the one being stood on, so nothing is pushed.
 *     waiting: True when the caller can ask again, so a subject the cache has
 *         not delivered yet answers « not yet » rather than a refusal.
 *
 * Returns:
 *     True when a panel was opened, false when the value was refused — a
 *     refusal leaves the caller's entry alone and says why — and "not yet" when
 *     a waiting caller should ask again.
 */
export function reopenAddressedPanel(
  search: string,
  onCurrentEntry: boolean,
  waiting?: boolean,
): boolean | "not yet" {
  const asked = addressSeam.parse(location.pathname, search);
  if (!asked.panel) return false;
  const separator = asked.panel.indexOf(":");
  const kind = separator > 0 ? asked.panel.slice(0, separator) : "";
  const subject = separator > 0 ? asked.panel.slice(separator + 1) : "";
  const entry = REOPEN[kind];
  /* NOT YET IS NOT NO, and telling them apart is what a cold load needs. Every
     entry of `REOPEN` answers « does this interface HOLD the subject », and
     those answers come from the query cache — the follows, the acquisitions in
     flight, the maintenance actions. On a cold load none of them has landed
     when the boot runs, so a perfectly good `?panel=follow:Silo` looks like a
     subject nobody holds. A caller that can wait asks for `waiting`, and gets
     « not yet » instead of a refusal that warns and cleans the address it was
     about to retry from. */
  if (waiting && !asked.notFound && subject && entry && !entry.resolves(subject)) {
    return "not yet";
  }
  if (asked.notFound || !subject || !entry || !entry.resolves(subject)) {
    /* ENGLISH, and not in the i18n resources: a console message is a tool
       message, read by a developer, never by a reader of the interface.

       AND IT SAYS WHICH REFUSAL IT IS. A panel asked for over an address nothing
       serves is refused for the ADDRESS, not for the panel: the subject may well
       be one this interface holds, and reporting it as unheld sends the reader
       looking for a missing medium instead of a mistyped path. */
    console.warn(
      asked.notFound
        ? "the addressed panel is declined because the address itself is not served:"
        : "the addressed panel names nothing this interface holds, and is ignored:",
      asked.panel,
    );
    return false;
  }
  /* DRIVEN because nothing here records a path of its own. The layer entry the
     panel pushes is not a path, and on a cold load it is pushed regardless —
     that entry is the point. */
  const drivenBefore = walk.driven;
  walk.driven = true;
  try {
    if (onCurrentEntry) panel.openOnCurrentEntry(() => entry.open(subject));
    else entry.open(subject);
  } catch (error) {
    console.error("reopening the addressed panel failed", error);
    window.__navEchec = true;
    return false;
  } finally {
    walk.driven = drivenBefore;
  }
  return true;
}
