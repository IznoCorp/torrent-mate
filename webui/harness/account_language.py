"""R526 — the interface speaks the account's language, chosen in Profil; before sign-in, the browser's.

The operator, 2026-10-03 (FG-1 B): « B » — the interface language is an ACCOUNT field, set in
Profil, the same on every device, not the device's storage; its pushes follow it (FG-2 A). And
2026-10-04 (OPEN-2 B): when nothing names a language, it is English.

R526-a — Profil says the account's language and changes it:
1. `profile`: « Langue » is drawn, its control pressed on the account's language — French, the
   seeded owner's — and the document's `lang` says it;
2. a real tap on « English » switches the WHOLE interface at once, with no reload: Profil's own
   headings and the page's heading read the English catalogue, the document's `lang` is `en`;
3. it persists: reloaded, Profil is still English, and so is another surface opened cold (the
   Médiathèque by its address) — the choice is held for the account, not the page;
4. it is the account's own: another account signed in reads French, its own, and the first
   account signed in again reads English again.

R526-b — the choice's own states, drawn:
5. `profile-language-saving`: while the server has not answered, the control says it is saving,
   takes no other tap, and the interface has NOT switched yet;
6. `profile-language-refused`: a refusal is said under the control, which stays on French, and
   the interface stays French.

R526-c — the sign-in page follows the browser (OPEN-2 B):
7. signed out in a French browser, the gate is French; in an English one, English; in a German
   one — a language the interface does not speak — English: its title, its accessible name, its
   submit button, its Plex door, and the document's `lang`.

Red on `origin/develop`: Profil has no « Langue », no named state exists, the interface never
leaves French, and the sign-in page is French in every browser.
"""

import asyncio
import json
import pathlib

from common import PROTOTYPE, SETTLED, Journal, browser_channel, chrome_launch_args, open_page, read_at, settle

from playwright.async_api import async_playwright

HERE = pathlib.Path(__file__).resolve().parent
I18N = HERE.parent / "design/src/i18n"
WORDS = {language: json.loads((I18N / f"{language}.json").read_text(encoding="utf-8")) for language in ("fr", "en")}
ABSENT = "<no words>"
# Profil's address under the prototype's root (`design/src/lib/addresses.ts`, `profile`).
PROFILE = "account"


def words(language, path):
    """One leaf of a catalogue.

    Args:
        language: `fr` or `en`.
        path: The dotted key.

    Returns:
        Its words, or the absent placeholder — so a key missing before the change fails a hold
        rather than crashing the rule.
    """
    node = WORDS[language]
    for part in path.split("."):
        node = node.get(part, {}) if isinstance(node, dict) else {}
    return node if isinstance(node, str) else ABSENT


READ = """() => {
  const section = document.querySelector('[data-part="profile/language"]');
  const pressed = section?.querySelector('[data-language-choice][aria-pressed="true"]');
  return {
    lang: document.documentElement.lang,
    section: section !== null,
    language: section?.dataset.language ?? null,
    saving: section?.hasAttribute('data-saving') ?? false,
    pressed: pressed?.dataset.languageChoice ?? null,
    disabled: [...(section?.querySelectorAll('[data-language-choice]') ?? [])].every((one) => one.disabled),
    heading: section?.querySelector('[data-part="heading"]')?.textContent.trim() ?? null,
    line: section?.querySelector('[data-part="profile/language-line"]')?.textContent.trim() ?? null,
    refusal: section?.querySelector('[data-part="profile/language-refusal"]')?.textContent.trim() ?? null,
    page: document.querySelector('[data-part="page/heading"]')?.textContent.trim() ?? null,
    you: [...document.querySelectorAll('[data-part="heading"]')].map((one) => one.textContent.trim()),
  };
}"""

GATE = """() => {
  const gate = document.querySelector('#login');
  return {
    lang: document.documentElement.lang,
    shown: gate !== null && !gate.hidden,
    title: gate?.querySelector('.logintitle')?.textContent.trim() ?? null,
    label: gate?.getAttribute('aria-label') ?? null,
    submit: gate?.querySelector('[data-part="login/submit"]')?.textContent.trim() ?? null,
    plex: gate?.querySelector('[data-part="login/plex-submit"]')?.textContent.trim() ?? null,
  };
}"""

SIGN_IN_AS = """async (id) => {
  window.__mocks.setIdentity(id);
  await window.__queries.refetchQueries({queryKey: ['/api/v1/auth/me']});
}"""


def speaks(seen, language):
    """Whether Profil, as read, speaks one language.

    Args:
        seen: The reading.
        language: `fr` or `en`.

    Returns:
        True when the document's `lang`, Profil's « Vous » heading and the page's heading are
        that language's words.
    """
    return (
        seen["lang"] == language
        and words(language, "screens.accountPage.you") in seen["you"]
        and seen["page"] == words(language, "navigation.pages.profile")
    )


async def exists(page, state):
    """Whether the prototype names a state.

    Args:
        page: The Playwright page.
        state: The state's id.

    Returns:
        True when `__states()` lists it.
    """
    return await page.evaluate("(id)=>window.__states().includes(id)", state)


async def reopen(page, address):
    """Loads one address cold, as a reload or a typed address does.

    Args:
        page: The Playwright page.
        address: The path under the prototype's root, without its leading slash.
    """
    await page.goto(PROTOTYPE + address, wait_until="load")
    await page.evaluate("()=>window.__loadingDone?.()")
    await page.evaluate("()=>document.querySelector('#toastx')?.click()")
    await page.wait_for_timeout(SETTLED)
    await settle(page)


async def main():
    journal = Journal(
        "R526 — the interface speaks the account's language, chosen in Profil; before sign-in, the browser's"
    )
    errors = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        page.on("pageerror", lambda error: errors.append(str(error)))

        # ── R526-a: Profil says the account's language and changes it ──────
        seen = await read_at(page, "profile", READ)
        journal.check(
            "Profil draws « Langue »",
            seen["section"] and seen["heading"] == words("fr", "screens.accountPage.language.heading"),
            f"section {seen['section']} · heading {seen['heading']!r}",
        )
        journal.check(
            "« Langue » is pressed on the account's language, French, and the document says it",
            seen["language"] == "fr" and seen["pressed"] == "fr" and speaks(seen, "fr"),
            f"{seen['language']} · pressed {seen['pressed']} · lang {seen['lang']} · page {seen['page']!r}",
        )

        if seen["section"]:
            await page.click('[data-part="profile/language"] [data-language-choice="en"]')
            await page.wait_for_timeout(SETTLED)
            await settle(page)
            seen = await page.evaluate(READ)
            journal.check(
                "a tap on « English » switches the whole interface at once: Profil, the page, the document",
                speaks(seen, "en")
                and seen["pressed"] == "en"
                and seen["heading"] == words("en", "screens.accountPage.language.heading"),
                f"lang {seen['lang']} · page {seen['page']!r} · headings {seen['you'][:3]}",
            )

        # PROFIL'S OWN ADDRESS, not the page's: a named state draws Profil without moving the
        # address, so reloading what the bar says would reopen the entry page.
        await reopen(page, PROFILE)
        seen = await page.evaluate(READ)
        journal.check(
            "reloaded, Profil is still English: the choice is held, not the page's",
            speaks(seen, "en") and seen["language"] == "en",
            f"lang {seen['lang']} · page {seen['page']!r}",
        )

        await reopen(page, "media")
        library = await page.evaluate(READ)
        journal.check(
            "another surface opened cold speaks English too — the Médiathèque says « Library »",
            library["lang"] == "en" and library["page"] == words("en", "navigation.pages.lib"),
            f"lang {library['lang']} · page {library['page']!r}",
        )

        await reopen(page, PROFILE)
        await page.evaluate(SIGN_IN_AS, "household-member")
        await page.wait_for_timeout(SETTLED)
        other = await page.evaluate(READ)
        journal.check(
            "another account signed in keeps its own language, French",
            speaks(other, "fr") and other["language"] == "fr",
            f"lang {other['lang']} · page {other['page']!r}",
        )
        await page.evaluate(SIGN_IN_AS, "izno")
        await page.wait_for_timeout(SETTLED)
        back = await page.evaluate(READ)
        journal.check(
            "the first account signed in again reads English again — its own",
            speaks(back, "en"),
            f"lang {back['lang']} · page {back['page']!r}",
        )

        # ── R526-b: the choice's own states ────────────────────────────────
        for state in ("profile-language-saving", "profile-language-refused"):
            journal.check(f"the named state {state} exists", await exists(page, state), state)
        if await exists(page, "profile-language-saving"):
            seen = await read_at(page, "profile-language-saving", READ)
            journal.check(
                "saving: the control says so, takes no other tap, English pressed as asked",
                seen["saving"]
                and seen["disabled"]
                and seen["pressed"] == "en"
                and seen["line"] == words("fr", "screens.accountPage.language.saving"),
                f"saving {seen['saving']} · disabled {seen['disabled']} · {seen['line']!r}",
            )
            journal.check(
                "saving: the interface has not switched before the server holds the choice",
                speaks(seen, "fr"),
                f"lang {seen['lang']}",
            )
        if await exists(page, "profile-language-refused"):
            seen = await read_at(page, "profile-language-refused", READ)
            journal.check(
                "refused: said under the control, in the interface's words",
                seen["refusal"] == words("fr", "screens.accountPage.language.refused"),
                f"{seen['refusal']!r}",
            )
            journal.check(
                "refused: the control stays on French, and so does the interface",
                seen["pressed"] == "fr" and seen["language"] == "fr" and speaks(seen, "fr"),
                f"pressed {seen['pressed']} · lang {seen['lang']}",
            )
        await context.close()

        # ── R526-c: the sign-in page follows the browser ───────────────────
        for locale, language in (("fr-FR", "fr"), ("en-US", "en"), ("de-DE", "en")):
            context, page = await open_page(browser, locale=locale)
            page.on("pageerror", lambda error: errors.append(str(error)))
            # THE SIGN-OUT IS STARTED, NOT AWAITED THROUGH THE BRIDGE: Playwright fails a pending
            # promise the page lets go of (« Resulting promise was garbage collected »), which says
            # nothing about the gate. What is read is the gate once it is up.
            await page.evaluate("()=>{ void window.__entry.signOut(); }")
            await page.wait_for_function("()=>document.querySelector('#login')?.hidden === false")
            await page.wait_for_timeout(SETTLED)
            gate = await page.evaluate(GATE)
            title = words(language, "screens.gate.title")
            journal.check(
                f"a {locale} browser meets the sign-in page in {language}",
                gate["shown"]
                and gate["lang"] == language
                and gate["title"] == title
                and gate["label"] == title
                and gate["submit"] == words(language, "screens.gate.submit")
                and gate["plex"] == words(language, "screens.gate.plex"),
                f"lang {gate['lang']} · {gate['title']!r} · {gate['submit']!r} · {gate['plex']!r}",
            )
            await context.close()
        await browser.close()

    journal.check("no JS error", not errors, str(errors[:3]))
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
