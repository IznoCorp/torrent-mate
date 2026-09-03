/* The scenario table — every state the harness can drive to by name.

   It used to live inside the engine, and it never belonged there: 656 lines of
   FIXTURE, carried by the product so that something outside it could measure
   the product. It is the harness's, and it lives with the harness's other
   concerns now.

   WHAT MOVED AND WHAT DID NOT. The table moved; the DRIVING did not. `__go`
   closes the harness panel, unmasks three overlays, resets the world unless
   asked not to, and holds `pilotage` — a latch the engine reassigns. An
   imported binding cannot be assigned, so moving `__go` here would have meant
   exporting a setter for a private flag: one indirection traded for a worse
   one. The engine keeps the mechanics and looks the state up in the table this
   module registers.

   REGISTERED, NOT IMPORTED, in that direction. The engine must not depend on
   the module that measures it, so nothing here is reachable from there except
   through the registrar it publishes. In the other direction the dependency is
   explicit: the twenty names below are imported by name, because a source file
   that reaches its neighbour through a global says nothing about what it
   depends on.

   Every entry is `[id, label, run]`. The id is what `window.__go(id)` takes and
   what `regions.json` names; the label is what the harness panel shows.
*/
import {
  SETTINGS,
  SETTINGS_STATE,
  showSignIn,
  showStartup,
  showInstallation,
  applyState,
  store,
  openDeleteDialog,
  openFollowSheet,
  openJourneySheet,
  openMoreSheet,
  openUserSheet,
  openActionMaintenance,
  openSetting,
  openDrawer,
  settingId,
  resetSettings,
  render,
} from "./legacy.js";

const STATES = [
    [
      "pwa-android",
      "Installation — Android et bureau",
      () => {
        applyState({ page: "acq", acqTab: "now", phase: "ready" });
        showInstallation("android");
      },
    ],
    [
      "pwa-ios",
      "Installation — iOS, méthode manuelle",
      () => {
        applyState({ page: "acq", acqTab: "now", phase: "ready" });
        showInstallation("ios");
      },
    ],
    [
      "startup",
      "Démarrage — l'interface se charge",
      () => {
        applyState({ page: "acq", acqTab: "now", phase: "ready" });
        showStartup();
      },
    ],
    ["signin", "Connexion — écran d'entrée", () => showSignIn(false)],
    [
      "signin-error",
      "Connexion — identifiants refusés",
      () => showSignIn(true),
    ],
    [
      "acq-now-idle",
      "Acquisition · En cours — état réel (repos)",
      () =>
        applyState({
          page: "acq",
          acqTab: "now",
          scen: "real",
          phase: "ready",
        }),
    ],
    [
      "acq-now-loaded",
      "Acquisition · En cours — chargé",
      () =>
        applyState({
          page: "acq",
          acqTab: "now",
          scen: "loaded",
          phase: "ready",
        }),
    ],
    [
      "acq-now-loading",
      "Acquisition · En cours — chargement",
      () =>
        applyState({ page: "acq", acqTab: "now", phase: "loading" }),
    ],
    [
      "acq-now-error",
      "Acquisition · En cours — erreur",
      () => applyState({ page: "acq", acqTab: "now", phase: "error" }),
    ],
    [
      "acq-follows-list",
      "Acquisition · Suivis — liste",
      () =>
        applyState({
          page: "acq",
          acqTab: "follows",
          followMode: "list",
          pill: "tout",
          filter: "",
          phase: "ready",
        }),
    ],
    [
      "acq-follows-group",
      "Acquisition · Suivis — groupé",
      () =>
        applyState({
          page: "acq",
          acqTab: "follows",
          followMode: "group",
          pill: "tout",
          filter: "",
          phase: "ready",
        }),
    ],
    [
      "acq-follows-grid",
      "Acquisition · Suivis — grille",
      () =>
        applyState({
          page: "acq",
          acqTab: "follows",
          followMode: "grid",
          pill: "tout",
          filter: "",
          phase: "ready",
        }),
    ],
    [
      "acq-follows-filter-empty",
      "Acquisition · Suivis — filtre sans résultat",
      () =>
        applyState({
          page: "acq",
          acqTab: "follows",
          followMode: "list",
          filter: "zzz",
          phase: "ready",
        }),
    ],
    [
      "acq-follows-pause-empty",
      "Acquisition · Suivis — « En pause » vide",
      () =>
        applyState({
          page: "acq",
          acqTab: "follows",
          followMode: "list",
          pill: "pause",
          filter: "",
          phase: "ready",
        }),
    ],
    [
      "acq-follows-error",
      "Acquisition · Suivis — erreur",
      () => applyState({ page: "acq", acqTab: "follows", phase: "error" }),
    ],
    [
      "acq-discover",
      "Acquisition · Découvrir — réserve pleine",
      () =>
        applyState({
          page: "acq",
          acqTab: "discover",
          tmdb: true,
          phase: "ready",
          sugCount: 30,
        }),
    ],
    [
      "acq-discover-posters",
      "Découvrir · affiches",
      () => {
        applyState({ page: "acq", acqTab: "discover", phase: "ready" });
        store.write({ sugMode: "poster" });
        render();
      },
    ],
    [
      "acq-discover-deck",
      "Découvrir · slide cards",
      () => {
        applyState({ page: "acq", acqTab: "discover", phase: "ready" });
        store.write({ sugMode: "deck" });
        render();
      },
    ],
    [
      "acq-discover-degraded",
      "Acquisition · Découvrir — sans compte TMDB",
      () =>
        applyState({
          page: "acq",
          acqTab: "discover",
          tmdb: false,
          phase: "ready",
        }),
    ],
    [
      "acq-discover-exhausted",
      "Acquisition · Découvrir — réserve épuisée",
      () =>
        applyState({
          page: "acq",
          acqTab: "discover",
          tmdb: true,
          phase: "ready",
          sugCount: 999,
        }),
    ],
    [
      "acq-discover-loading",
      "Acquisition · Découvrir — chargement",
      () =>
        applyState({ page: "acq", acqTab: "discover", phase: "loading" }),
    ],
    [
      "acq-add-empty",
      "Écran d'ajout — au repos",
      () => {
        applyState({ page: "acq", phase: "ready" });
        window.__screens.add("");
      },
    ],
    [
      "acq-add-results",
      "Écran d'ajout — résultats réels",
      () => {
        applyState({ page: "acq", phase: "ready" });
        window.__screens.add("star wars");
      },
    ],
    [
      "followsheet-complete",
      "Feuille de suivi — gros catalogue complet",
      () => {
        applyState({ page: "acq", acqTab: "follows", phase: "ready" });
        openFollowSheet("American Dad!");
      },
    ],
    [
      "followsheet-gaps",
      "Feuille de suivi — matrice à trous",
      () => {
        applyState({ page: "lib", libLens: "inc", phase: "ready" });
        openFollowSheet("Les aventures de Tintin");
      },
    ],
    [
      "acq-identify",
      "Recherche en mode IDENTIFIER (depuis une résolution)",
      () => {
        applyState({ page: "arr", phase: "ready", pipe: "idle" });
        store.write({
          resolveTarget: "Backrooms.2026.MULTi.2160p.WEB-DL",
        });
        window.__screens.add("Backrooms 2026", "identify");
      },
    ],
    [
      "screen-releases",
      "Écran — choisir une autre release",
      () => {
        applyState({ page: "acq", acqTab: "follows", phase: "ready" });
        window.__screens.releases("Silo");
      },
    ],
    [
      "screen-profile",
      "Écran — profil de qualité",
      () => {
        applyState({ page: "acq", acqTab: "follows", phase: "ready" });
        window.__screens.profile("Silo");
      },
    ],
    [
      "sheet-journey",
      "Feuille de parcours",
      () => {
        applyState({ page: "acq", phase: "ready" });
        openJourneySheet("Furious");
      },
    ],
    [
      "sheet-more",
      "Feuille « ⋮ » — veille et obligations",
      () => {
        applyState({ page: "acq", phase: "ready" });
        openMoreSheet();
      },
    ],
    [
      "sheet-user",
      "Menu utilisateur — profil et déconnexion",
      () => {
        applyState({ page: "acq", phase: "ready" });
        openUserSheet();
      },
    ],
    [
      "lib-grid",
      "Médiathèque · Médias — grille",
      () =>
        applyState({
          page: "lib",
          libLens: "cat",
          libMode: "grid",
          q: "",
          phase: "ready",
          selMode: false,
        }),
    ],
    [
      "lib-list",
      "Médiathèque · Médias — liste",
      () =>
        applyState({
          page: "lib",
          libLens: "cat",
          libMode: "list",
          q: "",
          phase: "ready",
          selMode: false,
        }),
    ],
    [
      "lib-search-empty",
      "Médiathèque — recherche sans résultat",
      () =>
        applyState({ page: "lib", libLens: "cat", q: "zzzz", phase: "ready" }),
    ],
    [
      "lib-incomplete",
      "Médiathèque · Incomplets",
      () => applyState({ page: "lib", libLens: "inc", phase: "ready" }),
    ],
    [
      "lib-recent",
      "Médiathèque · Récents",
      () => applyState({ page: "lib", libLens: "rec", phase: "ready" }),
    ],
    [
      "lib-selection",
      "Médiathèque — mode sélection",
      () => {
        applyState({
          page: "lib",
          libLens: "cat",
          libMode: "grid",
          phase: "ready",
          selMode: true,
        });
        // THE TITLES, because the selection is keyed by title — the three
        // rows drawn at ranks 0, 2 and 5 of the unfiltered listing, which is
        // the source's own order. french-ok: media titles, which are data.
        store.write({
          selected: new Set([
            "On l'appelait Robin des Bois",
            "Big Chicken Le complot de la malbouffe",
            "Marjorie Prime",
          ]),
        });
        render();
      },
    ],
    [
      "lib-delete",
      "Médiathèque — dialogue de suppression",
      () => {
        applyState({ page: "lib", phase: "ready" });
        openDeleteDialog("Les Animaniacs");
      },
    ],
    [
      "lib-delete-multiple",
      "Médiathèque — suppression multiple",
      () => {
        applyState({ page: "lib", phase: "ready" });
        openDeleteDialog(null, ["Les Animaniacs", "La cour de récré", "Earl"]);
      },
    ],
    [
      "lib-loading",
      "Médiathèque — chargement",
      () => applyState({ page: "lib", libLens: "cat", phase: "loading" }),
    ],
    [
      "lib-error",
      "Médiathèque — erreur",
      () => applyState({ page: "lib", libLens: "cat", phase: "error" }),
    ],
    /* The OTHER error, and it is a different surface: the page loaded, and the
       NEXT page of the list did not. It has always existed — the infinite
       scroll fails once, on purpose, to show that path for real — but only a
       long scroll reached it, so nothing could drive it and nothing measured
       the sentence it prints or the control that retries. */
    [
      "lib-error-more",
      "Médiathèque — la suite ne charge plus",
      () => {
        /* ONE write, not two: the failure has to be in force at the FIRST
           draw. Setting it afterwards lets the sentinel mount for one render,
           and a sentinel in view starts a load — which then lands 620 ms
           later, over the state, with a second page of media whose sheets are
           hollow (B-030). A state exists to show ONE thing; racing its own
           loader makes a red run say something other than what it is for. */
        /* THE FAILURE IS THE LAYER'S NOW, not a flag in the store. « The list
           loaded and then the next page did not » cannot be asked for by a
           status alone — an operation set to fail fails its FIRST call, and the
           list would never appear at all. `afterCalls: 1` lets the first page
           through and refuses the second, which is the state this exists to
           show. The reset is what makes it independent of whatever was driven
           before it. */
        window.__mocks?.reset();
        window.__mocks?.setOperationOutcome("readLibraryItems", {
          status: 500,
          afterCalls: 1,
          /* ONCE. « The next page failed » is a state whose way out is a retry
             that WORKS; an operation that keeps failing is a different state
             and draws differently. The engine said this with a `libFailedOnce`
             flag in the interface's own store. */
          failingCalls: 1,
        });
        applyState({
          page: "lib",
          libLens: "cat",
          libMode: "list",
          phase: "ready",
        });
        /* And ASK for the page that fails. The layer only fails a page somebody
           asks for, so a scenario alone leaves the list whole and the error
           nowhere — the state has to reach what it names. The waiting is the
           door's, not this state's: it is the same wait for every surface, and
           written here it would be written again for the next one. */
        window.__libraryNextPage?.();
      },
    ],
    [
      "arr-idle",
      "Arrivées — état réel (2 blocages)",
      () =>
        applyState({
          page: "arr",
          scen: "real",
          phase: "ready",
          pipe: "idle",
        }),
    ],
    [
      "arr-running",
      "Arrivées — pipeline en cours",
      () =>
        applyState({
          page: "arr",
          scen: "real",
          phase: "ready",
          pipe: "running",
        }),
    ],
    [
      "arr-queued",
      "Arrivées — un passage demandé pendant un autre",
      () =>
        applyState({ page: "arr", scen: "real", phase: "ready", pipe: "queued" }),
    ],
    [
      "arr-loaded",
      "Arrivées — chargé",
      () =>
        applyState({
          page: "arr",
          scen: "loaded",
          phase: "ready",
          pipe: "idle",
        }),
    ],
    [
      "arr-loading",
      "Arrivées — chargement",
      () => applyState({ page: "arr", phase: "loading", pipe: "idle" }),
    ],
    [
      "arr-error",
      "Arrivées — erreur",
      () => applyState({ page: "arr", phase: "error", pipe: "idle" }),
    ],
    [
      "arr-resolution",
      "Arrivées — résolution, aucun candidat",
      () => {
        applyState({ page: "arr", phase: "ready", pipe: "idle" });
        window.__screens.resolution();
      },
    ],
    [
      "arr-decision",
      "Arrivées — résolution, candidats à égalité",
      () => {
        applyState({
          page: "arr",
          scen: "loaded",
          phase: "ready",
          pipe: "idle",
        });
        window.__screens.resolution("Lucky");
      },
    ],
    [
      "mediasheet-suggestion-series",
      "Fiche — suggestion NON possédée (série)",
      () => {
        applyState({ page: "acq", acqTab: "discover", phase: "ready" });
        window.__screens.mediaSheet("The Venture Bros");
      },
    ],
    [
      "mediasheet-suggestion-movie",
      "Fiche — suggestion NON possédée (film)",
      () => {
        applyState({ page: "acq", acqTab: "discover", phase: "ready" });
        window.__screens.mediaSheet("Superman : L'Homme de demain");
      },
    ],
    [
      "mediasheet-series",
      "Fiche — série avec épisodes datés",
      () => {
        applyState({ page: "lib", phase: "ready" });
        window.__screens.mediaSheet("Silo (2023)");
      },
    ],
    [
      "mediasheet-movie",
      "Fiche — film",
      () => {
        applyState({ page: "lib", phase: "ready" });
        window.__screens.mediaSheet("Marjorie Prime");
      },
    ],
    [
      "mediasheet-no-trailer",
      "Fiche — sans bande-annonce",
      () => {
        applyState({ page: "lib", phase: "ready" });
        window.__screens.mediaSheet("Broadchurch");
      },
    ],
    [
      "mediasheet-no-poster",
      "Fiche — sans affiche",
      () => {
        applyState({ page: "lib", phase: "ready" });
        window.__screens.mediaSheet("Widow's Bay");
      },
    ],
    [
      "drawer-navigation",
      "Tiroir de navigation (hamburger)",
      () => {
        applyState({ page: "acq", phase: "ready" });
        openDrawer();
      },
    ],
    [
      "system",
      "Système — la santé de la machine",
      () => applyState({ page: "sys", phase: "ready", fault: false }),
    ],
    [
      "system-outage",
      "Système — une panne (simulée)",
      () => applyState({ page: "sys", phase: "ready", fault: true }),
    ],
    [
      "system-loading",
      "Système — chargement",
      () => applyState({ page: "sys", phase: "loading", fault: false }),
    ],
    [
      "system-error",
      "Système — erreur",
      () => applyState({ page: "sys", phase: "error", fault: false }),
    ],
    [
      "not-found",
      "Une adresse qui n'existe pas",
      () => applyState({ page: "une-page-qui-n-existe-pas", phase: "ready" }),
    ],
    [
      "profile",
      "Profil et préférences",
      () => applyState({ page: "profile", phase: "ready" }),
    ],
    [
      "maintenance",
      "Maintenance — les rubriques de commandes",
      () => applyState({ page: "maint", phase: "ready", maintTopic: null }),
    ],
    [
      "maintenance-topic",
      "Maintenance — une rubrique et ses commandes",
      () => applyState({ page: "maint", phase: "ready", maintTopic: "fix" }),
    ],
    [
      "maintenance-delete",
      "Maintenance — une commande qui supprime",
      () => {
        applyState({ page: "maint", phase: "ready", maintTopic: "clean" });
        openActionMaintenance("library-clean");
      },
    ],
    [
      "maintenance-loading",
      "Maintenance — chargement",
      () => applyState({ page: "maint", phase: "loading" }),
    ],
    [
      "settings",
      "Réglages — les rubriques",
      () => {
        resetSettings();
        applyState({ page: "cfg", phase: "ready" });
      },
    ],
    [
      "settings-topic",
      "Réglages — une rubrique",
      () => {
        resetSettings();
        SETTINGS_STATE.topic = "acquisition";
        applyState({ page: "cfg", phase: "ready" });
      },
    ],
    [
      "settings-search",
      "Réglages — recherche dans tous les réglages",
      () => {
        resetSettings();
        SETTINGS_STATE.q = "espace";
        applyState({ page: "cfg", phase: "ready" });
      },
    ],
    [
      "settings-one",
      "Réglages — un réglage, dans son panneau",
      () => {
        resetSettings();
        SETTINGS_STATE.topic = "acquisition";
        applyState({ page: "cfg", phase: "ready" });
        openSetting("thresholds:thresholds.min_free_space_staging_gb");
      },
    ],
    [
      "settings-edited",
      "Réglages — modifications en attente",
      () => {
        resetSettings();
        SETTINGS_STATE.topic = "acquisition";
        SETTINGS_STATE.modifs.set(
          "thresholds:thresholds.min_free_space_staging_gb",
          40,
        );
        SETTINGS_STATE.modifs.set("tracker:tracker.providers.c411.enabled", false);
        applyState({ page: "cfg", phase: "ready" });
      },
    ],
    /* One state per FIELD, because a field is a shape one judges by looking at
       it. The setting each opens is found by TYPE rather than named, so a
       config change that moves a key does not silently open something else. */
    ...[
      ["boolean", "un interrupteur"],
      ["number", "un nombre"],
      ["text", "un texte"],
      ["path", "un chemin"],
      ["list", "une liste"],
      ["duration", "une durée"],
      ["structure", "une structure, qui refuse"],
      ["empty", "une valeur non définie"],
      /* The ninth, since L09. Its CONTROL is the text field — the difference is
         in how the value is READ — and that is exactly why it needs a state of
         its own: the six cron settings were rendering « 15 * * * * » where the
         reference said « toutes les heures, à la 15ᵉ minute », and no state
         showed a schedule for anyone to look at. */
      ["schedule", "un horaire, dit en toutes lettres"],
    ].map(([genre, what]) => [
      `settings-field-${genre}`,
      `Réglages — ${what}`,
      () => {
        resetSettings();
        const found = SETTINGS.flatMap((r) => r.r).find(
          (x) => x.type === genre,
        );
        SETTINGS_STATE.topic =
          SETTINGS.find((r) => r.r.includes(found))?.id ?? null;
        applyState({ page: "cfg", phase: "ready" });
        if (found) openSetting(settingId(found));
      },
    ]),
    [
      "settings-secrets",
      "Réglages — secrets et accès",
      () => {
        resetSettings();
        SETTINGS_STATE.topic = "secrets";
        applyState({ page: "cfg", phase: "ready" });
      },
    ],
    [
      "settings-read-only",
      "Réglages — instance en lecture seule",
      () => {
        resetSettings();
        SETTINGS_STATE.readOnly = true;
        applyState({ page: "cfg", phase: "ready" });
      },
    ],
    [
      "settings-restart",
      "Réglages — redémarrage nécessaire",
      () => {
        resetSettings();
        SETTINGS_STATE.redemarrage = true;
        applyState({ page: "cfg", phase: "ready" });
      },
    ],
    [
      "relay-reconnecting",
      "Temps réel — la connexion a été perdue",
      () => {
        applyState({ page: "acq", acqTab: "now", phase: "ready" });
        window.__relay.force("reconnecting");
      },
    ],
    [
      "relay-lost",
      "Temps réel — cet écran ne se met plus à jour",
      () => {
        applyState({ page: "acq", acqTab: "now", phase: "ready" });
        window.__relay.force("lost");
      },
    ],
    [
      "relay-refused",
      "Temps réel — session expirée",
      () => {
        applyState({ page: "acq", acqTab: "now", phase: "ready" });
        window.__relay.force("refused");
      },
    ],
];

// EVERY STATE STARTS FROM A GOOD CONNECTION, and that is not a courtesy to the
// three above — it is what keeps them from leaking into the other eighty-four.
// A forced condition is a global, `__go` drives one state after another in one
// document, and a state that had drawn a warning would leave the next
// eighty-three drawing it too. Wrapping here rather than asking each state to
// clean up is the same decision `window.__reset()` embodies: a state pins what
// it means to show, and everything else starts from a known place.
//
// IT IS WRAPPED HERE AND NOT IN THE ENGINE because the engine dies by
// SUBTRACTION (D5): a line added to `legacy.js` is a line someone has to take
// back out at L13. This table is the harness's own fixture, and resetting the
// harness's own seam is its work.
const WITH_A_GOOD_CONNECTION = STATES.map(([id, label, run]) => [
  id,
  label,
  () => {
    window.__relay?.reset();
    run();
  },
]);

// The engine owns the driving and looks the state up here. Registering at
// module evaluation — before the shell's body starts the engine — means the
// table is in place by the time anything can ask for a state.
window.__recordStates(WITH_A_GOOD_CONNECTION);
