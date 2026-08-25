#!/usr/bin/env python3
"""The three patterns both halves of the token guard read a stylesheet with.

They live here because `check-css-tokens.py` and `csstokens_login.py` must
agree about what a comment is, what a `var()` use looks like, and which prefix
marks a token published at RUNTIME. A second copy of any of the three would be
a second thing to keep in step — and the first of them to drift would do so
silently, since both halves would still report « no violation » about a
stylesheet they were reading differently.
"""
from __future__ import annotations

import re

# Comments are stripped before anything is read: a declaration commented OUT
# used to satisfy a use, and `var(/*c*/--x)` used to be invisible. Both were
# found by an adversarial review, and both are the same mistake — reading CSS
# as text rather than as CSS.
COMMENT = re.compile(r"/\*.*?\*/", re.S)

# `var(--x)` and `var(--x, fallback)`. The fallback is captured, not merely
# detected: `var(--tm-h,)` carries a comma and nothing after it, and resolves
# to exactly as much as no fallback at all.
USE = re.compile(r"var\(\s*(--[\w-]+)\s*(?:,([^)]*))?\)")

# Tokens published at RUNTIME by script rather than declared in CSS. The prefix
# is the contract, and it is narrow on purpose: a name that merely happens to be
# missing must not be able to join this set by being renamed.
RUNTIME_PREFIX = "--tm-"

# The document's own comment syntax. The sign-in page is composed from CSS AND
# markup chunks, so the arm that reads the composition meets both.
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)

# A declaration may open a line, or follow `{` or `;` on one. Anchoring to the
# start of a line alone refused `.tm{--x:red}`, which is valid CSS.
DECLARATION = re.compile(r"(?:^|[{;])\s*(--[\w-]+)\s*:", re.M)
