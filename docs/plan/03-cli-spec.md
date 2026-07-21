# CLI Specification

The contract Claude relies on. Keep the surface small and predictable. The authoritative, always-current version of this is `ultra-fetch catalog` (generated from argparse) — this document is the design intent behind it.

## Global conventions

- Invocation (via the launcher): `ultra-fetch <command> [args] [flags]`.
- **Output goes to a file, chosen with `--output`.** Only a one-line human summary goes to **stderr**. stdout carries nothing substantive (keeps it out of Claude's context until Claude chooses to `Read` the file). If `--output` is omitted, write to a predictable temp path under the platform temp dir and print that path in the summary.
- All commands exit `0` on success; see the exit-code table.
- Text everywhere is UTF-8 (Korean sites are in scope — see e2e targets).

## `ultra-fetch fetch <url>`

Single page → clean (optionally query-filtered) markdown, saved to a file.

| Flag | Type / default | Meaning |
|---|---|---|
| `--output PATH` | path / temp file | Where to write the markdown. |
| `--query TEXT` | str / none | Turn on BM25 filtering to only query-relevant blocks (`fit_markdown`). Absent → clean pruned markdown. |
| `--fast` | flag | Force the fast static tier (curl_cffi + TLS impersonation). No browser. |
| `--stealth` | flag | Force the stealth browser tier (StealthyFetcher; solves Cloudflare). |
| `--timeout SECONDS` | int / 30 (static), ≥60 auto-applied when solving Cloudflare | Request timeout. |
| `--format {markdown,text,html}` | markdown | Output format. Default markdown. `html` = cleaned HTML; `text` = plain text. |
| `--no-filter` | flag | Skip content filtering; emit full clean markdown of the page (escape hatch when filtering drops wanted content). |
| `--wait-selector CSS` | str / none | (browser tiers) wait for a selector before capture — for JS/late content. |

Default behavior: auto-escalate access (D8), clean markdown (D7). On BM25 near-empty collapse, warn on stderr and fall back to pruned markdown (do not return near-nothing silently).

Summary line example:
`fetched https://example.com via stealth, 4,213 chars (query-filtered), saved to /tmp/uf-example.md`

## `ultra-fetch crawl <url>`

Multi-page traversal within a site → a directory of per-page markdown + a manifest.

| Flag | Type / default | Meaning |
|---|---|---|
| `--output DIR` | dir / temp dir | Directory to write pages + `manifest.json` into. |
| `--query TEXT` | str / none | BM25-filter each page, and (optionally) prioritize traversal toward query-relevant links. |
| `--max-pages N` | int / **25** | Hard cap. Always enforced (runaway guard). |
| `--max-depth N` | int / **2** | Link depth from the start URL. crawl4ai warns depth>3 explodes. |
| `--include-external` | flag / off | Follow off-domain links. Default single-site. |
| `--respect-robots` | flag / off | Honor robots.txt (default ignores it — D9). |
| `--include PATTERN` / `--exclude PATTERN` | glob, repeatable | URL pattern filters (`*/blog/*`, etc.). |
| `--strategy {best-first,bfs,dfs}` | best-first | Traversal order. best-first is docs-recommended. |
| `--delay SECONDS` | float / small default | Politeness delay between requests. |

Output: `manifest.json` (array of `{url, depth, score, chars, file}` + overall `stop_reason`, page count) and `NNN-<slug>.md` per page.

Summary line example:
`crawled 18 pages under https://docs.example.com (depth<=2), saved to /tmp/uf-docs/ (see manifest.json)`

## `ultra-fetch map <domain>`

Discover URLs on a domain (no page-content fetch) → a list, optionally ranked by query relevance.

| Flag | Type / default | Meaning |
|---|---|---|
| `--output PATH` | path / temp file | JSON (default) or newline-delimited URLs. |
| `--query TEXT` | str / none | BM25-rank the discovered URLs (`scoring_method="bm25"`), sorted most-relevant first. |
| `--deep` | flag / off | Use `DomainMapper` (8 sources incl. subdomains via crt.sh, wayback) instead of sitemap+CC seeding. Much broader. |
| `--pattern GLOB` | str / `*` | URL glob filter (`*/blog/*`). |
| `--max-urls N` | int / reasonable cap | Cap results. |
| `--format {json,txt}` | json | `json` includes scores/metadata; `txt` is bare URLs. |

Summary line example:
`mapped 142 urls for example.com (query-ranked), saved to /tmp/uf-map.json`

## `ultra-fetch setup [--browsers] [--upgrade] [--doctor]`

Provision or repair the dedicated venv and browser dependencies. Called automatically by the launcher on first run; also invocable directly.
- `--browsers` runs `scrapling install` + `crawl4ai-setup`.
- `--upgrade` bumps scrapling/crawl4ai (D12 manual-freshness path) and re-pins.
- `--doctor` runs `crawl4ai-doctor` and a scrapling smoke check.

## `ultra-fetch catalog`

Prints the full command/flag/exit-code/output contract as JSON, generated from argparse. The skill reads this rather than trusting prose. Never let it drift.

## Exit codes (design intent — finalize in `cli.py` and document in `catalog`)

| Code | Meaning | What Claude should do |
|---|---|---|
| 0 | Success | Read the output file. |
| 1 | Usage / bad arguments | Fix the invocation. |
| 2 | Setup needed / venv or browsers missing and auto-setup failed | Run `ultra-fetch setup --browsers`; surface the one-time-download note. |
| 3 | Access failed — page unreachable even after stealth escalation | Report the site as unreachable; do not loop. Consider the site genuinely blocked (commercial anti-bot beyond Cloudflare, or down). |
| 4 | Content empty / filter collapsed with no usable fallback | Retry without `--query` or with `--no-filter`; the page may be JS-gated (try `--wait-selector`). |
| 5 | Crawl/map produced zero results | Report honestly (empty sitemap, no matching links). Not retryable by rote. |
| 7 | Partial result — cap hit before completion (crawl `max_pages`/`max_depth`, or map `max_urls`) | Results are incomplete; say so, raise the cap only if warranted. |

Keep the code meanings stable and self-documented via `catalog`, exactly like the sibling CLIs. The skill body explains *what to do* per code; `catalog` explains *what each code means*.
