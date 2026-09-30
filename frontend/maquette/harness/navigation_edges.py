"""The navigation edges of the maquette, as data — R-navigation-a's table.

`docs/features/maquette-navigation/DESIGN.md` § 1 reads every edge of the
maquette against constitution § 16 (35 of them) and the operator's rulings of
2026-09-30; this module is that table, ONE copy, imported by the walker in
`journey.py`. It is not a rule and runs nothing: `run.sh` skips it.

A WALK is what a finger does from a cold address (`/acquisition` unless the walk
names another), then where each system Retour lands. Taps only: a step the
finger cannot make is a precondition on the mock world (`js:`), never a named
state and never `__go`.

Steps, as strings:
    `bar:<page>`    a tap on the bottom bar's button for that page;
    `menu:<page>`   the menu button, then the drawer's entry for that page;
    `tap:<css>`     a tap on the first element the selector matches;
    `tapif:<css>`   the same, only if something matches (a dialog that may ask);
    `press:<css>`   a long press on it (a card's panel);
    `fill:<css>|<text>`  a typed query;
    `js:<code>`     a precondition on the mock world a finger cannot produce.

A STOP is `(address, page, armed)` plus an optional fourth `sheet`, whether a
panel is up: `address` is a pathname, compared exactly — or as a prefix when it
ends with `*`, or with an EMPTY query when it ends with `?`. `landing` is where
the last step itself lands (a control that IS a Retour); `stops` are read after
each successive Retour.

An edge a later phase repairs carries `owed: (phase, stops)` — the stops it
lands on TODAY, asserted as such (None: the finger cannot make the walk today), so the table never lies about a row the lot
has not reached: the phase that repairs it removes the mark, and its hold flips.

`emits` names the emitters of DESIGN § 0.2's command each edge answers for, as
`<path under design/src>:<kind>=<value>`; the completeness hold in `journey.py`
fails on an emitter no edge names, and on a name no emitter answers.
"""
from common import HOME, HOME_PAGE, LIBRARY, PAGE_PATHS

SYSTEM = PAGE_PATHS["sys"]
SETTINGS = PAGE_PATHS["cfg"]
TRACKERS = PAGE_PATHS["trackers"]

# The controls the walks tap, anchored on values and parts, never on a line.
SETTINGS_ROW = 'tap:[data-part="topic"][data-page="cfg"]'
MAINTENANCE_LINK = 'tap:[data-region="system/body"] > [data-page="maint"]'
LOCKS_LINK = 'tap:[data-region="system/locks"] [data-page="maint"]'
RUNS_LINK = 'tap:[data-region="system/runs"] [data-go="acq"]'
RUN_LINK = 'tap:[data-region="run/body"] [data-go="acq"]'
A_RUN = "tap:[data-run]"
A_RUBRIC = 'tap:[data-part="topic"][data-topic="rangement"]'
SILO_PANEL = "tap:#view [data-panel='media:Silo']"
ADD_ACTION = 'tap:[data-part="shell/add-action"]'

# A ratio deferral no seed carries at rest, posed the way `acq-card-deferred-ratio`
# poses it, over the loaded world: the card then offers « Voir le tracker ».
RATIO_DEFERRAL = ("js:(()=>{window.__mocks.poseDeferral('This City Is Ours',"
                  "'ratio_below_threshold','c411');"
                  "window.__queries.removeQueries({queryKey:['/api/acquisition/to-handle']});"
                  "window.__queries.removeQueries({queryKey:['/api/staging/media']});"
                  "window.__store.write({scen:'loaded'});return true})()")

# A real add, so the add screen's footer exists: a query, a result's panel, its act.
A_REAL_ADD = [
    ADD_ACTION,
    "fill:#addq|star wars",
    'tap:[data-part="screen"][data-open] [data-panel^="add:"]',
    "tap:#sheet [data-add]",
    "tapif:#dlg [data-confirmadd]",
]

HOME_STOP = (HOME, HOME_PAGE, False)
GUARD = (HOME, HOME_PAGE, True)

TAB_BAR = "app/tab-bar.tsx:page=row.id"
DRAWER = "app/drawer.tsx:navgo=row.id"

EDGES = [
    # ── N — Système's links, B-577 first ────────────────────────────────────
    {"edge": "N1", "walk": ["menu:sys", SETTINGS_ROW],
     "stops": [(SYSTEM, "sys", False)], "emits": ["features/system/page.tsx:page=cfg"]},
    {"edge": "N2", "walk": ["menu:sys", MAINTENANCE_LINK],
     "stops": [(SYSTEM, "sys", False)], "emits": ["features/system/page.tsx:page=maint"]},
    {"edge": "N3", "walk": ["menu:sys", LOCKS_LINK],
     "stops": [(SYSTEM, "sys", False)], "emits": ["features/system/locks.tsx:page=maint"]},
    {"edge": "N4", "walk": ["menu:sys", RUNS_LINK],
     "stops": [(SYSTEM, "sys", False)], "owed": (3, [GUARD]),
     "emits": ["features/system/run-list.tsx:go=acq"]},
    {"edge": "N5", "walk": ["menu:sys", A_RUN, RUN_LINK],
     "stops": [("/run/*", "sys", False)], "owed": (3, [GUARD]),
     "emits": ["features/system/run-screen.tsx:go=acq"]},
    {"edge": "N6", "start": "run/a-run-nobody-knows", "walk": ['tap:[data-go="sys"]'],
     "landing": (SYSTEM, "sys", False), "stops": [HOME_STOP],
     "owed": (3, [(SYSTEM, "sys", False)]),
     "emits": ["features/system/run-screen.tsx:go=sys"]},
    # ── M — the side menu ────────────────────────────────────────────────────
    {"edge": "M1", "walk": ["menu:sys"], "stops": [HOME_STOP], "emits": [DRAWER]},
    {"edge": "M2", "walk": ["bar:lib", "menu:sys"],
     "stops": [(LIBRARY, "lib", False)], "emits": [DRAWER]},
    {"edge": "M3", "walk": ["menu:sys", "menu:cfg"],
     "stops": [(SYSTEM, "sys", False)], "emits": [DRAWER]},
    {"edge": "M4", "walk": ["menu:sys", SETTINGS_ROW, "menu:lib"],
     "stops": [HOME_STOP, GUARD], "emits": [DRAWER]},
    {"edge": "M5", "walk": ["menu:sys", SETTINGS_ROW, "menu:acq"],
     "stops": [GUARD], "emits": [DRAWER]},
    {"edge": "M6", "walk": ["menu:sys", "menu:sys"],
     "stops": [HOME_STOP], "emits": [DRAWER]},
    {"edge": "M7", "walk": ["menu:cfg", A_RUBRIC, "menu:sys"],
     "stops": [(SETTINGS + "?", "cfg", False)], "emits": [DRAWER]},
    # ── P — the account sheet ────────────────────────────────────────────────
    {"edge": "P1", "walk": ["bar:lib", "tap:[data-account]", 'tap:#sheet [data-go="profile"]'],
     "stops": [(LIBRARY, "lib", False, False)],
     "emits": ["features/account/panel-account.ts:go=profile"]},
    # ── T — the bottom bar ───────────────────────────────────────────────────
    {"edge": "T1", "walk": ["bar:lib"], "stops": [HOME_STOP, GUARD], "emits": [TAB_BAR]},
    {"edge": "T2", "walk": ["bar:lib", "bar:trackers"], "stops": [HOME_STOP], "emits": [TAB_BAR]},
    {"edge": "T3", "walk": ["bar:lib", "bar:acq"], "stops": [GUARD], "emits": [TAB_BAR]},
    {"edge": "T4", "walk": ["menu:sys", SETTINGS_ROW, "bar:trackers"],
     "stops": [HOME_STOP, GUARD], "emits": [TAB_BAR]},
    {"edge": "T5", "walk": ["bar:lib", "bar:lib"], "stops": [HOME_STOP], "emits": [TAB_BAR]},
    # ── L — the links inside a page ─────────────────────────────────────────
    {"edge": "L1", "walk": [RATIO_DEFERRAL, "tap:[data-acqtab=now]", 'tap:#view [data-go="trackers"]'],
     "stops": [HOME_STOP], "emits": ["features/acquisition/card-markup.ts:go=TRACKERS_PAGE"]},
    {"edge": "L2", "start": "nimportequoi", "walk": ['tap:[data-go="acq"]'],
     "stops": [("/nimportequoi", "404", False)], "emits": ["app/not-found.tsx:go=acq"]},
    {"edge": "L3", "walk": ["bar:lib", "tap:[data-lens=inc]", "press:#view [data-panel]",
                            "tap:#sheet [data-complete]"],
     "stops": [(LIBRARY, "lib", False, True)], "owed": (3, [HOME_STOP]),
     "emits": ["features/acquisition/verbs.ts:write=acq"]},
    {"edge": "L4", "walk": [*A_REAL_ADD, 'tap:[data-part="add/foot"] button'],
     "stops": [GUARD], "owed": (3, [HOME_STOP]),
     "emits": ["features/acquisition/add-screen.tsx:write=acq"]},
    # ── S — the screens ──────────────────────────────────────────────────────
    {"edge": "S1", "walk": ["bar:lib", "tap:#view [data-panel]"],
     "stops": [(LIBRARY, "lib", False)], "emits": []},
    {"edge": "S1", "walk": [ADD_ACTION], "stops": [HOME_STOP], "emits": []},
    {"edge": "S1", "walk": ["menu:sys", A_RUN], "stops": [(SYSTEM, "sys", False)], "emits": []},
    {"edge": "S1", "walk": ["tap:[data-acqtab=todo]", "tap:#view [data-resolution]"],
     "stops": [(HOME, HOME_PAGE, False)], "emits": []},
    {"edge": "S1", "walk": [SILO_PANEL, "tap:#sheet [data-releases]"],
     "stops": [(HOME, HOME_PAGE, False, True)], "emits": []},
    {"edge": "S1", "walk": [SILO_PANEL, "tap:#sheet [data-profile]"],
     "stops": [(HOME, HOME_PAGE, False, True)], "emits": []},
    {"edge": "S2", "walk": [SILO_PANEL, "tap:#sheet [data-releases]",
                            'tap:[data-part="screen"][data-open] [data-profile]'],
     "stops": [("/releases/*", HOME_PAGE, False)], "owed": (3, [(HOME, HOME_PAGE, False, True)]),
     "emits": []},
    {"edge": "S3", "walk": ["tap:[data-acqtab=todo]", "tap:#view [data-resolution]", "tap:[data-manual]"],
     "stops": [("/resolution/*", HOME_PAGE, False)], "owed": (3, [HOME_STOP]), "emits": []},
    {"edge": "S4", "walk": ["bar:lib", "tap:#view [data-panel]", 'tap:[data-part="screen/back"]'],
     "landing": (LIBRARY, "lib", False), "stops": [HOME_STOP], "emits": []},
    {"edge": "S5", "walk": ["js:window.__relay.force('refused')",
                            'tap:[data-connection-action="signin"]'],
     "landing": ("/login", HOME_PAGE, False), "stops": [HOME_STOP],
     # TODAY the notice is drawn under the bottom bar: no finger reaches it.
     "owed": (3, None), "emits": []},
    {"edge": "S6", "start": "settings/ranking", "walk": [],
     "stops": [(SETTINGS, "cfg", False), HOME_STOP, GUARD], "emits": []},
    {"edge": "S7", "start": "system", "walk": [], "stops": [HOME_STOP, GUARD], "emits": []},
    # ── Y — rubrics, panels, settings, and the guard ────────────────────────
    {"edge": "Y1", "walk": ["menu:cfg", A_RUBRIC], "stops": [(SETTINGS + "?", "cfg", False)],
     "emits": []},
    {"edge": "Y2", "walk": ["menu:cfg", 'tap:[data-part="topic"][data-profile="global"]'],
     "stops": [(SETTINGS, "cfg", False)], "emits": []},
    {"edge": "Y3", "walk": [SILO_PANEL], "stops": [(HOME, HOME_PAGE, False, False)], "emits": []},
    {"edge": "Y3", "walk": ["tap:[data-drawer]"], "stops": [HOME_STOP], "emits": []},
    {"edge": "Y4", "walk": ["bar:lib", "tap:[data-lens=inc]"], "stops": [HOME_STOP], "emits": []},
    {"edge": "Y5", "walk": ["menu:sys", RUNS_LINK],
     "stops": [(SYSTEM, "sys", False), HOME_STOP, GUARD], "owed": (3, [GUARD]), "emits": []},
    # ── DECIDED 1 — a page revisited moves to the top of the trail, never twice.
    # His own example: Acquisition → Système → Acquisition → Réglages → Système,
    # and Retour walks Réglages, then Acquisition, then the guard.
    {"edge": "D1", "walk": ["menu:sys", "menu:cfg", "menu:sys"],
     "stops": [(SETTINGS, "cfg", False), HOME_STOP, GUARD], "emits": []},
    {"edge": "D1", "walk": ["menu:sys", RUNS_LINK, "menu:cfg", "menu:sys"],
     "stops": [(SETTINGS, "cfg", False), HOME_STOP, GUARD], "emits": []},
]

# The ids DESIGN § 1 classifies, so a row dropped from the table is a failure too.
DESIGN_EDGES = [f"{family}{number}" for family, last in
                (("N", 6), ("M", 7), ("P", 1), ("T", 5), ("L", 4), ("S", 7), ("Y", 5))
                for number in range(1, last + 1)]

# The two page writes outside the three verbs — « Compléter » and the add
# screen's « Voir mes suivis » (L3, L4) — owed to phase 3, which routes both
# through the switch: `(phase, writes today)`.
PAGE_WRITES_OWED = (3, 2)

# The named states that lay a trail (DESIGN § 4), and where each Retour lands
# from them — a stop of None means the document was left.
NAMED_TRAILS = [
    ("nav-trail-settings", [(SYSTEM, "sys", False), (LIBRARY, "lib", False), HOME_STOP, GUARD]),
    ("nav-trail-revisited", [(SETTINGS, "cfg", False), HOME_STOP, GUARD]),
    ("nav-exit-armed", [None]),
]
