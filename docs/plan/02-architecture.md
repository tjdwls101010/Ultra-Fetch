# Architecture

## Directory layout (what the next session creates)

```
.claude/skills/ultra-fetch/
├── SKILL.md                      # the skill (see 03-skill-plan.md)
├── scripts/
│   ├── ultra-fetch               # bash launcher: resolves the venv, execs the CLI (chmod +x)
│   ├── ultra_fetch/              # the Python package-as-code (NOT a distributable package)
│   │   ├── __init__.py
│   │   ├── __main__.py           # `python -m ultra_fetch` entry → cli.main()
│   │   ├── cli.py                # argparse: subcommands, flags, dispatch, exit codes, `catalog`
│   │   ├── access.py             # scrapling fetch + tier escalation (fast → stealth)
│   │   ├── refine.py             # crawl4ai Pruning/BM25 on an HTML string → markdown
│   │   ├── crawl.py              # crawl4ai deep-crawl orchestration + politeness caps
│   │   ├── mapper.py             # crawl4ai AsyncUrlSeeder / DomainMapper
│   │   ├── output.py             # write-to-file + one-line stderr summary + format handling
│   │   ├── setup.py              # provision venv deps + `scrapling install` + `crawl4ai-setup` + doctor
│   │   └── config.py             # defaults, venv/cache paths (platformdirs), constants
│   ├── requirements.txt          # pinned scrapling[fetchers] + crawl4ai (+ platformdirs)
│   └── README.md                 # dev notes: how to set up, upgrade deps, run tests
├── references/                   # only if SKILL.md genuinely branches — see 03-skill-plan.md
└── tests/                        # pytest for the pure logic (arg parsing, format selection, summary)
```

Notes:
- The module split is by **concern**, exactly what the user asked for (maintainable, not one file). `cli.py` stays thin — parsing + dispatch; every real judgment lives in the concern modules.
- `ultra_fetch/` is an importable code package for internal structure only. It is **not** published and needs no `pyproject.toml`/entry-points. Invocation is `python -m ultra_fetch ...` inside the venv, fronted by the `ultra-fetch` launcher.
- Delete the stale empty `.claude/skills/ultra fetch/` (space) directory.

## The dedicated venv + launcher

**Why a dedicated venv (not `uv run --with` each call):** scrapling `[fetchers]` pins exact Playwright/patchright versions and crawl4ai pins its own; a stable pre-resolved venv avoids re-resolution cost and occasional conflict on every invocation, and gives the browser-setup steps a fixed home.

**Location:** outside the repo so it survives skill edits and isn't committed — `${XDG_CACHE_HOME:-$HOME/.cache}/ultra-fetch/venv`. (Define once in `config.py`; the bash launcher hard-codes the same path.)

**Launcher (`scripts/ultra-fetch`, bash):**
1. Resolve `VENV="${XDG_CACHE_HOME:-$HOME/.cache}/ultra-fetch/venv"`.
2. If `$VENV/bin/python` is missing, run the setup path (create venv with `uv venv`, `uv pip install -r requirements.txt`, `python -m ultra_fetch setup --browsers`) — printing the one-line "one-time large download" notice to stderr.
3. `exec "$VENV/bin/python" -m ultra_fetch "$@"` (with `PYTHONPATH` pointed at `scripts/` so `ultra_fetch` imports).

This gives the skill body a clean, stable invocation: `"$SKILL_DIR/scripts/ultra-fetch" fetch <url> ...`. No PATH pollution, no PyPI.

**Idempotent setup subcommand:** `ultra-fetch setup [--browsers] [--upgrade]` — creates/repairs the venv, installs/pins deps, runs `scrapling install` + `crawl4ai-setup`, and can run `crawl4ai-doctor`. `--upgrade` bumps scrapling/crawl4ai (D12's manual path).

## Data flow per command

### `fetch <url>`
```
url ─▶ access.py: scrapling
        ├─ tier 1 (default first): Fetcher.get(url, impersonate=..., stealthy_headers=True)   # fast static
        ├─ escalate if blocked/empty/JS-needed:
        │     StealthyFetcher.fetch(url, network_idle=..., solve_cloudflare=<auto>, timeout>=60000)
        └─▶ raw HTML  (+ final status, which tier resolved it)
        │
        ▼
     refine.py: crawl4ai on the HTML string (NO second network request)
        ├─ no --query:  PruningContentFilter(threshold=0.48).filter_content(html) → clean markdown
        └─ --query:     PruningContentFilter → then BM25ContentFilter(user_query=q).filter_content(...)
                        → fit_markdown ; if near-empty → warn + fall back to pruned/raw
        │
        ▼
     output.py: write markdown to --output ; stderr one-liner
        "fetched <url> via <tier>, <N> chars (<filtered|clean>), saved to <path>"
```

**Refine integration detail:** the reports confirm crawl4ai's `PruningContentFilter` / `BM25ContentFilter` expose `filter_content(html) -> list[str]` and take a raw HTML string directly. The clean two-pass recipe (prune → BM25) runs on one fetch. Markdown generation from the filtered HTML uses `DefaultMarkdownGenerator`; alternatively, feed scrapling's HTML to crawl4ai via the `raw:` URL scheme with a configured `markdown_generator` to get `result.markdown.fit_markdown` directly. Pick whichever the implementer verifies is cleanest against the installed versions — both are documented paths.

### `crawl <url>`
```
url ─▶ crawl.py: crawl4ai AsyncWebCrawler + CrawlerRunConfig(deep_crawl_strategy=...)
        ├─ strategy: BestFirstCrawlingStrategy (docs-recommended) or BFS, include_external=False
        ├─ caps (ALWAYS): max_pages (default e.g. 25), max_depth (default e.g. 2)
        ├─ politeness: check_robots_txt=False by default (D9); --respect-robots flips it;
        │              mean_delay / rate limiting on the dispatcher
        ├─ markdown_generator with PruningContentFilter (or BM25 if --query) per page
        └─▶ per-page clean/fit markdown
        │
        ▼
     output.py: write a DIRECTORY (--output dir):
        <dir>/manifest.json        # [{url, depth, score, chars, file}], stop reason, counts
        <dir>/001-<slug>.md ...    # one markdown file per page
     stderr one-liner: "crawled <N> pages under <url> (depth<=<d>), saved to <dir>/ (see manifest.json)"
```
Escalation-to-scrapling for a blocked page mid-crawl is a **v2** consideration (crawl4ai has its own stealth + a `fallback_fetch_function` hook if ever needed). v1 crawl uses crawl4ai end-to-end.

### `map <domain>`
```
domain ─▶ mapper.py: crawl4ai
        ├─ default: AsyncUrlSeeder(source="sitemap+cc", pattern=..., filter_nonsense_urls=True)
        ├─ --deep:  DomainMapper (8 sources incl. crt.sh subdomains, wayback) for broad discovery
        ├─ --query: SeedingConfig(query=..., scoring_method="bm25", score_threshold=...) → ranked URLs
        └─▶ list of {url, (relevance_score), (head metadata)}
        │
        ▼
     output.py: write JSON (or newline URLs) to --output ; stderr: "mapped <N> urls for <domain>, saved to <path>"
```

## The `catalog` self-description (borrowed from the sibling pattern — do implement)

`ultra-fetch catalog` prints, as JSON, every command with its real flags/types/defaults, the exit-code contract, and the output object each command emits — **generated from the argparse definition**, so it can never drift from the code. SKILL.md points Claude at `catalog` instead of restating flags in prose (which would rot). This is the single most important structural lesson from the `scrape-x` skill: *the CLI describes itself; the skill teaches judgment.*

## Layer routing (harness-creator framework) — why this is ONE skill and nothing else

- **Skill** (the whole deliverable): install/first-run, the command surface, output contract, when-to-use judgment, and the gotchas — all trigger from one situation ("Claude needs to read/crawl/map web content"), so per the split-on-branch rule it's a single SKILL.md. `allowed-tools` pre-approves the launcher + `Read`.
- **No hooks / no permissions rules / no agents.** Nothing here needs deterministic enforcement: fetching is read-only, there's no destructive surface, and the politeness caps live in the CLI itself. (Same conclusion the sibling `x` skill reached — enforcement would be theatre.)
- **CLAUDE.md:** optionally one trigger line (see `03-skill-plan.md`), since the skill listing does not survive `/compact` but CLAUDE.md does. Do **not** enumerate components.
