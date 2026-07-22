# Architecture

How Ultra Fetch is built: the major pieces, how a command flows through them, and what lives
where in the code. For anyone modifying the CLI or just wanting to trust what it does.

## 1. The two-layer design

Two libraries, deliberately non-overlapping in responsibility:

```mermaid
flowchart LR
    Claude["Claude Code<br/>(WebSearch → Ultra Fetch)"] -->|"fetch / crawl / map"| Launcher["ultra-fetch launcher<br/>(bash)"]
    Launcher --> CLI["cli.py<br/>argparse, dispatch, catalog"]

    CLI --> FetchCmd["fetch.py"]
    CLI --> CrawlCmd["crawl.py"]
    CLI --> MapCmd["mapper.py"]

    FetchCmd --> Access["access.py<br/>scrapling: fast → stealth"]
    Access --> Refine["refine.py<br/>crawl4ai: Pruning / BM25"]
    Refine --> Output["output.py<br/>file + stderr summary"]

    CrawlCmd --> Crawl4aiCrawl["crawl4ai deep-crawl<br/>+ Pruning/BM25 per page"]
    Crawl4aiCrawl --> Output

    MapCmd --> Crawl4aiMap["crawl4ai AsyncUrlSeeder /<br/>DomainMapper"]
    Crawl4aiMap --> Output

    Output -->|"file on disk"| Claude
```

- **`scrapling` is the access layer** — "can I even reach this page?" Fast static requests that
  escalate to a stealth browser only when needed.
- **`crawl4ai` is the refine + crawl + map layer** — "now make it useful." Its content filters turn
  raw HTML into clean or query-focused markdown; it also owns multi-page traversal and URL
  discovery.

The two compose without a second network request: `crawl4ai`'s filters accept a raw HTML string
directly (`filter_content(html)`), so `access.py` fetches once and hands the bytes straight to
`refine.py`.

## 2. Data flow — `fetch`

```mermaid
sequenceDiagram
    participant Claude
    participant Fetch as fetch.py
    participant Access as access.py (scrapling)
    participant Refine as refine.py (crawl4ai)
    participant Output as output.py

    Claude->>Fetch: fetch a URL --output path (optional --query)
    Fetch->>Access: fetch_html(url)
    Access->>Access: fast tier (Fetcher: curl_cffi, TLS-impersonated)
    alt blocked / thin / JS shell
        Access->>Access: escalate to stealth tier (StealthyFetcher, solve_cloudflare)
    end
    Access-->>Fetch: raw HTML + which tier resolved it
    Fetch->>Refine: to_markdown(html, query?)
    Refine->>Refine: PruningContentFilter (+ BM25ContentFilter if query)
    Refine-->>Fetch: clean or fit markdown (+ collapse-guard fallback if near-empty)
    Fetch->>Output: write file, print one-line stderr summary
    Output-->>Claude: one-line stderr summary (tier used, char count, clean or query-filtered, output path)
```

## 3. Data flow — `crawl`

```mermaid
flowchart TD
    Start["crawl a URL<br/>--max-pages --max-depth"] --> Strategy["deep-crawl strategy<br/>(best-first / bfs / dfs)"]
    Strategy --> Fetch1["fetch + refine each page<br/>(crawl4ai end-to-end)"]
    Fetch1 --> Cap{"page/depth cap<br/>reached first?"}
    Cap -->|no, sitemap exhausted| Done["write manifest.json<br/>+ NNN-slug.md per page"]
    Cap -->|yes| Partial["same output,<br/>exit code 7 (partial)"]
```

Caps are non-negotiable (`--max-pages` defaults to 25, `--max-depth` to 2) — crawl4ai's own
strategies default to unbounded, and depth grows exponentially, so an uncapped default would be a
runaway-fetch risk rather than a convenience. `robots.txt` is ignored by default (`--respect-robots`
opts in); see [Design Decisions §9](Design-Decisions.md#9-why-crawl-is-permissive-by-default-but-capped).

## 4. Data flow — `map`

```mermaid
flowchart TD
    Start["map a domain"] --> Mode{"--deep?"}
    Mode -->|no, default| Seeder["AsyncUrlSeeder<br/>sitemap + Common Crawl"]
    Mode -->|yes| Mapper["DomainMapper<br/>8 sources incl. crt.sh, wayback"]
    Seeder --> Query{"--query?"}
    Mapper --> Query
    Query -->|yes| Rank["BM25-rank URLs by relevance"]
    Query -->|no| List["URL list as discovered"]
    Rank --> Output["write JSON or newline URLs"]
    List --> Output
```

`map` never fetches a page's content — only what URLs exist, optionally ranked. See
[Concepts §3](Concepts.md#3-crawl-vs-map) for when to reach for this instead of `crawl`.

## 5. Module map

```
.claude/skills/ultra-fetch/
├── SKILL.md                  # the skill Claude reads — judgment, not a flag list
├── scripts/
│   ├── ultra-fetch            # bash launcher: resolves the venv, provisions on first run, execs the CLI
│   ├── requirements.txt       # pinned scrapling[fetchers] + crawl4ai
│   └── ultra_fetch/
│       ├── cli.py             # argparse: subcommands, flags, dispatch, exit codes, `catalog`
│       ├── access.py          # scrapling fetch + tier escalation (fast → stealth)
│       ├── refine.py          # crawl4ai Pruning/BM25 on an HTML string → markdown
│       ├── fetch.py           # the `fetch` command: sequences access → refine → output
│       ├── crawl.py           # the `crawl` command: crawl4ai deep-crawl + manifest
│       ├── mapper.py          # the `map` command: AsyncUrlSeeder / DomainMapper
│       ├── output.py          # file writing, the stderr contract, library log silencing
│       ├── setup.py           # venv provisioning, browser install, upgrade, doctor
│       ├── config.py          # every default and threshold, each with its measured rationale
│       └── errors.py          # exception → exit-code contract
└── tests/                     # pytest for pure logic only — nothing network-touching
```

`cli.py` stays thin by design — argument parsing and dispatch only. Every real judgment (when to
escalate, what to filter, how to cap a crawl) lives in its own concern module, which is what makes
the CLI maintainable as a set of small files rather than one growing script. See the
[Development Guide](Development-Guide.md) for how the dedicated virtualenv and launcher work
together, and to make a change here yourself.

## 6. Design rationale

Every default above — the escalation order, the two-pass Pruning-then-BM25 recipe, the crawl caps,
the file+stderr output shape — was an explicit decision made against a concrete alternative, not
just "the obvious way to do it." The full log, with the reasoning for each: [Design
Decisions](Design-Decisions.md).

---
**Next:** [Concepts](Concepts.md) for the vocabulary used above, or [CLI
Reference](CLI-Reference.md) for the exact flags each command takes. Back to the
[index](README.md).
