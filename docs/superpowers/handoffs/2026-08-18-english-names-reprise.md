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

## État à la reprise

- Branche `refactor/english-names`, dernier commit `37b39757`.
- **PR #455 OUVERTE**, CI verte 12/12 au dernier passage — mais elle ne contient
  PAS le travail non commité ci-dessous.
- **33 fichiers modifiés non commités** (le dégel des coutures + les clés
  d'écran + les réparations). C'est la première chose à commiter.

### Preuves déjà obtenues sur l'arbre courant

- `python3 /tmp/verify-unfreeze.py` → **les 82 états coïncident** une fois la
  table de renommage appliquée à l'enregistrement. (Si `/tmp` a été purgé, voir
  « Reconstruire les oracles » plus bas.)
- Suite de règles : **49 vertes, 0 rouge, 568 tenues**, identiques à `main` —
  passage COMPLET terminé sur cet arbre exact (dégel + clés d'écran inclus).
  Inutile de la relancer avant de commiter ; la relancer seulement si l'arbre
  bouge encore.
- `make test` 10 703 · `make lint` · `check-frontend` 1 364 · `check-no-french` ·
  `extract-maquette-css --check` · `audit_design_coverage --strict` ·
  `check-module-size` : tous verts avant le dégel, **à relancer après**.

## Ce qui reste à faire, dans l'ordre

1. ~~Relancer la suite complète~~ — **déjà verte sur cet arbre** (49/0/568).
2. **Relancer** `make test`, `make lint`, `make check-frontend`,
   `python3 scripts/check-no-french.py`, `extract-maquette-css.py --check`,
   `audit_design_coverage.py --strict`, `check-module-size.py`.
3. **Relancer l'audit INDÉPENDANT** (`/tmp/audit-french.py`) : il ne doit rester
   que `refonte.html` et les `.png` NON SUIVIS par git.
4. **Bumper la version** (règle opérateur : un bump par PR) et commiter.
5. Pousser, attendre la CI verte (12 contrôles), **puis fusionner en squash**.
6. Mettre à jour `docs/superpowers/shell-mobile-wave-log.md` : l'entrée
   « English names » existe déjà, ajouter le dégel des coutures et les clés
   d'écran.

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

Il connaît **neuf formes qui ressemblent à un identifiant sans en être**, et
chacune a coûté une porte rouge :

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
