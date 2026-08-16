// design/src/ecrans/ajout.tsx
// The second pilot: legacy `openAddScreen(query, mode)` (`refonte.html`) reborn
// as a real route (`/ajout`) and a final component. Markup is TRANSPLANTED,
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
//   - "suivi" mode (from the FAB) — the intent is to WATCH a medium: the
//     button says "Suivre" / "Ajouter", and an already-owned medium goes
//     through the replacement confirmation.
//   - "identifier" mode (from a resolution) — the intent is to add NOTHING:
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
// `/ajout`. Typing rewrites the address IN PLACE (`aller(..., remplacer:
// true)`, same discipline `aller()`'s own doc comment states) so keystrokes
// never stack history — R76's own rule, exercised here for the first time by
// a CONTROLLED input rather than a one-shot navigation.
import { useSearch } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
// Circular with coquille.tsx (it imports AjoutEcran from this file) and safe
// today for two reasons: `aller` is a hoisted function declaration there, so
// its binding is live before either module's body runs, and this module has
// no top-level side effect that could observe coquille.tsx mid-evaluation.
import { aller } from "../coquille";
import { ecrireEtat, useContenu, useEtat, useReferentiel } from "../donnees";

type Mode = "suivi" | "identifier";

// The exact shape `svgIcon(paths, strokeWidth)` produced as an HTML string —
// rebuilt as a real element so it composes with JSX. Same helper as
// `profil.tsx`'s, not shared between the two: a third migrated screen
// needing it is the signal to extract it, not a guess made here.
function Icone({
  paths,
  strokeWidth,
}: {
  paths: string;
  strokeWidth?: number;
}) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth || 2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      dangerouslySetInnerHTML={{ __html: paths }}
    />
  );
}

export function AjoutEcran() {
  const { q, mode: modeBrut } = useSearch({ from: "/ajout" });
  const mode: Mode = modeBrut === "identifier" ? "identifier" : "suivi";
  const identifier = mode === "identifier";
  const qEff = q ?? "";
  const hasQ = qEff !== "";

  // `state.added` is a Set MUTATED IN PLACE by the still-legacy cross-world
  // "add:N" panel act and the replace-confirm dialog (refonte.html) — both
  // bump the store's `version` without producing a new `etat` reference,
  // which `useEtat()` alone would not notice (`useSyncExternalStore`
  // compares the selected value by reference). Subscribing to `version`
  // directly forces this component to re-render on that bump too; the read
  // below then sees the mutated Set fresh, in the SAME render the version
  // change triggered.
  useContenu((c) => c.version);
  const etat = useEtat();
  const addKind = (etat.addKind as string) ?? "Tout";
  const idProv = (etat.idProv as string) ?? "TMDB";
  const recents = (etat.recents as string[]) ?? [];
  const added = etat.added as Set<number>;
  const resolveTarget = etat.resolveTarget as string | null;

  const { icons, baseTitle, SEARCH, cardHTML, addVerb, render } =
    useReferentiel();
  const { t } = useTranslation();

  function ecrire(patch: Record<string, unknown>): void {
    ecrireEtat(patch);
  }

  // Always invoked from INSIDE this screen — chercher() runs only while
  // AjoutEcran is mounted, which means the address already reads `/ajout`.
  // Routing it through `window.__ecrans.ajout()` (a PUSH, meant for arriving
  // here fresh from elsewhere — the FAB, a resolution's manual search)
  // stacked a second `/ajout` entry per search: the legacy engine never
  // pushed for a same-key re-render, and a screen already open should not
  // either — one "Retour" from a chip search used to leave the screen still
  // open, having only popped back onto an earlier `/ajout` entry. `aller()`
  // direct, with `remplacer: true`, keeps the sync with the legacy readers
  // (`state.addQ`/`state.addMode`) `window.__ecrans.ajout()` also performs,
  // without the push.
  function chercher(valeur: string): void {
    ecrire({ addQ: valeur, addMode: mode });
    aller({
      to: "/ajout",
      search: {
        q: valeur || undefined,
        mode: identifier ? "identifier" : undefined,
      },
      remplacer: true,
    });
  }

  // Leaving a ROUTER-OWNED screen back onto legacy ground is not a `back`
  // (however many entries deep the operator is, this always lands on the
  // right page) and not a `data-go` click either — that shared delegated
  // handler's own history handling (`closeScreen`, `pileEcrans`,
  // `__pont.remplacer`) is built for the LEGACY layer stack, which this
  // screen no longer belongs to. The router entry is REPLACED with the
  // destination — the same "the layer's entry becomes the arrival" semantics
  // `data-go`'s own comment describes, expressed as a router-owned replace
  // instead of a `__pont.remplacer` — and the legacy state is written +
  // rendered explicitly, since nothing subscribes the legacy `#view` to the
  // store automatically (see `render`'s own doc comment in donnees.ts).
  function verSuivis(): void {
    ecrire({ page: "acq", acqTab: "maintenant" });
    render();
    aller({
      to: "/",
      search: { page: "acq", tab: "maintenant" },
      remplacer: true,
    });
  }

  const filtres = SEARCH.results
    .map((r, i) => ({ r, i }))
    .filter(
      ({ r }) =>
        addKind === "Tout" || (addKind === "Films") === (r.k === "Film"),
    );
  const rows = filtres
    .map(({ r, i }) => {
      const fait = added.has(i);
      return cardHTML({
        t: r.t,
        k: r.k === "Film" ? "movie" : "show",
        s: `${r.y} · ${r.k} · TMDB`,
        overview: r.ov,
        chip: fait
          ? ["success", addVerb(r, i)]
          : r.owned
            ? [
                identifier ? "success" : "warning",
                t("screens.ajout.alreadyInLibrary"),
              ]
            : null,
        panel: `add:${i}`,
      });
    })
    .join("");

  return (
    <section className="screen open" data-cle={`ajout:${mode}`}>
      <div className="fichebar">
        <button className="fback" onClick={() => window.__pont.retour()}>
          <Icone paths={icons.left} />
          {t("screens.ajout.back")}
        </button>
        {identifier ? (
          <span
            style={{
              marginLeft: "auto",
              fontSize: "11px",
              color: "var(--muted-foreground)",
            }}
          >
            {t("screens.ajout.identifyFolder")}
          </span>
        ) : null}
      </div>
      <div className="port">
        {identifier ? (
          <div style={{ padding: "12px 14px 0" }}>
            <div
              className="surferr"
              style={{
                borderColor: "color-mix(in oklab,var(--info) 45%,transparent)",
                background: "color-mix(in oklab,var(--info) 8%,transparent)",
              }}
            >
              <b style={{ color: "var(--info)" }}>
                {t("screens.ajout.identifyTitle", {
                  titre: baseTitle(resolveTarget ?? ""),
                })}
              </b>
              {t("screens.ajout.identifyBody")}
            </div>
          </div>
        ) : null}
        <div className="addform">
          <div className="search">
            <Icone paths={icons.search} />
            <input
              type="search"
              id="addq"
              value={qEff}
              placeholder={t("screens.ajout.searchPlaceholder")}
              aria-label={t("screens.ajout.searchAria")}
              onChange={(event) =>
                aller({
                  to: "/ajout",
                  search: {
                    q: event.target.value || undefined,
                    mode: identifier ? "identifier" : undefined,
                  },
                  remplacer: true,
                })
              }
            />
          </div>
          <div className="addrow">
            <div className="segmini">
              {/* NOT interface copy: these three are the VALUES of
                  `state.addKind`, written to the legacy store, compared
                  against below (`addKind === "Tout"`, `=== "Films"`) and
                  initialised by the legacy engine itself. The datum is its own
                  label here, so it stays in the code with the rest of the data
                  contract — translating the render would only add a mapping
                  between a value and itself. */}
              {["Tout", "Séries", "Films"].map((element) => (
                <button
                  key={element}
                  aria-pressed={addKind === element}
                  onClick={() => ecrire({ addKind: element })}
                >
                  {element}
                </button>
              ))}
            </div>
            <button className="btnprimary" onClick={() => chercher(qEff)}>
              {t("screens.ajout.search")}
            </button>
          </div>
        </div>
        {hasQ ? (
          <>
            <p className="rescount">
              <b>{filtres.length}</b>{" "}
              {filtres.length > 1
                ? t("screens.ajout.resultPlural")
                : t("screens.ajout.result")}{" "}
              {filtres.length > 1
                ? t("screens.ajout.shownPlural")
                : t("screens.ajout.shown")}{" "}
              {t("screens.ajout.outOf")} <b>{SEARCH.total}</b>{" "}
              {SEARCH.total > 1
                ? t("screens.ajout.foundPlural")
                : t("screens.ajout.found")}
              {addKind !== "Tout"
                ? ` ${t("screens.ajout.filteredOn", { kind: addKind })}`
                : ""}
              {" — "}
              {t("screens.ajout.mostRelevant")}
            </p>
            <div
              className="reslist sec"
              dangerouslySetInnerHTML={{ __html: rows }}
            />
          </>
        ) : (
          <>
            <div className="sugg">
              {recents.map((recent) => (
                <button key={recent} onClick={() => chercher(recent)}>
                  {recent}
                </button>
              ))}
            </div>
            <div style={{ padding: "14px" }}>
              <div className="empty">
                <b>{t("screens.ajout.emptyTitle")}</b>
                {t("screens.ajout.emptyBody")}
              </div>
            </div>
          </>
        )}
        <details className="byid">
          <summary>
            {identifier
              ? t("screens.ajout.byIdIdentify")
              : t("screens.ajout.byIdAdd")}
          </summary>
          <div className="byidin">
            <div className="segmini" style={{ alignSelf: "flex-start" }}>
              {["TMDB", "TVDB", "IMDB"].map((element) => (
                <button
                  key={element}
                  aria-pressed={idProv === element}
                  onClick={() => ecrire({ idProv: element })}
                >
                  {element}
                </button>
              ))}
            </div>
            <div className="search">
              <input
                id="byidv"
                placeholder={idProv === "IMDB" ? "tt1234567" : "12e34"}
                aria-label={t("screens.ajout.idAria", { prov: idProv })}
              />
            </div>
            <p className="whyoff">
              {idProv === "IMDB" ? (
                <>
                  {t("screens.ajout.imdbBefore")} <code>tt</code>{" "}
                  {t("screens.ajout.imdbAfter")}
                </>
              ) : idProv === "TVDB" ? (
                t("screens.ajout.tvdbHint")
              ) : (
                <>
                  {t("screens.ajout.numberBefore")} <code>Number()</code>{" "}
                  {t("screens.ajout.numberAfter")}
                </>
              )}
            </p>
            <button
              className="btnprimary"
              disabled
              style={{ alignSelf: "flex-start", padding: "9px 16px" }}
            >
              {t("screens.ajout.add")}
            </button>
          </div>
        </details>
        {added.size > 0 ? (
          <div className="addfoot">
            <span>
              <b>{added.size}</b>{" "}
              {added.size > 1
                ? t("screens.ajout.mediaPlural")
                : t("screens.ajout.media")}{" "}
              {added.size > 1
                ? t("screens.ajout.addedPlural")
                : t("screens.ajout.added")}
            </span>
            <button onClick={verSuivis}>{t("screens.ajout.seeFollows")}</button>
          </div>
        ) : null}
      </div>
    </section>
  );
}
