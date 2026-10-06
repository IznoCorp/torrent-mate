// The signed-in account's own sessions and its in-app notices (the operator's ruling Q4 A,
// 2026-10-06: every new Plex session is told « par FCM et dans l'application » ; Profil lists
// the live sessions, each revocable).
//
// THE MAQUETTE HOLDS ONE SESSION, the identity dialled: the seed's `current` one. The others are
// the account's sessions elsewhere, held beside the layer's state and renewed with it, the
// cross-seed subject's own discipline. Revoking one ends it at once; the current one is refused
// `session.current`, an id the account does not hold `session.unknown` — the server's answers.
import SEED from "../seeds/own-sessions.json";
import { DELETE, GET, POST, field, route } from "./shared";
import { refused, type MockRoute } from "../router";
import { mockState } from "../state";
import type { components } from "../../contract/types";

type Schemas = components["schemas"];

const NOT_FOUND = 404;
const CONFLICT = 409;
const MILLISECONDS = 1000;

/** What the layer holds of the subject: the live sessions and the notices. */
type Held = { sessions: Schemas["OwnSession"][]; notices: Schemas["Notice"][] };

const held = new WeakMap<object, Held>();

/**
 * The subject, seeded once per layer state.
 *
 * @returns The sessions and notices the layer holds now.
 */
function subject(): Held {
  const owner = mockState();
  let found = held.get(owner);
  if (!found) {
    found = structuredClone(SEED) as Held;
    held.set(owner, found);
  }
  return found;
}

/** The dials a named state turns to pose the subject no verb leaves it in. */
export type OwnSessionDials = {
  /** The account's other sessions are all gone: only the session in hand is left. */
  poseOnlyCurrentSession: () => void;
  /** Every notice of the account is marked read. */
  poseNoticesRead: () => void;
  /** The account has no notice at all. */
  poseNoNotices: () => void;
};

/** Those dials, over the subject. */
export const ownSessionDials: OwnSessionDials = {
  poseOnlyCurrentSession: () => {
    const state = subject();
    state.sessions = state.sessions.filter((one) => one.current);
  },
  poseNoticesRead: () => {
    for (const notice of subject().notices) notice.readAt ??= Math.floor(Date.now() / MILLISECONDS);
  },
  poseNoNotices: () => {
    subject().notices = [];
  },
};

export function ownSessionRoutes(): MockRoute[] {
  return [
    route("readOwnSessions", GET, "/auth/sessions", () => ({ sessions: subject().sessions })),
    route("revokeOwnSession", DELETE, "/auth/sessions/{sessionId}", (request) => {
      const state = subject();
      const target = state.sessions.find((one) => String(one.id) === request.parameters.sessionId);
      if (!target) return refused(NOT_FOUND, "no live session of this account holds that id", "session.unknown");
      if (target.current) return refused(CONFLICT, "the current session is ended by signing out", "session.current");
      state.sessions = state.sessions.filter((one) => one !== target);
      return { ok: true };
    }),
    route("readNotices", GET, "/notices", () => ({ notices: subject().notices })),
    // Marks what the account saw: every notice numbered `upTo` or lower, none after it. A second
    // call marks nothing and keeps the first read time, the server's own answer.
    route("markNoticesRead", POST, "/notices/read", (request) => {
      const upTo = Number(field(request.body, "upTo"));
      const unread = subject().notices.filter((one) => one.id <= upTo && one.readAt === undefined);
      for (const notice of unread) notice.readAt = Math.floor(Date.now() / MILLISECONDS);
      return { marked: unread.length };
    }),
  ];
}
