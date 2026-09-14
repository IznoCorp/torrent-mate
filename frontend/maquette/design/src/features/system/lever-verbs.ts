// What answers a tap on one of the pipeline's levers.
//
// THE VERBS ARE REGISTERED, NOT DELEGATED TO THE ENGINE. `lib/verbs.ts` is the
// registry a feature declares its own `data-*` into; the engine knows none of
// these names and answers none of them, and no line is added to it for them.
//
// A VERB CALLS THE OPERATION AND NOTHING ELSE. It does not write the store, it
// does not decide what the screen then says: the read that draws the section is
// invalidated and says what the server now answers. A verb that wrote the
// interface's own copy of the state would be the defect invariant 4 names — and
// the one B-371 is, one page away.
import { registerVerb } from "../../lib/verbs";
import { HELD, send, sharedQueryClient } from "../../lib/query-client";
import { panel } from "../../lib/shell-doors";

/** The reads a lever moves, so what is on screen follows what was asked. */
const PIPELINE = ["/api/pipeline/status"];
const LOCKS = ["/api/maintenance/locks"];

/** What the automatic trigger's control carries when it would turn it on. */
const ON = "on";

/**
 * Asks the server, then re-reads what the section draws.
 *
 * @param address The operation's address.
 * @param body What to send, when the operation takes one.
 */
async function ask(address: string, body?: unknown): Promise<void> {
  await send("POST", address, body);
  // BOTH READS, because both project the fact that moved (§13): the pipeline's
  // own state and the lock its run holds are one question with two readers, and
  // refreshing one of them is how a screen comes to disagree with itself.
  for (const key of [PIPELINE, LOCKS]) {
    await sharedQueryClient?.invalidateQueries({ queryKey: key });
  }
}

registerVerb("pipeline-pause", () => {
  void ask("/api/pipeline/pause");
});

registerVerb("pipeline-resume", () => {
  void ask("/api/pipeline/resume");
});

// THE VALUE SAYS WHICH WAY, and the control carries it: a verb that read the
// current state and flipped it would be deciding from a copy of the truth it is
// about to change. The markup says what the press MEANS; the server says what
// is true afterwards.
registerVerb("watcher", (value) => {
  void ask("/api/pipeline/watcher", { enabled: value === ON });
});

// THE BOUND IS A PATH, NOT A CONTROL (the operator's ruling): a setting is
// edited where settings are edited. The value it carries is the setting's own
// identity — its file and its key — which is what the addressed panel resolves.
registerVerb("bound", (identity) => {
  panel.produce("setting", identity);
});

export { HELD };
