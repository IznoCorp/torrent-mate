/**
 * MediaSearchAdd — the add-by-search surface for the acquisitions screen (OBJ3).
 *
 * A title search (submit-on-enter, so a provider call never fires per keystroke)
 * with an optional Tout/Séries/Films filter, rendering results as poster
 * {@link MediaCard}s with a one-click "Suivre" action. Backed by the
 * ``GET /api/acquisition/search`` endpoint via {@link useMediaSearch}; following
 * reuses {@link useFollow}. Loading, error and empty states are all soigné.
 */

import { Search } from "lucide-react";
import { useState, type ReactElement, type SyntheticEvent } from "react";
import { toast } from "sonner";

import type { CreateFollowRequest, MediaSearchResult } from "@/api/acquisition";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { MediaCard } from "@/components/ds/MediaCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useFollow, useMediaSearch } from "@/hooks/useAcquisition";

/** The optional kind filter over the search. */
type KindFilter = "all" | "movie" | "tv";

/** Build the follow request body from a search result (provider → id field). */
function toFollowBody(result: MediaSearchResult): CreateFollowRequest {
  return result.provider === "tvdb"
    ? { tvdb_id: result.provider_id, title: result.title }
    : { tmdb_id: result.provider_id, title: result.title };
}

/**
 * MediaSearchAdd — search providers and follow media in one click.
 *
 * Returns:
 *   The add-by-search element.
 */
export function MediaSearchAdd(): ReactElement {
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<KindFilter>("all");
  const [followed, setFollowed] = useState<ReadonlySet<string>>(
    () => new Set(),
  );

  const searchQuery = useMediaSearch(query, kind === "all" ? undefined : kind);
  const followMut = useFollow();

  function submit(e: SyntheticEvent): void {
    e.preventDefault();
    setQuery(draft.trim());
  }

  function follow(result: MediaSearchResult): void {
    const key = `${result.provider}-${String(result.provider_id)}`;
    followMut.mutate(toFollowBody(result), {
      onSuccess: () => {
        toast.success(`« ${result.title} » ajouté au suivi`);
        setFollowed((prev) => new Set(prev).add(key));
      },
      onError: (err: unknown) => {
        toast.error(err instanceof Error ? err.message : "Échec de l'ajout");
      },
    });
  }

  const results = searchQuery.data?.results ?? [];

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
        <div className="flex flex-1 flex-col gap-1">
          <label
            htmlFor="acq-search"
            className="text-xs font-medium text-muted-foreground"
          >
            Rechercher un média à suivre
          </label>
          <Input
            id="acq-search"
            value={draft}
            onChange={(e) => {
              setDraft(e.target.value);
            }}
            placeholder="Titre (film ou série)"
          />
        </div>
        <div className="flex items-center gap-1 rounded-md border border-border p-0.5">
          {(["all", "tv", "movie"] as const).map((k) => (
            <Button
              key={k}
              type="button"
              size="sm"
              variant={kind === k ? "default" : "ghost"}
              onClick={() => {
                setKind(k);
              }}
            >
              {k === "all" ? "Tout" : k === "tv" ? "Séries" : "Films"}
            </Button>
          ))}
        </div>
        <Button type="submit">
          <Search className="size-4" aria-hidden="true" />
          Chercher
        </Button>
      </form>

      {query === "" ? (
        <EmptyState
          icon={Search}
          title="Recherchez un média"
          description="Tapez un titre puis validez pour trouver des films ou séries à suivre."
        />
      ) : searchQuery.isLoading ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={`sk-${String(i)}`} className="aspect-[2/3] w-full" />
          ))}
        </div>
      ) : searchQuery.isError ? (
        <ErrorState
          title="La recherche a échoué"
          {...(searchQuery.error instanceof Error
            ? { message: searchQuery.error.message }
            : {})}
          onRetry={() => {
            void searchQuery.refetch();
          }}
        />
      ) : results.length === 0 ? (
        <EmptyState
          title="Aucun résultat"
          description={`Aucun média trouvé pour « ${query} ».`}
        />
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {results.map((result) => {
            const key = `${result.provider}-${String(result.provider_id)}`;
            const done = followed.has(key);
            return (
              <MediaCard
                key={key}
                title={result.title}
                year={result.year ?? null}
                kind={result.kind === "tv" ? "tv" : "movie"}
                posterUrl={result.poster_url ?? null}
                overview={result.overview ?? null}
                footer={
                  <Button
                    size="sm"
                    variant={done ? "outline" : "default"}
                    className="w-full"
                    disabled={done || followMut.isPending}
                    onClick={() => {
                      follow(result);
                    }}
                  >
                    {done ? "Suivi ✓" : "Suivre"}
                  </Button>
                }
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
