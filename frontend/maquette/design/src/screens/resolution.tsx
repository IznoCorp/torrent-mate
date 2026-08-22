// design/src/screens/resolution.tsx
// Legacy `openResolve(cible)` (`refonte.html`) — the arbitration screen —
// reborn as a real route (`/resolution/$folder`) and a final component.
// Markup is TRANSPLANTED, not translated: every tag, class and data-attribute
// below is the one the legacy screen drew, so the same stylesheet applies
// unchanged. `data-key="resolution:" + dossier` is an identity this screen
// never had — the legacy `openScreen(html, undefined, …)` passed no `cle` at
// all — added here because a router-owned screen needs one to answer
// `.screen.open[data-key^="resolution:"]` the way every other migrated screen
// already does.
//
// ── L'écran de résolution ────────────────────────────────────────────────
// One screen answers two questions that used to live on two pages: « what is
// stuck » and « which medium is it ». It is a SCREEN and not a panel — on
// `/medias` the arbitration appeared UNDER the list being read, and on a phone
// it was never seen.
//
// What it is asked about is a FOLDER. The name is set in the mono face and
// never cleaned up: it is what is on disk, and recognising it is the whole
// point.
//
// THE SCORE IS SHOWN ONLY WHEN IT SEPARATES. « Lucky » is the real case that
// settles this: four of its five candidates came back at exactly 1.00.
// Printing « 100 % » four times suggests a ranking that does not exist and
// invites the operator to trust it. When the leaders tie, the screen says so —
// and that sentence is the reason a human is being asked at all.
//
// The desktop deck's keyboard shortcuts (← → ⏎) have no phone. What they were
// for — going through several in a row — is kept as a plain progression:
// « 1 sur 2 », and « Suivante » once this one is answered.
//
// Three ways out, and the third is the one that was missing: pick a candidate,
// search by hand, or LEAVE IT AS IT IS. The last exists in the engine
// (`dismissed`) and nowhere in the interface, so a folder whose automatic
// result was right had no way of being agreed with.
//
// Every way out carries NO onClick: the document-level click delegation the
// legacy engine still runs is the seam this screen leans on, exactly as
// `media.tsx`, `profile.tsx` and `releases.tsx`. `data-resolve` (pick this
// candidate) is read by the branch that treats `state.resolveTarget` as the
// folder and the attribute as the CHOICE — which is why the shell's
// `window.__screens.resolution()` door writes that target before navigating.
import { useParams } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
// The number words below are a LOOKUP TABLE, not prose: the same
// dictionary-by-direct-import rule `panel.tsx` follows for the settings
// dictionaries, and for the same reason — an index into a table is not a
// sentence, and `t()` would only wrap the lookup in a second one.
import fr from "../i18n/fr.json";
import {
  useStoreContent,
  useReference,
  type QueueCard,
  type PendingDecision,
  type SettledDecision,
} from "../data";

// Same helper as `media.tsx`'s, `profile.tsx`'s, `add.tsx`'s and
// `releases.tsx`'s, still not shared: the extraction those files' comments
// call for is a follow-up of its own, not a silent scope add here.
function Icon({ paths, strokeWidth }: { paths: string; strokeWidth?: number }) {
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
function ReleaseCard({
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
  const { posterBox } = useReference();
  const { t } = useTranslation();
  return (
    <div className="card" data-part="card" data-nonmedia={opts.genre || "release"}>
      <div className="ctop" data-part="card/top">
        <span
          className="poster"
          data-part="card/poster"
          title={
            opts.noPoster ? t("screens.resolution.noPosterTitle") : undefined
          }
          dangerouslySetInnerHTML={{
            __html: posterBox(title, opts.k, { exact: opts.exact }),
          }}
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
      <button className="cfoot solid" data-part="card/foot" data-solid="" data-resolve={title || undefined}>
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
function DecisionCard({ decision }: { decision: SettledDecision }) {
  const {
    posterBox,
    svgIcon,
    icons,
    DECISION_STATE,
    DECISION_STATE_DETAIL,
    REASON_TONE,
    REASON_LABEL,
    VIA_LABEL,
  } = useReference();
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
        <span
          className="poster"
          data-part="card/poster"
          dangerouslySetInnerHTML={{ __html: poster }}
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
function Candidates({ decision }: { decision: PendingDecision }) {
  const best = Math.max(...decision.c.map((candidate) => candidate.s));
  const tied = decision.c.filter((candidate) => candidate.s === best).length;
  const words: string[] = fr.screens.resolution.numbers;
  const { t } = useTranslation();
  return (
    <>
      {tied > 1 ? (
        <p className="rulenote">
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

export function ResolutionScreen() {
  const { folder: raw } = useParams({ from: "/resolution/$folder" });
  // Defensive: `__screens.resolution` already normalises on write, but an entry
  // reached by a typed/bookmarked URL did not necessarily go through it.
  const folder = raw.normalize("NFC");
  // The queue lists (`world.blocked` / `world.stuck` / `world.stuckReel`) are
  // MUTATED IN PLACE by `actionResolve` / `actionLeave` (splice, unshift),
  // which bump the store's `version` through `render()` without producing a new
  // `state` reference. Subscribing to `version` is what makes the progression
  // (« 1 sur 2 ») and « Passer à la suivante » answer the queue as it is now —
  // the legacy screen re-opened itself for the same reason.
  useStoreContent((c) => c.version);
  const {
    icons,
    REASON_DETAIL,
    REASON_LABEL,
    REASON_TONE,
    DECISIONS_REGLEES,
    decisionPending,
    derivedBlocked,
    derivedStuck,
  } = useReference();
  const { t } = useTranslation();
  // A folder either HAS a pending decision or it has none, and the screen must
  // not borrow one. Showing another folder's candidates would be the worst
  // possible lie on the one screen whose job is to name what is on disk.
  const decision = decisionPending(folder);
  // The queue spans BOTH surfaces a decision shows up on: « À traiter » on the
  // acquisition side and « Ça coince » in Arrivées. They are two views of one
  // thing — a folder the scrape could not name — and a progression that
  // counted only one of them would be wrong on the other.
  const pending = derivedBlocked()
    .concat(derivedStuck())
    .filter((card: QueueCard) => decisionPending(card.t as string) != null);
  const rank = decision
    ? pending.findIndex((card: QueueCard) => card.t === decision.d) + 1
    : 0;
  // The legacy screen picked its own subject between `decision.d` and
  // `state.resolveTarget`; here the ROUTE PARAM is the identity, and
  // `decisionPending` matches on that very `d` — so the two legacy branches
  // are one value. A target the door could not resolve at all reaches this
  // screen as the legacy's own last resort, « élément inconnu ».
  return (
    <section
      className="screen open"
      data-part="screen"
      data-open=""
      data-key={`resolution:${folder}`}
      aria-label={folder}
    >
      <div className="screenbar" data-part="screen/bar">
        <button className="fback" data-part="screen/back" onClick={() => window.__bridge.back()}>
          <Icon paths={icons.left} />
          {t("screens.resolution.back")}
        </button>
      </div>
      <div className="port" data-part="viewport">
        <div className="body" data-part="surface/body" data-region="screen-resolution/body">
          <div className="note" data-part="note">
            <b>{t("screens.resolution.noteTitle")}</b>{" "}
            {t("screens.resolution.noteOn")} <code>/medias</code>{" "}
            {t("screens.resolution.noteAppeared")}{" "}
            <em>{t("screens.resolution.noteUnder")}</em>{" "}
            {t("screens.resolution.noteRest")}
          </div>
          <h2 className="h2" data-part="heading">
            <code>{folder}</code>
          </h2>
          <p className="qhint">
            {decision
              ? (REASON_DETAIL[decision.reason] ?? "")
              : t("screens.resolution.noMediaIdentified")}
          </p>
          <div className="cmeta" data-part="card/meta" style={{ marginBottom: "12px" }}>
            {decision ? (
              <span
                className={`chip ${REASON_TONE[decision.reason] ?? "neutral"}`} data-part="chip"
                data-tone={REASON_TONE[decision.reason] ?? "neutral"}
              >
                {REASON_LABEL[decision.reason] ?? decision.reason}
              </span>
            ) : (
              ""
            )}
            {pending.length > 1 ? (
              <span className="caption" data-part="card/caption">
                {rank} {t("screens.resolution.outOf")} {pending.length}{" "}
                {t("screens.resolution.waiting")}
              </span>
            ) : (
              ""
            )}
          </div>
          {decision ? (
            <Candidates decision={decision} />
          ) : (
            <p className="rulenote">{t("screens.resolution.noCandidates")}</p>
          )}
          <div className="empty" data-part="empty-state">
            <b>{t("screens.resolution.emptyTitle")}</b>
            {t("screens.resolution.emptyBody")}
            <button
              className="cfoot"
              data-part="card/foot"
              style={{ marginTop: "10px" }}
              data-manual={folder || undefined}
            >
              {t("screens.resolution.searchManually")}
            </button>
          </div>
          <div className="sheetacts secondary" data-part="sheet/actions">
            <button className="sact" data-part="sheet/action" data-leave={folder || undefined}>
              <Icon paths={icons.check} />
              {t("screens.resolution.leaveAsIs")}
            </button>
            {pending.length > 1 ? (
              <button className="sact" data-part="sheet/action" data-next={folder}>
                <Icon paths={icons.right} />
                {t("screens.resolution.next")}
              </button>
            ) : (
              ""
            )}
          </div>
          <div className="note" data-part="note">
            <b>{t("screens.resolution.note2Title")}</b>{" "}
            {t("screens.resolution.note2Body")}
          </div>
          {DECISIONS_REGLEES.length > 0 ? (
            <>
              <h2 className="h2" data-part="heading" style={{ marginTop: "18px" }}>
                {t("screens.resolution.settledHeading")}
              </h2>
              <p className="qhint">{t("screens.resolution.settledHint")}</p>
              {DECISIONS_REGLEES.slice(0, 6).map((settled) => (
                <DecisionCard key={settled.d} decision={settled} />
              ))}
            </>
          ) : (
            ""
          )}
        </div>
      </div>
    </section>
  );
}
