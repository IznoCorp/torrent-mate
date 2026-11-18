"""Unit tests for ``personalscraper.app.supervisor.model`` — the queue's request and the lease, with their rules.

Coalescing (an ask joins a queued request equal in kind and options; a rescrape joins a queued or a
running one of the same item), every legal and illegal state transition, the staleness of a running
request at three heartbeats, and the lease's liveness and claimability.
"""

from __future__ import annotations

import re

import pytest

from personalscraper.app.accounts.ids import AccountId
from personalscraper.app.supervisor.ids import RunUid
from personalscraper.app.supervisor.model import (
    Lease,
    RequestState,
    RunKind,
    RunOptions,
    RunRequest,
    RunRequestStateError,
    RunTrigger,
    Settlement,
    WaitReason,
)
from personalscraper.core.identity import ItemId

ASKER = AccountId("account-a")
NOW = 1_000.0


def _ask(
    options: RunOptions | None = None,
    *,
    kind: RunKind = RunKind.PIPELINE,
    trigger: RunTrigger = RunTrigger.MANUAL,
    now: float = NOW,
) -> RunRequest:
    """Ask a run.

    Args:
        options: What the run is asked to do; the defaults when omitted.
        kind: The kind of run.
        trigger: Who asked.
        now: The epoch of the ask.

    Returns:
        The queued request.
    """
    return RunRequest.ask(kind, trigger, options or RunOptions(), ASKER, now)


def _running(request: RunRequest | None = None, *, now: float = NOW) -> RunRequest:
    """Admit a request (a fresh one when omitted).

    Args:
        request: The request to admit.
        now: The epoch of the admission.

    Returns:
        The running request.
    """
    request = request or _ask()
    request.admit(4242, now)
    return request


class TestAsk:
    """A new ask is a queued request that carries its options canonically."""

    def test_ask_is_queued_with_a_fresh_uid(self) -> None:
        """Ask is queued with a fresh uid."""
        request = _ask(trigger=RunTrigger.WEB)
        assert request.state is RequestState.QUEUED
        assert re.fullmatch(r"[0-9a-f]{32}", request.uid)
        assert (request.kind, request.trigger, request.asked_by, request.asked_at) == (
            RunKind.PIPELINE,
            RunTrigger.WEB,
            ASKER,
            NOW,
        )
        assert (request.admitted_at, request.worker_pid, request.heartbeat_at, request.settled_at) == (None,) * 4
        assert request.settlement is None
        assert request.wait_reason is None
        assert _ask().uid != request.uid

    def test_options_json_is_canonical_and_round_trips(self) -> None:
        """Options json is canonical and round trips."""
        options = RunOptions(skip_trailers=True, item_id=7)
        request = _ask(options, kind=RunKind.RESCRAPE)
        assert request.options_json == (
            '{"continue_on_trailer_error": false, "dry_run": false, "item_id": 7,'
            ' "no_post_maintenance": false, "skip_trailers": true}'
        )
        assert request.options == options

    def test_ask_keeps_a_supplied_uid(self) -> None:
        """Ask keeps a supplied uid, and makes a new one when none is supplied."""
        uid = RunUid("c" * 32)
        request = RunRequest.ask(RunKind.PIPELINE, RunTrigger.WEB, RunOptions(), ASKER, NOW, uid=uid)
        assert request.uid == uid
        assert RunRequest.ask(RunKind.PIPELINE, RunTrigger.WEB, RunOptions(), ASKER, NOW, uid=None).uid != uid

    def test_item_id_round_trips_as_an_integer_in_the_json(self) -> None:
        """The typed item id is an integer in ``options_json`` and comes back as the same value."""
        request = _ask(RunOptions(item_id=ItemId(7)), kind=RunKind.RESCRAPE)
        assert '"item_id": 7' in request.options_json
        assert request.options.item_id == ItemId(7)
        assert _ask().options.item_id is None

    def test_every_trigger_code_is_the_designs(self) -> None:
        """Every trigger code is the designs."""
        assert {t.value for t in RunTrigger} == {"completion", "safety_net", "manual", "web", "cli", "scrape-resolve"}
        assert {k.value for k in RunKind} == {"pipeline", "rescrape"}
        assert {s.value for s in RequestState} == {"queued", "running", "settled"}
        assert {s.value for s in Settlement} == {"success", "error", "killed", "interrupted", "abandoned"}
        assert {w.value for w in WaitReason} == {
            "behind_run",
            "pipeline_lock_held",
            "paused",
            "worker_start_failed",
            "supervisor_absent",
        }


class TestCoalescing:
    """``new.joins(existing)``: whether an ask is answered by a request already in the queue."""

    def test_equal_pipeline_options_join_a_queued_request(self) -> None:
        """Equal pipeline options join a queued request."""
        assert _ask(RunOptions(dry_run=True)).joins(_ask(RunOptions(dry_run=True)))

    def test_the_trigger_and_the_asker_do_not_matter(self) -> None:
        """The trigger and the asker do not matter."""
        assert _ask(trigger=RunTrigger.CLI).joins(_ask(trigger=RunTrigger.SAFETY_NET))

    def test_different_options_never_join(self) -> None:
        """Different options never join."""
        assert not _ask(RunOptions(dry_run=True)).joins(_ask())
        assert not _ask(RunOptions(skip_trailers=True)).joins(_ask())

    def test_a_pipeline_ask_does_not_join_a_running_request(self) -> None:
        """A pipeline ask does not join a running request."""
        assert not _ask().joins(_running())

    def test_a_pipeline_ask_does_not_join_a_settled_request(self) -> None:
        """A pipeline ask does not join a settled request."""
        settled = _running()
        settled.settle(Settlement.SUCCESS, NOW + 1)
        assert not _ask().joins(settled)

    def test_a_rescrape_joins_a_queued_request_of_the_same_item(self) -> None:
        """A rescrape joins a queued request of the same item."""
        queued = _ask(RunOptions(item_id=7), kind=RunKind.RESCRAPE)
        assert _ask(RunOptions(item_id=7), kind=RunKind.RESCRAPE).joins(queued)

    def test_a_rescrape_joins_a_running_request_of_the_same_item(self) -> None:
        """A rescrape joins a running request of the same item."""
        running = _running(_ask(RunOptions(item_id=7), kind=RunKind.RESCRAPE))
        assert _ask(RunOptions(item_id=7), kind=RunKind.RESCRAPE).joins(running)

    def test_a_rescrape_of_another_item_never_joins(self) -> None:
        """A rescrape of another item never joins."""
        queued = _ask(RunOptions(item_id=7), kind=RunKind.RESCRAPE)
        assert not _ask(RunOptions(item_id=8), kind=RunKind.RESCRAPE).joins(queued)

    def test_a_rescrape_does_not_join_a_settled_request(self) -> None:
        """A rescrape does not join a settled request."""
        settled = _running(_ask(RunOptions(item_id=7), kind=RunKind.RESCRAPE))
        settled.settle(Settlement.ERROR, NOW + 1)
        assert not _ask(RunOptions(item_id=7), kind=RunKind.RESCRAPE).joins(settled)

    def test_a_pipeline_run_and_a_rescrape_never_join_each_other(self) -> None:
        """A pipeline run and a rescrape never join each other."""
        rescrape = _ask(RunOptions(item_id=7), kind=RunKind.RESCRAPE)
        assert not _ask(RunOptions(item_id=7)).joins(rescrape)
        assert not _ask(RunOptions(item_id=7), kind=RunKind.RESCRAPE).joins(_ask(RunOptions(item_id=7)))


class TestTransitions:
    """queued → running → settled, and running → queued; every other move is a programming error."""

    def test_admit_marks_the_request_running(self) -> None:
        """Admit marks the request running."""
        request = _ask()
        request.wait_reason = WaitReason.BEHIND_RUN
        request.admit(4242, NOW + 5)
        assert request.state is RequestState.RUNNING
        assert (request.worker_pid, request.admitted_at, request.heartbeat_at) == (4242, NOW + 5, NOW + 5)
        assert request.wait_reason is None

    def test_back_to_queue_returns_a_running_request_with_its_reason(self) -> None:
        """Back to queue returns a running request with its reason."""
        request = _running()
        request.back_to_queue(WaitReason.PIPELINE_LOCK_HELD)
        assert request.state is RequestState.QUEUED
        assert request.wait_reason is WaitReason.PIPELINE_LOCK_HELD
        assert (request.worker_pid, request.admitted_at, request.heartbeat_at) == (None, None, None)

    def test_a_request_sent_back_can_be_admitted_again(self) -> None:
        """A request sent back can be admitted again."""
        request = _running()
        request.back_to_queue(WaitReason.PIPELINE_LOCK_HELD)
        request.admit(5151, NOW + 9)
        assert request.state is RequestState.RUNNING
        assert request.worker_pid == 5151
        assert request.wait_reason is None

    @pytest.mark.parametrize("settlement", list(Settlement))
    def test_settle_closes_a_running_request(self, settlement: Settlement) -> None:
        """Settle closes a running request."""
        request = _running()
        request.settle(settlement, NOW + 30)
        assert request.state is RequestState.SETTLED
        assert (request.settlement, request.settled_at) == (settlement, NOW + 30)

    def test_admit_refuses_a_running_request(self) -> None:
        """Admit refuses a running request."""
        with pytest.raises(RunRequestStateError):
            _running().admit(1, NOW)

    def test_admit_refuses_a_settled_request(self) -> None:
        """Admit refuses a settled request."""
        request = _running()
        request.settle(Settlement.SUCCESS, NOW)
        with pytest.raises(RunRequestStateError):
            request.admit(1, NOW)

    def test_settle_refuses_a_queued_request(self) -> None:
        """Settle refuses a queued request."""
        with pytest.raises(RunRequestStateError):
            _ask().settle(Settlement.SUCCESS, NOW)

    def test_settle_refuses_a_settled_request_and_keeps_its_first_outcome(self) -> None:
        """Settle refuses a settled request and keeps its first outcome."""
        request = _running()
        request.settle(Settlement.SUCCESS, NOW)
        with pytest.raises(RunRequestStateError):
            request.settle(Settlement.ERROR, NOW + 1)
        assert request.settlement is Settlement.SUCCESS

    def test_back_to_queue_refuses_a_queued_request(self) -> None:
        """Back to queue refuses a queued request."""
        with pytest.raises(RunRequestStateError):
            _ask().back_to_queue(WaitReason.BEHIND_RUN)

    def test_back_to_queue_refuses_a_settled_request(self) -> None:
        """Back to queue refuses a settled request."""
        request = _running()
        request.settle(Settlement.KILLED, NOW)
        with pytest.raises(RunRequestStateError):
            request.back_to_queue(WaitReason.BEHIND_RUN)

    def test_a_refused_transition_leaves_the_request_unchanged(self) -> None:
        """A refused transition leaves the request unchanged."""
        request = _ask()
        with pytest.raises(RunRequestStateError):
            request.settle(Settlement.SUCCESS, NOW)
        assert request.state is RequestState.QUEUED
        assert (request.settlement, request.settled_at) == (None, None)

    def test_abandon_settles_a_queued_request_that_never_ran(self) -> None:
        """Abandon closes a queued request ``abandoned`` without ever passing it through running."""
        request = _ask()
        request.wait_reason = WaitReason.BEHIND_RUN
        request.abandon(NOW + 3)
        assert request.state is RequestState.SETTLED
        assert (request.settlement, request.settled_at) == (Settlement.ABANDONED, NOW + 3)
        assert (request.admitted_at, request.worker_pid, request.heartbeat_at) == (None, None, None)
        assert request.wait_reason is None

    def test_abandon_refuses_a_running_request(self) -> None:
        """Abandon refuses a running request: its worker may be running."""
        with pytest.raises(RunRequestStateError):
            _running().abandon(NOW)

    def test_admit_without_a_worker_yet_then_record_it(self) -> None:
        """An admission saved before the worker starts names no process; its pid is recorded after."""
        request = _ask()
        request.admit(None, NOW + 5)
        assert request.state is RequestState.RUNNING
        assert (request.worker_pid, request.admitted_at, request.heartbeat_at) == (None, NOW + 5, NOW + 5)
        request.record_worker(4242)
        assert request.worker_pid == 4242

    def test_record_worker_refuses_a_queued_request(self) -> None:
        """Only a running request has a worker to record."""
        with pytest.raises(RunRequestStateError):
            _ask().record_worker(4242)


class TestStale:
    """A running request is stale once its heartbeat is older than 3 × 30 s."""

    def test_fresh_within_three_heartbeats(self) -> None:
        """Fresh within three heartbeats."""
        assert not _running(now=NOW).stale(NOW + 90)

    def test_stale_beyond_three_heartbeats(self) -> None:
        """Stale beyond three heartbeats."""
        assert _running(now=NOW).stale(NOW + 90.5)

    def test_a_queued_request_is_never_stale(self) -> None:
        """A queued request is never stale."""
        assert not _ask().stale(NOW + 10_000)

    def test_a_settled_request_is_never_stale(self) -> None:
        """A settled request is never stale."""
        request = _running()
        request.settle(Settlement.SUCCESS, NOW)
        assert not request.stale(NOW + 10_000)


class TestWait:
    """A queued request records why it still waits."""

    @pytest.mark.parametrize("reason", [WaitReason.BEHIND_RUN, WaitReason.PIPELINE_LOCK_HELD, WaitReason.PAUSED])
    def test_a_queued_request_records_its_reason(self, reason: WaitReason) -> None:
        """A queued request records its reason, and stays queued."""
        request = _ask()
        request.wait(reason)
        assert (request.state, request.wait_reason) == (RequestState.QUEUED, reason)

    def test_supervisor_absent_is_derived_never_recorded(self) -> None:
        """``supervisor_absent`` is derived at read time: recording it is refused."""
        request = _ask()
        with pytest.raises(ValueError, match="supervisor_absent"):
            request.wait(WaitReason.SUPERVISOR_ABSENT)
        assert request.wait_reason is None

    def test_a_running_or_settled_request_cannot_wait(self) -> None:
        """A request that is not queued cannot wait."""
        running = _running()
        with pytest.raises(RunRequestStateError):
            running.wait(WaitReason.PAUSED)
        running.settle(Settlement.SUCCESS, NOW)
        with pytest.raises(RunRequestStateError):
            running.wait(WaitReason.PAUSED)
        assert running.wait_reason is None


class TestLease:
    """The lease is live until its expiry, and claimable once it is not live or its holder is gone."""

    @staticmethod
    def _lease(expires_at: float = NOW + 60, holder_pid: int = 4242) -> Lease:
        return Lease(
            holder_pid=holder_pid, holder_host="iznoserver", taken_at=NOW, renewed_at=NOW, expires_at=expires_at
        )

    def test_live_until_its_expiry(self) -> None:
        """Live until its expiry."""
        lease = self._lease()
        assert lease.live(NOW + 59.9)
        assert not lease.live(NOW + 60)
        assert not lease.live(NOW + 61)

    def test_not_claimable_while_live_and_its_holder_is_alive(self) -> None:
        """Not claimable while live and its holder is alive."""
        assert not self._lease().claimable(NOW + 10, lambda pid: True, "iznoserver")

    def test_claimable_once_expired(self) -> None:
        """Claimable once expired."""
        assert self._lease().claimable(NOW + 60, lambda pid: True, "iznoserver")

    def test_claimable_while_live_when_its_holder_is_gone_on_this_host(self) -> None:
        """Claimable while live when its holder is gone and the lease is this host's."""
        assert self._lease().claimable(NOW + 10, lambda pid: False, "iznoserver")

    def test_another_hosts_live_lease_is_not_claimable_whatever_the_probe_says(self) -> None:
        """A pid probe only speaks for this machine: another host's live lease holds until it expires."""
        assert not self._lease().claimable(NOW + 10, lambda pid: False, "other-host")

    def test_another_hosts_lease_is_claimable_once_expired(self) -> None:
        """Another host's lease is claimable on expiry."""
        assert self._lease().claimable(NOW + 60, lambda pid: True, "other-host")

    def test_the_holder_pid_is_the_one_asked_about(self) -> None:
        """The holder pid is the one asked about."""
        asked: list[int] = []
        self._lease(holder_pid=77).claimable(NOW + 10, lambda pid: asked.append(pid) is None, "iznoserver")
        assert asked == [77]

    def test_the_probe_is_not_asked_about_another_hosts_pid(self) -> None:
        """A pid of another machine means nothing here: the probe is not called."""
        asked: list[int] = []
        self._lease().claimable(NOW + 10, lambda pid: asked.append(pid) is None, "other-host")
        assert asked == []


def test_run_uid_is_a_plain_string_on_the_wire() -> None:
    """Run uid is a plain string on the wire."""
    assert RunUid("a" * 32) == "a" * 32
