# ultra-fetch CLI — developer notes

Implementation notes for maintaining this CLI. For *using* it, read `../SKILL.md`;
for the authoritative flag list, run `./ultra-fetch catalog`.

## Layout

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

The package is **not** distributable: no `pyproject.toml`, no entry points, no PyPI.
It is imported only as `python -m ultra_fetch` with `scripts/` on `PYTHONPATH`, which
the launcher sets. See `docs/plan/01-decisions.md` D3 for why.

## Environment

The venv lives at `${XDG_CACHE_HOME:-$HOME/.cache}/ultra-fetch/venv` — outside the repo, so
it survives skill edits and is never committed. **That path is written in two places**
(`ultra-fetch` the launcher, and `config.VENV_DIR`); they must agree.

```bash
./ultra-fetch setup --browsers   # provision from scratch (idempotent; repairs a partial install)
./ultra-fetch setup --doctor     # crawl4ai-doctor + a scrapling fetch + a refine round-trip
./ultra-fetch setup --upgrade    # bump both libraries, then re-pin requirements.txt
```

## Tests

```bash
"$HOME/.cache/ultra-fetch/venv/bin/python" -m pytest tests/ -q
```

Unit tests cover only pure logic — escalation decisions, the collapse guard, catalog
integrity, output-path rules. Nothing here touches the network: network behavior is
verified by running the CLI against real sites, because a mocked fetch cannot tell you
whether a site's bot wall changed.

## Things that will bite you

- **Silence library logging *after* importing the library, never before.** scrapling sets a
  level on its own logger at import time, so silencing at CLI startup is silently
  overwritten. `output.silence_library_logging()` is called at each import site for this reason.
  Without it, scrapling logs an INFO line per request and a bare `ERROR: No Cloudflare
  challenge found.` on every stealth fetch of a non-Cloudflare site — which breaks the
  one-line stderr contract and reads as a failure when nothing failed.
- **Unit mismatch across the libraries.** scrapling's HTTP fetcher takes *seconds*, its browser
  fetchers take *milliseconds*, and crawl4ai's `page_timeout` is milliseconds. This CLI is
  seconds everywhere; conversion happens at each boundary.
- **`--query` (BM25) can correctly return nothing.** BM25 ranks a chunk by how much it stands
  out within one page, so on a page uniformly about the query no chunk stands out and the
  filter keeps nothing. The collapse guard falls back to the full clean page. This is right,
  not a bug — see `refine.py`'s module docstring.
- **A thin page is not a blocked page.** `access.diagnose()` splits hard signals (bot-wall
  status, Cloudflare interstitial) from soft ones (little text). Only hard signals may be
  terminal; treating "short" as terminal reported `example.com` — 142 chars and blocked by
  nobody — as unreachable.
- **Two browser stacks.** scrapling installs Patchright's Chromium, crawl4ai installs
  Playwright's. They coexist in separate caches; both are downloaded once at setup.

## Upgrading dependencies

Pinned on purpose (D12). When sites start blocking, or a library ships a fix you need:

```bash
./ultra-fetch setup --upgrade && "$HOME/.cache/ultra-fetch/venv/bin/python" -m pytest tests/ -q
```

`--upgrade` re-pins `requirements.txt` to whatever it just proved installable together.
Both libraries are Playwright-family sharing one venv, so record what works rather than
floating the versions.
