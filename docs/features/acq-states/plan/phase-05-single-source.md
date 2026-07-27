# Phase 05 — Fin des sources divergentes

**Goal**: supprimer la seconde source de vérité. La carte et le panneau de complétude doivent
répondre la même chose parce qu'ils lisent les mêmes faits, par la même fonction.

**Constitution servie**: NE-DOIT-PAS-1 (mentir), NE-DOIT-PAS-8 (pas de rafale providers).

**Design**: `DESIGN.md` §2 RC2 + §4 D3.

## Le défaut corrigé

`completeness.py:110-116` tombe en repli sur un `poll_aired` **live** quand le cache est vide,
alors que `models/acquisition.py:99-104` retombe, lui, sur les compteurs bruts. Sur la même
série au même instant, les deux chemins donnent des réponses opposées — c'est ce qui s'est
produit le 2026-07-27 : la carte disait « À jour » pendant que le panneau aurait listé trois
épisodes `manquant`. Les logs prod montrent que les deux endpoints ont bien été appelés.

## Surface

| Fichier                                               | Action                                                               |
| ----------------------------------------------------- | -------------------------------------------------------------------- |
| `personalscraper/web/acquisition/completeness.py`     | suppression du repli `poll_aired` ; état par épisode via `states.py` |
| `personalscraper/web/acquisition/truth.py`            | même source que la complétude                                        |
| `tests/unit/web/acquisition/test_source_agreement.py` | **NEW** — carte et détail s'accordent toujours                       |

## Sous-phases

### 5.1 — Test-first : l'accord des deux surfaces

**Commit**: `test(acq-states): card and completeness panel must never disagree`

```python
def test_card_and_completeness_agree_on_an_uncached_follow() -> None:
    """The card and the detail panel must never contradict each other.

    On 2026-07-27 they did: with an empty aired cache the card fell back to raw
    wanted counters and said « À jour », while compute_completeness fell back to
    a LIVE poll_aired and would have listed three episodes as missing. Same
    database, same instant, opposite answers. This test pins the agreement.
    """
```

Le test est paramétré sur les cas qui divergeaient : cache vide, cache partiel, cache à jour,
panne provider.

### 5.2 — Suppression du repli divergent

**Commit**: `fix(acq-states): remove the divergent live poll_aired fallback`

- Le repli `poll_aired` de `compute_completeness` est **supprimé**. Catalogue absent ⇒
  `non_verifie` (état honnête), plus un poll live qui contredit la carte.
- `_episode_state` de `completeness.py` est remplacé par `states.derive_episode_state` — une
  seule implémentation, plus deux.
- `provider_catalog_empty` est conservé : le cas « le provider connaît la série mais ne liste
  aucun épisode » (Top Chef Le Concours Parallèle) reste un état explicite distinct de
  « Non vérifié ». Ne pas fusionner les deux : ce sont deux ignorances différentes.

**Effet de bord assumé** : une série jamais détectée n'affiche plus sa matrice d'épisodes
immédiatement. C'est voulu — c'est le prix de la cohérence, et la phase 6 le rend indolore en
amorçant le catalogue dès la création du suivi.

## Gate

1. `make lint` + `make test`.
2. Le test d'accord échouait avant 5.2, passe après.
3. `rg -n "poll_aired" --type py personalscraper/web/` — plus aucun appel depuis un chemin de
   lecture web.
4. `rg -n "def _episode_state" --type py personalscraper/` — une seule définition, dans
   `states.py`.
5. Aucun appel provider ni tracker déclenché par `GET /followed` ou
   `GET /followed/{id}/completeness` — vérifié en comptant les appels réseau sur un test
   d'intégration.
