# Reprise — SP4 est fini, SP5 (le langage visuel) commence

> ⚠ **SA PRÉMISSE CENTRALE EST PÉRIMÉE — ne t'en sers plus comme point d'entrée.** Ce brief
> répète que « SP5 n'a aucun périmètre écrit » et conclut « ne code pas encore, demande le
> périmètre à l'opérateur ». Ce périmètre existe : `docs/reference/frontend-architecture.md`
> porte les décisions arrêtées et les lots ordonnés, et `IMPLEMENTATION.md` porte l'état. Le
> reste du document — les mesures datées, les pièges, la façon de servir le prototype — garde sa
> valeur. **Sa § Première action, non.**
>
> ⚠ **AMENDÉ LE 2026-08-20, une seconde fois.** Deux passages de plus ont perdu leur objet, et
> les laisser enverrait la session suivante reconstruire ce qui existe :
>
> - la § « **Ce qui reste, et c'est SP5** » dit « aucun fichier de spec ou de plan SP5 » et
>   « le périmètre est à cadrer avec l'opérateur avant toute ligne de code ». Le lot **L06** est
>   écrit dans le fichier d'architecture, et une spec parquée existe
>   (`docs/superpowers/roadmap/maquette-l06/specs/`) — à ré-arbitrer, pas à réinventer ;
> - elle décrit `extract-maquette-css.py` et `parity-probe.py` comme « outillage en place et
>   vert ». **Les deux ont été supprimés par #465** avec toute la couche de traduction. Ce que
>   `parity-probe.py` mesurait est repris, autrement et pour une autre question, par
>   `frontend/maquette/oracle.py` (lot L01, PR #467).
>
> **Le pointeur qui vaut : `IMPLEMENTATION.md` § « Where the frontend work stands ».**

> **Prompt de reprise pour une session neuve.** Le contexte a été vidé : tout ce qu'il faut
> savoir est ici, et rien ici ne suppose de se souvenir d'une session précédente.
>
> **Tous les chiffres de ce document ont été mesurés le 2026-08-19**, par quatre vérifications
> indépendantes dont une adversariale. Chaque affirmation porte sa commande ou son `fichier:ligne`.
> **Un chiffre qui n'est pas daté est un chiffre qu'il faut re-mesurer avant de le citer** — la
> version précédente de ce brief en a cité sept qui étaient faux.

État de départ vérifié : `main` = `05522b12`, version **0.98.4** (`personalscraper/__init__.py:17`),
arbre propre, CI verte sur les 14 jobs.

---

## AVANT TOUT — ce qui va t'égarer

### 1. `IMPLEMENTATION.md` se contredit lui-même, et la contradiction est d'origine

`IMPLEMENTATION.md` fait **472 lignes**. Deux passages disent l'inverse l'un de l'autre :

- **ligne 270** : `### What is therefore still owed — nothing, as far as the SURFACES go`,
  suivie du tableau des surfaces (lignes 272-280) où **tout est `drawn`**.
- **ligne 358** : `**Next action:** draw the missing surfaces […] — Arrivées first`.

**Les deux ont été écrites dans le MÊME commit** (`c49e7ada`, 2026-08-14) : à l'intérieur de ce
commit, Arrivées était déjà marquée `**drawn**` à la ligne 148 pendant que la ligne 231 disait
« draw the missing surfaces ». Ce n'est donc **pas** une dérive dans le temps, et l'argument
« la ligne du bas est plus vieille » est faux — il a été essayé et réfuté par `git blame`.

**C'est le tableau qui a raison, et la preuve est matérielle, pas chronologique :**

| Preuve | Vérification |
| --- | --- |
| `frontend/maquette/design/src/pages/arrivals.tsx` existe | `ls` |
| `frontend/maquette/harness/arrivals.py` existe et porte R66 | docstring ligne 1 ; `regions.json:1106` |
| **La règle passe, exécutée sur données réelles** | `24 rules EXECUTED — no violation`, **EXIT=0**, hold vérifié contre `library.db` |
| La vague qui l'a livrée | SP4d vague 2, **PR #448, MERGED** |

**Ne redessine aucune surface.** Les 8 pages du prototype
(`account · acquisition · arrivals · host · library · maintenance · not-found · settings · system`)
couvrent le tableau ligne à ligne, et `machine.py` (89 règles) comme `address.py` (15 règles)
sortent EXIT=0.

### 2. ⚠ ANNULÉ LE 2026-08-19 — `/control` et `/pipeline` SONT à dessiner

**Ce paragraphe disait l'inverse, et l'opérateur l'a renversé le 2026-08-19.** Il est conservé
ici barré plutôt que supprimé, parce que c'est un arbitrage qui a été pris puis repris, et
qu'une session future retrouvera l'ancienne formulation dans les documents datés.

> **LA MISSION (opérateur, 2026-08-19)** : la maquette est une **nouvelle version de l'app**, et
> **TOUS les écrans sont à redessiner, tous**. Objet : une expérience utilisateur cohérente ;
> premier objectif : **figer cette interface**. Aucune surface n'est hors périmètre. Ce que la
> maquette porte déjà est **validé**. Ce qui reste n'est pas que des pages — l'UX, le langage
> d'interaction et l'architecture doivent être terminés et consolidés. **Le backend suivra
> l'interface**, après le gel : une limite backend ne justifie jamais de dessiner moins.

Donc :

- **`/control`** (« Contrôle », `nav.ts:71`) et **`/pipeline`** (`nav.ts:70`) n'ont aucune page
  dans le prototype — **ce sont deux pages DUES**, pas deux absences voulues.
- ~~« Ces deux absences sont l'arbitrage, pas un manque. Ne les dessine pas. »~~ — **faux depuis
  le 2026-08-19.**

Ce qui **survit** de l'ancien arbitrage, c'est l'argument de PLACEMENT, et il reste bon :
> **La coupe se fait par la NATURE DE L'ENNUI.** Un média en difficulté → Arrivées. Une machine
> en difficulté → Système. Un réglage → Configuration. Une commande contre la bibliothèque →
> Maintenance.

Où atterrissent les panneaux de `/control` (`ATraiterList`, `CompactHealth`, …) et de
`/pipeline` (`FlowBoard`, `PipelineControls`, `LastRunDigest`, `StalledPanel`) reste donc une
question d'UX ouverte — mais qu'ils soient dessinés ne l'est plus.

### 3. La maquette est la PROCHAINE version de l'app, pas une image de la production

Elle porte un langage visuel différent, et l'app livrée ne l'a pas adopté. Leurs CSS diffèrent
**par construction** : cet écart EST la refonte qui reste à faire.

- Un écart maquette/production n'est **jamais** un défaut de production.
- Ne « répare » jamais la production en pointant un outil vers le CSS de la maquette.
- `extract-maquette-css.py` et `parity-probe.py` ne comparent **pas** la maquette à la prod : ils
  comparent la maquette à **sa propre extraction** (l'extraction réécrit chaque sélecteur en
  `.tm X`, ce qui change la spécificité — le rendu peut bouger à texte identique).
- **`frontend/src/styles/ps/app-surface.css` est importé par PERSONNE** — vérifié sur tout le
  graphe : `main.tsx:6` → `globals.css` → `ps/styles.css` + `ps/maquette-acquisition.css` →
  `tokens/*.css`. Aucun chemin n'y mène. **Le brancher = livrer la refonte**, décision de
  l'opérateur, jamais un détail de plomberie.

### 4. Deux affirmations fausses encore présentes dans le dépôt

- **`IMPLEMENTATION.md:377`** : « CSS is extracted, never retyped ». **Faux** — aucune feuille
  d'app n'est extraite. La même phrase a été retirée de `docs/reference/product-intent.md` le
  2026-08-19 sur décision de l'opérateur ; celle-ci a survécu.
- **`IMPLEMENTATION.md:39`** : « Fifteen waves have landed ». **Faux** — le tableau en compte
  **17**, et les 17 PR ont été vérifiées `MERGED` une par une.

### 5. Se repérer dans la maquette

Son **balisage** est dans `frontend/maquette/design/src/` (`pages/`, `screens/`, `components/`),
son **CSS** dans le `<style>` de `design/refonte.html`. Greper du balisage dans `refonte.html`
ne trouve rien et fait conclure à tort qu'une surface « n'est pas dans la maquette ».

---

## Où en est le travail — mesuré, pas cité

**17 vagues livrées**, toutes squash-mergées sur `main` après CI verte et revue adversariale :
SP1, SP2, Bascule, SP3, SP4a, SP4b, SP4c, clean-code/i18n, SP4d ×4, SP4-fin ×3, English names,
« Les valeurs, les routes et les paramètres ». PR #429 #430 #431 #432 #437 #441 #442 #446 #447
#448 #449 #450 #451 #452 #453 #455 #456 — **toutes MERGED**.

| Fait | Mesure du 2026-08-19 |
| --- | --- |
| `design/refonte.html` | **4 217 lignes** ; `grep -c "<script"` → **0** ; aucun `onclick`/`onload`. Un titre et une feuille de style. |
| `design/src/engine/legacy.js` | **34 626 lignes** — le moteur, déplacé octet pour octet |
| `design/src/states.js` | **709 lignes de fichier**, dont **656 de fixture** (le CORPS du tableau, lignes 48-703 ; les délimiteurs sont sur 47 et 704) et **82 états** |
| ⚠ Comment compter les 82 | **En EXÉCUTANT le module, jamais au grep.** 74 entrées sont écrites en clair et **8 sont générées** par un `...[…].map()` (les huit états `settings-field-*`, ligne 654). Une revue adversariale a compté 74 au grep et déclaré le chiffre 82 faux ; l'exécution de `window.__recordStates` reçoit bien 82, 82 ids uniques. **Le grep lisait le balisage, pas ce qui tourne.** |
| Pages / écrans | 8 pages + 5 écrans, tous composants `.tsx`. `PAGES_OF` ne porte **aucun** `render` |

**⚠ Une exception à « chaque surface est un composant » : `/login` et le splash** restent du
balisage piloté par le moteur dans `design/index.html` (`legacy.js:11219`, `:11254`). Dessinés,
mais non migrés.

**⚠ SP4 n'a rien supprimé, il a déplacé.** Le fragment tombe de 39 561 à 4 217 lignes **parce
que le moteur a changé de fichier**. Le total de lignes a **augmenté** : 39 454 → 41 400
(`IMPLEMENTATION.md`, troisième axe). Ne lis pas « 4 217 » comme une réduction de 90 %.

**Ce qui reste dans `refonte.html` — BLOCK 1 (harnais) et BLOCK 2 (CSS de l'application) — y
reste délibérément : le contrat CSS est le sujet de SP5.**

### La preuve « 0 divergence sur 82 états » n'est PAS rejouable

Elle est réelle et elle est citée cinq fois, mais :

- ⚠ **CORRECTION du 2026-08-19** — la version précédente de cette liste disait que son
  instrument `fidelity.py` « n'est pas dans le dépôt, aucun historique git ». **C'est faux.**
  `frontend/maquette/fidelity.py` est suivi par git, ajouté par `21c54a98` (PR #447), 9 commits
  le touchent. Voir D17 : l'outil est là, c'est sa CIBLE qui a disparu ;
- les moteurs de rendu legacy dont il avait besoin sont **supprimés** — plus aucun nom `*Legacy`
  n'est joignable depuis `window.__referentiel`, et son propre docstring (lignes 4-6) annonce
  cette péremption comme voulue : « prove first, delete after » ;
- **aucun enregistrement n'est commité** ; ceux qui traînent dans `/tmp` sont invalidés — **38
  des 82 identifiants d'état n'existent plus** après le renommage anglais (#455/#456).

Et l'énoncé complet porte une disjonction que la version précédente de ce brief avait supprimée :
> « 0 divergence on 82 states, **or — where the markup changes on purpose — the rename map applied
> to the RECORDING and exact equality required** ».

**Ne cite pas ce chiffre comme une garantie courante.** Les 82 états, eux, sont actuels — et
les 38 renommés aussi : les deux versions de `states.js` (avant #455 et à HEAD) s'évaluent à
82 chacune, et 38 ids de la première ont disparu de la seconde. Mesuré deux fois, par
exécution.

**Deux inventaires d'états coexistent, et ils ne comptent pas la même chose** : **82** =
états de `states.js` ; **49** = états nommés de `regions.json` pilotés par `window.__go` et
mesurés par `parity-probe.py`. L'un n'est pas une régression de l'autre.

---

## Ce qui reste, et c'est SP5

### SP5 — le langage visuel. Son périmètre n'existe nulle part.

Vérifié : **aucun fichier de spec ou de plan SP5**. Les 12 occurrences de « SP5 » dans le dépôt
sont toutes des renvois (« the visual language stays SP5's question »,
`shell-mobile-wave-log.md:757` ; « a CSS amendment the spec reserves for SP5 », `:291`).

**Le périmètre est donc à cadrer avec l'opérateur avant toute ligne de code.** Éléments connus :

- Le contrat CSS : la partition BLOCK 1 / BLOCK 2, l'allowlist `exportedSelectors` de
  `regions.json` (**461 entrées**), et ce que l'extraction a le droit d'exporter.
- **Six tokens existent dans le prototype** (`refonte.html:62-65`, `:69-70`) : `--mq-shadow-toast`,
  `--mq-shadow-pop`, `--mq-shadow-carte`, `--mq-shadow-badge`, `--mq-scrim-doux`,
  `--mq-tile-overlay`. **`frontend/src/styles/ps/tokens/maquette.css` en porte déjà UN**
  (`--mq-shadow-toast`, ligne 15) → **cinq sont dus**, pas six. Vérifie la liste contre la sortie
  de l'extraction, jamais contre cette phrase : en ajouter cinq sans regarder laisse le sixième
  nommé-mais-non-défini, qui est exactement la forme du piège B-014.
- Outillage en place et vert : `scripts/extract-maquette-css.py --check` (dérive textuelle,
  3 827 lignes générées) et `scripts/parity-probe.py` (identité de **rendu** — **51 régions ×
  49 états**). **Ne cite pas de nombre de mesures : lance la sonde et lis son résumé.**
  ⚠ `parity-probe.py:20` annonce « 53 selectors » alors que `regions.json` en déclare **51** —
  entête à corriger.

### Les trois questions d'architecture — chiffres DATÉS, à re-mesurer

`IMPLEMENTATION.md` § « The third axis » porte des mesures du **2026-08-16**, faites **avant**
le découpage du fichier unique. Elles ne sont plus vraies.

| Question | Ce que dit le doc | Mesure du 2026-08-19 |
| --- | --- | --- |
| **1. Par où entre une donnée ?** | 83 jeux de constantes | **~86** (dépend de la regex ; aucun script ne produit « 83 »). Le triage reste entier : combien sont vérifiées contre leur source, combien sont un couplage. |
| **2. Qui possède l'état ?** | 265 accès directs | **142** `state.` + **99** `currentState()`. La baisse vient de SP4-fin vague 3 qui a tué l'alias. **Reste LA question entière** : elle ne peut être réglée sans décider d'abord comment découper le prototype. |
| **3. Où vit une route ?** | réglé | **Confirmé.** L'URL porte l'état dans sa QUERY (décision assumée : le document s'ouvre aussi depuis `file://`). R69, `harness/url_state.py`. |

Les quatre règles qui retournent à la source vivante **à l'exécution** sont vérifiées :
R66 → `pipeline_run` dans `library.db` · R67 → `pm2 jlist` · R68 → `~/.torrentmate/config/web.json5`
· R63 → `.data/acquire.db`.

### Dettes résiduelles de SP4-fin — noms mis à jour

- **`__go` n'a pas migré côté coquille** (`legacy.js:11445`). Argumenté, **ouvert à
  contestation** : il détient `pilotage`, un verrou que le moteur réassigne, et une liaison
  importée n'est pas assignable.
- **Le délai de 240 ms survit** (`legacy.js:11953`, `:11961`). ⚠ **`data-suivante` n'existe
  plus** — renommé **`data-next`**. Le plan SP4-fin cite encore l'ancien nom.
- **Le chemin d'entrée profonde** : `resolveTarget` est vivant. ⚠ **`relTitre` est mort**,
  renommé `relatedTitle` ; il reste **trois commentaires périmés** (`shell.tsx:91`, `:493`,
  `data.ts:567`).

### Le registre de bugs

**2 `open`** — B-024 (« `data-go` settles ONE history entry, layers pile ») et B-030 (« 87 library
sheets carry no genre and no cast ») — et **13 `to confirm`**, 3 `closed`.
**Re-compte depuis `BUGS.md:32-55` avant de citer** : un grep sur le fichier entier avale le
tableau de vocabulaire d'en-tête et donne 3/22.

---

## Règles de travail — non négociables

- **Une branche par vague**, squash-merge sur `main` après CI verte **et** revue adversariale
  finale propre. Instruction permanente de l'opérateur. **Cela vaut aussi pour une correction de
  deux lignes dans un `.md` : on ne commite jamais sur `main`.**
- **Réclamer un ticket qui EXISTE DÉJÀ sur le tableau** avant de le coder :
  `/kanban-work <ticket>`, pour que le démon KanbanMate autonome reste à l'écart.
  ⚠ **Ne PAS créer un ticket pour un travail qu'on va faire dans la session en cours**
  (opérateur, 2026-08-19) : la procédure existe pour éviter la collision avec le démon, pas
  comme rituel de comptabilité. Inventer et réclamer une carte pour ce travail-là est
  contre-productif.
- **Avant chaque commit de gate** : `make lint` (0 erreur) · `make test` (0 failed, 0 error —
  une ERROR signifie que la COLLECTE a planté) · `make check`.
- **Bump de version à CHAQUE PR** (règle opérateur), patch par défaut, dans le même commit.
- Clone neuf : `pip install -e ".[dev]"` puis `./hooks/install.sh`.
- Toute PR web **cite les §§ de `docs/reference/product-intent.md`** qu'elle sert (constitution
  BINDING). §15 : la maquette se modifie D'ABORD, se vérifie avec son harnais, et le code en est
  dérivé ensuite. Jamais l'inverse.
- **Rien ne dérive de code d'app** tant que le jugement de l'opérateur n'est pas passé —
  `product-intent.md:309` : « Tant que ce jugement n'est pas passé, on ne dérive aucun code
  d'app depuis la maquette. » La production continue de servir la SPA livrée, intouchée.
- **Un correctif de bug porte une règle qui MORD**, mutation-testée : casser exprès, vérifier que
  la règle tombe et nomme le bon défaut, restaurer. Une règle qui n'a jamais mordu ne prouve rien.
- **La règle doit couvrir le chemin que l'opérateur emprunte réellement** — chargement à froid,
  vrai doigt, vrai menu de navigateur.
- **Une empreinte par capture d'écran n'est pas un oracle** (8 à 15 états divergent entre deux
  captures du même fichier). Rectangles englobants + sous-ensemble de styles calculés.
- **Un événement synthétique n'est pas un doigt** — il n'est jamais annulé.
- **« Ça ne peut pas affecter la production » est une MESURE, pas un argument.**
- **Une commande en échec n'est pas un no-op : c'est une édition qui n'a pas eu lieu.**
- Pas de français dans le code, textes d'interface en i18n — `scripts/check-no-french.py`,
  **12 bras** (`:1074-1085`). ⚠ `CLAUDE.md:252` dit « eleven » et le script lui-même dit
  « 4 arms » : les trois comptes divergent, seul `:1074-1085` fait foi.

---

## Comment faire tourner tout ça — corrigé, la version précédente était fausse

**Il y a DEUX serveurs, et le harnais n'en mesure qu'un.**

| | Port | Quoi | Qui le lance |
| --- | --- | --- | --- |
| **Hôte du harnais** | **8899** | `http.server` nu, enraciné dans `/private/tmp/tm-refonte`, sert `wrapped.html` (la COPIE du build) | à la main — **souvent déjà lancé** |
| **Hôte design** | **8712** | `serve.py`, **protégé par mot de passe scrypt** (`tm-design.iznogoudatall.xyz`) | PM2 (`torrentmate-design`) |

`harness/common.py:17` → `PROTOTYPE = "http://127.0.0.1:8899/wrapped.html"`.
`harness/server.py:37` → `RESERVED_PORTS = (8710, 8711, 8712, 8899)`.

**`python3 serve.py 8899` est FAUX** (recette héritée, antérieure à `serve.py`) : `serve.py` répond
**401** sans session, et le harnais mesurerait alors **l'écran de connexion** — un run vert sur
rien. Jamais non plus sur **8710/8711** (le reverse-proxy y route prod et staging).

```bash
# 1. Reconstruire et rafraîchir la copie que le harnais lit — AVANT CHAQUE RUN.
cd frontend/maquette/design
npm run build
cp dist/index.html /tmp/tm-refonte/wrapped.html
rm -rf /tmp/tm-refonte/vite && { [ -d dist/vite ] && cp -R dist/vite /tmp/tm-refonte/vite || true; }
ln -sfn "$(git rev-parse --show-toplevel)/frontend/maquette/design/assets" /tmp/tm-refonte/assets

# 2. L'hôte du harnais — vérifier avant de lancer, il tourne déjà la plupart du temps.
lsof -nP -iTCP:8899 -sTCP:LISTEN || (cd /private/tmp/tm-refonte && python3 -m http.server 8899 --bind 127.0.0.1 &)

# 3. Les règles. 52 fichiers, 51 règles (common.py = plomberie partagée).
cd ../harness
for s in *.py; do
  [ "$s" = common.py ] && continue
  python3 "$s" > /dev/null || echo "FAILED: $s"
done
```

**Playwright** tourne sous **`python3` du projet (3.12.4, Playwright 1.62.0)** comme sous
`/Users/izno/.pyenv/versions/3.11.9/bin/python3` (1.49.1). Le chemin 3.11.9 en dur n'est plus
nécessaire (PM2 le garde pour `serve.py`).

**Deux pièges payés deux fois chacun.** Une copie périmée des scripts vit dans `/tmp/tm-refonte` :
y exécuter mesure la version précédente. Et `wrapped.html` non recopié mesure le build d'avant.

Chaque script échoue par son **code de sortie** (`common.Journal.summary()` → `raise SystemExit(1)`),
jamais par sa sortie texte.

`pwa.py` mesure l'hôte **VIVANT** `tm-design.iznogoudatall.xyz`, ni 8899 ni 8712.
Après toute édition de `serve.py` : `pm2 restart torrentmate-design`.

**Sécurité machine (obligatoire).** Tout `rg` porte `--type py` ou `-g '*.ext'` —
`tests/e2e/perf/.fixture/` fait 14 Go et un `rg` nu fait tomber la machine. Tout `curl`/`wget`
porte `--connect-timeout 10 --max-time 30`. ⚠ `docs/` est ignoré par le gitignore global : `rg`
le saute en silence, utiliser `--no-ignore` pour y chercher.

---

## LES DÉFAUTS À CORRIGER — TOUS, SANS EXCEPTION

**Instruction de l'opérateur : les défauts ci-dessous sont corrigés dans la PREMIÈRE branche
de la prochaine session, avant tout travail SP5.** *(Cette phrase annonçait « 16 » quand la
section « Première action » en annonçait 17 — le brief se contredisait sur son propre décompte.
La correction a porté sur D1→D19 : D18 et D19 ont été trouvés en vérifiant les autres.)* Ils ont été trouvés le 2026-08-19 par quatre
vérifications indépendantes dont une adversariale. Chacun porte son fichier, sa ligne et sa
correction. Aucun n'est « mineur » : ce sont exactement les phrases qui ont fait perdre des
sessions entières.

**Commiter aussi ce brief lui-même** (`docs/superpowers/handoffs/2026-08-19-sp5-langage-visuel.md`,
non commité à ce jour — `docs/` est ignoré par le gitignore global, donc `git add -f`).

### A. `IMPLEMENTATION.md` — huit défauts

| # | Ligne | Ce qui est écrit | Correction |
| --- | --- | --- | --- |
| **D1** | `:39` | « **Fifteen** waves have landed » | **dix-sept** — le tableau `:68-84` a 17 lignes, les 17 PR vérifiées `MERGED` |
| **D2** | `:180` | ```cd frontend/maquette && python3 serve.py 8899``` | **FAUX et dangereux.** `serve.py` est l'hôte design **8712**, protégé par mot de passe : il répond **401** et le harnais mesurerait l'écran de connexion — un run vert sur rien. Le harnais lit `http://127.0.0.1:8899/wrapped.html` (`harness/common.py:17`), servi par un `http.server` **nu** enraciné dans `/private/tmp/tm-refonte`. Remplacer par le bloc « Comment faire tourner tout ça » de ce brief. |
| **D3** | `:183-184` | « a plain `http.server` would serve the sources and measure nothing real » | **Trompeur** : le harnais utilise précisément un `http.server` nu — mais enraciné sur la **copie du BUILD**, pas sur les sources. Reformuler pour distinguer « servir `design/` » de « servir `/tmp/tm-refonte` ». |
| **D4** | `:358` | « **Next action:** draw the missing surfaces […] Arrivées first » | **Périmé** — contredit par le tableau `:270-280` où tout est `drawn`. Les deux viennent du **même commit** `c49e7ada` : contradiction d'origine. Supprimer la ligne, ou la remplacer par « cadrer SP5 avec l'opérateur ». |
| **D5** | `:377` | « **CSS is extracted, never retyped.** » | **Faux** — aucune feuille d'app n'est extraite ; `app-surface.css` n'est importé par personne. La même phrase a été retirée de `product-intent.md` le 2026-08-19 sur décision de l'opérateur. Retirer, ou marquer explicitement comme cible de SP5. |
| **D6** | `:296-304` | « 83 » constantes, « 265 » accès directs à `state.`, et les autres mesures du troisième axe | **Datées du 2026-08-16**, faites **avant** le découpage du fichier unique. Re-mesuré le 2026-08-19 : `state.` → **142** (+ **99** `currentState()`), constantes → **~86** (dépend de la regex). **Aucun script ne produit « 83 » ni « 265 ».** Soit dater la colonne, soit écrire la commande qui la re-mesure. |
| **D7** | `:51`, `:62`, `:82` | « the **656**-line scenario table » | **Ambigu** : le FICHIER `states.js` fait **709** lignes, la FIXTURE en fait **656** (`const STATES = [` ligne 47 → `];` ligne 704). Écrire les deux. |
| **D8** | `:56`, `:80`, `:92` | « **0 divergence on 82 states** » | **Vrai mais IRREJOUABLE**, et amputé de sa disjonction. Voir D16. Ajouter le caveat et restaurer l'énoncé complet du wave-log : « …**or — where the markup changes on purpose — the rename map applied to the RECORDING and exact equality required** ». |

### B. `CLAUDE.md` — un défaut

| # | Ligne | Ce qui est écrit | Correction |
| --- | --- | --- | --- |
| **D9** | `:252` | « `scripts/check-no-french.py` (**eleven** arms…) » | **douze** — comptés à `scripts/check-no-french.py:1074-1085` |

### C. Code livré — trois défauts d'auto-description

| # | Fichier:ligne | Ce qui est écrit | Correction |
| --- | --- | --- | --- |
| **D10** | `scripts/parity-probe.py:20` | « regions   **53** selectors » | **51** (`regions.json`). Deux régions mortes ont été supprimées sans que l'entête suive. |
| **D11** | `scripts/check-no-french.py:10`, `:1068`, `:1100` | « **Four** arms », « Runs the **four** arms », « **4 arms** + the vocabulary + … » | **douze**. L'énumération de `:1100` omet `dictionary`, `app_interface_text` et `test_prose`. **Trois comptes divergents dans trois fichiers, aucun juste** — c'est de là que venait le « 11 ». |
| **D12** | `scripts/check-no-french.py` | — | Envisager un bras qui **compte les bras** et refuse une auto-description fausse. Un compte que personne ne compare est un compte que personne ne lit. |

### D. Restes du renommage anglais (#455/#456) — quatre défauts

`relTitre` a été renommé `relatedTitle`, et `data-suivante` en `data-next`. Quatre références
à l'ancien nom ont survécu — dans des **commentaires**, donc invisibles aux gardes :

| # | Fichier:ligne | Correction |
| --- | --- | --- |
| **D13** | `frontend/maquette/design/src/data.ts:567` | `state.relTitre` → `state.relatedTitle` |
| **D14** | `frontend/maquette/design/src/shell.tsx:91` | `state.relTitre` → `state.relatedTitle` |
| **D15** | `frontend/maquette/design/src/shell.tsx:493` | `state.relTitre` → `state.relatedTitle` |
| **D16** | `docs/superpowers/plans/2026-08-18-maquette-sp4fin-le-moteur-meurt.md:171-172` | `relTitre` → `relatedTitle` **et** `data-suivante` → `data-next` |

**Leçon à retenir, pas seulement à corriger** : la campagne de renommage a laissé quatre traces
parce que **aucun bras ne lit les commentaires**. Un identifiant mort cité dans un commentaire
envoie le lecteur suivant chercher un symbole qui n'existe plus.

### E. Un artefact manquant — la preuve la plus citée du projet

| # | Quoi | État |
| --- | --- | --- |
| **D17** | `fidelity.py` — l'instrument de « 0 divergence sur 82 états » | ⚠ **La prémisse de ce brief était FAUSSE et a été corrigée le 2026-08-19 :** `frontend/maquette/fidelity.py` **EST commité** — suivi par git, ajouté par `21c54a98` (PR #447), 9 commits le touchent (`git log --oneline -- frontend/maquette/fidelity.py`). Ce qui reste vrai, et qui est vérifié : plus aucun nom `*Legacy` n'est joignable depuis `window.__referentiel`, donc le chemin de comparaison vivante n'a plus de cible ; **aucun enregistrement n'est commité** ; ceux de `/tmp` sont invalidés — **38 des 82 identifiants d'état n'existent plus** (mesuré en comparant `states.js` à sa version d'avant #455). **Et surtout : cette péremption est VOULUE et documentée** — le docstring de l'outil, lignes 4-6, dit « it stops being runnable the moment the legacy renderer it compares against is deleted. That order is the point: prove first, delete after. » L'outil est un instrument de transition qui a fait son travail, pas un artefact perdu. L'arbitrage soumis à l'opérateur n'est donc plus « commiter ou déclasser » mais : (a) laisser l'outil en place tel quel et se contenter du caveat désormais écrit dans `IMPLEMENTATION.md`, ou (b) lui redonner une cible (un moteur de référence figé + un enregistrement commité) pour que la formule redevienne rejouable. **Fait en attendant** : le caveat est écrit, la disjonction complète est restaurée, et la formule n'est plus citée comme une garantie courante. |

### E bis. Trouvés en vérifiant les autres — corrigés dans la même branche

| # | Fichier:ligne | Ce qui était écrit | Correction |
| --- | --- | --- | --- |
| **D18** | `frontend/maquette/README.md:168-169` | `state.relTitre` **et** `data-prendre` | **Cinquième et sixième restes du renommage**, que la liste D13→D16 n'avait pas vus — dans le document que `CLAUDE.md` impose de lire AVANT toute évolution de design, donc le plus coûteux des six. → `state.relatedTitle`, `data-take`. |
| **D19** | `IMPLEMENTATION.md:373` | « `$adversarialReview` (**65** rules) et `$methodLessons` (**37**) » | **80** et **43**, mesurés (`python3 -c "import json; d=json.load(open('frontend/maquette/regions.json'))['\$adversarialReview']; print(len([k for k in d if k.startswith('R')]), len(d['\$methodLessons']))"`). Même classe de défaut que D1 et D6 : un compte que personne ne recompte. `$methodLessons` est en outre **imbriqué dans** `$adversarialReview`, pas frère de lui. |

**Encore non corrigé, signalé à l'opérateur** : `IMPLEMENTATION.md` est un document anglais qui
contient une ligne entièrement française (le tableau des vagues, ligne #456). `CLAUDE.md`
§Language interdit de mélanger deux langues dans un document. Traduire cette ligne est une
édition de fond, pas une correction de chiffre — elle attend l'accord de l'opérateur.

### F. Environnement — à signaler, pas à corriger sans accord

Un **second écouteur** occupe le port 8899 : PID 56167, lié à `*:8899` (**toutes interfaces**,
IPv6) au lieu de `127.0.0.1` comme le PID 25266 légitime. Exposition mineure mais réelle.
**Ne rien tuer sans l'accord de l'opérateur** — vérifier d'abord à qui il appartient.

---

## Première action

**Ne code pas encore.** SP5 n'a aucun périmètre écrit, et le prototype est dans un état stable et
prouvé — c'est le moment de cadrer, pas de deviner.

1. **Ouvrir une branche** (jamais sur `main`) et corriger **les défauts D1→D19** de la
   section ci-dessus — **tous, c'est l'instruction explicite de l'opérateur**, D17 étant un
   arbitrage à lui soumettre plutôt qu'une édition. *(Fait le 2026-08-19, branche
   `fix/mend-selfdescription`, ticket #461.)* Commiter ce brief dans la même branche
   (`git add -f`, `docs/` est gitignoré). Gates : `make lint && make test && make check`,
   bump de version, revue adversariale avant merge.
2. Lire `frontend/maquette/README.md`, puis `BUGS.md`.
3. **Demander à l'opérateur le périmètre de SP5** — quel langage visuel, sur quelles surfaces,
   dans quel ordre — avant d'ouvrir la branche de la vague.

**Alternative que l'opérateur peut préférer** : vider le registre d'abord (2 `open`,
13 `to confirm`) avant d'ouvrir SP5. **Lui demander.**
