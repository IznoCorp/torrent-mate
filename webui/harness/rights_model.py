"""R420 — one derivation of what an account may do, and its refusal side everywhere (§ 17).

DESIGN maquette-l18 § 1.2, § 2.2, § 5 (R-L18-a, R-L18-b, R-L18-c).

1. R-L18-a — THE RESTING MAQUETTE IS THE OWNER'S: with no dial turned, `readAccount`
   answers the owner on the Admin role, no forbidden write, and every follow and queue
   card names him alone as its requester — no invented account is readable at rest.
2. R-L18-b — NO SURFACE COMPARES A ROLE: outside the model (`lib/rights.ts`)
   no product source compares a role's kind, name or id. The source is read, never a
   rendering, because a comparison that happens to agree with the model today draws
   exactly the same screen.
3. R-L18-c — THE REFUSAL SIDE, READS AND WRITES: signed in as each invented account,
   every operation is forced by hand. An account whose role opens the library alone gets 403 from every
   write but the session's own acts; a household member gets 403 from every read of
   Système, Maintenance, the pipeline, Trackers and the configuration's own files (F30);
   the owner gets 403 from nothing. `acquisition.see.others` is a filter, never a 403: the
   acquisition lists answer 200 to everyone.

WHAT IT DOES NOT READ: which surface offers an act (the offer side is each surface's own
rule); the backend, which enforces nothing yet.
"""
import asyncio
import json
import pathlib
import re

from common import SETTLED, Journal, open_page, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
SEEDS = json.loads((SOURCE / "mocks/seeds/accounts.json").read_text(encoding="utf-8"))
OWNER = json.loads((SOURCE / "mocks/seeds/account.json").read_text(encoding="utf-8"))["id"]
# THE SESSION'S OWN ACTS, no right: signing in and out, and an account's own notification
# settings (the operator, 2026-10-03: « tout le monde à le droit de changer les notifications de
# son propre compte »).
SESSION = {
    "POST /auth/login", "POST /auth/logout", "POST /auth/plex", "POST /auth/plex/start", "PUT /auth/password",
    "PUT /notifications/preferences/{type}", "POST /notifications/devices",
    "POST /acquisition/journeys/{infoHash}/closure/seen",
    # The account's own language carries no right (the operator, 2026-10-03: FG-1 B).
    "PUT /auth/language",
}
# The reads F30 gates: Système, Maintenance, the pipeline's record, Trackers, the
# configuration's own files and secrets.
GATED_READ = re.compile(r"^GET /(system|maintenance|pipeline|trackers|acquisition/(downloads|obligations)"
                        r"|config/(secrets|files))")
ACQUISITION_LISTS = ("GET /acquisition/followed", "GET /acquisition/to-handle")
MODEL = "lib/rights.ts"
ROLE_COMPARED = re.compile(r"(\brole\??\.(kind|name|id)|\broleName)\s*[!=]==|[!=]==\s*[\"'](admin|default)[\"']")

FORCE = """async (identity) => {
  window.__go('profile');
  window.__mocks.setIdentity(identity);
  const out = {};
  for (const line of window.__mocks.routes()) {
    const [method, template] = line.split(' ');
    const path = template.replace(/\\{[^}]+\\}/g, 'x');
    // A handler handed an empty body may throw once past the guard: that is
    // not a refusal, and it is not this rule's question.
    try {
      // The routes are the contract's paths, relative to its server URL.
      const answer = await fetch('/api/v1' + path, method === 'GET' ? {} : { method, body: '{}' });
      out[line] = answer.status;
    } catch (error) {
      out[line] = 'threw';
    }
  }
  return out;
}"""

# THE OWN PASSWORD, forced once more for its CODE: an account's kind refuses it, never a right.
OWN_PASSWORD = "PUT /auth/password"
OWN_PASSWORD_CODE = """async (identity) => {
  window.__mocks.setIdentity(identity);
  const answer = await fetch('/api/v1/auth/password', { method: 'PUT', body: '{}' });
  return [answer.status, (await answer.json()).code ?? null];
}"""

REST = """async () => {
  window.__go('profile');
  const account = await (await fetch('/api/v1/auth/me')).json();
  const follows = await (await fetch('/api/v1/acquisition/followed')).json();
  const queue = await (await fetch('/api/v1/acquisition/to-handle')).json();
  const cards = [...follows, ...Object.values(queue).flat()];
  return { account, requesters: cards.map((card) => (card.requesters || []).map((one) => one.id).join(',')) };
}"""


def product_sources():
    """Every product source under `design/src`, the model and the harness-only trees aside."""
    for path in sorted(SOURCE.rglob("*.ts*")):
        relative = path.relative_to(SOURCE).as_posix()
        if relative == MODEL or relative.startswith(("mocks/", "harness/", "contract/")) or ".test." in relative:
            continue
        yield relative, path.read_text(encoding="utf-8")


async def main():
    journal = Journal("R420 — one derivation of what an account may do, refused everywhere else")

    compared = [f"{name}:{number}" for name, text in product_sources()
                for number, line in enumerate(text.splitlines(), 1) if ROLE_COMPARED.search(line)]
    journal.check("R-L18-b: no product source compares a role — the model alone reads it", not compared,
                  ", ".join(compared) or "none")

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        rest = await page.evaluate(REST)
        account = rest["account"]
        journal.check("R-L18-a: at rest the owner is signed in, on the Admin role",
                      account.get("id") == OWNER and account.get("role", {}).get("kind") == "admin",
                      f"{account.get('id')} / {account.get('role')}")
        journal.check("R-L18-a: at rest the instance forbids no write", account.get("forbiddenWrites") == [],
                      str(account.get("forbiddenWrites")))
        strangers = [one for one in rest["requesters"] if one != OWNER]
        journal.check("R-L18-a: at rest every acquisition names the owner alone as its requester",
                      rest["requesters"] and not strangers, f"{len(rest['requesters'])} cards, others {strangers[:3]}")

        by_role = {one["id"]: one["role"] for one in SEEDS["accounts"]}
        # THE LIBRARY ALONE (O-K1-4: Invité Plex) — what the Default role was.
        default_account = next(one for one, role in by_role.items() if role == "plex-guest")
        household = next(one for one, role in by_role.items() if role == "household")

        owner = await page.evaluate(FORCE, OWNER)
        # THE OWNER'S FALLBACK PASSWORD IS REFUSED BY HIS KIND (replaced on the server only, the
        # operator, 2026-10-03), not by a right: its refusal is read by its code, below.
        refused = [k for k, v in owner.items() if v == 403 and k != OWN_PASSWORD]
        journal.check("R-L18-c: the owner is refused nothing", not refused,
                      f"{len(owner)} operations forced, refused {refused[:4]}")
        held = await page.evaluate(OWN_PASSWORD_CODE, OWNER)
        journal.check("R-L18-c: the owner's own password is refused by his kind, password.held_by_cli",
                      held == [403, "password.held_by_cli"], str(held))

        bare = await page.evaluate(FORCE, default_account)
        writes = [k for k in bare if not k.startswith("GET ") and k not in SESSION]
        through = [k for k in writes if bare[k] != 403]
        journal.check(f"R-L18-c: a library-only role ({default_account}) is refused every write", writes and not through,
                      f"{len(writes)} writes, answered {[(k, bare[k]) for k in through][:4]}")
        # A PLEX-LINKED ACCOUNT'S OWN PASSWORD IS REFUSED BY ITS KIND (it holds none), not
        # by a right: its refusal is read by its code, below.
        session = [k for k in SESSION if bare.get(k) == 403 and k != OWN_PASSWORD]
        journal.check("R-L18-c: signing in and out answer every identity", not session, str(session))
        plex_only = await page.evaluate(OWN_PASSWORD_CODE, default_account)
        journal.check(f"R-L18-c: a Plex-linked account's ({default_account}) own password is refused by its kind, auth.plex_only",
                      plex_only == [403, "auth.plex_only"], str(plex_only))

        member = await page.evaluate(FORCE, household)
        reads = [k for k in member if GATED_READ.match(k)]
        open_reads = [k for k in reads if member[k] != 403]
        journal.check(f"R-L18-c: a household member ({household}) is refused every gated read (F30)",
                      reads and not open_reads, f"{len(reads)} reads, answered {open_reads[:4]}")
        lists = {k: member.get(k) for k in ACQUISITION_LISTS}
        journal.check("R-L18-c: the acquisition lists answer 200 — seeing others' is a filter, never a 403",
                      all(status == 200 for status in lists.values()), str(lists))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
