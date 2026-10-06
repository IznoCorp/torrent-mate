"""R-reveal — the sign-in page's password field can be shown, and is hidden again (§ 17).

The operator's order: an icon button beside the password field of the v1 sign-in page, pressed
to show what was typed and pressed again to hide it.

1. THE CONTROL: the open form draws one button on the password field, named in the interface's
   words, `aria-pressed="false"`, the field being `type="password"`.
2. SHOWN: pressed, the field becomes `type="text"`, the button `aria-pressed="true"`, and the
   value is the one typed, the very same input node (never re-rendered).
3. FOCUS AND CARET: pressed by a TAP (the context is a touch phone) while the field has the focus, the focus stays in the
   field and the caret where it was.
4. HIDDEN AGAIN: pressed a second time, the field is `type="password"` again.
5. SUBMIT: a submit leaves the field hidden, whichever way it ended.
6. THE DISCLOSURE: closing the password form hides the value again.
7. THE GATE RESTED: a revealed field, then the gate put back in its resting shape with the form open
   (a Plex sign-in ended, the gate shown again), comes back hidden.
8. THE NAMED STATES: `signin-password-typed` and `signin-password-revealed` draw the two faces.
9. WORDS: the label exists in French and in English.
"""
import asyncio
import json
import pathlib

from common import ACTED, SETTLED, Journal, browser_channel, chrome_launch_args, open_page
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOGGLE = '[data-part="login/password-reveal"]'
FIELD = '#loginform input[name="password"]'
SECRET = "correct horse"

READ = """() => {
  const field = document.querySelector('#loginform input[name="password"]');
  const toggle = document.querySelector('[data-part="login/password-reveal"]');
  return {
    type: field?.type ?? null,
    value: field?.value ?? null,
    toggle: !!toggle?.checkVisibility(),
    pressed: toggle?.getAttribute('aria-pressed') ?? null,
    label: toggle?.getAttribute('aria-label') ?? null,
    kind: toggle?.tagName ?? null,
    focused: document.activeElement === field,
    caret: [field?.selectionStart ?? null, field?.selectionEnd ?? null] };
}"""


async def main():
    journal = Journal("R-reveal — the sign-in password can be shown and is hidden again")
    languages = {name: json.loads((ROOT / f"design/src/i18n/{name}.json").read_text(encoding="utf-8"))
                 for name in ("fr", "en")}
    journal.check("the label is worded in French and in English",
                  all(bool(words["screens"]["gate"].get("showPassword")) for words in languages.values()))

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        async def go(state, wait=SETTLED):
            await page.evaluate("(id)=>window.__go(id)", state)
            await page.wait_for_timeout(wait)

        await go("signin-password-open")
        await page.fill(FIELD, SECRET)
        base = await page.evaluate(READ)
        words = await page.evaluate("()=>window.__i18n.t('screens.gate.showPassword')")
        journal.check("the open form draws the control, named, not pressed, the field hidden",
                      base["toggle"] and base["kind"] == "BUTTON" and base["pressed"] == "false"
                      and base["type"] == "password" and base["label"] == words and bool(words), str(base))

        await page.evaluate("()=>{window.__fieldNode = document.querySelector('#loginform input[name=\"password\"]');}")
        await page.focus(FIELD)
        await page.evaluate("()=>document.querySelector('#loginform input[name=\"password\"]').setSelectionRange(3, 7)")
        await page.tap(TOGGLE)
        await page.wait_for_timeout(SETTLED)
        shown = await page.evaluate(READ)
        same = await page.evaluate(
            "()=>window.__fieldNode === document.querySelector('#loginform input[name=\"password\"]')")
        journal.check("pressed, the field shows the value typed, in the same node",
                      shown["type"] == "text" and shown["pressed"] == "true" and shown["value"] == SECRET and same,
                      str(shown))
        journal.check("the focus stays in the field and the caret where it was",
                      shown["focused"] and shown["caret"] == [3, 7], str(shown))

        await page.tap(TOGGLE)
        await page.wait_for_timeout(SETTLED)
        hidden = await page.evaluate(READ)
        journal.check("pressed again, the field is hidden and the value kept",
                      hidden["type"] == "password" and hidden["pressed"] == "false" and hidden["value"] == SECRET,
                      str(hidden))

        await page.tap(TOGGLE)
        await page.fill('#loginform input[name="username"]', "someone@example.org")
        await page.click('[data-part="login/submit"]')
        await page.wait_for_timeout(ACTED + SETTLED)
        after = await page.evaluate(READ)
        journal.check("a submit leaves the field hidden", after["type"] == "password" and after["pressed"] == "false",
                      str(after))

        await go("signin-password-open")
        await page.fill(FIELD, SECRET)
        await page.tap(TOGGLE)
        await page.click('[data-part="login/password-disclosure"]')
        await page.wait_for_timeout(SETTLED)
        await page.click('[data-part="login/password-disclosure"]')
        await page.wait_for_timeout(SETTLED)
        reopened = await page.evaluate(READ)
        journal.check("closing the disclosure hides the value again",
                      reopened["type"] == "password" and reopened["pressed"] == "false", str(reopened))

        await go("signin-password-open")
        await page.fill(FIELD, SECRET)
        await page.tap(TOGGLE)
        await page.evaluate("()=>window.__entry.showSignIn(true, true)")
        await page.wait_for_timeout(SETTLED)
        rested = await page.evaluate(READ)
        journal.check("the gate put back at rest with the form open comes back hidden",
                      rested["type"] == "password" and rested["pressed"] == "false", str(rested))

        await go("signin-password-typed")
        typed = await page.evaluate(READ)
        await go("signin-password-revealed")
        revealed = await page.evaluate(READ)
        journal.check("the named states draw the two faces",
                      typed["type"] == "password" and typed["pressed"] == "false" and typed["value"]
                      and revealed["type"] == "text" and revealed["pressed"] == "true", f"{typed} / {revealed}")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())
