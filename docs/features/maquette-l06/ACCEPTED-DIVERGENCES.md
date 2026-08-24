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
