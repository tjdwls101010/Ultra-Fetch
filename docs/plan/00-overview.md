# Ultra Fetch — Plan Overview

> This directory (`docs/plan/`) is the implementation brief for a **future Claude session**.
> Planning and implementation are deliberately split across sessions. This session produced the plan only.
> Read every file here before writing a line of code. Read them in order (00 → 05), then `.claude/harness-spec.md`.

## What Ultra Fetch is

A Claude Code **skill** (`/ultra-fetch`) plus a bundled CLI that overcomes the structural limits of the built-in `WebFetch` tool. It is meant to be reached for naturally alongside the built-in `WebSearch` — WebSearch finds URLs, Ultra Fetch reads them properly.

### The four WebFetch limits this exists to fix

1. **Access** — WebFetch can't reach many sites (bot protection, JS-rendered content, Cloudflare).
2. **Crawl** — WebFetch reads one URL; it can't traverse a site.
3. **Save to file** — WebFetch results can't be persisted to disk.
4. **Context efficiency** — a naive full-HTML fetch floods context with boilerplate. (Note: WebFetch itself *does* already slice to the query for the sites it can reach — see the trigger discussion in `03-skill-plan.md`. Ultra Fetch's efficiency win is in the sites WebFetch *can't* reach, plus save/crawl/precise-filtering.)

## The one-paragraph architecture

Two popular libraries, split by role so they don't overlap:

- **scrapling = the access layer.** "Can I even reach this page?" Best-in-class stealth (StealthyFetcher bypasses Cloudflare Turnstile/Interstitial), TLS-impersonating fast static fetches. This is the core value: reaching what WebFetch can't.
- **crawl4ai = the refine + crawl + map layer.** "Now make it useful." Its `PruningContentFilter` (clean, no query) and `BM25ContentFilter` (cut to only the query-relevant blocks → `fit_markdown`) are the context-efficiency engine. It also owns multi-page crawling and URL discovery.

The two compose cleanly because **crawl4ai's filters accept a raw HTML string** (`filter_content(html)`) — so scrapling fetches the bytes, crawl4ai refines them, with no second network request.

## Locked scope for v1

**In scope:** public web content; `fetch` (single page), `crawl` (within a site), `map` (URL discovery); clean markdown output with optional query-focused filtering; save-to-file.

**Out of scope for v1 (deliberately):**
- **Login / authenticated fetching.** Orthogonal to the WebFetch limits, which are all about public content. The heavy fragility (cookie handling, sessions, bans) isn't worth it, and logged-in X/Facebook are already covered by the sibling `scrape-x` / `scrape-fb` tools. Do **not** architect against a future CDP-attach path, but do not build it now. (See decision D2 in `01-decisions.md`.)
- **LLM-API features** (crawl4ai's `-q` Q&A, `LLMContentFilter`, `LLMExtractionStrategy`). Redundant here — the CLI's job is to hand Claude clean, relevant text; Claude *is* the LLM that does the semantic reasoning. Offline BM25 + Pruning only. No API keys. (D9.)
- **Screenshots / PDF / MHTML.** crawl4ai can do them, but this tool is about text/markdown. (D-scope.)

## Distribution shape (important, and different from the siblings)

**Not a PyPI package.** The sibling projects (`scraper-for-x`, `scraper-for-facebook`) are published packages because *their own code rots* — X rotates GraphQL query-ids and the fix ships as a new release, justifying PyPI + a version check. **Ultra Fetch's own code is a thin, stable orchestration wrapper.** What decays here is the *dependencies* (scrapling/crawl4ai stealth vs. evolving sites), which are upgraded independently of any Ultra Fetch release. So the strongest argument for PyPI evaporates.

Instead: **a skill with a `scripts/` folder holding well-refactored, multi-file Python code**, run through a dedicated virtualenv provisioned once. See `01-decisions.md` (D3) and `02-architecture.md`.

## The full decision set (one-liners; rationale in `01-decisions.md`)

| # | Decision |
|---|---|
| Skill name | `ultra-fetch` → invoked `/ultra-fetch`. Replaces the stale empty `.claude/skills/ultra fetch/` (space) directory. |
| Form | Custom local CLI, **not** the libraries' built-in MCP servers. |
| Libraries | Both, role-split: scrapling = access, crawl4ai = refine/crawl/map. |
| Distribution | Skill-bundled multi-file code under `scripts/`; dedicated venv; **no PyPI, no distributable package**. |
| Commands | `fetch`, `crawl`, `map`. |
| Output | Write result to a `--output` file + a one-line stderr summary; Claude then `Read`s the file. |
| Default format | Clean markdown (Pruning); `--query` switches to BM25 `fit_markdown`. |
| Access | `fetch` auto-escalates fast-static → stealth-browser; `--fast` / `--stealth` override. |
| Crawl politeness | Permissive: robots.txt ignored by default, only page/depth caps; `--ignore-robots` / `--max-pages` override. |
| First run | Skill auto-provisions the venv + browsers, with a one-line "one-time large download" notice. |
| Freshness | Deps pinned in requirements; manual upgrade when needed. |
| LLM features | Excluded from v1 (offline BM25/Pruning only). |
| Language | All generated artifacts (SKILL.md, code, docs) in **English**. Interview happened in Korean. |

## What the next session must deliver

1. The refactored CLI code under `.claude/skills/ultra-fetch/scripts/` (see `02-architecture.md` for the module breakdown, `02-cli-spec.md`... i.e. `03-cli-spec.md` for the exact CLI contract).
2. `SKILL.md` (see `03-skill-plan.md`).
3. A working dedicated-venv provisioning path (setup step + launcher).
4. `.claude/harness-spec.md` status flips from `approved` → `generated` → `validated`.
5. Broad e2e validation (see `05-validation-and-release.md`), then GitHub commit / PR / merge / release.

Run `validate_harness.py` until 0 errors before calling anything done.
