// design/src/screens/resolution.tsx
// Legacy `openResolve(cible)` (`refonte.html@60530dbd8`) — the arbitration screen —
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
// NO « SUIVANT », AND NO « n SUR m EN ATTENTE ». Every exit returns to
// « À traiter », whose tab count carries the number; a count that leads nowhere
// is noise on a phone.
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
import { useEngineDrawing } from "../../lib/engine-drawing";
import { useParams } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { useDecisions } from "./decision-queries";
import { useAcquisitionQueue, useStaging } from "../../lib/queue";
import { useUiState } from "../../lib/store-access";
import { Candidates, DecisionCard, ReleaseCard } from "./resolution-cards";
import { REASON_TONE, reasonDetail, reasonLabel } from "./decision-vocabulary";
import { actionButton, backAction, body, emptyNote, qualityHint, ruleNote, screen, screenBar, scrollport, sectionHeading, sheetActions, type ChipTone } from "../../ui/variants";
import { Chip } from "../../ui/chip";
import { CardMeta } from "../../ui/card";
import { guidance } from "../../ui/variants/layout";
import { Icon } from "../../ui/icon";
import { bridge } from "../../lib/shell-doors";

export function ResolutionScreen() {
  const { folder: raw } = useParams({ from: "/resolution/$folder" });
  // Defensive: `__screens.resolution` already normalises on write, but an entry
  // reached by a typed/bookmarked URL did not necessarily go through it.
  const folder = raw.normalize("NFC");
  const { icons } = useEngineDrawing();
  const { t } = useTranslation();
  // THE DECISIONS COME FROM THE CACHE (invariant 4). `decisionPending` and
  // `DECISIONS_REGLEES` were the engine's, read straight off the fixture; the
  // same two answers are derived here from `/api/decisions/`.
  const { data: decisions } = useDecisions();
  // THE SCREEN HOLDS THE QUEUE IN THE CACHE, and draws nothing from it. Its
  // exits act on the queue — a pick and « Laisser tel quel » take the folder out
  // of BOTH lists it appears on, read from the cache — and a screen opened on
  // its own, from a cold link, is the one reader that would otherwise leave the
  // cache empty: the exit would then take nothing out.
  const scenario = String(useUiState().scen) === "loaded" ? "loaded" : "";
  const { data: staging } = useStaging(scenario);
  useAcquisitionQueue(scenario);
  // A PLEX MATCH TO CORRECT opens this screen on the identity held — the one the
  // pipeline and Plex agreed on — never on « no medium identified »: the pick is
  // the correction, and « Chercher manuellement » names another.
  const held = staging?.settled.find((card) => card.title === folder)?.plexMatch ?? null;
  const heldCard = held ? staging?.settled.find((card) => card.title === folder) : undefined;
  const settledDecisions = decisions?.settled ?? [];
  const decisionPending = (subject: string | null) =>
    decisions?.pending.find((entry) => entry.folder === subject) ?? null;
  // A folder either HAS a pending decision or it has none, and the screen must
  // not borrow one. Showing another folder's candidates would be the worst
  // possible lie on the one screen whose job is to name what is on disk.
  const decision = decisionPending(folder);
  // The legacy screen picked its own subject between `decision.folder` and
  // `state.resolveTarget`; here the ROUTE PARAM is the identity, and
  // `decisionPending` matches on that very `folder` — so the two legacy branches
  // are one value. A target the door could not resolve at all reaches this
  // screen as the legacy's own last resort, « élément inconnu ».
  return (
    <section
      className={screen({ open: true })}
      data-part="screen"
      data-open=""
      data-key={`resolution:${folder}`}
      aria-label={folder}
    >
      <div className={screenBar()} data-part="screen/bar">
        <button className={backAction()} data-part="screen/back" onClick={() => bridge.back()}>
          <Icon paths={icons.left} />
          {t("screens.resolution.back")}
        </button>
      </div>
      <div className={scrollport()} data-part="viewport">
        <div className={body()} data-part="surface/body" data-region="screen-resolution/body">
          <div className="note" data-part="note">
            <b>{t("screens.resolution.noteTitle")}</b>{" "}
            {t("screens.resolution.noteOn")} <code>/medias</code>{" "}
            {t("screens.resolution.noteAppeared")}{" "}
            <em>{t("screens.resolution.noteUnder")}</em>{" "}
            {t("screens.resolution.noteRest")}
          </div>
          <h2 className={sectionHeading()} data-part="heading">
            <code>{folder}</code>
          </h2>
          <p className={qualityHint()}>
            {decision
              ? reasonDetail(decision.reason)
              : held
              ? t("screens.resolution.plexHeld", { title: held.title })
              : t("screens.resolution.noMediaIdentified")}
          </p>
          <CardMeta as="div" style={{ marginBottom: "12px" }}>
            {decision ? (
              <Chip
                tone={(REASON_TONE[decision.reason] ?? "neutral") as ChipTone}
                label={reasonLabel(decision.reason)}
              />
            ) : (
              ""
            )}
          </CardMeta>
          {decision ? (
            <Candidates decision={decision} />
          ) : held ? (
            <ReleaseCard
              title={held.title}
              year={null}
              meta={Object.entries(held.ids ?? {}).slice(0, 1)
                .map(([provider, identifier]) => `${provider.toUpperCase()} ${identifier}`).join("")}
              confidence={null}
              opts={{ genre: "candidat", poster: heldCard?.poster ?? null }}
            />
          ) : (
            <p className={ruleNote()}>{t("screens.resolution.noCandidates")}</p>
          )}
          <div className={emptyNote()} data-part="empty-state">
            <b>{t("screens.resolution.emptyTitle")}</b>
            {t("screens.resolution.emptyBody")}
            <button
              className={actionButton({ kind: "cardFoot" })}
              data-part="card/foot"
              style={{ marginTop: "10px" }}
              data-manual={folder || undefined}
            >
              {t("screens.resolution.searchManually")}
            </button>
          </div>
          <div className={sheetActions({ secondary: true })} data-part="sheet/actions">
            <button className={actionButton({ kind: "panelAction" })} data-part="sheet/action" data-leave={folder || undefined}>
              <Icon paths={icons.check} />
              {t("screens.resolution.leaveAsIs")}
            </button>
          </div>
          <div className={guidance()} data-part="guidance">
            <b>{t("screens.resolution.note2Title")}</b>{" "}
            {t("screens.resolution.note2Body")}
          </div>
          {settledDecisions.length > 0 ? (
            <>
              <h2 className={sectionHeading()} data-part="heading" style={{ marginTop: "18px" }}>
                {t("screens.resolution.settledHeading")}
              </h2>
              <p className={qualityHint()}>{t("screens.resolution.settledHint")}</p>
              {settledDecisions.slice(0, 6).map((settled) => (
                <DecisionCard key={settled.folder} decision={settled} />
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
