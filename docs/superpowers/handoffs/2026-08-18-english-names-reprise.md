# Reprise — « plus de français » (branche `refactor/english-names`, PR #455)

## Ce que l'opérateur a demandé, et la condition de fusion

Son message d'origine : « data-suivante, trierLib, …. encore beaucoup d'éléments
utilise des noms français ». Puis, deux fois : **« merge quand tout est vérifié
complètement, plus de français, pas de régression, tous les tests passent,
toutes les règles sont respectées »**.

Il a tranché deux arbitrages, par `AskUserQuestion` :

1. **Renommer TOUT le moteur** (et non « garder l'exempté comme dette »).
2. **Les attributs `data-*` entrent dans la règle** — et CLAUDE.md est amendé en
   conséquence (leur exclusion explicite est levée).

Il a ensuite contesté les gels : « pourquoi des frozen-with-reason (ecrans,
panneau, pont, refonte.html, fiche) ? Pour refonte.html je comprends car il est
destiné à disparaître. Mais les autres ? » — **il avait raison** : trois de ces
quatre gels étaient des reports habillés en principes. Ils sont dégelés.

## État

- Branche `refactor/english-names`, PR #455, version **0.97.34**.
- La CI était verte 12/12 sur `7fee3ba8`. **Une passe de garant a ensuite trouvé cinq
  choses qu'une porte verte ne peut pas voir**, l'opérateur a tranché « on corrige TOUT
  ce qui n'est pas amené à disparaître », et le travail est fait.

### Ce que la passe de garant a trouvé, et ce qui a été corrigé

| Constat | Correctif |
| --- | --- |
| `code-vocabulary.txt` était **semé depuis le code**, donc les 25 mots français dont 29 noms de `legacy.js` avaient besoin y sont entrés avec les autres : le bras censé les attraper les autorisait | Ils sont sous une bannière, nommés comme français assumés, et `check_french_debt` les refuse à tout fichier sauf le moteur mourant |
| Les noms `data-*` avaient une règle et **aucun bras** : `data-prendre`, `data-maintrub`, `data-qreg`, `data-apparence` étaient restés | Bras `check_data_attributes`, qui pose la question du vocabulaire ; les trois vivants sont `data-take`, `data-maintopic`, `data-qsettings` |
| `frontend/scripts/` n'est pas `scripts/` : un outil entier (18 noms français) hors de tout bras | Ajouté au bras identifiants ; l'outil est renommé |
| La liste de mots français avait encore ses trous (`traiter`, `maintenant`, `controle`, `cherche`, `faits`, …) et **l'app de production dormait dessous** | 40 mots mesurés ajoutés ; `components/controle/` → `control/`, `ATraiterList` → `ToHandleList`, `MaintenantPanel` → `NowPanel`, `Medias` → `MediaLibrary`, 19 identifiants |
| L'outil de renommage **corrompait des textes d'interface en silence**, par quatre formes | Il lit ses zones protégées dans le parseur de TypeScript (`scripts/source-spans.mjs`) et refuse d'écrire un fichier dont une zone protégée bouge |

Les quatre formes : un littéral d'expression régulière portant une apostrophe
(`/n'est plus cherché/i`) désynchronisait le parseur pour tout le reste du fichier ; le
texte JSX ne porte pas de guillemets ; l'opérateur de décomposition `...` ressemble à un
accès membre (renommage à moitié fait) ; et en Python un `[…]` est aussi une liste.
**La première avait déjà frappé dans le travail commité** : `audit.py` portait
`retrait:'Retirer le isFollowed'` et `library_sort.py` une tenue nommée « add récent ».
Les deux sont réparées.

### Preuves, sur l'arbre courant

| Contrôle | Résultat |
| --- | --- |
| `make test` | **10 703 passés**, 0 échec |
| `make check-frontend` | typecheck + lint + **1 364 tenues** + build, verts |
| `make lint` | vert (ruff, format, mypy 484 fichiers, logging) |
| `check-no-french` | vert — 4 bras + vocabulaire + **data-\*** + **dette déclarée** + registre |
| Mutations de garde | un nom français, un `data-*` français et un emprunt à la dette font rougir, chacun pour sa raison |
| Zones protégées | **0 fichier sur 19** dont une chaîne, un morceau de gabarit, une regex ou un texte JSX a bougé |
| `extract-maquette-css --check` · `audit_design_coverage --strict` · pragma · typed-api · registry-catch · cli-coverage · feature-map · version-bump | verts |
| Audit INDÉPENDANT (dictionnaires anglais + français d'aspell, hors dépôt) | plus aucun identifiant français hors des catégories assumées |

## Ce qui reste français, délibérément

- **`design/src/engine/legacy.js`** — 29 noms, 24 mots. SP4-fin le démantèle. Dette
  **déclarée** dans `code-vocabulary.txt` et **bornée** par `check_french_debt`.
- `refonte.html`, `maquette` — nommés par R72 et par la constitution §15.
- Le vocabulaire d'états, qui est de la **donnée** : `en_attente`, `a_jour`, `non_verifie`,
  `en_acquisition`, `a_recuperer`, `annonce` — gelés avec leur raison dans `regions.json`.
- Les VALEURS : ids d'état, ids de page, thèmes, onglets, adresses (`/fiche/$titre`).
- `docs/` : des enregistrements datés ne se réécrivent pas.
- Le français que les tenues ASSERTENT — c'est la sortie rendue.

## Ce qui a été fait (pour ne pas le refaire)

| Lot | Contenu |
| --- | --- |
| 1 | 106 identifiants purs |
| 2a | 29 noms qui sont aussi des propriétés (+ `liste` en liaison seule) |
| 2b | `etat` + l'API du magasin (`lire`→`read`, `ecrire`→`write`, `adopterEtat`, `adopterMonde`, `toucher`, `monde`→`world`) |
| contrats | 19 noms `data-*`, dont `data-suivante`→`data-next`, `data-cle`→`data-key` (72 sites) |
| connexion | `identifiant`→`username`, `motdepasse`→`password`, sur 7 sites (balisage, `champs.get`, `serve.py`, `startup.py`, `switchover.py`) |
| vocabulaire | 27 derniers noms révélés par le vocabulaire, dont `trierLib`→`sortLibrary` |
| répertoires | `assets/acteurs`→`cast`, `affiches`→`posters-hd`, `heros`→`heroes` (528 chemins, 925 références résolvent) |
| dégel | `pont`→`bridge`, `ecrans`→`screens`, `panneau`→`panel` + 11 méthodes (`noter`→`record`, `remplacer`→`replace`, `coucher`→`pushLayer`, `retour`→`back`, `reculer`→`rewind`, `surRetour`→`onBack`, `ouvrir`→`open`, `fermer`→`close`, `ouverte`→`isOpen`, `ajout`→`add`, `fiche`→`mediaSheet`) |
| contrat fiche | `data-fiche`→`data-mediasheet` (nom distinct : `data-sheet` appartient déjà à l'ouverture de panneau) |
| clés d'écran | `data-key` : `fiche:`→`mediaSheet:`, `profil:`→`profile:`, `ajout:`→`add:`, des deux côtés |

## Le détecteur — il pose désormais la question inverse

`scripts/code-vocabulary.txt` (~520 mots) tient **les mots dont les noms de ce
dépôt sont faits**. « Ce mot est-il un des nôtres ? » n'a pas de trous par
construction, là où « ce mot est-il français ? » dépendait d'une liste de
156 mots qui ignorait `suivante`, `trier`, `fermer`, `afficher`, `chargement`,
`compte`, `monde` — et sous laquelle 141 noms français dormaient au vert.

Le bras lit aussi les `.js`, ce qui met le moteur hérité sous garde. Ajouter un
mot = une ligne, délibérément. **Trois mutations le font tomber** (un nom bâti
sur un mot inconnu ; un nom que l'ancien lexique connaissait ; une table vide).

## L'OUTIL — et la règle qui compte le plus

`scripts/rename-identifiers.py`. **Ne jamais renommer à la main ni avec une
regex ad hoc.** Chaque fois que je l'ai contourné « parce que le cas est
simple », j'ai cassé quelque chose : une route (22 segments), 11 identifiants
d'état, 8 textes d'interface, 5 assertions de règle. Toutes rattrapées par une
porte, aucune par relecture.

Il connaît **treize formes qui ressemblent à un identifiant sans en être**, et
chacune a coûté une porte rouge. Les quatre dernières viennent de la passe de
garant, et les trois premières d'entre elles corrompaient des textes
d'interface EN SILENCE :

| Forme | Ce que c'est |
| --- | --- |
| `"un compte, un identifiant."` | copie d'interface |
| `mode === "clair"` dans `${…}` | chaîne IMBRIQUÉE dans une interpolation |
| `reglages-modifie` | id d'état composé par un tiret |
| `"ajout:suivi"` | clé de donnée composée par un deux-points |
| `f"/profil/{titre}"` | chemin de route ; une barre oblique délimite une adresse |
| `[data-go=profil]` | sélecteur : l'attribut ET sa valeur |
| `liste:` dans `t("…", {…})` | placeholder d'interpolation nommé par `fr.json` |
| `PAGES = { profil: … }` | clé qui EST un id de page |
| `"PLANIFICATEURS"` | …mais celle-ci EST un identifiant, distinguée par la CASSE |
| `/n'est plus cherché/i` | une REGEX portant une apostrophe : elle ouvrait une chaîne jamais fermée, et **tout le reste du fichier se lisait comme du code** |
| `<p>En attente de torrent</p>` | du TEXTE JSX : il ne porte aucun guillemet, donc un scanner qui cherche des guillemets le lit comme du code |
| `{ ...REGLEE }` | la DÉCOMPOSITION ressemble à un accès membre — renommage à moitié fait, silencieux |
| `[center - radius, …]` | en Python, un crochet est aussi une LISTE, pas seulement un sélecteur |

**Il ne devine plus.** `scripts/source-spans.mjs` demande au parseur de
TypeScript les chaînes, les morceaux de gabarit, les regex et le texte JSX, et
l'outil **refuse d'écrire** un fichier dont une zone protégée a bougé. La preuve
de l'aller-retour à table vide ne pouvait pas voir ce défaut : un fichier mal
classé se réassemble à l'octet près.

**Sa preuve permanente** : une table VIDE doit faire un aller-retour identique à
l'octet sur chaque fichier. C'est elle qui a démasqué deux erreurs de
bissection (mesurer un seul état hors de l'ordre enregistré ; comparer des
tranches au lieu de préfixes croissants).

**Avant tout renommage en mode propriété** : vérifier que le nom cible n'existe
pas déjà comme contrat. `fiche`→`sheet` a FUSIONNÉ deux contrats (`data-sheet`
appartenait à l'ouverture de panneau) et le menu utilisateur répondait avec les
actions de la fiche. Sept règles l'ont vu.

## Ce qui reste français, délibérément

- `refonte.html` — nommé par R72, destiné à disparaître (l'opérateur l'accepte).
- `maquette` — le mot de l'opérateur, inscrit dans la constitution §15.
- `profil:` dans la table `PAGES` de `host.tsx` — cette clé EST l'id de page, la
  valeur de `state.page` et de l'adresse `?page=`. Commentaire `french-ok`.
- `liste:` dans `media.tsx` — placeholder d'interpolation nommé par `fr.json`.
- **Les VALEURS** : ids d'état (`reglages-modifie`), ids de page (`profil`),
  noms de thème (`clair`), onglets (`maintenant`), adresses (`/fiche/$titre`).
- Le français que les tenues ASSERTENT — c'est la sortie rendue.
- Les `.png` de débogage du harnais : **non suivis par git**.

## Reconstruire les oracles si `/tmp` a été purgé

```bash
# hôte du harnais
cd /tmp/tm-refonte && python3 -m http.server 8899 &
cd frontend/maquette/design && npm run build
cp dist/index.html /tmp/tm-refonte/wrapped.html
rm -rf /tmp/tm-refonte/vite && cp -R dist/vite /tmp/tm-refonte/vite
ln -sfn "$(git rev-parse --show-toplevel)/frontend/maquette/design/assets" /tmp/tm-refonte/assets

# la liste des 82 états
python3 - <<'EOF'
import asyncio, json
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(channel="chrome"); p = await b.new_page()
        await p.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
        await p.wait_for_timeout(800)
        json.dump(await p.evaluate("()=>window.__states()"), open("/tmp/tm-states.json","w"))
        await b.close()
asyncio.run(main())
EOF
```

**La preuve d'un lot qui change le balisage EXPRÈS** (renommage de contrat) n'est
pas « 0 divergence » : c'est **appliquer la table de renommage à
l'ENREGISTREMENT et exiger l'égalité exacte**. Sinon l'oracle mesure le
changement voulu comme une régression. Le script `/tmp/verify-unfreeze.py` fait
exactement cela ; il se reconstruit depuis `frontend/maquette/fidelity.py`.

## Pièges d'exécution déjà payés

- **Une commande shell en échec n'est pas un no-op** : c'est une édition qui n'a
  pas eu lieu. Relire la cible est une PREUVE, pas un décor. Un `cd` raté a
  laissé `state: { get: () => state }` après suppression de la liaison → le nom
  résolvait vers `window.state`, donc vers lui-même : page morte au chargement.
- Le harnais sert un build **figé** dans `/tmp/tm-refonte` : une tenue
  d'exécution ne se mute qu'À TRAVERS le build.
- `serve.py` est lu une fois au démarrage : après l'avoir modifié,
  `pm2 restart torrentmate-design`, sinon `pwa.py` et `entry.py` rougissent sur
  un processus périmé.
- Un enregistrement de fidélité VIEILLIT : l'horloge (« Prochaine recherche à
  3 h 20 ») et les données de `resync.py` en font partie.
