"""The design host's v1 door: a request is admitted when v1 accepts its session.

The real v1 sign-in is tm-design's only door (the operator, 2026-10-04; round 2
Q1 = A), and the application's code never reaches a visitor v1 has not signed
in. This host keeps its two-step shape — a public sign-in page, then the
document — but the second step asks v1 itself, with the request's own session,
rather than checking a password of its own.

THE COOKIE REACHES THIS HOST because v1 sets it host-only with `Path=/`
(`personalscraper/http_v1/session_cookie.py`), and Caddy serves v1 and this host
under one origin. It is `SameSite=Strict`, so a navigation ARRIVING from another
site carries none: the sign-in page asks v1 once, by `fetch` — same-site, so the
cookie goes — and reloads when v1 answers that the session holds.

THE PAGE SAYS WHY THE SESSION ENDED (the operator, 2026-10-04): v1's refusal
carries a closed code — `auth.required` for a session that is gone, `auth.access_disabled`
for an account an Admin cut — and the page words it from the interface's resource.
It also RETURNS WHERE THE VISITOR WAS GOING, to the address that was asked and not
to `/`; only a same-origin path is honoured (`safe_return_path`).
"""

from __future__ import annotations

import hashlib
import html
import http.cookies
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

# Where v1 answers, from this host — the loopback, behind the reverse proxy.
V1_URL = os.environ.get("TM_DESIGN_V1_URL", "http://127.0.0.1:8713").rstrip("/")
# v1's session cookie (`personalscraper/http_v1/session_cookie.py`).
V1_COOKIE = "tm_v1_session"
# How long a session v1 accepted is taken as still accepted: one page load asks
# for the document and its bundles at once, and asking v1 for each would be a
# round trip per file. A few seconds only, and positive only: a session ended is
# refused at most this long after, and a refusal is never remembered.
ADMITTED_FOR = 5.0
# How long v1 may take to answer before the host says it does not.
V1_TIMEOUT = 5.0
# The statuses by which v1 says the session is not one.
REFUSED = frozenset({401, 403})

# The refusal codes the sign-in page says in words, and where each one's words
# live in the interface's resource (`server.login.<key>`). Any other code — an
# unknown e-mail, a wrong password — is said nowhere here: it tells nothing.
REASONS = {
    "auth.required": "reasonExpired",
    "auth.access_disabled": "reasonDisabled",
}
# The query parameters the sign-in page itself writes. They are never part of
# the place a visitor was going.
OWN_PARAMS = frozenset({"refus", "why", "next"})
# The longest address the page will return to: a browser's own limits are far
# above any address the application draws.
MAX_RETURN = 2048

# Sessions v1 accepted, by a digest of their value, until when. The value
# itself is never kept.
_admitted: dict[str, float] = {}
_admitted_lock = threading.Lock()


class V1Unreachable(RuntimeError):
    """v1 did not answer whether a session holds — never read as a refusal."""


def session_of(cookie_header: str | None) -> str | None:
    """The v1 session value a request's `Cookie` header carries.

    Args:
        cookie_header: The raw header, if any.

    Returns:
        The `tm_v1_session` value, or None when absent, empty or unreadable.
    """
    if not cookie_header:
        return None
    cookies = http.cookies.SimpleCookie()
    try:
        cookies.load(cookie_header)
    except http.cookies.CookieError:
        return None
    found = cookies.get(V1_COOKIE)
    return found.value if found is not None and found.value else None


def ask_v1(token: str) -> tuple[int, str | None]:
    """Asks v1 whether a session holds, and why not when it does not.

    Args:
        token: The `tm_v1_session` value.

    Returns:
        v1's status for `/api/v1/auth/me`, and the refusal `code` its body
        carries when it refused (None otherwise, or when the body is no problem).

    Raises:
        V1Unreachable: When v1 does not answer.
    """
    # Only v1's own cookie is forwarded: the host's other cookies are not v1's.
    request = urllib.request.Request(
        f"{V1_URL}/api/v1/auth/me", headers={"Cookie": f"{V1_COOKIE}={token}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=V1_TIMEOUT) as answer:  # noqa: S310 — a configured loopback URL
            return answer.status, None
    except urllib.error.HTTPError as refusal:
        return refusal.code, _code_of(refusal)
    except (urllib.error.URLError, OSError) as down:
        raise V1Unreachable(f"v1 at {V1_URL} did not answer: {down}") from down


def _code_of(refusal: urllib.error.HTTPError) -> str | None:
    """The `code` of a refusal's problem body, or None when it carries none."""
    try:
        body = json.loads(refusal.read(4096))
    except (OSError, ValueError):
        return None
    code = body.get("code") if isinstance(body, dict) else None
    return code if isinstance(code, str) else None


def check_session(cookie_header: str | None) -> tuple[bool, str | None]:
    """Whether v1 accepts the session a request carries, and why not when it does not.

    One question to v1 answers both: the door's verdict and the sign-in page's
    reason.

    Args:
        cookie_header: The request's raw `Cookie` header.

    Returns:
        Whether the session holds (or did, a moment ago), and the refusal code
        v1 gave when it refused — None for no session at all, a session held,
        or a refusal with no code.

    Raises:
        V1Unreachable: When v1 does not answer, or answers neither — a door
            that read an outage as a refusal would send a signed-in person back
            to a sign-in that cannot work, and say nothing about why.
    """
    token = session_of(cookie_header)
    if token is None:
        return False, None
    digest = hashlib.sha256(token.encode()).hexdigest()
    now = time.monotonic()
    with _admitted_lock:
        if _admitted.get(digest, 0.0) > now:
            return True, None
    status, code = ask_v1(token)
    if status in REFUSED:
        return False, code
    if status != 200:
        raise V1Unreachable(f"v1 at {V1_URL} answered {status} to /api/v1/auth/me")
    with _admitted_lock:
        _admitted[digest] = now + ADMITTED_FOR
    return True, None


def admitted(cookie_header: str | None) -> bool:
    """Whether v1 accepts the session a request carries.

    Args:
        cookie_header: The request's raw `Cookie` header.

    Returns:
        True when v1's `/api/v1/auth/me` answers 200 for the session (or did, a
        moment ago); False when there is none, or v1 refuses it.

    Raises:
        V1Unreachable: When v1 does not answer — see `check_session`.
    """
    return check_session(cookie_header)[0]


def refusal_reason(code: str | None, why: str | None) -> str | None:
    """Why the sign-in page is being shown, as the key of its words.

    A session v1 refused says why by v1's own code; a sign-in v1 just refused
    comes back with that code as `why`. A plain first visit — no session, no
    code — has no reason, and says none.

    Args:
        code: The refusal code `check_session` returned.
        why: The `why` query parameter the page wrote after a refused sign-in.

    Returns:
        A key under `server.login` — only for a code in `REASONS`, so nothing
        else is ever echoed — or None.
    """
    return REASONS.get(code or "") or REASONS.get(why or "")


def safe_return_path(asked: str | None) -> str:
    """The place the page may send a visitor to once v1 opens the session.

    NO OPEN REDIRECT: only a same-origin path — one `/`, then anything — is
    honoured. `//host` and a backslash after the slash are read by a browser as another origin,
    a scheme or a bare host is no path at all, and a control character is a
    header injection waiting for a proxy. Whatever is not a plain path is `/`.

    Args:
        asked: The address as asked: a path and its query, or anything a
            visitor wrote into `next`.

    Returns:
        `asked` when it is a same-origin path, `/` otherwise.
    """
    if (
        not asked
        or len(asked) > MAX_RETURN
        or not asked.startswith("/")
        or asked.startswith("//")
        or "\\" in asked
        or any(ord(char) <= 0x20 or ord(char) == 0x7F for char in asked)
    ):
        return "/"
    return asked


def return_target(request_path: str) -> str:
    """The place to return to, from the address the sign-in page was asked at.

    Args:
        request_path: The request's raw path and query.

    Returns:
        The `next` the page wrote after a refusal when there is one, else the
        address itself minus the page's own parameters — both through
        `safe_return_path`.
    """
    parts = urllib.parse.urlsplit(request_path)
    params = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    for name, value in params:
        if name == "next":
            return safe_return_path(value)
    kept = urllib.parse.urlencode([(name, value) for name, value in params if name not in OWN_PARAMS])
    return safe_return_path(parts.path + (f"?{kept}" if kept else ""))


# The sign-in page's v1 half: the form posts the e-mail and the password to v1
# as declared JSON, and lands on the place that was asked once v1 opens the
# session — or back on the sign-in page, that place kept, when it does not.
# First, the session already held is asked about once (the SameSite note
# above), at most once in ten seconds so a page whose reload still carries no
# cookie cannot loop.
V1_SIGN_IN = """
<script>
(function () {
  var RETURN_TO = __RETURN_TO__;
  var REASONS = __REASONS__;
  var form = document.querySelector('#loginform');
  var asked = 0;
  function refused(code) {
    var why = REASONS.indexOf(code) < 0 ? '' : '&why=' + code;
    return '/?refus=1' + why + '&next=' + encodeURIComponent(RETURN_TO);
  }
  try { asked = Number(sessionStorage.getItem('tm-design-v1-asked') || 0); } catch (e) {}
  if (Date.now() - asked > 10000) {
    try { sessionStorage.setItem('tm-design-v1-asked', String(Date.now())); } catch (e) {}
    fetch('/api/v1/auth/me', { credentials: 'same-origin' })
      .then(function (answer) { if (answer.ok) location.replace(RETURN_TO); })
      .catch(function () {});
  }
  form.addEventListener('submit', function (event) {
    event.preventDefault();
    if (!form.checkValidity()) return;
    fetch('/api/v1/auth/login', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: form.username.value.trim(), password: form.password.value })
    }).then(function (answer) {
      if (answer.ok) {
        // The application boots from scratch after this page: the mark is how its first boot
        // knows a person has just signed in, and proposes the install (`app/install-state.ts`).
        try { sessionStorage.setItem('tm-signed-in', '1'); } catch (e) {}
        return location.replace(RETURN_TO);
      }
      return answer.json().catch(function () { return {}; })
        .then(function (problem) { location.replace(refused(problem && problem.code)); });
    }).catch(function () { location.replace(refused()); });
  });
})();
</script>
"""


def _as_js(value: object) -> str:
    """A JSON value safe inside an inline script: no `</script>`, no line terminators."""
    return (
        json.dumps(value)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def sign_in_script(return_to: str) -> str:
    """The sign-in page's script, built for the place it returns to.

    Args:
        return_to: Where the visitor was going; passed through `safe_return_path`
            again, since this is the one place it becomes script.

    Returns:
        The `<script>` element.
    """
    return V1_SIGN_IN.replace("__RETURN_TO__", _as_js(safe_return_path(return_to))).replace(
        "__REASONS__", _as_js(sorted(REASONS))
    )


def with_reason(markup: str, reason: str) -> str:
    """Says why the session ended, under the sign-in form's subtitle.

    Args:
        markup: The sign-in screen, as extracted from the shell document.
        reason: The sentence, already the interface's own.

    Returns:
        The markup with a `login/reason` line after the subtitle.

    Raises:
        ValueError: When the subtitle is not where the shell puts it — a page
            that dropped the reason would send a person back to a form that
            says nothing about why they are there.
    """
    line = f'<p class="loginerr" data-part="login/reason" role="status">{html.escape(reason)}</p>'
    said, found = re.subn(r'(<p class="loginsub">[^<]*</p>)', lambda match: match.group(1) + line, markup, count=1)
    if found != 1:
        raise ValueError("the sign-in form carries no subtitle to say the reason under")
    return said


def as_v1_form(markup: str, email_label: str) -> str:
    """Turns the extracted sign-in form into v1's: an e-mail, posted by script.

    Args:
        markup: The sign-in screen, as extracted from the shell document.
        email_label: The identifier's label, from the interface's resource.

    Returns:
        The markup with its identifier asked as an e-mail. The field keeps its
        name `username` — the region is the shell's, and the name is what a
        password manager files the e-mail under.

    Raises:
        ValueError: When the identifier field is not where the shell puts it —
            a page left asking for a user name would refuse every e-mail.
    """
    labelled, found = re.subn(
        r'(<label\b[^>]*>\s*<span>)[^<]*(</span>\s*<input\b[^>]*?)type="text"',
        lambda match: f'{match.group(1)}{email_label}{match.group(2)}type="email"',
        markup,
        count=1,
    )
    if found != 1:
        raise ValueError("the sign-in form carries no text identifier field to ask as an e-mail")
    return labelled


def email_label(resource: str) -> str:
    """The identifier's label when it is an e-mail, read from the interface's resource.

    Args:
        resource: The text of `design/src/i18n/fr.json`.

    Returns:
        `screens.gate.email`.

    Raises:
        KeyError: When the resource does not hold it.
    """
    return str(json.loads(resource)["screens"]["gate"]["email"])


def unreachable_page(error: str, texts: dict[str, str]) -> bytes:
    """Returns the 503 served when the v1 door cannot ask v1.

    A visitor signing in meets it, so its words are the interface's
    (`server.v1Unreachable`); what v1 did, or did not, answer follows for
    whoever looks into it.

    Args:
        error: What v1 did, or did not, answer.
        texts: The `server.v1Unreachable` words: `title`, `heading`, `body`.

    Returns:
        A complete HTML document that names the server that did not answer,
        never the sign-in.
    """
    return (
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,interactive-widget=resizes-content">'
        f"<title>{html.escape(texts['title'], quote=False)}</title></head><body "
        'style="font:16px system-ui;max-width:44em;margin:12vh auto;padding:0 1.5em">'
        f"<h1>{html.escape(texts['heading'], quote=False)}</h1><p>{html.escape(texts['body'], quote=False)}"
        "</p><pre style=\"white-space:pre-wrap;background:#f6f6f6;"
        'padding:12px;border-radius:8px">'
        f"{html.escape(error)}"
        "</pre></body></html>"
    ).encode()
