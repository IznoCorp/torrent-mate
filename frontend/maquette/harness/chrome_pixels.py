"""R118 — the persistent bar is PAINTED through a transition, not just grouped.

R115 holds that the tab bar has a `::view-transition-group` of its own, and that
hold is true and was not enough. The operator saw the bar go transparent, the
steward reproduced it in frames, and the rule stayed green: the labels painted
over the casting with no bar behind them, because the bar's group was ORDERED
underneath the arriving screen's.

THAT IS B-085 IN A RULE OF THE SAME GESTURE — green because of what it does not
read. The group's existence is a fact about the transition tree; the defect lives
in the pixels the tree paints, and nothing that refuses to look at them can hold
this surface.

WHY THIS IS NOT A SCREENSHOT ORACLE, and the distinction is D8's own. D8 refuses
screenshots as the general non-regression instrument because two captures of the
same unmodified page diverge on 8 to 15 states — a whole-page comparison is
noise. This compares ONE region against ITSELF: the bar's own box, mid-transition
against the same box settled, in the same run, on the same machine. The
comparison D8 rejects is between two runs; this one is between two moments, and
a bar that is opaque at rest and opaque in flight reads identical because it IS
identical.

WHAT IT REFUSES: any drift in the bar's average colour while a transition
crosses. The defect measured 52.1 of 255 on the widest channel; a correct bar
measures 0.0. The floor is deliberately far below what the defect produced and
far above what antialiasing moves.
"""
import asyncio
import pathlib
import struct
import sys
import zlib

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PHONE, PROTOTYPE, Journal

BAR = "#nav"
FROM_STATE = "lib-grid"
TILE = '[data-part="tile"]'

# Far below the 52.1 the defect produced and far above the sub-unit drift
# antialiasing accounts for. A tolerance is a floor somebody raises, so it is
# written against both measurements rather than chosen for comfort.
DRIFT_CEILING = 6.0

# Where in the transition to look. The arrival runs 450ms; 200 is inside it with
# room either side. The flight is established on BOTH sides of the capture, so a
# sample taken after the transition ended cannot decide the verdict.
MID_TRANSITION_MILLISECONDS = 200


def average_colour(png: bytes) -> list[float]:
    """The mean red, green and blue of a PNG, decoded without a dependency.

    Args:
        png: The image bytes.

    Returns:
        The three channel means.
    """
    position = 8
    width = height = 0
    colour_type = 6
    pixels = b""
    while position < len(png):
        length = struct.unpack(">I", png[position:position + 4])[0]
        kind = png[position + 4:position + 8]
        body = png[position + 8:position + 8 + length]
        if kind == b"IHDR":
            width, height, _depth, colour_type = struct.unpack(">IIBB", body[:10])
        elif kind == b"IDAT":
            pixels += body
        position += 12 + length
    raw = zlib.decompress(pixels)
    channels = {0: 1, 2: 3, 4: 2, 6: 4}[colour_type]
    stride = width * channels
    rows = bytearray()
    previous = bytearray(stride)
    index = 0
    for _ in range(height):
        filtering = raw[index]
        index += 1
        line = bytearray(raw[index:index + stride])
        index += stride
        for at in range(stride):
            left = line[at - channels] if at >= channels else 0
            up = previous[at]
            corner = previous[at - channels] if at >= channels else 0
            if filtering == 1:
                line[at] = (line[at] + left) & 255
            elif filtering == 2:
                line[at] = (line[at] + up) & 255
            elif filtering == 3:
                line[at] = (line[at] + (left + up) // 2) & 255
            elif filtering == 4:
                estimate = left + up - corner
                distances = (abs(estimate - left), abs(estimate - up),
                             abs(estimate - corner))
                nearest = (left if distances[0] <= distances[1] and distances[0] <= distances[2]
                           else up if distances[1] <= distances[2] else corner)
                line[at] = (line[at] + nearest) & 255
        rows += line
        previous = line
    totals = [0, 0, 0]
    counted = 0
    for row in range(height):
        for column in range(width):
            at = row * stride + column * channels
            totals[0] += rows[at]
            totals[1] += rows[at + 1]
            totals[2] += rows[at + 2]
            counted += 1
    return [total / counted for total in totals]


async def hold(journal):
    """Reads the bar's own region, mid-transition against settled."""
    errors = []
    async with async_playwright() as play:
        browser = await play.chromium.launch(channel="chrome")
        context = await browser.new_context(**PHONE)
        page = await context.new_page()
        await page.goto(PROTOTYPE, wait_until="load")
        await page.evaluate("()=>window.__loadingDone?.()")
        await page.evaluate("()=>document.querySelector('#toastx')?.click()")
        await page.wait_for_timeout(250)
        await page.evaluate("(s)=>window.__go(s)", FROM_STATE)
        await page.wait_for_timeout(700)

        box = await page.evaluate(
            "(sel)=>{const node=document.querySelector(sel);"
            " const r=node.getBoundingClientRect();"
            " return {x:Math.round(r.x), y:Math.round(r.y),"
            "         width:Math.round(r.width), height:Math.round(r.height)};}",
            BAR)
        journal.check("the bar has a box to read",
                      box["width"] > 100 and box["height"] > 20,
                      f"{box} — nothing below decides anything")
        if box["width"] <= 100:
            await browser.close()
            journal.summary(errors)
            return

        settled = average_colour(
            await page.screenshot(clip=box, animations="allow"))
        await page.click(TILE)
        # WAS A TRANSITION ACTUALLY CROSSING WHEN THIS WAS READ? Nothing asked,
        # and a rule whose whole subject is « in flight » that never establishes
        # flight is green over the case it exists for: delete
        # `document.startViewTransition` and the click still navigates, the two
        # reads are then two SETTLED bars, the drift is 0.0 and this rule passes
        # while the transition it measures does not happen. B-085, in the rule
        # written against B-085.
        #
        # Read on BOTH sides of the capture, because a screenshot is not
        # instantaneous and a transition that ended between the flag and the
        # shutter would leave the same false reading.
        # RETRIED, because the capture races the transition's end under load.
        # A screenshot is not instantaneous; on a loaded runner it can outlast
        # the 450ms crossing, and then the flag reads True before and False
        # after — the rule falls for the machine's reasons rather than the
        # page's, which is B-277's species. What is NOT done is dropping the
        # second read: a sample taken after the end is exactly the vacuity this
        # hold exists to refuse, so the run is repeated instead, from a fresh
        # arrival, and only a straddle EVERY time is a violation.
        crossing = None
        crossing_before = crossing_after = None
        for attempt in range(3):
            if attempt:
                await page.go_back()
                await page.wait_for_timeout(900)
                await page.click(TILE)
            await page.wait_for_timeout(MID_TRANSITION_MILLISECONDS)
            crossing_before = await page.evaluate(
                "()=>document.documentElement.matches(':active-view-transition')")
            sample = average_colour(
                await page.screenshot(clip=box, animations="allow"))
            crossing_after = await page.evaluate(
                "()=>document.documentElement.matches(':active-view-transition')")
            if crossing_before and crossing_after:
                crossing = sample
                break
        journal.check(
            "the mid-flight read is taken WHILE a transition crosses",
            crossing is not None,
            f"`:active-view-transition` read {crossing_before} before the "
            f"capture and {crossing_after} after it, on three arrivals — the "
            "sample below is of a settled bar, and comparing two settled bars "
            "proves nothing about how one is painted under an arriving screen")
        if crossing is None:
            await browser.close()
            journal.summary(errors)
            return
        await page.wait_for_timeout(1400)
        after = average_colour(
            await page.screenshot(clip=box, animations="allow"))

        # THE CONTROL: the bar must look the same before and after, or the
        # comparison below is between two different bars rather than two moments
        # of one.
        rested = max(abs(settled[channel] - after[channel]) for channel in range(3))
        journal.check(
            "the bar is the same at rest before and after the arrival",
            rested < DRIFT_CEILING,
            f"drift {rested:.1f} between the two settled reads — the bar itself "
            "changed, so the mid-flight comparison decides nothing")

        drift = max(abs(crossing[channel] - after[channel]) for channel in range(3))
        journal.check(
            "and it does not change colour WHILE the arrival crosses",
            drift < DRIFT_CEILING,
            f"drift {drift:.1f} of 255 — settled {[round(c, 1) for c in after]}, "
            f"in flight {[round(c, 1) for c in crossing]}. The bar is painted "
            "UNDER the arriving screen's group and the content shows through it; "
            "grouping the bar is not enough, the group has to be ordered")
        await browser.close()
    journal.summary(errors)


def main():
    """Runs the rule."""
    journal = Journal("R118 — the persistent bar is painted through a transition")
    asyncio.run(hold(journal))


if __name__ == "__main__":
    main()
