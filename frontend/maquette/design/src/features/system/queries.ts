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

/**
 * Reads one system resource.
 *
 * @param address The contract address.
 * @param family The fixture family its shape came from.
 * @returns The query, its answer already in the engine's names.
 */
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

/** The last runs, as the pipeline recorded them. */
export const usePipelineHistory = () =>
  useSystemRead<PipelineRun[]>("/api/pipeline/history", "EXECUTIONS");
