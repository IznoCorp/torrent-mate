// The three cards the resolution screen draws, beside the screen that draws
// them: a release CANDIDATE, a settled DECISION, and the list of candidates
// with what the ranking is allowed to claim about them. Each keeps the reason
// it is the shape it is; the screen keeps only the arbitration.
import { useTranslation } from "react-i18next";
// The number words below are a LOOKUP TABLE, not prose: the same
// dictionary-by-direct-import rule `panel.tsx` follows for the settings
// dictionaries, and for the same reason — an index into a table is not a
// sentence, and `t()` would only wrap the lookup in a second one.
import fr from "../../i18n/fr.json";
import { useArrivalsReference, type PendingDecision, type SettledDecision } from "./reference";
import { actionButton, ruleNote } from "../../ui/variants";
import { Markup } from "../../ui/markup";

// A RELEASE is not a medium, and its card is deliberately a different object.
// A release has no media sheet and no panel — it is one candidate among
// several for a medium that is already named elsewhere on the screen. Giving
// it a card that addressed a panel would promise a sheet that cannot exist.
//
// It is marked `data-nonmedia` so the contract check can tell the two apart by
// construction rather than by knowing which screens draw which.
//
// The legacy twin is `releaseCardHTML(titre, meta, confiance, opts)`; the
// props below are that signature, and the emission is the same tags, classes
// and attributes. The poster's inner markup comes from the published
// `posterBox` rather than from a re-implementation: its image-or-initials
// fallback is exactly what a second copy would drift on.
export function ReleaseCard({
  title,
  meta,
  confidence,
  opts,
}: {
  title: string;
  meta: string;
  confidence: string | null;
  opts: {
    genre?: string;
    k?: "movie" | "show";
    exact?: boolean;
    noPoster?: boolean;
    overview?: string;
  };
}) {
  const { posterBox } = useArrivalsReference();
  const { t } = useTranslation();
  return (
    <div className="card" data-part="card" data-nonmedia={opts.genre || "release"}>
      <div className="ctop" data-part="card/top">
        <Markup tag="span"
          className="poster"
          data-part="card/poster"
          title={
            opts.noPoster ? t("screens.resolution.noPosterTitle") : undefined
          }
          html={posterBox(title, opts.k, { exact: opts.exact })}
        />
        <span className="cbody" data-part="card/body">
          <span className="ctitle" data-part="card/title">{title}</span>
          <span className="csub" data-part="card/subtitle">{meta}</span>
          {/* The synopsis is what actually SEPARATES four series with nearly
              the same name, so it belongs on the card that asks to choose
              between them. It is an `overview`, not a reason: it clamps
              (R48 — a reason wraps and the card grows, a synopsis does not).
              Carrying it here is also what makes leaving the screen
              unnecessary: an arbitration that sends you to a full sheet to
              decide loses the queue you were working through. */}
          {opts.overview ? <span className="cov" data-part="card/overview">{opts.overview}</span> : ""}
          {confidence ? (
            <span className="cmeta" data-part="card/meta">
              <span className="chip info" data-part="chip" data-tone="info">
                {t("screens.resolution.confidence")} {confidence}
              </span>
            </span>
          ) : (
            ""
          )}
        </span>
      </div>
      <button className={`cfoot solid ${actionButton()}`} data-part="card/foot" data-solid="" data-resolve={title || undefined}>
        {t("screens.resolution.pickThis")}
      </button>
    </div>
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
  const {
    posterBox,
    svgIcon,
    icons,
    DECISION_STATE,
    DECISION_STATE_DETAIL,
    REASON_TONE,
    REASON_LABEL,
    VIA_LABEL,
  } = useArrivalsReference();
  const settled = decision.state != null;
  const state = settled ? DECISION_STATE[decision.state] : null;
  const poster =
    settled && decision.choice
      ? posterBox(decision.choice.t, decision.k)
      : `<span class="pfall" data-part="card/poster-fallback">${svgIcon(decision.k === "movie" ? icons.film : icons.tv, 1.25)}<b>?</b></span>`;
  const identity = decision.choice
    ? `${decision.choice.t} · ${decision.choice.p.toUpperCase()} ${decision.choice.id} · ${VIA_LABEL[decision.choice.via] ?? decision.choice.via}`
    : null;
  return (
    <div className="card" data-part="card" data-nonmedia="decision">
      <div className="ctop" data-part="card/top">
        <Markup tag="span"
          className="poster"
          data-part="card/poster"
          html={poster}
        />
        <span className="cbody" data-part="card/body">
          <span className="ctitle" data-part="card/title" title={decision.d}>
            <code>{decision.d}</code>
          </span>
          <span className="csub" data-part="card/subtitle">{decision.when}</span>
          {/* What was chosen is the most useful line here — it is the answer
              one comes back to read — so it wraps rather than truncating. On
              one line it lost its provider id and how it was found, which is
              exactly what one comes back for. */}
          {identity ? <span className="creason" data-part="card/reason">{identity}</span> : ""}
          <span className="cmeta" data-part="card/meta">
            <span className={`chip ${REASON_TONE[decision.reason] ?? "neutral"}`} data-part="chip"
              data-tone={REASON_TONE[decision.reason] ?? "neutral"}>
              {REASON_LABEL[decision.reason] ?? decision.reason}
            </span>
            {state ? (
              <span
                className={`chip ${state[0]}`} data-part="chip" data-tone={state[0]}
                title={DECISION_STATE_DETAIL[decision.state] ?? ""}
              >
                {state[1]}
              </span>
            ) : (
              ""
            )}
          </span>
        </span>
      </div>
    </div>
  );
}

// The candidates, and what the ranking is allowed to claim about them. The
// legacy twin is `candidatsHTML(decision)`: a decision whose provider answered
// with NOTHING (`c: []`) draws no note and no card — the empty list is drawn
// as emptiness, not as a sentence about it. The sentence belongs to the other
// case (no pending decision at all), and it is the screen's own, below.
export function Candidates({ decision }: { decision: PendingDecision }) {
  const best = Math.max(...decision.c.map((candidate) => candidate.s));
  const tied = decision.c.filter((candidate) => candidate.s === best).length;
  const words: string[] = fr.screens.resolution.numbers;
  const { t } = useTranslation();
  return (
    <>
      {tied > 1 ? (
        <p className={ruleNote()}>
          {words[tied] ?? String(tied)} {t("screens.resolution.tieNote")}
        </p>
      ) : (
        ""
      )}
      {decision.c.map((candidate) => (
        <ReleaseCard
          key={`${candidate.p}:${candidate.id}`}
          title={candidate.t}
          meta={`${candidate.y ? candidate.y + " · " : ""}${decision.k === "movie" ? t("common.film") : t("common.series")} · ${candidate.p.toUpperCase()} ${candidate.id}`}
          /* A score that ties with the others says nothing about this
             candidate, so it is not printed on it. */
          confidence={
            tied > 1 && candidate.s === best
              ? null
              : `${Math.round(candidate.s * 100)} %`
          }
          /* Exact match only, and the placeholder when the provider has no
             picture: a candidate wearing a neighbour's poster is the one
             mistake this screen cannot make. The absence is said by the
             placeholder itself, not by a sentence in a line that truncates. */
          opts={{
            genre: "candidat",
            k: decision.k,
            exact: true,
            noPoster: candidate.sans,
            overview: candidate.resume,
          }}
        />
      ))}
    </>
  );
}
