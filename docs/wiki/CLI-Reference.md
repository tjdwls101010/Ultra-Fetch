# CLI Reference

The command, flag, and exit-code contract, as implemented. This page is a snapshot for reading
without a terminal open; the CLI documents itself and can never drift from its own code — for the
exact contract of the version you have installed, run:

```bash
ultra-fetch catalog
```

(printed as JSON, generated directly from the argument parser). Treat this page as a readable
mirror of that output, not a replacement for it.

## 1. Global conventions

- Invocation via the launcher: `ultra-fetch <command> [args] [flags]`, where `ultra-fetch` is
  `.claude/skills/ultra-fetch/scripts/ultra-fetch`.
- **Results go to a file** (`--output`); **exactly one summary line** goes to stderr; stdout carries
  nothing substantive. See [Concepts §4](Concepts.md#4-the-output-contract).
- All commands exit `0` on success — see [§7](#7-exit-codes) for every other code.
- Text is UTF-8 throughout; non-English pages (Korean, Japanese, Chinese sites have all been
  exercised) round-trip cleanly.

## 2. `fetch <url>`

One page → clean, optionally query-filtered markdown.

| Flag | Type / default | Meaning |
|---|---|---|
| `--output PATH` | path / predictable temp path | Where to write the result. |
| `--query TEXT` | str / none | Keep only blocks relevant to this query (BM25 `fit_markdown`). Absent → clean pruned markdown. |
| `--fast` | flag | Force the fast static tier; never open a browser. Mutually exclusive with `--stealth`. |
| `--stealth` | flag | Force the stealth browser tier (solves Cloudflare). Mutually exclusive with `--fast`. |
| `--timeout SECONDS` | int / 30 | Request timeout; raised to 60s automatically when solving Cloudflare. |
| `--format {markdown,text,html}` | markdown | Output format. |
| `--no-filter` | flag | Skip content filtering entirely; emit the whole page. |
| `--wait-selector CSS` | str / none | Browser tiers only: wait for this selector before capturing (for late-rendering JS). Warns if the selector never matches rather than failing silently. |

Example summary line: `fetched https://example.com via stealth, 4,213 chars (query-filtered), saved to /tmp/uf-example.md`

## 3. `crawl <url>`

Multi-page traversal within a site → a directory of per-page markdown + `manifest.json`.

| Flag | Type / default | Meaning |
|---|---|---|
| `--output DIR` | dir / temp dir | Directory for the pages and `manifest.json`. |
| `--query TEXT` | str / none | BM25-filter each page and steer traversal toward relevant links. |
| `--max-pages N` | int / **25** | Hard cap on pages fetched. Always enforced. |
| `--max-depth N` | int / **2** | Link depth (hop count) from the start URL. |
| `--include-external` | flag / off | Follow off-domain links. Default stays on the start domain. |
| `--respect-robots` | flag / off | Honor `robots.txt` (default: ignored). |
| `--include GLOB` | repeatable | Only crawl URLs matching this glob. |
| `--exclude GLOB` | repeatable | Skip URLs matching this glob. |
| `--strategy {best-first,bfs,dfs}` | best-first | Traversal order. |
| `--delay SECONDS` | float / 0.5 | Politeness delay between requests. |
| `--timeout SECONDS` | int / 30 | Per-page timeout. |

`manifest.json` holds one entry per page (`url`, `depth`, `score`, `chars`, `file`) plus the
`stop_reason` and page count. Read it before the pages — see
[Concepts §6](Concepts.md#6-the-manifest). `--max-depth` reaching its cap at depth 1 is normal on
most sites (nav/tag-cloud links expose most pages one hop from the start URL); `--max-pages` is
what actually binds. See [Troubleshooting](Troubleshooting.md) before concluding a shallow crawl is
incomplete.

Example summary line: `crawled 18 pages under https://docs.example.com (depth<=2), saved to /tmp/uf-docs/ (see manifest.json)`

## 4. `map <domain>`

Discover URLs on a domain (no page-content fetch) → a list, optionally ranked.

| Flag | Type / default | Meaning |
|---|---|---|
| `--output PATH` | path / temp file | Where to write the URL list. |
| `--query TEXT` | str / none | BM25-rank discovered URLs by relevance to this query, most-relevant first. |
| `--deep` | flag / off | Use the broader multi-source mapper (sitemap, Common Crawl, crt.sh subdomains, wayback, path probing) instead of sitemap+CC seeding. Slower, much wider. |
| `--pattern GLOB` | str / `*` | URL glob filter. |
| `--max-urls N` | int / **500** | Cap on returned URLs. |
| `--format {json,txt}` | json | `json` includes scores/metadata; `txt` is bare URLs. |
| `--live-check` | flag / off | Verify each URL actually resolves before reporting it. Slower, but no dead links. |

Example summary line: `mapped 142 urls for example.com (query-ranked), saved to /tmp/uf-map.json`

## 5. `setup [--browsers] [--upgrade] [--doctor]`

Provision or repair the dedicated virtualenv and browser dependencies. Called automatically by the
launcher on first run; also invocable directly.

| Flag | Meaning |
|---|---|
| `--browsers` | Run `scrapling install` and `crawl4ai-setup` (browser engine installation). |
| `--upgrade` | Bump `scrapling` and `crawl4ai`, then re-pin `requirements.txt` to what just proved installable together. |
| `--doctor` | Diagnose the install: `crawl4ai-doctor` plus a scrapling smoke check. |

See [Development Guide](Development-Guide.md) for when and how to actually run these.

## 6. `catalog`

No flags. Prints the full command/flag/exit-code/output contract as JSON, walked directly from the
`argparse` definition — this is the authoritative version of everything on this page.

## 7. Exit codes

| Code | Meaning | What to do |
|---|---|---|
| 0 | Success. | Read the output file. |
| 1 | Usage or bad arguments. | Fix the invocation. |
| 2 | Setup needed — venv or browsers missing and auto-setup failed. | Run `ultra-fetch setup --browsers`; this is a one-time large browser download. |
| 3 | Access failed — unreachable even after stealth escalation. | Report the site unreachable; don't retry in a loop. Likely a commercial anti-bot beyond Cloudflare, or the site is down. |
| 4 | Content empty, or the URL isn't a page at all (e.g. a PDF/image/binary). | For a real page: retry without `--query`, or with `--no-filter`; try `--wait-selector` if it's JS-gated. For a non-page URL: nothing to retry — report it as a file, not a page. |
| 5 | Crawl or map produced zero results. | Report honestly (empty sitemap, no matching links); not retryable by rote. |
| 7 | Partial result — a cap stopped the run before completion. | The output is real but incomplete; say so, and raise the relevant cap only if the question actually needs more. |

The *meaning* of each code is stable and always in `catalog`; the *reaction* to each is in
[Troubleshooting](Troubleshooting.md), which goes deeper on the judgment calls each one implies.

---
**Next:** [Troubleshooting](Troubleshooting.md) for how to react to a result that looks wrong, or
[Design Decisions](Design-Decisions.md) for why the defaults above are what they are. Back to the
[index](README.md).
