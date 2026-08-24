# Open point — the a11y floor measures ONE of the two themes

Found during L06 phase 5, deliberately not decided inside the wave.

**The fact.** `a11y.py` drives the 83 named states in the default (dark)
theme only — no `data-theme` handling exists anywhere in the harness. The
contrast floor 5.3 arms is therefore a dark-theme floor: a light theme
carrying 2.1:1 text would sit under a green hard zero. This is not
hypothetical — phase 5 found and repaired exactly that (the light
`--primary-foreground` at 2.14:1 across 19 consumers, and `--primary` used
as a label colour at 2.16:1 on three sites), and both were found only
because a sub-agent drove `data-theme="light"` by hand and re-ran axe.

**The decision this needs.** Whether the a11y audit runs the 83 states in
BOTH themes (doubling its runtime, ~25 s → ~50 s, and widening every future
floor to 166 measurements), or whether a lighter arm audits the palette
pairs alone in light. Either is harness work with its own mutation tests —
a different kind of change from a palette repair, which is why it is
recorded rather than smuggled into L06.

**The size of what the dark-only floor cannot see, measured.** After phase
5's repairs, a full 83-state light sweep still reads **154 occurrences over
115 distinct rows in 34 states** — dominated by `--primary` written as a
label on a light surface (2.11–2.20, ~40 sites: `.fback`, `.hn`,
`.crossref > span`, the pipeline buttons…), plus the `warning`/`success`/
`info` tones repeating the fill-versus-label confusion (`.warnbox > b` 2.21,
`.miss` 2.01, `.dryrun` 3.52), the wordmark's SVG mark at 2.18 under the
3:1 non-text floor (axe's rule does not evaluate graphics at all), and one
`.tsx` inline re-skin (`add-screen.tsx:185-191`, `--info` as a lead colour,
3.17 in light). That is a remediation CAMPAIGN, not a call-site fix — per
the method it needs its own design and plan, which is the other reason it is
recorded here rather than absorbed into L06.

**Until then.** The light theme's contrast is only as good as the last hand
measurement (phase 5's, all repaired selectors at ≥ 4.5:1 in both themes).
