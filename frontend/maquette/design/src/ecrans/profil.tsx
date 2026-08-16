// design/src/ecrans/profil.tsx
// The pilot screen: legacy `openProfil(titre)` (the per-title quality-profile
// screen — resolution floor, required audio, two locks; NOT the account page
// at `?page=profil`, which stays legacy) reborn as a real route and a final
// component. Markup is TRANSPLANTED, not translated: every tag and class
// below is the one `refonte.html`'s BLOCK 2 CSS already targets
// (`.screen`, `.screen.open`, `.screen .port`, `.qgroup`, `.opt`, …), so the
// same stylesheet applies unchanged and the rule harness measures the same
// geometry it measured on the legacy `#screen`.
import { useParams } from "@tanstack/react-router";
import {
  ecrireEtat,
  useEtat,
  useReferentiel,
  type Release,
  type Resolution,
} from "../donnees";

type QualityProfile = {
  min_resolution: Resolution | null;
  required_audio: string[];
  exclude_3d: boolean;
  require_known_resolution: boolean;
};

// The exact shape `svgIcon(paths, strokeWidth)` produced as an HTML string —
// rebuilt as a real element so it composes with JSX, `paths` is still the
// SAME raw markup from `useReferentiel().icons`, injected verbatim (trusted:
// it is a fixed set of `<path>`/`<circle>` primitives defined in
// refonte.html, never user input).
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

// `retenus`: transplanted verbatim from `openProfil` — the SAME filter over
// the SAME mock release list, so the count on screen matches what the
// legacy screen showed for the same profile.
function compterRetenus(profil: QualityProfile, releases: Release[]): number {
  const ordre: Record<string, number> = { "720p": 0, "1080p": 1, "2160p": 2 };
  return releases.filter((release) => {
    if (
      profil.min_resolution &&
      ordre[release.res] < ordre[profil.min_resolution]
    )
      return false;
    if (profil.required_audio.length) {
      const tier =
        release.lang === "VOSTFR"
          ? "VOSTFR"
          : release.lang === "VO"
            ? "VO"
            : "VF";
      if (!profil.required_audio.includes(tier)) return false;
    }
    return true;
  }).length;
}

export function ProfilEcran() {
  const { titre: brut } = useParams({ from: "/profil/$titre" });
  // Defensive: `__ecrans.profil` already normalises on write, but an entry
  // reached by a typed/bookmarked URL did not necessarily go through it.
  const titre = brut.normalize("NFC");
  const etat = useEtat();
  const profil = etat.profil as QualityProfile;
  const { RELEASES, RESOS, AUDIOS, icons, baseTitle } = useReferentiel();
  const retenus = compterRetenus(profil, RELEASES);

  function ecrireProfil(patch: Partial<QualityProfile>): void {
    ecrireEtat({ profil: { ...profil, ...patch } });
  }

  function choisirResolution(reso: Resolution | null): void {
    ecrireProfil({ min_resolution: reso });
  }

  function basculerAudio(cle: string): void {
    const requises = profil.required_audio.includes(cle)
      ? profil.required_audio.filter((valeur) => valeur !== cle)
      : [...profil.required_audio, cle];
    ecrireProfil({ required_audio: requises });
  }

  function basculerVerrou(
    cle: "exclude_3d" | "require_known_resolution",
  ): void {
    ecrireProfil({ [cle]: !profil[cle] });
  }

  return (
    <section className="screen open" data-cle={`profil:${titre}`}>
      <div className="fichebar">
        <button className="fback" onClick={() => window.__pont.retour()}>
          <Icone paths={icons.left} />
          Retour
        </button>
        <span
          style={{
            marginLeft: "auto",
            fontSize: "11px",
            color: "var(--muted-foreground)",
          }}
        >
          {titre ? baseTitle(titre) : "profil par défaut"}
        </span>
      </div>
      <div className="port">
        <div className="body">
          <div className="note">
            <b>Corrigé après vérification du backend.</b> Ma première version de
            cet écran réglait des « sources acceptées » et des exclusions CAM/TS
            qui <em>n'existent pas</em> par suivi. Le{" "}
            <code>QualityProfile</code> réel n'a que les quatre champs
            ci-dessous. Le reste — les poids qui départagent — est global et vit
            déjà dans <code>/config ?tab=classement</code>.
          </div>

          <p className="qhint">
            Ce profil <b>filtre</b> : il élimine ce qui ne conviendra jamais. Il
            n'ordonne pas — ce qui survit est départagé par le classement
            global.
          </p>

          <div className="qgroup">
            <h2 className="h2">Résolution minimale</h2>
            <p className="qhint">
              Un plancher, pas une liste : tout ce qui est en dessous est
              écarté. « Aucun plancher » laisse passer les sources sans
              résolution lisible (REMUX, COMPLETE.BLURAY) que le classement note
              au mérite.
            </p>
            <p className="optkind">Un seul choix</p>
            <div
              className="optlist"
              role="radiogroup"
              aria-label="Résolution minimale"
            >
              <button
                className="opt radio"
                role="radio"
                aria-checked={profil.min_resolution === null}
                data-qres=""
                onClick={() => choisirResolution(null)}
              >
                <span className="mark" />
                <span className="lb">
                  Aucun plancher
                  <small>Aucune résolution n'est écartée</small>
                </span>
              </button>
              {RESOS.map((reso) => (
                <button
                  key={reso}
                  className="opt radio"
                  role="radio"
                  aria-checked={profil.min_resolution === reso}
                  data-qres={reso}
                  onClick={() => choisirResolution(reso)}
                >
                  <span className="mark" />
                  <span className="lb">
                    {reso} ou mieux
                    <small>
                      {reso === "720p"
                        ? "Écarte tout ce qui est sous 720p"
                        : reso === "1080p"
                          ? "Écarte le 720p et en dessous"
                          : "N'accepte que la 4K"}
                    </small>
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div className="qgroup">
            <h2 className="h2">Pistes audio exigées</h2>
            <p className="qhint">
              Aucune sélection = aucun filtre de langue. Une release doit porter{" "}
              <b>au moins une</b> des pistes cochées.
            </p>
            <p className="optkind">
              Plusieurs choix possibles
              {profil.required_audio.length === 0
                ? " — aucun coché = aucun filtre"
                : ""}
            </p>
            <div className="optlist">
              {AUDIOS.map(([cle, label]) => (
                <button
                  key={cle}
                  className="opt check"
                  role="checkbox"
                  aria-checked={profil.required_audio.includes(cle)}
                  data-qaud={cle}
                  onClick={() => basculerAudio(cle)}
                >
                  <span className="mark" />
                  <span className="lb">
                    {cle}
                    <small>{label}</small>
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div className="qgroup">
            <h2 className="h2">Deux verrous</h2>
            <div className="panel">
              <div className="kv reglage">
                <span>
                  Écarter la 3D
                  <br />
                  <span className="qhint">
                    Une release SBS / Over-Under est illisible sur un écran 2D.
                    Activé par défaut : c'est un plancher de correction, pas un
                    goût.
                  </span>
                </span>
                <button
                  className="switch"
                  role="switch"
                  aria-checked={profil.exclude_3d}
                  aria-label="Écarter la 3D"
                  data-qflag="exclude_3d"
                  onClick={() => basculerVerrou("exclude_3d")}
                />
              </div>
              <div className="kv reglage">
                <span>
                  Refuser une résolution illisible
                  <br />
                  <span className="qhint">
                    Par défaut on laisse passer : un nom non analysable est le
                    plus souvent un REMUX, pas un mauvais fichier.
                  </span>
                </span>
                <button
                  className="switch"
                  role="switch"
                  aria-checked={profil.require_known_resolution}
                  aria-label="Refuser une résolution illisible"
                  data-qflag="require_known_resolution"
                  onClick={() => basculerVerrou("require_known_resolution")}
                />
              </div>
            </div>
          </div>

          <div className="panel">
            <div className="kv">
              <span>Candidats retenus par ce profil</span>
              <span>
                {retenus} sur {RELEASES.length}
              </span>
            </div>
            <div className="kv">
              <span>Portée</span>
              <span>{titre ? "ce suivi seulement" : "tous les suivis"}</span>
            </div>
          </div>

          <button
            className="cfoot"
            data-toast="Dans l'app, ce bouton mènera à /config ?tab=classement — l'éditeur de classement existe déjà."
          >
            <Icone paths={icons.sort} />
            Poids du classement (global) →
          </button>

          <p className="rulenote">
            Un profil qui n'accepte plus rien se dit : la carte affichera «
            cherché, rien trouvé » avec la raison, jamais un silence (§8).
          </p>

          <div className="sheetacts">
            <button
              className="sact primary"
              data-toast="Profil enregistré — la prochaine recherche l'appliquera."
            >
              <Icone paths={icons.check} />
              Enregistrer
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
