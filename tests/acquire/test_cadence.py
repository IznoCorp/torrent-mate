"""Tests for acquire/cadence.py — Hot/Warm/Cold tier + cutoff predicates."""

from __future__ import annotations

import pytest

# Canonical cadence for tests: Hot <72h/2h, Warm <14d/1d, Cold <30d/7d, cutoff=30d
HOT_S = 2 * 3600
WARM_S = 24 * 3600
COLD_S = 7 * 24 * 3600
HOT_MAX = 72 * 3600
WARM_MAX = 14 * 24 * 3600
COLD_MAX = 30 * 24 * 3600
NOW = 1_000_000


def _canon():
    from personalscraper.acquire.cadence import Cadence, CadenceTier

    return Cadence(
        tiers=(
            CadenceTier(max_age_s=HOT_MAX, interval_s=HOT_S),
            CadenceTier(max_age_s=WARM_MAX, interval_s=WARM_S),
            CadenceTier(max_age_s=COLD_MAX, interval_s=COLD_S),
        ),
        cutoff_s=COLD_MAX,
    )


def test_is_due_hot_first_search():
    """age=0, last_search_at=None → due immediately (Hot tier)."""
    from personalscraper.acquire.cadence import is_due_by_cadence

    assert is_due_by_cadence(_canon(), now=NOW, enqueued_at=NOW, last_search_at=None) is True


def test_is_due_hot_too_soon():
    """age=1h, last_search_at=30min ago → NOT due (Hot interval=2h)."""
    from personalscraper.acquire.cadence import is_due_by_cadence

    enqueued = NOW - 3600
    last = NOW - 1800
    assert is_due_by_cadence(_canon(), now=NOW, enqueued_at=enqueued, last_search_at=last) is False


def test_is_due_hot_warm_boundary_minus1s():
    """age=72h-1s → still Hot tier, interval=2h."""
    from personalscraper.acquire.cadence import is_due_by_cadence

    enqueued = NOW - (HOT_MAX - 1)
    last = NOW - HOT_S - 1  # just past interval → due
    assert is_due_by_cadence(_canon(), now=NOW, enqueued_at=enqueued, last_search_at=last) is True


def test_is_due_warm_boundary_plus1s():
    """age=72h+1s → Warm tier, interval=1d."""
    from personalscraper.acquire.cadence import is_due_by_cadence

    enqueued = NOW - (HOT_MAX + 1)
    last = NOW - WARM_S - 1  # just past 1d interval → due
    assert is_due_by_cadence(_canon(), now=NOW, enqueued_at=enqueued, last_search_at=last) is True


def test_is_due_warm_cold_boundary_minus1s():
    """age=14d-1s → still Warm, interval=1d."""
    from personalscraper.acquire.cadence import is_due_by_cadence

    enqueued = NOW - (WARM_MAX - 1)
    last = NOW - WARM_S - 1
    assert is_due_by_cadence(_canon(), now=NOW, enqueued_at=enqueued, last_search_at=last) is True


def test_is_due_cold_boundary_plus1s():
    """age=14d+1s → Cold tier, interval=7d."""
    from personalscraper.acquire.cadence import is_due_by_cadence

    enqueued = NOW - (WARM_MAX + 1)
    last = NOW - COLD_S - 1
    assert is_due_by_cadence(_canon(), now=NOW, enqueued_at=enqueued, last_search_at=last) is True


def test_is_due_cold_too_soon():
    """age=15d, last_search_at=3d ago → NOT due (Cold interval=7d)."""
    from personalscraper.acquire.cadence import is_due_by_cadence

    enqueued = NOW - (15 * 24 * 3600)
    last = NOW - (3 * 24 * 3600)
    assert is_due_by_cadence(_canon(), now=NOW, enqueued_at=enqueued, last_search_at=last) is False


def test_is_past_cutoff_false_before():
    """age=30d-1s → NOT past cutoff."""
    from personalscraper.acquire.cadence import is_past_cutoff

    assert is_past_cutoff(_canon(), now=NOW, enqueued_at=NOW - (COLD_MAX - 1)) is False


def test_is_past_cutoff_true_at():
    """age=30d exactly → past cutoff."""
    from personalscraper.acquire.cadence import is_past_cutoff

    assert is_past_cutoff(_canon(), now=NOW, enqueued_at=NOW - COLD_MAX) is True


def test_is_past_cutoff_true_after():
    """age=30d+1s → past cutoff."""
    from personalscraper.acquire.cadence import is_past_cutoff

    assert is_past_cutoff(_canon(), now=NOW, enqueued_at=NOW - (COLD_MAX + 1)) is True


def test_is_due_returns_false_past_cutoff():
    """is_due_by_cadence returns False when past cutoff (don't search, abandon)."""
    from personalscraper.acquire.cadence import is_due_by_cadence

    enqueued = NOW - (COLD_MAX + 1)
    assert is_due_by_cadence(_canon(), now=NOW, enqueued_at=enqueued, last_search_at=None) is False


def test_cadence_config_default_reproduces_hot_warm_cold():
    """CadenceConfig() must reproduce the DESIGN §3 frozen policy."""
    from personalscraper.conf.models.acquire import CadenceConfig

    cfg = CadenceConfig()
    assert len(cfg.tiers) == 3
    assert cfg.tiers[0].max_age_hours == 72
    assert cfg.tiers[0].interval_minutes == 120
    assert cfg.tiers[1].max_age_hours == 336
    assert cfg.tiers[1].interval_minutes == 1440
    assert cfg.tiers[2].max_age_hours == 720
    assert cfg.tiers[2].interval_minutes == 10080
    assert cfg.cutoff_days == 30


def test_acquire_config_has_cadence_field():
    """AcquireConfig() has a cadence field defaulting to CadenceConfig()."""
    from personalscraper.conf.models.acquire import AcquireConfig, CadenceConfig

    cfg = AcquireConfig()
    assert isinstance(cfg.cadence, CadenceConfig)


def test_cadence_config_rejects_non_monotonic_tiers():
    """CadenceConfig rejects tiers that are not strictly increasing by max_age_hours."""
    from pydantic import ValidationError

    from personalscraper.conf.models.acquire import CadenceConfig, CadenceTierConfig

    # Default must NOT raise (non-vacuous baseline).
    CadenceConfig()

    with pytest.raises(ValidationError):
        CadenceConfig(
            tiers=[
                CadenceTierConfig(max_age_hours=336, interval_minutes=120),
                CadenceTierConfig(max_age_hours=72, interval_minutes=1440),
            ],
            cutoff_days=30,
        )


def test_cadence_config_rejects_cutoff_below_last_tier():
    """CadenceConfig rejects a cutoff that does not extend beyond the last tier."""
    from pydantic import ValidationError

    from personalscraper.conf.models.acquire import CadenceConfig, CadenceTierConfig

    # Default must NOT raise (non-vacuous baseline).
    CadenceConfig()

    with pytest.raises(ValidationError):
        # Last tier max_age_hours = 720h (30d); cutoff_days=20 → 480h, BELOW the last tier.
        CadenceConfig(
            tiers=[CadenceTierConfig(max_age_hours=720, interval_minutes=120)],
            cutoff_days=20,
        )


def test_cadence_config_rejects_empty_and_nonpositive_tiers():
    """CadenceConfig rejects empty tiers and non-positive tier durations.

    Validator-rejection completeness (F-E): pins that the model_validator
    guards ``tiers=[]``, ``max_age_hours=0`` and ``interval_minutes=0``.
    A default ``CadenceConfig()`` must NOT raise (non-vacuous baseline).
    """
    from pydantic import ValidationError

    from personalscraper.conf.models.acquire import CadenceConfig, CadenceTierConfig

    # Default must NOT raise (non-vacuous baseline).
    CadenceConfig()

    with pytest.raises(ValidationError):
        CadenceConfig(tiers=[])

    with pytest.raises(ValidationError):
        CadenceConfig(tiers=[CadenceTierConfig(max_age_hours=0, interval_minutes=120)])

    with pytest.raises(ValidationError):
        CadenceConfig(tiers=[CadenceTierConfig(max_age_hours=72, interval_minutes=0)])


def test_cadence_round_trip_json():
    """cadence_to_json → cadence_from_json round-trips all fields."""
    from personalscraper.acquire.cadence import Cadence, CadenceTier
    from personalscraper.acquire.desired import cadence_from_json, cadence_to_json

    c = Cadence(tiers=(CadenceTier(max_age_s=100, interval_s=10),), cutoff_s=200)
    assert cadence_from_json(cadence_to_json(c)) == c


def test_cadence_from_json_none_returns_none():
    """cadence_from_json(None) returns None (use global default)."""
    from personalscraper.acquire.desired import cadence_from_json

    assert cadence_from_json(None) is None


def test_cadence_from_json_malformed_returns_none():
    """A malformed or semantically-invalid blob fails soft to None (no crash).

    Covers all four except branches of the defensive decode (F-C / F-N) — one
    blob per exception type in ``(JSONDecodeError, KeyError, TypeError,
    ValueError)``:
    - ``"{not json"`` → ``json.JSONDecodeError`` (unparseable JSON),
    - ``'{"tiers": []}'`` → ``KeyError: 'cutoff_s'``: the tiers generator
      yields nothing for the empty list, then ``data["cutoff_s"]`` is accessed
      and raises — the empty-tiers ``ValueError`` in ``Cadence.__post_init__``
      is never reached because the missing-key access happens first,
    - ``'{"tiers": 5, "cutoff_s": 10}'`` → ``TypeError`` (``5`` is an ``int``,
      not iterable — the ``for t in data["tiers"]`` generator raises),
    - a negative ``max_age_s`` → ``ValueError`` from
      ``CadenceTier.__post_init__`` (leaf-guard fires at tier construction).

    Each decodes to ``None`` so the caller falls back to the global default.
    """
    from personalscraper.acquire.desired import cadence_from_json

    assert cadence_from_json("{not json") is None  # JSONDecodeError
    assert cadence_from_json('{"tiers": []}') is None  # KeyError: 'cutoff_s'
    assert cadence_from_json('{"tiers": 5, "cutoff_s": 10}') is None  # TypeError (int not iterable)
    # ValueError from CadenceTier.__post_init__ (negative max_age_s):
    assert cadence_from_json('{"tiers": [{"max_age_s": -1, "interval_s": 1}], "cutoff_s": 5}') is None


def test_cadence_from_config_converts_units():
    """cadence_from_config converts hours/minutes/days → seconds correctly."""
    from personalscraper.acquire.desired import cadence_from_config
    from personalscraper.conf.models.acquire import CadenceConfig, CadenceTierConfig

    cfg = CadenceConfig(tiers=[CadenceTierConfig(max_age_hours=1, interval_minutes=30)], cutoff_days=2)
    c = cadence_from_config(cfg)
    assert c.tiers[0].max_age_s == 3600
    assert c.tiers[0].interval_s == 1800
    assert c.cutoff_s == 2 * 24 * 3600


def test_effective_cadence_series_wins():
    """effective_cadence returns series override when not None."""
    from personalscraper.acquire.cadence import Cadence, CadenceTier
    from personalscraper.acquire.desired import effective_cadence

    override = Cadence(tiers=(CadenceTier(max_age_s=10, interval_s=1),), cutoff_s=20)
    default = Cadence(tiers=(CadenceTier(max_age_s=999, interval_s=999),), cutoff_s=999)
    assert effective_cadence(override, default) is override


def test_effective_cadence_none_returns_default():
    """effective_cadence(None, default) returns default verbatim."""
    from personalscraper.acquire.cadence import Cadence, CadenceTier
    from personalscraper.acquire.desired import effective_cadence

    default = Cadence(tiers=(CadenceTier(max_age_s=999, interval_s=999),), cutoff_s=999)
    assert effective_cadence(None, default) is default


# --- Dead-band fix (F-A) ----------------------------------------------------

# Cadence whose cutoff extends BEYOND the last tier (40d cutoff, 30d last tier):
# ages in [720h, 960h) now search at the Cold cadence instead of freezing.
CUTOFF_BEYOND_S = 960 * 3600  # 40 days


def _canon_cutoff_beyond():
    from personalscraper.acquire.cadence import Cadence, CadenceTier

    return Cadence(
        tiers=(
            CadenceTier(max_age_s=HOT_MAX, interval_s=HOT_S),
            CadenceTier(max_age_s=WARM_MAX, interval_s=WARM_S),
            CadenceTier(max_age_s=COLD_MAX, interval_s=COLD_S),
        ),
        cutoff_s=CUTOFF_BEYOND_S,
    )


def test_is_due_dead_band_uses_last_tier_interval():
    """Age in [last-tier, cutoff) with last_search past Cold interval → due.

    Mutation-proof: under the pre-fix ``return False`` (no tier matches), this
    item would be frozen and the assert would be False. The fix falls back to
    the last (Cold) tier's interval, so a search one Cold interval + 1s old is
    due.
    """
    from personalscraper.acquire.cadence import is_due_by_cadence

    enqueued = NOW - (800 * 3600)  # age=800h ∈ [720h, 960h) → beyond last tier
    last = NOW - COLD_S - 1  # one Cold interval (7d) + 1s back → due
    assert is_due_by_cadence(_canon_cutoff_beyond(), now=NOW, enqueued_at=enqueued, last_search_at=last) is True


def test_is_due_dead_band_too_recent_not_due():
    """Same dead-band window but last_search 3 days back → NOT due.

    Interval-DISCRIMINATING negative control (F-P): pins that the dead-band
    fallback applies the LAST (Cold, 7d) tier's interval — not a shorter one
    and not a blanket freeze. The ``last_search_at`` is chosen so the gap
    (3 days) sits strictly BETWEEN the Hot interval (2h) and the Cold interval
    (7d):

      Hot 2h (7200s)  <  3 days (259200s)  <  Cold 7d (604800s)

    - Under the real Cold-interval fallback: ``259200 >= 604800`` is False →
      NOT due (asserted here).
    - If the fallback regressed to a SHORTER interval (e.g. Hot 2h):
      ``259200 >= 7200`` is True → it would FLIP to due, failing this assert.

    A 1h-back search (the previous value) was ``< both`` intervals, so it
    could not distinguish Cold from Hot and was a weak control. It also still
    catches the pre-fix blanket ``return False`` because the paired
    ``test_is_due_dead_band_uses_last_tier_interval`` (same window, older
    search) asserts True — the pre-fix freeze would have made THAT False.
    """
    from personalscraper.acquire.cadence import is_due_by_cadence

    enqueued = NOW - (800 * 3600)  # age=800h, beyond last tier, before cutoff
    # 3 days back: > Hot interval (2h) but < Cold interval (7d) → not due ONLY
    # if the fallback uses the Cold interval, not a shorter one.
    last = NOW - (3 * 24 * 3600)
    assert is_due_by_cadence(_canon_cutoff_beyond(), now=NOW, enqueued_at=enqueued, last_search_at=last) is False


# --- Cadence VO invariant guard (F-B) ---------------------------------------


def test_cadence_post_init_canonical_builds():
    """Positive control: the canonical Cadence (cutoff == last tier) builds clean."""
    _canon()  # must not raise under the new __post_init__ guard


def test_cadence_post_init_rejects_empty_tiers():
    """Empty tiers → ValueError.

    ``match=`` pins the exact guard message so a future guard-reorder that
    swallows the empty check (or changes the wording) is a caught regression.
    """
    from personalscraper.acquire.cadence import Cadence

    with pytest.raises(ValueError, match="tiers must not be empty"):
        Cadence(tiers=(), cutoff_s=100)


def test_cadence_post_init_rejects_nonpositive():
    """A non-positive max_age_s or interval_s → ValueError.

    The leaf-level :meth:`CadenceTier.__post_init__` guard fires first (the
    tier is constructed before the enclosing ``Cadence`` body runs), so these
    raise at tier construction with a TIER-level message — still a
    ``ValueError``. ``match=`` therefore pins the CadenceTier message
    (``"max_age_s must be positive"`` / ``"interval_s must be positive"``),
    not the Cadence-body wording, which is what actually fires.
    """
    from personalscraper.acquire.cadence import Cadence, CadenceTier

    with pytest.raises(ValueError, match="max_age_s must be positive"):
        Cadence(tiers=(CadenceTier(max_age_s=0, interval_s=10),), cutoff_s=100)
    with pytest.raises(ValueError, match="interval_s must be positive"):
        Cadence(tiers=(CadenceTier(max_age_s=100, interval_s=0),), cutoff_s=100)


def test_cadence_tier_rejects_nonpositive():
    """CadenceTier leaf guard rejects a non-positive max_age_s or interval_s.

    Independent of any enclosing :class:`Cadence`: a malformed tier is
    unrepresentable on its own. A valid tier still builds (positive control).
    """
    from personalscraper.acquire.cadence import CadenceTier

    with pytest.raises(ValueError, match="max_age_s must be positive"):
        CadenceTier(max_age_s=0, interval_s=1)
    with pytest.raises(ValueError, match="interval_s must be positive"):
        CadenceTier(max_age_s=1, interval_s=-1)
    # Positive control: a valid tier builds without raising.
    CadenceTier(max_age_s=1, interval_s=1)


def test_cadence_post_init_rejects_non_monotonic():
    """Tiers not strictly increasing by max_age_s → ValueError.

    ``match=`` pins the monotonicity-guard wording so a guard-reorder that
    drops the strictly-increasing check is a caught regression.
    """
    from personalscraper.acquire.cadence import Cadence, CadenceTier

    with pytest.raises(ValueError, match="strictly increasing"):
        Cadence(
            tiers=(
                CadenceTier(max_age_s=200, interval_s=10),
                CadenceTier(max_age_s=100, interval_s=20),
            ),
            cutoff_s=300,
        )


def test_cadence_post_init_rejects_cutoff_below_last_tier():
    """cutoff_s below the last tier's max_age_s → ValueError.

    ``match=`` pins the cutoff-guard wording so a guard-reorder that drops the
    cutoff >= last-tier check is a caught regression.
    """
    from personalscraper.acquire.cadence import Cadence, CadenceTier

    with pytest.raises(ValueError, match="cutoff_s must be >="):
        Cadence(tiers=(CadenceTier(max_age_s=100, interval_s=10),), cutoff_s=50)


def test_cadence_module_imports_are_pure() -> None:
    """PURITY (DESIGN §11 criterion 9): cadence.py imports stdlib only.

    AST-parses ``personalscraper/acquire/cadence.py`` and asserts every
    imported top-level module is in the stdlib allowlist — pinning that no
    ``store``/``indexer``/``scraper``/``event_bus``/``conf``/``personalscraper.*``
    runtime import sneaks into the pure cadence value-object module.
    """
    import ast
    from pathlib import Path

    allowed = {"__future__", "dataclasses"}
    src = Path("personalscraper/acquire/cadence.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top in allowed, f"Forbidden import in cadence.py: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            top = module.split(".")[0]
            assert top in allowed, f"Forbidden import in cadence.py: {module}"
