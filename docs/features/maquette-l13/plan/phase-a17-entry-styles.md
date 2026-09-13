# Phase a·17 — The entry's styles

A CONVERSION: the 13 shell classes of the login gate and the startup screen leave `legacy.css` for a
delimited `entry` block of `styles/base.css`, which `serve.py` extracts for the host's own sign-in
page, and `serve.py`'s `.logincard` rewrite is re-aimed (DESIGN § 2.6; § 3, the shell-classes row).

## The proof FIRST

- **The oracle**: zero divergence on the `signin*` states and on `startup`.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST and
  no movement.
  - `logout.py` (R54, which starts `serve.py` on a scratch port) and `startup.py` keep their counts.
  - `entry.py` keeps its count.
  - A hold that reads a class name (`logincard`, `loginfield`, `splash`) is RE-AIMED to the `id` or
    `data-part` anchor the markup already carries, with its count unchanged and said in its
    docstring.
- **`python3 scripts/check-css-tokens.py` exit 0**, with the sign-in arm (`scripts/csstokens_login.py`)
  following `serve.py`'s bindings as they stand after the move.
- `python3 scripts/check-legacy-css-residue.py --record` after the shrink, then the plain run exit 0.

## The move

- **The 13 classes keep their names in `frontend/maquette/design/index.html`**: `loginscreen`,
  `logincard`, `loginfield`, `loginerr`, `loginsub`, `loginsubmit`, `logintitle`, `splash`,
  `splashbar`, `splashmsg`, `brandbig`, `mk` and `wm`. Their rules move, unchanged, from
  `styles/legacy.css` to the `entry` block below.
- **The rewrite is re-aimed.** `serve.py:416` rewrites `<form class="logincard" id="loginform"`,
  and it matches by pattern on `id="loginform"`, never on the class string. A `str.replace` that
  matches nothing returns the markup unchanged and silently, which is why that file already moved
  the `hidden` removal to a pattern.
- **THE HOST'S SIGN-IN PAGE IS NOT THE BUILD.** `serve.py` composes the page from raw extracts:
  `extract(legacy_source, "style")` and `extract(legacy_source, "splashstyle")` (`serve.py:452`,
  bound to `LEGACY_STYLESHEET`), and that page loads no bundle. So the 13 classes do NOT become
  utilities: their rules move to a delimited `entry` block of `styles/base.css` (DESIGN § 3 — the
  document's own markup, served before any module, which is D3's base layer), and `serve.py`
  extracts that block instead. The page draws the same thing; `logout.py` reads it.
- **Restart the design host after editing `serve.py`.** It serves the markup hot but the Python
  cold, so the phase restarts its own scratch host before reading `logout.py`, and never the
  operator's host.
- **The z-ladder table in `ui/variants/frame.ts`** names `.loginscreen` and `.splash` as
  `legacy.css`. Its comments are rewritten to name the utilities.

## Gate

Per INDEX « Gates ». In addition, `check-css-tokens.py` exits 0 and the `signin*` and `startup`
oracle states read zero, and `logout.py` reads the host's sign-in page drawn from the `entry` block.

## Commit

`refactor(maquette-l13): the login gate and the startup screen take their styles from the base layer`
