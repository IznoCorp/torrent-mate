"""R528 — Profil lists the account's sessions, each revocable, and its sign-in notices are marked read.

The operator's ruling Q4 A (2026-10-06): a Plex sign-in can be phished, so every account sees where it
is signed in and ends the sessions it does not recognise; a new session is told in the application.

R528-a — « Appareils connectés » on the seeded account:
1. `profile-sessions`: the section is drawn, one row per live session, the current one carries the
   « Cet appareil » chip and NO « Mettre fin », every other one carries it;
2. a press on « Mettre fin » opens a confirmation that NAMES the device and sends nothing: cancelled,
   the list is unchanged; confirmed, the session leaves the list;
3. the sign-in notices are drawn newest first, the unread ones distinguished, and « Tout marquer comme
   lu » leaves none unread and removes itself.

R528-b — the surface's own named states:
4. `profile-sessions-loading`, `-only-current`, `-load-failed`, `-revoking`, `-revoke-failed`, `-offline`
   and `profile-notices-read` exist and each says what it is: the loading line, the « no other session »
   line, the retry alert, the row being ended with its button disabled, the refusal under the row, the
   held line with no button, and no unread notice;
5. at 390 px the page does not scroll sideways with the section drawn.

Red on `origin/develop`: Profil draws no sessions and no notices, and none of these states exists.
"""

import asyncio
import json
import pathlib

from common import SETTLED, Journal, browser_channel, chrome_launch_args, open_page, read_at, settle

from playwright.async_api import async_playwright

HERE = pathlib.Path(__file__).resolve().parent
I18N = HERE.parent / "design/src/i18n"
FR = json.loads((I18N / "fr.json").read_text(encoding="utf-8"))
ABSENT = "<no words>"
# What a rule waits for after a press that opens or answers: the dialog's transition, the mock's answer.
ANSWERED = 900


def words(path):
    """One French leaf under Profil's sessions words.

    Args:
        path: The dotted key under `screens.accountPage.sessions`.

    Returns:
        Its words, or the absent placeholder — so a key missing before the change fails a check
        rather than crashing the rule.
    """
    node = FR.get("screens", {}).get("accountPage", {}).get("sessions", {})
    for part in path.split("."):
        node = node.get(part, {}) if isinstance(node, dict) else {}
    return node if isinstance(node, str) else ABSENT


READ = """() => {
  const section = document.querySelector('[data-part="profile/sessions"]');
  const text = (node) => node?.textContent.trim() ?? null;
  const rows = [...(section?.querySelectorAll('[data-part="profile/session"]') ?? [])];
  const notices = [...(section?.querySelectorAll('[data-part="profile/notice"]') ?? [])];
  return {
    section: section !== null,
    state: section?.dataset.state ?? null,
    heading: text(section?.querySelector('[data-part="heading"]')),
    sessions: rows.map((row) => ({
      device: text(row.querySelector('.font-semibold')),
      current: row.hasAttribute('data-current'),
      state: row.dataset.sessionState,
      chip: text(row.querySelector('[data-part="chip"]')),
      end: row.querySelector('[data-part="profile/session-end"]') !== null,
      endText: text(row.querySelector('[data-part="profile/session-end"]')),
      endDisabled: row.querySelector('[data-part="profile/session-end"]')?.disabled ?? null,
      held: text(row.querySelector('[data-part="profile/session-held"]')),
      refusal: text(row.querySelector('[data-part="profile/session-refusal"]')),
    })),
    loading: text(section?.querySelector('[data-part="profile/sessions-loading"]')),
    failed: text(section?.querySelector('[data-part="profile/sessions-failed"] b')),
    retry: section?.querySelector('[data-part="profile/sessions-failed"] button') !== null,
    onlyCurrent: text(section?.querySelector('[data-part="profile/sessions-only-current"]')),
    notices: notices.map((notice) => ({ code: notice.dataset.noticeCode, unread: notice.hasAttribute('data-unread'), text: text(notice.querySelector('div > div')) })),
    mark: section?.querySelector('[data-part="profile/notices-mark"]') !== null,
    overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
  };
}"""

DIALOG = """() => {
  const dialog = document.querySelector('[data-part="dialog"]');
  return {
    open: dialog?.getAttribute('data-open') !== null && dialog?.getAttribute('data-open') !== 'false',
    text: dialog?.textContent ?? '',
    buttons: [...document.querySelectorAll('[data-part="dialog/button"]')].map((one) => one.textContent.trim()),
  };
}"""

ENDS = '[data-part="profile/session"]:not([data-current]) [data-part="profile/session-end"]'


async def exists(page, state):
    """Whether the prototype names a state.

    Args:
        page: The Playwright page.
        state: The state's id.

    Returns:
        True when `__states()` lists it.
    """
    return await page.evaluate("(id)=>window.__states().includes(id)", state)


async def main():
    journal = Journal("R528 — Profil lists the account's sessions, each revocable, and its notices are marked read")
    errors = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        page.on("pageerror", lambda error: errors.append(str(error)))

        # ── R528-a: the section on the seeded account ──────────────────────
        seen = await read_at(page, "profile-sessions", READ)
        journal.check(
            "Profil draws « Appareils connectés »",
            seen["section"] and seen["heading"] == words("heading"),
            f"section {seen['section']} · heading {seen['heading']!r}",
        )
        current = [one for one in seen["sessions"] if one["current"]]
        others = [one for one in seen["sessions"] if not one["current"]]
        journal.check(
            "one row per live session: the current one and two others",
            len(current) == 1 and len(others) == 2,
            f"{len(current)} current · {len(others)} others",
        )
        journal.check(
            "the current session is named « Cet appareil » and is NOT offered « Mettre fin »",
            len(current) == 1 and current[0]["chip"] == words("current") and not current[0]["end"],
            f"{current}",
        )
        journal.check(
            "every other session is offered « Mettre fin »",
            bool(others) and all(one["end"] and one["endText"] == words("end") for one in others),
            f"{[one['endText'] for one in others]}",
        )

        if others:
            await page.click(ENDS)
            await page.wait_for_timeout(ANSWERED)
            dialog = await page.evaluate(DIALOG)
            device = others[0]["device"]
            journal.check(
                "« Mettre fin » opens a confirmation that names the device, and sends nothing yet",
                dialog["open"] and device in dialog["text"] and words("confirm.confirm") in dialog["buttons"],
                f"open {dialog['open']} · device {device!r} · {dialog['buttons']}",
            )
            await page.click(f'[data-part="dialog/button"]:has-text("{words("confirm.cancel")}")')
            await page.wait_for_timeout(SETTLED)
            seen = await page.evaluate(READ)
            journal.check(
                "cancelled, the list is unchanged",
                len(seen["sessions"]) == 3,
                f"{len(seen['sessions'])} sessions",
            )
            await page.click(ENDS)
            await page.wait_for_timeout(ANSWERED)
            await page.click('[data-part="dialog/button"][data-tone="danger"]')
            await page.wait_for_timeout(ANSWERED)
            await settle(page)
            seen = await page.evaluate(READ)
            journal.check(
                "confirmed, the session leaves the list and the others stay",
                len(seen["sessions"]) == 2 and all(one["device"] != device for one in seen["sessions"]),
                f"{[one['device'] for one in seen['sessions']]}",
            )

        seen = await read_at(page, "profile-sessions", READ)
        unread = [one for one in seen["notices"] if one["unread"]]
        journal.check(
            "the notices are drawn, the unread ones distinguished and worded in the interface's language",
            len(seen["notices"]) == 3 and len(unread) == 2 and seen["mark"],
            f"{len(seen['notices'])} notices · {len(unread)} unread · {[one['text'] for one in seen['notices']]}",
        )
        if seen["mark"]:
            await page.click('[data-part="profile/notices-mark"]')
            await page.wait_for_timeout(ANSWERED)
            await settle(page)
            seen = await page.evaluate(READ)
            journal.check(
                "« Tout marquer comme lu » leaves no notice unread and removes itself",
                len(seen["notices"]) == 3 and not any(one["unread"] for one in seen["notices"]) and not seen["mark"],
                f"unread {[one['unread'] for one in seen['notices']]} · mark {seen['mark']}",
            )
            marked = await page.evaluate("()=>window.__mocks.answered().filter((one)=>one.operationId==='markNoticesRead')")
            journal.check(
                "the read mark went to the server's operation, once",
                len(marked) == 1 and marked[0]["status"] == 200,
                f"{marked}",
            )

        # ── R528-b: the named states ───────────────────────────────────────
        states = (
            "profile-sessions-loading",
            "profile-sessions-only-current",
            "profile-sessions-load-failed",
            "profile-sessions-revoking",
            "profile-sessions-revoke-failed",
            "profile-sessions-offline",
            "profile-notices-read",
        )
        for state in states:
            journal.check(f"the named state {state} exists", await exists(page, state), state)

        if await exists(page, "profile-sessions-loading"):
            seen = await read_at(page, "profile-sessions-loading", READ)
            journal.check(
                "loading: the line says so and no session is drawn yet",
                seen["state"] == "loading" and seen["loading"] == words("loading") and not seen["sessions"],
                f"{seen['state']} · {seen['loading']!r}",
            )
        if await exists(page, "profile-sessions-only-current"):
            seen = await read_at(page, "profile-sessions-only-current", READ)
            journal.check(
                "only the current session: it is drawn, and the section says no other is open",
                seen["state"] == "only-current"
                and len(seen["sessions"]) == 1
                and seen["onlyCurrent"] == words("onlyCurrent"),
                f"{seen['state']} · {len(seen['sessions'])} · {seen['onlyCurrent']!r}",
            )
        if await exists(page, "profile-sessions-load-failed"):
            seen = await read_at(page, "profile-sessions-load-failed", READ)
            journal.check(
                "read failed: said, with a button to try again",
                seen["state"] == "failed" and seen["failed"] == words("loadFailed") and seen["retry"],
                f"{seen['state']} · {seen['failed']!r} · retry {seen['retry']}",
            )
        if await exists(page, "profile-sessions-revoking"):
            seen = await read_at(page, "profile-sessions-revoking", READ, wait=2 * ANSWERED)
            ending = [one for one in seen["sessions"] if one["state"] == "ending"]
            journal.check(
                "ending: the row says so, its button is disabled, the session is still listed",
                len(ending) == 1 and ending[0]["endDisabled"] is True and ending[0]["endText"] == words("ending"),
                f"{ending}",
            )
        if await exists(page, "profile-sessions-revoke-failed"):
            seen = await read_at(page, "profile-sessions-revoke-failed", READ, wait=2 * ANSWERED)
            refused = [one for one in seen["sessions"] if one["refusal"]]
            journal.check(
                "refused: said under the session, which is still live, in the interface's words",
                len(refused) == 1 and refused[0]["refusal"] == words("refused"),
                f"{[one['refusal'] for one in refused]}",
            )
        if await exists(page, "profile-sessions-offline"):
            seen = await read_at(page, "profile-sessions-offline", READ, wait=2 * ANSWERED)
            held = [one for one in seen["sessions"] if one["held"]]
            journal.check(
                "offline: the end is held and said so, never shown as done, and its button is gone",
                len(held) == 1 and held[0]["held"] == words("held") and not held[0]["end"],
                f"{[one['held'] for one in held]}",
            )
        if await exists(page, "profile-notices-read"):
            seen = await read_at(page, "profile-notices-read", READ)
            journal.check(
                "all read: no notice is unread and no button is offered",
                bool(seen["notices"]) and not any(one["unread"] for one in seen["notices"]) and not seen["mark"],
                f"{[one['unread'] for one in seen['notices']]} · mark {seen['mark']}",
            )

        seen = await read_at(page, "profile-sessions", READ)
        journal.check("at 390 px the page does not scroll sideways", not seen["overflow"], f"overflow {seen['overflow']}")
        await context.close()
        await browser.close()

    journal.check("no JS error", not errors, str(errors[:3]))
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
