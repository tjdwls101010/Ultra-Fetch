# Development Guide

How to work on Ultra Fetch's own code — the dedicated environment, running tests, and the traps
that have already bitten this project once. For making a change, not just using the CLI.

## 1. Layout

```
scripts/
├── ultra-fetch          bash launcher: resolves the venv, provisions on first run, execs the CLI
├── requirements.txt     pinned scrapling + crawl4ai
└── ultra_fetch/
    ├── cli.py           argparse, dispatch, exit-code mapping, `catalog`
    ├── access.py        scrapling: fast static → stealth escalation
    ├── refine.py        crawl4ai: Pruning/BM25 on an HTML string → markdown
    ├── fetch.py         the `fetch` command (sequences access → refine → output)
    ├── crawl.py         the `crawl` command (crawl4ai deep crawl + manifest)
    ├── mapper.py        the `map` command (AsyncUrlSeeder / DomainMapper)
    ├── output.py        file writing, the stderr contract, library log silencing
    ├── setup.py         venv provisioning, browser install, upgrade, doctor
    ├── config.py        every default and threshold, each with its rationale
    └── errors.py        exception → exit-code contract
```

The package is **not distributable** — no `pyproject.toml`, no entry points, no PyPI publish (see
[Design Decisions §3](Design-Decisions.md#3-why-skill-bundled-code-no-pypi-package)). It's imported
only as `python -m ultra_fetch`, with `scripts/` on `PYTHONPATH`, which the launcher sets.

## 2. The dedicated venv + launcher

The venv lives at `${XDG_CACHE_HOME:-$HOME/.cache}/ultra-fetch/venv` — deliberately **outside the
repo**, so it survives skill edits and is never committed. **That path is written in two places**
(the `ultra-fetch` launcher script, and `config.VENV_DIR`) — they must agree, so change both
together if either ever moves.

```bash
.claude/skills/ultra-fetch/scripts/ultra-fetch setup --browsers   # provision from scratch; idempotent, repairs a partial install
.claude/skills/ultra-fetch/scripts/ultra-fetch setup --doctor     # crawl4ai-doctor + a scrapling fetch + a refine round-trip
.claude/skills/ultra-fetch/scripts/ultra-fetch setup --upgrade    # bump both libraries, then re-pin requirements.txt
```

## 3. Running tests

```bash
~/.cache/ultra-fetch/venv/bin/python -m pytest .claude/skills/ultra-fetch/tests/ -q
```

There is no project-local virtualenv — the CLI is not installed and not on `PATH`, and a system
Python running `pytest` directly will fail on missing imports. Unit tests cover **pure logic only**
(escalation decisions, the collapse guard, catalog integrity, output-path rules) and never touch the
network — network behavior can only be verified by running the CLI against a real site, because a
mocked fetch can't tell you whether a site's bot wall changed. See [Validation
History](Validation-History.md) for what real-site testing has actually found that unit tests
couldn't.

## 4. Making a change

- Keep `cli.py` thin — parsing and dispatch only. Every real judgment (when to escalate, what to
  filter, how to cap a crawl) belongs in its own concern module.
- A new default or threshold goes in `config.py` **with a comment explaining its rationale** — every
  existing constant there carries one, because a threshold without a reason is one nobody can safely
  tune later.
- If a change touches extraction thresholds (`PRUNE_THRESHOLD`, `PRUNE_PRESERVE_TAGS`,
  `BM25_THRESHOLD`, the shell-detection constants) or the grounding guidance in `SKILL.md`, re-run
  the broader scenario set in [Validation History](Validation-History.md), not just the page you were
  fixing — this project's history includes two separate cases where a fix for one page silently
  broke detection on another.

## 5. Upgrading dependencies

Dependencies are pinned on purpose (see [Design Decisions
§12](Design-Decisions.md#12-why-dependencies-are-pinned-not-auto-upgraded)). When a site starts
blocking requests, or a library ships a fix you need:

```bash
.claude/skills/ultra-fetch/scripts/ultra-fetch setup --upgrade
~/.cache/ultra-fetch/venv/bin/python -m pytest .claude/skills/ultra-fetch/tests/ -q
```

`--upgrade` re-pins `requirements.txt` to whatever version combination it just proved installable
together — both libraries are Playwright-family sharing one venv, so recording what actually works
matters more than floating the versions.

## 6. Things that will bite you

- **Silence library logging *after* importing the library, never before.** `scrapling` sets its own
  logger level at import time, silently overwriting anything set earlier. Without
  `output.silence_library_logging()` called at each import site, `scrapling` logs an INFO line per
  request and a bare `ERROR: No Cloudflare challenge found.` on every stealth fetch of a
  *non*-Cloudflare site — which breaks the one-line stderr contract and reads as a failure when
  nothing failed.
- **Unit mismatch across the libraries.** `scrapling`'s HTTP fetcher takes seconds, its browser
  fetchers take milliseconds, and `crawl4ai`'s `page_timeout` is milliseconds. This CLI is seconds
  everywhere at its own boundary; conversion happens at each library call site.
- **`--query` (BM25) can correctly return nothing.** It ranks a chunk by how much it stands out
  *within one page*, so a page uniformly about the query has nothing that stands out and the filter
  correctly keeps nothing. The collapse guard falls back to the full clean page — this is right, not
  a bug.
- **A thin page is not a blocked page.** `access.py`'s diagnosis splits hard signals (a bot-wall
  status code, a challenge-page marker) from soft ones (little text). Only hard signals may be
  terminal — treating "short" as terminal reported `example.com` (142 genuine chars) as unreachable.
- **Two browser stacks.** `scrapling` installs Patchright's Chromium; `crawl4ai` installs
  Playwright's. They live in separate caches and coexist fine, but both download once at setup.

## 7. Where the deeper reasoning lives

This guide covers the mechanics. For the *why* behind the architecture and every default, see
[`docs/plan/`](../plan/) (the original implementation brief, read in order 00→06) and
[`.claude/harness-spec.md`](../../.claude/harness-spec.md) (the canonical, continuously-updated spec
this project is audited against) — or the wiki's own [Design Decisions](Design-Decisions.md) and
[Validation History](Validation-History.md) for the same material in a more digestible form.

---
**Next:** [Design Decisions](Design-Decisions.md) for why the code is shaped this way, or
[Validation History](Validation-History.md) for the testing methodology behind §4's re-run
guidance. Back to the [index](README.md).
