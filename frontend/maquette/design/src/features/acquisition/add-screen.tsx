// design/src/screens/add.tsx
// The second pilot: legacy `openAddScreen(query, mode)` (`refonte.html@60530dbd8`) reborn
// as a real route (`/add`) and a final component. Markup is TRANSPLANTED,
// not translated — every tag and class below is one `refonte.html@60530dbd8`'s BLOCK 2
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
// follows the MODE the screen was opened with, carried in the URL.
//
// The FIRST router-owned search params: `q` and `mode` live in the address
// alone — the router is the single source of truth for as long as it reads
// `/add`. Typing rewrites the address IN PLACE (`go(..., replace: true)`,
// same discipline `go()`'s own doc comment states) so keystrokes never stack
// history — R76's own rule, exercised here for the first time by a CONTROLLED
// input rather than a one-shot navigation.
import { useEngineDrawing } from "../../lib/engine-drawing";
import { useSearch } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
// Circular with shell.tsx (it imports AddScreen from this file) and safe
// today for two reasons: `go` is a hoisted function declaration there, so
// its binding is live before either module's body runs, and this module has
// no top-level side effect that could observe shell.tsx mid-evaluation.
import { Icon } from "../../ui/icon";
import { go } from "../../lib/navigate";
import { useState } from "react";
import { useStoreContent, useUiState, writeUiState } from "../../lib/store-access";
import { useProviderSearch } from "./search-queries";
import { actionButton, backAction, emptyNote, resultCount, screen, screenBar, scrollport, searchField, searchInput, section, surfaceError } from "../../ui/variants";
import { AddFooter } from "./add-footer";
import {
  addForm,
  addRow,
  byIdentifier,
  byIdentifierBody,
  refusalReason,
  resultList,
  segmentSmall,
  suggestionChip,
  suggestions,
} from "../../features/acquisition/variants";
import { Markup } from "../../ui/markup";
import { bridge, redraw } from "../../lib/shell-doors";
import { baseTitle } from "../../lib/titles";
import { mediumCardMarkup } from "./card-markup";
import { addVerb } from "./add-label";
import { addedCount, beginVisit, isAdded, setVisitMode } from "./add-visit";

type Mode = "follow" | "identify";

export function AddScreen() {
  const { q, mode: rawMode } = useSearch({ from: "/add" });
  const mode: Mode = rawMode === "identify" ? "identify" : "follow";
  const identify = mode === "identify";
  const query = q ?? "";
  const hasQuery = query !== "";

  // A FRESH VISIT PER OPENING, begun before the first row is drawn (B-340). What
  // it adds is recorded by the add verbs, which announce it with `store.touch()`
  // — a version bump this component subscribes to, since no `state` reference
  // changes with it.
  useState(beginVisit);
  setVisitMode(mode);
  useStoreContent((c) => c.version);
  const state = useUiState();
  const addKind = (state.addKind as string) ?? "Tout";
  const idProv = (state.idProv as string) ?? "TMDB";
  const recents = (state.recents as string[]) ?? [];
  const resolveTarget = state.resolveTarget as string | null;

  const { icons } = useEngineDrawing();
  const { t } = useTranslation();

  // Always invoked from INSIDE this screen — search() runs only while
  // AddScreen is mounted, which means the address already reads `/add`.
  // Routing it through `window.__screens.add()` (a PUSH, meant for arriving
  // here fresh from elsewhere — the FAB, a resolution's manual search)
  // stacked a second `/add` entry per search, so `go()` replaces instead.
  function search(value: string): void {
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
  // handler's own history handling is built for the engine's layers, which
  // this screen does not belong to. The router entry is REPLACED with the
  // destination — the same "the layer's entry becomes the arrival" semantics
  // `data-go`'s own comment describes, expressed as a router-owned replace
  // instead of a `__bridge.remplacer` — and the legacy state is written +
  // rendered explicitly, since nothing subscribes the legacy `#view` to the
  // store automatically (see `render`'s own doc comment in data.ts).
  function toFollows(): void {
    writeUiState({ page: "acq", acqTab: "now" });
    redraw();
    // THE IDENTITY IS IN THE PATH AND THE STATE IS IN THE QUERY — D1, and this
    // function was the counter-example (B-051). It navigated to `/` with
    // `search: { page: "acq", tab: "now" }`: the page's identity travelling as
    // a query parameter, and to an address that is not even the acquisition
    // page — `/` is the root, which the boot SETTLES onto `/acquisition` with a
    // replace. So the destination was right only by way of a redirect, and the
    // key that named it was in the wrong half of the URL.
    //
    // `/acquisition` declares `SearchParams = { tab?: string }` and carries no
    // `page` at all, which is what the address model has said all along.
    go({
      to: "/acquisition",
      search: { tab: "now" },
      replace: true,
    });
  }

  // FROM THE CACHE (invariant 4). Nothing is drawn before it answers, and the
  // oracle measures at rest — which is where the answer is.
  // THE ROUTER'S OWN `q`: typing updates the address through `go()`, so any
  // other copy would answer for what the screen was opened with.
  const { data: SEARCH } = useProviderSearch(q ?? "");
  const filtered = (SEARCH?.results ?? [])
    .map((r, i) => ({ r, i }))
    .filter(
      ({ r }) =>
        addKind === "Tout" || (addKind === "Films") === (r.kind === "Film"),
    );
  const rows = filtered
    .map(({ r, i }) => {
      const done = isAdded(r);
      return mediumCardMarkup({
        title: r.title,
        k: r.kind === "Film" ? "movie" : "show",
        secondaryLine: `${r.year} · ${r.kind === "Film" ? t("common.film") : t("common.series")} · TMDB`,
        overview: r.overview,
        chip: done
          ? { tone: "success", text: addVerb(r) }
          : r.owned
            ? {
                tone: identify ? "success" : "warning",
                text: t("screens.add.alreadyInLibrary"),
              }
            : null,
        panel: `add:${i}`,
        poster: r.poster,
        ids: r.ids,
      });
    })
    .join("");

  return (
    <section
      className={screen({ open: true })}
      data-part="screen"
      data-open=""
      data-key={`add:${mode}`}
      aria-label={t("screens.add.landmark")}
    >
      <div className={screenBar()} data-part="screen/bar">
        <button className={backAction()} data-part="screen/back" onClick={() => bridge.back()}>
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
          its THREE named states — `acq-add-empty`, `acq-add-results` and
          `acq-identify` — were driven, captured and compared against zero
          regions (B-222). The anchor rides the scrollport it already has rather
          than a wrapper of its own: a new block element in a scroll container
          is a layout change, and this is a measurement being added, not a
          drawing being altered.

          WHAT THIS DOES NOT DO IS CLOSE B-139. The oracle measures a region's
          ROOT — this scrollport's box and computed style — not the elements
          inside it, so a button painted white deeper in the tree is still
          invisible to it. Writing that the region « is why B-139 survived » was
          a claim the instrument does not support, in a comment that will be
          read as current for years. What the region buys is that the screen is
          measured at all. */}
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
            <div className={segmentSmall()} data-part="segment-small">
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
            <button className={actionButton({ kind: "submit" })} onClick={() => search(query)}>
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
            <Markup
              className={`${resultList()} ${section()}`}
              data-part="result/list"
              html={rows}
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
            <div className={segmentSmall()} data-part="segment-small" style={{ alignSelf: "flex-start" }}>
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
              className={actionButton({ kind: "submit" })}
              disabled
              style={{ alignSelf: "flex-start", padding: "9px 16px" }}
            >
              {t("screens.add.add")}
            </button>
          </div>
        </details>
        <AddFooter count={addedCount()} icons={icons} toFollows={toFollows} />
      </div>
    </section>
  );
}
