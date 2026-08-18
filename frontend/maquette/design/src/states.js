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
  REG_ETAT,
  showSignIn,
  showStartup,
  showInstallation,
  applyState,
  magasin,
  openDeleteDialog,
  openFollowSheet,
  openJourneySheet,
  openPlusSheet,
  openUserSheet,
  openActionMaintenance,
  openSetting,
  openDrawer,
  reglageId,
  resetSettings,
  render,
} from "./engine/legacy.js";

const STATES = [
    [
      "pwa-android",
      "Installation — Android et bureau",
      () => {
        applyState({ page: "acq", acqTab: "maintenant", phase: "prete" });
        showInstallation("android");
      },
    ],
    [
      "pwa-ios",
      "Installation — iOS, méthode manuelle",
      () => {
        applyState({ page: "acq", acqTab: "maintenant", phase: "prete" });
        showInstallation("ios");
      },
    ],
    [
      "demarrage",
      "Démarrage — l'interface se charge",
      () => {
        applyState({ page: "acq", acqTab: "maintenant", phase: "prete" });
        showStartup();
      },
    ],
    ["connexion", "Connexion — écran d'entrée", () => showSignIn(false)],
    [
      "connexion-erreur",
      "Connexion — identifiants refusés",
      () => showSignIn(true),
    ],
    [
      "acq-encours-repos",
      "Acquisition · En cours — état réel (repos)",
      () =>
        applyState({
          page: "acq",
          acqTab: "maintenant",
          scen: "reel",
          phase: "prete",
        }),
    ],
    [
      "acq-encours-charge",
      "Acquisition · En cours — chargé",
      () =>
        applyState({
          page: "acq",
          acqTab: "maintenant",
          scen: "charge",
          phase: "prete",
        }),
    ],
    [
      "acq-encours-chargement",
      "Acquisition · En cours — chargement",
      () =>
        applyState({ page: "acq", acqTab: "maintenant", phase: "chargement" }),
    ],
    [
      "acq-encours-erreur",
      "Acquisition · En cours — erreur",
      () => applyState({ page: "acq", acqTab: "maintenant", phase: "erreur" }),
    ],
    [
      "acq-suivis-liste",
      "Acquisition · Suivis — liste",
      () =>
        applyState({
          page: "acq",
          acqTab: "suivis",
          followMode: "list",
          pill: "tout",
          filtre: "",
          phase: "prete",
        }),
    ],
    [
      "acq-suivis-groupe",
      "Acquisition · Suivis — groupé",
      () =>
        applyState({
          page: "acq",
          acqTab: "suivis",
          followMode: "group",
          pill: "tout",
          filtre: "",
          phase: "prete",
        }),
    ],
    [
      "acq-suivis-grille",
      "Acquisition · Suivis — grille",
      () =>
        applyState({
          page: "acq",
          acqTab: "suivis",
          followMode: "grid",
          pill: "tout",
          filtre: "",
          phase: "prete",
        }),
    ],
    [
      "acq-suivis-filtre-vide",
      "Acquisition · Suivis — filtre sans résultat",
      () =>
        applyState({
          page: "acq",
          acqTab: "suivis",
          followMode: "list",
          filtre: "zzz",
          phase: "prete",
        }),
    ],
    [
      "acq-suivis-pause-vide",
      "Acquisition · Suivis — « En pause » vide",
      () =>
        applyState({
          page: "acq",
          acqTab: "suivis",
          followMode: "list",
          pill: "pause",
          filtre: "",
          phase: "prete",
        }),
    ],
    [
      "acq-suivis-erreur",
      "Acquisition · Suivis — erreur",
      () => applyState({ page: "acq", acqTab: "suivis", phase: "erreur" }),
    ],
    [
      "acq-decouvrir",
      "Acquisition · Découvrir — réserve pleine",
      () =>
        applyState({
          page: "acq",
          acqTab: "decouvrir",
          tmdb: true,
          phase: "prete",
          sugCount: 30,
        }),
    ],
    [
      "acq-decouvrir-affiches",
      "Découvrir · affiches",
      () => {
        applyState({ page: "acq", acqTab: "decouvrir", phase: "prete" });
        magasin.ecrire({ sugMode: "poster" });
        render();
      },
    ],
    [
      "acq-decouvrir-deck",
      "Découvrir · slide cards",
      () => {
        applyState({ page: "acq", acqTab: "decouvrir", phase: "prete" });
        magasin.ecrire({ sugMode: "deck" });
        render();
      },
    ],
    [
      "acq-decouvrir-degrade",
      "Acquisition · Découvrir — sans compte TMDB",
      () =>
        applyState({
          page: "acq",
          acqTab: "decouvrir",
          tmdb: false,
          phase: "prete",
        }),
    ],
    [
      "acq-decouvrir-epuise",
      "Acquisition · Découvrir — réserve épuisée",
      () =>
        applyState({
          page: "acq",
          acqTab: "decouvrir",
          tmdb: true,
          phase: "prete",
          sugCount: 999,
        }),
    ],
    [
      "acq-decouvrir-chargement",
      "Acquisition · Découvrir — chargement",
      () =>
        applyState({ page: "acq", acqTab: "decouvrir", phase: "chargement" }),
    ],
    [
      "acq-ajout-vide",
      "Écran d'ajout — au repos",
      () => {
        applyState({ page: "acq", phase: "prete" });
        window.__ecrans.ajout("");
      },
    ],
    [
      "acq-ajout-resultats",
      "Écran d'ajout — résultats réels",
      () => {
        applyState({ page: "acq", phase: "prete" });
        window.__ecrans.ajout("star wars");
      },
    ],
    [
      "feuille-suivi-complet",
      "Feuille de suivi — gros catalogue complet",
      () => {
        applyState({ page: "acq", acqTab: "suivis", phase: "prete" });
        openFollowSheet("American Dad!");
      },
    ],
    [
      "feuille-suivi-trous",
      "Feuille de suivi — matrice à trous",
      () => {
        applyState({ page: "lib", libLens: "inc", phase: "prete" });
        openFollowSheet("Les aventures de Tintin");
      },
    ],
    [
      "acq-identifier",
      "Recherche en mode IDENTIFIER (depuis une résolution)",
      () => {
        applyState({ page: "arr", phase: "prete", pipe: "repos" });
        magasin.ecrire({
          resolveTarget: "Backrooms.2026.MULTi.2160p.WEB-DL",
        });
        window.__ecrans.ajout("Backrooms 2026", "identifier");
      },
    ],
    [
      "ecran-releases",
      "Écran — choisir une autre release",
      () => {
        applyState({ page: "acq", acqTab: "suivis", phase: "prete" });
        window.__ecrans.releases("Silo");
      },
    ],
    [
      "ecran-profil",
      "Écran — profil de qualité",
      () => {
        applyState({ page: "acq", acqTab: "suivis", phase: "prete" });
        window.__ecrans.profil("Silo");
      },
    ],
    [
      "feuille-parcours",
      "Feuille de parcours",
      () => {
        applyState({ page: "acq", phase: "prete" });
        openJourneySheet("Furious");
      },
    ],
    [
      "feuille-plus",
      "Feuille « ⋮ » — veille et obligations",
      () => {
        applyState({ page: "acq", phase: "prete" });
        openPlusSheet();
      },
    ],
    [
      "feuille-utilisateur",
      "Menu utilisateur — profil et déconnexion",
      () => {
        applyState({ page: "acq", phase: "prete" });
        openUserSheet();
      },
    ],
    [
      "lib-grille",
      "Médiathèque · Médias — grille",
      () =>
        applyState({
          page: "lib",
          libLens: "cat",
          libMode: "grid",
          q: "",
          phase: "prete",
          selMode: false,
        }),
    ],
    [
      "lib-liste",
      "Médiathèque · Médias — liste",
      () =>
        applyState({
          page: "lib",
          libLens: "cat",
          libMode: "list",
          q: "",
          phase: "prete",
          selMode: false,
        }),
    ],
    [
      "lib-recherche-vide",
      "Médiathèque — recherche sans résultat",
      () =>
        applyState({ page: "lib", libLens: "cat", q: "zzzz", phase: "prete" }),
    ],
    [
      "lib-incomplets",
      "Médiathèque · Incomplets",
      () => applyState({ page: "lib", libLens: "inc", phase: "prete" }),
    ],
    [
      "lib-recents",
      "Médiathèque · Récents",
      () => applyState({ page: "lib", libLens: "rec", phase: "prete" }),
    ],
    [
      "lib-selection",
      "Médiathèque — mode sélection",
      () => {
        applyState({
          page: "lib",
          libLens: "cat",
          libMode: "grid",
          phase: "prete",
          selMode: true,
        });
        magasin.ecrire({ selected: new Set([0, 2, 5]) });
        render();
      },
    ],
    [
      "lib-suppression",
      "Médiathèque — dialogue de suppression",
      () => {
        applyState({ page: "lib", phase: "prete" });
        openDeleteDialog("Les Animaniacs");
      },
    ],
    [
      "lib-suppression-multiple",
      "Médiathèque — suppression multiple",
      () => {
        applyState({ page: "lib", phase: "prete" });
        openDeleteDialog(null, ["Les Animaniacs", "La cour de récré", "Earl"]);
      },
    ],
    [
      "lib-chargement",
      "Médiathèque — chargement",
      () => applyState({ page: "lib", libLens: "cat", phase: "chargement" }),
    ],
    [
      "lib-erreur",
      "Médiathèque — erreur",
      () => applyState({ page: "lib", libLens: "cat", phase: "erreur" }),
    ],
    /* The OTHER error, and it is a different surface: the page loaded, and the
       NEXT page of the list did not. It has always existed — the infinite
       scroll fails once, on purpose, to show that path for real — but only a
       long scroll reached it, so nothing could drive it and nothing measured
       the sentence it prints or the control that retries. */
    [
      "lib-erreur-suite",
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
          phase: "prete",
          libFailedOnce: true,
          libErr: true,
        });
      },
    ],
    [
      "arr-repos",
      "Arrivées — état réel (2 blocages)",
      () =>
        applyState({
          page: "arr",
          scen: "reel",
          phase: "prete",
          pipe: "repos",
        }),
    ],
    [
      "arr-encours",
      "Arrivées — pipeline en cours",
      () =>
        applyState({
          page: "arr",
          scen: "reel",
          phase: "prete",
          pipe: "encours",
        }),
    ],
    [
      "arr-file",
      "Arrivées — un passage demandé pendant un autre",
      () =>
        applyState({ page: "arr", scen: "reel", phase: "prete", pipe: "file" }),
    ],
    [
      "arr-charge",
      "Arrivées — chargé",
      () =>
        applyState({
          page: "arr",
          scen: "charge",
          phase: "prete",
          pipe: "repos",
        }),
    ],
    [
      "arr-chargement",
      "Arrivées — chargement",
      () => applyState({ page: "arr", phase: "chargement", pipe: "repos" }),
    ],
    [
      "arr-erreur",
      "Arrivées — erreur",
      () => applyState({ page: "arr", phase: "erreur", pipe: "repos" }),
    ],
    [
      "arr-resolution",
      "Arrivées — résolution, aucun candidat",
      () => {
        applyState({ page: "arr", phase: "prete", pipe: "repos" });
        window.__ecrans.resolution();
      },
    ],
    [
      "arr-decision",
      "Arrivées — résolution, candidats à égalité",
      () => {
        applyState({
          page: "arr",
          scen: "charge",
          phase: "prete",
          pipe: "repos",
        });
        window.__ecrans.resolution("Lucky");
      },
    ],
    [
      "fiche-suggestion-serie",
      "Fiche — suggestion NON possédée (série)",
      () => {
        applyState({ page: "acq", acqTab: "decouvrir", phase: "prete" });
        window.__ecrans.fiche("The Venture Bros");
      },
    ],
    [
      "fiche-suggestion-film",
      "Fiche — suggestion NON possédée (film)",
      () => {
        applyState({ page: "acq", acqTab: "decouvrir", phase: "prete" });
        window.__ecrans.fiche("Superman : L'Homme de demain");
      },
    ],
    [
      "fiche-serie",
      "Fiche — série avec épisodes datés",
      () => {
        applyState({ page: "lib", phase: "prete" });
        window.__ecrans.fiche("Silo (2023)");
      },
    ],
    [
      "fiche-film",
      "Fiche — film",
      () => {
        applyState({ page: "lib", phase: "prete" });
        window.__ecrans.fiche("Marjorie Prime");
      },
    ],
    [
      "fiche-sans-trailer",
      "Fiche — sans bande-annonce",
      () => {
        applyState({ page: "lib", phase: "prete" });
        window.__ecrans.fiche("Broadchurch");
      },
    ],
    [
      "tiroir-navigation",
      "Tiroir de navigation (hamburger)",
      () => {
        applyState({ page: "acq", phase: "prete" });
        openDrawer();
      },
    ],
    [
      "systeme",
      "Système — la santé de la machine",
      () => applyState({ page: "sys", phase: "prete", panne: false }),
    ],
    [
      "systeme-panne",
      "Système — une panne (simulée)",
      () => applyState({ page: "sys", phase: "prete", panne: true }),
    ],
    [
      "systeme-chargement",
      "Système — chargement",
      () => applyState({ page: "sys", phase: "chargement", panne: false }),
    ],
    [
      "systeme-erreur",
      "Système — erreur",
      () => applyState({ page: "sys", phase: "erreur", panne: false }),
    ],
    [
      "introuvable",
      "Une adresse qui n'existe pas",
      () => applyState({ page: "une-page-qui-n-existe-pas", phase: "prete" }),
    ],
    [
      "profil",
      "Profil et préférences",
      () => applyState({ page: "profil", phase: "prete" }),
    ],
    [
      "maintenance",
      "Maintenance — les rubriques de commandes",
      () => applyState({ page: "maint", phase: "prete", maintRub: null }),
    ],
    [
      "maintenance-rubrique",
      "Maintenance — une rubrique et ses commandes",
      () => applyState({ page: "maint", phase: "prete", maintRub: "fix" }),
    ],
    [
      "maintenance-suppression",
      "Maintenance — une commande qui supprime",
      () => {
        applyState({ page: "maint", phase: "prete", maintRub: "clean" });
        openActionMaintenance("library-clean");
      },
    ],
    [
      "maintenance-chargement",
      "Maintenance — chargement",
      () => applyState({ page: "maint", phase: "chargement" }),
    ],
    [
      "reglages",
      "Réglages — les rubriques",
      () => {
        resetSettings();
        applyState({ page: "cfg", phase: "prete" });
      },
    ],
    [
      "reglages-rubrique",
      "Réglages — une rubrique",
      () => {
        resetSettings();
        REG_ETAT.rubrique = "acquisition";
        applyState({ page: "cfg", phase: "prete" });
      },
    ],
    [
      "reglages-recherche",
      "Réglages — recherche dans tous les réglages",
      () => {
        resetSettings();
        REG_ETAT.q = "espace";
        applyState({ page: "cfg", phase: "prete" });
      },
    ],
    [
      "reglages-un",
      "Réglages — un réglage, dans son panneau",
      () => {
        resetSettings();
        REG_ETAT.rubrique = "acquisition";
        applyState({ page: "cfg", phase: "prete" });
        openSetting("thresholds:thresholds.min_free_space_staging_gb");
      },
    ],
    [
      "reglages-modifie",
      "Réglages — modifications en attente",
      () => {
        resetSettings();
        REG_ETAT.rubrique = "acquisition";
        REG_ETAT.modifs.set(
          "thresholds:thresholds.min_free_space_staging_gb",
          40,
        );
        REG_ETAT.modifs.set("tracker:tracker.providers.c411.enabled", false);
        applyState({ page: "cfg", phase: "prete" });
      },
    ],
    /* One state per FIELD, because a field is a shape one judges by looking at
       it. The setting each opens is found by TYPE rather than named, so a
       config change that moves a key does not silently open something else. */
    ...[
      ["booleen", "un interrupteur"],
      ["nombre", "un nombre"],
      ["texte", "un texte"],
      ["chemin", "un chemin"],
      ["liste", "une liste"],
      ["duree", "une durée"],
      ["structure", "une structure, qui refuse"],
      ["nul", "une valeur non définie"],
    ].map(([genre, quoi]) => [
      `reglages-champ-${genre}`,
      `Réglages — ${quoi}`,
      () => {
        resetSettings();
        const trouve = SETTINGS.flatMap((r) => r.r).find(
          (x) => x.type === genre,
        );
        REG_ETAT.rubrique =
          SETTINGS.find((r) => r.r.includes(trouve))?.id ?? null;
        applyState({ page: "cfg", phase: "prete" });
        if (trouve) openSetting(reglageId(trouve));
      },
    ]),
    [
      "reglages-secrets",
      "Réglages — secrets et accès",
      () => {
        resetSettings();
        REG_ETAT.rubrique = "secrets";
        applyState({ page: "cfg", phase: "prete" });
      },
    ],
    [
      "reglages-lecture-seule",
      "Réglages — instance en lecture seule",
      () => {
        resetSettings();
        REG_ETAT.lectureSeule = true;
        applyState({ page: "cfg", phase: "prete" });
      },
    ],
    [
      "reglages-redemarrage",
      "Réglages — redémarrage nécessaire",
      () => {
        resetSettings();
        REG_ETAT.redemarrage = true;
        applyState({ page: "cfg", phase: "prete" });
      },
    ],
];

// The engine owns the driving and looks the state up here. Registering at
// module evaluation — before the shell's body starts the engine — means the
// table is in place by the time anything can ask for a state.
window.__enregistrerEtats(STATES);
