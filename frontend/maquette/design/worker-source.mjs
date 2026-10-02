// The served `sw.js` from its source (fcm-push DESIGN § 3.5): the build's four
// values written over the four placeholders, and a refusal when one survives.
// Pure — no file is read here — so the suite proves the refusal the build relies
// on; `vite.config.mjs` reads the files and calls it.

export const PLACEHOLDERS = ["__BUILD__", "__SHELL__", "__EXTRAS__", "__PUSH_TEXTS__"];

// The `push` namespace of `fr.json`: a push is worded on the device from the
// same catalogue as every other string. Its GENERIC line is required — the worker
// shows it for any code it cannot word, and a worker with nothing to show would
// break iOS's rule that every push shows a notification.
export function pushTexts(catalogue) {
  const push = catalogue?.push;
  if (!push || typeof push.generic?.title !== "string" || typeof push.generic?.body !== "string") {
    throw new Error("build-worker: fr.json holds no push.generic title and body");
  }
  return push;
}

// Each value is written through a replacer FUNCTION: a replacement STRING reads `$&`,
// `$'`, `` $` `` and `$$` as patterns, and a push text of `fr.json` may hold them.
export function substituteWorker(source, { build, shell, extras, push }) {
  const worker = source
    .replace("__BUILD__", () => build)
    .replace("__SHELL__", () => JSON.stringify(shell))
    .replace("__EXTRAS__", () => JSON.stringify(extras))
    .replace("__PUSH_TEXTS__", () => JSON.stringify(push));
  if (PLACEHOLDERS.some((placeholder) => worker.includes(placeholder))) {
    throw new Error("build-worker: a placeholder survived substitution");
  }
  return worker;
}
