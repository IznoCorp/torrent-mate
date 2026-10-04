"""The design host's v1 door: a request is admitted when v1 accepts its session.

With `TM_DESIGN_GATE=v1` (the operator, 2026-10-04; round 2 Q1 = A) the real v1
sign-in is tm-design's door, and the application's code never reaches a visitor
v1 has not signed in. This host keeps its two-step shape — a public sign-in
page, then the document — but the second step asks v1 itself, with the
request's own session, rather than checking a password of its own.

THE COOKIE REACHES THIS HOST because v1 sets it host-only with `Path=/`
(`personalscraper/http_v1/session_cookie.py`), and Caddy serves v1 and this host
under one origin. It is `SameSite=Strict`, so a navigation ARRIVING from another
site carries none: the sign-in page asks v1 once, by `fetch` — same-site, so the
cookie goes — and reloads when v1 answers that the session holds.
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


def admitted(cookie_header: str | None) -> bool:
    """Whether v1 accepts the session a request carries.

    Args:
        cookie_header: The request's raw `Cookie` header.

    Returns:
        True when v1's `/api/v1/auth/me` answers 200 for the session (or did, a
        moment ago); False when there is none, or v1 refuses it.

    Raises:
        V1Unreachable: When v1 does not answer, or answers neither — a door
            that read an outage as a refusal would send a signed-in person back
            to a sign-in that cannot work, and say nothing about why.
    """
    token = session_of(cookie_header)
    if token is None:
        return False
    digest = hashlib.sha256(token.encode()).hexdigest()
    now = time.monotonic()
    with _admitted_lock:
        if _admitted.get(digest, 0.0) > now:
            return True
    # Only v1's own cookie is forwarded: the host's other cookies are not v1's.
    request = urllib.request.Request(
        f"{V1_URL}/api/v1/auth/me", headers={"Cookie": f"{V1_COOKIE}={token}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=V1_TIMEOUT) as answer:  # noqa: S310 — a configured loopback URL
            status = answer.status
    except urllib.error.HTTPError as refusal:
        status = refusal.code
    except (urllib.error.URLError, OSError) as down:
        raise V1Unreachable(f"v1 at {V1_URL} did not answer: {down}") from down
    if status in REFUSED:
        return False
    if status != 200:
        raise V1Unreachable(f"v1 at {V1_URL} answered {status} to /api/v1/auth/me")
    with _admitted_lock:
        _admitted[digest] = now + ADMITTED_FOR
    return True


# The sign-in page's v1 half: the form posts the e-mail and the password to v1
# as declared JSON, and lands on the document once v1 opens the session — or on
# the refusal state when it does not. First, the session already held is asked
# about once (the SameSite note above), at most once in ten seconds so a page
# whose reload still carries no cookie cannot loop.
V1_SIGN_IN = """
<script>
(function () {
  var form = document.querySelector('#loginform');
  var asked = 0;
  try { asked = Number(sessionStorage.getItem('tm-design-v1-asked') || 0); } catch (e) {}
  if (Date.now() - asked > 10000) {
    try { sessionStorage.setItem('tm-design-v1-asked', String(Date.now())); } catch (e) {}
    fetch('/api/v1/auth/me', { credentials: 'same-origin' })
      .then(function (answer) { if (answer.ok) location.replace(location.pathname + location.search); })
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
      location.replace(answer.ok ? '/' : '/?refus=1');
    }).catch(function () { location.replace('/?refus=1'); });
  });
})();
</script>
"""


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


def unreachable_page(error: str) -> bytes:
    """Returns the 503 served when the v1 door cannot ask v1.

    Args:
        error: What v1 did, or did not, answer.

    Returns:
        A complete HTML document, in English like the host's other diagnostic:
        it names the server that did not answer, never the sign-in.
    """
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,interactive-widget=resizes-content">'
        "<title>Design host: v1 unreachable</title></head><body "
        'style="font:16px system-ui;max-width:44em;margin:12vh auto;padding:0 1.5em">'
        "<h1>The design host cannot ask v1 who is signed in</h1><p>Its door is the "
        "v1 session (<code>TM_DESIGN_GATE=v1</code>), and v1 did not answer whether "
        "this one holds.</p><pre style=\"white-space:pre-wrap;background:#f6f6f6;"
        'padding:12px;border-radius:8px">'
        f"{html.escape(error)}"
        "</pre></body></html>"
    ).encode()
