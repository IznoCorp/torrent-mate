// A card on « Arrivées »: what the staging area holds, drawn as the one card
// every list draws.
//
// ONE CARD, ONE BEHAVIOUR (R41–R46). The poster opens the media sheet; the body
// opens the panel. A folder the scrape could not name has no sheet to open, so
// it does not wear a poster: it wears a FOLDER, which addresses the folder's own
// panel and nothing else, and the card says it is not a medium.
//
// NO HANDLER IS ATTACHED HERE. The document-level delegation answers
// `data-mediasheet` and `data-panel` on the button tapped, which is
// why every attribute below is the one the engine's string builder writes for
// the same card.
import type { ReactElement } from "react";
import { useTranslation } from "react-i18next";
// The stage labels are a LOOKUP TABLE indexed by position, read the way the
// resolution screen reads its number words.
import fr from "../../i18n/fr.json";
import { posterArtwork, useEngineDrawing } from "../../lib/engine-drawing";
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

/** A staging card in the engine's names, narrowed to what this card reads. */
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
  foot?: { label: string; attributes: Record<string, string> };
}): ReactElement {
  const reference = useEngineDrawing();
  const { t } = useTranslation();
  const card = queued;
  const title = card.title;
  // A sheet stands behind a card exactly when the card carries provider ids.
  const hasSheet = card.ids != null;
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
          {card.withoutPoster ? (
            <span className={posterFallback()} data-part="card/poster-fallback">
              <b>{initials(title)}</b>
            </span>
          ) : (
            <PosterArtwork artwork={posterArtwork(reference.icons, card.poster, title)} />
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
            {card.secondaryLine ? <CardSubtitle>{card.secondaryLine}</CardSubtitle> : null}
            {card.reason ? <CardReason>{card.reason}</CardReason> : null}
            {card.chip ? (
              <CardMeta>
                <Chip tone={card.chip.tone as ChipTone} label={card.chip.text} />
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
          <button className={actionButton({ kind: "cardFoot" })} data-part="card/foot" {...foot.attributes}>
            {foot.label}
          </button>
        ) : null}
      </CardContent>
    </Card>
  );
}
