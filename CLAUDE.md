# Ultra Fetch

A Claude Code skill plus a bundled Python CLI that reads, crawls and maps web pages that the built-in `WebFetch` can't reach or can't return usefully. See `.claude/harness-spec.md` for the harness inventory and design rationale, and `docs/plan/` for the full decision log.

## Using the tool

When you need to actually read a web page's content, reach a site WebFetch can't, crawl a site, or save fetched content to a file, use the `/ultra-fetch` skill rather than WebFetch.

## Working on the tool

- The CLI is not installed and not on PATH. Run it through its launcher: `.claude/skills/ultra-fetch/scripts/ultra-fetch <command>`.
- It runs from a dedicated venv at `~/.cache/ultra-fetch/venv`, deliberately outside the repo. There is no project virtualenv; `python -m pytest` from a system interpreter will fail on missing imports. Tests: `~/.cache/ultra-fetch/venv/bin/python -m pytest .claude/skills/ultra-fetch/tests/ -q`.
- Unit tests cover pure logic only and never touch the network. Changes to fetching, escalation or crawling need a real run against a real site to be considered verified — a passing suite proves nothing about whether a site's bot wall moved.
- `docs/plan/` records decisions already made and argued (no PyPI, no auth, no LLM features in v1). Read the relevant entry before reopening one.
