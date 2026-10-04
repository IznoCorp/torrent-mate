// What the event stream looks like ON THE WIRE.
//
// ITS OWN FILE BECAUSE IT IS ITS OWN SUBJECT, and the split is on that rather
// than on a line count: this is the shape of a frame and the arithmetic of a
// cursor — facts about the PROTOCOL, true of the real server as much as of the
// fake — while `stream.ts` is a server that behaves. Nothing here holds state.
//
// The protocol is `docs/production/web-ui.md` § WebSocket Protocol.

/** What the server pushes once, before anything else. */
export const HELLO_TYPE = "ws.hello";
/** What the server pushes after thirty seconds of client silence. */
export const PING_TYPE = "ws.ping";

/** What the hello carries. Fixed, so a rule can assert it without a fixture. */
export const BUILD_COMMIT = "0000000000000000000000000000000000000000";

/**
 * One entry of the stream, as the server writes it.
 *
 * The `id` is the Redis stream cursor the client sends back as `last_id`. Its
 * shape is the real one — `<milliseconds>-<sequence>` — because the client
 * compares cursors and a shape it never meets in the maquette is a shape its
 * comparison is never proved against.
 */
export type StreamEntry = {
  id: string;
  type: string;
  data: Record<string, unknown>;
};

/**
 * Says whether one cursor comes strictly after another.
 *
 * RE-EXPORTED FROM `lib/`, not implemented here. The relay compares cursors to
 * refuse one that moves backwards and this server compares them to replay from
 * an exclusive lower bound — one arithmetic, one trap, one place.
 */
export { isNewerCursor } from "../lib/stream-cursor";
