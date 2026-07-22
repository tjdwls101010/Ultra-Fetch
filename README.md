<div align="center">

<img src="https://raw.githubusercontent.com/tjdwls101010/tjdwls101010/refs/heads/main/Images/ultra%20fetch.png" alt="Ultra Fetch logo" width="180" />

# Ultra Fetch

**A Claude Code skill and CLI that reads, crawls, and maps web pages the built-in WebFetch can't reach.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[Overview](#1-overview) · [Features](#2-features) · [Quick Start](#3-quick-start) · [Usage](#4-usage) · [Documentation](#5-documentation)

</div>

## 1. Overview

Claude Code's built-in `WebFetch` has four structural limits: it can't reach many real sites (bot
protection, Cloudflare interstitials, JS-rendered content), it can't traverse a site across
multiple pages, it can't save what it finds to disk, and a naive fetch floods the conversation with
unfiltered page content. Ultra Fetch is a skill-bundled Python CLI that fixes all four — a stealth
browser (via [`scrapling`](https://github.com/D4Vinci/Scrapling)) that reaches what `WebFetch`
can't, clean and optionally query-filtered markdown (via
[`crawl4ai`](https://github.com/unclecode/crawl4ai)'s Pruning/BM25 filters) instead of raw HTML, and
`fetch` / `crawl` / `map` commands that always write to a file rather than the context window. It's
built to be reached for automatically alongside the built-in `WebSearch` — search finds a URL,
Ultra Fetch actually reads it.

## 2. Features

- **Access that escalates on its own.** `fetch` tries a fast static request first and only opens a
  stealth browser (Cloudflare-solving included) when the fast tier looks blocked — no judgment call
  needed up front, with `--fast`/`--stealth` to force a tier. See
  [Concepts](docs/wiki/Concepts.md#1-access-tiers).
- **Clean by default, precise on request.** Every fetch is pruned to clean markdown; add `--query`
  to cut it further to only the passages relevant to a specific question (BM25), with a collapse
  guard that falls back rather than returning near-nothing. See
  [Concepts](docs/wiki/Concepts.md#2-content-refinement).
- **`crawl`** — bounded multi-page traversal within one site, writing one markdown file per page
  plus a `manifest.json` describing what was visited and why the run stopped.
- **`map`** — discovers a domain's URLs (sitemap + Common Crawl, or a broader `--deep` multi-source
  scan) without fetching page content, so you can pick the right pages before crawling.
- **A file, not a flood.** Every command writes its result to `--output` and prints exactly one
  summary line to stderr — nothing substantive lands on stdout, so the caller decides how much
  enters context.
- **Self-describing.** `ultra-fetch catalog` prints the CLI's exact commands, flags, defaults, and
  exit codes as JSON, generated from the code itself — it can't drift from a prose doc the way a
  hand-maintained flag list would.

## 3. Quick Start

**Prerequisites:** macOS or Linux, `bash`, and Python 3.12 available on the system (used once to
bootstrap a dedicated virtualenv). [`uv`](https://github.com/astral-sh/uv) speeds up that first-run
provisioning if it's installed, but isn't required.

**Add it to a project:**

```bash
cp -r .claude/skills/ultra-fetch /path/to/your-project/.claude/skills/
```

Claude Code picks up a skill directory automatically — there's no build step and nothing to
publish or install from a package index.

**Run it** (directly from a terminal, to see it work standalone; inside a Claude Code session you
don't call the CLI yourself — see below):

```bash
.claude/skills/ultra-fetch/scripts/ultra-fetch fetch https://example.com --output /tmp/example.md
cat /tmp/example.md
```

The first invocation provisions a dedicated virtualenv and downloads both browser engines (a few
hundred MB, once); it prints a notice and proceeds — don't mistake the pause for a hang. Every call
after that is immediate.

**Inside Claude Code**, you don't run any of this by hand: ask Claude to read, crawl, or map a page,
and the `/ultra-fetch` skill fires on its own whenever `WebFetch` would fall short.

## 4. Usage

```bash
# One page, cut down to only what answers a specific question
ultra-fetch fetch https://docs.example.com/config --query "default timeout value" --output /tmp/config.md

# Multiple pages under one site, bounded by page and depth caps
ultra-fetch crawl https://docs.example.com --max-pages 15 --max-depth 2 --output /tmp/docs-crawl/

# What URLs exist on a domain, before deciding what to fetch
ultra-fetch map example.com --output /tmp/urls.json
```

(`ultra-fetch` above is the launcher at `.claude/skills/ultra-fetch/scripts/ultra-fetch`.) For the
full flag list, defaults, and exit-code contract, see the
[CLI Reference](docs/wiki/CLI-Reference.md) — or run `ultra-fetch catalog` for the version you
actually have installed.

## 5. Documentation

The full docs live in [`docs/wiki`](docs/wiki/README.md): architecture, the CLI reference, the
design decisions behind what's in and out of scope, and a troubleshooting guide for reading results
correctly.

## 6. Project status

Actively used and extensively validated: every documented CLI code path — all three access tiers,
crawling at scale, `map` both plain and `--deep`, every exit code, and first-run provisioning — has
been run against real sites across 15+ rounds of end-to-end testing. See
[Validation History](docs/wiki/Validation-History.md) for what was tested and what it found. There
is no tagged release yet; `main` is the stable line.

## 7. Contributing

Contributions and bug reports are welcome — see [`CONTRIBUTING.md`](CONTRIBUTING.md) for the
(lightweight) process.

## 8. License

MIT — see [`LICENSE`](LICENSE).
