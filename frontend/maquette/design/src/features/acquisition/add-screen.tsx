// design/src/screens/add.tsx
// The second pilot: legacy `openAddScreen(query, mode)` (`refonte.html`) reborn
// as a real route (`/add`) and a final component. Markup is TRANSPLANTED,
// not translated — every tag and class below is one `refonte.html`'s BLOCK 2
// CSS already targets (`.screen`, `.addform`, `.addrow`, `.reslist`, `.byid`,
// `.addfoot`…), so the same stylesheet applies unchanged.
//
// A full SCREEN, not a bottom sheet: the keyboard eats half the phone. A
// VERTICAL result list, never a horizontal rail — a rail shows three
// posters and hides the year, the type and the synopsis, which is exactly
// what separates two homonyms. The "already known" state lives on a CHIP,
// and so does "done".
//
// One search, TWO verbs. The same screen serves two intentions that nothing
// must confuse:
//   - "follow" mode (from the FAB) — the intent is to WATCH a medium: the
//     button says "Suivre" / "Ajouter", and an already-owned medium goes
//     through the replacement confirmation.
//   - "identify" mode (from a resolution) — the intent is to add NOTHING:
//     it is to TELL the pipeline which medium a stuck folder is, so it
//     resumes its scrape. The button says "Associer", and an already-owned
//     medium is normal — it is the expected case.
// Sending the second into the first is a mistake of intent: it offers to
// add a follow where the operator wanted to unblock a folder. The verb
// follows the MODE the screen was opened with, carried in the URL now
// rather than in `state.addMode`.
//
// The FIRST router-owned search params: `q` and `mode` no longer live in the
// legacy `state.addQ` / `state.addMode` while this screen is open — the
// router is the single source of truth for as long as the address reads
// `/add`. Typing rewrites the address IN PLACE (`go(..., replace: true)`,
// same discipline `go()`'s own doc comment states) so keystrokes never stack
// history — R76's own rule, exercised here for the first time by a CONTROLLED
// input rather than a one-shot navigation.
import { useState } from "react";
import { useSearch } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
// Circular with shell.tsx (it imports AddScreen from this file) and safe
// today for two reasons: `go` is a hoisted function declaration there, so
// its binding is live before either module's body runs, and this module has
// no top-level side effect that could observe shell.tsx mid-evaluation.
import { Icon } from "../../ui/icon";
import { go } from "../../lib/navigate";
import { useAcquisitionReference } from "../../features/acquisition/reference";
import { useStoreContent, useUiState, writeUiState } from "../../lib/store-access";
import { useProviderSearch } from "./search-queries";
import { actionButton, backAction, emptyNote, resultCount, screen, screenBar, scrollport, searchField, searchInput, surfaceError } from "../../ui/variants";
import {
  addFooter,
  addFooterAction,
  addFooterDismiss,
  addForm,
  addRow,
  byIdentifier,
  byIdentifierBody,
  refusalReason,
  resultList,
  suggestionChip,
  suggestions,
} from "../../features/acquisition/variants";

type Mode = "follow" | "identify";

export function AddScreen() {
  const { q, mode: rawMode } = useSearch({ from: "/add" });
  const mode: Mode = rawMode === "identify" ? "identify" : "follow";
  const identify = mode === "identify";
  const query = q ?? "";
  const hasQuery = query !== "";

  // `state.added` is a Set MUTATED IN PLACE by the still-legacy cross-world
  // "add:N" panel act and the replace-confirm dialog (refonte.html) — both
  // bump the store's `version` without producing a new `state` reference,
  // which `useUiState()` alone would not notice (`useSyncExternalStore`
  // compares the selected value by reference). Subscribing to `version`
  // directly forces this component to re-render on that bump too; the read
  // below then sees the mutated Set fresh, in the SAME render the version
  // change triggered.
  useStoreContent((c) => c.version);
  const state = useUiState();
  const addKind = (state.addKind as string) ?? "Tout";
  const idProv = (state.idProv as string) ?? "TMDB";
  const recents = (state.recents as string[]) ?? [];
  const added = state.added as Set<number>;
  const resolveTarget = state.resolveTarget as string | null;

  const {
    icons,
    baseTitle,
    cardHTML,
    addVerb,
    render,
  } = useAcquisitionReference();
  const { t } = useTranslation();

  // THE BAR IS A NOTIFICATION AND IS DISMISSED, not a state of the screen
  // (operator, 2026-08-29). What is remembered is the count it was dismissed
  // AT, never a bare boolean: adding a further medium is a new announcement and
  // must be seen, and a boolean would swallow it. This is genuinely ephemeral
  // interface state — nothing server-side is copied here, which is what
  // invariant 4 refuses.
  const [dismissedAtCount, setDismissedAtCount] = useState<number | null>(null);

  // Always invoked from INSIDE this screen — search() runs only while
  // AddScreen is mounted, which means the address already reads `/add`.
  // Routing it through `window.__screens.ajout()` (a PUSH, meant for arriving
  // here fresh from elsewhere — the FAB, a resolution's manual search)
  // stacked a second `/add` entry per search: the legacy engine never
  // pushed for a same-key re-render, and a screen already open should not
  // either — one "Retour" from a chip search used to leave the screen still
  // open, having only popped back onto an earlier `/add` entry. `go()`
  // direct, with `replace: true`, keeps the sync with the legacy readers
  // (`state.addQ`/`state.addMode`) `window.__screens.ajout()` also performs,
  // without the push.
  function search(value: string): void {
    writeUiState({ addQ: value, addMode: mode });
    go({
      to: "/add",
      search: {
        q: value || undefined,
        mode: identify ? "identify" : undefined,
      },
      replace: true,
    });
  }

  // Leaving a ROUTER-OWNED screen back onto legacy ground is not a `back`
  // (however many entries deep the operator is, this always lands on the
  // right page) and not a `data-go` click either — that shared delegated
  // handler's own history handling (`closeScreen`, `screenStack`,
  // `__bridge.remplacer`) is built for the LEGACY layer stack, which this
  // screen no longer belongs to. The router entry is REPLACED with the
  // destination — the same "the layer's entry becomes the arrival" semantics
  // `data-go`'s own comment describes, expressed as a router-owned replace
  // instead of a `__bridge.remplacer` — and the legacy state is written +
  // rendered explicitly, since nothing subscribes the legacy `#view` to the
  // store automatically (see `render`'s own doc comment in data.ts).
  function toFollows(): void {
    writeUiState({ page: "acq", acqTab: "now" });
    render();
    go({
      to: "/",
      search: { page: "acq", tab: "now" },
      replace: true,
    });
  }

  // FROM THE CACHE (invariant 4). Nothing is drawn before it answers, and the
  // oracle measures at rest — which is where the answer is.
  // THE ROUTER'S OWN `q`, never `state.addQ`. The store's copy is the ENTRY
  // query and is stale by construction — the shell's own comment says so:
  // typing updates the ROUTER's search params through `go()`, and nothing
  // writes it back. Wiring the read to the store made the search answer for
  // what the screen was opened with and ignore every keystroke after it.
  const { data: SEARCH } = useProviderSearch(q ?? "");
  const filtered = (SEARCH?.results ?? [])
    .map((r, i) => ({ r, i }))
    .filter(
      ({ r }) =>
        addKind === "Tout" || (addKind === "Films") === (r.k === "Film"),
    );
  const rows = filtered
    .map(({ r, i }) => {
      const done = added.has(i);
      return cardHTML({
        t: r.t,
        k: r.k === "Film" ? "movie" : "show",
        s: `${r.y} · ${r.k === "Film" ? t("common.film") : t("common.series")} · TMDB`,
        overview: r.ov,
        chip: done
          ? ["success", addVerb(r, i)]
          : r.owned
            ? [
                identify ? "success" : "warning",
                t("screens.add.alreadyInLibrary"),
              ]
            : null,
        panel: `add:${i}`,
      });
    })
    .join("");

  return (
    <section
      className={`${screen()} open`}
      data-part="screen"
      data-open=""
      data-key={`add:${mode}`}
      aria-label={t("screens.add.landmark")}
    >
      <div className={screenBar()} data-part="screen/bar">
        <button className={backAction()} data-part="screen/back" onClick={() => window.__bridge.back()}>
          <Icon paths={icons.left} />
          {t("screens.add.back")}
        </button>
        {identify ? (
          <span
            style={{
              marginLeft: "auto",
              fontSize: "11px",
              color: "var(--color-muted-foreground)",
            }}
          >
            {t("screens.add.identifyFolder")}
          </span>
        ) : null}
      </div>
      {/* THE ONLY SCREEN THE ORACLE DID NOT MEASURE. Four of the five overlay
          screens carry a body region of their own; this one carried none, so
          its two named states were driven, captured and compared against zero
          regions — which is how a button the browser painted white survived
          every gate (B-139, B-222). The anchor rides the scrollport it already
          has rather than a wrapper of its own: a new block element in a scroll
          container is a layout change, and this is a measurement being added,
          not a drawing being altered. */}
      <div className={scrollport()} data-part="viewport" data-region="screen-add/body">
        {identify ? (
          <div style={{ padding: "12px 14px 0" }}>
            <div
              className={surfaceError()} data-part="surface-error" role="alert"
              style={{
                borderColor: "color-mix(in oklab,var(--color-info) 45%,transparent)",
                background: "color-mix(in oklab,var(--color-info) 8%,transparent)",
              }}
            >
              <b style={{ color: "var(--color-info)" }}>
                {t("screens.add.identifyTitle", {
                  // french-ok: the INTERPOLATION placeholder, named by
                  // `identifyTitle` in fr.json — renaming this half alone
                  // leaves « Identifier « {{titre}} » » on screen.
                  titre: baseTitle(resolveTarget ?? ""),
                })}
              </b>
              {t("screens.add.identifyBody")}
            </div>
          </div>
        ) : null}
        <div className={addForm()}>
          <div className={searchField()}>
            <Icon paths={icons.search} />
            <input
              className={searchInput()}
              type="search"
              id="addq"
              value={query}
              placeholder={t("screens.add.searchPlaceholder")}
              aria-label={t("screens.add.searchAria")}
              onChange={(event) =>
                go({
                  to: "/add",
                  search: {
                    q: event.target.value || undefined,
                    mode: identify ? "identify" : undefined,
                  },
                  replace: true,
                })
              }
            />
          </div>
          <div className={addRow()}>
            <div className="segmini" data-part="segment-small">
              {/* NOT interface copy: these three are the VALUES of
                  `state.addKind`, written to the legacy store, compared
                  against below (`addKind === "Tout"`, `=== "Films"`) and
                  initialised by the legacy engine itself. The datum is its own
                  label here, so it stays in the code with the rest of the data
                  contract — translating the render would only add a mapping
                  between a value and itself. */}
              {(
                [
                  // The VALUES of `state.addKind` — written to the legacy store,
                  // compared against below, initialised by the engine itself.
                  // The datum is not its own label any more: the label is read
                  // from the resource beside it, so the value can stay data.
                  ["Tout", "kindAll"],
                  // french-ok: a state VALUE, not the label beside it
                  ["Séries", "kindSeries"],
                  ["Films", "kindFilms"],
                ] as const
              ).map(([value, key]) => (
                <button
                  key={value}
                  aria-pressed={addKind === value}
                  onClick={() => writeUiState({ addKind: value })}
                >
                  {t(`screens.add.${key}`)}
                </button>
              ))}
            </div>
            <button className={`btnprimary ${actionButton()}`} onClick={() => search(query)}>
              {t("screens.add.search")}
            </button>
          </div>
        </div>
        {hasQuery ? (
          <>
            <p className={resultCount()} data-part="result/count">
              <b>{filtered.length}</b>{" "}
              {filtered.length > 1
                ? t("screens.add.resultPlural")
                : t("screens.add.result")}{" "}
              {filtered.length > 1
                ? t("screens.add.shownPlural")
                : t("screens.add.shown")}{" "}
              {t("screens.add.outOf")} <b>{SEARCH?.total ?? 0}</b>{" "}
              {(SEARCH?.total ?? 0) > 1
                ? t("screens.add.foundPlural")
                : t("screens.add.found")}
              {addKind !== "Tout"
                ? ` ${t("screens.add.filteredOn", { kind: addKind })}`
                : ""}
              {" — "}
              {t("screens.add.mostRelevant")}
            </p>
            <div
              className={`${resultList()} sec`}
              data-part="result/list"
              dangerouslySetInnerHTML={{ __html: rows }}
            />
          </>
        ) : (
          <>
            <div className={suggestions()}>
              {recents.map((recent) => (
                <button
                  key={recent}
                  className={suggestionChip()}
                  onClick={() => search(recent)}
                >
                  {recent}
                </button>
              ))}
            </div>
            <div style={{ padding: "14px" }}>
              <div className={emptyNote()} data-part="empty-state">
                <b>{t("screens.add.emptyTitle")}</b>
                {t("screens.add.emptyBody")}
              </div>
            </div>
          </>
        )}
        <details className={byIdentifier()} data-part="add/by-id">
          <summary>
            {identify
              ? t("screens.add.byIdIdentify")
              : t("screens.add.byIdAdd")}
          </summary>
          <div className={byIdentifierBody()}>
            <div className="segmini" data-part="segment-small" style={{ alignSelf: "flex-start" }}>
              {["TMDB", "TVDB", "IMDB"].map((element) => (
                <button
                  key={element}
                  aria-pressed={idProv === element}
                  onClick={() => writeUiState({ idProv: element })}
                >
                  {element}
                </button>
              ))}
            </div>
            <div className={searchField()}>
              <input
                className={searchInput()}
                id="byidv"
                placeholder={idProv === "IMDB" ? "tt1234567" : "12e34"}
                aria-label={t("screens.add.idAria", { prov: idProv })}
              />
            </div>
            <p className={refusalReason()}>
              {idProv === "IMDB" ? (
                <>
                  {t("screens.add.imdbBefore")} <code>tt</code>{" "}
                  {t("screens.add.imdbAfter")}
                </>
              ) : idProv === "TVDB" ? (
                t("screens.add.tvdbHint")
              ) : (
                <>
                  {t("screens.add.numberBefore")} <code>Number()</code>{" "}
                  {t("screens.add.numberAfter")}
                </>
              )}
            </p>
            <button
              className={`btnprimary ${actionButton()}`}
              disabled
              style={{ alignSelf: "flex-start", padding: "9px 16px" }}
            >
              {t("screens.add.add")}
            </button>
          </div>
        </details>
        {added.size > 0 && added.size !== dismissedAtCount ? (
          <div className={addFooter()} data-part="add/foot">
            <span>
              <b>{added.size}</b>{" "}
              {added.size > 1
                ? t("screens.add.mediaPlural")
                : t("screens.add.media")}{" "}
              {added.size > 1
                ? t("screens.add.addedPlural")
                : t("screens.add.added")}
            </span>
            <button className={addFooterAction()} onClick={toFollows}>
              {t("screens.add.seeFollows")}
            </button>
            <button
              className={addFooterDismiss()}
              data-part="add/foot-dismiss"
              aria-label={t("screens.add.dismissAdded")}
              onClick={() => setDismissedAtCount(added.size)}
            >
              <Icon paths={icons.x} />
            </button>
          </div>
        ) : null}
      </div>
    </section>
  );
}
