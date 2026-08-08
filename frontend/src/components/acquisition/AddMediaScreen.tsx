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

import { ArrowLeft, Search as SearchIcon, X } from "lucide-react";
import { useEffect, useRef, useState, type ReactElement, type SyntheticEvent, type UIEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { mediaSheetHref } from "@/lib/media-href";


import type { CreateFollowRequest, MediaSearchResult } from "@/api/acquisition";
import { EmptyState } from "@/components/ds/EmptyState";
import { MediaPoster } from "@/components/ds/MediaPoster";
import { ErrorState } from "@/components/ds/ErrorState";
import { actionWords, asMediaKind, FOLLOW_KIND_LABEL } from "@/components/acquisition/meta";
import { MqDialog } from "@/components/acquisition/MqDialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { useFollow, useFollowed, useMediaSearch } from "@/hooks/useAcquisition";

import { pushRecentSearch, readRecentSearches } from "./recentSearches";
import {
  buildIdFollowBody,
  lookupMedia,
  type FollowProvider,
} from "@/api/acquisition";

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
  const [searchParams, setSearchParams] = useSearchParams();

  // Search state — seeded from ?q= so a « Voir la fiche » round-trip restores
  // the search instead of silently dropping it (the results come back from
  // the query cache, keyed by this same string).
  const [draft, setDraft] = useState(() => searchParams.get("q") ?? "");
  const [query, setQuery] = useState(() => searchParams.get("q") ?? "");
  const [kind, setKind] = useState<KindFilter>("all");
  /** The scrolling results body — used to return to its top on a new list. */
  const bodyRef = useRef<HTMLDivElement | null>(null);

  // Session-local adds; the rendered « ✓ Suivi » state ALSO title-matches
  // the live follows list (maquette isFollowed) — see `done` at the button.
  const [followed, setFollowed] = useState<ReadonlySet<string>>(
    () => new Set(),
  );
  // Maquette .toast: the add confirmation lives INSIDE this screen (a global
  // toaster under the full-screen sheet is a confirmation nobody sees).
  // Auto-hides after 5 s; the close cross remains the real control.
  const [toastMsg, setToastMsg] = useState<string | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const showToast = (msg: string): void => {
    setToastMsg(msg);
    if (toastTimer.current != null) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => {
      setToastMsg(null);
    }, 5000);
  };
  // Count of items added this session (for the footer bar).
  const [addedCount, setAddedCount] = useState(0);

  // §5 replacement confirmation (already-owned film).
  const [confirmReplace, setConfirmReplace] =
    useState<MediaSearchResult | null>(null);

  // Closing RESETS the screen. It stays mounted (a Sheet), so its state
  // outlives the closing: « Voir mes suivis » left the last query in place
  // and it reappeared on the next opening (operator report). Every exit must
  // behave like the Back one. Reopening seeds itself from the URL, so a
  // deep-linked ?q= still opens on its results.
  const wasOpen = useRef(open);
  useEffect(() => {
    if (wasOpen.current && !open) {
      setDraft("");
      setQuery("");
      setKind("all");
      setAddedCount(0);
      setIdOpen(false);
      setIdValue("");
      setIdResult(null);
      setIdLookupError(null);
    }
    if (!wasOpen.current && open) {
      const q = searchParams.get("q") ?? "";
      setDraft(q);
      setQuery(q);
    }
    wasOpen.current = open;
  }, [open, searchParams]);

  // Add-by-ID state
  const [provider, setProvider] = useState<FollowProvider>("tvdb");
  const [idValue, setIdValue] = useState("");
  const [idOpen, setIdOpen] = useState(false);
  /** Movie or series — the lookup needs to know which endpoint to ask. */
  const [idKind, setIdKind] = useState<"movie" | "tv">("tv");
  /** The RESOLVED media, shown as a result card until the operator acts. */
  const [idResult, setIdResult] = useState<MediaSearchResult | null>(null);
  const [idLooking, setIdLooking] = useState(false);
  const [idLookupError, setIdLookupError] = useState<string | null>(null);

  const searchQuery = useMediaSearch(query, kind === "all" ? undefined : kind);

  // `.sugg` dedup source: a query that names an existing follow is a
  // shortcut to nowhere (its resbtn would read « ✓ Suivi »).
  const followedList = useFollowed();
  const followedTitles = new Set(
    (followedList.data?.items ?? []).map((i) => i.title.toLowerCase()),
  );
  // Follow identity, by PROVIDER ID — the only key that cannot confuse two
  // works. A title match alone declared « Dune » (1984) already followed
  // because « Dune » (2021) is, and hard-disabled its add button: the
  // operator could not follow the other film at all.
  const followedRefs = new Set<string>();
  for (const i of followedList.data?.items ?? []) {
    const { tmdb_id: tmdb, tvdb_id: tvdb } = i.media_ref;
    if (tmdb != null) followedRefs.add(`tmdb-${String(tmdb)}`);
    if (tvdb != null) followedRefs.add(`tvdb-${String(tvdb)}`);
  }
  const recents =
    query === ""
      ? readRecentSearches().filter((q) => !followedTitles.has(q.toLowerCase()))
      : [];
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

  /** Apply a query — shared by form submit and the `.sugg` shortcut chips
   *  (maquette: a shortcut that still leaves a gesture to make is not a
   *  shortcut — tapping a chip RUNS the search). */
  function applyQuery(q: string): void {
    setDraft(q);
    setQuery(q);
    // Honest .sugg source (§3.5c): only queries actually submitted here.
    if (q !== "") pushRecentSearch(q);
    // Mirror into the URL so the search survives leaving for a fiche and
    // coming back. Replace: refining a query is not a navigation step.
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (q === "") next.delete("q");
        else next.set("q", q);
        return next;
      },
      { replace: true },
    );
  }

  /** Submit the search — fire on validation only, never per keystroke. */
  function submit(e: SyntheticEvent): void {
    e.preventDefault();
    // Blur FIRST: submitting from the on-screen keyboard's « Entrée » left
    // the field focused, so the keyboard stayed up and covered the results
    // (tapping « Chercher » blurs by definition — the two paths must feel
    // the same).
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }
    applyQuery(draft.trim());
  }

  /** Follow a search result (or ask §5 confirmation for an owned film). */
  function follow(result: MediaSearchResult): void {
    // §5 replacement confirmation is a FILM rule: acquiring a film again
    // replaces the copy in place. A series is owned episode by episode —
    // following it adds tracking for the MISSING ones and replaces nothing,
    // so the film dialog would state something false about it. The « déjà en
    // médiathèque » badge still shows: that part IS true for both.
    if (result.already_owned && result.kind === "movie") {
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
        showToast(`« ${result.title} » ajouté au suivi`);
        setFollowed((prev) => new Set(prev).add(key));
        setAddedCount((c) => c + 1);
        // Keep the results visible so several media can be added in a row (§7).
        // The footer bar accumulates the count.
      },
    });
  }

  /** Resolve the add-by-ID form — it RESOLVES, it does not follow.
   *
   *  Operator, 2026-08-08: typing an id used to follow on submit, sight
   *  unseen and usually nameless. The id now becomes a normal result card;
   *  the add stays one deliberate tap on « Suivre » / « Ajouter ». */
  function handleLookupById(): void {
    if (idBody === null || provider === "imdb") return;
    setIdLookupError(null);
    setIdLooking(true);
    lookupMedia({
      provider,
      provider_id: Number(idValue.trim()),
      kind: idKind,
    })
      .then((found) => {
        setIdResult(found);
        setIdLookupError(null);
      })
      .catch(() => {
        // §8 — an id the provider does not know says so, instead of quietly
        // creating a nameless follow (which is exactly what used to happen).
        setIdResult(null);
        setIdLookupError(
          "Aucun média avec cet identifiant chez ce fournisseur.",
        );
      })
      .finally(() => {
        setIdLooking(false);
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
  // A by-id lookup renders through the SAME card as a search result: same
  // « Suivre »/« Ajouter », same done state, same §5 confirmation. Nothing
  // about the add is special-cased for ids.
  const results = idResult != null ? [idResult] : pages.flatMap((page) => page.results);
  // §8: the PROVIDER total, not the row count — five out of eighty-one
  // with no count reads as "that's all there is."
  const total = pages[0]?.total ?? 0;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        // Maquette .fiche: a FULL SCREEN that slides in from the right, with
        // its own « ‹ Retour » — never a low sheet (the keyboard eats half
        // the phone), never a close cross (leaving is the back gesture; the
        // open state lives in the history).
        side="right"
        className="mq h-dvh max-h-none w-full max-w-none gap-0 p-0 pb-[env(safe-area-inset-bottom)] flex flex-col"
        showCloseButton={false}
      >
        <SheetHeader className="p-0">
          <SheetTitle className="sr-only">Ajouter un média à suivre</SheetTitle>
          <SheetDescription className="sr-only">
            Recherchez un film ou une série, ou ajoutez-le directement par son
            identifiant.
          </SheetDescription>
          <div className="fichebar">
            <button
              type="button"
              aria-label="Retour"
              className="fback"
              onClick={() => {
                onOpenChange(false);
              }}
            >
              <ArrowLeft aria-hidden="true" />
              Retour
            </button>
          </div>
        </SheetHeader>

        {/* ── Search form (fixed, never scrolls) — maquette .addform ──── */}
        <form onSubmit={submit} className="addform">
          <label className="search">
            <SearchIcon aria-hidden="true" />
            <input
              id="add-media-search"
              type="search"
              role="searchbox"
              value={draft}
              onChange={(e) => {
                setDraft(e.target.value);
              }}
              placeholder="Titre (film ou série)"
              aria-label="Rechercher un média"
              autoComplete="off"
            />
          </label>
          <div className="addrow">
            <div className="pillscroll">
              {(["all", "tv", "movie"] as const).map((k) => (
                <button
                  key={k}
                  type="button"
                  className="pill"
                  aria-pressed={kind === k}
                  onClick={() => {
                    setKind(k);
                    // A new filter is a new list — read it from its top
                    // (operator: « on revient pas en haut de la liste »).
                    bodyRef.current?.scrollTo({ top: 0 });
                  }}
                >
                  {k === "all" ? "Tout" : k === "tv" ? "Séries" : "Films"}
                </button>
              ))}
            </div>
            <button type="submit" className="btnprimary">
              Chercher
            </button>
          </div>
        </form>

        {/* ── Scrolling body — maquette #addbody ─────────────────────── */}
        {/* Maquette #addbody: NO horizontal padding of its own — every child
            carries its maquette inset (.empty 20, .reslist 16, .sugg 20). */}
        <div
          ref={bodyRef}
          className="min-h-0 flex-1 overflow-y-auto"
          data-testid="search-results"
          onScroll={handleScroll}
        >
          {query === "" && idResult == null ? (
            /* Maquette idle state: what to do, and the one honesty rule of
               this screen, before anything has been asked. */
            <>
              <div className="empty addidle">
                <b>Cherchez un titre</b>
                Les fournisseurs ne sont interrogés qu&apos;à la validation —
                pas à chaque frappe.
              </div>
              {recents.length > 0 && (
                /* .sugg chips — honest shortcuts (§3.5c): this device's
                   recent searches, minus what is already followed. A tap
                   RUNS the search (maquette: a shortcut that leaves a
                   gesture to make is not a shortcut). */
                <div className="sugg">
                  {recents.map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => {
                        applyQuery(q);
                      }}
                    >
                      {q}
                    </button>
                  ))}
                </div>
              )}
            </>
          ) : searchQuery.isLoading ? (
            /* Maquette loading: three .skel shimmer cards in a busy reslist. */
            <div className="reslist" aria-busy="true">
              <p className="sr-only">Recherche en cours…</p>
              <div className="skel" />
              <div className="skel" />
              <div className="skel" />
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
            <div>
              {/* §8: provider total, not row count. */}
              <p className="rescount" data-testid="search-result-count">
                {results.length} résultat{results.length > 1 ? "s" : ""} affiché
                {results.length > 1 ? "s" : ""} sur {total} trouvé
                {total > 1 ? "s" : ""}
              </p>

              {/* Vertical list — each row carries year, kind, provider,
                  and a two-line overview so two homonyms are distinguishable
                  (§12: width is the scarce resource). */}
              <ul className="reslist" role="list">
                {results.map((result) => {
                  const key = `${result.provider}-${String(result.provider_id)}`;
                  // Maquette isFollowed: session adds OR the SAME work already
                  // followed — searching what you already follow answers
                  // « ✓ Suivi », not a second follow button. Identity is the
                  // provider id: a homonym is a different work, and marking it
                  // done would lock the operator out of adding it.
                  const done = followed.has(key) || followedRefs.has(key);
                  const words = actionWords(result.kind);
                  const kindLabel =
                    FOLLOW_KIND_LABEL[asMediaKind(result.kind)] ?? result.kind;
                  return (
                    <li key={key} className="res">
                      {/* Poster 54x81 (maquette .rp). It is a button: a search
                          result is an identified media, so it always has a
                          sheet, and §11 requires every media to lead to it. */}
                      <button
                        type="button"
                        className="rp"
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
                        <MediaPoster
                          title={result.title}
                          src={result.poster_url ?? null}
                          className="!h-full !w-full"
                        />
                      </button>
                      <div className="rb">
                        <p className="rt truncate">{result.title}</p>
                        <p className="rm">
                          {result.year != null ? `${String(result.year)} · ` : ""}
                          {kindLabel}
                          {" · "}
                          {providerLabel(result.provider)}
                        </p>
                        {result.overview && <p className="ro">{result.overview}</p>}
                        {/* Button FIRST, badge after (operator): the badge
                            appears on some rows and not others, and putting it
                            ahead of the button made the button dance down the
                            list. Fixed anchor, variable annotation. */}
                        <div className="ra">
                          {/* Operator directive (2026-08-08, overrides the
                              maquette's third « owned » look): the button has
                              exactly TWO states — solid primary « Suivre/
                              Ajouter », or OUTLINED success « ✓ Suivi/
                              ✓ Ajouté » once followed. Library ownership is
                              the badge's job; an owned media still confirms
                              the replacement on tap (§5). */}
                          <button
                            type="button"
                            className={`resbtn ${done ? "done" : ""}`}
                            disabled={done || followMut.isPending}
                            onClick={() => {
                              follow(result);
                            }}
                          >
                            {done ? words.added : words.add}
                          </button>
                          {result.already_owned && (
                            <span className="text-[length:var(--text-2xs)] text-warning">
                              Déjà en médiathèque
                            </span>
                          )}
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>

              {/* Infinite-scroll loading indicator — same .skel grammar,
                  reslist inset (the body no longer pads). */}
              {searchQuery.isFetchingNextPage && (
                <div aria-busy="true" className="flex flex-col gap-2.5 px-4 pt-2.5">
                  <p className="sr-only">Chargement de résultats supplémentaires…</p>
                  <div className="skel" />
                  <div className="skel" />
                  <div className="skel" />
                </div>
              )}
            </div>
          )}

          {/* ── Add-by-ID (collapsible) — maquette .byid accordion, INSIDE
              the scrolling body after the state content (idle, results and
              no-results all end on it in the maquette; loading shows the
              skeletons alone). */}
          {!searchQuery.isLoading && (
            <details
              className="byid"
              open={idOpen}
              onToggle={(e) => {
                setIdOpen((e.target as HTMLDetailsElement).open);
              }}
            >
              <summary
                role="button"
                aria-expanded={idOpen}
                aria-controls="acq-by-id-region"
              >
                Ajouter directement par identifiant
              </summary>
              <div
                id="acq-by-id-region"
                role="group"
                aria-label="Ajout par identifiant"
                className="byidin"
              >
                <div className="segmini">
                  {(["tvdb", "tmdb", "imdb"] as const).map((p) => (
                    <button
                      key={p}
                      type="button"
                      aria-pressed={provider === p}
                      onClick={() => {
                        setProvider(p);
                      }}
                    >
                      {p.toUpperCase()}
                    </button>
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
                  {/* The typed title is gone: the provider owns the name, and
                      a hand-typed one is how nameless follows happened. What
                      the lookup genuinely needs is film vs série. */}
                  <div
                    role="group"
                    aria-label="Nature du média"
                    className="segmini min-w-0 flex-1"
                  >
                    {(["tv", "movie"] as const).map((k) => (
                      <button
                        key={k}
                        type="button"
                        aria-pressed={idKind === k}
                        onClick={() => {
                          setIdKind(k);
                        }}
                      >
                        {k === "tv" ? "Série" : "Film"}
                      </button>
                    ))}
                  </div>
                  <button
                    type="button"
                    className="btnprimary w-full sm:w-auto sm:shrink-0"
                    disabled={idBody === null || provider === "imdb" || idLooking}
                    onClick={handleLookupById}
                  >
                    {idLooking ? "Recherche…" : "Chercher cet ID"}
                  </button>
                </div>
                {idLookupError != null && (
                  <p role="alert" className="text-xs text-danger">
                    {idLookupError}
                  </p>
                )}
                {provider === "imdb" && (
                  <p className="text-xs text-muted-foreground">
                    La recherche par identifiant IMDB n&apos;est pas encore
                    servie — utilisez TVDB ou TMDB, ou la recherche par titre.
                  </p>
                )}
              </div>
            </details>
          )}
        </div>

        {/* ── Footer bar — maquette .addfoot ─────────────────────────── */}
        {addedCount > 0 && (
          <div className="addfoot">
            <p>
              {addedCount} média{addedCount > 1 ? "s" : ""} ajouté
              {addedCount > 1 ? "s" : ""} au suivi
            </p>
            <button
              type="button"
              onClick={() => {
                // Canonical target — the legacy value costs a redirect render.
                void navigate("/acquisition?tab=suivis");
                onOpenChange(false);
              }}
            >
              Voir mes suivis →
            </button>
          </div>
        )}

        {/* ── §5 replacement confirmation — maquette .dlg, copy verbatim ── */}
        <MqDialog
          open={confirmReplace != null}
          title="Ce film est déjà en médiathèque"
          text={`« ${confirmReplace?.title ?? ""} » est déjà rangé. Le suivre relancera une acquisition dont le résultat REMPLACERA la version en place.`}
          okLabel="Remplacer"
          onOk={() => {
            if (confirmReplace != null) doFollow(confirmReplace);
            setConfirmReplace(null);
          }}
          onCancel={() => {
            setConfirmReplace(null);
          }}
        />
        {/* ── Maquette toast — in-screen confirmation ─────────────────── */}
        <div
          className={`mqtoast ${toastMsg != null ? "show" : ""}`}
          role="status"
          aria-atomic="true"
          aria-live="polite"
        >
          <span>{toastMsg ?? ""}</span>
          <button
            type="button"
            className="mqtoastclose"
            aria-label="Fermer la notification"
            onClick={() => {
              if (toastTimer.current != null) clearTimeout(toastTimer.current);
              setToastMsg(null);
            }}
          >
            <X aria-hidden="true" />
          </button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
