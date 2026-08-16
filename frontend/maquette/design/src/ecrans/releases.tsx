// design/src/ecrans/releases.tsx
// Legacy `openReleases(title)` (`refonte.html`) — "choose another release" —
// reborn as a real route (`/releases/$titre`) and a final component. Markup
// is TRANSPLANTED, not translated: every tag, class and data-attribute below
// is the one the legacy screen drew, so the same stylesheet applies
// unchanged. `data-cle="releases:" + titre` is an identity this screen never
// had — the legacy `openScreen(html, undefined, () => openReleases(titre))`
// passed no `cle` at all — added here because a router-owned screen needs one
// to answer `.screen.open[data-cle^="releases:"]` the way every other
// migrated screen already does (see `coquille.tsx`'s dispatcher rewrite).
//
// The `.rel` rows are release CANDIDATES, not media cards — no poster, no
// `data-fiche`/`data-panel`. `data-prendre` (pick this release) and
// `data-profil` (open the quality profile) carry NO onClick: the
// document-level click delegation the legacy engine still runs is the seam
// this screen leans on, exactly as `fiche.tsx` and `profil.tsx`.
import { useParams } from "@tanstack/react-router";
import { useReferentiel } from "../donnees";

// Same helper as `fiche.tsx`'s, `profil.tsx`'s and `ajout.tsx`'s, still not
// shared: the extraction those files' comments call for is a follow-up of
// its own, not a silent scope add here.
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

export function ReleasesEcran() {
  const { titre: brut } = useParams({ from: "/releases/$titre" });
  // Defensive: `__ecrans.releases` already normalises on write, but an entry
  // reached by a typed/bookmarked URL did not necessarily go through it.
  const titre = brut.normalize("NFC");
  const { icons, baseTitle, RELEASES } = useReferentiel();

  return (
    <section className="screen open" data-cle={`releases:${titre}`}>
      <div className="fichebar">
        <button className="fback" onClick={() => window.__pont.retour()}>
          <Icone paths={icons.left} />
          Retour
        </button>{" "}
        <span
          style={{
            marginLeft: "auto",
            fontSize: "11px",
            color: "var(--muted-foreground)",
          }}
        >
          {baseTitle(titre)}
        </span>
      </div>
      <div className="port">
        <div className="body">
          <div className="note">
            <b>Écran neuf.</b> « Chercher une autre release » ne menait nulle
            part. Ce qui manquait n&apos;est pas une liste : c&apos;est{" "}
            <em>pourquoi</em> le moteur a classé ainsi — sans ça, choisir est un
            pari.
          </div>
          <p className="rescount" style={{ padding: 0 }}>
            <b>{RELEASES.length}</b> candidats retenus par le profil de qualité
            · dernière recherche il y a 12 min
          </p>
          {RELEASES.map((release, index) => (
            <article
              className={`rel${index === 0 ? " best" : ""}`}
              key={release.n}
            >
              <span className="rn">{release.n}</span>{" "}
              <span className="rt">
                <span
                  className={`chip ${
                    release.res === "2160p"
                      ? "success"
                      : release.res === "1080p"
                        ? "info"
                        : "neutral"
                  }`}
                >
                  {release.res}
                </span>{" "}
                <span className="chip">{release.src}</span>{" "}
                <span className="chip">{release.lang}</span>{" "}
                <span className="chip">{release.s} sources</span>{" "}
                <span className="chip">
                  {String(release.go).replace(".", ",")} Go
                </span>{" "}
                <span className="sc">score {release.sc}</span>
              </span>{" "}
              {index === 0 ? (
                <p className="qhint">
                  Retenue : meilleure résolution admise par le profil, langue
                  MULTi préférée, et le plus de sources à qualité égale.
                </p>
              ) : (
                ""
              )}
              <button
                className={`cfoot${index === 0 ? " solid" : ""}`}
                data-prendre={index}
              >
                {index === 0
                  ? "Reprendre celle-ci"
                  : "Prendre celle-ci à la place"}
              </button>
            </article>
          ))}
          <div className="empty">
            <b>Aucune ne convient ?</b>Élargir le profil de qualité fera revenir
            des candidats écartés — la liste dit ce qu&apos;elle a rejeté et
            pourquoi.
            <button
              className="cfoot"
              style={{ marginTop: "10px" }}
              data-profil={titre}
            >
              Ouvrir le profil de qualité →
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
