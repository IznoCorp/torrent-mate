/**
 * Mutation hook for "Relancer et terminer le pipeline" (continue, §5.2).
 *
 * Thin TanStack useMutation wrapper over :func:`continueMedia` that invalidates
 * every surface the continuation touches on success so the grid, the resolution
 * deck, and the Flow Board all reflect the continued item immediately.
 */

import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";

import { continueMedia, type ContinueResponse } from "@/api/client";
import { decisionsKeys } from "@/api/decisions";
import { pipelineStagesKeys } from "@/hooks/usePipelineStages";
import { stagingMediaKeys } from "@/hooks/useStagingMedia";

/**
 * Mutation hook for ``POST /api/staging/media/{id}/continue``.
 *
 * Invalidates staging, decisions, and pipeline stages on success so every
 * surface the continuation touches reflects the change without a manual
 * refresh.
 *
 * Returns:
 *   A TanStack mutation result; call ``mutate(mediaId)`` from a button.
 */
export function useContinueMedia(): UseMutationResult<
  ContinueResponse,
  Error,
  string
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (mediaId: string) => continueMedia(mediaId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: stagingMediaKeys.all });
      void queryClient.invalidateQueries({ queryKey: decisionsKeys.all });
      void queryClient.invalidateQueries({
        queryKey: pipelineStagesKeys.stages,
      });
    },
  });
}
