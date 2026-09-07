// « Récupérer cette saison » — the verb a season with a hole owes (B-301).
//
// THE SEASON MATRIX SHOWED THE HOLE AND OFFERED NOTHING. It draws « Saison 3 ·
// 6/7 · 1 manquant » and there was no way to ask for the missing episode.
// DOIT-3 is « agir là où l'on observe »; this is where one observes it.
//
// IT LIVES IN `features/media/` BECAUSE THAT IS WHERE THE PANEL IS DRAWN, and
// invariant 7 is absolute: the media feature may not import
// `features/acquisition/`. What it does instead is call the OPERATION — a
// mutation on the contract is not a feature import. `features/media/queries.ts`
// is this feature's own door to the layer, and this is its mutating half.
//
// A FILE OF ITS OWN beside the block it serves, never a growth of
// `panel-seasons.tsx`: a verb is behaviour, the block is drawing, and invariant
// 6 asks for the cut before the ceiling rather than after it.
import i18next from "i18next";
import { HELD, send } from "../../lib/query-client";

/** What the operation answers, as the contract declares it. */
type SeasonGrab = {
  season: number;
  absorbedCount: number;
  queued: boolean;
  runUid: string | null;
};

/**
 * Asks for one season of one follow.
 *
 * WHAT IT SAYS DEPENDS ON WHAT CAME BACK, and that is DOIT-4 rather than a
 * nicety. An ask that arrives while the pipeline is working is QUEUED — the
 * interface says « En file — pipeline en cours » and never « occupé », and it
 * never shows the 409 the backend answers for that case (NE-DOIT-PAS-3, §20).
 * An ask that starts now says so. **A toast is written from the ANSWER, never
 * before it**: a sentence composed optimistically is a sentence that can be
 * right about nothing, which is NE-DOIT-PAS-1 and the defect `data-take` wore
 * for a whole wave.
 *
 * OFFLINE IS NOT A FAILURE. `send` answers `HELD` when the mutation is queued
 * for a network that is not there; saying « asked for » then would be a lie and
 * saying « failed » would be a worse one, so the interface says it is held.
 *
 * Args:
 *     title: The follow, as this interface knows it — by TITLE. The backend
 *         wants a rowid; that is a demand on the register (§ 2b), not something
 *         to invent here.
 *     season: The season number, 1-based.
 *
 * Returns:
 *     Whether the ask is WAITING on the pipeline rather than under way. The
 *     caller records it so the season can go on saying so after the message
 *     has gone (DOIT-4's visible half): a sentence shown for four seconds
 *     tells the operator who was looking, and nobody else.
 */
export async function grabSeason(title: string, season: number): Promise<boolean> {
  const say = (key: string, values?: Record<string, unknown>) =>
    i18next.t(`verbs.media.${key}`, values ?? {});
  try {
    const answered = await send<SeasonGrab>(
      "POST",
      `/api/acquisition/follows/${encodeURIComponent(title)}/seasons/${season}/grab`,
    );
    if (answered === HELD) {
      window.__toast?.show({ message: say("seasonHeld", { season }) });
      return false;
    }
    const grab = answered as SeasonGrab | undefined;
    window.__toast?.show({
      message: grab?.queued
        ? say("seasonQueued", { season })
        : say("seasonAsked", { season, count: grab?.absorbedCount ?? 0 }),
    });
    return grab?.queued === true;
  } catch {
    // THE REFUSAL IS SAID, and it is said as a refusal. Swallowing it would
    // leave the operator looking at a season that never moved with no reason
    // given — the silent failure this interface's own constitution refuses.
    window.__toast?.show({ message: say("seasonRefused", { season }) });
    return false;
  }
}
