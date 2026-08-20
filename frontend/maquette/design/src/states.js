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
} from "./engine/legacy.js";

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
        applyState({ page: "acq", acqTab: "now", phase: "chargement" }),
    ],
    [
      "acq-now-error",
      "Acquisition · En cours — erreur",
      () => applyState({ page: "acq", acqTab: "now", phase: "erreur" }),
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
      "acq-follows-groupe",
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
      () => applyState({ page: "acq", acqTab: "follows", phase: "erreur" }),
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
        applyState({ page: "acq", acqTab: "discover", phase: "chargement" }),
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
        applyState({ page: "arr", phase: "ready", pipe: "repos" });
        store.write({
          resolveTarget: "Backrooms.2026.MULTi.2160p.WEB-DL",
        });
        window.__screens.add("Backrooms 2026", "identifier");
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
        store.write({ selected: new Set([0, 2, 5]) });
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
      () => applyState({ page: "lib", libLens: "cat", phase: "chargement" }),
    ],
    [
      "lib-error",
      "Médiathèque — erreur",
      () => applyState({ page: "lib", libLens: "cat", phase: "erreur" }),
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
        applyState({
          page: "lib",
          libLens: "cat",
          libMode: "list",
          phase: "ready",
          libFailedOnce: true,
          libErr: true,
        });
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
          pipe: "repos",
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
          pipe: "encours",
        }),
    ],
    [
      "arr-queued",
      "Arrivées — un passage demandé pendant un autre",
      () =>
        applyState({ page: "arr", scen: "real", phase: "ready", pipe: "file" }),
    ],
    [
      "arr-loaded",
      "Arrivées — chargé",
      () =>
        applyState({
          page: "arr",
          scen: "loaded",
          phase: "ready",
          pipe: "repos",
        }),
    ],
    [
      "arr-loading",
      "Arrivées — chargement",
      () => applyState({ page: "arr", phase: "chargement", pipe: "repos" }),
    ],
    [
      "arr-error",
      "Arrivées — erreur",
      () => applyState({ page: "arr", phase: "erreur", pipe: "repos" }),
    ],
    [
      "arr-resolution",
      "Arrivées — résolution, aucun candidat",
      () => {
        applyState({ page: "arr", phase: "ready", pipe: "repos" });
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
          pipe: "repos",
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
      "system-panne",
      "Système — une panne (simulée)",
      () => applyState({ page: "sys", phase: "ready", fault: true }),
    ],
    [
      "system-loading",
      "Système — chargement",
      () => applyState({ page: "sys", phase: "chargement", fault: false }),
    ],
    [
      "system-error",
      "Système — erreur",
      () => applyState({ page: "sys", phase: "erreur", fault: false }),
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
      () => applyState({ page: "maint", phase: "chargement" }),
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
];

// The engine owns the driving and looks the state up here. Registering at
// module evaluation — before the shell's body starts the engine — means the
// table is in place by the time anything can ask for a state.
window.__recordStates(STATES);
