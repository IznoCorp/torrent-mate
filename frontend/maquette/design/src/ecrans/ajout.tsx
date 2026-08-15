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
import { aller } from "../coquille";
import { useContenu, useEtat, useReferentiel } from "../donnees";

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

  function ecrire(patch: Record<string, unknown>): void {
    window.__magasin.ecrire(patch);
  }

  // Same-screen query changes (the "Chercher" button, a recent-search chip)
  // go through the public bridge rather than a bare `aller()`: it is what
  // keeps `state.addQ`/`state.addMode` — the transitional contract below —
  // in sync for the one remaining legacy reader on this path, exactly as a
  // fresh arrival from the FAB or a resolution's manual search already does.
  function chercher(valeur: string): void {
    window.__ecrans.ajout(valeur, mode);
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
            ? [identifier ? "success" : "warning", "Déjà en médiathèque"]
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
          Retour
        </button>
        {identifier ? (
          <span
            style={{
              marginLeft: "auto",
              fontSize: "11px",
              color: "var(--muted-foreground)",
            }}
          >
            identifier un dossier
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
                Identifier « {baseTitle(resolveTarget ?? "")} »
              </b>
              Vous ne créez PAS un suivi : vous dites au pipeline quel média est
              ce dossier. Il reprendra son scrape — renommage, métadonnées,
              affiches — puis le rangera en médiathèque.
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
              placeholder="Titre du film ou de la série"
              aria-label="Chercher un média à ajouter"
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
              Chercher
            </button>
          </div>
        </div>
        {hasQ ? (
          <>
            <p className="rescount">
              <b>{filtres.length}</b> résultat{filtres.length > 1 ? "s" : ""}{" "}
              affiché{filtres.length > 1 ? "s" : ""} sur <b>{SEARCH.total}</b>{" "}
              trouvé{SEARCH.total > 1 ? "s" : ""}
              {addKind !== "Tout" ? ` · filtré sur « ${addKind} »` : ""} — les
              plus pertinents d'abord.
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
                <b>Cherchez un titre.</b>
                Vos recherches récentes sont au-dessus. La recherche part à la
                validation, jamais à chaque frappe — sinon chaque lettre coûte
                un appel aux providers.
              </div>
            </div>
          </>
        )}
        <details className="byid">
          <summary>
            {identifier
              ? "Ou identifier par identifiant provider"
              : "Ou ajouter par identifiant"}
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
                aria-label={`Identifiant ${idProv}`}
              />
            </div>
            <p className="whyoff">
              {idProv === "IMDB" ? (
                <>
                  Un identifiant IMDB commence par <code>tt</code> suivi de
                  chiffres — « 12e34 » est refusé.
                </>
              ) : idProv === "TVDB" ? (
                "Un identifiant TVDB ne contient que des chiffres. Si TVDB ne le résout pas, le suivi sera créé mais la détection d'épisodes restera indisponible — et on vous le dira."
              ) : (
                <>
                  Identifiant refusé : « 12e34 » n'est pas un nombre —{" "}
                  <code>Number()</code> le lirait comme une notation
                  scientifique.
                </>
              )}
            </p>
            <button
              className="btnprimary"
              disabled
              style={{ alignSelf: "flex-start", padding: "9px 16px" }}
            >
              Ajouter
            </button>
          </div>
        </details>
        {added.size > 0 ? (
          <div className="addfoot">
            <span>
              <b>{added.size}</b> média{added.size > 1 ? "s" : ""} ajouté
              {added.size > 1 ? "s" : ""}
            </span>
            <button onClick={verSuivis}>Voir mes suivis →</button>
          </div>
        ) : null}
      </div>
    </section>
  );
}
