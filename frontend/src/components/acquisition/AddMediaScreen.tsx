/**
 * AddMediaScreen — the full-screen add-by-search + add-by-ID surface.
 *
 * Rebuilds the add flow (OBJ3) as a vertical-list full-screen Sheet, replacing
 * the horizontal-rail carousel that hid year/kind/overview — precisely what
 * separates two homonyms (§12: width is the scarce resource).
 *
 * Search fires on validation only (submit, never per keystroke). Results list
 * scrolls alone so the search field stays reachable with the keyboard up (§7).
 * The by-ID block reuses {@link buildIdFollowBody} for every validation rule.
 * After a successful follow the row's button flips and a footer bar reports the
 * count so several media can be added in a row.
 */

import { ChevronDown } from "lucide-react";
import {
  useState,
  type ReactElement,
  type SyntheticEvent,
  type UIEvent,
} from "react";
import { useNavigate } from "react-router-dom";

import { mediaSheetHref } from "@/lib/media-href";
import { toast } from "sonner";

import { cn } from "@/lib/utils";

import type { CreateFollowRequest, MediaSearchResult } from "@/api/acquisition";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { actionWords, asMediaKind, FOLLOW_KIND_LABEL } from "@/components/acquisition/meta";
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
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { useFollow, useMediaSearch } from "@/hooks/useAcquisition";
import {
  buildIdFollowBody,
  type FollowProvider,
} from "@/hooks/useFollowedPanel";

// ── Props ──────────────────────────────────────────────────────────────────

/** Props for {@link AddMediaScreen}. */
export interface AddMediaScreenProps {
  /** Whether the full-screen sheet is visible. */
  readonly open: boolean;
  /** Callback to close (or open) the sheet. */
  readonly onOpenChange: (open: boolean) => void;
}

// ── Helpers ────────────────────────────────────────────────────────────────

/** The optional kind filter over the search. */
type KindFilter = "all" | "movie" | "tv";

/**
 * Build the follow request body from a search result.
 *
 * Carries the candidate's card metadata (poster, overview, year) so the
 * watch-list card can render without a later provider call (OBJ3).
 */
function toFollowBody(result: MediaSearchResult): CreateFollowRequest {
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

/** French label for a provider token. */
function providerLabel(provider: string): string {
  return provider.toUpperCase();
}

// ── Component ──────────────────────────────────────────────────────────────

/**
 * AddMediaScreen — full-screen add-by-search + add-by-ID.
 *
 * A ``Sheet`` opened from the bottom that fills the viewport (``h-dvh``, not
 * the default ``max-h-[80vh]`` cap — the keyboard eats half the phone, and a
 * results list in 80vh is unreadable).  The search field stays fixed at the
 * top while only the results list scrolls.
 *
 * Args:
 *   props: {@link AddMediaScreenProps} — open state + close callback.
 *
 * Returns:
 *   The full-screen add surface.
 */
export function AddMediaScreen({
  open,
  onOpenChange,
}: AddMediaScreenProps): ReactElement {
  const navigate = useNavigate();

  // Search state
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<KindFilter>("all");

  // Session-local follow state (NOT an API cross-check — see Correction 3).
  const [followed, setFollowed] = useState<ReadonlySet<string>>(
    () => new Set(),
  );
  // Count of items added this session (for the footer bar).
  const [addedCount, setAddedCount] = useState(0);

  // §5 replacement confirmation (already-owned film).
  const [confirmReplace, setConfirmReplace] =
    useState<MediaSearchResult | null>(null);

  // Add-by-ID state
  const [provider, setProvider] = useState<FollowProvider>("tvdb");
  const [idValue, setIdValue] = useState("");
  const [idTitle, setIdTitle] = useState("");
  const [idOpen, setIdOpen] = useState(false);

  const searchQuery = useMediaSearch(query, kind === "all" ? undefined : kind);
  const followMut = useFollow();

  // ── By-ID helpers ────────────────────────────────────────────────────

  const idLabel =
    provider === "imdb"
      ? "Identifiant IMDB"
      : provider === "tmdb"
        ? "Identifiant TMDB"
        : "Identifiant TVDB";
  const idPlaceholder =
    provider === "imdb"
      ? "ex: tt0903747"
      : provider === "tmdb"
        ? "ex: 1399"
        : "ex: 255968";
  const trimmedId = idValue.trim();
  // Reuse buildIdFollowBody for every validation rule — it already encodes
  // the digits-only gate, the safe-integer check, and the IMDB tt… format
  // (ticket 250: Number() would coerce "12e34" into a bogus huge id).
  const numericIdOk = provider === "imdb" || /^[0-9]+$/.test(trimmedId);
  const idBody = numericIdOk ? buildIdFollowBody(provider, idValue) : null;
  const idInvalid = trimmedId !== "" && idBody === null;
  const idErrorText =
    provider === "imdb"
      ? "Identifiant IMDB invalide — format attendu : tt1234567."
      : "Identifiant invalide — entrez un nombre entier positif.";

  // ── Handlers ─────────────────────────────────────────────────────────

  /** Submit the search — fire on validation only, never per keystroke. */
  function submit(e: SyntheticEvent): void {
    e.preventDefault();
    setQuery(draft.trim());
  }

  /** Follow a search result (or ask §5 confirmation for an owned film). */
  function follow(result: MediaSearchResult): void {
    if (result.already_owned) {
      setConfirmReplace(result);
      return;
    }
    doFollow(result);
  }

  /** Execute the follow mutation for a search result. */
  function doFollow(result: MediaSearchResult): void {
    const key = `${result.provider}-${String(result.provider_id)}`;
    followMut.mutate(toFollowBody(result), {
      onSuccess: () => {
        toast.success(`« ${result.title} » ajouté au suivi`);
        setFollowed((prev) => new Set(prev).add(key));
        setAddedCount((c) => c + 1);
        // Keep the results visible so several media can be added in a row (§7).
        // The footer bar accumulates the count.
      },
    });
  }

  /** Submit the add-by-ID form. */
  function handleAddById(): void {
    if (idBody === null) return;
    const body = { ...idBody };
    if (idTitle.trim()) body.title = idTitle.trim();
    followMut.mutate(body, {
      onSuccess: (created) => {
        toast.success("Média ajouté au suivi");
        setIdValue("");
        setIdTitle("");
        setAddedCount((c) => c + 1);
        if (created.tvdb_unresolved) {
          toast.warning(
            "Série ajoutée, mais l'ID TVDB n'a pas pu être résolu — la détection d'épisodes est indisponible tant qu'un ID TVDB n'est pas fourni.",
          );
        }
      },
    });
  }

  /**
   * Fetch the next page as the list approaches its end.
   *
   * Distance-based rather than a "load more" button: on a phone the operator
   * is already swiping, and asking them to stop and hit a target breaks the
   * gesture (§12).
   */
  function handleScroll(e: UIEvent<HTMLDivElement>): void {
    const el = e.currentTarget;
    const remaining = el.scrollHeight - el.scrollTop - el.clientHeight;
    if (
      remaining < el.clientHeight &&
      searchQuery.hasNextPage &&
      !searchQuery.isFetchingNextPage
    ) {
      void searchQuery.fetchNextPage();
    }
  }

  // ── Derived data ─────────────────────────────────────────────────────

  const pages = searchQuery.data?.pages ?? [];
  const results = pages.flatMap((page) => page.results);
  // §8: the PROVIDER total, not the row count — five out of eighty-one
  // with no count reads as "that's all there is."
  const total = pages[0]?.total ?? 0;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="bottom"
        // Correction 2: h-dvh, not the default max-h-[80vh] cap —
        // the keyboard eats half the phone and a results list in 80vh
        // is exactly the failure §7 names. pb-safe kept from the base.
        className="h-dvh max-h-none flex flex-col pb-[env(safe-area-inset-bottom)]"
      >
        <SheetHeader>
          <SheetTitle>Ajouter un média</SheetTitle>
          <SheetDescription>
            Recherchez un film ou une série, ou ajoutez-le directement par son
            identifiant.
          </SheetDescription>
        </SheetHeader>

        {/* ── Search form (fixed, never scrolls) ─────────────────────── */}
        <form
          onSubmit={submit}
          className="flex flex-col gap-2 sm:flex-row sm:items-end"
        >
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <Input
              id="add-media-search"
              type="search"
              role="searchbox"
              value={draft}
              onChange={(e) => {
                setDraft(e.target.value);
              }}
              placeholder="Titre (film ou série)"
              aria-label="Rechercher un média"
            />
          </div>
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
              Chercher
            </Button>
          </div>
        </form>

        {/* ── Add-by-ID (collapsible) ────────────────────────────────── */}
        <details
          className="flex flex-col gap-2 rounded-lg border border-border p-3"
          open={idOpen}
          onToggle={(e) => {
            setIdOpen((e.target as HTMLDetailsElement).open);
          }}
        >
          <summary
            role="button"
            aria-expanded={idOpen}
            aria-controls="acq-by-id-region"
            className="flex cursor-pointer items-center gap-1.5 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            <ChevronDown
              className={cn(
                "size-3.5 transition-transform",
                idOpen ? "rotate-0" : "-rotate-90",
              )}
              aria-hidden="true"
            />
            ou ajouter directement par ID
          </summary>
          <div
            id="acq-by-id-region"
            role="group"
            aria-label="Ajout par identifiant"
            className="mt-2 flex flex-col gap-2"
          >
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
                <Label htmlFor="add-media-id">{idLabel}</Label>
                <Input
                  id="add-media-id"
                  type="text"
                  inputMode={provider === "imdb" ? "text" : "numeric"}
                  placeholder={idPlaceholder}
                  value={idValue}
                  aria-invalid={idInvalid ? true : undefined}
                  aria-describedby={idInvalid ? "add-media-id-error" : undefined}
                  onChange={(e) => {
                    setIdValue(e.target.value);
                  }}
                />
                {idInvalid && (
                  <p
                    id="add-media-id-error"
                    role="alert"
                    className="text-xs text-danger"
                  >
                    {idErrorText}
                  </p>
                )}
              </div>
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                <Label htmlFor="add-media-id-title">Titre (optionnel)</Label>
                <Input
                  id="add-media-id-title"
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
        </details>

        {/* ── Results — the ONLY scrolling region (§7) ────────────────── */}
        <div
          className="min-h-0 flex-1 overflow-y-auto"
          data-testid="search-results"
          onScroll={handleScroll}
        >
          {query === "" ? null : searchQuery.isLoading ? (
            <div className="flex flex-col gap-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <div
                  key={`sk-${String(i)}`}
                  className="flex items-center gap-3"
                >
                  <Skeleton className="h-[81px] w-[54px] shrink-0 rounded" />
                  <div className="flex flex-1 flex-col gap-1.5">
                    <Skeleton className="h-4 w-3/4" />
                    <Skeleton className="h-3 w-1/2" />
                    <Skeleton className="h-3 w-full" />
                    <Skeleton className="h-3 w-2/3" />
                  </div>
                </div>
              ))}
            </div>
          ) : searchQuery.isError ? (
            <ErrorState
              title="La recherche a échoué"
              {...(searchQuery.error instanceof Error
                ? {
                    // Wrapped: the raw ApiError starts with a bare status code
                    // and an English backend detail — machine text (NE-DOIT-PAS-4).
                    message: `La recherche a échoué (${searchQuery.error.message}). Réessayez, ou ajoutez par identifiant ci-dessous.`,
                  }
                : {})}
              onRetry={() => {
                void searchQuery.refetch();
              }}
            />
          ) : results.length === 0 ? (
            <EmptyState
              title="Aucun résultat"
              description={`Aucun résultat pour « ${query} ».`}
            />
          ) : (
            <div className="flex flex-col gap-2">
              {/* §8: provider total, not row count. */}
              <p
                className="text-xs text-muted-foreground"
                data-testid="search-result-count"
              >
                {results.length} résultat{results.length > 1 ? "s" : ""} affiché
                {results.length > 1 ? "s" : ""} sur {total} trouvé
                {total > 1 ? "s" : ""}
              </p>

              {/* Vertical list — each row carries year, kind, provider,
                  and a two-line overview so two homonyms are distinguishable
                  (§12: width is the scarce resource). */}
              <ul className="flex flex-col gap-3" role="list">
                {results.map((result) => {
                  const key = `${result.provider}-${String(result.provider_id)}`;
                  const done = followed.has(key);
                  const words = actionWords(result.kind);
                  const kindLabel =
                    FOLLOW_KIND_LABEL[asMediaKind(result.kind)] ?? result.kind;
                  return (
                    <li
                      key={key}
                      className="flex items-start gap-3 rounded-lg border border-border p-3"
                    >
                      {/* Poster 54x81. It is a button: a search result is an
                          identified media, so it always has a sheet, and §11
                          requires every media to lead to it. The poster rather
                          than the whole row, because the row already carries
                          the add action — nesting one control inside another is
                          invalid HTML and makes the tap target ambiguous. */}
                      <button
                        type="button"
                        className="shrink-0 leading-none"
                        aria-label={`Fiche de ${result.title}`}
                        onClick={() => {
                          void navigate(
                            mediaSheetHref({
                              provider: result.provider,
                              providerId: String(result.provider_id),
                              kind: result.kind === "tv" ? "tv" : "movie",
                            }),
                          );
                        }}
                      >
                        {result.poster_url ? (
                          <img
                            src={result.poster_url}
                            alt=""
                            className="h-[81px] w-[54px] rounded object-cover"
                            loading="lazy"
                          />
                        ) : (
                          <div className="flex h-[81px] w-[54px] items-center justify-center rounded bg-muted text-[length:var(--text-2xs)] text-muted-foreground">
                            N/A
                          </div>
                        )}
                      </button>
                      <div className="flex min-w-0 flex-1 flex-col gap-1">
                        <p className="truncate text-sm font-medium">
                          {result.title}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {result.year != null ? `${String(result.year)} · ` : ""}
                          {kindLabel}
                          {" · "}
                          {providerLabel(result.provider)}
                        </p>
                        {result.overview && (
                          <p className="line-clamp-2 text-xs text-muted-foreground">
                            {result.overview}
                          </p>
                        )}
                        <div className="mt-1 flex items-center gap-2">
                          {result.already_owned && (
                            <span className="text-[length:var(--text-2xs)] text-warning">
                              Déjà en médiathèque
                            </span>
                          )}
                          <Button
                            size="sm"
                            variant={done ? "outline" : "default"}
                            className="ml-auto"
                            disabled={done || followMut.isPending}
                            onClick={() => {
                              follow(result);
                            }}
                          >
                            {done ? (
                              words.added
                            ) : result.already_owned ? (
                              words.addAsk
                            ) : (
                              words.add
                            )}
                          </Button>
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>

              {/* Infinite-scroll loading indicator */}
              {searchQuery.isFetchingNextPage &&
                Array.from({ length: 3 }).map((_, i) => (
                  <div
                    key={`more-sk-${String(i)}`}
                    className="flex items-center gap-3"
                  >
                    <Skeleton className="h-[81px] w-[54px] shrink-0 rounded" />
                    <div className="flex flex-1 flex-col gap-1.5">
                      <Skeleton className="h-4 w-3/4" />
                      <Skeleton className="h-3 w-1/2" />
                      <Skeleton className="h-3 w-full" />
                    </div>
                  </div>
                ))}
            </div>
          )}
        </div>

        {/* ── Footer bar — count of added items ──────────────────────── */}
        {addedCount > 0 && (
          <div className="flex items-center justify-between border-t border-border px-1 pt-3">
            <p className="text-sm text-muted-foreground">
              {addedCount} média{addedCount > 1 ? "s" : ""} ajouté
              {addedCount > 1 ? "s" : ""}
            </p>
            <Button
              variant="link"
              size="sm"
              onClick={() => {
                // Canonical target — the legacy value costs a redirect render.
                void navigate("/acquisition?tab=suivis");
                onOpenChange(false);
              }}
            >
              Voir mes suivis →
            </Button>
          </div>
        )}

        {/* ── §5 replacement confirmation dialog ─────────────────────── */}
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
                relancera son acquisition puis REMPLACERA la version en place
                par la nouvelle une fois le pipeline terminé.
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
      </SheetContent>
    </Sheet>
  );
}
