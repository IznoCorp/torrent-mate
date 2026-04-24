# Phase 03 — `print()` cleanup

**Goal**: no `print(` call remains in production modules.

## Sub-phase 3.1 — Replace confidence prompt prints with `typer.echo`

Target : `personalscraper/scraper/confidence.py` lines 364-369.

- Replace all `print(...)` with `typer.echo(...)`.
- `input(...)` stays as-is — that is the interactive prompt; `typer.prompt` is overkill for a numeric menu.
- Update the one unit test that captures the prompt output if it asserts on stdout.

### Commit

`refactor(scraper): route confidence prompt output through typer.echo`

## Sub-phase 3.2 — Replace cli.py info print with Rich console

Target : `personalscraper/cli.py:1020` — `print(format_info(report))`.

- Replace with `state["console"].print(format_info(report))`.
- Verify the info subcommand still renders correctly by invoking `personalscraper info` in a smoke test.

### Commit

`refactor(cli): route info command output through rich console`

### Quality gate (after 3.2)

- Full test suite green.
- `scripts/check_logging.py` shows zero `print(` findings in `personalscraper/`.
