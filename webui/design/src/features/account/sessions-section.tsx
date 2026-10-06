// « Appareils connectés », in Profil — where the account is signed in, and what it was told of its
// latest sign-ins.
//
// The operator's ruling Q4 A (2026-10-06): a Plex sign-in can be phished, so every account sees its
// live sessions and ends the ones it does not recognise; a new session is told in the application
// (and by push). Both are the ACCOUNT'S OWN acts — no right, like its language and its switches.
//
// THE CURRENT SESSION IS NAMED AND NEVER OFFERED « Mettre fin » (signing out is the page's own
// button): the server refuses it too (`session.current`). Every other session carries one, and it
// asks first — a confirmation that names the device — because ending a session cannot be undone.
//
// THE STATES ARE NAMED in `variants.ts` and in the harness: loading, the list, only the current
// session, one being ended, a refusal, and the network down (the end is HELD by the outbox and
// said so, never shown as done).
//
// THE NOTICES SIT UNDER THE LIST, newest first, an unread one distinguished. They are marked read
// by the account's own press, « Tout marquer comme lu », which names the newest notice it saw: one
// raised meanwhile is not marked unseen.
import { useState, type ReactElement } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { momentOf } from "../../lib/clock";
import { dialog } from "../../lib/shell-doors";
import { HELD, read, send } from "../../lib/query-client";
import { refusalWords } from "../../lib/refusal";
import { Chip } from "../../ui/chip";
import { actionButton, factsPanel, guidance, keyValueRow, qualityHint, sectionHeading, settingRow, surfaceError } from "../../ui/variants";
import { noticeRow, sessionRow } from "./variants";
import type { components } from "../../contract/types";

type OwnSession = components["schemas"]["OwnSession"];
type Notice = components["schemas"]["Notice"];

const SESSIONS_KEY = ["/api/v1/auth/sessions"];
const NOTICES_KEY = ["/api/v1/notices"];
const WORDS = "screens.accountPage.sessions";

/** Where one session's end stands, by session id: asked of the server, held offline, or refused with words. */
type Ending = { kind: "ending" } | { kind: "held" } | { kind: "refused"; words: string };

/**
 * The account's live sessions, read from the server.
 *
 * @returns The query.
 */
function useOwnSessions() {
  return useQuery({
    queryKey: SESSIONS_KEY,
    queryFn: () => read<{ sessions: OwnSession[] }>("/api/v1/auth/sessions"),
  });
}

/**
 * The account's notices, read from the server.
 *
 * @returns The query.
 */
function useNotices() {
  return useQuery({
    queryKey: NOTICES_KEY,
    queryFn: () => read<{ notices: Notice[] }>("/api/v1/notices"),
  });
}

/**
 * The « Appareils connectés » section.
 *
 * @returns The section.
 */
export function SessionsSection(): ReactElement {
  const { t } = useTranslation();
  const client = useQueryClient();
  const sessions = useOwnSessions();
  const [endings, setEndings] = useState<Record<number, Ending>>({});

  function settle(id: number, ending: Ending | null): void {
    setEndings((held) => {
      const { [id]: _gone, ...rest } = held;
      return ending === null ? rest : { ...rest, [id]: ending };
    });
  }

  async function end(session: OwnSession): Promise<void> {
    settle(session.id, { kind: "ending" });
    try {
      const answer = await send("DELETE", `/api/v1/auth/sessions/${session.id}`);
      // HELD: the network is down and the outbox keeps the end — it is not done, and is not shown as done.
      if (answer === HELD) return settle(session.id, { kind: "held" });
      settle(session.id, null);
      await client.invalidateQueries({ queryKey: SESSIONS_KEY });
    } catch (refused) {
      settle(session.id, { kind: "refused", words: refusalWords(refused, `${WORDS}.refused`) });
      await client.invalidateQueries({ queryKey: SESSIONS_KEY });
    }
  }

  function confirmEnd(session: OwnSession): void {
    const device = session.device ?? t(`${WORDS}.unknownDevice`);
    dialog?.open({
      heading: t(`${WORDS}.confirm.heading`),
      body: [{
        type: "paragraph",
        runs: [
          { text: t(`${WORDS}.confirm.bodyBefore`) },
          { text: device, strong: true },
          { text: t(`${WORDS}.confirm.bodyAfter`) },
        ],
      }],
      actions: [
        { text: t(`${WORDS}.confirm.confirm`), tone: "danger", run: () => void end(session) },
        { text: t(`${WORDS}.confirm.cancel`), tone: "ghost", dismiss: true },
      ],
    });
  }

  const others = sessions.data?.sessions.filter((one) => !one.current) ?? [];
  const state = sessions.isError ? "failed" : sessions.data === undefined ? "loading" : others.length === 0 ? "only-current" : "list";

  return (
    <section data-part="profile/sessions" data-state={state}>
      <h2 className={sectionHeading()} data-part="heading">{t(`${WORDS}.heading`)}</h2>
      <p className={guidance()} data-part="profile/sessions-guidance">{t(`${WORDS}.intro`)}</p>
      {state === "loading" ? (
        <p className={qualityHint()} role="status" data-part="profile/sessions-loading">{t(`${WORDS}.loading`)}</p>
      ) : null}
      {state === "failed" ? (
        <div className={surfaceError({ tone: "danger" })} role="alert" data-part="profile/sessions-failed">
          <b>{t(`${WORDS}.loadFailed`)}</b>
          <button type="button" onClick={() => void sessions.refetch()}>{t(`${WORDS}.retry`)}</button>
        </div>
      ) : null}
      {sessions.data ? (
        <div className={factsPanel()} data-part="panel">
          {sessions.data.sessions.map((session) => {
            const ending = endings[session.id];
            const rowState = session.current ? "current" : (ending?.kind ?? "rest");
            return (
              <div key={session.id} className={`${keyValueRow()} ${settingRow()} ${sessionRow({ state: rowState })}`}
                data-part="profile/session" data-session-state={rowState} data-current={session.current || undefined}>
                <div className="min-w-0">
                  <div className="font-semibold">{session.device ?? t(`${WORDS}.unknownDevice`)}</div>
                  {session.current ? (
                    <div className="my-1 flex"><Chip tone="success" label={t(`${WORDS}.current`)} /></div>
                  ) : null}
                  <div className={qualityHint()}>
                    {t(`${WORDS}.lastSeen`, { moment: momentOf(session.lastSeenAt) })}
                  </div>
                  {ending?.kind === "held" ? (
                    <div className={qualityHint()} role="status" data-part="profile/session-held">{t(`${WORDS}.held`)}</div>
                  ) : null}
                  {ending?.kind === "refused" ? (
                    <p className={surfaceError({ tone: "danger" })} role="status" data-part="profile/session-refusal">
                      {ending.words}
                    </p>
                  ) : null}
                </div>
                {session.current || ending?.kind === "held" ? null : (
                  <button type="button" className={actionButton({ kind: "panelAction" })} data-part="profile/session-end"
                    disabled={ending?.kind === "ending"} onClick={() => confirmEnd(session)}>
                    {t(ending?.kind === "ending" ? `${WORDS}.ending` : `${WORDS}.end`)}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      ) : null}
      {state === "only-current" ? (
        <p className={qualityHint()} data-part="profile/sessions-only-current">{t(`${WORDS}.onlyCurrent`)}</p>
      ) : null}
      <NoticesList />
    </section>
  );
}

/**
 * The sign-in notices of the account, the unread ones distinguished and marked read by a press.
 *
 * @returns The list, or nothing while the account has no notice.
 */
function NoticesList(): ReactElement | null {
  const { t } = useTranslation();
  const client = useQueryClient();
  const { data } = useNotices();
  const [marking, setMarking] = useState<"rest" | "marking" | "failed">("rest");
  if (!data || data.notices.length === 0) return null;
  const unread = data.notices.filter((one) => one.readAt === undefined);
  // THE NEWEST NOTICE THE ACCOUNT SAW: one raised after it has a higher id and stays unread.
  const newest = Math.max(...data.notices.map((one) => one.id));

  async function markAll(): Promise<void> {
    setMarking("marking");
    try {
      const answer = await send("POST", "/api/v1/notices/read", { upTo: newest });
      setMarking("rest");
      // HELD offline: nothing new to show, and a refetch would put the unread marks back over it.
      if (answer !== HELD) await client.invalidateQueries({ queryKey: NOTICES_KEY });
    } catch {
      setMarking("failed");
    }
  }

  return (
    <div data-part="profile/notices" data-unread={unread.length}>
      <h3 className={sectionHeading()} data-part="heading">{t(`${WORDS}.notices.heading`)}</h3>
      <div className={factsPanel()} data-part="panel">
        {data.notices.map((notice) => (
          <div key={notice.id} className={`${keyValueRow()} ${noticeRow({ unread: notice.readAt === undefined })}`}
            data-part="profile/notice" data-notice-code={notice.code} data-unread={notice.readAt === undefined || undefined}>
            <div className="min-w-0">
              <div>{t(`notices.${notice.code}`, notice.params)}</div>
              <div className={qualityHint()}>{momentOf(notice.createdAt)}</div>
            </div>
            {notice.readAt === undefined ? <Chip tone="info" label={t(`${WORDS}.notices.new`)} /> : null}
          </div>
        ))}
      </div>
      {marking === "failed" ? (
        <p className={surfaceError({ tone: "danger" })} role="status" data-part="profile/notices-refusal">
          {t(`${WORDS}.notices.markFailed`)}
        </p>
      ) : null}
      {unread.length > 0 ? (
        <button type="button" className={actionButton({ kind: "cardFoot" })} data-part="profile/notices-mark"
          disabled={marking === "marking"} onClick={() => void markAll()}>
          {t(marking === "marking" ? `${WORDS}.notices.marking` : `${WORDS}.notices.markAll`)}
        </button>
      ) : null}
    </div>
  );
}
