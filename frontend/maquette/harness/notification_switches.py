"""R521 — Profil carries « Notifications »: this device's line, then one switch per type the account may receive.

The operator, 2026-10-03: « il faudra une gestion des canaux, des canaux de notification, de façon à
pouvoir couper les notifications FCM de certains types tout en gardant les autres. Donc il faut créer
des types de notifications FCM. » His rulings the same day: the switches belong to the ACCOUNT, on
all its devices, the server filtering before it sends (Q1 A), and the section lives in Profil, under
the device's line, for every account that receives pushes, its types filtered by rights (Q2 A).

R521-a — the device's line, one per support of this device:
1. `profile-notifications` — push granted here: the section's FIRST row is the device's line,
   `data-support` « granted », its words those of `fr.json`;
2. `profile-notifications-unasked`, `-denied`, `-needs-install`, `-unsupported` — each its own
   `data-support` and its own words, and the switches still drawn: a choice is the account's and
   holds on its other devices;
3. the action « activer » is offered where, and only where, this device can still be asked
   (`unasked`); pressed, the permission granted, the token is registered (`registerPushDevice`)
   and the line says « granted ».

R521-b — the switches, the account's:
4. one switch per type the read answers, each named by its `data-notification-type` from the
   contract's `NotificationType`, its label the type's label, all on in the seeded layer;
5. the types drawn are exactly those whose right (`x-rights` on `NotificationType`) the account
   holds — every type for the Admin, a subset for a household member;
6. a switch pressed turns that type off, the others staying on, and a fresh read keeps it off
   (the server holds the choice, never the device);
7. an account that may receive no type (`profile-notifications-none`) is shown no section.

R521-c — the writes ask `notifications.manage`, and the interface says so:
8. under the read-only instance's ceiling (`profile-notifications-ceiling`, on a device that
   could still be asked), the switches are drawn with their state but none can be pressed, and
   « activer » is absent — the ceiling's notice, said once on the page, is the reason;
9. a write the server refuses is SAID refused, in a message naming the type, and the switch
   returns to what the server holds — never a silent snap back.

Red before R521-c: the switches were pressable and « activer » offered under the ceiling, and a
refused write rolled back with no word. Red before the change: none of the named states exists, Profil has no « Notifications » section,
and the contract declares neither the read nor the write.
"""
import asyncio
import json
import pathlib

from common import SETTLED, Journal, browser_channel, chrome_launch_args, open_page, read_at
from playwright.async_api import async_playwright

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE.parent / "design/src"
CONTRACT = json.loads((HERE.parent / "contract/openapi.json").read_text(encoding="utf-8"))
TYPE_SCHEMA = CONTRACT["components"]["schemas"].get("NotificationType", {})
TYPES = TYPE_SCHEMA.get("enum", [])
# THE RIGHT EACH TYPE ASKS — absent on the contract before the change: every type then reads as
# asking a right nobody holds, so the rule FAILS on behaviour rather than crashing.
TYPE_RIGHTS = TYPE_SCHEMA.get("x-rights", {})
ABSENT = "<no words>"
WORDS = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))
PAGE = WORDS["screens"]["accountPage"]
NOTIFICATIONS = PAGE.get("notifications", {})
DEVICE = NOTIFICATIONS.get("device", {})
TYPE_WORDS = WORDS.get("notifications", {}).get("types", {})
REFUSED = NOTIFICATIONS.get("refused", ABSENT)
CEILING_EVERY = WORDS["access"]["ceilingEvery"]


def type_label(notification_type):
    """The label `fr.json` gives one notification type.

    Args:
        notification_type: The type's id, `area.name`.

    Returns:
        Its label, or the absent placeholder.
    """
    area, name = notification_type.split(".", 1)
    return TYPE_WORDS.get(area, {}).get(name, {}).get("label", ABSENT)


SECTION = """() => {
  const section = document.querySelector('[data-part="profile/notifications"]');
  if (!section) return null;
  const device = section.querySelector('[data-part="profile/push-device"]');
  const firstRow = section.querySelector('[data-part="profile/push-device"], [data-notification-type]');
  return {
    heading: section.querySelector('[data-part="heading"]')?.textContent.trim() ?? null,
    support: device?.dataset.support ?? null,
    deviceText: device?.textContent ?? '',
    deviceFirst: device !== null && firstRow === device,
    enable: section.querySelector('[data-part="profile/push-enable"]') !== null,
    switches: [...section.querySelectorAll('[data-notification-type]')].map((row) => ({
      type: row.dataset.notificationType,
      text: row.textContent,
      on: row.querySelector('[role="switch"]')?.getAttribute('aria-checked') === 'true',
      pressable: row.querySelector('[role="switch"]')?.disabled === false,
    })),
  };
}"""

SAID = """()=>{const held = window.__toast?.read?.();
  return held && held.message ? (held.message.message || "") : "";}"""

CEILING = """()=>document.querySelector('[data-part="access/ceiling"]')?.textContent ?? null"""

ACCOUNT = """async () => {
  const answer = await fetch('/api/auth/me');
  const account = await answer.json();
  return {admin: account.role.kind === 'admin', rights: account.role.rights};
}"""

SUPPORTS = (
    ("profile-notifications", "granted"),
    ("profile-notifications-unasked", "unasked"),
    ("profile-notifications-denied", "denied"),
    ("profile-notifications-needs-install", "needs-install"),
    ("profile-notifications-unsupported", "unsupported"),
)


def receivable(account):
    """The types an account may receive, by the contract's rights.

    Args:
        account: `{admin, rights}` as the layer answers it.

    Returns:
        The types, in the contract's order.
    """
    return [one for one in TYPES if account["admin"] or TYPE_RIGHTS.get(one) in account["rights"]]


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
    journal = Journal("R521 — Profil carries « Notifications »: the device's line, then the account's switches")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        journal.check("the contract declares the eleven types and the right each asks",
                      len(TYPES) == 11 and set(TYPE_RIGHTS) == set(TYPES), f"{len(TYPES)} types, rights {TYPE_RIGHTS}")

        # ── R521-a: the device's line, per support ──────────────────────────
        for state, support in SUPPORTS:
            known = await exists(page, state)
            journal.check(f"the named state {state} exists", known, state)
            if not known:
                continue
            seen = await read_at(page, state, SECTION)
            if seen is None:
                journal.check(f"{state}: Profil carries the « Notifications » section", False, "no section")
                continue
            words = DEVICE.get(support, {})
            # WHERE THE DEVICE CAN STILL BE ASKED, its value IS the action: « Activer sur cet appareil ».
            value = DEVICE.get("enable", ABSENT) if support == "unasked" else words.get("value", ABSENT)
            line = words.get("line", ABSENT)
            journal.check(f"{state}: the device's line LEADS the section, « {support} »",
                          seen["deviceFirst"] and seen["support"] == support,
                          f"first {seen['deviceFirst']} · {seen['support']}")
            text = seen["deviceText"].replace("\xa0", " ")
            journal.check(f"{state}: the device's line says its support in words", value in text and line in text,
                          f"{value!r} / {line!r} in {text!r}")
            journal.check(f"{state}: the switches are drawn whatever the device", len(seen["switches"]) > 0,
                          f"{len(seen['switches'])} switches")
            journal.check(f"{state}: « activer » is offered only where the device can still be asked",
                          seen["enable"] == (support == "unasked"), f"enable {seen['enable']}")

        if await exists(page, "profile-notifications-unasked"):
            await read_at(page, "profile-notifications-unasked", SECTION)
            enable = page.locator('[data-part="profile/push-enable"]')
            if await enable.count():
                await enable.click()
                await page.wait_for_timeout(SETTLED)
                after = await page.evaluate(SECTION)
                registered = await page.evaluate(
                    "()=>(window.__mocks?.answered() ?? []).filter((one)=>one.operationId==='registerPushDevice'"
                    " && one.status===200)")
                journal.check("« activer » pressed, granted: the token is registered and the line says « granted »",
                              after is not None and after["support"] == "granted" and not after["enable"]
                              and len(registered) == 1, f"{after and after['support']} · devices {registered}")

        # ── R521-b: the account's switches ──────────────────────────────────
        if await exists(page, "profile-notifications"):
            seen = await read_at(page, "profile-notifications", SECTION)
            account = await page.evaluate(ACCOUNT)
            drawn = [row["type"] for row in (seen or {}).get("switches", [])]
            journal.check("the Admin is offered every type, in the contract's order",
                          drawn == receivable(account) and len(drawn) == len(TYPES), f"{drawn}")
            mislabelled = [row["type"] for row in (seen or {}).get("switches", [])
                           if type_label(row["type"]) not in row["text"]]
            journal.check("each switch says its type's label", not mislabelled, f"mislabelled {mislabelled}")
            journal.check("every type is on in the seeded layer",
                          seen is not None and all(row["on"] for row in seen["switches"]), repr(seen and seen["switches"]))

            turned = "system.disk_full"
            await page.click(f'[data-notification-type="{turned}"] [role="switch"]')
            await page.wait_for_timeout(SETTLED)
            after = await page.evaluate(SECTION)
            states = {row["type"]: row["on"] for row in (after or {}).get("switches", [])}
            journal.check("a switch pressed turns its type off, the others staying on",
                          states.get(turned) is False and all(on for kind, on in states.items() if kind != turned),
                          repr(states))
            await page.evaluate("()=>window.__queries?.resetQueries()")
            await page.wait_for_timeout(SETTLED)
            reread = await page.evaluate(SECTION)
            kept = {row["type"]: row["on"] for row in (reread or {}).get("switches", [])}
            journal.check("a fresh read keeps it off — the server holds the choice", kept.get(turned) is False,
                          repr(kept))

        # ── R521-c: the right the writes ask ────────────────────────────────
        if await exists(page, "profile-notifications-ceiling"):
            seen = await read_at(page, "profile-notifications-ceiling", SECTION)
            switches = (seen or {}).get("switches", [])
            journal.check("under the ceiling the switches are drawn, their state shown",
                          len(switches) == len(TYPES), f"{len(switches)} switches")
            journal.check("under the ceiling no switch can be pressed",
                          bool(switches) and not any(row["pressable"] for row in switches),
                          repr([row["type"] for row in switches if row["pressable"]]))
            journal.check("under the ceiling « activer » is absent, on a device that could still be asked",
                          seen is not None and seen["support"] == "unasked" and not seen["enable"],
                          f"{seen and seen['support']} · enable {seen and seen['enable']}")
            notice = await page.evaluate(CEILING)
            journal.check("the ceiling's notice says why, once on the page",
                          notice is not None and CEILING_EVERY in notice, repr(notice))
        else:
            journal.check("the named state profile-notifications-ceiling exists", False, "absent")

        if await exists(page, "profile-notifications"):
            await read_at(page, "profile-notifications", SECTION)
            await page.evaluate("()=>window.__toast?.hide?.()")
            # ARMED AFTER `__go`, which re-seeds the scenario and would throw an earlier outcome away.
            await page.evaluate(
                """()=>window.__mocks.setOperationOutcome("updateNotificationPreference", {status: 403})""")
            refused = "system.run_failed"
            await page.click(f'[data-notification-type="{refused}"] [role="switch"]')
            await page.wait_for_timeout(SETTLED)
            said = (await page.evaluate(SAID)).replace("\xa0", " ")
            expected = REFUSED.replace("{{type}}", type_label(refused))
            journal.check("a refused write is said refused, naming its type", said == expected,
                          f"said {said!r}, expected {expected!r}")
            after = await page.evaluate(SECTION)
            states = {row["type"]: row["on"] for row in (after or {}).get("switches", [])}
            journal.check("the refused switch returns to what the server holds", states.get(refused) is True,
                          repr(states.get(refused)))

        if await exists(page, "profile-notifications-household"):
            seen = await read_at(page, "profile-notifications-household", SECTION)
            account = await page.evaluate(ACCOUNT)
            drawn = [row["type"] for row in (seen or {}).get("switches", [])]
            expected = receivable(account)
            journal.check("a household member is offered exactly the types its rights receive",
                          seen is not None and drawn == expected and 0 < len(drawn) < len(TYPES),
                          f"drawn {drawn}, expected {expected}")
        else:
            journal.check("the named state profile-notifications-household exists", False, "absent")

        if await exists(page, "profile-notifications-none"):
            seen = await read_at(page, "profile-notifications-none", SECTION)
            journal.check("an account that receives no type is shown no section", seen is None, repr(seen))
        else:
            journal.check("the named state profile-notifications-none exists", False, "absent")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
