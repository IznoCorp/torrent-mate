// The three cards the resolution screen draws, beside the screen that draws
// them: a release CANDIDATE, a settled DECISION, and the list of candidates
// with what the ranking is allowed to claim about them. Each keeps the reason
// it is the shape it is; the screen keeps only the arbitration.
import { useTranslation } from "react-i18next";
import { type PendingDecision, type SettledDecision } from "./types";
import { actionButton, ruleNote, type ChipTone } from "../../ui/variants";
import {
  Card,
  CardBody,
  CardMeta,
  CardOverview,
  CardPoster,
  CardReason,
  CardSubtitle,
  CardTitle,
  CardTop,
} from "../../ui/card";
import { Chip } from "../../ui/chip";
import { PosterArtwork } from "../../ui/poster";
import { posterArtwork, useEngineDrawing } from "../../lib/engine-drawing";
import { candidateCard, pickPlace } from "./variants";
import { REASON_TONE, decisionState, decisionStateDetail, reasonLabel, viaLabel } from "./decision-vocabulary";

// A RELEASE is not a medium, and its card is deliberately a different object.
// A release has no media sheet and no panel — it is one candidate among
// several for a medium that is already named elsewhere on the screen. Giving
// it a card that addressed a panel would promise a sheet that cannot exist.
//
// It is marked `data-nonmedia` so the contract check can tell the two apart by
// construction rather than by knowing which screens draw which.
//
// The legacy twin was `releaseCardHTML(titre, meta, confiance, opts)`; the
// props below are that signature. Its emission stopped being the twin's the
// day the card became the gesture, below. The poster is `PosterArtwork`, resolved
// by `posterArtwork` — the one resolution every poster goes through, because a
// second copy of its image-or-initials fallback is exactly what would drift.
export function ReleaseCard({
  title,
  year,
  meta,
  confidence,
  opts,
}: {
  title: string;
  year: string | number | null;
  meta: string;
  confidence: string | null;
  opts: {
    genre?: string;
    k?: "movie" | "show";
    poster?: string | null;
    noPoster?: boolean;
    overview?: string;
    /** The provider identity the poster opens the sheet at, when the cache holds none under the title. */
    identity?: { provider: string; id: number | string };
    /** The candidate a re-opened decision had kept (« Corriger »): marked, so the choice being corrected is seen. */
    kept?: boolean;
  };
}) {
  const reference = useEngineDrawing();
  const { icons } = reference;
  const { t } = useTranslation();
  // ONE GESTURE PICKS, EVERYTHING ELSE LEARNS MORE (B-578, his 09-29 word:
  // « toucher l'affiche ou la carte d'un candidat OUVRE SA FICHE ; seul le
  // bouton « Choisir » choisit »). The poster and the body both open the
  // candidate's sheet — what a poster and a card do everywhere else — and
  // « Choisir » is a button of its own that carries the candidate's title in
  // `data-resolve`. All three are BUTTONS because the engine's delegation
  // answers `button` and nothing else, and they are SIBLINGS: a button holds
  // phrasing content only, so none can hold another. « Choisir » draws no
  // check: a check on every card read as « already selected » (B-500).
  //
  // EACH IS NAMED FROM ITS DATA. The pick is announced by its word, the title
  // and the year, never by the card's whole text — up to 524 characters
  // opening on the poster fallback's initial where the provider had no
  // picture; the year is a prop of its own rather than a slice of `meta`,
  // because re-parsing a display string to recover a datum the caller already
  // holds is how the two drift apart. The poster and the body are announced as
  // the sheet they open.
  const sheet = {
    "data-mediasheet": title || undefined,
    "data-provider": opts.identity?.provider,
    "data-provider-id": opts.identity === undefined ? undefined : String(opts.identity.id),
    "aria-label": t("surfaces.card.sheetOf", { title }),
  };
  return (
    <Card data-nonmedia={opts.genre || "release"} data-kept={opts.kept ? "" : undefined}>
      <CardTop>
        <CardPoster
          as="button"
          type="button"
          {...sheet}
          title={
            opts.noPoster ? t("screens.resolution.noPosterTitle") : undefined
          }
        >
          <PosterArtwork artwork={posterArtwork(icons, opts.poster, title, opts.k)} />
        </CardPoster>
        <CardBody type="button" className={candidateCard()} {...sheet}>
          <CardTitle>{title}</CardTitle>
          <CardSubtitle>{meta}</CardSubtitle>
          {/* The synopsis is what actually SEPARATES four series with nearly
              the same name, so it belongs on the card that asks to choose
              between them. It is an `overview`, not a reason: it clamps
              (R48 — a reason wraps and the card grows, a synopsis does not).
              Carrying it here is also what makes leaving the screen
              unnecessary: an arbitration that sends you to a full sheet to
              decide loses the queue you were working through. */}
          {opts.overview ? <CardOverview>{opts.overview}</CardOverview> : ""}
          {confidence || opts.kept ? (
            <CardMeta>
              {opts.kept ? <Chip tone="success" label={t("screens.resolution.kept")} /> : ""}
              {confidence ? (
                <Chip tone="info" label={<>{t("screens.resolution.confidence")} {confidence}</>} />
              ) : (
                ""
              )}
            </CardMeta>
          ) : (
            ""
          )}
        </CardBody>
        <span className={pickPlace()}>
          <button
            type="button"
            className={actionButton({ kind: "panelAction", tone: "primary" })}
            data-part="card/pick"
            data-resolve={title || undefined}
            aria-label={t("screens.resolution.chooseOf", { name: year ? `${title} ${year}` : title })}
          >
            {t("screens.resolution.choose")}
          </button>
        </span>
      </CardTop>
    </Card>
  );
}

// A DECISION is a FOLDER, and that is why it has its own card.
//
// The scrape could not name what is inside it, so what the operator is asked
// about is the thing on disk — never a media title, which is precisely what is
// missing. It carries no media sheet and no panel for the same reason a
// release candidate carries none: there is no medium here yet. Marked
// `data-nonmedia` so the contract check tells them apart by construction.
//
// A settled decision shows the CHOSEN medium's poster, and it is not a button:
// the card's subject is still the folder. One that recorded no choice
// (« remplacée depuis », « laissée telle quelle ») shows the placeholder,
// because nothing was chosen — the picture would be a guess, and a guess drawn
// as a fact is the failure this interface exists to avoid.
//
// The legacy twin is `decisionCardHTML(decision, opts)`. Its `opts.foot`
// variant — a `data-decision` footer button — is not carried over: no call
// site ever passed it and the click delegation reads no such attribute, so it
// would be a button leading nowhere.
export function DecisionCard({ decision }: { decision: SettledDecision }) {
  const reference = useEngineDrawing();
  const { icons } = reference;
  const settled = decision.state != null;
  const state = settled ? decisionState(decision.state) : null;
  const artwork =
    settled && decision.choice
      ? posterArtwork(icons, decision.choice.poster, decision.choice.title, decision.kind)
      : { source: undefined, icon: decision.kind === "movie" ? icons.film : icons.tv, label: "?" };
  const identity = decision.choice
    ? `${decision.choice.title} · ${decision.choice.provider.toUpperCase()} ${decision.choice.id} · ${viaLabel(decision.choice.via)}`
    : null;
  return (
    <Card data-nonmedia="decision">
      <CardTop>
        <CardPoster>
          <PosterArtwork artwork={artwork} />
        </CardPoster>
        <CardBody as="span">
          <CardTitle title={decision.folder}>
            <code>{decision.folder}</code>
          </CardTitle>
          <CardSubtitle>{decision.when}</CardSubtitle>
          {/* What was chosen is the most useful line here — it is the answer
              one comes back to read — so it wraps rather than truncating. On
              one line it lost its provider id and how it was found, which is
              exactly what one comes back for. */}
          {identity ? <CardReason>{identity}</CardReason> : ""}
          <CardMeta>
            <Chip
              tone={(REASON_TONE[decision.reason] ?? "neutral") as ChipTone}
              label={reasonLabel(decision.reason)}
            />
            {state ? (
              <Chip
                tone={state[0] as ChipTone}
                label={state[1]}
                title={decisionStateDetail(decision.state)}
              />
            ) : (
              ""
            )}
          </CardMeta>
        </CardBody>
      </CardTop>
    </Card>
  );
}

// The candidates, and what the ranking is allowed to claim about them. The
// legacy twin is `candidatsHTML(decision)`: a decision whose provider answered
// with NOTHING (`c: []`) draws no note and no card — the empty list is drawn
// as emptiness, not as a sentence about it. The sentence belongs to the other
// case (no pending decision at all), and it is the screen's own, below.
export function Candidates({ decision }: { decision: PendingDecision }) {
  const best = Math.max(...decision.candidates.map((candidate) => candidate.score));
  const tied = decision.candidates.filter((candidate) => candidate.score === best).length;
  const { t } = useTranslation();
  // The number words are a LOOKUP TABLE, read as one through `t()` the way
  // `card-markup.ts` reads the card's stages: a feature importing the
  // dictionary itself counts against its fan-in ceiling.
  const words = t("screens.resolution.numbers", { returnObjects: true }) as string[];
  return (
    <>
      {tied > 1 ? (
        <p className={ruleNote()}>
          {words[tied] ?? String(tied)} {t("screens.resolution.tieNote")}
        </p>
      ) : (
        ""
      )}
      {decision.candidates.map((candidate) => (
        <ReleaseCard
          key={`${candidate.provider}:${candidate.id}`}
          title={candidate.title}
          year={candidate.year ?? null}
          meta={`${candidate.year ? candidate.year + " · " : ""}${decision.kind === "movie" ? t("common.film") : t("common.series")} · ${candidate.provider.toUpperCase()} ${candidate.id}`}
          /* A score that ties with the others says nothing about this
             candidate, so it is not printed on it. */
          confidence={
            tied > 1 && candidate.score === best
              ? null
              : `${Math.round(candidate.score * 100)} %`
          }
          /* Its OWN picture only, and the placeholder when the provider has no
             picture: a candidate wearing a neighbour's poster is the one
             mistake this screen cannot make. The absence is said by the
             placeholder itself, not by a sentence in a line that truncates. */
          opts={{
            genre: "candidat",
            k: decision.kind as "movie" | "show",
            poster: candidate.poster,
            noPoster: candidate.withoutPoster,
            overview: candidate.overview,
            identity: { provider: candidate.provider, id: candidate.id },
            // A RE-OPENED DECISION OFFERS ITS OWN CANDIDATES, the one it kept
            // marked: « Corriger » is read against what is being corrected.
            kept: decision.kept?.provider === candidate.provider && decision.kept?.id === candidate.id,
          }}
        />
      ))}
    </>
  );
}
