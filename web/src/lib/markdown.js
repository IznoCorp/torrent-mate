// Safe markdown rendering. `marked` emits raw HTML verbatim (it does NOT sanitize), so any markdown
// that carries HTML — GitHub issue bodies/comments, agent-generated text, artifact files — could
// inject <script>/<img onerror=…> and run in the operator's authenticated session. Always route
// markdown → HTML through this helper, which sanitizes the output with DOMPurify before it reaches
// dangerouslySetInnerHTML.
import { marked } from "marked";
import DOMPurify from "dompurify";

/**
 * Parse markdown to SANITISED HTML, safe for dangerouslySetInnerHTML.
 *
 * @param {string} text - the markdown source (untrusted).
 * @param {object} [opts] - marked options (e.g. { breaks: true }).
 * @returns {string} sanitised HTML.
 */
export function renderMarkdown(text, opts = { breaks: true }) {
  return DOMPurify.sanitize(marked.parse(text || "", opts));
}
