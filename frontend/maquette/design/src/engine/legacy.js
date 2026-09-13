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
import { installPullGesture } from "../lib/pull-gesture";
import { icons } from "../app/icons";
/* THE STORE, IMPORTED. The shell creates it and installs it before anything
   here is called; the engine reads the same object every module does. */
import { store } from "../lib/store-access";
/* THE LADDER, THE PAGE SWITCH AND THE ADDRESSED PANELS, IMPORTED BACK. The
   handler that reads a Back, the verbs that write a navigation and the table
   that reopens an addressed panel are `app/`'s; the click delegation below
   still calls them by name. */
import { hideLayers, installPageRestore } from "../app/layers";
import { replacePath, switchPage, switchPageFromLayer, walk } from "../app/page-switch";
import { installKnownMedium } from "../app/addressed-panels";
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

  const svgIcon = (paths, strokeWidth) =>
    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${strokeWidth || 2}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths}</svg>`;
  const escapeHtml = (value) =>
    String(value).replace(
      /[&<>"]/g,
      (character) =>
        ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[character],
    );
  /* Some library.db titles carry a year suffix — sometimes DOUBLED (« Silo
     (2023) (2023) »). It is not a word of the title: neither the initials
     nor the poster lookup should see it. */
  function baseTitle(title) {
    return String(title)
      .replace(/\s*\((?:19|20)\d{2}\)\s*/g, " ")
      .trim();
  }
  const initialsOf = (title) =>
    title
      .replace(/^(Le |La |Les |The |L'|Un |Une )/i, "")
      .trim()[0]
      .toUpperCase();

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
  /* Taken VERBATIM from components/acquisition/meta.ts and FollowsPanel.tsx:
     same labels, same tones, same urgency order, same groups. */
  const ST_LABEL = {
    disabled: "En pause",
    verifying: "Vérification en cours",
    to_grab: "À récupérer",
    acquiring: "En cours d'acquisition",
    pending: "En attente de torrent",
    unverified: "Non vérifié",
    up_to_date: "À jour",
    ended: "Terminé",
  };
  const ST_LABEL_MOVIE = {
    up_to_date: "Acquis",
    ended: "Acquis",
    disabled: "Recherche arrêtée",
  };
  const ST_TONE = {
    disabled: "neutral",
    verifying: "info",
    to_grab: "warning",
    acquiring: "info",
    pending: "waiting",
    unverified: "muted",
    up_to_date: "success",
    ended: "neutral",
  };
  const URGENCY = {
    to_grab: 0,
    acquiring: 1,
    verifying: 2,
    pending: 3,
    unverified: 4,
    up_to_date: 5,
    ended: 6,
    disabled: 7,
  };
  const GROUPS = [
    {
      key: "demandent",
      l: "Demandent quelque chose",
      pip: "warning",
      of: ["to_grab", "pending", "unverified"],
    },
    {
      key: "en-cours",
      l: "En cours",
      pip: "info",
      of: ["acquiring", "verifying"],
    },
    { key: "a-jour", l: "À jour", pip: "success", of: ["up_to_date"] },
    { key: "terminees", l: "Terminées", pip: "neutral", of: ["ended"] },
    { key: "en-pause", l: "En pause", pip: "neutral", of: ["disabled"] },
  ];
  /* A cron expression on a phone card is raw jargon. The scheduler returns
     it that way; the interface TRANSLATES it, and falls back to the raw
     form only when it cannot — in which case it says so rather than
     inventing. */
  /* The schedule the engine really runs, as the scheduler returns it. */
  const CADENCE_CRON = "20 3,15 * * *";

  function cadenceFR(cron) {
    const exec = /^(\d+)\s+([\d,]+)\s+\*\s+\*\s+\*$/.exec(String(cron).trim());
    if (!exec)
      return `Recherche automatique : ${escapeHtml(cron)} (cadence non interprétée)`;
    const min = exec[1].padStart(2, "0");
    const hours = exec[2].split(",").map((split) => `${split} h ${min}`);
    const when =
      hours.length === 1
        ? `à ${hours[0]}`
        : `à ${hours.slice(0, -1).join(", ")} et ${hours[hours.length - 1]}`;
    const freq =
      hours.length === 1
        ? "une fois par jour"
        : `${hours.length} fois par jour`;
    return `Recherche automatique : ${freq}, ${when}`;
  }

  /* The next slot that cron will fire, phrased as the cadence line phrases the
     others. Returns null when the expression cannot be read — a card then says
     nothing about the next search rather than inventing one. */
  function nextSearchFR(cron, now) {
    const exec = /^(\d+)\s+([\d,]+)\s+\*\s+\*\s+\*$/.exec(String(cron).trim());
    if (!exec) return null;
    const min = Number(exec[1]);
    const hours = exec[2]
      .split(",")
      .map(Number)
      .sort((a2, b) => a2 - b);
    const h = now.getHours(),
      m = now.getMinutes();
    const next =
      hours.find((x) => x > h || (x === h && min > m)) ?? hours[0];
    return `${next} h ${String(min).padStart(2, "0")}`;
  }

  function stLabel(follow) {
    return follow.k === "movie"
      ? (ST_LABEL_MOVIE[follow.st] ?? ST_LABEL[follow.st])
      : ST_LABEL[follow.st];
  }
  /* followFraction: a film has no fraction; an unknown catalogue yields « —
     ». */
  function stFraction(follow) {
    if (follow.k === "movie") return null;
    if (follow.aired == null) return "—";
    return `${follow.own ?? 0}/${follow.aired}`;
  }
  /* gridBadge: a NUMBER for what is actionable, « • » for a film, « ? »
     with no verdict, NOTHING when there is nothing to do — absence IS the
     signal. */
  function gridBadge(follow) {
    if (
      follow.st === "to_grab" ||
      follow.st === "acquiring" ||
      follow.st === "pending"
    ) {
      if (follow.k === "movie") return { txt: "•", tone: follow.st };
      return {
        txt: String(Math.max(1, (follow.aired ?? 0) - (follow.own ?? 0))),
        tone: follow.st,
      };
    }
    if (follow.st === "unverified" || follow.st === "verifying")
      return { txt: "?", tone: "muted" };
    return null;
  }

  /* REAL seasons (library.db): [season number, aired, owned]. American Dad!
     exercises the large-catalogue rules (22 seasons, 403 episodes, all
     complete → all collapsed); Tintin exercises the holed matrix. */
  /* Results of a REAL TMDB search for « star wars », cross-checked against
     the library: 3 already owned, 3 absent. 257 results found, 6 shown —
     which the interface must state. */

  const SEASONS = {
    "American Dad!": [
      [1, 7, 7],
      [2, 16, 16],
      [3, 19, 19],
      [4, 16, 16],
      [5, 20, 20],
      [6, 18, 18],
      [7, 19, 19],
      [8, 18, 18],
      [9, 19, 19],
      [10, 20, 20],
      [11, 3, 3],
      [12, 15, 15],
      [13, 22, 22],
      [14, 22, 22],
      [15, 22, 22],
      [16, 20, 20],
      [17, 24, 24],
      [18, 22, 22],
      [19, 22, 22],
      [20, 22, 22],
      [21, 22, 22],
      [22, 11, 11],
    ],
    "Les aventures de Tintin": [
      [1, 13, 7],
      [2, 13, 7],
      [3, 13, 7],
    ],
    "Dexter: Resurrection": [[1, 10, 10]],
    Silo: [
      [1, 10, 10],
      [2, 10, 10],
      [3, 7, 6],
    ],
    Furious: [[1, 5, 5]],
    "President Curtis": [[1, 3, 3]],
    "House of the Dragon": [
      [1, 10, 10],
      [2, 8, 8],
      [3, 8, 8],
    ],
    "Star Trek: Strange New Worlds": [
      [1, 10, 10],
      [2, 10, 10],
      [3, 10, 10],
      [4, 3, 3],
    ],
    "Ted Lasso": [
      [1, 10, 10],
      [2, 12, 12],
      [3, 12, 12],
      [4, 1, 1],
    ],
    "Les Animaniacs": [
      [1, 172, 93],
      [2, 12, 4],
      [3, 46, 13],
    ],
  };

  const EP_LABEL = {
    in_library: "En médiathèque",
    to_grab: "À récupérer",
    acquiring: "En cours d'acquisition",
    pending: "En attente de torrent",
    announced: "Annoncé",
    unverified: "Non vérifié",
  };
  /* Lifecycle order, as the operator reads it. */
  const EP_ORDER = [
    "unverified",
    "announced",
    "pending",
    "to_grab",
    "acquiring",
    "in_library",
  ];
  const EP_SWATCH = {
    unverified: "sw-muted",
    announced: "sw-upcoming",
    pending: "sw-waiting",
    to_grab: "sw-warning",
    acquiring: "sw-info",
    in_library: "sw-success",
  };

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

  /* The synopsis of every medium the library holds, read from the <plot> of
     its own NFO on disk. It is NOT in `library.db`: neither a column of
     `media_item` nor a key of `item_attribute` carries it, so the app cannot
     render this today — the read-model has to grow a field first. Nine of the
     345 titles have none, and those show nothing rather than a filler. */
  const LIBRARY = [
    { t: "On l'appelait Robin des Bois", f: "2026 · Film", c: "movies" },
    { t: "Ninja Turtles", f: "2014 · Film", c: "movies" },
    {
      t: "Big Chicken Le complot de la malbouffe",
      f: "2026 · Film",
      c: "movies_documentary",
    },
    { t: "The Bombing of Pan Am 103", f: "2025 · Série", c: "tv_shows" },
    { t: "Batman Caped Crusader (2024)", f: "2024 · Série", c: "tv_shows" },
    { t: "Marjorie Prime", f: "2017 · Film", c: "movies" },
    {
      t: "Alison Wheeler La Promesse d'un soir",
      f: "2026 · Film",
      c: "movies",
    },
    { t: "Alexandre Kominek Bâtard sensible", f: "2026 · Film", c: "movies" },
    { t: "President Curtis (2026)", f: "2026 · Série", c: "tv_shows" },
    { t: "Supergirl", f: "2026 · Film", c: "movies" },
    { t: "Margin Call", f: "2011 · Film", c: "movies" },
    { t: "Furious (2026)", f: "2026 · Série", c: "tv_shows" },
    { t: "The Hawk", f: "2026 · Série", c: "tv_shows" },
    { t: "Disclosure Day", f: "2026 · Film", c: "movies" },
    { t: "The Mandalorian and Grogu", f: "2026 · Film", c: "movies" },
    { t: "Scary Movie", f: "2026 · Film", c: "movies" },
    { t: "Rick and Morty (2013)", f: "2013 · Série", c: "tv_shows" },
    { t: "Le Premier Jour du reste de ta vie", f: "2008 · Film", c: "movies" },
    {
      t: "Gone Girls The Long Island Serial Killer",
      f: "2025 · Série",
      c: "tv_shows",
    },
    {
      t: "The Alabama Solution dans l’enfer de la prison",
      f: "2025 · Film",
      c: "movies_documentary",
    },
    { t: "Lucky", f: "2026 · Série", c: "tv_shows" },
    { t: "Backrooms", f: "2026 · Film", c: "movies" },
    {
      t: "Aymeric Lompret & Pierre-Emmanuel Barré Woke me up !",
      f: "2026 · Film",
      c: "movies",
    },
    { t: "Obsession", f: "2026 · Film", c: "movies" },
    { t: "Le Réveil de la Momie", f: "2026 · Film", c: "movies" },
    { t: "Inès Reg On est toujours ensemble", f: "2026 · Film", c: "movies" },
    {
      t: "Guillermo Guiz - La formidable ascension sociale temporaire de Guy Verstraeten",
      f: "2026 · Film",
      c: "movies",
    },
    {
      t: "Benjamin Tranié - Félicitations et tout et tout",
      f: "2026 · Film",
      c: "movies",
    },
    { t: "Smiling Friends", f: "2020 · Série", c: "tv_shows" },
    { t: "Simpsley", f: "2026 · Film", c: "movies_animation" },
    { t: "Chouette, un jeu d'enfants", f: "2024 · Film", c: "movies" },
    { t: "La Liste de Schindler", f: "1993 · Film", c: "movies" },
    { t: "This City Is Ours", f: "2025 · Série", c: "tv_shows" },
    { t: "Les Groos", f: "2022 · Série", c: "tv_shows" },
    { t: "I Will Find You", f: "2026 · Série", c: "tv_shows" },
    { t: "Dead Landes", f: "2016 · Série", c: "tv_shows" },
    { t: "Les Moutons détectives", f: "2026 · Film", c: "movies" },
    { t: "The Hack", f: "2025 · Série", c: "tv_shows" },
    { t: "Star City", f: "2026 · Série", c: "tv_shows" },
    { t: "PONIES", f: "2026 · Série", c: "tv_shows" },
    { t: "Michael Jackson The Verdict", f: "2026 · Série", c: "tv_shows" },
    { t: "Lucky Luke", f: "2026 · Série", c: "tv_shows" },
    { t: "Due spicci", f: "2026 · Série", c: "tv_shows" },
    {
      t: "Dear Killer Nannies Criado por sicarios",
      f: "2026 · Série",
      c: "tv_shows",
    },
    { t: "Among Us", f: "2026 · Série", c: "tv_shows" },
    { t: "War Machine", f: "2026 · Film", c: "movies" },
    { t: "Une famille de bâtards", f: "2026 · Film", c: "movies" },
    {
      t: "Super Mario Galaxy, le film",
      f: "2026 · Film",
      c: "movies_animation",
    },
    { t: "Over Your Dead Body", f: "2026 · Film", c: "movies" },
    { t: "Mortal Kombat II", f: "2026 · Film", c: "movies" },
    { t: "Michael", f: "2026 · Film", c: "movies" },
    { t: "Marty Supreme", f: "2025 · Film", c: "movies" },
    { t: "Marsupilami", f: "2026 · Film", c: "movies" },
    { t: "L'éléphant", f: "2025 · Film", c: "movies_animation" },
    { t: "Jumpers", f: "2026 · Film", c: "movies_animation" },
    {
      t: "Jack Ryan de Tom Clancy Guerre Fantôme",
      f: "2026 · Film",
      c: "movies",
    },
    { t: "Fantômes contre fantômes", f: "1996 · Film", c: "movies" },
    { t: "La Cité des Anges", f: "1998 · Film", c: "movies" },
    { t: "Les Griffes de la Nuit", f: "1984 · Film", c: "movies" },
    { t: "Les Légendaires", f: "2026 · Film", c: "movies_animation" },
    { t: "Top Chef", f: "2010 · Série", c: "tv_programs" },
    { t: "The Boys", f: "2019 · Série", c: "tv_shows" },
    { t: "From", f: "2022 · Série", c: "tv_shows" },
    { t: "Widow's Bay (2026)", f: "2026 · Série", c: "tv_shows" },
    { t: "Spider-Noir", f: "2026 · Série", c: "tv_shows" },
    { t: "Rafa", f: "2026 · Série", c: "tv_shows" },
    { t: "Prescott", f: "2026 · Série", c: "tv_shows" },
    { t: "Lord of the Flies", f: "2026 · Série", c: "tv_shows" },
    { t: "Achtsam Morden", f: "2024 · Série", c: "tv_shows" },
    { t: "Gourou", f: "2026 · Film", c: "movies" },
    { t: "Les Griffes de la nuit", f: "2010 · Film", c: "movies" },
    { t: "RoboCop", f: "2014 · Film", c: "movies" },
    { t: "Superman", f: "2025 · Film", c: "movies" },
    {
      t: "Astérix Le Domaine des dieux",
      f: "2014 · Film",
      c: "movies_animation",
    },
    {
      t: "Bob l'éponge - Le film Un héros sort de l'eau",
      f: "2015 · Film",
      c: "movies_animation",
    },
    {
      t: "L'Âge de glace 4 La dérive des continents",
      f: "2012 · Film",
      c: "movies_animation",
    },
    { t: "La Petite Sirène", f: "2023 · Film", c: "movies_animation" },
    { t: "Le Livre de la jungle", f: "2016 · Film", c: "movies_animation" },
    { t: "Le Temple du Soleil", f: "1992 · Film", c: "movies_animation" },
    { t: "Les Schtroumpfs", f: "2025 · Film", c: "movies_animation" },
    { t: "Lilo & Stitch", f: "2025 · Film", c: "movies_animation" },
    { t: "Scrubs", f: "2001 · Série", c: "tv_shows" },
    { t: "Mulan", f: "2020 · Film", c: "movies" },
    { t: "Le Grinch", f: "2018 · Film", c: "movies_animation" },
    { t: "Pinocchio", f: "2022 · Film", c: "movies_animation" },
    { t: "The Staircase", f: "2022 · Série", c: "tv_shows" },
    { t: "De si remarquables créatures", f: "2026 · Film", c: "movies" },
    { t: "Projet Dernière Chance", f: "2026 · Film", c: "movies" },
    {
      t: "Le Bus Les Bleus en grève",
      f: "2026 · Film",
      c: "movies_documentary",
    },
    { t: "Qui a poussé Mélodie", f: "2025 · Série", c: "tv_shows" },
    { t: "The Killing", f: "2010 · Série", c: "tv_shows" },
    { t: "The Boroughs", f: "2026 · Série", c: "tv_shows" },
    { t: "Stranger Things Tales from '85", f: "2026 · Série", c: "tv_shows" },
    { t: "Maximum Pleasure Guaranteed", f: "2026 · Série", c: "tv_shows" },
    { t: "Imperfect Women", f: "2026 · Série", c: "tv_shows" },
    { t: "Dexter New Blood", f: "2021 · Série", c: "tv_shows" },
    { t: "I Origins", f: "2014 · Film", c: "movies" },
    { t: "Dossier 137", f: "2025 · Film", c: "movies" },
    { t: "Monk", f: "2002 · Série", c: "tv_shows" },
    { t: "Squid Game", f: "2021 · Série", c: "tv_shows" },
    { t: "Andrew The Problem Prince", f: "2023 · Série", c: "tv_shows" },
    { t: "Good Luck, Have Fun, Don't Die", f: "2026 · Film", c: "movies" },
    { t: "Une affaire d'honneur", f: "2023 · Film", c: "movies" },
    { t: "Une vie", f: "2023 · Film", c: "movies" },
    { t: "Vermines", f: "2023 · Film", c: "movies" },
    { t: "Chérie, j'ai agrandi le bébé", f: "1992 · Film", c: "movies" },
    { t: "Chérie, j'ai rétréci les gosses", f: "1989 · Film", c: "movies" },
    { t: "Comme un prince", f: "2024 · Film", c: "movies" },
    { t: "Daaaaaalí !", f: "2024 · Film", c: "movies" },
    { t: "Die Hart Die Harter", f: "2024 · Film", c: "movies" },
    { t: "Dune Deuxième Partie", f: "2024 · Film", c: "movies" },
    { t: "Breathe", f: "2024 · Film", c: "movies" },
    { t: "Mothers' Instinct", f: "2024 · Film", c: "movies" },
    { t: "Sentinel", f: "2023 · Film", c: "movies" },
    { t: "Ultraman Rising", f: "2024 · Film", c: "movies_animation" },
    { t: "22.11.63", f: "2016 · Série", c: "tv_shows" },
    { t: "3%", f: "2016 · Série", c: "tv_shows" },
    { t: "Anger Management", f: "2012 · Série", c: "tv_shows" },
    { t: "Band of Brothers", f: "2001 · Série", c: "tv_shows" },
    { t: "Battlestar Galactica", f: "2004 · Série", c: "tv_shows" },
    { t: "Beacon 23", f: "2023 · Série", c: "tv_shows" },
    { t: "Better Call Saul", f: "2014 · Série", c: "tv_shows" },
    { t: "Bodkin", f: "2024 · Série", c: "tv_shows" },
    { t: "Broadchurch", f: "2013 · Série", c: "tv_shows" },
    { t: "Broute 24.", f: "2024 · Série", c: "tv_shows" },
    { t: "Fiasco", f: "2024 · Série", c: "tv_shows" },
    { t: "Furies", f: "2024 · Série", c: "tv_shows" },
    { t: "Game of Thrones", f: "2011 · Série", c: "tv_shows" },
    { t: "Go On", f: "2012 · Série", c: "tv_shows" },
    {
      t: "Heeramandi Les diamants de la cour",
      f: "2024 · Série",
      c: "tv_shows",
    },
    { t: "Hero Corp", f: "2008 · Série", c: "tv_shows" },
    { t: "Joey", f: "2004 · Série", c: "tv_shows" },
    { t: "Kaboul Kitchen", f: "2012 · Série", c: "tv_shows" },
    { t: "Kevin Can Wait", f: "2016 · Série", c: "tv_shows" },
    { t: "La Brea", f: "2021 · Série", c: "tv_shows" },
    { t: "La cape et l'épée", f: "2000 · Série", c: "tv_shows" },
    { t: "La quatrième dimension", f: "1959 · Série", c: "tv_shows" },
    { t: "La Vie de famille", f: "1989 · Série", c: "tv_shows" },
    { t: "Le Caméléon", f: "1996 · Série", c: "tv_shows" },
    { t: "Le Régime", f: "2024 · Série", c: "tv_shows" },
    { t: "Le Visiteur du Futur", f: "2009 · Série", c: "tv_shows" },
    { t: "Les Papillons noirs", f: "2022 · Série", c: "tv_shows" },
    { t: "MacGyver", f: "1985 · Série", c: "tv_shows" },
    { t: "Man With A Plan", f: "2016 · Série", c: "tv_shows" },
    { t: "Manhunt", f: "2024 · Série", c: "tv_shows" },
    { t: "Misfits", f: "2009 · Série", c: "tv_shows" },
    { t: "Mon petit renne", f: "2024 · Série", c: "tv_shows" },
    { t: "Mr. & Mrs. Smith", f: "2024 · Série", c: "tv_shows" },
    { t: "Mr. Bean", f: "1990 · Série", c: "tv_shows" },
    { t: "Only Murders in the Building", f: "2021 · Série", c: "tv_shows" },
    { t: "Rapa", f: "2022 · Série", c: "tv_shows" },
    { t: "Reine rouge", f: "2024 · Série", c: "tv_shows" },
    { t: "Ripley", f: "2024 · Série", c: "tv_shows" },
    { t: "Shameless", f: "2004 · Série", c: "tv_shows" },
    { t: "Six Feet Under", f: "2001 · Série", c: "tv_shows" },
    { t: "Stargate Atlantis", f: "2004 · Série", c: "tv_shows" },
    { t: "Stargate SG-1", f: "1997 · Série", c: "tv_shows" },
    { t: "Stargate Universe", f: "2009 · Série", c: "tv_shows" },
    { t: "Sugar", f: "2024 · Série", c: "tv_shows" },
    { t: "Terminal", f: "2024 · Série", c: "tv_shows" },
    { t: "The Acolyte", f: "2024 · Série", c: "tv_shows" },
    { t: "The Big Cigar", f: "2024 · Série", c: "tv_shows" },
    { t: "The Drew Carey Show", f: "1995 · Série", c: "tv_shows" },
    { t: "The King of Queens", f: "1998 · Série", c: "tv_shows" },
    { t: "The Last Man on Earth", f: "2015 · Série", c: "tv_shows" },
    { t: "The Lost Room", f: "2006 · Série", c: "tv_shows" },
    { t: "The Michael J. Fox Show", f: "2013 · Série", c: "tv_shows" },
    { t: "The OA", f: "2016 · Série", c: "tv_shows" },
    { t: "The Odd Couple", f: "2015 · Série", c: "tv_shows" },
    { t: "The Wrong Mans", f: "2013 · Série", c: "tv_shows" },
    { t: "Time Traveling Bong", f: "2016 · Série", c: "tv_shows" },
    { t: "Twin Peaks", f: "1990 · Série", c: "tv_shows" },
    { t: "Un meurtre est-il facile", f: "2023 · Série", c: "tv_shows" },
    { t: "Unbelievable", f: "2019 · Série", c: "tv_shows" },
    { t: "United States of Tara", f: "2009 · Série", c: "tv_shows" },
    { t: "Voilà", f: "1997 · Série", c: "tv_shows" },
    { t: "X-Files  Aux frontières du réel", f: "1993 · Série", c: "tv_shows" },
    { t: "Caïn", f: "2012 · Série", c: "tv_shows" },
    { t: "Chernobyl", f: "2019 · Série", c: "tv_shows" },
    { t: "Childhood's End", f: "2015 · Série", c: "tv_shows" },
    { t: "Coupling - Six Sexy", f: "2000 · Série", c: "tv_shows" },
    { t: "Dark Matter", f: "2024 · Série", c: "tv_shows" },
    { t: "Des gens bien ordinaires", f: "2022 · Série", c: "tv_shows" },
    { t: "Doctor Who", f: "2005 · Série", c: "tv_shows" },
    { t: "Doctor Who", f: "2023 · Série", c: "tv_shows" },
    { t: "Eric", f: "2024 · Série", c: "tv_shows" },
    { t: "Eux", f: "2021 · Série", c: "tv_shows" },
    { t: "Fallout", f: "2024 · Série", c: "tv_shows" },
    { t: "Family Business", f: "2019 · Série", c: "tv_shows" },
    { t: "Caméra Café", f: "2001 · Série", c: "tv_shows" },
    { t: "Farscape", f: "1999 · Série", c: "tv_shows" },
    { t: "That '70s Show", f: "1998 · Série", c: "tv_shows" },
    {
      t: "L'Odyssée interstellaire",
      f: "2018 · Série",
      c: "tv_shows_documentary",
    },
    { t: "Zero Day", f: "2025 · Série", c: "tv_shows" },
    { t: "Ça Bienvenue à Derry", f: "2025 · Série", c: "tv_shows" },
    { t: "The Big Bang Theory", f: "2007 · Série", c: "tv_shows" },
    { t: "The Big Door Prize", f: "2023 · Série", c: "tv_shows" },
    { t: "The Bridge", f: "2011 · Série", c: "tv_shows" },
    { t: "The Crowded Room", f: "2023 · Série", c: "tv_shows" },
    { t: "The Deal", f: "2025 · Série", c: "tv_shows" },
    { t: "The Fall", f: "2013 · Série", c: "tv_shows" },
    { t: "The Flight Attendant", f: "2020 · Série", c: "tv_shows" },
    { t: "The Inbetweeners", f: "2008 · Série", c: "tv_shows" },
    { t: "The Island", f: "2025 · Série", c: "tv_shows" },
    { t: "The Keepers", f: "2017 · Série", c: "tv_shows" },
    { t: "Derrière la façade", f: "2024 · Série", c: "tv_shows" },
    { t: "Des gens bien", f: "2022 · Série", c: "tv_shows" },
    { t: "Des vivants", f: "2025 · Série", c: "tv_shows" },
    { t: "Dexter", f: "2006 · Série", c: "tv_shows" },
    { t: "Dexter Les Origines", f: "2024 · Série", c: "tv_shows" },
    { t: "Dexter Resurrection", f: "2025 · Série", c: "tv_shows" },
    { t: "Dope Girls", f: "2025 · Série", c: "tv_shows" },
    { t: "Dope Thief", f: "2025 · Série", c: "tv_shows" },
    { t: "Douglas Is Cancelled", f: "2024 · Série", c: "tv_shows" },
    { t: "Down Cemetery Road", f: "2025 · Série", c: "tv_shows" },
    { t: "Dune Prophecy", f: "2024 · Série", c: "tv_shows" },
    { t: "Défendre Jacob", f: "2020 · Série", c: "tv_shows" },
    { t: "Désenchantées", f: "2025 · Série", c: "tv_shows" },
    { t: "Earl", f: "2005 · Série", c: "tv_shows" },
    { t: "Empathie", f: "2025 · Série", c: "tv_shows" },
    { t: "Engrenages", f: "2005 · Série", c: "tv_shows" },
    { t: "Enterrement de vie de garçon", f: "2024 · Série", c: "tv_shows" },
    { t: "Espion à l'ancienne", f: "2024 · Série", c: "tv_shows" },
    { t: "Esterno Notte", f: "2022 · Série", c: "tv_shows" },
    { t: "Extra-Lucide", f: "2025 · Série", c: "tv_shows" },
    { t: "Extrapolations", f: "2023 · Série", c: "tv_shows" },
    { t: "Flashback", f: "2025 · Série", c: "tv_shows" },
    { t: "Florida Man", f: "2023 · Série", c: "tv_shows" },
    {
      t: "Fonction Juré présente Le Séminaire d'Entreprise",
      f: "2026 · Série",
      c: "tv_shows",
    },
    { t: "For All Mankind", f: "2019 · Série", c: "tv_shows" },
    { t: "Foundation", f: "2021 · Série", c: "tv_shows" },
    { t: "La Meilleure Version de moi-même", f: "2021 · Série", c: "tv_shows" },
    { t: "La mer de la Tranquillité", f: "2021 · Série", c: "tv_shows" },
    {
      t: "La nuit où Laurier Gaudreault s’est réveillé",
      f: "2022 · Série",
      c: "tv_shows",
    },
    { t: "La Réalité en face", f: "2021 · Série", c: "tv_shows" },
    { t: "La Résidence", f: "2025 · Série", c: "tv_shows" },
    { t: "La Voisine danoise", f: "2025 · Série", c: "tv_shows" },
    { t: "Landman", f: "2024 · Série", c: "tv_shows" },
    { t: "Le Crime à la racine", f: "2025 · Série", c: "tv_shows" },
    { t: "Le Garçon et l'Univers", f: "2024 · Série", c: "tv_shows" },
    { t: "Le Livre de Boba Fett", f: "2021 · Série", c: "tv_shows" },
    { t: "Le Maître du Haut Château", f: "2015 · Série", c: "tv_shows" },
    { t: "Le Problème à 3 corps", f: "2024 · Série", c: "tv_shows" },
    { t: "Le Président foudroyé", f: "2025 · Série", c: "tv_shows" },
    { t: "Blue Lights", f: "2023 · Série", c: "tv_shows" },
    { t: "Bodies", f: "2023 · Série", c: "tv_shows" },
    { t: "Boglands, enquête en terre noire", f: "2024 · Série", c: "tv_shows" },
    { t: "Boots", f: "2025 · Série", c: "tv_shows" },
    { t: "bref.", f: "2011 · Série", c: "tv_shows" },
    { t: "Cassandra", f: "2025 · Série", c: "tv_shows" },
    { t: "Casting(s)", f: "2013 · Série", c: "tv_shows" },
    { t: "Cent ans de solitude", f: "2024 · Série", c: "tv_shows" },
    { t: "Chacal", f: "2024 · Série", c: "tv_shows" },
    { t: "Channel Zero", f: "2016 · Série", c: "tv_shows" },
    { t: "Chief of War", f: "2025 · Série", c: "tv_shows" },
    { t: "Chère petite", f: "2023 · Série", c: "tv_shows" },
    { t: "Citoyens clandestins", f: "2024 · Série", c: "tv_shows" },
    { t: "City on Fire", f: "2023 · Série", c: "tv_shows" },
    { t: "Arcane", f: "2021 · Série", c: "tv_shows_animation" },
    { t: "Archer", f: "2009 · Série", c: "tv_shows_animation" },
    { t: "Famille Pirate", f: "1999 · Série", c: "anime" },
    { t: "Hé, oua-oua", f: "2014 · Série", c: "anime" },
    { t: "Animal Crackers", f: "1997 · Série", c: "anime" },
    { t: "Batman, la série animée", f: "1992 · Série", c: "anime" },
    { t: "Bob l'éponge", f: "1999 · Série", c: "anime" },
    { t: "BoJack Horseman", f: "2014 · Série", c: "anime" },
    { t: "City Hunter", f: "1985 · Série", c: "anime" },
    { t: "Death Note", f: "2006 · Série", c: "anime" },
    {
      t: "Disney, les courts-métrages d'animation",
      f: "1921 · Série",
      c: "anime",
    },
    { t: "Les aventures de Tintin", f: "1991 · Série", c: "anime" },
    { t: "Les castors allumés", f: "1997 · Série", c: "anime" },
    { t: "Les Contes de la rue Broca", f: "1969 · Série", c: "anime" },
    { t: "Les Entrechats", f: "1985 · Série", c: "anime" },
    { t: "Les histoires du Père Castor", f: "1993 · Série", c: "anime" },
    {
      t: "Hamas, la fabrique d'un monstre",
      f: "2024 · Film",
      c: "movies_documentary",
    },
    { t: "La Citadelle assiégée", f: "2006 · Film", c: "movies_documentary" },
    { t: "La Famille Suricate", f: "2008 · Film", c: "movies_documentary" },
    { t: "La Marche de l'empereur", f: "2005 · Film", c: "movies_documentary" },
    { t: "Le Jeu de la mort", f: "2010 · Film", c: "movies_documentary" },
    {
      t: "Matthew Perry Not just Friends",
      f: "2023 · Film",
      c: "movies_documentary",
    },
    { t: "Poulet Frites", f: "2022 · Film", c: "movies_documentary" },
    {
      t: "STILL la vie de Michael J. Fox",
      f: "2023 · Film",
      c: "movies_documentary",
    },
    { t: "Un Jour Au Haram", f: "2017 · Film", c: "movies_documentary" },
    {
      t: "Un pays qui se tient sage",
      f: "2020 · Film",
      c: "movies_documentary",
    },
    {
      t: "À la recherche de Harry L'art derrière la magie",
      f: "2026 · Film",
      c: "movies_documentary",
    },
    { t: "Ahmed Sylla - Origami", f: "2025 · Film", c: "standup" },
    {
      t: "Arnaud Tsamere 2 mariages & 1 enterrement",
      f: "2024 · Film",
      c: "standup",
    },
    { t: "Arnaud Tsamère - Chose Promise", f: "2013 · Film", c: "standup" },
    {
      t: "Arnaud Tsamère - Confidences sur pas mal de trucs plus ou moins confidentiels",
      f: "2016 · Film",
      c: "standup",
    },
    { t: "Artus - Saignant à point", f: "2015 · Film", c: "standup" },
    { t: "Aymeric Lompret Tant Pis", f: "2023 · Film", c: "standup" },
    {
      t: "Jérémy Ferrari - Anesthésie Générale",
      f: "2024 · Film",
      c: "standup",
    },
    {
      t: "Jérémy Ferrari - Hallelujah Bordel !",
      f: "2013 · Film",
      c: "standup",
    },
    {
      t: "Jérémy Ferrari - Vends 2 pièces à Beyrouth",
      f: "2018 · Film",
      c: "standup",
    },
    {
      t: "Jérémy Ferrari Emporté par la Fougue",
      f: "2018 · Film",
      c: "standup",
    },
    {
      t: "Jérôme Commandeur - Toujours en douceur",
      f: "2022 · Film",
      c: "standup",
    },
    { t: "Kyan Khojandi Pulsions", f: "2019 · Film", c: "standup" },
    { t: "Kyan Khojandi Une bonne soirée", f: "2023 · Film", c: "standup" },
    { t: "L'Exoconference", f: "2014 · Film", c: "standup" },
    { t: "Le Discours", f: "2025 · Film", c: "theater" },
    { t: "Les Bonobos", f: "2012 · Film", c: "theater" },
    { t: "L’effet miroir", f: "2024 · Film", c: "theater" },
    { t: "Sans filtre", f: "2015 · Film", c: "theater" },
    {
      t: "Sexe, magouilles et culture générale",
      f: "2001 · Film",
      c: "theater",
    },
    { t: "TOC TOC", f: "2005 · Film", c: "theater" },
    { t: "Un point c'est tout !", f: "2009 · Film", c: "theater" },
    { t: "Mon voisin nu", f: "2024 · Film", c: "theater" },
    {
      t: "Harry Potter, les secrets enfin révélés",
      f: "2024 · Série",
      c: "tv_programs",
    },
    { t: "Loups-garous", f: "2024 · Série", c: "tv_programs" },
    { t: "Nus et culottés", f: "2012 · Série", c: "tv_programs" },
    { t: "Les Minikeums", f: "1993 · Série", c: "tv_programs" },
    { t: "Aller simple la téléréalité", f: "2025 · Série", c: "tv_programs" },
    { t: "Au bout c'est la mer", f: "2018 · Série", c: "tv_programs" },
    { t: "Burger Quiz", f: "2001 · Série", c: "tv_programs" },
    { t: "Cash Investigation", f: "2012 · Série", c: "tv_programs" },
    { t: "Cauchemar en cuisine", f: "2011 · Série", c: "tv_programs" },
    { t: "Club Dorothée", f: "1987 · Série", c: "tv_programs" },
    { t: "Comedy Class", f: "2024 · Série", c: "tv_programs" },
    {
      t: "Des trains pas comme les autres",
      f: "2011 · Série",
      c: "tv_programs",
    },
    {
      t: "J'irai dormir chez les Gaulois",
      f: "2023 · Série",
      c: "tv_programs",
    },
    {
      t: "Astérix & Obélix Le Combat des chefs",
      f: "2025 · Série",
      c: "tv_shows_animation",
    },
    { t: "Babar", f: "1968 · Série", c: "tv_shows_animation" },
    { t: "Bluey", f: "2016 · Série", c: "tv_shows_animation" },
    { t: "Caillou", f: "1998 · Série", c: "tv_shows_animation" },
    { t: "Captain Fall", f: "2023 · Série", c: "tv_shows_animation" },
    { t: "Ce monde ne m'aura pas", f: "2023 · Série", c: "tv_shows_animation" },
    { t: "Close Enough", f: "2020 · Série", c: "tv_shows_animation" },
    { t: "Common Side Effects", f: "2025 · Série", c: "tv_shows_animation" },
    { t: "Couacs en vrac", f: "1996 · Série", c: "tv_shows_animation" },
    { t: "Cédric", f: "2001 · Série", c: "tv_shows_animation" },
    { t: "Didou", f: "2006 · Série", c: "tv_shows_animation" },
    { t: "Dora l'exploratrice", f: "2000 · Série", c: "tv_shows_animation" },
    {
      t: "John Lennon Murder Without a Trial",
      f: "2024 · Série",
      c: "tv_shows_documentary",
    },
    { t: "Parole de tueur", f: "2019 · Série", c: "tv_shows_documentary" },
    { t: "Antigang", f: "2023 · Série", c: "tv_shows_documentary" },
    {
      t: "C'était la guerre d'Algérie",
      f: "2022 · Série",
      c: "tv_shows_documentary",
    },
    {
      t: "Cold Case Les meurtres au Tylenol",
      f: "2025 · Série",
      c: "tv_shows_documentary",
    },
    {
      t: "De rockstar à tueur Le cas Cantat",
      f: "2025 · Série",
      c: "tv_shows_documentary",
    },
    {
      t: "Don't Fk with Cats Un tueur trop viral",
      f: "2019 · Série",
      c: "tv_shows_documentary",
    },
    {
      t: "FAKE YOU! Une vraie histoire de faux",
      f: "2026 · Série",
      c: "tv_shows_documentary",
    },
    { t: "Hantises", f: "2025 · Série", c: "tv_shows_documentary" },
    { t: "High School Radical", f: "2025 · Série", c: "tv_shows_documentary" },
    {
      t: "Jinx la vie et les morts de Robert Durst",
      f: "2015 · Série",
      c: "tv_shows_documentary",
    },
    {
      t: "Kerviel Un trader, 50 milliards",
      f: "2024 · Série",
      c: "tv_shows_documentary",
    },
    {
      t: "L'affaire du juge Delisle",
      f: "2025 · Série",
      c: "tv_shows_documentary",
    },
  ];

  /* Categories are the REAL storage ones (categories.json5 → disk folders),
     with their counts read from library.db. « Animation » and «
     Documentaires » merge their film/series variants: storage is by nature,
     not by medium. The total is 1,861 and it adds up — a filter whose parts
     do not sum to the whole is a filter that lies. */


  const INCOMPLETE = [
    { t: "SAV des émissions", o: 12, a: 71, y: 2005 },
    { t: "Les Animaniacs", o: 110, a: 230, y: 1993 },
    { t: "La cour de récré", o: 54, a: 100, y: 1997 },
    { t: "Les Zinzins de l'Espace", o: 78, a: 104, y: 1997 },
    { t: "Les aventures de Tintin", o: 21, a: 39, y: 1991 },
    { t: "Earl", o: 90, a: 96, y: 2005 },
    { t: "Stargate SG-1", o: 211, a: 214, y: 1997 },
    { t: "Parks and Recreation", o: 122, a: 125, y: 2009 },
    { t: "Regular Show", o: 204, a: 207, y: 2010 },
    { t: "Friends", o: 234, a: 236, y: 1994 },
    { t: "Monk", o: 60, a: 61, y: 2002 },
    { t: "Farscape", o: 89, a: 90, y: 1999 },
  ];

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
  const REASON_LABEL = {
    below_threshold: "Confiance faible",
    mid_band: "Confiance moyenne",
    ambiguous: "Candidats ambigus",
    manual: "Envoi manuel",
  };
  const REASON_TONE = {
    below_threshold: "danger",
    mid_band: "warning",
    ambiguous: "info",
    manual: "neutral",
  };
  const REASON_DETAIL = {
    below_threshold:
      "Aucun candidat n'atteignait le seuil de confiance automatique.",
    mid_band:
      "Le meilleur candidat était en confiance moyenne — une validation humaine est demandée.",
    ambiguous:
      "Plusieurs candidats étaient trop proches pour trancher automatiquement.",
    manual: "Dossier envoyé à la main depuis la zone de préparation.",
  };
  /* `dismissed` and `superseded` are spelled out: the raw words say what the
     code did, not what happened to the folder. */
  const DECISION_STATE = {
    resolved: ["success", "Réglée"],
    dismissed: ["neutral", "Laissée telle quelle"],
    superseded: ["info", "Remplacée depuis"],
  };
  const DECISION_STATE_DETAIL = {
    resolved: "Un candidat a été choisi, et un re-scrapage ciblé a été lancé.",
    dismissed:
      "Le dossier a été laissé tel quel : le résultat automatique est conservé, rien n'a été re-scrapé.",
    superseded:
      "Une version plus récente du dossier a été re-scrapée depuis. Cette décision ne veut plus rien dire.",
  };
  const VIA_LABEL = {
    pick: "choisi dans la liste",
    search_override: "trouvé par une recherche manuelle",
  };

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

  /* ── MAINTENANCE ──────────────────────────────────────────────────────
     The 26 `library-*` commands the engine really registers, read from
     `web/maintenance/registry.py`: their French title, their category, and —
     the field that decides how each is drawn — their RISK.

     One navigates by what one wants to DO, the same decision the settings
     already carry: six rubrics, never a flat list of twenty-six lines whose
     order means nothing. The engine's command name sits under each label in
     the mono face, because that is what one needs when reading a log.

     Risk is not decoration. Eight of these read and change nothing, twelve
     write and can be undone, and six DELETE. A list that draws them alike
     asks the operator to remember which is which, and the one they will
     forget is the one that matters. */
  const MAINT_TOPICS = [
    {
      id: "query",
      t: "Regarder",
      s: "Lire l'état de la médiathèque. Rien n'est modifié.",
    },
    {
      id: "scan",
      t: "Indexer",
      s: "Parcourir les disques et remettre l'index en accord avec eux.",
    },
    {
      id: "repair",
      t: "Vérifier et réparer",
      s: "Contrôler les fichiers, et vider la file de réparation.",
    },
    {
      id: "clean",
      t: "Nettoyer les disques",
      s: "Retirer ce qui n'a rien à y faire. Ces commandes suppriment.",
    },
    {
      id: "fix",
      t: "Corriger",
      s: "Redresser une donnée fausse : un lien, un compte, un identifiant.",
    },
    {
      id: "analyze",
      t: "Analyser",
      s: "Comprendre ce que la médiathèque contient, et ce qui lui manque.",
    },
  ];


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

  /* WHAT A FAULT LOOKS LIKE — and it is SIMULATED, which the screen says.

     Everything on this machine is green, and a screen that can only be green
     cannot be judged: the operator has no way of knowing what they would see
     the day something stops. So a named state replays a fault, in the same
     spirit as the dense « charge » scenario — declared, never passed off as
     read from the system.

     A stopped SERVICE and an overdue SCHEDULER are two different sentences,
     and only the service half is still here. A service is late by nothing: it
     is up or it is not. The scheduler twin is derived beside the list it
     alters, in `features/system/fault.ts`, because the healthy list it maps
     over comes from the mock layer and no longer from this file. */
  const SERVICES_PANNE = SERVICES.map((service, rang) =>
    rang === 2
      ? {
          ...service,
          ton: "alert",
          v: "hors ligne",
          s: "arrêté depuis 14 h 02 · sortie en erreur",
        }
      : service,
  );

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
  /* WHAT A SEARCH TURNED UP, and WHAT A RELEASE PICKER LISTS, read from the
     layer. Both were fixtures here and left at L09; both are indexed into from
     click handlers that cannot await. They go with the delegation at L13. */
  function searchResults() {
    return seam.searchResults?.() ?? { total: 0, shown: 0, results: [] };
  }

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

  function actionTake(title) {
    /* Same as the two above. */
    seam.queueActions?.take(title);
    render();
    toast(`« ${baseTitle(title)} » récupéré — suivez-le dans « En vol ».`);
  }

  /* Agreeing with the machine. The automatic result stands, nothing is
     re-scraped — and the folder LEAVES the queue, because the operator has
     answered. A queue that kept what has been answered would grow forever and
     stop meaning « what is waiting for me ». */
  /* A folder awaiting a decision shows up on TWO lists — « À traiter » on the
     acquisition side and « Ça coince » in Arrivées — and an answer has to
     reach whichever one it is on. Looking in only one of them is why
     « Résoudre → » on an acquisition card used to change nothing at all: the
     button was there, the screen opened, the choice was made, and the item
     stayed exactly where it was. */

  /* Agreeing with the machine. The automatic result stands, nothing is
     re-scraped — and the folder LEAVES the queue, because the operator has
     answered. A queue that kept what has been answered would grow forever and
     stop meaning « what is waiting for me ». */
  function actionLeave(title) {
    /* THE MOVE IS THE LAYER'S SINCE L09, and what stays here is the sentence
       the operator reads. The folder leaving one queue and joining another is
       server state; keeping a copy of it in `world` beside the cache the
       surfaces read would be two truths about one queue. `leaveQueue` went with
       it — the layer walks the same three lists, in the same order, and it says
       so in its own words. */
    if (!seam.queueActions?.leave(title)) return false;
    render();
    toast(
      `« ${title} » laissé tel quel — le résultat automatique est conservé, rien n'a été re-scrapé.`,
    );
    return true;
  }

  function actionResolve(title, choice, picked) {
    /* Same as `actionLeave`: the move is the layer's, the sentence is this
       function's. A PICK on the candidate card waits and answers an undo. */
    const undo = seam.queueActions?.[picked ? "pick" : "resolve"](title, choice);
    render();
    const message = `Identifié comme « ${choice ?? title} » — le pipeline reprend jusqu'à la médiathèque.`;
    if (typeof undo === "function") toastUndo(message, undo); else toast(message);
  }

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
  const RESOLUTIONS = ["720p", "1080p", "2160p"];
  const AUDIOS = [
    ["VF", "Piste française (VF, VFF, VFQ, TRUEFRENCH)"],
    ["VOSTFR", "Sous-titres français"],
    ["VO", "Version originale"],
  ];

  /* Read-only reference data + pure rendering helpers a migrated route
     component reuses VERBATIM rather than re-declaring — a re-declaration
     would drift the day one of these changes here. None of it is engine
     STATE (never mutated by an action), so exposing it does not bypass the
     store's reactivity contract; it is exposed once, at definition time,
     well before the deferred module script (shell.tsx) runs. */
  window.__referentiel = {
    RESOLUTIONS,
    AUDIOS,
    icons,
    baseTitle,
    addVerb,
    render,
    /* What the Arrivées page draws. `PIPELINE` is the run's own data, read and never written; the three
       `derived` verbs answer what is stuck, moving and settled, which depends
       on the scenario and so cannot be a frozen value. */
    /* What the Acquisition page draws. The follow DESCRIPTORS and their
       vocabulary (`stFraction`, `stLabel`, `gridBadge`, `ST_TONE`, `URGENCY`,
       `GROUPS`) are the page's own language; `cadenceFR` and
       `nextSearchFR` turn a cron expression into a sentence — and the
       page says out loud that the raw expression is a defect it inherited. The
       SUGGESTION machinery is NOT here: `#sugitems`, `#sugload` and
       `.deckbody` stay the fragment's to fill, because the deck's gesture
       mutates its own DOM and a replaced node cannot animate. */
    stFraction,
    stLabel,
    gridBadge,
    cadenceFR,
    nextSearchFR,
    ST_TONE,
    URGENCY,
    GROUPS,
    CADENCE_CRON,
    /* The account the server really has, and the escaper the fragment's own
       emitters use — a migrated page that builds a fragment of markup has to
       escape exactly what the legacy escaped. */
    ACCOUNT,
    escapeHtml,
    /* The suggestion machinery, called by the page AFTER React has drawn its
       containers. `render()` calls these too, for as long as a legacy page can
       hold them — but it calls them BEFORE the shell has drawn, so a migrated
       page asks again from an effect, exactly as it asks for the selection bar
       to be repainted. */
    /* Published for the MEASUREMENT of the deck's gesture: a rule drives the
       two halves the way the swipe handler drives them, and reads what the
       animation is doing one frame later. */
    /* The selection bar stays the FRAGMENT's: it lives in `#device`, React
       never draws it, and the component only asks for it to be repainted after
       a render — the legacy owns that node from creation to removal, which is
       what keeps two worlds from writing one element. */
    paintSelBar,
    /* How many titles the prototype really carries, which the end mark says
       out loud rather than letting the end of the list contradict the « of
       1 861 » counter. A thin arrow, like `derivedStuck`: the value is the
       WORLD's and stays live. */
    INCOMPLETE,
    /* A GETTER: `LIB_PAGE` is a `const` declared further down this same script,
       so a plain shorthand would hit the temporal dead zone the instant this
       literal is built — the same trap `TODAY` is published
       around. */
    get LIB_PAGE() {
      return LIB_PAGE;
    },
    SERVICES,
    SERVICES_PANNE,
    EXECUTIONS,
    DISKS,
    INDEX,
    DEPENDENCIES,
    ERRORS,
    /* What the Maintenance page draws. The command PANEL has left — it is
       `features/maintenance/panel-action.ts` now, reached through
       `panel.produce("action", id)` — and the risk vocabulary went with it,
       which is why `RISQUES` is no longer published from here at all. */
    MAINT_TOPICS,
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
    EP_LABEL,
    dateFR,
    // TODAY is declared with `const` further down this same script, past this
    // literal's evaluation point — a plain shorthand reference would hit the
    // temporal dead zone the instant this object is built. A getter defers
    // the read to first access, by which time the whole script has run.
    get TODAY() {
      return TODAY;
    },
    svgIcon,
    settingId,
    typedValue,
    // The arbitration flow's LABELS, which are the interface's own words and
    // were never server state — the register classifies them `interface`, and
    // they stay exactly where they are.
    REASON_LABEL,
    REASON_TONE,
    REASON_DETAIL,
    DECISION_STATE,
    DECISION_STATE_DETAIL,
    VIA_LABEL,
    // The flow's own lookup. Its DATA left at L09 — the surface reads
    // `/api/decisions/` and `PENDING_DECISIONS` is deleted — and this answer
    // stays because the engine's « Passer à la suivante » branch asks it
    // synchronously from a click handler. It reads the cache through
    // `seam.pendingDecisions` and goes with that branch at L13.
    decisionPending,
    // Thin arrows over `derived.blocked` / `derived.stuck` — `derived` itself
    // is already initialized above this literal, but the wrapper still earns
    // its keep: it publishes a STABLE function reference while the value each
    // call returns stays live against the scenario switch inside `derived`.
    actionResolve,
    actionLeave,
    actionTake,
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
  function sortLabel() {
    /* THE NAMES ARE THE FEATURE'S — `features/library/sorting.ts`, read
       through `engine/seams.ts` rather than a copy kept here, the way a
       setting's label is read from the settings feature. */
    const named = seam.sortWays();
    return named[currentState().sortKey][
      currentState().sortReversed ? "inverse" : "normal"
    ];
  }
  const LIB_PAGE = 24;

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

  /* THE SELECTION BAR IS NOT DRAWN HERE ANY MORE. It was created per open and
     appended to `#device`; it is `features/library/selection-bar.tsx` now,
     rendered into the frame's bottom slot and reading the same store fields.
     This function stayed a VERB the delegation and the drivers still say —
     `paintSelBar()` after a tile toggles — so that moving the drawing did not
     take away the vocabulary. It draws nothing: the store bump beside every
     call site is what the component listens to. It goes with the library's
     verbs at L19. */
  function paintSelBar() {}

  /* Reads the panel an element addresses.
     Split on the FIRST colon only: titles carry their own — « Dexter:
     Resurrection » would otherwise address a panel for « Dexter ». */
  function refPanel(element) {
    // `panelName`, not `panel`: the seam the engine calls to OPEN a panel is
    // named `panel`, and a local of the same name would shadow it silently
    // inside this function. The value here is the attribute's text.
    const panelName = element.dataset.panel;
    const indexOf = panelName.indexOf(":");
    return {
      genre: panelName.slice(0, indexOf),
      ref: panelName.slice(indexOf + 1),
    };
  }

  /* Opens the panel an element addresses. One entry point, so a surface that
     wants a panel states WHICH one and never how to build it. */
  function openPanel(element) {
    const { genre, ref } = refPanel(element);
    if (genre === "sug") panel.produce("suggestion", ref);
    else if (genre === "add") panel.produce("add", ref);
    else panel.produce("follow", ref);
  }

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
    onPress: openPanel,
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
     `data-*` this file's own delegation still reads.

     `closeDlg` stays a VERB the producers say. */
  function closeDlg() {
    seam.dialog?.close();
  }

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

     The verbs stay verbs. `openDrawer()` writes the store and pushes the
     layer's own entry, exactly as it did — a conversion moves the drawing. */
  function openDrawer() {
    store.write({ drawerOpen: true });
    try {
      bridge.pushLayer("drawer");
    } catch (error) {}
  }
  function closeDrawer(pop) {
    seam.layers?.close("drawer", pop);
  }

  /* THE APPEARANCE IS NOT THIS FILE'S ANY MORE. The three states, the stored
     choice, the live media listener and the attribute they write are
     `app/appearance.ts`'s — the frame's entry (`MODEL.md` § 2 Part 9), because
     §17 redraws the sign-in gate beside them and cannot do so while the entry
     is engine code. The drawer offers the control and calls that module
     directly; the `data-apparence` branch of the delegation went with it, and
     with it the last French `data-*` name this file wrote. */

  /* Global delegation */
  document.addEventListener("click", (event) => {
    // A navigation link is an <a>, not a <button>: delegation that looked
    // only at buttons left the drawer inert.
    const closest = event.target.closest("button, a[data-navgo]");
    if (!closest) return;
    if (closest.tagName === "A") event.preventDefault();

    if (closest.dataset.page) {
      // Navigating CLOSES whatever is open above: without this, one changed
      // page while staying stuck on the media sheet.
      const leaving = currentState().page;
      hideLayers();
      store.write({ page: closest.dataset.page });
      port.scrollTop = 0;
      render();
      switchPage(leaving);
      return;
    }
    if (closest.dataset.go) {
      /* A go control can sit INSIDE a layer — today only the user sheet's
         « Profil et préférences »: every OTHER producer renders into
         page-body `#view` content, which sits under every layer and is
         therefore covered — untappable — the instant one is open (walked
         control by control, BUGS.md B-024). Landing must LEAVE the layer:
         every layer closes without touching history, and history is settled
         HERE, by `switchPageFromLayer`, exactly as a drawer navigation settles
         itself (see data-navgo). Letting the close unwind and the arrival push
         would race, the asynchronous pop landing after the push and
         overwriting it. */
      const onLayer = history.state && history.state.layer;
      const leaving = currentState().page;
      closeDrawer(true);
      panel.close(true);
      // The settling below walks the layer's entry plus at most one page
      // entry, on the assumption that at most one layer (drawer or sheet —
      // never both at once) precedes a `data-go` tap. B-024 found that
      // assumption unenforced in code, then walked every producer and found
      // it latent — unreachable — because the one producer that can sit over
      // a layer allows at most the sheet itself.
      store.write({ page: closest.dataset.go });
      if (closest.dataset.go === "acq")
        store.write({ acqTab: "now" });
      port.scrollTop = 0;
      render();
      try {
        if (onLayer) switchPageFromLayer(leaving);
        else switchPage(leaving);
      } catch (error) {
        console.error("data-go : écriture de navigation échouée", error);
        window.__navEchec = true;
      }
      return;
    }
    if (closest.dataset.acqtab) {
      store.write({ acqTab: closest.dataset.acqtab });
      port.scrollTop = 0;
      render();
      replacePath();
      return;
    }
    if (closest.dataset.lens) {
      // Changing lens changes the list: start again from the first page. And the
      // SELECTION goes with it — a tick taken in another listing is one the
      // reader cannot see to untick, and « Supprimer » would still offer it.
      store.write({
        libLens: closest.dataset.lens,
        selected: new Set(),
        });
      port.scrollTop = 0;
      render();
      replacePath();
      return;
    }
    if (closest.dataset.cat) {
      store.write({
        libCat: closest.dataset.cat,
        selected: new Set(),
        });
      port.scrollTop = 0;
      render();
      return;
    }
    if (closest.dataset.lmode) {
      store.write({ libMode: closest.dataset.lmode });
      render();
      return;
    }
    if (closest.dataset.pill) {
      store.write({ pill: closest.dataset.pill });
      render();
      return;
    }
    if (closest.dataset.fmode) {
      store.write({ followMode: closest.dataset.fmode });
      render();
      return;
    }
    if (closest.dataset.sugmode) {
      store.write({ sugMode: closest.dataset.sugmode });
      render();
      return;
    }
    if (closest.dataset.toast) {
      toast(closest.dataset.toast);
      return;
    }

    if (closest.dataset.manual != null) {
      // The way out is not a sentence, it is a pre-filled screen.
      // Clean the folder name to turn it into a query.
      const trim = String(closest.dataset.manual)
        .replace(/\.(mkv|mp4|avi)$/i, "")
        .replace(/[._]+/g, " ")
        .replace(
          /\b(MULTi|VOSTFR|WEB-DL|WEBRip|BluRay|x264|x265|HEVC|1080p|2160p|720p|FRENCH|TRUEFRENCH)\b/gi,
          "",
        )
        .replace(/\s{2,}/g, " ")
        .trim();
      // `/resolution` is a router-owned address now: leaving it is
      // `__bridge.retour()` — the same single pop `.fback` uses — unwinding the
      // ONE entry `screens.resolution` pushed to get here. The
      // dispatcher no-ops that pop: the entry carries neither `layer` nor
      // `tm`, so the legacy popstate checks fall through it and the router has
      // already re-rendered by the time they run.
      bridge.back();
      setTimeout(() => screens.add(trim, "identify"), 260);
      return;
    }
    /* THE FOLDER IS `currentState().resolveTarget`, NEVER THE ATTRIBUTE: what
       `data-resolve` carries here is the CHOSEN CANDIDATE, and the folder is
       what the resolution screen was opened on. This branch answers every
       carrier of the attribute. */
    if (closest.dataset.resolve) {
      const target = currentState().resolveTarget;
      bridge.back();
      setTimeout(() => actionResolve(target, closest.dataset.resolve, true), 240);
      return;
    }
    /* Agreeing with the machine. It keeps the automatic result and re-scrapes
       nothing — which is why it says what it did rather than « fait ». */
    if (closest.dataset.leave) {
      const target = currentState().resolveTarget;
      bridge.back();
      setTimeout(() => actionLeave(target), 240);
      return;
    }
    /* What the desktop deck's ⏎ did, without a keyboard: the next folder
       waiting, on the same screen. */
    if (closest.dataset.next) {
      const suite = queued()
        .blocked.concat(queued().stuck)
        .map((blockedCount) => decisionPending(blockedCount.t))
        .find(
          (decision) =>
            decision != null && decision.d !== closest.dataset.next,
        );
      if (suite) {
        // Closing the screen and re-opening it on the next folder was a pop
        // plus a push — net ONE entry. The address is the screen's identity
        // now, so the same depth is a REPLACE: one entry in, one entry out,
        // and a single back still leaves the arbitration rather than walking
        // the folders one has already answered.
        setTimeout(() => screens.resolution(suite.d, true), 240);
      }
      return;
    }
    if (closest.dataset.sheetprim) {
      const [split, split2] = closest.dataset.sheetprim.split("|");
      panel.close();
      setTimeout(() => {
        if (split2 === "to_grab") actionTake(split);
        else
          toast(
            `Recherche lancée pour « ${baseTitle(split)} » — le résultat s'affichera sur la carte.`,
          );
      }, 240);
      return;
    }
    // `data-take` HAS NO BRANCH HERE ANY MORE (B-309). It had two, told apart
    // by guessing at the value. The release picker says `data-pick-release`
    // now and the panel's take kept this name, so each has one meaning and one
    // reader, and both answer on the tap registry.
    if (closest.dataset.standby) {
      panel.close();
      toast(
        "Veille lancée — 12 suivis balayés, 0 nouvelle release conforme. Prochain passage à 15 h 20.",
      );
      return;
    }
    if (closest.dataset.ep) {
      openPopEp(closest);
      return;
    }
    if (closest.dataset.drawer) {
      openDrawer();
      return;
    }
    if (closest.dataset.pipe) {
      /* Asked while a run is already going, a run is QUEUED and says so
         (DOIT-4). « Occupé, réessaie » is the answer this interface does not
         give: it puts the burden of remembering on the operator. */
      store.write({
        pipe:
          closest.dataset.pipe === "stop"
            ? "idle"
            : currentState().pipe === "idle"
              ? "running"
              : "queued",
      });
      render();
      toast(
        currentState().pipe === "running"
          ? "Pipeline lancé — il se raconte ici, étape par étape."
          : currentState().pipe === "queued"
            ? "En file — votre passage partira dès que celui-ci sera fini."
            : "Pipeline arrêté. Ce qui était déjà rangé le reste.",
      );
      return;
    }
    if (closest.dataset.navgo) {
      const id = closest.dataset.navgo;
      /* The drawer is NOT a route, so its entry does not survive the
         destination — and neither does the entry of the page one is leaving.
         A drawer entry is a top-level destination like any other, so § 16
         rule 2 applies to it whole: `switchPageFromLayer` walks down to the
         floor and settles the destination there, which is what makes one back
         from the destination reach the entry page and not the médiathèque one
         happened to open the drawer from.

         This is also why history is settled here rather than by letting the
         close unwind and the arrival push: a back is asynchronous, so its
         pop would land after the push and overwrite it. The close is
         therefore told not to touch history at all. */
      const onDrawer = history.state && history.state.layer === "drawer";
      const leaving = currentState().page;
      closeDrawer(true);
      store.write({ page: id });
      port.scrollTop = 0;
      render();
      try {
        if (onDrawer) switchPageFromLayer(leaving);
        else switchPage(leaving);
      } catch (error) {
        console.error("data-navgo : écriture de navigation échouée", error);
        window.__navEchec = true;
      }
      return;
    }
    if (closest.dataset.sort) {
      // THE PRODUCER HAS LEFT. `features/library/panel-sort.ts` answers.
      panel.produce("sort");
      return;
    }
    if (closest.dataset.setsort) {
      store.write({
        sortKey: closest.dataset.setsort,
        sortReversed: closest.dataset.reversed === "1",
        selected: new Set(),
      });
      panel.close();
      render();
      toast(`Trié par ${sortLabel().toLowerCase()}.`);
      return;
    }
    if (closest.dataset.phase) {
      store.write({ phase: closest.dataset.phase });
      render();
      return;
    }
    if (closest.dataset.tmdb) {
      store.write({ tmdb: true });
      render();
      toast(
        "Compte TMDB connecté — la réserve se remplit, vos notes sont lues.",
      );
      return;
    }
    if (closest.dataset.clearq) {
      if (closest.dataset.clearq === "lib")
        // THE SELECTION GOES WITH THE QUESTION. Clearing the search widens what
        // is on screen, and the ticks taken under the narrower listing are not
        // the ones a reader is looking at.
        store.write({ q: "", selected: new Set() });
      else store.write({ filter: "" });
      render();
      return;
    }
    if (closest.dataset.selmode) {
      store.write({ selMode: closest.dataset.selmode === "1", selectedMedia: 0 });
      // Set mutated in place; render() right below carries the bump.
      currentState().selected.clear();
      render();
      return;
    }
    if (closest.dataset.delsel) {
      // THE SET HOLDS TITLES, so the dialog names what the reader ticked. It
      // used to read each entry as an index into the SOURCE array while the
      // ticks were taken on the LISTING — so under any order but the source's
      // it named other media and destroyed them: ticking « 3% » and « À la
      // recherche de Harry » under A → Z deleted « Ninja Turtles » and « Big
      // Chicken », and the two ticked rows stayed.
      openDeleteDialog(null, [...state.selected]);
      return;
    }
    if (closest.dataset.tile != null && currentState().selMode) {
      const title = closest.dataset.selectedTitle;
      if (title == null) return;
      if (currentState().selected.has(title)) currentState().selected.delete(title);
      else currentState().selected.add(title);
      // paintSelBar() below draws the bar directly, not through render():
      // the explicit bump is what tells React the selection changed.
      // THE BAR COUNTS MEDIA, not ticks. One press on a title this library holds
      // twice lights both rows and the dialog says « 2 médias »; a caption
      // reading « 1 sélectionné » beside them is the only figure in the flow
      // still counting something else. Written rather than touched: a write
      // bumps too, and hold (f) drives `write({})` on nine states to prove a
      // surface keeps its nodes across one.
      store.write({
        selectedMedia: [...currentState().selected].reduce(
          (accumulator, element) => accumulator + mediaNamedBy(element),
          0,
        ),
      });
      closest.setAttribute("aria-pressed", String(currentState().selected.has(title)));
      paintSelBar();
      return;
    }
    if (closest.dataset.del) {
      panel.close();
      openDeleteDialog(closest.dataset.del);
      return;
    }
    if (closest.dataset.mediasheet) {
      // The seam closes the layer inside the navigation's own commit, so an
      // open sheet no longer needs closing here and no longer needs a delay to
      // finish leaving: its departure is drawn by the transition.
      screens.mediaSheet(closest.dataset.mediasheet);
      return;
    }
    if (closest.dataset.act === "resolve") {
      screens.resolution();
      return;
    }
    if (closest.dataset.sheet === "plus") {
      // THE PRODUCER HAS LEFT. `features/acquisition/panel-more.ts` answers.
      panel.produce("more");
      return;
    }
    if (closest.dataset.act?.startsWith("add:")) {
      // The act carries the list POSITION, not the title: a search can
      // return the same title twice — « Star Wars : The Clone Wars » is both a
      // film and a series here — so the title does not identify the result.
      const index = Number(closest.dataset.act.slice(4));
      const result = searchResults().results[index];
      if (currentState().addMode === "identify") {
        // This ASSOCIATES: the stuck folder becomes this medium and the pipeline
        // resumes. No follow is created — that was not the request.
        const target = currentState().resolveTarget;
        // No render() on this branch until the delayed actionResoudre()
        // fires — the bump is explicit so React sees the pick immediately.
        currentState().added.add(index);
        store.touch();
        /* ONE settlement for the TWO entries this journey stacked — the
           result's panel, and `/add` itself, a router-owned address (which
           is why no screen layer is closed here). The panel is ASKED before it is closed, because the layer's
           own entry is what decides the count, and it is closed DOM-only
           (`close(true)`) so it does not unwind on its own: its unwind plus a
           raw `__bridge.retour()` were two backs racing in the same task, only
           one of them announced, and the surplus pop was then read as the
           operator's own back gesture. */
        const entries = (panel.isOpen() ? 1 : 0) + 1;
        panel.close(true);
        bridge.rewind(entries);
        setTimeout(() => {
          actionResolve(target, result.t);
          toast(
            `« ${baseTitle(target ?? "")} » identifié comme « ${result.t} » — le scrape reprend, aucun suivi créé.`,
          );
        }, 260);
        return;
      }
      // The act lives in the result's panel, which must not stay open
      // behind what comes next — the dialog below, or the re-rendered list.
      // The identify branch above settles its own layer, with the entry count
      // its single settlement needs, so this close is the follow branches'.
      panel.close();
      if (result.owned) {
        seam.dialog?.open({
          heading: `Remplacer « ${result.t} » ?`,
          body: [
            {
              type: "paragraph",
              runs: [
                {
                  text:
                    "Ce " +
                    (result.k === "Film" ? "film est déjà" : "média est déjà") +
                    " en médiathèque. L'acquisition ",
                },
                { text: "remplacera", strong: true },
                { text: " la version en place par celle qui sera récupérée." },
              ],
            },
          ],
          actions: [
            {
              text: "Remplacer",
              tone: "danger",
              target: { "data-confirmadd": String(index) },
            },
            { text: "Annuler", tone: "ghost", dismiss: true },
          ],
        });
        return;
      }
      // The screen stays open, re-rendered in place with the "added" chip
      // and (once this is the first) the footer: `AddScreen` re-renders
      // itself from this same store bump, so no redraw call belongs here
      // any more.
      currentState().added.add(index);
      store.touch();
      seam.followVerbs?.follow(result.t, result.k);
      return;
    }
    if (closest.dataset.confirmadd) {
      currentState().added.add(Number(closest.dataset.confirmadd));
      store.touch();
      closeDlg();
      toast(
        "Ajouté — la version en place sera remplacée une fois la nouvelle récupérée.",
      );
      return;
    }
    if (closest.dataset.journey) {
      // THE PRODUCER HAS LEFT, and its 260 ms wait went with it: the panel
      // leaves inside the navigation's own commit, as `data-mediasheet`
      // already did once B-249's wait left that branch. R103 refuses the gap on
      // this path now rather than printing it.
      panel.close();
      panel.produce("journey", closest.dataset.journey);
      return;
    }
    /* A card body opens the panel on a simple tap. The gallery reaches the
       same panel by a long press, handled where the press is timed. */
    if (closest.dataset.panel) {
      openPanel(closest);
      return;
    }
    if (closest.dataset.complete) {
      store.write({ page: "acq", acqTab: "now" });
      panel.close();
      render();
      toast(
        `« ${baseTitle(closest.dataset.complete)} » : recherche des épisodes manquants lancée.`,
      );
      return;
    }

    if (closest.classList.contains("cfoot")) {
      const title =
        closest.closest(".card")?.querySelector(".ctitle")?.textContent ?? "";
      const lab = closest.textContent.trim();
      if (lab.startsWith("Récupérer")) return actionTake(title);
      if (lab.startsWith("Résoudre")) return screens.resolution(title);
      toast("Action lancée — le résultat s'affichera ici.");
      return;
    }
    if (closest.classList.contains("act")) {
      const textContent = closest
        .closest(".swipe")
        .querySelector(".ctitle").textContent;
      // Through the shared close, so what is recorded about the open row — and
      // about where it rests — cannot drift from what is on screen. Clearing
      // the transform alone left the next drag resuming from a drawer that was
      // no longer open, which is the jump seen from the other side.
      const card = closest.closest(".swipe").querySelector(".card");
      if (openCard === card) collapseCard();
      else card.style.transform = "";
      if (closest.classList.contains("remove"))
        return currentState().page === "lib"
          ? openDeleteDialog(textContent)
          : seam.followVerbs?.removeFollow(textContent);
      if (closest.classList.contains("pause"))
        return seam.followVerbs?.pause(textContent);
      toast(`${closest.textContent.trim()} — ${textContent}`);
      return;
    }
  });

  /* Deletion */
  /* How many library rows one title names. The delete acts BY TITLE — the only
     key the contract offers — so a title naming two rows is two media, and every
     figure the interface prints about a selection has to say so. */
  function mediaNamedBy(title) {
    return Math.max(1, LIBRARY.filter((row) => row.t === title).length);
  }

  function openDeleteDialog(title, many) {
    const titles = many && many.length > 0 ? many : [title];
    const multi = titles.length > 1;
    const inc = (title2) =>
      INCOMPLETE.find((INCOMPLETE2) => INCOMPLETE2.t === title2);
    const followed = titles.filter(
      (title2) =>
        follows().some((follow) => follow.t === title2) || !!inc(title2),
    );
    // HOW MANY MEDIA EACH TITLE NAMES, and it is not always one. The delete
    // acts BY TITLE — the only key the contract offers — and this library holds
    // « Doctor Who » twice, 2005 and 2023 — ONE duplicated title in 345 rows,
    // 344 of them distinct. (The first version of this sentence said five, a
    // count taken over a window that ran past this array into the next one.)
    // Confirming one of them removes both, and the count below said one file:
    // a manifest whose whole purpose is « voici exactement ce qui serait
    // supprimé » naming half of it. The interface cannot delete one of the two
    // — that needs an identifier the backend does not serve, and the demand is
    // recorded — but it can say the truth about what it is about to do.
    const mediaFor = mediaNamedBy;
    const files = titles.reduce(
      (accumulator, element) =>
        accumulator + (inc(element) ? inc(element).o : mediaFor(element)),
      0,
    );
    const media = titles.reduce(
      (accumulator, element) => accumulator + mediaFor(element),
      0,
    );
    // What the four rows above the fold account for, so « et N autres » names
    // media like every other figure in this dialog.
    const shown = titles.slice(0, 4).reduce(
      (accumulator, element) => accumulator + mediaFor(element),
      0,
    );
    // AND THE FOLLOWED WARNING TOO. A followed title that names two rows is two
    // media coming back at the next search. Latent while no duplicated title is
    // followed, which is exactly how it would ship unnoticed.
    const followedMedia = followed.reduce(
      (accumulator, element) => accumulator + mediaFor(element),
      0,
    );
    const size = (files * 0.41).toFixed(1).replace(".", ",") + " Go";
    /* NOT ESCAPED, and it is the one `escapeHtml` site in this file that must
       not be: the heading crosses as a DESCRIPTOR field and is rendered as a
       React text node, which escapes it itself. Escaped here it was escaped
       twice — « Supprimer « Lilo &amp; Stitch » ? » on every title carrying an
       ampersand, and the seeds carry five. The other thirty-five sites still
       feed `innerHTML` and still need it. */
    const head = multi
      ? `Supprimer ${media} médias ?`
      : media > 1
        ? `Supprimer « ${titles[0]} » — ${media} médias ?`
        : `Supprimer « ${titles[0]} » ?`;
    seam.dialog?.open({
      heading: head,
      body: [
        {
          type: "dryRun",
          text:
            "Simulation — rien ne sera supprimé tant que vous n'aurez pas " +
            "validé que cette liste dit vrai.",
        },
        ...(multi
          ? [
              {
                type: "manifest",
                entries: [
                  ...titles.slice(0, 4).map((title2) => ({
                    text: title2,
                    value: `${inc(title2) ? inc(title2).o : mediaFor(title2)} fichier${(inc(title2) ? inc(title2).o : mediaFor(title2)) > 1 ? "s" : ""}`,
                  })),
                  ...(titles.length > 4
                    ? [
                        {
                          text: `et ${media - shown} autre${media - shown > 1 ? "s" : ""}`,
                          value: "",
                        },
                      ]
                    : []),
                ],
              },
            ]
          : []),
        {
          type: "paragraph",
          runs: [{ text: "Voici exactement ce qui serait supprimé :" }],
        },
        {
          type: "manifest",
          entries: [
            { text: "Fichiers vidéo", value: `${files} · ${size}` },
            {
              text: "Métadonnées (NFO, affiches, fanart)",
              value: `${files * 3} fichiers`,
            },
            {
              text: "Lignes de la médiathèque",
              // THE MEDIA, not the titles: one title can name two rows, and this
              // manifest's whole purpose is to say exactly what would go.
              value: `${media} item${media > 1 ? "s" : ""}`,
            },
            { text: "Entrée Plex", value: `${media} · à vérifier` },
          ],
        },
        ...(followed.length > 0
          ? [
              {
                type: "warning",
                strong:
                  followed.length === 1
                    ? `« ${followed[0]} » est suivi.`
                    : `${followedMedia} de ces médias sont suivis.`,
                text:
                  "Sans action de votre part, ces épisodes seront " +
                  "re-téléchargés à la prochaine recherche.",
              },
            ]
          : []),
      ],
      actions: [
        ...(followed.length > 0
          ? [
              {
                text: "Supprimer et arrêter le suivi",
                tone: "danger",
                target: {
                  "data-toast":
                    "Simulation terminée — 0 fichier touché. Le suivi aurait été arrêté.",
                },
                run: () => actionDelete(titles),
              },
              {
                text: "Supprimer, garder le suivi",
                target: {
                  "data-toast":
                    "Simulation terminée — 0 fichier touché. Le suivi aurait été conservé.",
                },
                run: () => actionDelete(titles),
              },
            ]
          : [
              {
                text: "Supprimer",
                tone: "danger",
                target: {
                  "data-toast": "Simulation terminée — 0 fichier touché.",
                },
                run: () => actionDelete(titles),
              },
            ]),
        { text: "Annuler", tone: "ghost", dismiss: true },
      ],
    });
  }

  /* Screens and sheets */
  const MOIS = [
    "janv.",
    "févr.",
    "mars",
    "avr.",
    "mai",
    "juin",
    "juil.",
    "août",
    "sept.",
    "oct.",
    "nov.",
    "déc.",
  ];
  function dateFR(iso) {
    if (!iso) return null;
    const [map, map2, map3] = iso.split("-").map(Number);
    return `${map3} ${MOIS[map2 - 1]} ${map}`;
  }
  const TODAY = "2026-08-10";



  /* The media sheet moved to the shell with the rest of the screens:
     `src/screens/media.tsx` renders it as the route `/mediasheet/$title`. The
     verb a call site says is `screens.mediaSheet(title)`; the template,
     the seasons and the actions live there, at identical markup — the
     click delegation below still reads their data attributes. */
  /* The resolution screen moved to the shell the same way:
     `src/screens/resolution.tsx` renders it as the route
     `/resolution/$folder`, and the design rationale it carries — what the
     screen is FOR, why a tied score is not printed, the three ways out —
     moved there with it. The verb a call site says is
     `screens.resolution(dossier, remplacer)`: it resolves the same
     default this file used to (the first stuck folder) and writes
     `currentState().resolveTarget` before navigating, so the `data-resolve` and
     `data-leave` branches below still read the folder they always read.
     `decisionPending` stays here: it is the référentiel's own answer to
     « does this folder have a pending decision », read by the screen AND by
     the « Passer à la suivante » branch below. */
  /* A folder either HAS a pending decision or it has none, and the screen must
     not borrow one. Showing another folder's candidates would be the worst
     possible lie on the one screen whose job is to name what is on disk. */
  /* IT READS THE CACHE NOW, and the fixture it used to read is gone (L09). The
     shell publishes `seam.pendingDecisions` over the query cache — a
     SYNCHRONOUS read, because this is called from a click handler that cannot
     await. Before the query has answered it reports « no decision », which is
     the same answer this function already gave for a folder that has none, and
     the surfaces that draw a decision render nothing until the cache has one.
     It dies with the branch below at L13. */
  function decisionPending(target) {
    const pending = seam.pendingDecisions?.() ?? [];
    return pending.find((decision) => decision.d === target) ?? null;
  }

  /* Tapping a cell: its air date, in French. The sentence follows the state
     — « Sortie prévue » for an announced episode, « Diffusé » otherwise —
     and a missing date is stated, not invented. */
  /* THE POPOVER'S LAYER IS NOT THIS FILE'S ANY MORE — but its SENTENCE still
     is. `openPopEp` built the node, placed it against the phone frame, wrote
     what it says and armed its dismissal, all in one function. Only the first,
     second and fourth are the frame's: `ui/popover.tsx` over
     `app/popover-host.ts`, behind `{ anchor, content }`. What is left here is
     the PRODUCER — the five lines that turn an episode into three facts — and
     a producer moves to its feature with L19 (Part 12). */
  function closePopEp() {
    seam.popover?.close();
  }
  function openPopEp(btn) {
    // THE SENTENCE HAS LEFT. The frame places, the feature says —
    // `features/media/popover-episode.ts`, reached through the seam it
    // publishes. What stays here is the tap, which is the delegation's.
    const saying = seam.episodeSaying?.(btn);
    if (saying) seam.popover?.open(btn, saying);
  }

  /* Does this interface HOLD a medium by that title?
     the follow panel answers for ANYTHING: a title it recognises in
     none of its sources still gets a panel, synthesised from the title alone.
     That is right for the in-app door — every medium opens the same panel, and
     « rien n'est connu de celui-ci » is one of the truths a library title can
     carry — and wrong for a door anyone can type, where the same fallback
     turns a stale link into a medium that does not exist. So the question is
     asked apart from the opening, and only an ADDRESS asks it.

     THE MEMBERSHIP IS EXACT, and it reads the three sources the opener itself
     matches exactly. A sheet is not a fourth one, deliberately: `sheetFor` is
     built to be FORGIVING, because the lists it serves truncate their titles.
     It answers on any prefix of more than six characters, and — being a
     bracket read on a plain object — it answers for `constructor` and every
     other name `Object.prototype` carries. Both hand back a title the opener
     then finds in none of its own sources, so it synthesises exactly the
     medium the address was meant to be refused for. A title that only has a
     sheet is not a follow. */
  function knownMedium(title) {
    return (
      follows().some((follow) => follow.t === title) ||
      INCOMPLETE.some((entry) => entry.t === title) ||
      LIBRARY.some((entry) => entry.t === title)
    );
  }
  installKnownMedium(knownMedium);

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

  /* 1) Card swipe — a drag born on a card belongs to the card.

     It runs BOTH ways: the drawer on the right holds what one does to a medium
     — pause it, drop it — and the one on the left holds the single thing the
     card is FOR, the action its footer already names. A card with no such
     action has no left drawer, and the gesture simply does not travel that
     way rather than opening an empty one.

     Only ONE card is open at a time. Two open drawers ask which one an action
     belongs to, and the answer is never on screen; starting a drag anywhere
     puts the previous card back first.

     A drag is not a tap. The card body opens the bottom panel on a tap, so a
     swipe that also fired it would open a panel over the drawer it just
     revealed — the click that follows the release is swallowed, identified by
     the DISTANCE travelled, not by a timer.

     Listened for on the FRAME, not the scrollport: every layer above it — the
     sheet, the screen, the drawer — sits outside, and a row drawn in one of
     them would answer no gesture at all. */
  let cardDrag = null;
  let openCard = null;
  /* Where the open row RESTS, in pixels — negative for the right drawer,
     positive for the left. A drag beginning on an open row resumes from where
     the row actually is; deducing that origin from a side instead read every
     open row as if it were open on the RIGHT, so a row open on the left leapt
     the width of both drawers on the finger's first move. Measured at 252px
     of jump for a 15px step. */
  let openCardDx = 0;
  let clickAfterDrag = null;

  function collapseCard() {
    if (!openCard) return;
    openCard.style.transform = "";
    openCard = null;
    openCardDx = 0;
  }

  function drawerWidth(sw, sens) {
    const cote = sw.querySelector(sens < 0 ? ".side.right" : ".side.left");
    return cote ? cote.querySelectorAll(".act").length * 84 : 0;
  }

  cadre.addEventListener(
    "pointerdown",
    (event) => {
      clickAfterDrag = null;
      const closest = event.target.closest(".swipe");
      if (!closest || !event.isPrimary) return;
      // A new gesture anywhere puts the previously opened row back.
      if (openCard && openCard !== closest.querySelector(".card"))
        collapseCard();
      cardDrag = {
        sw: closest,
        card: closest.querySelector(".card"),
        x: event.clientX,
        y: event.clientY,
        depart:
          openCard === closest.querySelector(".card") ? openCardDx : 0,
        axis: null,
        dx: 0,
      };
    },
    { passive: true },
  );
  cadre.addEventListener(
    "pointermove",
    (event) => {
      if (!cardDrag) return;
      const deltaX = event.clientX - cardDrag.x,
        deltaY = event.clientY - cardDrag.y;
      if (cardDrag.axis === null) {
        if (Math.abs(deltaX) < 6 && Math.abs(deltaY) < 6) return;
        cardDrag.axis = Math.abs(deltaX) > Math.abs(deltaY) * 1.2 ? "x" : "y";
        if (cardDrag.axis === "x") cardDrag.card.classList.add("dragging");
      }
      if (cardDrag.axis !== "x") return;
      const brut = cardDrag.depart + deltaX;
      cardDrag.lastX = event.clientX;
      cardDrag.lastY = event.clientY;
      /* An open row can only be CLOSED by a drag. Its travel is clamped
         between where it rests and zero, so a swipe the other way settles it
         back rather than crossing rest and opening the opposite drawer within
         the same gesture. Reaching the other side is a second, deliberate
         swipe — the row has to have come back first. */
      cardDrag.dx = cardDrag.depart
        ? Math.min(
            Math.max(brut, Math.min(cardDrag.depart, 0)),
            Math.max(cardDrag.depart, 0),
          )
        : Math.max(
            -drawerWidth(cardDrag.sw, -1),
            Math.min(drawerWidth(cardDrag.sw, 1), brut),
          );
      cardDrag.card.style.transform = `translateX(${cardDrag.dx}px)`;
    },
    { passive: true },
  );
  function endCardDrag() {
    if (!cardDrag) return;
    const drag = cardDrag;
    cardDrag = null;
    if (drag.axis !== "x") return;
    drag.card.classList.remove("dragging");
    // Past a third of a drawer's width the row rests open on that side.
    const gauche = drawerWidth(drag.sw, 1);
    const right = drawerWidth(drag.sw, -1);
    let repos = 0;
    if (drag.depart) {
      // Closing an open row takes a third of its own travel, so a thumb
      // brushing past one does not shut what it came to use.
      repos =
        Math.abs(drag.dx) > Math.abs(drag.depart) * (2 / 3) ? drag.depart : 0;
    } else if (drag.dx < -right / 2.4) repos = -right;
    else if (drag.dx > gauche / 2.4) repos = gauche;
    drag.card.style.transform = repos ? `translateX(${repos}px)` : "";
    openCard = repos ? drag.card : null;
    openCardDx = repos;
    // The release is followed by a click, and a drag must not also tap. The
    // click is identified by its POINT — the same answer the long press
    // already needed — because a bare flag stays armed until SOME click
    // happens, and the next one it meets may be elsewhere entirely.
    /* Armed on what the FINGER travelled, never on what the row moved.

       The guard exists to tell a drag from a tap, and that distinction belongs
       to the pointer: a row is free to refuse to move — a list with no left
       drawer does exactly that — and measuring its displacement turns every
       such drag into a tap. Two ways in, one old and one new: a right drag on
       a row with no left drawer has always ended at zero, and since an open
       row can only be closed, dragging one further in the same direction now
       ends where it started too. Both armed nothing, so the click went
       through and the bottom panel opened over the row.

       Only a MOUSE ever showed it. After a touch drag the browser suppresses
       the click by itself, so every finger measurement was green over the
       hole — which is why the check for this asserts the click was actively
       SWALLOWED rather than that no panel appeared. A panel that fails to
       appear can be an accident of where the release landed. */
    const travelled = Math.hypot(
      (drag.lastX ?? drag.x) - drag.x,
      (drag.lastY ?? drag.y) - drag.y,
    );
    clickAfterDrag =
      travelled > 4 ? { x: drag.lastX, y: drag.lastY } : null;
  }
  window.addEventListener("pointerup", endCardDrag);
  window.addEventListener("pointercancel", endCardDrag);
  document.addEventListener(
    "click",
    (event) => {
      if (!clickAfterDrag) return;
      const mark = clickAfterDrag;
      clickAfterDrag = null;
      if (Math.hypot(event.clientX - mark.x, event.clientY - mark.y) > 24)
        return;
      event.preventDefault();
      event.stopPropagation();
    },
    { capture: true },
  );

  /* 1b) Suggestion card: a swipe either way means dismiss. Same reason as
     `.swipe`: the row claims the horizontal axis, otherwise the browser
     takes the gesture and cancels it at the first pixel. */
  let sugDrag = null;
  cadre.addEventListener(
    "pointerdown",
    (event) => {
      const closest = event.target.closest(".sugwrap");
      if (!closest || !event.isPrimary) return;
      const point = event;
      sugDrag = {
        w: closest,
        card: closest.querySelector(".card"),
        x: point.clientX,
        y: point.clientY,
        axis: null,
        dx: 0,
      };
    },
    { passive: true },
  );
  cadre.addEventListener(
    "pointermove",
    (event) => {
      if (!sugDrag) return;
      const point = event;
      const deltaX = point.clientX - sugDrag.x,
        deltaY = point.clientY - sugDrag.y;
      if (sugDrag.axis === null) {
        if (Math.abs(deltaX) < 6 && Math.abs(deltaY) < 6) return;
        sugDrag.axis = Math.abs(deltaX) > Math.abs(deltaY) * 1.2 ? "x" : "y";
        if (sugDrag.axis === "x") sugDrag.card.classList.add("dragging");
      }
      if (sugDrag.axis !== "x") return;
      sugDrag.dx = deltaX;
      sugDrag.card.style.transform = `translateX(${deltaX}px)`;
      sugDrag.card.style.opacity = String(
        Math.max(0.35, 1 - Math.abs(deltaX) / 260),
      );
    },
    { passive: true },
  );
  function endSugDrag() {
    if (!sugDrag) return;
    const drag = sugDrag;
    sugDrag = null;
    if (drag.axis !== "x") return;
    drag.card.classList.remove("dragging");
    if (Math.abs(drag.dx) > 92) {
      drag.card.style.transform = `translateX(${drag.dx > 0 ? 420 : -420}px)`;
      dismissSug(Number(drag.w.dataset.dismissable));
    } else {
      drag.card.style.transform = "";
      drag.card.style.opacity = "";
    }
  }
  window.addEventListener("pointerup", endSugDrag);
  window.addEventListener("pointercancel", endSugDrag);

  /* Deck gesture. Left « Passer » sends the card to the back of the order —
     it decides nothing and comes round again. Right « Pas intéressé » removes
     it, with an undo. Listeners are passive; the card claims the horizontal
     axis through `touch-action: pan-y` on `.deck`. */
  let deckDrag = null;
  cadre.addEventListener(
    "pointerdown",
    (event) => {
      const card = event.target.closest?.('.dcard[data-depth="0"]');
      if (!card || !event.isPrimary) return;
      deckDrag = {
        card,
        x: event.clientX,
        y: event.clientY,
        dx: 0,
        axis: null,
      };
    },
    { passive: true },
  );
  cadre.addEventListener(
    "pointermove",
    (event) => {
      if (!deckDrag) return;
      const point = event;
      const deltaX = point.clientX - deckDrag.x,
        deltaY = point.clientY - deckDrag.y;
      if (deckDrag.axis === null) {
        if (Math.abs(deltaX) < 6 && Math.abs(deltaY) < 6) return;
        deckDrag.axis = Math.abs(deltaX) > Math.abs(deltaY) * 1.2 ? "x" : "y";
        if (deckDrag.axis === "x") deckDrag.card.classList.add("dragging");
      }
      if (deckDrag.axis !== "x") return;
      deckDrag.dx = deltaX;
      // The card leans into the movement: the rotation is what makes it read
      // as a card being pulled off a deck rather than a panel sliding.
      deckDrag.card.style.transform = `translateX(${deltaX}px) rotate(${deltaX / 26}deg)`;
      const element = deckDrag.card.querySelector(".dhint.l");
      const element2 = deckDrag.card.querySelector(".dhint.r");
      const min = Math.min(1, Math.max(0, (Math.abs(deltaX) - 20) / 70));
      if (element) element.style.opacity = deltaX < 0 ? String(min) : "0";
      if (element2) element2.style.opacity = deltaX > 0 ? String(min) : "0";
    },
    { passive: true },
  );
  function endDeckDrag() {
    if (!deckDrag) return;
    const drag = deckDrag;
    deckDrag = null;
    drag.card.classList.remove("dragging");
    if (drag.axis !== "x") return;
    const index = Number(drag.card.dataset.deck);
    if (Math.abs(drag.dx) > 88) {
      // The pile is ANIMATED, not rebuilt: avancerDeck moves the existing
      // nodes, which is the only way the card underneath can rise rather than
      // appear. The state is updated alongside, never by re-rendering.
      if (drag.dx > 0) {
        // avancerDeck() animates the DOM directly, never through render():
        // the bump is explicit so React learns the card left the deck.
        currentState().sugGone.add(index);
        store.touch();
        advanceDeck(index, 1);
        toastUndo(`« ${suggestions()[index].t} » écarté.`, () => {
          currentState().sugGone.delete(index);
          store.touch();
          refreshDeck();
        });
      } else {
        passerSug(index);
        advanceDeck(index, -1);
      }
      return;
    }
    drag.card.style.transform = "";
    drag.card
      .querySelectorAll(".dhint")
      .forEach((querySelectorAll) => (querySelectorAll.style.opacity = "0"));
  }
  window.addEventListener("pointerup", endDeckDrag);
  window.addEventListener("pointercancel", endDeckDrag);

  /* 3) Pull-to-refresh — on the rest of the surface. ALL listeners are
     passive: a single non-passive touchmove takes iOS out of the compositor
     and makes the sticky chrome shimmer.

     THE FINGER IS READ FROM TOUCH EVENTS, everything else from pointer
     events, and one implementation serves both.

     The reason is not stylistic. These two gestures live INSIDE the
     scrollport, and the browser owns vertical panning there. The moment it
     decides a drag is a scroll it fires `pointercancel` and stops delivering
     `pointermove` for that pointer — measured: one move delivered, then
     cancel, while ten `touchmove` arrive for the same finger. A pointer-only
     implementation therefore works under synthetic events, which are never
     cancelled, and does nothing at all under a real thumb.

     Claiming the axis in `touch-action` is the usual answer and is not
     available here: `pan-y` on the scrollport intersects down onto
     `.pillscroll` and `.cast`, which declare `pan-x pan-y`, and a `pan-x`
     scroller under a `pan-y` ancestor pans on neither axis. The gestures that
     CAN claim their axis — a swipeable row, a deck card — keep the pointer
     path, and their stream is never cancelled. */
  let refreshing = false,
    minuteurRefresh = null;
  const ptr = select("#ptr");

  /* Puts the indicator back to rest, pending refresh included.

     A refresh in flight outlives a change of state, and the indicator's classes
     are not part of the state object, so without this a measurement inherits
     the spinner of the one before it — which is exactly how a first pass at
     this gesture reported it working on half the surfaces and broken on the
     other half, in alternation. */
  window.__reposPTR = () => {
    if (minuteurRefresh !== null) {
      clearTimeout(minuteurRefresh);
      minuteurRefresh = null;
    }
    refreshing = false;
    pullGesture.reset();
    ptr.className = "ptr";
    ptr.style.height = "0px";
    ptr.style.transition = "";
    return true;
  };

  /* THE PULL — arbitrated in `lib/pull-gesture.ts`.

     The GESTURE moved to that module: the axis decision, the edge dead zone, the
     damping and the arming distance are vocabulary, and vocabulary is not the
     engine's (invariant 10). `MODEL.md` Part 8 places it exactly — « a gesture
     on `#port` that knows nothing of what refreshes ».

     What stays here is what a completed pull MEANS: drawing the indicator and
     saying « Actualisé ». Nothing was added to the engine to do it — the block
     left and an import took its place, which is the only shape D5 allows. */
  const pullGesture = installPullGesture({
    port,
    isExcluded: (target) =>
      !!(
        target.closest?.(".swipe") ||
        target.closest?.(".sugwrap") ||
        // A drag born on a deck card belongs to the card: without this the
        // page handler also fires and navigates away mid-gesture.
        target.closest?.(".deck") ||
        target.closest?.(".pillscroll")
      ),
    onPull: (pulled, armed) => {
      if (refreshing) return;
      ptr.style.height = pulled + "px";
      ptr.style.transition = "none";
      ptr.classList.toggle("armed", armed);
    },
    onRelease: (armed) => {
      ptr.style.transition = "";
      if (armed && !refreshing) {
        refreshing = true;
        ptr.classList.add("loading");
        ptr.style.height = "44px";
        minuteurRefresh = window.setTimeout(() => {
          minuteurRefresh = null;
          refreshing = false;
          ptr.classList.remove("loading", "armed");
          ptr.style.height = "0px";
          toast("Actualisé.");
        }, 1100);
      } else {
        ptr.style.height = "0px";
        ptr.classList.remove("armed");
      }
    },
  });

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
  openDeleteDialog,
  openDrawer,
  resetSettings,
  render,
  toast,
  svgIcon,
  escapeHtml,
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
  POSTERS_HD, AUDIOS,
  TODAY, CADENCE_CRON, ACCOUNT,
  DEPENDENCIES, DISKS,
  EP_LABEL, EP_ORDER, EP_SWATCH, ERRORS, DECISION_STATE,
  DECISION_STATE_DETAIL, EXECUTIONS,
  GROUPS, INCOMPLETE, INDEX, JOURNAL, LIBRARY,
  LIB_PAGE, LIB_TOTAL, MAINT_TOPICS, MOIS, REASON_LABEL,
  REASON_DETAIL, REASON_TONE,
  SETTINGS_STATE, RESOLUTIONS,
  SEASONS, SECRETS, SERVICES, SERVICES_PANNE,
  ST_LABEL,
  ST_LABEL_MOVIE, ST_TONE,
  URGENCY, VIA_LABEL, actionLeave,
  actionTake, actionResolve,
  actionDelete, addVerb, showSignIn,
  baseTitle, beforeReset, cadenceFR,
  closeDlg, closeSheet,
  dateFR, decisionPending,
  endCardDrag, endDeckDrag,
  endSugDrag, escapeHtml,
  closePopEp, closeDrawer, changedFiles,
  gridBadge, icons, initialsOf, drawerWidth,
  mountLoaders, mountSearch, fileName,
  openDeleteDialog,
  openPanel,
  openSheet,
  openPopEp,
  openDrawer, paintSelBar, panelUnderFinger,
  nextSearchFR,
  ptr, refPanel, collapseCard,
  settingId, resetSettings, render,
  select, sortLabel,
  stFraction, stLabel,
  sugVerb,
  svgIcon, toast, toastUndo,
  displayedValue,
  typedValue, view,
});

// Read live, because the engine reassigns each of these.
Object.defineProperties(window, {
  cardDrag: { get: () => cardDrag, configurable: true },
  openCard: { get: () => openCard, configurable: true },
  openCardDx: { get: () => openCardDx, configurable: true },
  clickAfterDrag: { get: () => clickAfterDrag, configurable: true },
  swallowClick: { get: () => pressArbitration.swallowClick, configurable: true },
  deckDrag: { get: () => deckDrag, configurable: true },
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
  sugDrag: { get: () => sugDrag, configurable: true },
});
