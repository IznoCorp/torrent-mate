// What Système has to say — the number the menu button and the drawer's entry
// carry.
//
// TWO FAMILIES, BOTH COUNTED. The maintenance facts the locks read names — a
// lock whose process is gone, a sweep that has not finished, temporary entries
// a crash left behind — AND the machine's faults: a service that stopped
// answering, a dependency that is down. Counting the first alone would keep
// the badge to what one can DO from Maintenance and stay silent on a machine
// that is unwell, which is the reading that was refused.
//
// ONE DERIVATION WITH THE PAGE. The answers are the ones the page draws, from
// the same cache, and the simulated fault is replayed through the same words
// the page replays it with (`./fault`): what the page shows in alert is what
// the badge counts.
//
// IT COUNTS WITHOUT RIGHTS. No right exists yet; when one does, a term counts
// only for an account the right opens its page to — the machine's faults under
// Système's, the maintenance facts under Maintenance's — and a row the account
// cannot open adds nothing and asks for nothing.
import i18next from "i18next";

import type { components } from "../../contract/types";
import type { Schemas } from "../../lib/contract-schemas";
import { sharedQueryClient } from "../../lib/query-client";
import { store } from "../../lib/store-access";
import { serviceDownWords, withOneRowDown } from "./fault";
import { useLocks } from "./locks-queries";
import { useDependencies, useDisks, useIndexHealth, useServices } from "./queries";
import { factTone } from "./state-words";

type Fact = Schemas["Fact"];
type Locks = components["schemas"]["Locks"];

// The three answers, by the addresses their reads are keyed on.
const LOCKS_KEY = ["/api/v1/maintenance/locks"];
const SERVICES_KEY = ["/api/v1/system/services"];
const DEPENDENCIES_KEY = ["/api/v1/system/dependencies"];
const DISKS_KEY = ["/api/v1/maintenance/disks"];
const INDEX_KEY = ["/api/v1/maintenance/index-health"];

// The contract's tone for a fact that is wrong, and its sweep status for « not
// counted yet ».
const ALERT = "alert";
const WARNING = "warning";
const SWEEP_PENDING = "pending";

/**
 * How many things Système has to say.
 *
 * SYNCHRONOUS, over the query cache, as every badge is: the frame reads it at
 * render time, and `useSystemBadgeReads` is what keeps the three answers
 * observed.
 *
 * Returns:
 *     The maintenance facts and the machine's faults, counted; zero when
 *     nothing is wrong or nothing has answered yet.
 */
export function systemBadge(): number {
  // WHAT IS NOT AN ANSWER COUNTS NOTHING. The frame reads these three on every
  // page, and a cache entry may hold something other than the contract's shape
  // — a marker written over a read still pending — which a page that draws the
  // answer never meets, because it waits for the read first.
  const held = sharedQueryClient?.getQueryData<Partial<Locks>>(LOCKS_KEY);
  const locks = held?.pipelineLock && held.sweep ? (held as Locks) : undefined;
  const listAt = (key: string[]): Fact[] => {
    const answer = sharedQueryClient?.getQueryData<unknown>(key);
    return Array.isArray(answer) ? (answer as Fact[]) : [];
  };
  // A SECTION THAT CANNOT BE READ IS ONE FAULT, as the page draws it — one row,
  // « indisponible », in the alert tone — and never « nothing to report »: the
  // badge dropped when the disks or the index could not be read. What its last
  // answer held is not counted over it, since the page does not draw it.
  const unreadable = (key: string[]) => sharedQueryClient?.getQueryState(key)?.status === "error";
  const counted = (key: string[], tone: string) =>
    unreadable(key) ? 1 : listAt(key).filter((fact) => factTone(fact) === tone).length;
  const services = listAt(SERVICES_KEY);
  const dependencies = listAt(DEPENDENCIES_KEY);
  const drawn = store.read().state.fault === true
    ? withOneRowDown(services, serviceDownWords((key) => i18next.t(key)))
    : services;
  const maintenance = locks
    ? [
        locks.pipelineLock.stale,
        locks.sweep.status === SWEEP_PENDING,
        locks.sweep.status !== SWEEP_PENDING && locks.sweep.orphans.length > 0,
      ].filter(Boolean).length
    : 0;
  const faults = (unreadable(SERVICES_KEY) ? 1 : drawn.filter((fact) => factTone(fact) === ALERT).length)
    + counted(DEPENDENCIES_KEY, ALERT);
  // A DISK NEARLY FULL AND AN INDEX ANOMALY COUNT TOO (L24, OPEN 2 = A), each
  // read on the fact's own tone, never on its words.
  const care = counted(DISKS_KEY, WARNING) + counted(INDEX_KEY, WARNING);
  return maintenance + faults + care;
}

/**
 * Observes the three answers `systemBadge` derives from, for as long as the
 * frame draws Système's row.
 */
export function useSystemBadgeReads(): void {
  useLocks();
  useServices();
  useDependencies();
  useDisks();
  useIndexHealth();
}
