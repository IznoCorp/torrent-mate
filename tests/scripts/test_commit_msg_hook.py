"""The commit-msg hook's AI-attribution ban: it refuses a TRAILER, not English.

B-058. Two of the hook's four alternatives were unanchored, so they matched
anywhere in the message — and a commit explaining this very ban was refused by
the hook it was explaining. The two that were already anchored never had the
problem, which is what proved the anchor is the answer rather than a weaker
pattern.

WHY THIS IS A TEST AND NOT A ONE-OFF RUN. The hook is compliance-relevant, the
register's own entry says so, and « a same-commit reflex fix on a guard like
this is exactly the haste this register exists to slow down ». A pattern that
was loosened once can be loosened again by someone chasing a false positive; the
four REFUSALS below are what stops that, and they are the half a loosening
breaks first.

The hook is run as a process, the way git runs it, so what is tested is the file
git executes and not a Python transcription of it.
"""
import pathlib
import subprocess

import pytest

HOOK = pathlib.Path(__file__).resolve().parents[2] / "hooks" / "commit-msg"

# The real footers. Every one begins its line, which is what a trailer does and
# what the anchors read.
REFUSED = {
    "the Claude Code footer, verbatim":
        "fix(scope): a thing\n\n"
        "🤖 Generated with [Claude Code](https://claude.com/claude-code)\n",
    "a Co-Authored-By trailer":
        "fix(scope): a thing\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n",
    "a Claude-Session trailer":
        "fix(scope): a thing\n\nClaude-Session: https://claude.ai/code/session_x\n",
    "a bare generated-with footer":
        "fix(scope): a thing\n\nGenerated with Claude Code\n",
    "the same trailer indented, which is still a trailer":
        "fix(scope): a thing\n\n  Co-Authored-By: Anthropic\n",
}

# English about the ban. Refusing these is refusing the documentation of the
# rule, which is what happened.
ACCEPTED = {
    "prose describing the footer":
        "docs(scope): explain the hook\n\n"
        "The hook refuses a footer reading « Generated with Claude Code » and one\n"
        "carrying the 🤖 emoji, which is what CLAUDE.md forbids.\n",
    "prose quoting the trailer mid-sentence":
        "docs(scope): explain the hook\n\n"
        "It refuses a Co-Authored-By: Claude trailer, mid-sentence like this.\n",
    "an ordinary message naming neither":
        "fix(scope): repair the thing\n\nIt was broken and now it is not.\n",
}


def run_hook(tmp_path, message):
    """Runs the hook on one message, the way git does.

    Args:
        tmp_path: pytest's per-test directory.
        message: The commit message to write and check.

    Returns:
        The hook's exit code.
    """
    target = tmp_path / "COMMIT_EDITMSG"
    target.write_text(message, encoding="utf-8")
    return subprocess.run(["bash", str(HOOK), str(target)],
                          capture_output=True, text=True, check=False).returncode


@pytest.mark.parametrize("what", sorted(REFUSED))
def test_a_real_attribution_trailer_is_refused(tmp_path, what):
    assert run_hook(tmp_path, REFUSED[what]) == 1, (
        f"{what} was accepted; the ban is compliance-relevant and this half is "
        "what a loosened pattern breaks first")


@pytest.mark.parametrize("what", sorted(ACCEPTED))
def test_english_about_the_ban_is_accepted(tmp_path, what):
    assert run_hook(tmp_path, ACCEPTED[what]) == 0, (
        f"{what} was refused — B-058: the hook caught prose because two of its "
        "four alternatives were not anchored to a line start")
