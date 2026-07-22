# Contributing to Ultra Fetch

Thanks for your interest in Ultra Fetch. This is a small, personal Claude Code skill project — the
process below is intentionally lightweight. If you're the maintainer working solo, this is also
the checklist to follow for your own changes.

## Scope

Ultra Fetch is deliberately narrow: a `fetch`/`crawl`/`map` CLI plus the skill that teaches Claude
to use it, covering public web content only. Before proposing a feature, check
[`docs/plan/01-decisions.md`](docs/plan/01-decisions.md) and
[`docs/wiki/Design-Decisions.md`](docs/wiki/Design-Decisions.md) — authenticated fetching, LLM-API
features (an in-CLI Q&A model, `LLMContentFilter`), and screenshot/PDF export were all considered
and explicitly cut from v1 for reasons recorded there. Reopening one of those needs a new argument,
not just a request.

Welcome:
- Bug reports against a real site (a URL that misbehaves, with the CLI invocation used)
- Fixes with a measured before/after, not just a plausible-sounding change
- Documentation improvements

## Ways to contribute

- **Issues** — a bug, a site that fails in a specific way, or a documentation gap.
- **Pull requests** — see the workflow below.
- **Nothing else is currently set up** (no issue templates, no discussion board) — open an issue for anything that doesn't fit a PR.

## Development setup

The CLI is not installed and not on `PATH`; it always runs through its launcher, which provisions
its own environment on first use:

```bash
.claude/skills/ultra-fetch/scripts/ultra-fetch catalog
```

The first invocation creates a dedicated virtualenv at `~/.cache/ultra-fetch/venv` (deliberately
outside the repo — see [`docs/wiki/Development-Guide.md`](docs/wiki/Development-Guide.md)) and
downloads both browser stacks (several hundred MB, once). There is no project-local virtualenv;
running `python -m pytest` with a system interpreter will fail on missing imports.

## Tests & checks

```bash
~/.cache/ultra-fetch/venv/bin/python -m pytest .claude/skills/ultra-fetch/tests/ -q
```

Unit tests cover pure logic only (escalation decisions, the collapse guard, catalog integrity,
output-path rules) and never touch the network. **They are not sufficient to verify a change to
fetching, escalation, or crawling** — those need a real run against a real site, because a passing
suite proves nothing about whether a site's bot wall moved. Run the CLI directly against a live URL
before calling such a change done.

## Making a change

- Branch names follow `<type>/<short-description>`, matching this repo's history: `feat/…`,
  `fix/…`, `docs/…`, `test/…`.
- Commit messages are short and state what changed and why.
- Open a PR against `main` describing what was tested (unit tests, and — for anything touching
  access/refine/crawl — the real site(s) it was run against) and merge once it's green.
- A PR that changes extraction thresholds or the grounding guidance in `SKILL.md` should re-run the
  broader scenario set described in `docs/wiki/Validation-History.md`, not just the file it edited
  — several fixes in this project's history repaired one behavior while silently breaking another.

## Code style

No separate formatter or linter config is checked in; `pyflakes` is used ad hoc to catch unused
imports and undefined names. Match the style already in `.claude/skills/ultra-fetch/scripts/ultra_fetch/`
— module-per-concern, a docstring only where a threshold or a decision needs its rationale recorded,
no comments that just restate the code.

## Reporting bugs / requesting features

Open a GitHub issue. Include the exact `ultra-fetch` command you ran, the URL, the exit code, and
(if relevant) the saved output file's content — this project has repeatedly found real defects only
by running the tool against a real site, so a concrete reproduction is worth far more than a
description of the symptom.

## Code of Conduct

Participation in this project is covered by [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).
