# Overview

What Ultra Fetch is, why it exists, and what it deliberately does not do. Read this first if you're
deciding whether the project fits what you need.

## 1. The problem

Claude Code's built-in `WebFetch` tool has four structural limits:

1. **Access** — it can't reach many real sites: bot-protected pages, Cloudflare interstitials,
   content that only appears after JavaScript runs.
2. **Crawl** — it reads exactly one URL per call. It has no notion of following links across a
   site.
3. **Save to file** — a fetch's result lives only in the conversation; there's no way to persist it
   to disk for later reference or for a follow-up command to read back.
4. **Context efficiency** — a naive fetch of a real page returns the whole thing, boilerplate
   included. (`WebFetch` itself already slices to a query for sites it *can* reach — Ultra Fetch's
   efficiency win is mainly on the sites it can't, plus the save/crawl/precise-filtering pieces.)

## 2. What Ultra Fetch does about it

It's a Claude Code skill (`/ultra-fetch`) plus a bundled Python CLI, built to be reached for
naturally alongside the built-in `WebSearch` — search finds a URL, Ultra Fetch actually reads it.
Two libraries, split cleanly by role:

- **[`scrapling`](https://github.com/D4Vinci/Scrapling) is the access layer.** "Can I even reach
  this page?" A fast static tier (TLS-impersonated HTTP) escalates automatically to a stealth
  browser (bypasses Cloudflare Turnstile/Interstitial) when the fast tier looks blocked.
- **[`crawl4ai`](https://github.com/unclecode/crawl4ai) is the refine + crawl + map layer.** "Now
  make it useful." Its content filters strip boilerplate into clean markdown, or — with a query —
  cut further to only the relevant passages. It also owns multi-page crawling and URL discovery.

The two compose without a second network request: scrapling fetches the bytes, crawl4ai's filters
accept that raw HTML directly. See [Architecture](Architecture.md) for how the pieces fit together
and [Concepts](Concepts.md) for the vocabulary (access tiers, refinement, the output contract).

## 3. Where it sits among alternatives

Both underlying libraries already ship their own MCP servers (`scrapling mcp`; crawl4ai's Docker
MCP). Ultra Fetch doesn't use either — a skill+CLI loads on demand instead of sitting in the tool
listing every session, unifies both libraries behind one escalation story that two separate MCP
servers can't share, and needs no running Docker container. See
[Design Decisions §1](Design-Decisions.md#1-why-a-custom-cli-not-the-libraries-built-in-mcp-servers)
for the full reasoning.

Ultra Fetch is also the third tool in a small personal lineup, after `scrape-x` and `scrape-fb`
(logged-in, per-platform scrapers). Those are PyPI packages because *their own code* rots — a
platform changes its API and the fix ships as a release. Ultra Fetch's own code is a thin,
stable wrapper; what decays here is its *dependencies*, upgraded independently — so it isn't
published as a package at all. See [Design Decisions §3](Design-Decisions.md#3-why-skill-bundled-code-no-pypi-package).

## 4. Who it's for

Claude, primarily — the skill is written so Claude picks the right command and reads results
correctly without a human in the loop. Secondarily, anyone adapting this as a template for their
own Claude Code skill that needs to reach the open web reliably.

## 5. Capabilities at a glance

| Command | Answers |
|---|---|
| `fetch <url>` | "What does this one page say?" — with automatic access escalation and optional query-focused filtering. |
| `crawl <url>` | "What's on this whole site (bounded)?" — a directory of per-page markdown plus a manifest. |
| `map <domain>` | "What URLs even exist here?" — discovery without fetching content, for picking pages before crawling. |

Every command writes its result to a file and prints one summary line to stderr — see
[Concepts §4](Concepts.md#4-the-output-contract).

## 6. Non-goals (v1)

Deliberately out of scope, not simply unfinished:

- **Login / authenticated fetching.** The four `WebFetch` limits above are all about *public*
  content. Auth is a different axis with heavy fragility (cookies, sessions, bans) that belongs to
  per-site tools — already covered by the sibling `scrape-x`/`scrape-fb` for X and Facebook.
- **LLM-API features** (crawl4ai's own `-q` Q&A, `LLMContentFilter`, `LLMExtractionStrategy`).
  Redundant here: Claude is already the reasoning LLM. Ultra Fetch's job stops at handing back
  clean, relevant text.
- **Screenshots, PDF, or MHTML export.** This tool is about text/markdown.

Full rationale for each: [Design Decisions](Design-Decisions.md).

---
**Next:** [Getting Started](Getting-Started.md) to run it, or [Architecture](Architecture.md) for
how it's built. Back to the [index](README.md).
