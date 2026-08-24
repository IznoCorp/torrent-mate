# L06 — Accepted oracle divergences

One section per folding phase; one row per accepted divergence signature. A
signature is one (region, property, before → after) shape, with the states
that carry it counted — the oracle reports it once per state, and reviewing
the same 2 px shift 83 times as 83 findings would bury the one line that is
NOT the same shift. The reason column is the review: a row whose reason does
not name the fold that produced it is a row that was waved through, and
ACC-24 counts those.

## Phase 2 — Space folds

### 2.1 — The shell (spacing 277 → 202)

| states | region                                         | change                                         | reason                                                                                                                                                                                                                                                                        |
| ------ | ---------------------------------------------- | ---------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 83     | shell/dialog                                   | padding `16px` → `14px`                        | `.dlg` 16 → `--spacing-7` (14); §1.1 folds 16 onto the 14 step — the largest single move of the sub-phase, 2 px per side                                                                                                                                                      |
| 83     | shell/sign-in                                  | padding `20px 18px` → `18px`                   | `.logincard` 20/18 → `--spacing-8` (18) both sides; computed style collapses the equal pair                                                                                                                                                                                   |
| 83     | shell/toast                                    | padding `11px 12px` → `10px 12px`              | `.toast` 11 → `--spacing-5` (10)                                                                                                                                                                                                                                              |
| 82+1   | shell/viewport                                 | padding-bottom `74px`/`16px` → `72px`/`14px`   | one declaration: `.port` calc's constant 16 → `--spacing-7` (14); 74 = bar height + 16 where the runtime token contributes                                                                                                                                                    |
| 16     | shell/search-field                             | padding `9px 0` → `8px 0`                      | `.search` 9 → `--spacing-4` (8)                                                                                                                                                                                                                                               |
| 83     | shell/toast rect                               | y +2, height −2                                | the two vertical padding pixels above; bottom-anchored, so it rises                                                                                                                                                                                                           |
| 44     | shell/dialog rect                              | y +12.4, height −25                            | the manifest (dry-run) dialog: `.dlg` −4 plus the folded interior — `.manifest li` padding 5 → 4 (−2 per item on a fixed demo list), `.dryrun`/`.manifest` margins 11 → 10, `.dlgacts`/`.dryrun` gaps 7 → 6, `.warnbox` 9 → 8; a stack of 1–2 px folds, centered so y follows |
| 37+1+1 | shell/dialog rect                              | y +1.9/+9.5/+13, height −3.8/−19/−26           | the same folds on the dialog's other content variants; −3.8 is the bare dialog (padding alone)                                                                                                                                                                                |
| 38+2   | shell/sheet-content rect                       | height −1 (±y 1)                               | sheet chrome folds: `.sheetmeta`-class margins 13 → 12 in the sheet head                                                                                                                                                                                                      |
| 32+8   | shell/page rect                                | height ±2                                      | −2 where a page's interior lost a folded 2 px; +2 where the viewport's bottom padding 16 → 14 hands the page the freed room                                                                                                                                                   |
| 16     | library/filters + shell/search-field rect      | height −2, bodies/count-line/library-list y −2 | the search field's vertical padding −2; every row below rises by the same 2 px                                                                                                                                                                                                |
| 12     | acquisition/filters + acquisition/body rect    | height −2 / y −2                               | the same search-field fold rendered on the acquisition page                                                                                                                                                                                                                   |
| 4      | settings/body rect                             | height −2                                      | the settings page's own search field, same fold                                                                                                                                                                                                                               |
| 4+1    | screen-media/body, screen-resolution/body rect | height −1                                      | the sheet-head chrome fold (−1) rendered inside the two screens that compose it                                                                                                                                                                                               |
| 2      | shell/sign-in rect                             | y +4, height −12                               | `.loginscreen` gap 22 → `--spacing-8` (18) twice (−8) plus `.logincard` vertical padding −4; centered, so y follows                                                                                                                                                           |
| 1      | shell/install-bar rect                         | y +2, height −2                                | install card interior folds (`.installcard`/`.installsteps` 1–2 px)                                                                                                                                                                                                           |

Reviewed against the two stop-shapes: no region changed WIDTH on a full-width
surface (the dialog's x and width are untouched; only y/height move), and no
state's height moved by more than the sum of the steps folded inside it (the
−25 decomposes exactly into the dialog's folded interior).

### 2.2 — The pages (spacing 202 → 49)

312 divergences, 61 rect signatures, no style-tier line: the folded rules are
page interiors, not region boxes. Two facts carry the whole review, both
verified on the diff rather than on the report: the sub-phase's diff contains
ONLY padding/gap (and shorthand-margin) value substitutions, so every rendered
difference below is a fold's; and NO signature moves x or width, and none
grows — so the chip rows did not wrap at 390 px and the stop-shapes are absent.

| states | signature | reason |
| --- | --- | --- |
| 32+16 | acquisition/tabs, library/tabs height −2 | `.seg > button` vertical padding 9 → 8 |
| 23+16 | acquisition/filters, library/filters y −2, height −2 | the tab strip above them shortened; `.pill`/`.search` folds trim the row |
| 16+16+13+13+14 | search-field y −2; library count-line/body/list y −4 | the cumulative climb: tabs −2, filters −2, everything below follows |
| 8+8+3+1+1 | acquisition/body y −2/−4, height −2…−10 | card interiors: `.ccol`/`.cfoot` 9 → 8, `.chip` rows, `.strip` padding |
| 4+2+1 | arrivals/body height −26/−28/−31 | the deck: `.kv` rows 9 → 8 each, `.dhint` −2, `.crating` +2 absorbed; a stack of ±2 folds across a card list (odd totals are line-box rounding) |
| 6+5+1+2 | settings/body height −76/−60/−47.5/−4 | `.settingrow` −2 per row across the settings lists, `.litem`/`.opt`/`.fieldinput` −2 each; −76 is ~38 folded rows, the fraction is line-box rounding |
| 2+1 | system/body height −62/−2 | the `.kv` 9 → 8 fold over the système page's key/value rows |
| 1+1+1 | maintenance/body height −4/−10/−18 | `.topic`/panel row folds on the maintenance states |
| 2+2+2+1+1 | screen-media −16/−20/−22, screen-profile −22, screen-releases −29.9 | `.mediaadd`/`.tsrc`/`.trailer`/`.eprow`/`.season` −2 each ×rows; releases ≈ 14 `.rel` rows ×−2 |
| 6+4+4+3+1+1+1 | sheet-content y +2…+10, height −2…−10 | the sheet's interior rows tightened; bottom-anchored content rises |
| 1+1 | screen-resolution/body height −0.2/−0.3 | sub-pixel line-box rounding after the `.byid`/`.opt` −2 folds — no layout change |
| 20+10+8+5+2+1… | shell/page height mirrors | `#view` is the page's container; every mirror equals its body's delta |
| 1 | arrivals/pilot-bar height −2 | its own padding fold |
| 1 | account/body height −10 | account rows −2 each |

Reviewed against the stop-shapes: no width moved anywhere (the `.btnprimary`
inline trims stay inside the element's own box; no region narrowed), and every
height delta decomposes into the ±2 px folds its surface contains.

### 2.3 — The margins (spacing 49 → 0)

83 divergences, all rect heights, no style-tier line, nothing horizontal. 16 of
the 48 folds changed a value, every one by exactly 1 px; the negatives are all
value-preserving (−4/−6/−8/−10/−14 are exact steps written as
calc(var(--spacing-N) * -1)), and `.hero`'s −62px is exempted, untouched.

| states | signature | reason |
| --- | --- | --- |
| 9+1+1 | acquisition/body height −5/−4/−1 | `.creason`/`.cov`/`.strip`/`.cfoot` margin-top 1 px folds, ×cards |
| 8 | shell/page height −1 | a single 1 px fold on the state's one affected row |
| 7 | arrivals/pilot-bar height −1 | its own 1 px margin fold |
| 5+2 | arrivals/body height −7/−10 | deck card interiors: four 1 px folds per card, ×cards |
| 4+3+1+1 | library/body, shell/library-list height −8/−1/−4 | `.folder` margin 9 → 8 top and bottom: −2 per folder row, 4 folders = −8 |
| 5+1 | screen-media/body height −1/−2 | `.hero .hm`/`.hero .hn` −1 px each |
| 1 | screen-profile/body height +6 | the one growth: `.opt .lb small` margin-top 1 → 2 (+1 per option, six options) — §1.1 folds 1 onto the 2 px step |
| 1 | screen-releases/body height −4 | release row margin folds |
| 1+1+1+1+1 | settings/system/account/not-found/screen-resolution −1 | one 1 px margin fold each (`.endmark`, `.quota`, error buttons) |
| mirrors | shell/page −4…−10 | `#view` mirrors its page's delta |

Stop-shapes: no width or x anywhere; the single height growth decomposes into
the six +1 px folds the profile screen contains.

## Phase 3 — Type folds

### 3.1 — The half-pixel collapse (text 149 → 88)

556 divergences: 6 style signatures (the three measured regions whose own
font-size was fractional — toast 12.5→12, count-line and library-count
11.5→11 — each with its 1.35-ratio line-height following), and 82 rect
signatures. The review's two forbidden shapes are absent by arithmetic:

- **No new wrap**: not one region grew. The two growing folds (8.5→10 on
  `.dlabel`, 9.5→10 on `.tilebadge`/`.st .l`) were absorbed by their
  containers — a wrap would read as +13 px or more somewhere, and the largest
  positive delta in the whole run is zero.
- **No line-count change hiding in the negatives**: every multi-line delta
  decomposes as (lines × −0.675 px), the line-height shrink of a 0.5 px fold
  at ratio 1.35 — arrivals −29.3 ≈ 43 lines, acquisition −17.1 ≈ 25 lines,
  the −39.1 outlier ≈ 58 lines on the longest deck state. A de-wrap would
  leave a −16.2 residue the decomposition doesn't show.
- **The one width move**: shell/library-count −4.9 px — `#libcount` is an
  intrinsic-width inline span; its box follows its glyphs at 11 px. Not a
  layout region and not a full-width surface.
- The button family (`.sact`/`.dlgbtn`/`.btnprimary`, −0.5 px) moved its
  controls by at most −2 px (dialog rows), never more than the size change
  times its line count — line-heights are set by the ratio, not inherited.

### 3.2a — The three fields reach 16 px (text 88 → 85)

193 divergences, every one the GROWTH this fold exists to buy (D-L06-6, the
operator's wider reading): the search field goes 13 → 16 px (line-height
17.55 → 21.6, so its box and the filters row grow 4.1 px and every row below
slides down by the same), the Configuration panel's fields go 14 → 16 px
(+2.7 px per field, +5.4 where two stack), and the settings page follows its
own search field. Nothing horizontal, no label wrapped — the growth is the
field boxes' own line-height, nowhere a text reflow.

### 3.3 + the font-shorthand repair (text 85 → 0, and the arm learns `font:`)

50 divergences. The six value-changing folds of 3.3 and the two of the
shorthand repair account for every line; the poster-fallback letters
(26→27, 30→27) and the drawer's version figure live in fixed-ratio boxes and
move no rect at all.

| states | signature | reason |
| --- | --- | --- |
| 45+1 | shell/dialog y +0.7, height −1.3/−1.4 | `.dlg h2` 15 → `--text-5` (14): one heading line at ratio line-height, centered box |
| 2 | shell/sign-in y −1.4 | `.brandbig .wm` 21 → `--text-7` (19): the wordmark above the card shrinks, the centered form rises |
| 1 | shell/install-bar y +1, height −1 | `.installgo` 12.5 → `--text-3` (12), the shorthand literal the arm could not see |
| 1 | shell/save-bar y +1, height −1 | `.savebar button` 13.5 → `--text-4` (13), the other hidden half-pixel |

No width, no x, no wrap.

### 3.2b — The rule's first catch (a 12.5px inline style in media-screen.tsx)

6 divergences, all screen-media/body, all height-only (−2.3 to −4.7 px),
width fixed at 390: the synopsis paragraph's inline `fontSize: "12.5px"` —
invisible to the static arm, caught by the browser rule R83 on its first run —
folds to `var(--text-3)` (12 px), and the paragraph's 3-6 line boxes each lose
0.675 px. Nothing wrapped, no control height moved.

## Phase 4 — Radius, motion, the runtime token

### 4.1 — The radii (radius 105 → 0)

173 divergences, all style-tier border-radius, not one rect moved:

| states | signature | reason |
| --- | --- | --- |
| 83 | shell/action-button border-radius 99px → 999px | the pill written once (`--radius-full`); on the 52 px fab both clamp to 26 px — declared value moves, rendering does not |
| 83 | shell/toast border-radius 9px → 8px | 9 → `--radius-3` (8) |
| 7 | arrivals/pilot-bar border-radius 10px → 8px | 10 → `--radius-3` (8) |

The single 50% site (`.ps-dot__d`, 8×8, square by construction) and all 37
pill sites show no computed change; no corner became a circle on a non-square
element.

### 4.2 — The motion (motion 24 → 0) — reviewed on the report, since the oracle cannot see motion

No geometric divergence: motion changes no box. The review is the fold list
itself, read change by change. Durations: the four sliding surfaces (screen,
sheet, drawer) slow 0.26 → 0.3 s; the dialog and switch family 0.18 → 0.2 s;
the deck card's entrance 0.42 → 0.45 s and its fade 0.34 → 0.3 s; the live
dot's pulse quickens 1.6 → 1.4 s and the skeleton shimmer slows 1.3 → 1.4 s.
Curves: every keyword easing and both written-out cubic-beziers now read the
two named curves; the eight transitions that carried NO easing (rendering the
browser's own `ease`, a curve nobody chose) are dressed with the standard
curve — one easing language, held by the widened arm, which now refuses
keyword easings, literal beziers, discrete steps() and a duration with no
curve, each proved by a fallen mutation. The one rhythm whose feel changes:
`.live .d`'s pulse loses its ease-in-out symmetry to the standard curve, as
§1.1's table prescribes — named here because no instrument will ever show it.
