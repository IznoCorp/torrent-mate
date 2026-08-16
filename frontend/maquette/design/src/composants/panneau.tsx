// design/src/composants/panneau.tsx
// The unique bottom-panel constructor, reborn as a component. Every panel
// in the legacy engine is built by ONE function (`panneauHTML`, refonte.html)
// from a plain descriptor of facts — never ready-made markup — and this
// component is that same constructor, transplanted: same tags, same
// classes, same data-attribute vocabulary, so the document-level click
// delegation the legacy engine still runs (`.sact[data-fiche]`,
// `.ep[data-ep]`, `.champ*[data-champ]`, …) keeps working unchanged. Not
// mounted anywhere yet — a later task wires `openSheet`/`__panneau` to it.
//
// Markup is TRANSPLANTED, not translated: React escapes text nodes
// natively, so there is no `escapeHtml` here — every plain string prop
// below is a JSX child or attribute value, which is already safe.
import { Fragment, type JSX } from "react";
import { useReferentiel, type Reglage, type Referentiel } from "../donnees";

// The exact shape `svgIcon(paths, strokeWidth)` produced as an HTML
// string — rebuilt as a real element so it composes with JSX. Same helper
// as `profil.tsx`'s and `ajout.tsx`'s, not shared between the three: this
// is now the third copy the extraction comment on those two warned about,
// but this task creates exactly one file — the extraction is a follow-up,
// not a silent scope add here.
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

// A `richText` segment: plain text, a mono/code aside (`{ m }`), or an
// emphasised aside (`{ e }`) — exactly the three shapes `richText` switches
// on in refonte.html.
export type Segment = string | { m: string } | { e: string };
export type Texte = string | Segment[];

function RichText({ valeur }: { valeur: Texte | null | undefined }) {
  if (valeur == null) return null;
  if (typeof valeur === "string") return <>{valeur}</>;
  return (
    <>
      {valeur.map((segment, index) =>
        typeof segment === "string" ? (
          <Fragment key={index}>{segment}</Fragment>
        ) : "m" in segment ? (
          <code key={index}>{segment.m}</code>
        ) : (
          <b key={index}>{segment.e}</b>
        ),
      )}
    </>
  );
}

function Puce({ puce }: { puce: [string, string] | null | undefined }) {
  if (!puce) return null;
  return <span className={`chip ${puce[0]}`}>{puce[1]}</span>;
}

// `posterBox`'s image-or-initials fallback, at panel size. `POSTERS` /
// `baseTitle` / `icons` / `initials` are the exact référentiel entries
// `posterBox` itself reads from (refonte.html), and this call carries no
// `opts` — the panel head never asks for the `exact` (no base-title
// fallback) variant.
function Portrait({ affiche }: { affiche: { t: string; k?: string } }) {
  const { POSTERS, baseTitle, icons, initials } = useReferentiel();
  const src = POSTERS[affiche.t] ?? POSTERS[baseTitle(affiche.t)];
  if (src) return <img src={src} alt="" loading="lazy" />;
  const iconPath =
    affiche.k === "movie"
      ? icons.film
      : affiche.k === "show"
        ? icons.tv
        : icons.clap;
  return (
    <span className="pfall">
      <Icone paths={iconPath} strokeWidth={1.25} />
      <b>{initials(affiche.t)}</b>
    </span>
  );
}

// An ACTION is `{ texte, icone, cible, ton, desactive, mention, infobulle }`
// — `cible` is a map of DATA ATTRIBUTES, never a handler and never markup;
// the click delegation reads those attributes, exactly as it does for a
// card. This component adds NO `onClick` of its own for it.
export type Action = {
  texte: string;
  icone?: string;
  cible?: Record<string, string | number>;
  ton?: string;
  desactive?: boolean;
  mention?: string;
  infobulle?: string;
};

function ActionBouton({ action }: { action: Action | null | undefined }) {
  if (!action) return null;
  // The only dynamically-keyed attribute set in this file: `cible`'s keys
  // are the action's own vocabulary (`fiche`, `go`, `toast`, …), decided by
  // each call site, not by this component.
  const attributs = Object.fromEntries(
    Object.entries(action.cible ?? {}).map(([nom, valeur]) => [
      `data-${nom}`,
      String(valeur),
    ]),
  ) as Record<`data-${string}`, string>;
  return (
    <button
      className={`sact${action.ton ? ` ${action.ton}` : ""}`}
      disabled={action.desactive || undefined}
      title={action.infobulle || undefined}
      {...attributs}
    >
      {action.icone ? <Icone paths={action.icone} /> : null}
      {action.texte}
      {action.mention ? <span className="soon">{action.mention}</span> : null}
    </button>
  );
}

function BlocActions({ bloc }: { bloc: Extract<Bloc, { type: "actions" }> }) {
  const liste = (bloc.actions ?? []).filter((action): action is Action =>
    Boolean(action),
  );
  if (!liste.length) return null;
  return (
    <div className={`sheetacts${bloc.secondaire ? " secondary" : ""}`}>
      {liste.map((action, index) => (
        <ActionBouton key={index} action={action} />
      ))}
    </div>
  );
}

function BlocNote({ bloc }: { bloc: Extract<Bloc, { type: "note" }> }) {
  return (
    <p className="rulenote">
      <RichText valeur={bloc.texte} />
    </p>
  );
}

// A LIGNE of « faits » is `{ c, v, pip, pipValeur, terne }`: caption, value,
// a status dot on either side — one qualifies the step and the other the
// figure — and whether the value is still to come.
export type Ligne = {
  c: string;
  v: string;
  pip?: string;
  pipValeur?: string;
  terne?: boolean;
};

function BlocFaits({ bloc }: { bloc: Extract<Bloc, { type: "faits" }> }) {
  return (
    <div className="panel sheetfaits">
      {(bloc.lignes ?? []).map((ligne, index) => (
        <div
          key={index}
          className={`kv${ligne.pip ? " avecpip" : ""}${ligne.terne ? " avenir" : ""}`}
        >
          <span>
            {ligne.pip ? <span className={`pip ${ligne.pip}`} /> : null}
            {ligne.c}
          </span>
          <span>
            {ligne.pipValeur ? (
              <span className={`pip ${ligne.pipValeur}`} />
            ) : null}
            {ligne.v}
          </span>
        </div>
      ))}
    </div>
  );
}

/* --- saisons ------------------------------------------------------- */

// Lifecycle order and swatch classes for the season legend — refonte.html
// keeps `EP_ORDER`/`EP_SWATCH` private (only `EP_LABEL` is published on the
// référentiel). Both are small, static, keyed on the same six states
// `EP_LABEL` already carries, so they are reproduced here verbatim rather
// than re-derived.
const EP_ORDER = [
  "non_verifie",
  "annonce",
  "en_attente",
  "a_recuperer",
  "en_acquisition",
  "en_mediatheque",
] as const;

const EP_SWATCH: Record<string, string> = {
  non_verifie: "sw-muted",
  annonce: "sw-upcoming",
  en_attente: "sw-waiting",
  a_recuperer: "sw-warning",
  en_acquisition: "sw-info",
  en_mediatheque: "sw-success",
};

// The slice of a "follow" record the season blocks read: `t` for lookups
// against the référentiel (`sheetFor`/`possedesDe`), `st` as the fallback
// state when a season has no per-episode ownership data. Not an exported
// donnees.ts type — the panel receives whatever the caller's `suivi` object
// is, and only ever reads these two fields.
export type Suivi = { t: string; st?: string };

export type Saison = ReturnType<Referentiel["saisonsDe"]>[number];

type EpisodeCatalogue = { n: number; air?: string | null }[];

// Presence is read from the LIST of owned numbers when the référentiel
// knows it, never from a `num <= owned` threshold that assumes the hole is
// at the end of the season — the same correction `epState` applies on the
// media sheet.
function epState(
  referentiel: Referentiel,
  suivi: Suivi,
  saisonNum: number,
  numero: number,
  owned: number,
): string {
  const detenus = referentiel.possedesDe(suivi.t, saisonNum);
  if (detenus)
    return detenus.has(numero)
      ? "en_mediatheque"
      : suivi.st === "en_attente"
        ? "en_attente"
        : suivi.st === "en_acquisition"
          ? "en_acquisition"
          : "a_recuperer";
  if (numero <= owned) return "en_mediatheque";
  if (suivi.st === "en_attente") return "en_attente";
  if (suivi.st === "en_acquisition") return "en_acquisition";
  return "a_recuperer";
}

function catalogueDe(
  referentiel: Referentiel,
  suivi: Suivi,
  numero: number,
): EpisodeCatalogue | null {
  const fiche = referentiel.sheetFor(suivi.t) as { eps?: unknown } | null;
  const eps = fiche?.eps as Record<string, EpisodeCatalogue> | undefined;
  return eps?.[String(numero)] ?? null;
}

function SaisonDetail({
  suivi,
  saison,
  referentiel,
}: {
  suivi: Suivi;
  saison: Saison;
  referentiel: Referentiel;
}) {
  const [num, airedBrut, owned] = saison;
  const aired = airedBrut ?? 0;
  const complete = owned >= aired;
  const manque = aired - owned;
  // An ANNOUNCED episode appears in the matrix but NEVER in the
  // denominator: it is not missing, it is not out yet. The provider
  // catalogue knows more than what has aired.
  const catalogue = catalogueDe(referentiel, suivi, num);
  const total = Math.max(aired, catalogue ? catalogue.length : 0);
  const cellules = Array.from({ length: total }, (_, index) => {
    const numero = index + 1;
    const info = catalogue?.find((entree) => entree.n === numero) ?? null;
    const futur = Boolean(info?.air && info.air > referentiel.AUJOURDHUI);
    const etat = futur
      ? "annonce"
      : epState(referentiel, suivi, num, numero, owned);
    return (
      <button
        key={numero}
        className={`ep ${etat}`}
        data-ep={`${suivi.t}|${num}|${numero}|${etat}`}
        aria-label={`S${String(num).padStart(2, "0")}E${String(numero).padStart(2, "0")} — ${referentiel.EP_LABEL[etat]}`}
      >
        {String(numero).padStart(2, "0")}
      </button>
    );
  });
  return (
    <details className="season" open={!complete}>
      <summary>
        Saison {num}
        <span className="sfr">
          {owned}/{aired}
        </span>
        {complete ? null : (
          <span className="miss">
            {manque} manquant{manque > 1 ? "s" : ""}
          </span>
        )}
      </summary>
      <div className="eps">{cellules}</div>
    </details>
  );
}

// The season matrix and the legend that reads it — ONE block, so a panel
// asking for seasons cannot get the matrix without the key to it. The
// legend lists only the states actually PRESENT, above the matrix.
function BlocSaisons({ bloc }: { bloc: Extract<Bloc, { type: "saisons" }> }) {
  const referentiel = useReferentiel();
  const { suivi, saisons } = bloc;
  const aDesAnnonces = saisons.some((saison) =>
    (catalogueDe(referentiel, suivi, saison[0]) ?? []).some(
      (episode) => episode.air && episode.air > referentiel.AUJOURDHUI,
    ),
  );
  const etatsPresents = new Set<string>([
    ...(aDesAnnonces ? ["annonce"] : []),
    ...saisons.flatMap((saison) => [
      ...(saison[2] > 0 ? ["en_mediatheque"] : []),
      ...((saison[1] ?? 0) > saison[2]
        ? [epState(referentiel, suivi, saison[0], saison[1] ?? 0, saison[2])]
        : []),
    ]),
  ]);
  return (
    <>
      <div className="legend">
        {EP_ORDER.filter((etat) => etatsPresents.has(etat)).map((etat) => (
          <span key={etat}>
            <i className={EP_SWATCH[etat]} />
            {referentiel.EP_LABEL[etat]}
          </span>
        ))}
      </div>
      {saisons.map((saison) => (
        <SaisonDetail
          key={saison[0]}
          suivi={suivi}
          saison={saison}
          referentiel={referentiel}
        />
      ))}
    </>
  );
}

/* --- champ ----------------------------------------------------------- */

// `uniteDe` / `nomDeFichier` are pure formatting off a `Reglage`'s own
// fields — refonte.html keeps them private (not published on
// `__referentiel`) but they carry no engine state, so they are reproduced
// verbatim rather than re-derived differently.
const UNITES: Record<string, string> = {
  gb: "Go",
  days: "jours",
  hours: "heures",
  seconds: "secondes",
  minutes: "minutes",
  m: "minutes",
  s: "secondes",
  ratio: "ratio",
};

function uniteDe(reglage: Reglage): string | null {
  const dernier = reglage.n.split("_").pop();
  return dernier ? (UNITES[dernier] ?? null) : null;
}

function nomDeFichier(f: string): string {
  return f.includes(".") ? f : `${f}.json5`;
}

function BlocChamp({ bloc }: { bloc: Extract<Bloc, { type: "champ" }> }) {
  const { reglageId, valeurSaisie, modifierReglage, ouvrirReglage, icons } =
    useReferentiel();
  const { reglage } = bloc;
  const id = reglageId(reglage);
  // `valeurEnCours` (the `REG_ETAT.modifs` pending-edit overlay) is private,
  // mutable engine state — never published on the référentiel. `reglage.v`
  // is donnees.ts's own documented "current value" for a setting and is
  // used here in its place.
  const v = reglage.v;

  if (reglage.type === "structure")
    return (
      <div className="champ refus">
        <p className="rulenote">
          Cette valeur est une <b>structure</b> — une liste d&apos;objets avec
          leurs propres clés. Elle ne s&apos;édite pas ici : un formulaire
          qu&apos;on ne peut pas valider promettrait une modification qui casse
          le fichier. Ouvrez <code>{nomDeFichier(reglage.f)}</code>.
        </p>
      </div>
    );

  if (reglage.type === "booleen")
    return (
      <div className="champ">
        <button
          className={`interrupteur${v ? " actif" : ""}`}
          role="switch"
          aria-checked={v ? "true" : "false"}
          data-champ={id}
          data-vers={v ? "non" : "oui"}
        >
          <span className="pastille" />
        </button>
        <span className="champlbl">{v ? "Activé" : "Désactivé"}</span>
      </div>
    );

  if (reglage.type === "liste") {
    const items = Array.isArray(v) ? (v as unknown[]) : [];
    return (
      <div className="champ liste">
        {items.length ? (
          items.map((x, index) => (
            <div className="litem" key={index}>
              <span>{String(x)}</span>
              <button
                className="lsupp"
                data-champsupp={id}
                data-index={index}
                aria-label={`Retirer ${String(x)}`}
              >
                <Icone paths={icons.x} />
              </button>
            </div>
          ))
        ) : (
          <p className="rulenote">
            Aucune valeur. La liste est vide, ce qui n&apos;est pas la même
            chose qu&apos;une valeur absente.
          </p>
        )}
        <button className="lajout" data-champajout={id}>
          <Icone paths={icons.plus} />
          Ajouter
        </button>
      </div>
    );
  }

  const vide = v === null || v === undefined || v === "";
  const mono = reglage.type === "chemin";
  const numerique = reglage.type === "nombre";
  const unite = uniteDe(reglage);

  return (
    <div className="champ">
      <input
        className={`champsaisie${mono ? " mono" : ""}`}
        data-champ={id}
        type={numerique ? "number" : "text"}
        inputMode={numerique ? "decimal" : undefined}
        defaultValue={vide ? "" : String(v)}
        placeholder={vide ? "non défini" : ""}
        // `libelleReglage` (the curated French label) is private too — it
        // needs `LIBELLES_REGLAGES`, never published — so the accessible
        // name falls back to the same humanised key it would fall back to
        // when no curated entry exists (`reglage.n.replace(/_/g, " ")`).
        aria-label={reglage.n.replace(/_/g, " ")}
        // The ONE place mountSearch's `.champsaisie` `onchange` binding
        // (refonte.html) is replaced by a component-owned handler. `onBlur`,
        // not React's `onChange` (which fires on every keystroke, unlike
        // the DOM `change` event `onchange` bound to): the legacy behaviour
        // commits on blur, not per keystroke, and the input stays
        // uncontrolled (`defaultValue`) so a component-driven re-render
        // never fights the caret mid-edit.
        onBlur={(event) => {
          modifierReglage(id, valeurSaisie(reglage, event.target.value));
          ouvrirReglage(id);
        }}
      />
      {unite ? (
        <span className="champunite">{unite}</span>
      ) : reglage.type === "duree" ? (
        <span className="champunite">format 72h</span>
      ) : null}
    </div>
  );
}

/* --- the descriptor + dispatcher ------------------------------------- */

// A BLOC is `{ type, … }`, never HTML. Order matters and is the caller's:
// the five kinds `panneauBlocHTML` switches on in refonte.html.
export type Bloc =
  | { type: "note"; texte: Texte }
  | { type: "faits"; lignes: Ligne[] }
  | {
      type: "actions";
      actions: (Action | null | undefined)[];
      secondaire?: boolean;
    }
  | { type: "saisons"; suivi: Suivi; saisons: Saison[] }
  | { type: "champ"; reglage: Reglage };

function BlocView({ bloc }: { bloc: Bloc }) {
  switch (bloc.type) {
    case "note":
      return <BlocNote bloc={bloc} />;
    case "faits":
      return <BlocFaits bloc={bloc} />;
    case "actions":
      return <BlocActions bloc={bloc} />;
    case "saisons":
      return <BlocSaisons bloc={bloc} />;
    case "champ":
      return <BlocChamp bloc={bloc} />;
    default:
      // Silence here would draw an empty panel and blame the data. A block
      // type nobody declared is a fact nobody declared — same refusal as
      // `panneauBlocHTML`'s own throw, same message, so the signal a probe
      // reads (the Error's text) stays the one refonte.html already sets
      // `window.__panneauInconnu` to exercise.
      throw new Error(
        "bloc de panneau inconnu : " + (bloc as { type: string }).type,
      );
  }
}

// THE DESCRIPTOR — facts, never markup. `titre` is read unconditionally by
// `panneauHTML` (no guard around it), so it is required here, not optional
// as a first read of the legacy source might suggest.
export type Descripteur = {
  titre: string;
  sousTitre?: string;
  meta?: Texte;
  puce?: [string, string] | null;
  affiche?: { t: string; k?: string };
  avatar?: string;
  blocs?: Bloc[];
};

// ONE bottom panel, and its shape follows the facts it is given — the
// component form of `panneauHTML` (refonte.html). Not mounted anywhere in
// this task: a later task wires `openSheet`/the React sheet layer to it.
export function PanneauContenu({
  descripteur,
}: {
  descripteur: Descripteur;
}): JSX.Element {
  const identite = (
    <>
      <h3 className="sheettitle">{descripteur.titre}</h3>
      {descripteur.sousTitre ? (
        <span className="sheetsub">{descripteur.sousTitre}</span>
      ) : null}
      {descripteur.meta ? (
        <p className="sheetmeta">
          <RichText valeur={descripteur.meta} />
        </p>
      ) : null}
      <Puce puce={descripteur.puce} />
    </>
  );
  const portrait = descripteur.affiche ? (
    <span className="sheetposter">
      <Portrait affiche={descripteur.affiche} />
    </span>
  ) : descripteur.avatar ? (
    <span className="avatar big" aria-hidden="true">
      <img src={descripteur.avatar} alt="" />
    </span>
  ) : null;

  return (
    <>
      {portrait ? (
        <div
          className={`sheethead${descripteur.affiche ? " avecaffiche" : ""}`}
        >
          {portrait}
          <div className="sheetid">{identite}</div>
        </div>
      ) : (
        identite
      )}
      {(descripteur.blocs ?? []).map((bloc, index) => (
        <BlocView key={index} bloc={bloc} />
      ))}
    </>
  );
}
