/**
 * Mutation hook for "Ignorer / nettoyer" (discard, §7).
 *
 * Thin TanStack useMutation wrapper over :func:`discardMedia` that invalidates
 * the staging grid on success so the discarded artifact disappears immediately.
 */

import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";

import { discardMedia, type DiscardResponse } from "@/api/client";
import { stagingMediaKeys } from "@/hooks/useStagingMedia";

/**
 * Mutation hook for ``POST /api/staging/media/{id}/discard``.
 *
 * Invalidates the staging read-model on success so the grid drops the
 * discarded artifact without a manual refresh.
 *
 * Returns:
 *   A TanStack mutation result; call ``mutate(mediaId)`` from a button.
 */
export function useDiscardMedia(): UseMutationResult<
  DiscardResponse,
  Error,
  string
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (mediaId: string) => discardMedia(mediaId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: stagingMediaKeys.all });
    },
  });
}
