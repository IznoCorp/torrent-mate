// What Système asks the server for.
//
// SEVEN READS, ONE SURFACE. The page draws the services, the schedulers, the
// disks, the index's health, the dependencies, the errors and the last runs —
// seven resources answering seven questions, and one « everything about the
// system » read would make a slow answer hold up the other six.
//
// THE SERVICE FAULT VARIANT STAYS IN THE ENGINE, and that is what the register
// says rather than a choice made here: `SERVICES_PANNE` is declared inside a
// named function and carries no class, so no seed derives from it and no
// operation answers it. Its SCHEDULER twin left with the family it mapped over:
// the healthy schedulers are the layer's answer now, so the overdue list is
// derived beside the list it alters (`./fault`). The page therefore reads one
// broken list from the engine and derives the other — a mixture, and a visible
// one, rather than a fixture quietly surviving its own removal.
import { useQuery } from "@tanstack/react-query";
import { read } from "../../lib/query-client";
import { toEngineShape } from "../../engine/engine-shape";
import type { Fact } from "../../lib/engine-drawing";
import type { CodeErrors, PipelineRun } from "./reference";
import { useTranslation } from "react-i18next";
import type { components } from "../../contract/types";

type RunHistory = components["schemas"]["RunHistory"];

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

/** The pipeline's status as the engine's markup reads it. */
type PipelineStatus = { state?: string; watcherEnabled?: boolean };

/** One rubric of the settings catalogue, in the engine's own field names. */
type SettingsTopic = { r: { f: string; c: string; brut: unknown }[] };

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
 * The last runs, as the pipeline recorded them.
 *
 * A PAGE NOW, and the rows the section draws are the ones carrying the
 * fixture's line: the list still draws that line rather than composing its own
 * from the counts, so a run with no line has nothing it could be drawn with
 * yet. That filter goes when the list composes the line.
 */
export const usePipelineHistory = () =>
  useQuery({
    queryKey: ["/api/pipeline/history"],
    queryFn: async () => {
      const history = (await read("/api/pipeline/history")) as RunHistory;
      const carried = history.runs.filter((run) => run.result !== undefined);
      return toEngineShape<PipelineRun[]>("EXECUTIONS", carried);
    },
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
      toEngineShape<PipelineStatus>("PIPELINE", await read("/api/pipeline/status")),
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
      toEngineShape<SettingsTopic[]>("SETTINGS", await read("/api/config/schema")),
  });
  if (topics === undefined) return undefined;
  const setting = topics
    .flatMap((topic) => topic.r)
    .find((one) => one.c === BOUND_KEY);
  // THE KEY DOES NOT EXIST YET, and the row says so rather than inventing one.
  // It is a DEMAND (§20-1 makes the bound « une variable de configuration
  // réglable »), so the catalogue answers nothing for it — and a settings seed
  // carrying a key no configuration file has is a seed the settings rule
  // refuses, rightly: what this interface lists is the REAL configuration.
  if (setting === undefined) return { identity: undefined, said: t("screens.system.boundOwed") };
  return {
    identity: `${setting.f}:${setting.c}`,
    said: setting.brut === null || setting.brut === undefined
      ? t("screens.system.boundUnset")
      : String(setting.brut),
  };
}
