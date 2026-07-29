# Phase 02 — Observabilité du swarm + classification du blocage

## Gate

- `python -m pytest tests/torrent/ tests/acquire/test_classify_stall.py -q` vert.
- `make lint` vert.

## Sous-phases

### 2.1 — `TorrentItem.swarm_seeds` + mapping qBit

- `api/torrent/_base.py` : ajouter `swarm_seeds: int | None = None` au dataclass `TorrentItem`
  (optionnel, rétro-compat — aucun appelant existant ne le fournit).
- `api/torrent/qbittorrent.py:_torrent_item` : renseigner `swarm_seeds` depuis le champ
  `num_complete` du payload `torrents/info` (nb de seeds connus du tracker). Fail-soft : absent →
  `None`.
- Test : `_torrent_item` sur un payload avec/ sans `num_complete` ⇒ `swarm_seeds` correct / `None`.

### 2.2 — `classify_stall` (helper pur)

Nouveau module `acquire/_stall.py` (ou fonction dans un module existant approprié) :

```
class StallVerdict(StrEnum): HEALTHY, STALLED_RECOVERABLE, STALLED_DEAD
def classify_stall(item: TorrentItem, grabbed_age_s: float, *, dead_after_s: float) -> StallVerdict
```

Règles :

- `HEALTHY` : progress > 0 (ça avance) OU état non bloqué.
- `STALLED_DEAD` : état bloqué (`stalled`/`stalledDL`/`missingFiles`/`error`) **ET** progress == 0
  **ET** (`swarm_seeds == 0` **OU** `grabbed_age_s > dead_after_s`).
- `STALLED_RECOVERABLE` : bloqué + progress 0 mais swarm vivant et âge < seuil (on attend encore).

Test rouge-avant `tests/acquire/test_classify_stall.py` : matrice état × progress × swarm × âge
couvrant chaque verdict (dont : swarm vivant récent ⇒ recoverable ; swarm mort ⇒ dead ; âge
dépassé ⇒ dead même si swarm inconnu ; progress > 0 ⇒ healthy).
