// A card on « Arrivées »: what the staging area holds, drawn as the one card
// every list draws.
//
// ONE CARD, ONE BEHAVIOUR (R41–R46). The poster opens the media sheet; the body
// opens the panel. A folder the scrape could not name has no sheet to open, so
// it does not wear a poster: it wears a FOLDER, which addresses the folder's own
// panel and nothing else, and the card says it is not a medium.
//
// NO HANDLER IS ATTACHED HERE. The document-level delegation answers
// `data-mediasheet`, `data-panel` and `data-act` on the button tapped, which is
// why every attribute below is the one the engine's string builder writes for
// the same card.
import type { ReactElement } from "react";
import { useTranslation } from "react-i18next";
// The stage labels are a LOOKUP TABLE indexed by position, read the way the
// resolution screen reads its number words.
import fr from "../../i18n/fr.json";
import { posterArtwork } from "../../lib/engine-drawing";
import { initials } from "../../lib/titles";
import type { QueueCard } from "../../lib/engine-queue";
import {
  Card,
  CardBody,
  CardContent,
  CardFolder,
  CardMeta,
  CardPoster,
  CardReason,
  CardStrip,
  CardSubtitle,
  CardTitle,
  CardTop,
  type StripState,
} from "../../ui/card";
import { Chip } from "../../ui/chip";
import { PosterArtwork } from "../../ui/poster";
import { actionButton, posterFallback, type ChipTone } from "../../ui/variants";
import { useArrivalsReference } from "./reference";

/** A staging card in the engine's names, narrowed to what this card reads. */
type StagingCard = {
  t: string;
  k?: string;
  s?: string;
  r?: string;
  chip?: [string, string] | null;
  strip?: (number | string)[];
  noposter?: boolean;
  poster?: string | null;
};

/**
 * Where the journey stands at one stage, from the value the strip carries.
 *
 * @param value `1` for a stage passed, `"now"`, `"blocked"`, anything else for one not reached.
 * @returns The step's state.
 */
function stageState(value: number | string): StripState {
  if (value === 1) return "done";
  if (value === "now") return "now";
  if (value === "blocked") return "blocked";
  return "pending";
}

/**
 * One staging card.
 *
 * @param properties The card, and the foot a section offers for its own action.
 * @returns The card.
 */
export function ArrivalCard({
  card: queued,
  foot,
}: {
  card: QueueCard;
  foot?: { label: string; act: string };
}): ReactElement {
  const reference = useArrivalsReference();
  const { t } = useTranslation();
  const card = queued as StagingCard;
  const title = card.t;
  const hasSheet = reference.sheetFor(title) != null;
  // french-ok: a panel ADDRESS and the non-medium marker, contract values the delegation and R46 read
  const folderAddress = `dossier:${title}`;
  const stages: string[] = fr.surfaces.card.stages;
  return (
    // french-ok: the non-medium marker R46 reads, a contract value
    <Card data-nonmedia={hasSheet ? undefined : "dossier"}>
      {hasSheet ? (
        <CardPoster
          as="button"
          aria-label={t("surfaces.card.sheetOf", { title })}
          data-mediasheet={title}
        >
          {card.noposter ? (
            <span className={posterFallback()} data-part="card/poster-fallback">
              <b>{initials(title)}</b>
            </span>
          ) : (
            <PosterArtwork artwork={posterArtwork(reference.icons, card.poster, title, card.k)} />
          )}
        </CardPoster>
      ) : (
        <CardFolder
          icon={reference.icons.folder}
          label={t("surfaces.card.folder")}
          aria-label={t("surfaces.card.folderActions", { title })}
          data-panel={folderAddress}
        />
      )}
      <CardContent>
        <CardTop>
          <CardBody data-panel={hasSheet ? `media:${title}` : folderAddress}>
            <CardTitle title={title}>{title}</CardTitle>
            {card.s ? <CardSubtitle>{card.s}</CardSubtitle> : null}
            {card.r ? <CardReason>{card.r}</CardReason> : null}
            {card.chip ? (
              <CardMeta>
                <Chip tone={card.chip[0] as ChipTone} label={card.chip[1]} />
              </CardMeta>
            ) : null}
          </CardBody>
        </CardTop>
        {card.strip ? (
          <CardStrip
            steps={card.strip.map((value, index) => ({ state: stageState(value), label: stages[index] }))}
          />
        ) : null}
        {foot ? (
          <button className={actionButton({ kind: "cardFoot" })} data-part="card/foot" data-act={foot.act}>
            {foot.label}
          </button>
        ) : null}
      </CardContent>
    </Card>
  );
}
