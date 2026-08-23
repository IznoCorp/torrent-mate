# R69's docstring counts its own pages wrong

Found while correcting the two sentences 9.9 names in `frontend/maquette/harness/url_state.py`.
Item 12 of the rule's docstring reads:

> EVERY page has its address, not most of them. Four of the seven were asserted nowhere,
> because the nav carries four and a rule written from the nav measures the nav.

The rule before 36e86ce5 asserted a page address for FOUR of the seven — `acq`, `lib` and
`arr` off the nav, and `maint` off a cold `/maintenance` — leaving THREE asserted nowhere:
`sys`, `cfg` and `profile`. So the two halves of that sentence swap: three were asserted
nowhere, and the nav-written part of the rule measured three (which is the correction 9.9
made to the comment above `PAGE_WALKS`, where the same figure appears).

Left alone deliberately: 9.9 (c) closes with « nothing else in that file », and the sentence
is prose about what the rule used to be, not a hold. It costs one line whenever that
paragraph is next touched.
