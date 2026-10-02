// THE SEEDS A MEASUREMENT READS, through the mock layer's driving surface.
//
// READ BY THE HARNESS ALONE — the driver, the named states and the rules — and
// never by the product. The product asks the served reads, by address; this is
// what a rule compares those reads against, and what a named state needs to open
// a medium no served list happens to hold (DESIGN § 4.2: the mock layer exposes
// the seeds it answers from). Nothing outside `app/` imports `mocks/`, so a
// product module could not reach this even by mistake.
//
// THREE FAMILIES: every media sheet keyed by the title the seed holds it under,
// with the poster the sheet read composes beside it; the settings catalogue; and
// the passages, so a named state opens a run by what it is about — a failure,
// a maintenance command — rather than by an identifier written into it.
import MEDIA_SHEETS from "./seeds/media-sheets.json";
import POSTERS from "./seeds/posters.json";
import SETTINGS from "./seeds/settings.json";
import PIPELINE_RUNS from "./seeds/pipeline-runs.json";
import type { components } from "../contract/types";
import SEASON_FAMILY from "./seeds/seasons.json";
import { candidateSheet, seasonsAnswerFor } from "./handlers/media";
import FOLLOWS from "./seeds/follows.json";
import INCOMPLETE_SHOWS from "./seeds/incomplete-shows.json";
import { seasonsHeld, type SeasonsAnswer } from "../lib/season-rows";
import { renameAccount } from "./account";
import { mockState } from "./state";
import { poseDisagreement, poseStuckFolders, setAside } from "./handlers/staging";
import { poseTunnelError } from "./handlers/follow-errors";
import { poseUnknownIdentity } from "./handlers/posed-identity";
import { liftBlock, liftCause, poseBlock, poseServiceDown } from "./handlers/posed-block";
import { poseClosure, poseFiled, poseFiledByHand, poseKeptNewer, poseMediumBack } from "./handlers/posed-closure";
import { sameItem } from "./handlers/same-item";
import {
  SEARCHING, poseAutomatic, poseBeforeAsk, poseSeasonArrived, poseSeasonAt, poseSeasonBlocked, poseSeasonEnded,
  poseSeasonShelved, poseReleaseTried,
} from "./handlers/season-recovery";
import { poseKeepsItsFiles } from "./handlers/staged-folders";
import { confirmInPlex, placeAtPlexCheck, placeInEnrichment } from "./handlers/ladder";
import { emit } from "./stream";

/** What the layer exposes of its seeds. */
export type MockSeeds = {
  /** Every media sheet, keyed by title, in the contract's names, with its poster. */
  sheets: () => Record<string, Record<string, unknown>>;
  /** The sheet the layer composes for a resolution candidate's identity, or null. */
  candidateSheet: (provider: string, identifier: string) => Record<string, unknown> | null;
  /** The settings catalogue, rubric by rubric, in the contract's names. */
  settings: () => { id: string; settings: { file: string; key: string; type: string }[] }[];
  /** Every passage the history holds at rest, in the snapshot's order and the contract's names. */
  pipelineRuns: () => components["schemas"]["RunDetail"][];
  /**
   * Every medium's season rows — number, aired (null when unknown), held — as
   * the seasons read answers them and every season row is drawn from them.
   */
  seasons: () => Record<string, [number, number | null, number][]>;
  /** The season family seed, as its rows were written: `[season, aired, owned]` per title. */
  seasonFamily: () => Record<string, [number, number, number][]>;
  /** Renames the seeded account until the layer is next reset — the seed changed, every reader must follow. */
  renameAccount: (name: string) => void;
  /** Empties what is blocked — the queue's, the staging area's, a match to confirm — until the layer is next reset. */
  clearBlocked: () => void;
  /** Sets one queued folder aside, as « Laisser tel quel » does, until the layer is next reset. */
  setAside: (title: string) => boolean;
  /** Queues more stuck folders, so « À traiter » holds enough « Résoudre » cards to scroll, until the layer is next reset. */
  poseStuckFolders: (titles: string[]) => void;
  /** Poses « the torrent keeps its files » on a staged folder — a DERIVATION, never read (RULINGS 22). */
  poseKeepsItsFiles: (title: string) => void;
  /** Poses a Plex match that DISAGREES with the identity held — a DERIVATION, never read (RULINGS 24). */
  poseDisagreement: (title: string, match: { title: string; ids: Record<string, string | number> }) => void;
  /** Poses a tunnel error on a follow's folder in flight — a DERIVATION, never read (RULINGS 26). */
  poseTunnelError: typeof poseTunnelError;
  /** Poses an arrival in flight whose identity is not known yet — a DERIVATION, never read: the backend reads the « identifié » rung in progress. */
  poseUnknownIdentity: typeof poseUnknownIdentity;
  /** Poses an external block on an acquisition — a deferral or one of Q7's causes — a DERIVATION, never read: the backend serves the cause (BK1). */
  poseBlock: typeof poseBlock;
  /** Poses one dependency down — a DERIVATION, never read: the backend serves its reachability (BK6). */
  poseServiceDown: typeof poseServiceDown;
  /** The engine sees one acquisition's cause lifted and resumes it, with its live event (BK2). */
  liftBlock: typeof liftBlock;
  /** The engine sees one cause lifted and resumes every acquisition it held, in one live event (BK2). */
  liftCause: typeof liftCause;
  /** Closes an acquisition's tunnel with its reason — a DERIVATION, never read: the engine closes it (BK3, BK4). */
  poseClosure: typeof poseClosure;
  /** The vanished medium back: a new tunnel under the same key, the closed one still unseen (BK3). */
  poseMediumBack: typeof poseMediumBack;
  /** The medium filed by hand elsewhere: its tunnel ends with no card (BK3). */
  poseFiledByHand: typeof poseFiledByHand;
  /** A pack filed save the episodes a later choice holds, each named in its journey (BK4). */
  poseKeptNewer: typeof poseKeptNewer;
  /** A pack filed and verifying — the release in place of a superseded one (BK4). */
  poseFiled: typeof poseFiled;
  /**
   * A whole season's recovery, POSED on the one the dense world holds — each a
   * DERIVATION until the layer is next reset: the moment before the ask, a rung
   * of the season's card, stopped, arrived, launched by the engine, ended.
   */
  seasonRecovery: {
    beforeAsk: typeof poseBeforeAsk;
    searching: (title: string, season: number) => void;
    blocked: typeof poseSeasonBlocked;
    arrived: typeof poseSeasonArrived;
    automatic: typeof poseAutomatic;
    ended: typeof poseSeasonEnded;
    shelved: typeof poseSeasonShelved;
    releaseTried: typeof poseReleaseTried;
  };
  /** Whether two queue cards stand for one item — the layer's own rapprochement (R238). */
  sameItem: typeof sameItem;
  /** Lays a medium's ladder one event away from « vérifié dans Plex » — a DERIVATION from its real row (RULINGS 14). */
  placeAtPlexCheck: (title: string) => void;
  /** Lays a medium's ladder in the middle of its enrichment — « enrichi » unfolded, each part at its own state. */
  placeInEnrichment: (title: string) => void;
  /**
   * The medium confirmed in the library: its last rung done, carried on the
   * engine's per-step event, `ItemProgressed`. Answers true once emitted.
   */
  confirmInPlex: (title: string) => boolean;
};

/** The seeds the harness reads, composed on each call so no caller holds a copy it could mutate. */
export const mockSeeds: MockSeeds = {
  sheets: () =>
    Object.fromEntries(
      Object.entries(MEDIA_SHEETS as Record<string, Record<string, unknown>>).map(
        ([title, sheet]) => [
          title,
          { ...sheet, poster: (POSTERS as Record<string, string>)[title] ?? null },
        ],
      ),
    ),
  candidateSheet: (provider, identifier) =>
    candidateSheet(provider, identifier) as Record<string, unknown> | null,
  settings: () => structuredClone(SETTINGS) as ReturnType<MockSeeds["settings"]>,
  pipelineRuns: () => structuredClone(PIPELINE_RUNS) as ReturnType<MockSeeds["pipelineRuns"]>,
  seasons: () => {
    // EVERY TITLE A RULE CAN ASK ABOUT — a follow, an incomplete show, a sheet,
    // the family — each answered under its IDENTITY, as the served read is: a
    // follow named « Silo » holds its episodes under the sheet « Silo (2023) ».
    const identityByTitle = new Map<string, Record<string, unknown> | undefined>();
    for (const title of Object.keys(MEDIA_SHEETS))
      identityByTitle.set(title, (MEDIA_SHEETS as Record<string, { ids?: Record<string, unknown> }>)[title].ids);
    for (const title of Object.keys(SEASON_FAMILY)) if (!identityByTitle.has(title)) identityByTitle.set(title, undefined);
    for (const one of [...FOLLOWS, ...INCOMPLETE_SHOWS] as { title: string; ids?: Record<string, unknown> | null }[])
      identityByTitle.set(one.title, one.ids ?? identityByTitle.get(one.title));
    return Object.fromEntries(
      [...identityByTitle].map(([title, ids]) => {
        const answer = seasonsAnswerFor(title, ids);
        // One shape since B-471: the read answers the catalogue in its own names.
        const catalogue = answer.seasons as SeasonsAnswer["seasons"];
        return [title, seasonsHeld({ seasons: catalogue, owned: answer.owned, aired: answer.aired })];
      }),
    );
  },
  seasonFamily: () =>
    Object.fromEntries(
      Object.entries(SEASON_FAMILY as Record<string, { season: number; aired: number; owned: number }[]>).map(
        ([title, rows]) => [title, rows.map((row) => [row.season, row.aired, row.owned])],
      ),
    ) as Record<string, [number, number, number][]>,
  renameAccount,
  // « À TRAITER » WITH NOTHING WAITING: no blocked card, no stuck folder — the
  // other lists are left as they are, so the rest of the page still draws.
  clearBlocked: () => {
    const state = mockState();
    // A settled folder whose Plex match waits is blocked too: the match is dropped.
    const answered = (cards: typeof state.settled) => cards.map(({ plexMatch, ...card }) => card);
    Object.assign(state, {
      blocked: [], stuck: [], stuckLoaded: [],
      settled: answered(state.settled), settledLoaded: answered(state.settledLoaded),
      // and every ladder already laid is laid again, from where the cards now stand.
      journeyStages: {},
    });
  },
  setAside,
  poseStuckFolders,
  poseKeepsItsFiles,
  poseDisagreement,
  poseTunnelError,
  poseUnknownIdentity,
  poseBlock,
  poseServiceDown,
  liftBlock,
  liftCause,
  poseClosure,
  poseMediumBack,
  poseFiledByHand,
  poseKeptNewer,
  poseFiled,
  seasonRecovery: {
    beforeAsk: poseBeforeAsk,
    searching: (title, season) => poseSeasonAt(title, season, SEARCHING),
    blocked: poseSeasonBlocked,
    arrived: poseSeasonArrived,
    automatic: poseAutomatic,
    ended: poseSeasonEnded,
    shelved: poseSeasonShelved,
    releaseTried: poseReleaseTried,
  },
  sameItem,
  placeAtPlexCheck,
  placeInEnrichment,
  confirmInPlex: (title) => {
    confirmInPlex(title);
    emit("ItemProgressed", { step: "plex", item: title, status: "verified" });
    return true;
  },
};
