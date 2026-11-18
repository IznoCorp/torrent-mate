// What became of one Acquisition write, in the four ways `send()` can end.
//
// A verb that awaits `send()` bare reads three different events as one: the layer accepted (done), the
// network would not answer and the outbox KEEPS the write (held — the sentinel, not a result), the
// layer ANSWERED a refusal (a problem body), or nothing could even keep it (a plain error). Each is
// said in its own words: a held write is never announced as done, and a network error is never worded
// as a decision the layer did not make.
import { HELD, isRequestFailure, send, type RequestFailure } from "../../lib/query-client";

/** The four ends of a write. */
export type VerbOutcome<Answer> =
  | { kind: "done"; answer: Answer | undefined }
  | { kind: "held" }
  | { kind: "refused"; failure: RequestFailure }
  | { kind: "failed" };

/**
 * Sends one write and answers how it ended; it never throws.
 *
 * @param method The method.
 * @param path The contract address, parameters already substituted.
 * @param body What to send, if anything.
 * @returns Done with the layer's answer, held by the outbox, refused with the layer's reason, or failed.
 */
export async function sendVerb<Answer = unknown>(
  method: "POST" | "PUT" | "PATCH" | "DELETE",
  path: string,
  body?: unknown,
): Promise<VerbOutcome<Answer>> {
  try {
    const answer = await send<Answer>(method, path, body);
    return answer === HELD ? { kind: "held" } : { kind: "done", answer };
  } catch (error) {
    if (isRequestFailure(error)) return { kind: "refused", failure: error };
    // A failure that is not the layer's answer is not silent: it is the one trace of what happened.
    console.warn("an Acquisition write failed without an answer", error);
    return { kind: "failed" };
  }
}
