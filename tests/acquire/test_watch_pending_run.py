"""L'attente du watcher est PUBLIÉE — sinon elle est invisible (§8, NE-DOIT-PAS-2).

Le watcher est un process PM2 séparé du serveur web : sa fenêtre de temporisation vit en
mémoire et personne ne peut la lire. C'est ce qui a fait dire à l'opérateur « le pipeline
ne s'est pas lancé » alors qu'il attendait, muet, quinze minutes. Le daemon publie donc
son attente à chaque cycle dans ``watch_state``, la seule table que les deux process
partagent.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a real acquire store on a temp acquire.db, closed afterwards."""
    s = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    try:
        yield s
    finally:
        s.close()


class TestPendingRunIsPublished:
    """Ce que le daemon publie, et ce que le web peut donc afficher."""

    def test_nothing_published_yet_reads_as_no_wait(self, store: ConcreteAcquireStore) -> None:
        """Avant le premier cycle, il n'y a rien à dire — et surtout rien à inventer."""
        assert store.watch.get_pending_run() is None

    def test_a_running_countdown_is_published_with_its_deadline(self, store: ConcreteAcquireStore) -> None:
        """Compte à rebours en cours : l'échéance est lisible par le web."""
        store.watch.set_pending_run(fires_at=1_785_900_060.0, active_downloads=0, now=1_785_900_000.0)
        pending = store.watch.get_pending_run()
        assert pending is not None
        assert pending.fires_at == 1_785_900_060.0
        assert pending.active_downloads == 0
        assert pending.updated_at == 1_785_900_000.0

    def test_a_held_counter_publishes_what_holds_it(self, store: ConcreteAcquireStore) -> None:
        """Compteur suspendu : le nombre de téléchargements est LA raison à afficher (DOIT-2)."""
        store.watch.set_pending_run(fires_at=None, active_downloads=3, now=1_785_900_000.0)
        pending = store.watch.get_pending_run()
        assert pending is not None
        assert pending.fires_at is None
        assert pending.active_downloads == 3

    def test_the_snapshot_is_replaced_each_cycle_never_accumulated(self, store: ConcreteAcquireStore) -> None:
        """Un instantané, pas un journal : le dernier cycle écrase le précédent."""
        store.watch.set_pending_run(fires_at=None, active_downloads=2, now=1_000.0)
        store.watch.set_pending_run(fires_at=1_160.0, active_downloads=0, now=1_100.0)
        pending = store.watch.get_pending_run()
        assert pending is not None
        assert (pending.fires_at, pending.active_downloads, pending.updated_at) == (1_160.0, 0, 1_100.0)

    def test_a_finished_wait_clears_the_deadline(self, store: ConcreteAcquireStore) -> None:
        """Une échéance périmée ne survit pas : l'UI ne doit jamais compter à rebours dans le vide."""
        store.watch.set_pending_run(fires_at=1_160.0, active_downloads=0, now=1_100.0)
        store.watch.set_pending_run(fires_at=None, active_downloads=0, now=1_200.0)
        pending = store.watch.get_pending_run()
        assert pending is not None and pending.fires_at is None

    def test_it_does_not_disturb_the_last_successful_run(self, store: ConcreteAcquireStore) -> None:
        """La clé historique de la table reste intacte — même KV, deux sujets."""
        store.watch.set_last_successful_run_at(42.0)
        store.watch.set_pending_run(fires_at=None, active_downloads=1, now=99.0)
        assert store.watch.get_last_successful_run_at() == 42.0
