// design/src/features/acquisition/add-screen.tsx
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
import { store, useStoreContent, useUiState, writeUiState } from "../../lib/store-access";
import { useProviderSearch } from "./search-queries";
import { actionButton, backAction, emptyNote, resultCount, screen, screenBar, scrollport, searchField, searchInput, section, viewSwitch, viewSwitchButton } from "../../ui/variants";
import { Disclosure } from "../../ui/disclosure";
import { SurfaceError } from "../../ui/state-surfaces";
import { AddFooter } from "./add-footer";
import {
  addForm,
  addRow,
  byIdentifier,
  byIdentifierBody,
  emptyNotePlace,
  identifyFolder,
  identifyNotice,
  identifierHint,
  providerSwitchPlace,
  refusalReason,
  resultList,
  suggestionChip,
  suggestions,
} from "../../features/acquisition/variants";
import { Markup } from "../../ui/markup";
import { bridge, panel, redraw, replaceAddress } from "../../lib/shell-doors";
import { addressSeam } from "../../lib/addresses";
import { entriesAbovePage } from "../../lib/navigation-entry";
import { baseTitle } from "../../lib/titles";
import { mediumCardMarkup } from "./card-markup";
import { addVerb } from "./add-label";
import { addedCount, beginVisit, isAdded, setVisitMode } from "./add-visit";
import { addById, type IdOutcome } from "./add-verbs";
import { ID_EXAMPLES, validId, type IdProvider } from "./id-examples";

type Mode = "follow" | "identify";

export function AddScreen() {
  const { q, mode: rawMode } = useSearch({ from: "/add" });
  const mode: Mode = rawMode === "identify" ? "identify" : "follow";
  const identify = mode === "identify";
  const query = q ?? "";
  const hasQuery = query !== "";
  // WHAT THE FIELD HOLDS IS THIS COMPONENT'S, written in the keystroke's own
  // event (B-690). The address is written too, but the router answers a task
  // later, and a controlled `<input>` whose state did not move in its event is
  // put BACK by React to the value it rendered: every keystroke rewrote the
  // field to the text before it, then to the new one. On an iPhone the first
  // letter came back to an empty field and iOS re-armed its capital — « star »
  // came out « STar ». Held here, the field never differs from what was typed,
  // so React writes nothing into it. An address that changes from ELSEWHERE (a
  // suggestion, a driven state) still reaches it: the text follows the query
  // whenever the query moves to a value this field did not type.
  const [typed, setTyped] = useState(query);
  const [heard, setHeard] = useState(query);
  if (query !== heard) {
    setHeard(query);
    if (query !== typed) setTyped(query);
  }

  // A FRESH VISIT PER OPENING, begun before the first row is drawn (B-340). What
  // it adds is recorded by the add verbs, which announce it with `store.touch()`
  // — a version bump this component subscribes to, since no `state` reference
  // changes with it.
  useState(beginVisit);
  setVisitMode(mode);
  useStoreContent((c) => c.version);
  const state = useUiState();
  const addKind = (state.addKind as string) ?? "Tout";
  const idProv = (state.idProv as IdProvider | undefined) ?? "TMDB";
  // What the identifier field holds, and whether its provider refuses it: an
  // IMDB identifier is « tt » and digits, a TMDB or TVDB one digits only.
  const [typedId, setTypedId] = useState("");
  const idRefused = typedId.trim() !== "" && !validId(idProv, typedId);
  const idReady = typedId.trim() !== "" && !idRefused;
  // What the last identifier asked came to, said under the field until the
  // field or the source changes; and whether an answer is still awaited.
  const [idOutcome, setIdOutcome] = useState<IdOutcome | null>(null);
  const [idAsking, setIdAsking] = useState(false);

  /** Asks the source for the identifier typed, and says what came of it (B-691). */
  async function submitId(): Promise<void> {
    setIdAsking(true);
    try {
      const outcome = await addById(idProv, typedId);
      setIdOutcome(outcome);
      if (outcome.kind === "added") setTypedId("");
    } finally {
      setIdAsking(false);
    }
  }
  // `recent`, the store's own key (`app/arrival.ts`): read as `recents` after
  // the English rename, it was always absent, and the empty screen lost the
  // searches its note says sit above it (B-314).
  const recents = (state.recent as string[]) ?? [];
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

  // « Voir mes suivis » CLOSES the screen (§ 16 rule 1) and sets the tab as a
  // setting: the entries above the page — this screen and a result's panel —
  // are given back in ONE traversal, and the page's own entry then takes the
  // tab, replaced. Stacking a second Acquisition over the screen left a Retour
  // that only undid the tab (the navigation lot, L4).
  function toFollows(): void {
    const entries = entriesAbovePage(addressSeam.homePage, String(store.read().state.page));
    panel.close(true);
    writeUiState({ acqTab: "now" });
    redraw();
    window.addEventListener("popstate", () => replaceAddress?.(), { once: true });
    bridge.rewind(entries);
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
          <span className={identifyFolder()}>{t("screens.add.identifyFolder")}</span>
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
          <div className={identifyNotice()} data-part="add/notice">
            <SurfaceError tone="info" part="notice">
              <b>
                {t("screens.add.identifyTitle", {
                  // french-ok: the INTERPOLATION placeholder, named by
                  // `identifyTitle` in fr.json — renaming this half alone
                  // leaves « Identifier « {{titre}} » » on screen.
                  titre: baseTitle(resolveTarget ?? ""),
                })}
              </b>
              {t("screens.add.identifyBody")}
            </SurfaceError>
          </div>
        ) : null}
        <div className={addForm()}>
          <div className={searchField()}>
            <Icon paths={icons.search} />
            <input
              className={searchInput()}
              type="search"
              // A SEARCH IS NOT A SENTENCE (B-690): no capital, no correction of a title.
              autoCapitalize="off"
              autoCorrect="off"
              id="addq"
              value={typed}
              placeholder={t("screens.add.searchPlaceholder")}
              aria-label={t("screens.add.searchAria")}
              onChange={(event) => {
                setTyped(event.target.value);
                go({
                  to: "/add",
                  search: {
                    q: event.target.value || undefined,
                    mode: identify ? "identify" : undefined,
                  },
                  replace: true,
                });
              }}
            />
          </div>
          <div className={addRow()}>
            <div className={viewSwitch()} data-part="view/switch">
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
                  className={viewSwitchButton({ size: "text" })}
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
            <div className={emptyNotePlace()}>
              <div className={emptyNote()} data-part="empty-state">
                <b>{t("screens.add.emptyTitle")}</b>
                {t("screens.add.emptyBody")}
              </div>
            </div>
          </>
        )}
        <div className={byIdentifier()} data-part="add/by-id">
        <Disclosure summary={identify ? t("screens.add.byIdIdentify") : t("screens.add.byIdAdd")}>
          <div className={byIdentifierBody()}>
            <div className={`${viewSwitch()} ${providerSwitchPlace()}`} data-part="view/switch">
              {["TMDB", "TVDB", "IMDB"].map((element) => (
                <button
                  key={element}
                  className={viewSwitchButton({ size: "text" })}
                  aria-pressed={idProv === element}
                  onClick={() => {
                    setIdOutcome(null);
                    writeUiState({ idProv: element });
                  }}
                >
                  {element}
                </button>
              ))}
            </div>
            <div className={searchField()}>
              <input
                className={searchInput()}
                id="byidv"
                // An identifier is typed as written (B-690).
                autoCapitalize="off"
                autoCorrect="off"
                // AN EXAMPLE THAT WORKS, in the source's own format (B-691): « 1234 »
                // served for TMDB and TVDB alike and named no medium at all.
                placeholder={t("screens.add.idExample", { id: ID_EXAMPLES[idProv] })}
                aria-label={t("screens.add.idAria", { prov: idProv })}
                value={typedId}
                onChange={(event) => {
                  setIdOutcome(null);
                  setTypedId(event.target.value);
                }}
              />
            </div>
            {/* NO REFUSAL BEFORE A CHARACTER IS TYPED, and none in a
                developer's words: the screen opened on « Identifiant refusé :
                « 12e34 » … Number() … » with the field empty. */}
            {idRefused ? (
              <p className={refusalReason()} data-part="add/id-refused">
                {t(idProv === "IMDB" ? "screens.add.idRefusedImdb" : "screens.add.idRefusedNumber", {
                  typed: typedId.trim(),
                  prov: idProv,
                })}
              </p>
            ) : idOutcome?.kind === "missing" ? (
              <p className={refusalReason()} data-part="add/id-missing">
                {t("screens.add.idMissing", { typed: typedId.trim(), prov: idProv })}
              </p>
            ) : idOutcome?.kind === "owned" ? (
              <p className={refusalReason()} data-part="add/id-owned">
                {t("screens.add.idOwned", { title: idOutcome.title })}
              </p>
            ) : !idReady ? (
              // WHY « AJOUTER » WAITS, said rather than left to a greyed button.
              <p className={identifierHint()} data-part="add/id-waiting">
                {t("screens.add.idWaiting", { prov: idProv })}
              </p>
            ) : idProv === "TVDB" ? (
              <p className={identifierHint()}>{t("screens.add.tvdbHint")}</p>
            ) : null}
            <button
              className={actionButton({ kind: "submit" })}
              data-part="add/id-submit"
              disabled={!idReady || idAsking}
              onClick={() => void submitId()}
            >
              {t("screens.add.add")}
            </button>
          </div>
        </Disclosure>
        </div>
        <AddFooter count={addedCount()} icons={icons} toFollows={toFollows} />
      </div>
    </section>
  );
}
