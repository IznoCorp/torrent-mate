/**
 * MediaSearchAdd — the add-by-search surface for the acquisitions screen (OBJ3).
 *
 * A title search (submit-on-enter, so a provider call never fires per keystroke)
 * with an optional Tout/Séries/Films filter, rendering results as poster
 * {@link MediaCard}s with a one-click "Suivre" action. Backed by the
 * ``GET /api/acquisition/search`` endpoint via {@link useMediaSearch}; following
 * reuses {@link useFollow}. Loading, error and empty states are all soigné.
 */

import { Check, ChevronDown, Search } from "lucide-react";
import { useState, type ReactElement, type SyntheticEvent } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { mediaSheetHref } from "@/lib/media-href";
import { cn } from "@/lib/utils";

import type { CreateFollowRequest, MediaSearchResult } from "@/api/acquisition";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { MediaCard } from "@/components/ds/MediaCard";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useFollow, useMediaSearch } from "@/hooks/useAcquisition";
import {
  buildIdFollowBody,
  type FollowProvider,
} from "@/hooks/useFollowedPanel";

/** The optional kind filter over the search. */
type KindFilter = "all" | "movie" | "tv";

/** Build the follow request body from a search result (provider → id field). */
function toFollowBody(result: MediaSearchResult): CreateFollowRequest {
  // Carry the candidate's card metadata so the watch-list card can show a
  // poster / description / year without a later provider call (OBJ3). The kind
  // ('movie'|'show') starts the §5 film lifecycle server-side.
  const kind: "movie" | "show" = result.kind === "tv" ? "show" : "movie";
  const meta = {
    kind,
    ...(result.poster_url != null ? { poster_url: result.poster_url } : {}),
    ...(result.overview != null ? { overview: result.overview } : {}),
    ...(result.year != null ? { year: result.year } : {}),
  };
  return result.provider === "tvdb"
    ? { tvdb_id: result.provider_id, title: result.title, ...meta }
    : { tmdb_id: result.provider_id, title: result.title, ...meta };
}

/**
 * MediaSearchAdd — search providers and follow media in one click.
 *
 * Returns:
 *   The add-by-search element.
 */
export function MediaSearchAdd(): ReactElement {
  const navigate = useNavigate();
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<KindFilter>("all");
  const [followed, setFollowed] = useState<ReadonlySet<string>>(
    () => new Set(),
  );
  // §5 replacement confirmation target (an already-owned film).
  const [confirmReplace, setConfirmReplace] =
    useState<MediaSearchResult | null>(null);
  // Add-by-ID (#21): the same surface also accepts a TVDB/TMDB/IMDB id, so the
  // by-ID accordion no longer lives in FollowedPanel.
  const [provider, setProvider] = useState<FollowProvider>("tvdb");
  const [idValue, setIdValue] = useState("");
  const [idTitle, setIdTitle] = useState("");
  // The by-ID entry is collapsed by default so the add surface stays compact
  // (search is the primary path; add-by-ID is the occasional fallback).
  const [idOpen, setIdOpen] = useState(false);

  const searchQuery = useMediaSearch(query, kind === "all" ? undefined : kind);
  const followMut = useFollow();

  const idLabel =
    provider === "imdb"
      ? "ID IMDB"
      : provider === "tmdb"
        ? "ID TMDB"
        : "ID TVDB";
  const idPlaceholder =
    provider === "imdb"
      ? "ex: tt0903747"
      : provider === "tmdb"
        ? "ex: 1399"
        : "ex: 255968";
  const trimmedId = idValue.trim();
  // ACQUISITION-2 (ticket 250): Number() coerces scientific ("12e34") and hex
  // ("0x1f") notation into valid positive integers, so the numeric providers
  // gate on plain digits BEFORE buildIdFollowBody — otherwise "12e34" would
  // silently follow a bogus huge id.
  const numericIdOk = provider === "imdb" || /^[0-9]+$/.test(trimmedId);
  const idBody = numericIdOk ? buildIdFollowBody(provider, idValue) : null;
  // ACQUISITION-2 (ticket 250): a typed-but-invalid id must say WHY the
  // « Suivre » button stays disabled — never a silent no-op.
  const idInvalid = trimmedId !== "" && idBody === null;
  const idErrorText =
    provider === "imdb"
      ? "Identifiant IMDB invalide — format attendu : tt1234567."
      : "Identifiant invalide — entrez un nombre entier positif.";

  function handleAddById(): void {
    if (idBody === null) return;
    if (idTitle.trim()) idBody.title = idTitle.trim();
    // Error feedback is owned by the useFollow hook (X3) — a second onError
    // here would double-toast the same failure.
    followMut.mutate(idBody, {
      onSuccess: (created) => {
        toast.success("Média ajouté au suivi");
        setIdValue("");
        setIdTitle("");
        if (created.tvdb_unresolved) {
          toast.warning(
            "Série ajoutée, mais l'ID TVDB n'a pas pu être résolu — la détection d'épisodes est indisponible tant qu'un ID TVDB n'est pas fourni.",
          );
        }
      },
    });
  }

  function submit(e: SyntheticEvent): void {
    e.preventDefault();
    setQuery(draft.trim());
  }

  function follow(result: MediaSearchResult): void {
    // §5 replacement confirmation: a film already in the library must ask before
    // following — the pipeline will REPLACE the existing version once acquired.
    if (result.already_owned) {
      setConfirmReplace(result);
      return;
    }
    doFollow(result);
  }

  function doFollow(result: MediaSearchResult): void {
    const key = `${result.provider}-${String(result.provider_id)}`;
    // Error feedback is owned by the useFollow hook (X3) — no second onError.
    followMut.mutate(toFollowBody(result), {
      onSuccess: () => {
        toast.success(`« ${result.title} » ajouté au suivi`);
        setFollowed((prev) => new Set(prev).add(key));
        // Reset the search so the surface is ready for the next one (#19) —
        // the results collapse and the input clears.
        setDraft("");
        setQuery("");
      },
    });
  }

  const results = searchQuery.data?.results ?? [];

  return (
    <div className="flex flex-col gap-4">
      {/* Full-width input on mobile (its own line), the kind filter + Chercher on
          a second row; a single inline row on sm+. */}
      <form
        onSubmit={submit}
        className="flex flex-col gap-2 sm:flex-row sm:items-end"
      >
        <div className="flex min-w-0 flex-1 flex-col gap-1">
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
        {/* `flex-wrap` so at 390 px the « Chercher » button drops below the
            segmented kind filter instead of overflowing past the viewport
            (it reached 430 px pre-fix); on sm+ the row has room and stays
            inline. */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex flex-1 items-center gap-1 rounded-md border border-border p-0.5 sm:flex-none">
            {(["all", "tv", "movie"] as const).map((k) => (
              <Button
                key={k}
                type="button"
                size="sm"
                className="flex-1 sm:flex-none"
                variant={kind === k ? "default" : "ghost"}
                onClick={() => {
                  setKind(k);
                }}
              >
                {k === "all" ? "Tout" : k === "tv" ? "Séries" : "Films"}
              </Button>
            ))}
          </div>
          <Button type="submit" className="shrink-0">
            <Search className="size-4" aria-hidden="true" />
            Chercher
          </Button>
        </div>
      </form>

      {/* Add-by-ID (#21): the same surface accepts a TVDB/TMDB/IMDB id, so the
          by-ID entry no longer lives in a separate FollowedPanel accordion. */}
      <div className="flex flex-col gap-2 rounded-lg border border-border p-3">
        <button
          type="button"
          className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
          aria-expanded={idOpen}
          aria-controls="acq-by-id"
          onClick={() => {
            setIdOpen((prev) => !prev);
          }}
        >
          <ChevronDown
            className={cn(
              "size-3.5 transition-transform",
              idOpen ? "rotate-0" : "-rotate-90",
            )}
            aria-hidden="true"
          />
          ou ajouter directement par ID
        </button>
        {idOpen && (
          <div id="acq-by-id" className="flex flex-col gap-2">
            <div className="flex items-center gap-1 rounded-md border border-border p-0.5 sm:w-fit">
              {(["tvdb", "tmdb", "imdb"] as const).map((p) => (
                <Button
                  key={p}
                  type="button"
                  size="sm"
                  className="flex-1 sm:flex-none"
                  variant={provider === p ? "default" : "ghost"}
                  onClick={() => {
                    setProvider(p);
                  }}
                >
                  {p.toUpperCase()}
                </Button>
              ))}
            </div>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
              <div className="flex flex-col gap-1 sm:w-40">
                <Label htmlFor="acq-id">{idLabel}</Label>
                <Input
                  id="acq-id"
                  // ACQUISITION-2 (ticket 250): type="text" for ALL providers —
                  // a type="number" input reports value "" on badInput ("12e",
                  // "-") while the garbage stays visible, so the inline error
                  // never fired (silent no-op). inputMode keeps the mobile
                  // numeric keypad for TVDB/TMDB.
                  type="text"
                  inputMode={provider === "imdb" ? "text" : "numeric"}
                  placeholder={idPlaceholder}
                  value={idValue}
                  aria-invalid={idInvalid ? true : undefined}
                  aria-describedby={idInvalid ? "acq-id-error" : undefined}
                  onChange={(e) => {
                    setIdValue(e.target.value);
                  }}
                />
                {/* ACQUISITION-2: inline field error under the input. */}
                {idInvalid && (
                  <p
                    id="acq-id-error"
                    role="alert"
                    className="text-xs text-danger"
                  >
                    {idErrorText}
                  </p>
                )}
              </div>
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                <Label htmlFor="acq-id-title">Titre (optionnel)</Label>
                <Input
                  id="acq-id-title"
                  type="text"
                  placeholder="ex: Top Chef"
                  value={idTitle}
                  onChange={(e) => {
                    setIdTitle(e.target.value);
                  }}
                />
              </div>
              <Button
                className="w-full sm:w-auto sm:shrink-0"
                disabled={idBody === null || followMut.isPending}
                onClick={handleAddById}
              >
                {followMut.isPending ? "Ajout…" : "Suivre"}
              </Button>
            </div>
          </div>
        )}
      </div>

      {query === "" ? null : searchQuery.isLoading ? (
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
                onOpen={() => {
                  void navigate(
                    mediaSheetHref({
                      provider: result.provider,
                      providerId: String(result.provider_id),
                      kind: result.kind as "movie" | "tv",
                    }),
                  );
                }}
                footer={
                  <div className="flex w-full flex-col gap-1">
                    {result.already_owned && (
                      <span className="text-center text-[length:var(--text-2xs)] text-warning">
                        Déjà en médiathèque
                      </span>
                    )}
                    <Button
                      size="sm"
                      variant={done ? "outline" : "default"}
                      className="w-full"
                      disabled={done || followMut.isPending}
                      onClick={() => {
                        follow(result);
                      }}
                    >
                      {/* CONFIG-4 leftover (ticket 250): lucide Check, not a
                          raw ✓ glyph. */}
                      {done ? (
                        <span className="inline-flex items-center gap-1">
                          <Check className="size-4" aria-hidden="true" />
                          Suivi
                        </span>
                      ) : result.already_owned ? (
                        "Remplacer…"
                      ) : (
                        "Suivre"
                      )}
                    </Button>
                  </div>
                }
              />
            );
          })}
        </div>
      )}

      {/* §5 replacement confirmation dialog: the film is already in the library;
          following it will REPLACE the existing version once re-acquired. */}
      <Dialog
        open={confirmReplace != null}
        onOpenChange={(open) => {
          if (!open) setConfirmReplace(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remplacer la version en médiathèque ?</DialogTitle>
            <DialogDescription>
              « {confirmReplace?.title} » est déjà en médiathèque. Le suivre
              relancera son acquisition puis remplacera la version existante par
              la nouvelle une fois le pipeline terminé.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="ghost"
              onClick={() => {
                setConfirmReplace(null);
              }}
            >
              Annuler
            </Button>
            <Button
              onClick={() => {
                if (confirmReplace != null) doFollow(confirmReplace);
                setConfirmReplace(null);
              }}
            >
              Remplacer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
