// What Système asks the server for.
//
// SEVEN READS, ONE SURFACE. The page draws the services, the schedulers, the
// disks, the index's health, the dependencies, the errors and the last runs —
// seven resources answering seven questions, and one « everything about the
// system » read would make a slow answer hold up the other six.
//
// THE FAULT VARIANTS ARE NOT READS. The simulated fault is the interface's own
// replay of the healthy services and schedulers, derived beside the lists it
// alters (`./fault`) — no seed derives from it and no operation answers it.
import { useQuery } from "@tanstack/react-query";
import { read } from "../../lib/query-client";
import { toEngineShape } from "../../engine/engine-shape";
import type { Fact } from "../../lib/engine-drawing";
import type { CodeErrors, PipelineRun } from "./types";
import { useTranslation } from "react-i18next";
import type { components } from "../../contract/types";

type RunHistory = components["schemas"]["RunHistory"];
type RunDetail = components["schemas"]["RunDetail"];

/**
 * Reads one system resource.
 *
 * @param address The contract address.
 * @param family The fixture family its shape came from.
 * @returns The query, its answer already in the engine's names.
 */
// THE SETTING THE LEVERS DRAW, by the key its own file owns. Named once here
// so the row, the demand and the panel's address cannot drift apart.
const BOUND_KEY = "pipeline.tunnels.max_parallel";

/** The pipeline's status, in the contract's names. */
type PipelineStatus = components["schemas"]["Pipeline"];

/** One rubric of the settings catalogue, in the contract's names. */
type SettingsTopic = components["schemas"]["SettingsTopic"];

function useSystemRead<Result>(address: string, family: string) {
  return useQuery({
    queryKey: [address],
    queryFn: async () => toEngineShape<Result>(family, await read(address)),
  });
}

/** The services, and what each is doing. */
export const useServices = () =>
  useSystemRead<Fact[]>("/api/system/services", "SERVICES");

/** The schedulers, and when each next runs. */
export const useSchedulers = () =>
  useSystemRead<Fact[]>("/api/maintenance/schedulers", "SCHEDULERS");

/** The disks, and what is left on each. */
export const useDisks = () => useSystemRead<Fact[]>("/api/maintenance/disks", "DISKS");

/** The index's own health. */
export const useIndexHealth = () =>
  useSystemRead<Fact[]>("/api/maintenance/index-health", "INDEX");

/** What the engine depends on, and whether each answers. */
export const useDependencies = () =>
  useSystemRead<Fact[]>("/api/system/dependencies", "DEPENDENCIES");

/** What has gone wrong lately. */
export const useSystemErrors = () =>
  useSystemRead<CodeErrors>("/api/system/errors", "ERRORS");

/**
 * The last runs, a page of them, and whether the list can be trusted.
 *
 * THE WHOLE ANSWER, because `degraded` is part of it: a read that failed and
 * came back short is a fact about the list, and the section draws it above the
 * rows. The list composes its own line from the counts now, so nothing is
 * filtered out for want of a sentence to draw it with.
 */
export const usePipelineHistory = () =>
  useQuery({
    queryKey: ["/api/pipeline/history"],
    queryFn: async () => (await read("/api/pipeline/history")) as RunHistory,
  });

/**
 * One passage in full, by its identifier.
 *
 * UNDER THE HISTORY'S OWN KEY, so the veille's invalidation of the history
 * reaches it too: the list and the passage cannot show two truths about one
 * run. The shape is the contract's, the same one the veille reads it in.
 *
 * @param runUid The run's identifier.
 * @returns The query.
 */
export const useRun = (runUid: string) =>
  useQuery({
    queryKey: ["/api/pipeline/history", runUid],
    queryFn: async () => (await read(`/api/pipeline/history/${runUid}`)) as RunDetail,
  });

/**
 * What the pipeline is doing, and whether its automatic trigger is on.
 *
 * THE SAME KEY AND THE SAME SHAPE AS ARRIVÉES', deliberately: one address, one
 * cached answer. Two definitions of one key that shaped it differently would
 * hand whichever surface mounted second the other one's idea of the payload —
 * and the two would be right by turns. Arrivées is a FEATURE, so this is not
 * imported from it (invariant 7): it is written the same way, and the shape is
 * held by the contract both read through.
 */
export const usePipelineState = () =>
  useQuery({
    queryKey: ["/api/pipeline/status"],
    queryFn: async () =>
      read<PipelineStatus>("/api/pipeline/status"),
  });

/**
 * The bound on how many media may be handled at once, as the levers draw it.
 *
 * READ THROUGH THE OPERATION, never through the settings FEATURE (invariant 7):
 * a read on the contract is not a feature import, and the identity this returns
 * is the address of the setting's own panel, which is where it is edited.
 *
 * @returns Its identity and what it is worth, or undefined while the read is in
 *   flight — the section prints nothing it does not yet know.
 */
export function useBoundSetting(): { identity?: string; said: string } | undefined {
  const { t } = useTranslation();
  const { data: topics } = useQuery({
    queryKey: ["/api/config/schema"],
    queryFn: async () =>
      read<SettingsTopic[]>("/api/config/schema"),
  });
  if (topics === undefined) return undefined;
  const setting = topics
    .flatMap((topic) => topic.settings)
    .find((one) => one.key === BOUND_KEY);
  // THE KEY DOES NOT EXIST YET, and the row says so rather than inventing one.
  // It is a DEMAND (§20-1 makes the bound « une variable de configuration
  // réglable »), so the catalogue answers nothing for it — and a settings seed
  // carrying a key no configuration file has is a seed the settings rule
  // refuses, rightly: what this interface lists is the REAL configuration.
  if (setting === undefined) return { identity: undefined, said: t("screens.system.boundOwed") };
  return {
    identity: `${setting.file}:${setting.key}`,
    said: setting.raw === null || setting.raw === undefined
      ? t("screens.system.boundUnset")
      : String(setting.raw),
  };
}
