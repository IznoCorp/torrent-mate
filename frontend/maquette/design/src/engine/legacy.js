/* The legacy engine, at its own address.

   THIS IS NOT NEW CODE. It is the prototype's original inline script, moved
   here byte for byte so that the fragment can stop being a program and the
   engine can start being files. Nothing in it was rewritten in the move: the
   proof that it is the same engine is a state-by-state comparison of the
   whole phone frame, taken before the move and replayed after it.

   It stays JavaScript, and that is deliberate. Typing it would mean editing
   it, and an edit hidden inside a 35 000-line move is an edit nobody can
   review. The conversion of what is left happens in the open, module by
   module, against the same oracle.

   HOW IT REACHES THE PAGE. It used to be a classic script, evaluated while
   the document parsed. It is now a module, evaluated as the shell's own
   dependency — `shell.tsx` imports it before its boot calls `installArrival`,
   so the order the engine has always relied on is the order it still gets:
   everything here runs first, the shell's boot runs second. Nothing in here
   reads `document.readyState` or waits for `DOMContentLoaded`, so being
   deferred changes no branch (measured before the move: zero occurrences).

   WHY IT PUBLISHES ITSELF AT THE END. A classic script's top-level
   declarations land in the realm's global scope, where anything evaluated in
   the page can see them — and there are two hundred and fifty-four of them,
   seen that way today by the harness, which drives this engine through
   `page.evaluate` using their bare names. A module's declarations are private, so the same
   names would simply vanish, and every rule that names one would fail with a
   ReferenceError instead of a verdict. The block at the bottom republishes
   exactly the surface that already existed — no more, no less — so that
   nothing outside can tell the difference. It is a SEAM, and it is written
   down rather than inferred; it narrows when the bridge dies, not before,
   because narrowing it means editing the instrument that measures the move.
*/

import { screens, panel, bridge, seam } from "./seams.js";
import { installPressArbitration } from "../lib/press-arbitration";
import { openAddressedPanel } from "../lib/shell-doors";
import { hideLayers, installPageRestore } from "../app/layers";
import { icons } from "../app/icons";
/* THE VOCABULARY THAT LEFT, READ BACK FOR THE RULES. The constants and helpers
   this file declared live with the subject that says them now; the rules still
   reach four of them under the names they always used, so they are published
   below from their homes and die with the publication. */
import { baseTitle } from "../lib/titles";
import { dateLabel } from "../features/media/format";
import {
  cadenceSentence,
  followStatusLabel,
  nextSearchTime,
} from "../features/acquisition/follow-vocabulary";
/* THE STORE, IMPORTED. The shell creates it and installs it before anything
   here is called; the engine reads the same object every module does. */
import { store } from "../lib/store-access";
/* THE LADDER, THE PAGE SWITCH AND THE ADDRESSED PANELS, IMPORTED BACK. The
   handler that reads a Back, the verbs that write a navigation and the table
   that reopens an addressed panel are `app/`'s; the click delegation below
   still calls them by name. */
import { replacePath, walk } from "../app/page-switch";
/* THE SETTINGS CATALOGUE, IMPORTED BACK. How a setting is identified,
   listed and read moved to the feature that owns settings when its panels did,
   and the engine reads the same answers rather than keeping its own —
   `app/icons.ts`'s arrangement and its reasoning word for word: one copy, read
   by both worlds, and the day this file goes the feature loses an importer
   rather than a subject. */
import {
  settingIdentifier,
  valueShown,
} from "../features/settings/catalog";
/* THE DÉCOUVRIR FEED, IMPORTED BACK. The reserve, the pile and the
   gesture that spends them are `features/acquisition/` now — the last feature
   surface this file still DREW. Its containers were already React's; what moved
   is who owns their content, and the technique is unchanged because a replaced
   node cannot animate. `render()`, `mountLoaders()`, the click delegation and
   the swipe handlers below all still call these by name. */
import {
  advanceDeck,
  deckOrder,
  dismissSug,
  fillSug,
  loadMoreSug,
  mountDeck,
  passerSug,
  refreshDeck,
  deckHTML,
  remountSuggestionLoader,
  sugFoot,
} from "../features/acquisition/discover-feed";

  /* TorrentMate — mobile-first redesign prototype
     Data: real library titles (1,861 items). */

  /* THE VIEWPORT FALLBACK IS GONE (B-230), and it is deleted rather than
     corrected. It added a viewport meta carrying a maximum scale and a
     user-scalable refusal to any host that had none — the exact pair L03
     removed for WCAG 1.4.4, restored by a branch nobody reads. Dead on this
     host, which has one; live on any host that does not, which is what makes
     it a landmine rather than a defect: axe reports the violation when the
     directive is PRESENT on the served document, and it never was here.

     « A page that does not own its <head> » is not a case this prototype has:
     `index.html` IS the document and `serve.py` serves it. A fallback for a
     host nobody serves is machinery nobody can justify, which is D5's own
     shape, and `scripts/check-viewport-directives.py` now refuses the pair
     anywhere under `design/`. */


  /* Real data */
  const LIB_TOTAL = 1861;


  /* The 12 REAL follows, read from acquire.db with their true state: 4
     films waiting for a torrent, 8 series up to date (fractions cross-
     checked against library.db). The state is calm — it is the real one,
     and it is not dressed up. */
  /* In the « réel » scenario: nothing to grab, nothing to resolve, nothing
     in flight — the four followed films are at the legitimate rest state «
     searched, found nothing ». */


  /* 150 REAL suggestions: the output of the engine actually run against
     library.db (16 seeds → 32 TMDB calls → 640 raw titles → 503 survivors
     after excluding the 1,832 owned TMDB ids). */
  /* A cron expression on a phone card is raw jargon. The scheduler returns
     it that way; the interface TRANSLATES it, and falls back to the raw
     form only when it cannot — in which case it says so rather than
     inventing. */
  /* The schedule the engine really runs, as the scheduler returns it. */
  const CADENCE_CRON = "20 3,15 * * *";


  /* Results of a REAL TMDB search for « star wars », cross-checked against
     the library: 3 already owned, 3 absent. 257 results found, 6 shown —
     which the interface must state. */



  /* Only FILLED-IN suggestions are served: a card that opens a hollow sheet
     is a dead end, and the reserve honestly states how many it carries out
     of the 503 computed. */
  /* Only suggestions whose sheet is COMPLETE (synopsis, genres, cast) are
     served: a card that opens a hollow sheet is a dead end. The reserve
     honestly states how many it carries. */

  /* 260 REAL titles extracted from library.db (read-only) — enough to
     exercise scrolling on more than a handful of examples. */
  /* ONE sub-line grammar for the library: « year · type ». Films said «
     2026 · Film » and series « 6 ép. » — two grammars for the same line, so
     nothing was comparable from row to row. */
  /* ONE sub-line grammar (« year · type ») and the REAL storage category,
     the one used on the disks — not an invented label. */
  /* STRATIFIED sample: the 260 most recent titles, plus enough that no
     category is empty — a filter with nothing to show cannot be judged.
     Single sub-line « year · type », and the REAL storage category. */
  /* 38 REAL posters at 620 × 930, one per served suggestion, for the slide
     cards format only. The 154px poster used everywhere else is right at
     thumbnail size and mush once blown up to fill a phone screen: a format
     that shows one poster full-screen needs its own source. */
  const POSTERS_HD = {
    "Superman : L'Homme de demain": "assets/posters-hd/62e12311.webp",
    "Alita : Battle Angel": "assets/posters-hd/b39c19c9.webp",
    "Numéro quatre": "assets/posters-hd/0cb20ccb.webp",
    "Avengers : Endgame": "assets/posters-hd/46844527.webp",
    "L'Incroyable Hulk": "assets/posters-hd/97b46743.webp",
    "Man of Steel": "assets/posters-hd/94def384.webp",
    "X-Men : Dark Phoenix": "assets/posters-hd/da5a5404.webp",
    "Premier Contact": "assets/posters-hd/f2c6e872.webp",
    "Ant-Man et la Guêpe : Quantumania": "assets/posters-hd/55232278.webp",
    "The Venture Bros": "assets/posters-hd/890d8f76.webp",
    "Fast Charlie": "assets/posters-hd/01829da1.webp",
    Grimsburg: "assets/posters-hd/db2a8861.webp",
    "Solo: A Star Wars Story": "assets/posters-hd/d33616f2.webp",
    "L'Assassin": "assets/posters-hd/41922de1.webp",
    "Power Rangers": "assets/posters-hd/6bc13ec8.webp",
    "Agent Elvis": "assets/posters-hd/26da5927.webp",
    "Marvel's M.O.D.O.K.": "assets/posters-hd/5a40a4a5.webp",
    "Un Duplex pour 3": "assets/posters-hd/b4bb05a1.webp",
    "Les Trois Corniauds": "assets/posters-hd/9b1711ea.webp",
    "L'Embrouille est dans le sac": "assets/posters-hd/e4bceec0.webp",
    Impostor: "assets/posters-hd/d62c7202.webp",
    "Green Lantern : Le Complot": "assets/posters-hd/c30fc907.webp",
    "Green Lantern : Méfiez-vous de mon pouvoir":
      "assets/posters-hd/fec17dad.webp",
    "Monsieur le député": "assets/posters-hd/fe65e1aa.webp",
    "Touche pas à mon gazon": "assets/posters-hd/10abc7cf.webp",
    "LOL 2.0": "assets/posters-hd/83dc400c.webp",
    Thunderstruck: "assets/posters-hd/41c67e3d.webp",
    "American Dreamer": "assets/posters-hd/74c17774.webp",
    "Y-a-t'il quelqu'un pour l'ambulance ?": "assets/posters-hd/6db670f4.webp",
    "Jim Gaffigan: Beyond the Pale": "assets/posters-hd/3c3354da.webp",
    "Eddie Murphy: Delirious": "assets/posters-hd/9c24447d.webp",
    "Jim Gaffigan: Mr. Universe": "assets/posters-hd/608656ba.webp",
    "Spider-Man : Brand New Day": "assets/posters-hd/8c3d11b6.webp",
    "Esprits criminels": "assets/posters-hd/3f107d28.webp",
    "Avengers : Infinity War": "assets/posters-hd/e1bc275f.webp",
    Arrow: "assets/posters-hd/46781e16.webp",
    "Avatar : De feu et de cendres": "assets/posters-hd/4587e6f0.webp",
    Manhunt: "assets/posters-hd/05565116.webp",
  };

  /* The signed-in account. One place, hard-coded for now: this instance has a
     single user, and the multi-user system with per-user rights is a later
     mission. When it lands, this object is what a session payload fills.

     The avatar comes from Gravatar. The APP builds the URL at runtime:

         https://www.gravatar.com/avatar/{sha256(lowercased trimmed email)}
             ?s={size * devicePixelRatio}&d={fallback}

     Use SHA-256, not MD5 — MD5 is the legacy form Gravatar still answers but
     no longer documents. Always pass `d=`: without a fallback an account with
     no Gravatar gets the default mystery silhouette, which says less than the
     initials this interface already draws. The image below is what that URL
     returns today, embedded because this prototype has no external resource —
     a page that reaches the network is a page that renders differently
     depending on where it is opened. */
  const ACCOUNT = {
    name: "izno",
    mail: "iznogoudatall@gmail.com",
    avatar: "assets/avatar.webp",
  };


  /* Categories are the REAL storage ones (categories.json5 → disk folders),
     with their counts read from library.db. « Animation » and «
     Documentaires » merge their film/series variants: storage is by nature,
     not by medium. The total is 1,861 and it adds up — a filter whose parts
     do not sum to the whole is a filter that lies. */



  /* Two scenarios, and the resting one is the real one
     « réel » replays the exact state of the system: the staging area holds
     two folders only, and the 12 follows are at rest. That is what is
     needed to judge the rest states — which an always-busy prototype never
     shows.
     « charge » replays a dense state, to judge density and scrolling.
     The switch lives in the harness, not in the app. */

  /* REAL contents of the staging directory. */

  /* « Ça coince » holds TWO populations, and merging them would be the defect.
     A folder can be stuck because the scrape could not CHOOSE — that is a
     scrape decision, and its entry reason is a fact worth a chip — or because
     nothing in it can go through the pipeline at all, which no arbitration
     will ever fix. The first here carries a pending decision; the last two
     carry none, and say so by having no reason chip. */
  /* ── Décisions de scrapage ────────────────────────────────────────────
     A decision is a FOLDER, never a medium — that is the whole reason it
     exists. The scrape could not name what is inside it, so what the operator
     is asked about is the thing on disk: `staging_path`. Everything else on
     these screens is a proposition.

     The vocabulary is the engine's, said in French rather than encoded:
     `below_threshold` is « aucun candidat n'atteignait le seuil »,
     `mid_band` « le meilleur candidat était en confiance moyenne »,
     `ambiguous` « plusieurs candidats trop proches pour trancher », and
     `manual` « envoyé à la main depuis la préparation ». A chip saying
     « zone grise » described a STATE nobody could act on; these describe the
     REASON it is here, which is actionable. */

  /* Décisions RÉGLÉES — les dix vraies lignes de scrape_decision. */

  /* Décisions EN ATTENTE.

     « Lucky » is a real ambiguity, arbitrated for good on 15 July; the only
     thing replayed here is its status, so the screen can be judged. Its five
     candidates, their scores and their posters are what TVDB actually
     returned that day — four of them at exactly the same score, which is the
     case this screen exists for.

     The second is the OTHER shape a decision takes, and it is just as real:
     two of the ten rows in the base came back with no candidate at all. It
     hangs on the dense scenario's folder, whose stated reason already says
     precisely that. */



  /* ── LE PIPELINE ──────────────────────────────────────────────────────
     Read from `pipeline_run` in `library.db`: the last real run, its trigger,
     its duration, and what each of its NINE steps actually did.

     The steps are the engine's own, in its execution order, and each is named
     for what it DOES rather than for the command that runs it (DOIT-1). The
     engine's name is kept beside it in the mono face — it is what one needs
     when reading a log, and it is not the map.

     A step that did nothing says so with an em dash, never with « 0 ». Zero is
     a measurement; nothing to do is a state, and printing nine zeroes for a
     calm run turns a healthy pipeline into a wall of failures.

     `blockedCount` is what makes this page more than a report: the step that BLOCKS
     is the one the operator can act on, and it points at « Ça coince » just
     below rather than at a log. */

  /* The destructive journal, read from `destructive_op` in `library.db`.
     Twenty-seven operations, and every one of them was written by the
     pipeline itself rather than by a hand: `actor` says `dispatch`. That is
     worth showing as it is — a journal that only ever recorded the operator
     would be a journal nobody consults. */
  const JOURNAL = {
    total: 27,
    lignes: [
      {
        l: "Star Trek Strange New Worlds (2022)",
        v: "hier à 15 h 25",
        s: "fusion de série · métadonnées et visuels régénérés, aucun épisode écrasé · par le pipeline",
      },
      {
        l: "Ted Lasso (2020)",
        v: "le 12 août",
        s: "fusion de série · métadonnées et visuels régénérés, aucun épisode écrasé · par le pipeline",
      },
      {
        l: "Futurama (1999)",
        v: "le 12 août",
        s: "fusion de série · métadonnées et visuels régénérés, aucun épisode écrasé · par le pipeline",
      },
      {
        l: "President Curtis (2026)",
        v: "le 10 août",
        s: "fusion de série · métadonnées et visuels régénérés, aucun épisode écrasé · par le pipeline",
      },
      {
        l: "Furious (2026)",
        v: "le 10 août",
        s: "fusion de série · métadonnées et visuels régénérés, aucun épisode écrasé · par le pipeline",
      },
    ],
  };

  /* ── LA MACHINE ───────────────────────────────────────────────────────
     Read from `pm2 jlist`, from `df`, and from `library.db`. Système answers
     one question — is the machine in trouble — and never « is a medium in
     trouble », which is Arrivées' business.

     The trap this data carries, and it is the reason these two lists are
     separate: PM2 reports a SCHEDULED job as `stopped` between two runs. It is
     the literal truth about the process and a lie about the system, and an
     interface that repeats it paints six red rows on a machine in perfect
     health. A service is judged on whether it is UP; a scheduler is judged on
     whether it RAN. They are not the same object and they do not share a
     vocabulary. */
  const SERVICES = [
    {
      l: "TorrentMate",
      ton: "success",
      v: "en ligne",
      s: "depuis ce matin 09 h 36",
    },
    {
      l: "TorrentMate (staging)",
      ton: "success",
      v: "en ligne",
      s: "depuis ce matin 08 h 25",
    },
    {
      l: "Veille des téléchargements",
      ton: "success",
      v: "en ligne",
      s: "depuis le 10 août",
    },
    {
      l: "Déploiement automatique",
      ton: "success",
      v: "en ligne",
      s: "depuis le 10 août",
    },
    /* PM2's restart counter means THREE different things depending on what it
       is counting, and none of them is « how unhealthy is this ».

       On a daemon it counts manual restarts: this host sits at 92 because the
       procedure asks for one after every edit to `serve.py`. Its unstable
       count — PM2's own word for « died before min_uptime » — is zero. On a
       scheduled job the same field counts RUNS, which is why the hourly health
       check reads 263. And on a scheduled job the unstable count is not a
       crash either: a job that finishes and exits has, by definition, died
       before min_uptime.

       So the raw number is not printed. What a service owes is « is it up and
       since when »; a count whose meaning changes with the row is a figure the
       operator has to decode, which is the opposite of what a line is for. */
    {
      l: "Hôte de la maquette",
      ton: "success",
      v: "en ligne",
      s: "depuis ce matin 08 h 28 · redémarré à la main après chaque édition",
    },
  ];


  /* The disks, read from `df`. The percentage is what fills, so it is what is
     printed; a disk at 92 % says so before it says how many gigabytes remain,
     because « 335 Go » sounds like a lot and is four days of this library. */
  const DISKS = [
    {
      l: "Disk1",
      ton: "success",
      v: "de la place",
      s: "1,8 To libres · 15 To · rempli à 88 %",
    },
    {
      l: "Disk2",
      ton: "warning",
      v: "bientôt plein",
      s: "335 Go libres · 4,1 To · rempli à 92 % — quatre jours à ce rythme",
    },
    {
      l: "Disk3",
      ton: "success",
      v: "de la place",
      s: "906 Go libres · 4,1 To · rempli à 78 %",
    },
    {
      l: "Disk4",
      ton: "success",
      v: "de la place",
      s: "730 Go libres · 3,1 To · rempli à 76 %",
    },
  ];

  /* The index, read from `library.db`. « Anomalies » are counted by type
       rather than totalled: 633 alone reads as a system falling apart, and
       607 of them are junk files, which is a housekeeping errand rather than
       a fault. What one does about them lives in Maintenance. */
  const INDEX = [
    /* A quantity is not a state, so it wears no badge: « 1 863 titres » is
       neither good nor bad, it is how big the library is. */
    {
      l: "Médiathèque",
      ton: "info",
      v: "1 863 titres",
      s: "97 999 fichiers · 25 939 épisodes",
    },
    {
      l: "Dernier balayage",
      ton: "success",
      v: "réussi",
      s: "réparation, à la fin du dernier passage du pipeline",
    },
    {
      l: "Réparations en attente",
      ton: "success",
      v: "aucune",
      s: "la file est vide",
    },
    {
      l: "Écritures en attente",
      ton: "success",
      v: "aucune",
      s: "rien ne reste à propager",
    },
    /* Where a quantity hides a state, the STATE is the badge and the quantity
       moves underneath: « 633 » in red reads as a system falling apart, and
       607 of them are junk files — a housekeeping errand, not a fault. */
    {
      l: "Anomalies relevées",
      ton: "warning",
      v: "à nettoyer",
      s: "633 en tout · 607 fichiers parasites · 18 restes de release · 8 autres",
    },
  ];

  const DEPENDENCIES = [
    {
      l: "Redis",
      ton: "success",
      v: "connecté",
      s: "le relais d'événements répond",
    },
    {
      l: "TMDB / TVDB",
      ton: "success",
      v: "disponibles",
      s: "aucun disjoncteur ouvert",
    },
    {
      l: "qBittorrent",
      ton: "success",
      v: "joignable",
      s: "derrière le proxy, comme il doit l'être",
    },
  ];

  /* Code errors, and only those: a medium the pipeline refused is not an
     error, it is a decision, and it belongs to Arrivées. What is counted here
     is a run that RAISED. */
  const ERRORS = {
    total: 14,
    outOf: 425,
    latest: "le 6 août à 08 h 08",
    what: "une maintenance : grab --followed-id 26 est sorti en erreur",
    where: "api/torrent/qbittorrent.py, dans build_client",
  };

  /* The pipeline's EXECUTIONS, read from `pipeline_run`: did it run, did it
     succeed, how long did it take. That is a machine's health and it belongs
     to Système. What each run DID to the media belongs to Arrivées, which
     tells the last one step by step.

     Note that every run of the last five days blocked exactly one item. That
     is not a coincidence and it is not noise: the same folder — « Top Chef Le
     Concours Parallèle » — fails the quality gate at every pass, because no
     provider has episode data for it. A number that never moves says something
     the operator can act on, which is why it is printed. */
  const EXECUTIONS = [
    {
      q: "14/08 07 h 08",
      ok: true,
      d: "fin d'un téléchargement",
      r: "1 rangé · 1 bloqué · 1 min 44",
    },
    {
      q: "13/08 15 h 23",
      ok: true,
      d: "fin d'un téléchargement",
      r: "1 rangé · 1 bloqué · 1 min 59",
    },
    {
      q: "12/08 15 h 24",
      ok: true,
      d: "fin d'un téléchargement",
      r: "2 rangés · 1 bloqué · 7 min 19",
    },
    {
      q: "12/08 11 h 16",
      ok: true,
      d: "fin d'un téléchargement",
      r: "1 rangé · 1 bloqué · 1 min 37",
    },
    {
      q: "11/08 15 h 28",
      ok: true,
      d: "filet de sécurité",
      r: "rien de nouveau · 1 bloqué · 2 s",
    },
    {
      q: "10/08 15 h 23",
      ok: true,
      d: "fin d'un téléchargement",
      r: "2 rangés · 1 bloqué · 2 min 31",
    },
  ];

  /* What really left the pipeline in the last 24 hours, read from the
     `dispatch` step of the two runs that fall inside it. « merged » and
     « moved » are two different events for the operator — an episode joining
     a series they already have is not a new title on a disk — so they are not
     flattened into one word. */

  /* State */
  /* THE SEED, and only the seed. This used to be `let state`, a module-level
     binding re-pointed at the store's object on every notification — a cached
     copy, correct only for as long as the subscriber that refreshed it kept
     up. Every read now goes through `currentState()` instead, so there is no
     copy to be stale: the store is the one place the state is.

     What that removes is a whole class rather than an instance. A rule could
     drive a page by mutating the cached object, and R77 had to hold that
     nobody did; with no cached object there is nothing to mutate. */
  /* THE ONE READ PATH. Every `state.x` in this engine is now
     `currentState().x`, and this is what it calls: the store, each time. No
     copy is kept anywhere, so none can be stale.

     It is a function rather than a getter on some object because the call site
     reads `currentState().page` — the parentheses are the point, visible at
     every site, saying « this is a read, now » instead of looking like a
     module-level variable that someone must remember to refresh. */
  const currentState = () => store.read().state;

  /* Rendering: building blocks */


  /* The release candidate's card and the decision's card moved to the shell
     with the screen that draws them: `ReleaseCard` and `DecisionCard` in
     `src/screens/resolution.tsx`, at identical emission — `.card[data-nonmedia]`,
     no media sheet and no panel, because neither subject is a medium. Their
     rationale moved there with them; nothing here builds either shape any
     more, and a second builder kept alive next to the one being drawn is
     exactly the drift this file names below. */


  /* ONE bottom panel, and its shape follows the facts it is given — and it is
     built in the shell now: `src/components/panel.tsx` is that single
     constructor, `src/components/sheet.tsx` the layer it draws into, and
     `panel.ouvrir` the verb a producer here calls, on a descriptor.

     The DESCRIPTOR crosses unchanged (facts, never markup: `title`, `meta`,
     `subtitle`, `poster`, `avatar`, `puce`, `blocs`, and the typed blocks
     `note` / `facts` / `actions` / `seasons` / `field`) — the vocabulary is
     declared with the component, and a view wanting something outside it is
     describing a fact the panel does not know about yet. The fix is still to
     add the fact.

     An ACTION's `target` remains a map of DATA ATTRIBUTES, never a handler:
     the click delegation below reads those attributes, exactly as it does for
     a card, and that is what keeps a panel opened by the shell answering to
     the engine's own acts. */


  /* WORKING STATE — actions really MUTATE
     The datasets above are the seed; `W` is the live copy. An action does
     not settle for a toast: it moves the card, decrements the badge,
     empties the section. That is what makes this prototype a contract of
     BEHAVIOUR and not only of pixels — an implementer can point at « in the
     prototype, grabbing moves the card to in-flight », which no screenshot
     states.

     `window.__reset()` restores the seed; `__go()` calls it systematically,
     so every measurement starts from the same state. */
  /* THE DECK'S CARDS, read from the layer. `SUGGESTIONS` was a fixture here and
     left at L09; the deck still indexes into a list from a click handler that
     cannot await, so it asks a synchronous accessor. It reports an empty list
     before the query has answered, which is what the deck already drew for a
     batch fully seen. It goes with the deck at L13. */
  /* THE QUEUE, read from the layer. The lists left at L09 and these callers
     ask from click handlers that cannot await; they read the same cache the
     surfaces do, never a copy. They go with the drawing at L13. */
  /* THE FOLLOWS, read from the layer. Same reason as `queued()`: these callers
     ask from click handlers that cannot await, and they read the same cache the
     deck draws. */
  function follows() {
    return seam.followActions?.all() ?? [];
  }

  function queued() {
    return (
      seam.queue?.() ?? {
        stuck: [], moving: [], settled: [], takeable: [],
        blocked: [], inFlight: [], notFound: [], doneToday: [],
      }
    );
  }

  function suggestions() {
    return seam.suggestions?.() ?? [];
  }

  /* Simulated behaviours
     Every action really moves the data. What an implementer must reproduce
     is not « a toast appears » but « the card leaves À récupérer, appears
     in En vol at the taken step, and the badge loses 1 ». */

  function actionDelete(titres) {
    /* THE REMOVAL IS THE LAYER'S SINCE L09. `world.lib` stopped holding the
       library when the listing converted, so this filtered an empty array and
       deleted nothing at all — on the one surface whose subject is what is
       there. The confirmation stays here: it is drawn here (NE-DOIT-PAS-6). */
    seam.deleteLibraryItems?.(titres);
    store.write({ selMode: false, selected: new Set() });
    render();
    toast(
      `${titres.length} média${titres.length > 1 ? "s" : ""} supprimé${titres.length > 1 ? "s" : ""} — simulation, aucun fichier touché.`,
    );
  }

  /* The shell is static markup, so the avatar is placed once at boot — which is
     also what the app does, from its session payload. */
  const beforeReset = document.querySelector(".topbar .avatar img");
  if (beforeReset) beforeReset.src = ACCOUNT.avatar;


  /* Active datasets, resolved by scenario. The rest of the code does not
     know which scenario is running — it reads these accessors. */





  /* ── MAINTENANCE ──────────────────────────────────────────────────────
     Two levels and a panel, the shape the settings already use: the rubrics,
     a rubric's commands, then the command itself in the bottom panel.

     The panel is where the one decision of this page lives. A command that
     DELETES opens with « à blanc » on, and it cannot be turned off until the
     panel has NAMED what would be destroyed. That is not a confirmation
     dialog with another name: a dialog asks « are you sure », which one
     answers without reading, while this asks the operator to look at a list.
     A real deletion cannot be rehearsed on this machine — staging writes to
     the real disks — so what the interface owes is the look before, not a
     safety net after. */

  /* One command's panel. Derived from what is TRUE about the command — does
     it delete, can it run blank, is it long — never from a list of screens. */
  /* ── RÉGLAGES ────────────────────────────────────────────────────────
     The configuration, and the one decision that shapes everything else:
     ONE NAVIGATES BY WHAT ONE WANTS TO CHANGE, NEVER BY FILE.

     The engine keeps 19 JSON5 files and the shipped editor put them in a
     dropdown. That asks the operator to know that « thresholds.json5 » holds
     how much free space is needed before an ingest — which is knowledge about
     the code, not about the media library. The files are not hidden: each
     setting says which one it lives in, in the mono face, because that is what
     one needs when reading a diff or a log. They are simply not the map.

     Three levels, and the third is the panel this interface already has:
       · the rubrics — what one might want to change;
       · a rubric's settings — one row each, label left, value right;
       · one setting — the bottom panel, with its control and its explanation.

     The explanation is not written here. It is the comment the operator wrote
     above the key in the file itself, which until now nobody could read
     without opening the file. */

  const SECRETS = [
    { k: "QBIT_USERNAME", l: "Nom d'utilisateur qBittorrent", def: true },
    { k: "QBIT_PASSWORD", l: "Mot de passe qBittorrent", def: true },
    { k: "TMDB_API_KEY", l: "Clé API TMDB", def: true },
    { k: "TVDB_API_KEY", l: "Clé API TVDB", def: true },
    { k: "TRAKT_CLIENT_ID", l: "Identifiant client Trakt", def: true },
    { k: "TELEGRAM_BOT_TOKEN", l: "Jeton du bot Telegram", def: true },
    {
      k: "TELEGRAM_CHAT_ID",
      l: "Identifiant de discussion Telegram",
      def: true,
    },
    { k: "HEALTHCHECK_URL", l: "URL du service Healthchecks.io", def: true },
    { k: "YOUTUBE_API_KEY", l: "Clé API YouTube Data v3", def: true },
    { k: "YOUTUBE_COOKIES_FILE", l: "Fichier cookies.txt YouTube", def: false },
    {
      k: "YOUTUBE_COOKIES_FROM_BROWSER",
      l: "Navigateur source pour les cookies YouTube",
      def: false,
    },
    { k: "OMDB_API_KEY", l: "Clé API OMDb", def: true },
    {
      k: "WEB_PASSWORD_HASH",
      l: "Empreinte du mot de passe web (scrypt)",
      def: true,
    },
    {
      k: "WEB_JWT_SECRET",
      l: "Clé de signature des jetons de session",
      def: true,
    },
    { k: "C411_PASSKEY", l: "Passkey C411", def: true },
  ];

  /* ── La surface des réglages ──────────────────────────────────────────

     Level 1 lists the rubrics; level 2 a rubric's settings; level 3 is the
     bottom panel this interface already has. The search sits at level 1 and
     looks through EVERY setting of every rubric by its French label, because
     the fastest way to a setting one already knows the name of is to type it —
     and on a phone that is the difference between two taps and eleven.

     Nothing is written until the save bar is used. A setting changed here is
     PENDING, marked on its own row and counted in the bar, and the bar names
     the files it will write. */
  const SETTINGS_STATE = {
    modifs: new Map(),
    topic: null,
    q: "",
    readOnly: false,
    conflict: false,
  };

  /* Every named state starts from the same place: pending edits, the rubric
     one is in and the search are all state, and a measurement must not inherit
     the one before it. */
  function resetSettings() {
    SETTINGS_STATE.modifs.clear();
    SETTINGS_STATE.topic = null;
    SETTINGS_STATE.q = "";
    SETTINGS_STATE.readOnly = false;
    window.__mocks?.setRestartRequired(false);
    SETTINGS_STATE.conflict = false;
  }

  const settingId = settingIdentifier;

  const displayedValue = (setting) => valueShown(setting, SETTINGS_STATE.modifs);

  /* The file a setting really lives in. Nineteen of them are JSON5 overlays
     named by their concern, and one is not: the schedules belong to PM2 and
     live in `ecosystem.config.js`. Appending « .json5 » to every name would
     make the save bar promise a file that does not exist — and the save bar's
     whole job is to name what it will write. */
  function fileName(f) {
    return f.includes(".") ? f : f + ".json5";
  }

  function changedFiles() {
    return [
      ...new Set([...SETTINGS_STATE.modifs.keys()].map((id) => id.split(":")[0])),
    ];
  }

  /* What a field's value BECOMES, read from the field itself. A number field
     returns a string; storing it as one would compare unequal to the file's
     number for ever, so the type it goes back as is the type it came from. */
  function typedValue(setting, text) {
    if (setting.type === "number") {
      const n = Number(text);
      return text.trim() === "" ? null : Number.isNaN(n) ? setting.brut : n;
    }
    return text === "" ? null : text;
  }

  /* One setting, in the panel — the same panel as everywhere else, taking the
     same descriptor of facts. What it says: where the value comes from, what
     the file's own comment explains, and what it is now. */
  /* Navigation — THE PAGE TABLE IS NOT HERE ANY MORE.
     `PAGES_OF()` declared eight pages beside three other copies of the same
     fact (the drawer's own `NAVIGATION`, `PAGES` in the shell's page
     host, `PAGE_PATHS` in the address model), and a fact that exists four
     times is stale in three of them. There is one table, `app/navigation.ts`,
     and this engine reads it through `seam.navigation`, exactly as it
     reads `seam.address` for a path. The rows arrive already translated:
     no French reaches this file and none has to. */
  const navigationRows = () => seam.navigation?.rows() ?? [];

  const select = (selector) => document.querySelector(selector);
  /* The `open` class and the `data-open` attribute name ONE state, so one
     function writes both. Every layer this engine raises or clears goes
     through it: rules select and assert the attribute, and an attribute set
     anywhere the class is not would lie about the layer it describes. */
  function setOpen(element, on) {
    element.classList.toggle("open", on);
    if (on) element.setAttribute("data-open", "");
    else element.removeAttribute("data-open");
  }
  const view = select("#view"),
    port = select("#port"),
    cadre = select("#device");

  /* THE FLOATING ACTION BUTTON IS NOT THIS FILE'S ANY MORE.
     It was static markup this engine showed and hid, from two flags kept in
     step by hand — a page's own answer and whether a message was on screen.
     Both are store state now and the button reads them itself
     (`app/action-button.tsx`), which is the whole of what « one decision point »
     asked for: written in two places, the second writer erases the first. */

  function render() {
    // Every action ends in render(): one bump here reaches React for every
    // simulated mutation, including the ones made in place on `world`
    // (splice, unshift…) that never pass through `write`.
    store?.touch();
    /* An id no page carries is not a crash: it is the `*` route. Looking one
       up and calling `.render()` on nothing stopped the whole interface on a
       TypeError, which is the worst possible answer to a stale bookmark.
       The row itself is not read here any more — nothing below consumes it —
       so only the redirection is made.

       AND IT IS REFUSED RATHER THAN MADE WITH `undefined` where the table
       cannot answer. That only happens with the seam absent, and the seam is
       installed before this engine starts; written the other way it would blank
       the interface with nothing in the console, which is a worse answer than
       the TypeError this branch was written against. */
    const notFound = seam.navigation?.notFoundPage;
    if (!navigationRows().some((element) => element.id === currentState().page)) {
      if (notFound === undefined)
        // ENGLISH, and not in `fr.json`: a console message is a tool message.
        console.error("render: the navigation table answered nothing");
      else store.write({ notFound: "/" + currentState().page, page: notFound });
    }
    /* EVERY PAGE IS DRAWN BY THE SHELL, and this file writes `#view` nowhere.
       It used to branch: a page the shell owned was portalled into this very
       container, and a page the ENGINE owned had its markup written here from
       the table's own `render()`. That second half had already lost its
       subject before this lot opened — all eight rows of `PAGES_OF()` carried
       `shellOwned: true` and none carried a `render`, so the branch was
       unreachable and would have thrown if reached (B-232, and `SURVEY.md`
       § 1.3 measured it). Its subject left the file with the table: a row of
       `app/navigation.ts` carries a component and nothing else could draw it.
       So the branch is subtracted, with `shellOwnsView` and `legacyNodes`,
       which existed only to tell the two halves apart.

       Everything below still runs: the bar, the nav and the save bar are
       shared furniture, not the page's. */
    mountDeck();
    mountLoaders();
    mountSearch();
  }

  /* Loading
     Two regimes, and the difference is not ergonomic — it is ethical.

     · LIBRARY   → infinite scroll. The source is `library.db`, locally: one
     more page costs neither provider quota nor external network. Scrolling
     is the phone's natural gesture, so it is served. The shown/total count
     stays visible so one always knows where one stands within 1,861 items.

     · DÉCOUVRIR → explicit batches. Each batch costs TMDB calls. Infinite
     scroll would turn a distracted thumb into a burst against a dependency.
     The next batch is asked for.

     In both cases a loading failure SAYS SO and offers a retry: a list that
     stops in silence reads as « there is nothing left », which is a lie. */

  /* Release candidates — INVENTED, and the only invented data in this
     prototype: no tracker is queried here. The vocabulary (source,
     resolution, language, seeders) is the real ranking's. */
  /* The REAL profile, as defined in acquire/desired.py
     `QualityProfile` has only FOUR fields, and that is everything a follow
     can set. Anything else (accepted sources, CAM/TS exclusions) does not
     exist per follow.

     What is global and lives in `ranking.json5` (already editable under
     /config ?tab=classement): the ranking WEIGHTS — resolution, codec,
     container, audio, language, source, seeders, size, provider. A follow
     does not redefine them; it only sets FLOORS and requirements.

     A distinction never to lose: the profile FILTERS (it eliminates), the
     ranking ORDERS (it separates what remains). */

  /* Read-only reference data + pure rendering helpers a migrated route
     component reuses VERBATIM rather than re-declaring — a re-declaration
     would drift the day one of these changes here. None of it is engine
     STATE (never mutated by an action), so exposing it does not bypass the
     store's reactivity contract; it is exposed once, at definition time,
     well before the deferred module script (shell.tsx) runs. */
  window.__referentiel = {
    icons,
    baseTitle,
    addVerb,
    render,
    /* What the Arrivées page draws. `PIPELINE` is the run's own data, read and never written; the three
       `derived` verbs answer what is stuck, moving and settled, which depends
       on the scenario and so cannot be a frozen value. */
    /* What the Acquisition page draws: the schedule its cadence line reads. The
       follow vocabulary is `features/acquisition/follow-vocabulary.ts`'s. The
       SUGGESTION machinery is NOT here: `#sugitems`, `#sugload` and
       `.deckbody` stay the fragment's to fill, because the deck's gesture
       mutates its own DOM and a replaced node cannot animate. */
    CADENCE_CRON,
    /* The account the server really has. */
    ACCOUNT,
    /* The suggestion machinery, called by the page AFTER React has drawn its
       containers. `render()` calls these too, for as long as a legacy page can
       hold them — but it calls them BEFORE the shell has drawn, so a migrated
       page asks again from an effect, exactly as it asks for the selection bar
       to be repainted. */
    /* Published for the MEASUREMENT of the deck's gesture: a rule drives the
       two halves the way the swipe handler drives them, and reads what the
       animation is doing one frame later. */
    SERVICES,
    EXECUTIONS,
    DISKS,
    INDEX,
    DEPENDENCIES,
    ERRORS,
    /* What the Maintenance page draws. The command PANEL has left — it is
       `features/maintenance/panel-action.ts` now, reached through
       `panel.produce("action", id)` — and the risk vocabulary went with it,
       which is why `RISQUES` is no longer published from here at all. */
    /* What the Réglages page draws. REG_ETAT est l'objet
       MUTABLE que la délégation écrit : il reste la source, et le composant le
       relit à chaque bump de version du magasin (`render()` appelle
       `store?.toucher()` en premier). Le NOM d'un réglage, lui, n'est plus
       ici : `settings-labels.ts` le porte pour la page comme pour le panneau,
       et le fragment le lit par `window.__settingLabels`. */
    SETTINGS_STATE,
    SECRETS,
    
    displayedValue,
    fileName,
    changedFiles,
    JOURNAL,
    dateFR: dateLabel,
    // TODAY is declared with `const` further down this same script, past this
    // literal's evaluation point — a plain shorthand reference would hit the
    // temporal dead zone the instant this object is built. A getter defers
    // the read to first access, by which time the whole script has run.
    get TODAY() {
      return TODAY;
    },
    settingId,
    typedValue,
    toast,
  };

  /* EVERY SORT GOES BOTH WAYS, and each way has its own NAME rather than an
     arrow bolted onto a shared one: « Ajout récent » reversed is « Ajout
     ancien », which is what one would say out loud, and « Les plus incomplets »
     reversed is « Les plus complets », not « incomplets, à l'envers ».

     The panel lists the six, and the one in force is marked. The alternative —
     tapping the sort one has already chosen to flip it — costs half the rows
     and is invisible: nothing on a phone says that a second tap on the row one
     just chose does something else. A row that reads « A → Z » and answers
     Z → A is the opposite of showing what the machine will do. */

  /* The name of the sort in force, which is what the control on the count line
     reads. `sortReversed` is a store field like any other and, like `sortKey`, it
     stays OUT of the address: the sort is a preference, not a place (A7). */

  /* THE PAGE'S OWN DERIVATION, and it stays HERE while the drawing leaves.
     WHAT LEFT AT L09. `sortLibrary` and `libFiltered` answered « which media,
     in which order » over this fixture; the layer answers it now, and it
     answers it where the paging is — a page of an unsorted set, sorted
     afterwards, is a page of the wrong rows. `libraryLoaded` went with them:
     how many titles the source holds is a field of the listing's own answer. */


  /* Deleting from the poster view
     The problem: offer deletion inside a poster grid without spoiling the
     grid. Two paths, neither costing a pixel at rest:

     · LONG-PRESS on a poster → the same action sheet as everywhere else
     (Voir la fiche · Supprimer). Fast, but invisible.
     · « Sélectionner » in the count line — which already exists — switches
     the grid into selection mode: checkboxes on posters, action bar at the
     bottom, and deletion becomes MULTIPLE. That is what makes long-press
     discoverable, and the only path that allows real housekeeping.

     A simple tap still opens the sheet: the most frequent path is never
     sacrificed to a rare action. */


  /* WHICH PANEL AN ELEMENT ADDRESSES, AND WHAT OPENING IT MEANS, ARE THE
     FRAME'S — `app/frame-verbs.ts` answers `data-panel` and fills the door this
     file's press reads. Only the press stays here, and it goes with the
     gesture. */

  /* THE LONG PRESS — arbitrated in `lib/press-arbitration.ts`.

     The arbitration MOVED to that module: the timer, the 12px tolerance, the
     pointer listeners, the click swallowed by its POINT and the refusal of the
     browser's own menu are vocabulary, and vocabulary is not the engine's
     (invariant 10). What stays here is what only this surface knows — WHICH
     element a press addresses, and what opening it means. That is the whole of
     the two callbacks below.

     Nothing was added to the engine to do it: the block left and an import
     took its place, which is the only shape D5 allows. Its behaviour is
     unchanged and R55 proves that against a real thumb, before the move and
     after it. */

  /* Which panel a press addresses, from wherever the finger landed.

     Pressing a POSTER must reach the panel too, and a poster carries no
     `data-panel`: it carries the sheet it opens on a tap. Its card knows the
     panel, so the search widens to the card the finger is in — one gesture,
     one meaning, on every part of a medium. */
  function panelUnderFinger(target) {
    return (
      target.closest?.("[data-panel]") ??
      target.closest?.(".card, .sugwrap")?.querySelector("[data-panel]") ??
      null
    );
  }

  const pressArbitration = installPressArbitration({
    resolveTarget: (target) => {
      const element = panelUnderFinger(target);
      if (currentState().selMode || !element) return null;
      /* A card body opens the panel on a simple TAP, so arming a timer on it
         would fire the panel twice — once on the press, once on the click. */
      if (element.classList.contains("cbody") && target.closest?.(".cbody")) {
        return null;
      }
      return element;
    },
    onPress: (element) => openAddressedPanel?.(element),
  });

  /* User menu.
     One entry today — signing out — and the shape that will hold the rest: this
     interface is single-user for now, and a multi-user one with per-user rights
     is what the profile entry will open onto. The entry is drawn disabled and
     says why, rather than being absent: a menu that grows an item later teaches
     its shape twice. */
  /* Découvrir: one card, one tappable body
     · poster            → the media sheet, never a dead link
     · rest of the card   → bottom panel, same grammar as Suivis
     · swipe left OR right → dismissed, with « Annuler » in the toast
     The verb follows the nature: one FOLLOWS a series, one ADDS a film. */

  function sugVerb(suggestion) {
    return suggestion.k === "Film" ? "Ajouter" : "Suivre";
  }

  /* THE DÉCOUVRIR FEED HAS LEFT — the reserve, the three card shapes, the
     pile and the gesture that spends them are
     `features/acquisition/discover-feed.ts` and `discover-cards.ts` now, and
     this file imports them back. Its own `resize` listener went with
     `mountDeck`: two listeners on one window would measure the deck twice. */

  /* The label a search result's action carries, computed ONCE. The panel
     entry and the done chip on the card must say the same thing, and the
     only way to be sure of that is for there to be one sentence to say it.

     « Associer » is not a synonym of « Ajouter »: identifying a stuck folder
     tells the pipeline WHICH medium that folder is, and creates no follow. */
  function addVerb(result, index) {
    const identifier = currentState().addMode === "identify";
    if (currentState().added.has(index)) {
      return identifier
        ? "✓ Associé"
        : result.k === "Film"
          ? "✓ Ajouté"
          : "✓ Suivi";
    }
    const verbLabel = identifier
      ? "Associer"
      : result.k === "Film"
        ? "Ajouter"
        : "Suivre";
    // The ellipsis warns that the act opens a question — it will replace
    // something already held — rather than happening on the spot.
    return result.owned && !identifier ? `${verbLabel}…` : verbLabel;
  }

  /* A search result is not one of your media yet, so it has a panel of its own
     rather than a follow's: what it offers is the act that WOULD make it one,
     and the sheet to judge it by. This panel is the ONLY place that carries
     the act — the card wears no inline button, so the row stays the size of
  /* Typing filters as you go (the source is LOCAL, therefore free) — unlike
     the provider search on the add screen, which runs on submit. */
  function mountSearch() {
    /* `#libq` is NOT bound here anymore either, for the same reason as
       `.fieldinput` below: the library page owns its own search field now
       (`src/pages/library.tsx`), and the caret dance this function used to do
       around it existed only because the legacy rebuilt the node on every
       draw. React keeps the node, so there is nothing to put back.

       `.fieldinput` is NOT bound here: a settings field only ever appears
       inside the panel, and the panel's own `field` block owns its
       commit-on-blur handler now (`src/components/panel.tsx`). Binding it
       from outside would put two writers on one field. */
    const element2 = document.querySelector("#follq");
    if (element2)
      element2.oninput = () => {
        store.write({ filter: element2.value });
        const pos = element2.selectionStart;
        render();
        const element3 = document.querySelector("#follq");
        if (element3) {
          element3.focus();
          element3.setSelectionRange(pos, pos);
        }
      };
  }

  /* THE SUGGESTIONS' loader, and only theirs. The library's half left with the
     page it belonged to: its list, its footer and its sentinel are drawn by the
     component now, and filling a container React owns from here is what makes
     two worlds write one element. */
  const mountLoaders = remountSuggestionLoader;

  /* Interactions */
  /* WHETHER A MESSAGE IS ON SCREEN IS WRITTEN IN ONE PLACE. Six call sites
     flipped the class and the attribute by hand — across two functions and a
     handler bound beside them — which was already two ends kept in step by
     hand. The moment a THIRD end appeared (the action button, which must not
     sit under the message's close target) all of them would have had to move
     together or the interface would half-work in a way no single one reveals.

     THERE WAS A SEVENTH, and counting six is how it was missed: the boot hint
     is also dismissed from a capture-phase `pointerdown`, which wrote the class
     alone and left the state saying a message was up. It goes through here now,
     and R86 drives that path. */
  /* THE MESSAGE IS NOT DRAWN HERE ANY MORE. `setMessageShown` toggled a class
     and an attribute on static markup, and `toast`/`toastUndo` wrote
     `#toastmsg` — one of them with `innerHTML`, to inject an undo control as a
     string. The layer is `ui/toast.tsx` and its verbs are
     `app/toast-host.ts`'s, behind a DESCRIPTOR: what happened, and what undoes
     it. `app/panel-host.ts` is the precedent — facts cross, markup is the
     component's.

     THE THIRTY-FOUR CALLERS BELOW KEEP SAYING `toast(…)` and `toastUndo(…)`,
     because they are PRODUCERS and a producer moves to its feature at L19.
     These two lines die with them. */
  function toast(msg) {
    seam.toast?.show({ message: msg });
  }
  /* An action triggered by a GESTURE must be undoable: a sliding thumb is
     wrong more often than a pressing finger. */
  function toastUndo(msg, undo) {
    seam.toast?.show({ message: msg, undo });
  }

  /* The panel layer belongs to the shell now (`window.__panel`, rendered by
     `src/components/sheet.tsx`): a producer describes FACTS and the shell
     builds the panel. This function opens nothing anymore — it is a tripwire,
     kept so a producer nobody converted fails where it is written instead of
     quietly doing nothing. Every call site was converted with the layer. */
  function openSheet() {
    throw new Error("openSheet est mort — passer par __panel");
  }
  /* A page restored the way a named state starts: the layers hidden without
     touching history, the store written, the port back at the top when the
     patch names a new place, and the page drawn. The ladder's handler restores
     a page through it, and the harness drives its named states through it. */
  function applyState(patch) {
    hideLayers();
    store.write(patch);
    if (patch.page || patch.libLens || patch.q !== undefined)
    port.scrollTop = 0;
    render();
  }
  installPageRestore(applyState);
  /* Kept as a VERB the driver can still say: `touch.py`, `drag.py` and
     `machine.py` call `closeSheet()` from inside the page, and moving a layer
     to the shell must not take away the vocabulary that drives it. The layer
     state, the per-layer guard and the unwind all live in
     `panel.fermer` now — this is one line pointing there, not a
     second implementation. */
  function closeSheet(pop) {
    panel.close(pop);
  }
  /* THE CONFIRMATION IS NOT DRAWN HERE ANY MORE. `openDlg(html)` took an HTML
     STRING — several hundred characters of template with the escaping done by
     hand at every interpolation — wrote it into `#dlg`, then read the heading
     back out of what it had just written so the layer could name itself. The
     layer is `ui/dialog/index.tsx` and its verbs are `app/dialog-host.ts`'s,
     behind a DESCRIPTOR of facts: a heading, blocks, and actions carrying the
     `data-*` this file's own delegation still reads. */

  /* Re-rendering a screen must NEVER send the operator back to the top:
     ticking a box at the bottom of a form jumped to the top, which makes
     the form unusable. Re-rendering the SAME screen (same key) preserves
     scroll position, field values and caret; a DIFFERENT screen starts at
     zero, which is correct.
     The guard lives here, once, rather than in every control — otherwise
     the next control added reintroduces the defect. */
  /* B-026: a navigation write that fails must not fail silently — the URL
     and the interface would then disagree with nothing on record. Published
     so the harness can read it, the same way the shell publishes the set of
     path segments no table names rather than hiding them: it catches a write
     that DID fail, never a wrong one. Reset only at load — a measurement that ran before
     leaves no residue, because nothing here ever clears it back to false. */
  window.__navEchec = false;


  /* THE ENTRY IS NOT THIS FILE'S ANY MORE — the splash, the sign-in gate and
     the install proposal are `app/entry.ts`'s (`MODEL.md` § 2 Part 9). It was
     LOGIC over static markup, and it is the logic that had to move: §17
     redraws the gate for Plex SSO and cannot do so while the gate is engine
     code, because D5 allows no addition here.

     The MARKUP stays in `index.html`, for two reasons that are not the same
     one: the splash is on screen from the first painted frame, which a
     component cannot be; and the gate is EXTRACTED by `serve.py` and served as
     the design host's own password page, so a component would leave that host
     a second copy to keep in step.

     What is left below is the vocabulary the drivers still say, one line each,
     pointing at the seam. They go with the boot handshake at L13. */
  /* THE DRIVEN FLAG CROSSES AS AN ARGUMENT. `__go` drives a named state
     without touching history (R74 holds it), and `walk.driven` is how the page
     switch knows. It used to be read from INSIDE `showSignIn`, which is a
     private flag read by a function that is no longer here — so it is passed.
     Left out, driving the `signin` state replaced the address with `/login`
     and every state measured after it inherited that route: caught by the
     oracle as a divergence in `relay-refused`, eighty states later, which is
     what a leaked address looks like from the outside. */
  const showSignIn = (withError, silent) =>
    seam.entry?.showSignIn(withError, silent === true || walk.driven);



  /* THE DRAWER IS NOT DRAWN HERE ANY MORE. It was an empty `<aside>` this
     engine filled on every open — the brand, the three titled groups from a
     table of its own, the appearance control and the served identity. It is
     `app/drawer.tsx` now, over `ui/drawer.tsx`, reading the ONE navigation
     table; and it REGISTERS with the ladder rather than being found by it, so
     the ladder's handler asks a registration instead of testing a class.

     The verbs are verbs, and they are NOT this file's any more: opening the
     drawer and closing it belong to the frame that answers the taps
     (`app/frame-verbs.ts`, `app/layers.ts`). */

  /* THE APPEARANCE IS NOT THIS FILE'S ANY MORE. The three states, the stored
     choice, the live media listener and the attribute they write are
     `app/appearance.ts`'s — the frame's entry (`MODEL.md` § 2 Part 9), because
     §17 redraws the sign-in gate beside them and cannot do so while the entry
     is engine code. The drawer offers the control and calls that module
     directly; the `data-apparence` branch of the delegation went with it, and
     with it the last French `data-*` name this file wrote. */

  /* Screens and sheets */
  const TODAY = "2026-08-10";



  /* The media sheet moved to the shell with the rest of the screens:
     `src/screens/media.tsx` renders it as the route `/mediasheet/$title`. The
     verb a call site says is `screens.mediaSheet(title)`; the template,
     the seasons and the actions live there, at identical markup — the
     click delegation below still reads their data attributes. */



  /* Journey sheet
     A journey has no hole. A step not reached is stated « à venir », never
     « pas faite »; a step without a date is stated « inconnue », never
     given an invented date. */
  /* Add screen (« + ») — migrated to a real route, `AddScreen`
     (`design/src/screens/add.tsx`, reached at `/add`). The design
     rationale (full screen not a sheet, vertical result list, the two
     modes' verbs) lives there now, next to the code it explains. `SEARCH`
     and `addVerb` stay defined here and cross the handshake
     through `window.__referentiel` — the search execution itself is still
     the engine's, reached through that seam. */

  /* Choose another release — migrated to a real route, `ReleasesScreen`
     (`design/src/screens/releases.tsx`, reached at `/releases/$title`). Show
     what is NOT happening and why. Here: why the engine picked this one —
     and enough to pick another knowingly. The score shown is the ranking's,
     not an opinion. `RELEASES` stays defined here and crosses the handshake
     through `window.__referentiel` — same seam as `SEARCH`/`addVerb` above. */

  /* Gestures — pointer events, so one path serves finger, mouse and pen.
     Two differences a touch-only implementation never meets:
     · a touch is captured implicitly by the element that received the start; a
       mouse is not, so the END of a drag is listened for on the window — a
       release outside the frame would otherwise never arrive;
     · dragging a picture is a browser default that swallows the pointer stream
       outright, which is why images inside a draggable surface disable it. */
  /* WHERE A GESTURE LISTENS, and it is not a matter of taste.

     A gesture that belongs to the SCROLLPORT — the pull to refresh — listens
     on the scrollport, because that is the thing it acts on. Every other
     gesture belongs to an OBJECT: a row, a suggestion, a deck card. Objects
     are drawn in layers ABOVE the scrollport too — the sheet, the screen, the
     drawer — so an object gesture listens on the FRAME. Bound to the
     scrollport it answers only where the object happens to be drawn today, and
     four states already drew a poster no press could reach.

     The guard is the same in every one of them: `closest(...)` decides whether
     the press concerns this gesture, so listening wider costs nothing and
     stops a surface from silently losing its gesture the day it moves. */

  /* THE THREE CARD GESTURES ARE GONE FROM HERE.

     The SWIPE's shape — the axis decision, the two drawers' travel, where a
     released row rests, and the click a drag must not let through — is
     vocabulary, and vocabulary is not the engine's (invariant 10):
     `lib/swipe-arbitration.ts`. What a suggestion's swipe and a deck card's
     swipe MEAN is Découvrir's, so both went to the feature that draws them
     (`features/acquisition/card-gestures.ts`), where `dismissSug`, `passerSug`
     and `advanceDeck` already live.

     Nothing took their place here: the boot installs them on the same frame
     element this file listened on, BEFORE the tap registry, because the swipe's
     guard now says `stopImmediatePropagation` and only a listener registered
     first can stop the registry beside it. */

  /* THE PULL IS GONE FROM HERE TOO, both halves of it.

     The GESTURE was already `lib/pull-gesture.ts`'s. What stayed was the
     indicator — its height under the finger, its spinner, the message a
     finished refresh says — and that is the FRAME's affordance, so it went to
     `app/pull-indicator.ts` with the reset the harness drives through
     (`window.__reposPTR`, published from there now).

     The reset no longer writes `className = "ptr"`: it removes the two state
     classes it added. That one assignment erased every utility the markup
     paints on the indicator, which is why its states had to be read on the
     spinner inside it (ruling 59). */

  /* 4) Sheet: dragging the handle to close moved to the shell with the layer
     itself — `src/components/sheet.tsx` owns the handle, the pointer capture
     and the dismissal threshold. Nothing binds here anymore: `#sheetgrab` does
     not exist when this script runs. */


/* ── what the scenario table needs, exported by name ────────────────────────

   The harness module (`src/harness/`) holds the named states and their
   driver, and they call back into it. They could have gone through the `window` surface below
   like the harness does — but the table is SOURCE, not a probe typed into a
   browser, and a source file that reaches its neighbour through a global says
   nothing about what it actually depends on. The names are listed, so the
   dependency is readable and a deletion breaks the build instead of a run. */
export {
  applyState,
  resetSettings,
  render,
  toast,
};

/* ── the published surface ───────────────────────────────────────────────────

   Two lists, and the split is measured rather than chosen: a binding the
   engine REASSIGNS cannot be published by value, because the copy taken here
   would keep pointing at the object that was current when this line ran.
   `state` and `world` are both reassigned, and both are what the harness
   reads most — published by value they would answer a stale world, silently,
   and every rule reading them would measure a page that no longer exists.

   The rest never change identity (a `const` cannot, and no `function` here is
   reassigned — checked, not assumed), so a plain value is exactly as live as
   a getter and reads better.

   230 by value, 24 by getter, 254 in all — and BOTH numbers were wrong once,
   for the same reason twice: a pattern that answers a question narrower than
   the one being asked.

   The first count said 253, because the regex collecting the names knew
   `function`, `const`, `let`, `var` and `class`, and `signOut` is an
   `async function`. No state's markup depends on logging out, so a
   state-by-state comparison of the whole frame said « identical » while the
   rule suite said `ReferenceError`.

   The first SPLIT put `unwindInProgress` on the by-value side, because the
   test for « does the engine rebind this » looked for `name =` — and this one
   is only ever written `unwindInProgress += 1` and `-= 1`. Published by
   value it would have answered 0 forever, which is the same class of silent
   lie the getters exist to prevent, arrived at from the other direction. The
   forms that rebind without a bare `=` are compound assignment, `++`/`--`,
   destructuring on either side, and `for (name of …)`; all four were searched
   across all 254 names, and this is the only one. */
Object.assign(window, {
  POSTERS_HD,
  TODAY, CADENCE_CRON, ACCOUNT,
  DEPENDENCIES, DISKS,
  ERRORS, EXECUTIONS,
  INDEX, JOURNAL,
  LIB_TOTAL,
  SETTINGS_STATE,
  SECRETS, SERVICES,
  actionDelete, addVerb, showSignIn,
  beforeReset,
  closeSheet,
  changedFiles,
  icons,
  mountLoaders, mountSearch, fileName,
  openSheet,
  panelUnderFinger,
  settingId, resetSettings, render,
  select,
  sugVerb,
  toast, toastUndo,
  displayedValue,
  typedValue, view,
  // The rules' names for three moved helpers, published from their homes.
  cadenceFR: cadenceSentence,
  nextSearchFR: nextSearchTime,
  stLabel: followStatusLabel,
});

// Read live, because the engine reassigns each of these.
Object.defineProperties(window, {
  store: { get: () => store, configurable: true },
  // A LIVE READ, not an alias. There is no cached `state` binding left to
  // publish — the getter goes to the store, exactly as the engine's own
  // reads do, so a rule reading `state.page` reads what is on screen. And it
  // is the PRODUCT's, not only the harness's: this file reads the bare name
  // itself — the boot writes `Object.assign(state, …)` — so it is published
  // here, at evaluation, before anything starts.
  //
  // Written `() => state` for one build, after the binding was removed:
  // the name then resolved to `window.state`, i.e. to THIS getter, and
  // the page died at load with « Maximum call stack size exceeded ». A
  // getter that names the property it defines is a loop, and the only
  // reason it is not a syntax error is that the resolution is late.
  state: { get: () => currentState(), configurable: true },
});
