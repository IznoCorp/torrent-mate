"""§13 — la dérivation unique produit les mêmes compteurs côté carte et côté fiche.

``truth.py`` (les agrégats de la carte « Suivis ») et ``completeness.py`` (la
matrice saison/épisode de la fiche de détail) lisent les faits d'un même suivi à
travers la MÊME couture — ``governing_facts_by_episode`` +
``derive_episode_state`` — et doivent donc tomber d'accord sur chaque épisode.
Ce test est le garde-fou : il sème UN suivi avec des épisodes diffusés et des
lignes ``wanted``, appelle les DEUX chemins, et vérifie que les agrégats
concordent.

Il échouera le jour où quelqu'un modifie ``truth.py`` sans ``completeness.py``
(ou l'inverse).
"""

from __future__ import annotations

import time
from datetime import date
from unittest.mock import MagicMock

from personalscraper.acquire.domain import FollowedSeries, MediaRef, WantedItem
from personalscraper.web.acquisition.completeness import compute_completeness
from personalscraper.web.acquisition.truth import compute_follow_truth


def test_truth_and_completeness_agree_on_counts(acquire_store):
    """Pour un suivi semé, aired_count et owned_count sont identiques dans les deux vues.

    Sème :
    - S01E1, S01E2  → en médiathèque (owned)
    - S01E3         → en_attente (searched, nothing takeable)
    - S02E1         → annoncé (air_date future, exclu des deux vues)
    """
    store = acquire_store
    now = int(time.time())

    # 1. Créer le suivi
    media_ref = MediaRef(tvdb_id=12345, tmdb_id=None, imdb_id=None)
    followed = FollowedSeries(
        media_ref=media_ref,
        title="Test Show",
        active=True,
        added_at=now,
        kind="show",
    )
    followed_id = store.follow.add(followed)

    # 2. Semer le catalogue diffusé : 3 épisodes S01 + 1 futur S02
    store.aired.replace_for_followed(
        followed_id,
        [
            (1, 1, "Owned 1", "2024-01-01"),
            (1, 2, "Owned 2", "2024-01-08"),
            (1, 3, "En attente", "2024-01-15"),
            (2, 1, "Futur", "2099-12-31"),
        ],
        now=now,
    )

    # 3. Semer une ligne wanted pour S01E3 (cherché, rien de prenable)
    store.wanted.add(
        WantedItem(
            media_ref=media_ref,
            kind="episode",
            season=1,
            episode=3,
            status="searching",
            followed_id=followed_id,
            enqueued_at=now,
            last_search_outcome="no_candidates",
            last_search_found=0,
        )
    )

    # 4. Propriété : S01E1 et S01E2 sont en médiathèque
    owned_set = {(1, 1), (1, 2)}
    mock_checker = MagicMock()
    mock_checker.owned_pairs.return_value = owned_set
    mock_checker.owns.side_effect = (
        lambda media_ref, kind, season, episode: (season, episode) in owned_set
    )

    ref_date = date.today()

    # 5. Chemin carte (truth.py)
    truth = compute_follow_truth(
        store._ensure_open(),  # noqa: SLF001 — le test a besoin de la connexion brute
        mock_checker,
        followed_id=followed_id,
        media_ref=media_ref,
        today=ref_date,
    )

    # 6. Chemin fiche (completeness.py)
    followed_from_store = store.follow.get(followed_id)
    assert followed_from_store is not None, "le suivi doit exister après add()"
    completeness = compute_completeness(
        followed_from_store,
        ownership=mock_checker,
        store=store,
        today=ref_date,
    )

    # 7. Les agrégats concordent
    total_aired = sum(s.total for s in completeness.seasons)
    assert truth.aired_count == total_aired, (
        f"truth.aired_count={truth.aired_count} ≠ sum saisons.total={total_aired}"
    )

    total_owned = sum(s.owned for s in completeness.seasons)
    assert truth.owned_count == total_owned, (
        f"truth.owned_count={truth.owned_count} ≠ sum saisons.owned={total_owned}"
    )

    # 8. L'épisode annoncé (S02E1) est exclu des deux vues
    #    — truth : le SQL exclut air_date > today
    #    — completeness : derive_episode_state rend "annonce", total exclut "annonce"
    assert truth.aired_count == 3, (
        f"3 épisodes diffusés, aired_count={truth.aired_count} (le futur ne compte pas)"
    )
