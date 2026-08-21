// design/src/components/panel.tsx
// The unique bottom-panel constructor, reborn as a component. Every panel
// in the legacy engine is built by ONE function (`panneauHTML`, refonte.html)
// from a plain descriptor of facts — never ready-made markup — and this
// component is that same constructor, transplanted: same tags, same
// classes, same data-attribute vocabulary, so the document-level click
// delegation the legacy engine still runs (`.sact[data-mediasheet]`,
// `.ep[data-ep]`, `.field*[data-field]`, …) keeps working unchanged.
//
// Markup is TRANSPLANTED, not translated: React escapes text nodes
// natively, so there is no `escapeHtml` here — every plain string prop
// below is a JSX child or attribute value, which is already safe.
//
// The DESCRIPTOR's own field names are the seam: the legacy producers build
// those objects, so every key below (`title`, `blocs`, a block's `type`, an
// action's `target`…) stays whatever the fragment writes.
//
// Prose — anything a reader reads as a sentence — goes through `t()`, so this
// component re-renders when the language changes. HOW A SETTING IS NAMED is
// not prose and is not here: `settings-labels.ts` owns it, for this panel and
// for the page that lists the settings alike.
import { Fragment, type JSX } from "react";
import { useTranslation } from "react-i18next";
import { useReference, type Setting, type Reference } from "../data";
import { Icon } from "./icon";
import { settingLabel, unitOf } from "../settings-labels";

// A `richText` segment: plain text, a mono/code aside (`{ m }`), or an
// emphasised aside (`{ e }`) — exactly the three shapes `richText` switches
// on in refonte.html.
export type Segment = string | { m: string } | { e: string };
export type RichTextValue = string | Segment[];

function RichText({ value }: { value: RichTextValue | null | undefined }) {
  if (value == null) return null;
  if (typeof value === "string") return <>{value}</>;
  return (
    <>
      {value.map((segment, index) =>
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

function Chip({ chip }: { chip: [string, string] | null | undefined }) {
  if (!chip) return null;
  return <span className={`chip ${chip[0]}`} data-part="chip">{chip[1]}</span>;
}

// `posterBox`'s image-or-initials fallback, at panel size. `POSTERS` /
// `baseTitle` / `icons` / `initials` are the exact référentiel entries
// `posterBox` itself reads from (refonte.html), and this call carries no
// `opts` — the panel head never asks for the `exact` (no base-title
// fallback) variant.
function Poster({ poster }: { poster: { t: string; k?: string } }) {
  const { POSTERS, baseTitle, icons, initials } = useReference();
  const src = POSTERS[poster.t] ?? POSTERS[baseTitle(poster.t)];
  if (src) return <img src={src} alt="" loading="lazy" />;
  const iconPath =
    poster.k === "movie"
      ? icons.film
      : poster.k === "show"
        ? icons.tv
        : icons.clap;
  return (
    <span className="pfall" data-part="card/poster-fallback">
      <Icon paths={iconPath} strokeWidth={1.25} />
      <b>{initials(poster.t)}</b>
    </span>
  );
}

// An ACTION is `{ texte, icone, cible, ton, desactive, mention, infobulle }`
// — `target` is a map of DATA ATTRIBUTES, never a handler and never markup;
// the click delegation reads those attributes, exactly as it does for a
// card. This component adds NO `onClick` of its own for it.
export type Action = {
  text: string;
  icone?: string;
  target?: Record<string, string | number>;
  ton?: string;
  desactive?: boolean;
  mention?: string;
  infobulle?: string;
};

function ActionButton({ action }: { action: Action | null | undefined }) {
  if (!action) return null;
  // The only dynamically-keyed attribute set in this file: `target`'s keys
  // are the action's own vocabulary (`mediaSheet`, `go`, `toast`, …), decided by
  // each call site, not by this component.
  const attributes = Object.fromEntries(
    Object.entries(action.target ?? {}).map(([name, value]) => [
      `data-${name}`,
      String(value),
    ]),
  ) as Record<`data-${string}`, string>;
  return (
    <button
      className={`sact${action.ton ? ` ${action.ton}` : ""}`}
      data-tone={action.ton || undefined}
      disabled={action.desactive || undefined}
      title={action.infobulle || undefined}
      {...attributes}
    >
      {action.icone ? <Icon paths={action.icone} /> : null}
      {action.text}
      {action.mention ? <span className="soon">{action.mention}</span> : null}
    </button>
  );
}

function ActionsBlock({
  block,
}: {
  block: Extract<PanelBlock, { type: "actions" }>;
}) {
  const list = (block.actions ?? []).filter((action): action is Action =>
    Boolean(action),
  );
  if (!list.length) return null;
  return (
    <div className={`sheetacts${block.secondary ? " secondary" : ""}`}>
      {list.map((action, index) => (
        <ActionButton key={index} action={action} />
      ))}
    </div>
  );
}

function NoteBlock({
  block,
}: {
  block: Extract<PanelBlock, { type: "note" }>;
}) {
  return (
    <p className="rulenote">
      <RichText value={block.text} />
    </p>
  );
}

// A LIGNE of « faits » is `{ c, v, pip, pipValeur, terne }`: caption, value,
// a status dot on either side — one qualifies the step and the other the
// figure — and whether the value is still to come.
export type FactLine = {
  c: string;
  v: string;
  pip?: string;
  pipValue?: string;
  terne?: boolean;
};

function FactsBlock({
  block,
}: {
  block: Extract<PanelBlock, { type: "faits" }>;
}) {
  return (
    <div className="panel sheetfacts" data-part="panel">
      {(block.lignes ?? []).map((line, index) => (
        <div
          key={index}
          className={`kv${line.pip ? " withpip" : ""}${line.terne ? " upcoming" : ""}`}
        >
          <span>
            {line.pip ? <span className={`pip ${line.pip}`} data-part="status-dot" /> : null}
            {line.c}
          </span>
          <span>
            {line.pipValue ? (
              <span className={`pip ${line.pipValue}`} data-part="status-dot" />
            ) : null}
            {line.v}
          </span>
        </div>
      ))}
    </div>
  );
}

/* --- seasons ------------------------------------------------------- */

// Lifecycle order and swatch classes for the season legend — refonte.html
// keeps `EP_ORDER`/`EP_SWATCH` private (only `EP_LABEL` is published on the
// référentiel). Both are small, static, keyed on the same six states
// `EP_LABEL` already carries, so they are reproduced here verbatim rather
// than re-derived.
const EP_ORDER = [
  "unverified",
  "announced",
  "pending",
  "to_grab",
  "acquiring",
  "in_library",
] as const;

const EP_SWATCH: Record<string, string> = {
  unverified: "sw-muted",
  announced: "sw-upcoming",
  pending: "sw-waiting",
  to_grab: "sw-warning",
  acquiring: "sw-info",
  in_library: "sw-success",
};

// The slice of a "follow" record the season blocks read: `t` for lookups
// against the référentiel (`sheetFor`/`ownedFor`), `st` as the fallback
// state when a season has no per-episode ownership data. Not an exported
// data.ts type — the panel receives whatever the caller's `isFollowed` object
// is, and only ever reads these two fields.
export type Follow = { t: string; st?: string };

export type Season = ReturnType<Reference["seasonsOf"]>[number];

type EpisodeCatalog = { n: number; air?: string | null }[];

// Presence is read from the LIST of owned numbers when the référentiel
// knows it, never from a `num <= owned` threshold that assumes the hole is
// at the end of the season — the same correction `epState` applies on the
// media sheet.
function epState(
  reference: Reference,
  follow: Follow,
  seasonNum: number,
  number: number,
  owned: number,
): string {
  const held = reference.ownedFor(follow.t, seasonNum);
  if (held)
    return held.has(number)
      ? "in_library"
      : follow.st === "pending"
        ? "pending"
        : follow.st === "acquiring"
          ? "acquiring"
          : "to_grab";
  if (number <= owned) return "in_library";
  if (follow.st === "pending") return "pending";
  if (follow.st === "acquiring") return "acquiring";
  return "to_grab";
}

function catalogFor(
  reference: Reference,
  follow: Follow,
  number: number,
): EpisodeCatalog | null {
  const sheet = reference.sheetFor(follow.t) as { eps?: unknown } | null;
  const eps = sheet?.eps as Record<string, EpisodeCatalog> | undefined;
  return eps?.[String(number)] ?? null;
}

function SeasonDetails({
  follow,
  season,
  reference,
}: {
  follow: Follow;
  season: Season;
  reference: Reference;
}) {
  const { t } = useTranslation();
  const [num, rawAired, owned] = season;
  const aired = rawAired ?? 0;
  const complete = owned >= aired;
  const missing = aired - owned;
  // An ANNOUNCED episode appears in the matrix but NEVER in the
  // denominator: it is not missing, it is not out yet. The provider
  // catalogue knows more than what has aired.
  const catalog = catalogFor(reference, follow, num);
  const total = Math.max(aired, catalog ? catalog.length : 0);
  const cells = Array.from({ length: total }, (_, index) => {
    const number = index + 1;
    const info = catalog?.find((entry) => entry.n === number) ?? null;
    const upcoming = Boolean(info?.air && info.air > reference.TODAY);
    const state = upcoming
      ? "announced"
      : epState(reference, follow, num, number, owned);
    return (
      <button
        key={number}
        className={`ep ${state}`}
        data-part="episode"
        data-ep={`${follow.t}|${num}|${number}|${state}`}
        aria-label={`S${String(num).padStart(2, "0")}E${String(number).padStart(2, "0")} — ${reference.EP_LABEL[state]}`}
      >
        {String(number).padStart(2, "0")}
      </button>
    );
  });
  return (
    <details className="season" data-part="season" open={!complete}>
      <summary>
        {/* The blanks between these children are NOT decoration: the legacy
            `saisonsHTML` carried a line break at each of them, and JSX drops
            the whitespace it finds between an expression and an element. Left
            out, `summary.textContent` reads « Saison 2211/11 » — the season
            number welded to its own counter, for anything that reads the row
            as one string (a rule deriving the number from it, an assistive
            technology announcing it). `summary` is a flex container, so a
            whitespace-only node draws nothing: the fix is invisible and the
            text is right again. */}
        {t("common.season")} {num}{" "}
        <span className="sfr">
          {owned}/{aired}
        </span>{" "}
        {complete ? null : (
          <span className="miss" data-part="season/missing">
            {missing}{" "}
            {missing > 1 ? t("common.missingPlural") : t("common.missing")}
          </span>
        )}
      </summary>
      <div className="eps" data-part="episode/set">
        {cells}
      </div>
    </details>
  );
}

// The season matrix and the legend that reads it — ONE block, so a panel
// asking for seasons cannot get the matrix without the key to it. The
// legend lists only the states actually PRESENT, above the matrix.
function SeasonsBlock({
  block,
}: {
  block: Extract<PanelBlock, { type: "saisons" }>;
}) {
  const reference = useReference();
  const { isFollowed: follow, seasons: seasons } = block;
  const hasUpcoming = seasons.some((season) =>
    (catalogFor(reference, follow, season[0]) ?? []).some(
      (episode) => episode.air && episode.air > reference.TODAY,
    ),
  );
  const statesPresent = new Set<string>([
    ...(hasUpcoming ? ["announced"] : []),
    ...seasons.flatMap((season) => [
      ...(season[2] > 0 ? ["in_library"] : []),
      ...((season[1] ?? 0) > season[2]
        ? [epState(reference, follow, season[0], season[1] ?? 0, season[2])]
        : []),
    ]),
  ]);
  return (
    <>
      <div className="legend">
        {EP_ORDER.filter((state) => statesPresent.has(state)).map((state) => (
          <span key={state}>
            <i className={EP_SWATCH[state]} />
            {reference.EP_LABEL[state]}
          </span>
        ))}
      </div>
      {seasons.map((season) => (
        <SeasonDetails
          key={season[0]}
          follow={follow}
          season={season}
          reference={reference}
        />
      ))}
    </>
  );
}

/* --- field ----------------------------------------------------------- */

// `fileName` is pure formatting off a `Setting`'s own fields —
// refonte.html keeps it private (not published on `__referentiel`) but it
// carries no engine state, so it is reproduced verbatim rather than
// re-derived differently. HOW A SETTING IS NAMED is not reproduced at all:
// `settings-labels.ts` is the one implementation, read by the page that lists
// the settings and by this panel alike, so a curated label cannot say one
// thing on a row and another above it.
function fileName(f: string): string {
  return f.includes(".") ? f : `${f}.json5`;
}

function FieldBlock({
  block,
}: {
  block: Extract<PanelBlock, { type: "field" }>;
}) {
  const {
    settingId,
    rawValue,
    typedValue,
    changeSetting,
    openSetting,
    icons,
  } = useReference();
  const { t } = useTranslation();
  const { setting: setting } = block;
  const id = settingId(setting);
  // The field draws what `rawValue` answers — the pending edit if there
  // is one, the file's `brut` otherwise. Reading `.brut` alone would draw a
  // list one has just shortened at its old length, so a removal would look
  // like it did nothing. Never `.v`: that is a pre-formatted DISPLAY string
  // (a boolean's `.brut: false` reads `.v: "non"`, always truthy, which would
  // wedge the switch on).
  const v = rawValue(setting);

  if (setting.type === "structure")
    return (
      <div className="field readonly" data-part="field">
        <p className="rulenote">
          {t("settings.field.structureBefore")}{" "}
          <b>{t("settings.field.structureWord")}</b>{" "}
          {t("settings.field.structureAfter")}{" "}
          <code>{fileName(setting.f)}</code>.
        </p>
      </div>
    );

  if (setting.type === "boolean")
    return (
      <div className="field" data-part="field">
        <button
          className={`fieldtoggle${v ? " active" : ""}`}
          data-part="field/toggle"
          role="switch"
          aria-checked={v ? "true" : "false"}
          data-field={id}
          data-to={v ? "non" : "oui"}
        >
          <span className="fieldknob" />
        </button>
        <span className="fieldlabel">
          {v ? t("settings.field.enabled") : t("settings.field.disabled")}
        </span>
      </div>
    );

  if (setting.type === "list") {
    const items = Array.isArray(v) ? (v as unknown[]) : [];
    return (
      <div className="field list" data-part="field">
        {items.length ? (
          items.map((x, index) => (
            <div className="litem" key={index}>
              <span>{String(x)}</span>
              <button
                className="lremove"
                data-deletefield={id}
                data-index={index}
                aria-label={t("settings.field.removeAria", {
                  // french-ok: the INTERPOLATION placeholder, named by
                  // `removeAria` in fr.json — renaming this half alone
                  // leaves « Retirer {{valeur}} » on screen.
                  valeur: String(x),
                })}
              >
                <Icon paths={icons.x} />
              </button>
            </div>
          ))
        ) : (
          <p className="rulenote">{t("settings.field.emptyList")}</p>
        )}
        <button className="ladd" data-addfield={id}>
          <Icon paths={icons.plus} />
          {t("settings.field.add")}
        </button>
      </div>
    );
  }

  const empty = v === null || v === undefined || v === "";
  const mono = setting.type === "path";
  const numeric = setting.type === "number";
  const unit = unitOf(setting);

  return (
    <div className="field" data-part="field">
      <input
        // KEYED BY THE SETTING, and this is a correctness fix, not a hint.
        // `#sheetin` is a persistent node now, where the legacy layer replaced
        // its innerHTML on every open — a fresh field each time, implicitly.
        // Here the blocks are the same kinds in the same order from one panel
        // to the next, so React would REUSE this very `<input>`: once the
        // operator has typed, the DOM node carries a permanent dirty-value
        // flag, React only updates the `value` ATTRIBUTE, and the next
        // setting's panel opens showing the previous setting's text — which
        // the next blur then files under the NEW setting's id. Keying by the
        // setting makes a different setting a different node.
        key={id}
        className={`fieldinput${mono ? " mono" : ""}`}
        data-part="field/input"
        data-field={id}
        type={numeric ? "number" : "text"}
        inputMode={numeric ? "decimal" : undefined}
        defaultValue={empty ? "" : String(v)}
        placeholder={empty ? t("settings.field.undefinedPlaceholder") : ""}
        aria-label={settingLabel(setting)}
        // The ONE place mountSearch's `.fieldinput` `onchange` binding
        // (refonte.html) is replaced by a component-owned handler — and it is
        // the SAME event, bound natively rather than through React's synthetic
        // `onChange`. Three reasons, all measured rather than stylistic:
        //   · the DOM `change` event commits on blur, once; React's `onChange`
        //     fires on every keystroke, which would file a pending edit per
        //     character typed;
        //   · a `change` event dispatched at the element (what a probe does to
        //     exercise this field) reaches a native listener, while React's
        //     synthetic `onChange` is gated by its own value tracker and
        //     silently does nothing for a value already seen;
        //   · the input stays uncontrolled (`defaultValue`), so a re-render
        //     never fights the caret mid-edit.
        // The listener is re-attached on each render, which is what keeps this
        // closure reading the CURRENT setting rather than the one this field
        // was first drawn for.
        ref={(element) => {
          if (!element) return;
          const commit = () => {
            changeSetting(id, typedValue(setting, element.value));
            openSetting(id);
          };
          element.addEventListener("change", commit);
          return () => element.removeEventListener("change", commit);
        }}
      />
      {unit ? (
        <span className="fieldunit">{unit}</span>
      ) : setting.type === "duration" ? (
        <span className="fieldunit">{t("settings.field.durationFormat")}</span>
      ) : null}
    </div>
  );
}

/* --- the descriptor + dispatcher ------------------------------------- */

// A BLOC is `{ type, … }`, never HTML. Order matters and is the caller's:
// the five kinds `panneauBlocHTML` switches on in refonte.html. The `type`
// values and every field name are the producers' own vocabulary.
export type PanelBlock =
  | { type: "note"; text: RichTextValue }
  | { type: "faits"; lignes: FactLine[] }
  | {
      type: "actions";
      actions: (Action | null | undefined)[];
      secondary?: boolean;
    }
  | { type: "saisons"; isFollowed: Follow; seasons: Season[] }
  | { type: "field"; setting: Setting };

// The refusal itself, named, so the probe that exercises it
// (`window.__unknownPanel`, published by the shell) raises the SAME error
// the renderer raises rather than a copy of its message that can drift.
export function refuseBlock(block: { type: string }): never {
  // ENGLISH, and deliberately not in `fr.json`: this is a tool message. It
  // reaches a developer console and the rule harness, never a reader of the
  // interface, so it is not a translatable string — the same reason
  // `console.error` calls in the shell are English.
  throw new Error("unknown panel block: " + block.type);
}

function BlockView({ block }: { block: PanelBlock }) {
  switch (block.type) {
    case "note":
      return <NoteBlock block={block} />;
    case "faits":
      return <FactsBlock block={block} />;
    case "actions":
      return <ActionsBlock block={block} />;
    case "saisons":
      return <SeasonsBlock block={block} />;
    case "field":
      return <FieldBlock block={block} />;
    default:
      // Silence here would draw an empty panel and blame the data. A block
      // type nobody declared is a fact nobody declared, and the refusal goes
      // through the ONE named thrower above, so the signal a probe reads (the
      // Error's text) is the one `window.__unknownPanel` exercises rather
      // than a copy of it that can drift.
      return refuseBlock(block as { type: string });
  }
}

// THE DESCRIPTOR — facts, never markup. `title` is read unconditionally by
// `panneauHTML` (no guard around it), so it is required here, not optional
// as a first read of the legacy source might suggest.
export type PanelDescriptor = {
  title: string;
  subtitle?: string;
  meta?: RichTextValue;
  puce?: [string, string] | null;
  poster?: { t: string; k?: string };
  avatar?: string;
  // A block may be ABSENT and say so in place: a caller writes
  // `setting.note ? { type: "note", … } : null` inline rather than assembling
  // the list conditionally, and `panneauBlocHTML` answered an empty string for
  // it. The same tolerance, expressed in the type instead of discovered at
  // render time.
  blocs?: (PanelBlock | null | undefined)[];
};

// ONE bottom panel, and its shape follows the facts it is given — the
// component form of `panneauHTML` (refonte.html).
export function PanelContent({
  descriptor,
}: {
  descriptor: PanelDescriptor;
}): JSX.Element {
  const identity = (
    <>
      <h3 className="sheettitle">{descriptor.title}</h3>
      {descriptor.subtitle ? (
        <span className="sheetsub">{descriptor.subtitle}</span>
      ) : null}
      {descriptor.meta ? (
        <p className="sheetmeta">
          <RichText value={descriptor.meta} />
        </p>
      ) : null}
      <Chip chip={descriptor.puce} />
    </>
  );
  const poster = descriptor.poster ? (
    <span className="sheetposter">
      <Poster poster={descriptor.poster} />
    </span>
  ) : descriptor.avatar ? (
    <span className="avatar big" data-part="avatar" aria-hidden="true">
      <img src={descriptor.avatar} alt="" />
    </span>
  ) : null;

  return (
    <>
      {poster ? (
        <div
          className={`sheethead${descriptor.poster ? " withposter" : ""}`}
        >
          {poster}
          <div className="sheetid">{identity}</div>
        </div>
      ) : (
        identity
      )}
      {(descriptor.blocs ?? [])
        .filter((block): block is PanelBlock => Boolean(block))
        .map((block, index) => (
          <BlockView key={index} block={block} />
        ))}
    </>
  );
}
