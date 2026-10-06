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
// The end is the registered verb `session-end` (`session-end.ts`), so the consent rule covers it.
//
// THE STATES ARE NAMED in `variants.ts` and in the harness: loading, the list, only the current
// session, one being ended, a refusal, and the network down (the end is HELD by the outbox and
// said so, never shown as done).
//
// THE NOTICES SIT UNDER THE LIST, newest first, an unread one distinguished. They are marked read
// by the account's own press, « Tout marquer comme lu », which names the newest notice it saw: one
// raised meanwhile is not marked unseen. THEIR STATES ARE NAMED TOO — being read, failed to read
// (with a retry), none to report, the mark being written, refused, or HELD offline (said, and the
// button off so the mark is not queued twice) — because nothing happens in silence.
import { useEffect, useState, type ReactElement } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { momentOf } from "../../lib/clock";
import { HELD, read, send } from "../../lib/query-client";
import { Chip } from "../../ui/chip";
import { actionButton, factsPanel, guidance, keyValueRow, loadError, loadErrorAction, qualityHint, sectionHeading, settingRow, surfaceError } from "../../ui/variants";
import { forgetEndings, SESSIONS_KEY, useEndings, WORDS } from "./session-end";
import { noticeRow, noticesBlock, sessionRow } from "./variants";
import type { components } from "../../contract/types";

type OwnSession = components["schemas"]["OwnSession"];
type Notice = components["schemas"]["Notice"];

const NOTICES_KEY = ["/api/v1/notices"];

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
  const sessions = useOwnSessions();
  const endings = useEndings();
  // A visit starts from the server's list: an end still held when Profil was left is not carried over.
  useEffect(() => forgetEndings, []);

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
        <div className={loadError()} role="alert" data-part="profile/sessions-failed">
          <b>{t(`${WORDS}.loadFailed`)}</b>
          <button type="button" className={loadErrorAction()} onClick={() => void sessions.refetch()}>{t(`${WORDS}.retry`)}</button>
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
                    data-session-end={session.id} disabled={ending?.kind === "ending"}>
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
 * @returns The block, in the state the read and the mark are in.
 */
function NoticesList(): ReactElement {
  const { t } = useTranslation();
  const client = useQueryClient();
  const notices = useNotices();
  const [marking, setMarking] = useState<"rest" | "marking" | "failed" | "held">("rest");
  const list = notices.data?.notices ?? [];
  const unread = list.filter((one) => one.readAt === undefined);
  const state = notices.isError ? "failed"
    : notices.data === undefined ? "loading"
      : list.length === 0 ? "empty"
        : marking === "marking" ? "marking"
          : marking === "failed" ? "mark-failed"
            : marking === "held" && unread.length > 0 ? "held"
              : "list";
  // THE NEWEST NOTICE THE ACCOUNT SAW: one raised after it has a higher id and stays unread.
  const newest = Math.max(0, ...list.map((one) => one.id));

  async function markAll(): Promise<void> {
    // ONE WRITE AT A TIME: a press while one is asked or held queues nothing more.
    if (marking === "marking" || marking === "held") return;
    setMarking("marking");
    try {
      const answer = await send("POST", "/api/v1/notices/read", { upTo: newest });
      // HELD offline: the mark is not done and is not shown as done; a refetch would only put the
      // unread marks back over it, so none is asked and the button stays off.
      if (answer === HELD) return setMarking("held");
      setMarking("rest");
      await client.invalidateQueries({ queryKey: NOTICES_KEY });
    } catch {
      setMarking("failed");
    }
  }

  return (
    <div className={noticesBlock({ state })} data-part="profile/notices" data-state={state} data-unread={unread.length}>
      <h3 className={sectionHeading()} data-part="heading">{t(`${WORDS}.notices.heading`)}</h3>
      {state === "loading" ? (
        <p className={qualityHint()} role="status" data-part="profile/notices-loading">{t(`${WORDS}.notices.loading`)}</p>
      ) : null}
      {state === "failed" ? (
        <div className={loadError()} role="alert" data-part="profile/notices-failed">
          <b>{t(`${WORDS}.notices.loadFailed`)}</b>
          <button type="button" className={loadErrorAction()} onClick={() => void notices.refetch()}>{t(`${WORDS}.retry`)}</button>
        </div>
      ) : null}
      {state === "empty" ? (
        <p className={qualityHint()} data-part="profile/notices-none">{t(`${WORDS}.notices.none`)}</p>
      ) : null}
      {list.length > 0 ? (
        <div className={factsPanel()} data-part="panel">
          {list.map((notice) => (
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
      ) : null}
      {state === "mark-failed" ? (
        <p className={surfaceError({ tone: "danger" })} role="status" data-part="profile/notices-refusal">
          {t(`${WORDS}.notices.markFailed`)}
        </p>
      ) : null}
      {state === "held" ? (
        <p className={qualityHint()} role="status" data-part="profile/notices-held">{t(`${WORDS}.notices.held`)}</p>
      ) : null}
      {unread.length > 0 ? (
        <button type="button" className={actionButton({ kind: "cardFoot" })} data-part="profile/notices-mark"
          disabled={state === "marking" || state === "held"} onClick={() => void markAll()}>
          {t(state === "marking" ? `${WORDS}.notices.marking` : `${WORDS}.notices.markAll`)}
        </button>
      ) : null}
    </div>
  );
}
