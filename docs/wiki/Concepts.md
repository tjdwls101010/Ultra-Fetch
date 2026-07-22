# Concepts

The vocabulary the rest of the docs assume. Defined in the order you'll actually need them.

## 1. Access tiers

`fetch` doesn't use one fixed method to retrieve a page — it escalates:

1. **Fast tier** (default first) — a static HTTP request with TLS fingerprint impersonation
   (`scrapling`'s `Fetcher`, built on `curl_cffi`). No browser, seconds not tens-of-seconds.
2. **Stealth tier** (escalation target) — a real, fingerprint-hardened browser (`StealthyFetcher`,
   built on Patchright) that renders JavaScript and can solve a Cloudflare Turnstile/Interstitial
   challenge. Slower, but reaches what the fast tier can't.

Escalation is automatic: the fast tier's response is checked against hard signals (a bot-wall
status code, a challenge-page marker in the text) and soft signals (suspiciously little text), and
only the hard signals force escalation on their own — a short-but-genuine page like `example.com`
must not be mistaken for a block. `--fast` and `--stealth` force a tier when you already know which
one you want. See [Design Decisions §8](Design-Decisions.md#8-why-fetch-auto-escalates-access) for
why this is automatic rather than a flag you set every time, and
[Troubleshooting](Troubleshooting.md) for what to do when even the stealth tier fails.

## 2. Content refinement

Once HTML is in hand, `crawl4ai` turns it into markdown in one of two ways:

- **Pruning** (the default, no query needed) — heuristic junk removal by text/link density: drops
  navigation, footers, and sidebars while keeping article-shaped prose. This is what makes plain
  markdown clean without you asking for anything.
- **BM25 / `fit_markdown`** (when you pass `--query`) — a second pass that keeps only the chunks
  lexically relevant to your query, cutting a long mixed page down to the part that answers your
  question.

BM25 is **lexical, not semantic** — it ranks a chunk by how much it stands out *within that one
page*. Two consequences that look like bugs and aren't: a page uniformly on-topic has nothing that
"stands out," so filtering can correctly keep nothing (a collapse guard then falls back to the
clean, unfiltered page); and a page that never discusses your query still returns its least-bad
passages rather than an explicit "not found." Both cases produce a stderr warning — read it. See
[Troubleshooting](Troubleshooting.md) for the re-run playbook.

## 3. Crawl vs. map

Easy to conflate, answering different questions:

- **`crawl`** fetches and refines multiple pages under one site, bounded by page/depth caps, and
  writes each page's content to disk.
- **`map`** discovers what URLs *exist* on a domain — via sitemap/Common Crawl seeding, or a
  broader `--deep` multi-source scan — **without fetching any page's content**. It's the move when
  a site is large and you need to pick the handful of pages that matter before spending a crawl's
  budget on them.

A common pattern: `map` a domain, look at the URLs, then `fetch` the two or three that actually
answer the question — often cheaper and more precise than crawling and discarding most of it.

## 4. The output contract

Every command writes its actual result to a **file** (`--output`) and prints **exactly one summary
line to stderr**. Nothing substantive goes to stdout — it is never parsed, only the file is read.
This is deliberate: it hands the caller control over how much content enters its own context,
rather than dumping a whole page (or a whole crawl) into the conversation by default.

## 5. Exit codes as verdicts

Exit codes aren't generic pass/fail — each one tells the caller what kind of failure it is and
whether retrying makes sense:

- Most non-zero codes here are **informative, not transient** — a blocked site stays blocked in the
  next second, an empty filter result stays empty. The reaction is to change something specific
  (drop `--query`, add `--no-filter`, accept the site is unreachable), not to retry the same call.
- **Exit 7 is a distinct case: partial success.** A page/depth/URL cap stopped the run early; the
  output is real, just incomplete.

Full table: [CLI Reference §7](CLI-Reference.md#7-exit-codes). What to actually do about each one:
[Troubleshooting](Troubleshooting.md).

## 6. The manifest

`crawl`'s output directory always includes `manifest.json` alongside the per-page markdown files —
one entry per page (URL, depth, relevance score if `--query` was used, character count, filename),
plus the overall stop reason and page count. Read it *before* the pages themselves: it tells you
where the page budget actually went, and whether a shallow or capped result is a complete picture
of the site or one that stopped on boilerplate.

---
**Next:** [CLI Reference](CLI-Reference.md) for the exact commands and flags, or
[Troubleshooting](Troubleshooting.md) for how to react when a result looks wrong. Back to the
[index](README.md).
