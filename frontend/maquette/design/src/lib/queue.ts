// The staging queue, and what may be done to it.
//
// IT IS IN `lib/` BECAUSE TWO SURFACES CHANGE IT FOR THEIR OWN REASONS. Arrivées
// draws what is stuck, moving and settled; Acquisition draws what is takeable,
// blocked, in flight and done. The engine's own `leaveQueue` spanned all of
// them, and four modules read the lists — those two pages, the resolution
// screen, and the shell's own screen opener. L04's rule decides it: « one
// surface makes it change → `features/<that surface>/`; two surfaces for their
// own reasons → either it knows no domain, or it is two files. » It is neither:
// it is ONE resource that two surfaces read.
//
// INVARIANT 7 IS WHAT SETTLES WHERE IT GOES, and it is absolute: two features
// never import each other. Leaving it under `features/acquisition/` made
// Arrivées import it, which the boundaries guard refused — the same breach L07
// made three times, each because a surface needed a piece of another.
//
// AND INVARIANT 10 ALLOWS IT, in its own words: the count of domain words per
// directory is « refused upward, never an interdiction, so a shared component
// that genuinely needs a domain word is one reviewed line, not a wall ». This
// is that line. What it must not become is a place where anything shared ends
// up; it holds one resource, and it holds it because both its readers are pages.
//
// EVERY MUTATION ANSWERS THE FINGER BEFORE THE NETWORK DOES. That is the
// largest single lever on how native this feels, and it is not a library: a
// surface that waits for a round trip to acknowledge a tap feels like a web
// page, and no amount of animation later repairs it. Each one writes the cache
// first, remembers what it wrote over, and puts it back if the layer refuses.
import { useQuery, type QueryClient } from "@tanstack/react-query";
import { HELD, read, send } from "./query-client";
import { toEngineShape } from "../engine/engine-shape";
import type { QueueCard } from "./engine-queue";

/** The staging queue, as Arrivées and the deck both read it. */
export type Staging = {
  stuck: QueueCard[];
  moving: QueueCard[];
  settled: QueueCard[];
};

/** What is waiting to be acquired, and what already went. */
export type AcquisitionQueue = {
  takeable: QueueCard[];
  blocked: QueueCard[];
  inFlight: QueueCard[];
  notFound: QueueCard[];
  doneToday: QueueCard[];
};

// The cache, kept once the boot has made it, so the two answers below can be
// given OUTSIDE React. Both are asked from places React does not reach: the
// engine's document-level delegation, and the shell's own screen opener.
let heldClient: QueryClient | null = null;

/**
 * The folder a resolution screen opens on when nobody named one.
 *
 * THE SHELL'S OWN DEFAULT, and it used to read the engine's fixture. Two call
 * sites open the resolution with no argument — the deck's own state and the
 * « Résoudre → » act — and the engine answered with the first stuck folder.
 * That is one derivation of one question (§13), so it is answered here, where
 * the queue is.
 *
 * @returns The folder, or null when nothing is stuck.
 */
export function firstStuckFolder(): string | null {
  const scenario =
    String(window.__store?.read().state.scen ?? "") === "loaded" ? "loaded" : "";
  const staging = heldClient?.getQueryData<Staging>(stagingKey(scenario));
  const first = staging?.stuck[0]?.t;
  return typeof first === "string" ? first : null;
}

/**
 * The queue's lists, answered synchronously from the cache.
 *
 * WHAT STILL ASKS. The engine draws its own nav badges, its `__blocked` probe
 * and two « next folder » walks from click handlers that cannot await. They are
 * the same question the surfaces ask, so they read the same cache rather than a
 * copy — §13's « une seule dérivation par question », which a second world was
 * the standing way to break. It goes with the drawing at L13.
 *
 * @returns Every list, empty before the queries have answered.
 */
export function queueNow(): Staging & AcquisitionQueue {
  const scenario =
    String(window.__store?.read().state.scen ?? "") === "loaded" ? "loaded" : "";
  const staging = heldClient?.getQueryData<Staging>(stagingKey(scenario));
  const queue = heldClient?.getQueryData<AcquisitionQueue>(queueKey(scenario));
  return {
    stuck: staging?.stuck ?? [],
    moving: staging?.moving ?? [],
    settled: staging?.settled ?? [],
    takeable: queue?.takeable ?? [],
    blocked: queue?.blocked ?? [],
    inFlight: queue?.inFlight ?? [],
    notFound: queue?.notFound ?? [],
    doneToday: queue?.doneToday ?? [],
  };
}

/** The key the staging read is cached under, scenario included. */
export const stagingKey = (scenario: string) => ["/api/staging/media", scenario];

/** The key the acquisition queue is cached under, scenario included. */
export const queueKey = (scenario: string) => ["/api/acquisition/to-handle", scenario];

/**
 * What is sitting in staging: stuck, moving, settled.
 *
 * @param scenario Which world, as the harness's own dial names it.
 * @returns The query, its cards already in the engine's names.
 */
export function useStaging(scenario: string) {
  return useQuery({
    queryKey: stagingKey(scenario),
    queryFn: async () => {
      const parameters = new URLSearchParams(scenario ? { scenario } : {});
      const answer = await read<Record<string, unknown[]>>(
        "/api/staging/media", parameters);
      return {
        stuck: toEngineShape<QueueCard[]>("STUCK_REAL", answer.stuck),
        moving: toEngineShape<QueueCard[]>("MOVING", answer.moving),
        settled: toEngineShape<QueueCard[]>("SETTLED_REAL", answer.settled),
      } satisfies Staging;
    },
  });
}

/**
 * What is waiting to be acquired, and what already went.
 *
 * @param scenario Which world, as the harness's own dial names it.
 * @returns The query, its cards already in the engine's names.
 */
export function useAcquisitionQueue(scenario: string) {
  return useQuery({
    queryKey: queueKey(scenario),
    queryFn: async () => {
      const parameters = new URLSearchParams(scenario ? { scenario } : {});
      const answer = await read<Record<string, unknown[]>>(
        "/api/acquisition/to-handle", parameters);
      return {
        takeable: toEngineShape<QueueCard[]>("TAKEABLE", answer.takeable),
        blocked: toEngineShape<QueueCard[]>("BLOCKED", answer.blocked),
        inFlight: toEngineShape<QueueCard[]>("INFLIGHT", answer.inFlight),
        notFound: toEngineShape<QueueCard[]>("NOTFOUND_REAL", answer.notFound),
        doneToday: toEngineShape<QueueCard[]>("DONE_TODAY", answer.doneToday),
      } satisfies AcquisitionQueue;
    },
  });
}


/**
 * Removes one card from wherever it is queued, in the cache, at once.
 *
 * THE OPTIMISTIC HALF, written once because all three actions do the same thing
 * to the same two caches: a folder answered leaves the queue it was waiting in.
 * What each of them does NEXT differs, and that is their own callers' part.
 *
 * @param queryClient The cache.
 * @param scenario Which world the action happened in.
 * @param title The card's own title, which is how the queue keys one.
 * @returns What was in both caches before, so a refusal can put it back.
 */
function takeOutOfQueue(
  queryClient: QueryClient,
  scenario: string,
  title: string,
): { staging?: Staging; queue?: AcquisitionQueue } {
  const staging = queryClient.getQueryData<Staging>(stagingKey(scenario));
  const queue = queryClient.getQueryData<AcquisitionQueue>(queueKey(scenario));
  const without = (cards: QueueCard[]) => cards.filter((card) => card.t !== title);
  if (staging) {
    queryClient.setQueryData<Staging>(stagingKey(scenario), {
      ...staging, stuck: without(staging.stuck),
    });
  }
  if (queue) {
    queryClient.setQueryData<AcquisitionQueue>(queueKey(scenario), {
      ...queue, blocked: without(queue.blocked), takeable: without(queue.takeable),
    });
  }
  return { staging, queue };
}

/**
 * Puts back what an optimistic write moved, when the layer refuses.
 *
 * @param queryClient The cache.
 * @param scenario Which world.
 * @param held What was there before.
 */
function putBack(
  queryClient: QueryClient,
  scenario: string,
  held: { staging?: Staging; queue?: AcquisitionQueue },
): void {
  if (held.staging) queryClient.setQueryData(stagingKey(scenario), held.staging);
  if (held.queue) queryClient.setQueryData(queueKey(scenario), held.queue);
}

// THE TWO ADDRESSES THIS MODULE'S OPTIMISTIC WRITE SPANS.
//
// `takeOutOfQueue` removes the card from WHICHEVER of the two lists holds it
// and `putBack` restores both, so every path here — online or replayed —
// invalidates the pair. The list is declared HERE, where the two keys are built
// and where the two-key write is made, and not in the frame: these are domain
// addresses, and invariant 10 refuses those in `app/`. The frame reads the list
// without knowing what is in it.
//
// A PAIR IS SYMMETRIC. Its reader matches on EITHER end — reading only the
// first left a replayed `/api/acquisition/to-handle/…/take` never reaching
// staging, which is this constant's own defect in the other direction.
export const ADDRESSES_THAT_MOVE_TOGETHER: readonly (readonly string[])[] = [
  ["/api/staging/media", "/api/acquisition/to-handle"],
];

/**
 * Installs the queue's three actions, for the dying engine to call.
 *
 * WHY A SEAM RATHER THAN A HOOK. The engine's document-level delegation is what
 * a tap on a card reaches — that delegation is cross-cutting and belongs to L13
 * — so the verbs have to be reachable from outside React. It is the same
 * arrangement `window.__panel` and `window.__screens` already use, and it goes
 * the same way.
 *
 * THE ENGINE KEEPS ITS TOAST AND LOSES ITS WORLD. What each action DID — move a
 * card from one list to another — is the layer's now, and the cache is what the
 * surfaces read. Leaving the engine's own mutation in place beside this one
 * would be two truths about one queue.
 *
 * @param queryClient The cache the surfaces read.
 */
export function installQueueActions(queryClient: QueryClient): void {
  heldClient = queryClient;
  window.__queue = queueNow;

  const scenarioNow = () =>
    String((window.__store?.read().state.scen ?? "") === "loaded" ? "loaded" : "");

  const settle = async (title: string, outcome: string, choice?: string) => {
    const scenario = scenarioNow();
    const held = takeOutOfQueue(queryClient, scenario, title);
    let answer: unknown;
    try {
      answer = await send("POST", `/api/staging/media/${encodeURIComponent(title)}/continue`,
                          { outcome, ...(choice === undefined ? {} : { choice }) });
    } catch (refusal) {
      putBack(queryClient, scenario, held);
      void queryClient.invalidateQueries({ queryKey: stagingKey(scenario) });
      void queryClient.invalidateQueries({ queryKey: queueKey(scenario) });
      throw refusal;
    }
    // NOT ON THE HELD PATH. `send` answers `HELD` when the network would not
    // take the mutation: the optimistic write is the truth the operator is
    // looking at, and refreshing over it replaces it with server state that
    // does not contain the mutation — the action snapping back with no
    // explanation, minutes before it actually applies.
    if (answer === HELD) return;
    void queryClient.invalidateQueries({ queryKey: stagingKey(scenario) });
    void queryClient.invalidateQueries({ queryKey: queueKey(scenario) });
  };

  window.__queueActions = {
    resolve: (title, choice) => void settle(title, "resolved", choice),
    // IT ANSWERS WHETHER THE FOLDER WAS THERE, synchronously, because the
    // engine's own `actionLeave` did and its caller reads the answer. The
    // optimistic write is what makes that answerable without waiting: the
    // folder is either in a queue the cache holds, or it is not.
    leave: (title) => {
      const scenario = scenarioNow();
      const staging = queryClient.getQueryData<Staging>(stagingKey(scenario));
      const queue = queryClient.getQueryData<AcquisitionQueue>(queueKey(scenario));
      const queued = [
        ...(staging?.stuck ?? []),
        ...(queue?.blocked ?? []),
      ].some((card) => card.t === title);
      if (!queued) return false;
      void settle(title, "left");
      return true;
    },
    take: (title) => {
      const scenario = scenarioNow();
      const held = takeOutOfQueue(queryClient, scenario, title);
      void send("POST", `/api/acquisition/to-handle/${encodeURIComponent(title)}/take`)
        .catch((refusal) => {
          putBack(queryClient, scenario, held);
          throw refusal;
        })
        .then((outcome) => {
        // NOT ON THE HELD PATH. `send` answers `HELD` when the network would not
        // take the mutation: the optimistic write is the truth the operator is
        // looking at, and refreshing over it replaces it with server state that
        // does not contain the mutation — the action snapping back with no
        // explanation, minutes before it actually applies.
          if (outcome === HELD) return;
          // BOTH KEYS, because `takeOutOfQueue` writes to both. Invalidating
          // only the queue left staging holding the optimistic removal — the
          // asymmetry `ADDRESSES_THAT_MOVE_TOGETHER` names, present in the
          // ONLINE path that constant was written to mirror.
          void queryClient.invalidateQueries({ queryKey: stagingKey(scenario) });
          void queryClient.invalidateQueries({ queryKey: queueKey(scenario) });
        }, () => {
          // AND ON A REFUSAL, which the `.finally` this replaced also covered.
          void queryClient.invalidateQueries({ queryKey: stagingKey(scenario) });
          void queryClient.invalidateQueries({ queryKey: queueKey(scenario) });
        });
    },
  };
}

declare global {
  interface Window {
    /** The queue's lists, read synchronously by the dying engine. */
    __queue?: () => Record<string, { t?: unknown }[]>;
    /** The queue's three verbs, called by the dying engine's delegation. */
    __queueActions?: {
      resolve: (title: string, choice?: string) => void;
      leave: (title: string) => boolean;
      take: (title: string) => void;
    };
  }
}
