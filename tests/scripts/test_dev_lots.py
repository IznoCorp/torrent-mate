"""The lots progress generator (`scripts/dev_lots.py`), held on fixtures.

The generator reads a lots definition, the plans and the dispatch record it
names, and the repository's pull requests, and writes the JSON the design
host's `/dev/lots` page draws. Nothing here touches the network: the pull
requests come from `tests/fixtures/dev_lots/prs.json` through an injected
runner, and every output lands in `tmp_path`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import dev_lots
import pytest

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "dev_lots"


def fixture_prs(arguments: list[str]) -> str:
    """Answers the pull-request listing from the fixture, as `gh` would print it.

    Args:
        arguments: The command line the generator asked to run.

    Returns:
        The fixture's JSON text.
    """
    return (FIXTURES / "prs.json").read_text(encoding="utf-8")


def failing_gh(arguments: list[str]) -> str:
    """Fails as `gh` does when it cannot answer.

    Args:
        arguments: The command line the generator asked to run.

    Raises:
        subprocess.CalledProcessError: Always.
    """
    raise subprocess.CalledProcessError(1, arguments)


def generated(tmp_path: Path, runner=fixture_prs) -> dict:
    """Runs the generator over a copy of the fixtures and reads what it wrote.

    Args:
        tmp_path: The pytest scratch directory.
        runner: What answers the pull-request listing.

    Returns:
        The written JSON.
    """
    source = tmp_path / "source"
    shutil.copytree(FIXTURES, source)
    out = tmp_path / "out" / "dev-lots.json"
    status = dev_lots.main(
        {"TM_DEV_LOTS_DEFINITION": str(source / "lots.json"), "TM_DEV_LOTS_OUT": str(out)},
        run_gh=runner,
    )
    assert status == 0
    return json.loads(out.read_text(encoding="utf-8"))


def phases_of(document: dict, lot_id: str) -> dict[str, dict]:
    """Indexes one lot's phases by id.

    Args:
        document: The generated JSON.
        lot_id: The lot.

    Returns:
        The lot's phases, by id.
    """
    lot = next(lot for lot in document["lots"] if lot["id"] == lot_id)
    return {phase["id"]: phase for phase in lot["phases"]}


def test_phase_titles_come_from_the_plan_headings() -> None:
    """A level-two heading names a phase; its title loses the decorations."""
    titles = dev_lots.plan_titles((FIXTURES / "PLAN.md").read_text(encoding="utf-8"))
    assert titles == {
        "P1": "the first phase (conversion)",
        "P2": "the second phase",
        "P3": "the third phase",
        "OP-1": "the operation owed by hand",
    }


def test_a_merged_pull_request_makes_the_phase_merged(tmp_path: Path) -> None:
    """The phase whose PR merged is merged, its closed-unmerged PR left out."""
    phase = phases_of(generated(tmp_path), "alpha")["P1"]
    assert phase["state"] == "merged"
    assert phase["title"] == "the first phase (conversion)"
    assert phase["prs"] == [{"number": 11, "url": "https://github.com/example/repo/pull/11", "state": "merged"}]


def test_an_open_pull_request_makes_the_phase_pr_open(tmp_path: Path) -> None:
    """An open PR whose branch ends with the codename; a longer codename is another phase's."""
    phase = phases_of(generated(tmp_path), "alpha")["P2"]
    assert phase["state"] == "pr-open"
    assert [pr["number"] for pr in phase["prs"]] == [13]


def test_an_active_dispatch_row_without_pr_makes_the_phase_in_progress(tmp_path: Path) -> None:
    """A row in flight and no PR yet: in progress, the row's state word carried."""
    phase = phases_of(generated(tmp_path), "alpha")["P3"]
    assert phase["state"] == "in-progress"
    assert phase["dispatch"] == "in-flight"
    assert phase["prs"] == []


def test_nothing_started_is_planned_and_says_what_blocks_it(tmp_path: Path) -> None:
    """No PR, no active row: planned, with the definition's blocker for the phase and the lot."""
    document = generated(tmp_path)
    phase = phases_of(document, "alpha")["OP-1"]
    assert phase["state"] == "planned"
    assert phase["blockedBy"] == "Owed by hand"
    lot = next(lot for lot in document["lots"] if lot["id"] == "alpha")
    assert lot["blockedBy"] == "Waits for the sample decision"


def test_a_missing_plan_falls_back_to_the_definition_title(tmp_path: Path) -> None:
    """A plan that is absent costs the titles, never the lot."""
    phase = phases_of(generated(tmp_path), "beta")["B1"]
    assert phase["title"] == "The title the definition gives"
    assert phase["state"] == "planned"


def test_no_orchestration_text_is_copied_out(tmp_path: Path) -> None:
    """The dispatch record's labels and the input paths never reach the output."""
    generated(tmp_path)
    text = (tmp_path / "out" / "dev-lots.json").read_text(encoding="utf-8")
    assert "sample row" not in text
    assert str(tmp_path / "source") not in text


def test_the_output_is_stamped_and_available(tmp_path: Path) -> None:
    """A complete run says it is available and when it was generated."""
    document = generated(tmp_path)
    assert document["available"] is True
    assert isinstance(document["generatedAt"], int)
    assert [lot["id"] for lot in document["lots"]] == ["alpha", "beta"]


def test_the_pull_requests_are_listed_once_read_only(tmp_path: Path) -> None:
    """One `gh pr list` over every state, asking only the fields the page draws."""
    asked: list[list[str]] = []

    def recording(arguments: list[str]) -> str:
        asked.append(arguments)
        return fixture_prs(arguments)

    generated(tmp_path, recording)
    assert len(asked) == 1
    assert asked[0][:4] == ["gh", "pr", "list", "--state"]
    assert "all" in asked[0]
    assert "number,title,state,headRefName,url" in asked[0]


@pytest.mark.parametrize("unset", ["TM_DEV_LOTS_DEFINITION", "both"])
def test_an_unconfigured_generator_writes_nothing_to_show(tmp_path: Path, unset: str) -> None:
    """Without the definition's path the output says it is unavailable, or nothing is written."""
    out = tmp_path / "dev-lots.json"
    environment = {} if unset == "both" else {"TM_DEV_LOTS_OUT": str(out)}
    assert dev_lots.main(environment, run_gh=fixture_prs) == 0
    if unset == "both":
        assert not out.exists()
    else:
        assert json.loads(out.read_text(encoding="utf-8")) == {"available": False}


@pytest.mark.parametrize("missing", ["lots.json", "dispatch.jsonl"])
def test_an_absent_input_writes_nothing_to_show(tmp_path: Path, missing: str) -> None:
    """An absent definition or dispatch record: the page shows nothing rather than half."""
    source = tmp_path / "source"
    shutil.copytree(FIXTURES, source)
    (source / missing).unlink()
    out = tmp_path / "dev-lots.json"
    status = dev_lots.main(
        {"TM_DEV_LOTS_DEFINITION": str(source / "lots.json"), "TM_DEV_LOTS_OUT": str(out)},
        run_gh=fixture_prs,
    )
    assert status == 0
    assert json.loads(out.read_text(encoding="utf-8")) == {"available": False}


def test_a_failed_listing_keeps_the_previous_output(tmp_path: Path) -> None:
    """`gh` failing exits non-zero and leaves the last good output in place."""
    source = tmp_path / "source"
    shutil.copytree(FIXTURES, source)
    out = tmp_path / "dev-lots.json"
    out.write_text('{"available": true, "lots": []}', encoding="utf-8")
    status = dev_lots.main(
        {"TM_DEV_LOTS_DEFINITION": str(source / "lots.json"), "TM_DEV_LOTS_OUT": str(out)},
        run_gh=failing_gh,
    )
    assert status == 1
    assert out.read_text(encoding="utf-8") == '{"available": true, "lots": []}'


def run_main(tmp_path: Path, runner=fixture_prs, *, definition: str | None = None, dispatch: str | None = None):
    """Runs the generator over a copy of the fixtures, optionally with an input replaced.

    Args:
        tmp_path: The pytest scratch directory.
        runner: What answers the pull-request listing.
        definition: Text to write as the lots definition instead of the fixture's.
        dispatch: Text to write as the dispatch record instead of the fixture's.

    Returns:
        The exit status and the output path, which holds a previous good output.
    """
    source = tmp_path / "source"
    shutil.copytree(FIXTURES, source)
    if definition is not None:
        (source / "lots.json").write_text(definition, encoding="utf-8")
    if dispatch is not None:
        (source / "dispatch.jsonl").write_text(dispatch, encoding="utf-8")
    out = tmp_path / "dev-lots.json"
    out.write_text(PREVIOUS, encoding="utf-8")
    status = dev_lots.main(
        {"TM_DEV_LOTS_DEFINITION": str(source / "lots.json"), "TM_DEV_LOTS_OUT": str(out)},
        run_gh=runner,
    )
    return status, out


PREVIOUS = '{"available": true, "lots": []}'


def test_a_failed_replace_keeps_the_previous_file_and_leaves_no_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The write is atomic: when the final replace fails, the old output stands and no temp file stays."""
    out = tmp_path / "dev-lots.json"
    out.write_text(PREVIOUS, encoding="utf-8")

    def refusing(self: Path, target: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(Path, "replace", refusing)
    with pytest.raises(OSError, match="disk full"):
        dev_lots.write(out, {"available": False})
    assert out.read_text(encoding="utf-8") == PREVIOUS
    assert list(tmp_path.glob("*.partial")) == []


def test_a_malformed_dispatch_line_is_skipped_with_a_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Bad JSON, a non-object line and a row without an id are each skipped; the good rows still count."""
    record = tmp_path / "dispatch.jsonl"
    record.write_text('{not json\n[1, 2]\n{"state": "armed"}\n\n{"id": 7, "state": "armed"}\n', encoding="utf-8")
    assert dev_lots.read_dispatch(record) == {7: "armed"}
    assert capsys.readouterr().err.count("dev-lots: skipped a malformed dispatch line") == 3


def failing_with(failure: Exception):
    """Builds a runner that raises the given failure, as `gh` would.

    Args:
        failure: What to raise.

    Returns:
        The runner.
    """

    def runner(arguments: list[str]) -> str:
        raise failure

    return runner


@pytest.mark.parametrize(
    "runner",
    [
        failing_with(FileNotFoundError("gh")),
        failing_with(subprocess.TimeoutExpired("gh", 60)),
        lambda arguments: "this is not json",
        lambda arguments: '{"number": 1}',
        lambda arguments: "null",
        lambda arguments: "[1, 2]",
    ],
    ids=["gh-missing", "gh-timeout", "bad-json", "object-not-list", "null", "list-of-non-objects"],
)
def test_a_bad_listing_keeps_the_previous_output(tmp_path: Path, runner) -> None:
    """Any way the listing can be unusable takes the clean path: exit 1, previous output kept."""
    status, out = run_main(tmp_path, runner)
    assert status == 1
    assert out.read_text(encoding="utf-8") == PREVIOUS


@pytest.mark.parametrize("definition", ["{broken", "[1, 2]"], ids=["bad-json", "not-an-object"])
def test_a_malformed_definition_keeps_the_previous_output(tmp_path: Path, definition: str) -> None:
    """A definition that is not a JSON object exits 1 with the previous output kept."""
    status, out = run_main(tmp_path, definition=definition)
    assert status == 1
    assert out.read_text(encoding="utf-8") == PREVIOUS


def test_a_malformed_dispatch_line_does_not_stop_a_run(tmp_path: Path) -> None:
    """The whole run goes through with a bad line in the record."""
    source_record = (FIXTURES / "dispatch.jsonl").read_text(encoding="utf-8")
    status, out = run_main(tmp_path, dispatch="{oops\n" + source_record)
    assert status == 0
    assert json.loads(out.read_text(encoding="utf-8"))["available"] is True


def test_the_lot_details_pass_through_when_given_and_are_absent_otherwise(tmp_path: Path) -> None:
    """The optional per-lot fields reach the document; a lot without them carries none of the keys."""
    document = generated(tmp_path)
    alpha = next(lot for lot in document["lots"] if lot["id"] == "alpha")
    assert alpha["description"] == "What the sample lot does"
    assert alpha["note"] == "A note about the sample lot"
    assert (alpha["start"], alpha["end"]) == ("2026-09-01", "2026-10-15")
    assert alpha["estimated"] is True
    assert alpha["duration"] == "six weeks"
    beta = next(lot for lot in document["lots"] if lot["id"] == "beta")
    assert not {"description", "note", "start", "end", "estimated", "duration"} & beta.keys()


def test_the_dispatch_states_the_generator_carries_each_have_a_word_on_the_page() -> None:
    """The generator's active states and the page's `dispatch.*` words are one set, in both languages."""
    strings = Path(__file__).resolve().parents[2] / "webui" / "design" / "src" / "i18n"
    for language in ("fr", "en"):
        words = json.loads((strings / f"{language}.json").read_text(encoding="utf-8"))["screens"]["devLots"]["dispatch"]
        assert set(words) - {"unknown"} == set(dev_lots.ACTIVE_DISPATCH), language
        assert "unknown" in words, language
