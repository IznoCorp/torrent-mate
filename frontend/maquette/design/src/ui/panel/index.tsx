// The bottom panel — one constructor, and the three blocks that know no domain.
//
// Every panel in the legacy engine is built by ONE function (`panneauHTML`,
// refonte.html) from a plain descriptor of facts — never ready-made markup —
// and this component is that same constructor, transplanted: same tags, same
// classes, same data-attribute vocabulary, so the document-level click
// delegation the legacy engine still runs (`.sact[data-mediasheet]`,
// `.ep[data-ep]`, `.field*[data-field]`, …) keeps working unchanged.
//
// Markup is TRANSPLANTED, not translated: React escapes text nodes natively,
// so there is no `escapeHtml` here — every plain string prop below is a JSX
// child or attribute value, which is already safe.
//
// WHAT THIS FILE DOES NOT KNOW, and that is the point: a television season and
// a configuration setting. Those two blocks live with the domains that own
// them and register themselves through `contract.ts`. While they lived here,
// this « primitive » read `seasonsOf`, `ownedFor`, `sheetFor` and
// `settingLabel`, and eight entries of the engine's reference surface counted
// as shared between two domains for no reason but this file.
//
// Prose — anything a reader reads as a sentence — goes through `t()`, so this
// component re-renders when the language changes.
import { Fragment, type JSX } from "react";
import { useTranslation } from "react-i18next";
import { useEngineDrawing } from "../../lib/engine-drawing";
import { Icon } from "../../ui/icon";
import { comingSoon, factsPanel, keyValueRow, ruleNote, sheetActions, sheetAvatar, sheetFacts, sheetHead, sheetIdentity, sheetMeta, sheetTitle } from "../variants";
import {
  refuseBlock,
  registerBlock,
  rendererFor,
  type Action,
  type PanelBlock,
  type PanelDescriptor,
  type RichTextValue,
} from "./contract";

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
  return <span className={`chip ${chip[0]}`} data-part="chip" data-tone={chip[0]}>{chip[1]}</span>;
}

// `posterBox`'s image-or-initials fallback, at panel size. `POSTERS` /
// `baseTitle` / `icons` / `initials` are the exact référentiel entries
// `posterBox` itself reads from (refonte.html), and this call carries no
// `opts` — the panel head never asks for the `exact` (no base-title
// fallback) variant.
function Poster({ poster }: { poster: { t: string; k?: string } }) {
  const {
    POSTERS,
    baseTitle,
    icons,
    initials,
  } = useEngineDrawing();
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
      data-part="sheet/action"
      data-tone={action.ton || undefined}
      disabled={action.desactive || undefined}
      title={action.infobulle || undefined}
      {...attributes}
    >
      {action.icone ? <Icon paths={action.icone} /> : null}
      {action.text}
      {action.mention ? <span className={comingSoon()}>{action.mention}</span> : null}
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
    <div className={sheetActions({ secondary: Boolean(block.secondary) })} data-part="sheet/actions">
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
    <p className={ruleNote()}>
      <RichText value={block.text} />
    </p>
  );
}

function FactsBlock({
  block,
}: {
  block: Extract<PanelBlock, { type: "faits" }>;
}) {
  return (
    <div className={`${factsPanel()} ${sheetFacts()}`} data-part="panel">
      {(block.lignes ?? []).map((line, index) => (
        <div
          key={index}
          className={keyValueRow({ withPip: Boolean(line.pip), upcoming: Boolean(line.terne) })}
          data-part="key-value"
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

/* --- the dispatcher -------------------------------------------------- */

// The three kinds this file owns, declared to the registry as this module
// evaluates. A feature's own block registers itself the same way, from its own
// file — see `contract.ts`.
registerBlock("note", (block) => <NoteBlock block={block} />);
registerBlock("faits", (block) => <FactsBlock block={block} />);
registerBlock("actions", (block) => <ActionsBlock block={block} />);

function BlockView({ block }: { block: PanelBlock }) {
  const render = rendererFor(block.type);
  // Silence here would draw an empty panel and blame the data. A block type
  // nobody declared is a fact nobody declared — and so is a block kind whose
  // owning feature was never imported at boot, which is the new way this can
  // go wrong and the reason it throws rather than rendering nothing. The
  // refusal goes through the ONE named thrower, so the signal a probe reads
  // (the Error's text) is the one `window.__unknownPanel` exercises rather
  // than a copy of it that can drift.
  if (!render) return refuseBlock(block);
  return render(block);
}

export function PanelContent({
  descriptor,
}: {
  descriptor: PanelDescriptor;
}): JSX.Element {
  const identity = (
    <>
      <h2 className={sheetTitle()} data-part="sheet/title">{descriptor.title}</h2>
      {descriptor.subtitle ? (
        <span className="sheetsub">{descriptor.subtitle}</span>
      ) : null}
      {descriptor.meta ? (
        <p className={sheetMeta()} data-part="sheet/meta">
          <RichText value={descriptor.meta} />
        </p>
      ) : null}
      <Chip chip={descriptor.puce} />
    </>
  );
  const poster = descriptor.poster ? (
    <span className="sheetposter" data-part="sheet/poster">
      <Poster poster={descriptor.poster} />
    </span>
  ) : descriptor.avatar ? (
    <span className={`avatar ${sheetAvatar()}`} data-part="avatar" aria-hidden="true">
      <img src={descriptor.avatar} alt="" />
    </span>
  ) : null;

  return (
    <>
      {poster ? (
        <div
          className={sheetHead({ withPoster: Boolean(descriptor.poster) })}
        >
          {poster}
          <div className={sheetIdentity()}>{identity}</div>
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
