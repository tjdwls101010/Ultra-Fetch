# Design Decisions

Every default in this project traces back to an explicit choice made against a concrete
alternative, argued during the original planning interview. Recorded here so a future change can
re-derive the original intent instead of guessing at it — reopening one of these needs a new
argument, not just a preference. The full original log (with more verification detail) lives in
[`docs/plan/01-decisions.md`](../plan/01-decisions.md).

## 1. Why a custom CLI, not the libraries' built-in MCP servers

Both `scrapling` (`scrapling mcp`) and `crawl4ai` (a Docker MCP server) already ship MCP servers
Claude Code could connect to directly. A skill+CLI was chosen instead because: a skill loads **on
demand**, unlike MCP tools which sit in the tool listing every session regardless of use; a CLI
**unifies both libraries** behind one escalation story, which two independent MCP servers can't
coordinate; `crawl4ai`'s MCP needs a **running Docker container**; and **file output** (a core
`WebFetch` gap) is natural for a CLI in a way it isn't for an MCP tool call.

## 2. Why login/auth is out of scope for v1

The four `WebFetch` limits this project fixes are all about *public* content — authentication is a
different axis entirely. Verified against `scrapling`'s own docs: authenticated browser fetching
isn't even reachable through its CLI (no `--cookies`/`--user-data-dir`/`--cdp-url` on the fetch
commands). The realistic mechanisms (a persistent `user_data_dir`, attaching to a real Chrome via
CDP) carry heavy fragility — profile locking, session expiry, account bans — and belong to per-site
tools, not a general fetcher. Logged-in X/Facebook access is already the sibling `scrape-x`/
`scrape-fb` tools' job. This is deferred, not architecturally blocked — nothing here forecloses a
future CDP-attach path, it just isn't built.

## 3. Why skill-bundled code, no PyPI package

The sibling tools (`scrape-x`, `scrape-fb`) are published packages because *their own code* rots —
a platform rotates its API and the fix ships as a new release, which justifies a package plus a
task-start version check. Ultra Fetch's own code is a thin, stable orchestration wrapper; what
decays here is its **dependencies** (`scrapling`/`crawl4ai` stealth capability, as sites evolve
their defenses), which are upgraded independently of any release of this project's own code. The
strongest argument for a package doesn't transfer, so there isn't one — just a skill directory with
well-separated modules under `scripts/`, run through a dedicated virtualenv provisioned once.

## 4. Why both libraries, role-split

`scrapling` is stealth-first (its docs are explicit and repeated about bypassing Cloudflare) but has
**no markdown converter** in its Python API — only HTML, text, or JSON. `crawl4ai` is refine-first
(its whole `fit_markdown` machinery exists to cut tokens) and owns deep crawling plus URL discovery,
but its own stealth is only "moderate" by its own docs' description. Each covers exactly the other's
gap, and their strengths barely overlap — worth the cost of both being Playwright-family libraries
sharing one virtualenv (two separate browser-engine downloads at setup, accepted as a one-time
cost).

## 5. Why `fetch` + `crawl` + `map`

`fetch` and `crawl` directly answer the two hardest `WebFetch` limits (access, crawl). `map` was
added because "map a big site first, then fetch the right pages" is a distinct and useful move that
pairs naturally with a `WebSearch` → narrow-down workflow, and `crawl4ai` already exposes the
building blocks (`AsyncUrlSeeder`, `DomainMapper`) needed to do it without fetching page content.

## 6. Why file + stderr output

Every command writes its result to a `--output` path and prints only a one-line summary to stderr,
nothing substantive to stdout. This directly fixes the `WebFetch` "can't save" gap, and — just as
important — hands **context control to the caller**: Claude decides how much of the saved file to
read, rather than a full page arriving in the conversation whether wanted or not. This mirrors the
same file+stderr pattern already proven in the sibling `scrape-x`/`scrape-fb` tools.

## 7. Why clean markdown by default, BM25 on query

`crawl4ai`'s own docs are explicit that context-efficiency is **not** the library's default —
`DefaultMarkdownGenerator()` with no filter emits the whole page. A wrapper has to make the filtered
path the default rather than an opt-in, so `fetch` always prunes; passing `--query` layers a second
BM25 pass on top (prune, then BM25, on the same fetched HTML — no re-fetch). If the BM25 pass
collapses to near-nothing (threshold too strict, or a lexical mismatch with the page's own wording),
the CLI warns and falls back to the pruned result rather than returning almost nothing silently.

## 8. Why fetch auto-escalates access

Trying the fast static tier first and escalating to the stealth browser only when the response
looks blocked was chosen over always asking the caller to pick a tier: it "just works" for the
common case with no judgment call required, while `--fast`/`--stealth` still let Claude force a tier
when it already knows better. The stealth path needs a timeout of at least 60 seconds specifically
when solving a Cloudflare challenge — a shorter timeout there doesn't fail fast, it fails *wrongly*,
aborting a solve that was about to succeed.

## 9. Why crawl is permissive by default, but capped

`crawl` ignores `robots.txt` by default, matching `crawl4ai`'s own `check_robots_txt=False` — this
is a personal research tool, and politeness is judged per-task rather than forced (`--respect-robots`
opts in). **Runaway prevention is non-negotiable regardless of politeness posture**: default
`max_pages`/`max_depth` caps always apply, because `crawl4ai`'s own docs warn that depth beyond 3
grows exponentially and urge a hard page cap independent of any politeness stance.

## 10. Why no LLM-API features in v1

`crawl4ai` ships its own LLM-backed features (`-q` Q&A, `LLMContentFilter`, `LLMExtractionStrategy`),
all excluded here. This is an architectural call, not just cost-avoidance: Claude is already the
reasoning LLM in this loop. The CLI's job stops at handing back clean, relevant text — running
another LLM inside the CLI to do the same kind of reasoning would be redundant, and would add an
API-key/cost/config burden that offline BM25 and Pruning don't need.

## 11. Why first-run setup is automatic

Both libraries download hundreds of MB of browser engines on first use. Rather than asking the
human to run a separate setup step, the launcher provisions the virtualenv and both browser stacks
idempotently on first invocation, printing a one-line "one-time large download" notice so the pause
is diagnosable rather than read as a hang.

## 12. Why dependencies are pinned, not auto-upgraded

`requirements.txt` pins exact `scrapling`/`crawl4ai` versions; there is deliberately **no**
task-start version check (unlike the sibling tools, whose rationale for that pattern doesn't
transfer here — see [§3](#3-why-skill-bundled-code-no-pypi-package)). Predictability was chosen over
auto-upgrade churn: when a site starts blocking requests or a library ships a needed fix, `ultra-fetch
setup --upgrade` is the explicit, manual remedy, and it re-pins `requirements.txt` to whatever
version combination it just proved installable together.

## 13. Why generated artifacts are in English

`SKILL.md`, code, comments, and this documentation are all English, independent of the language any
given conversation happens in — matching the sibling skills and the surrounding CLI ecosystem, and
the most stable substrate for Claude's own skill-triggering and technical vocabulary.

## Corrections to the original mental model

A few assumptions going in didn't survive contact with the libraries' actual docs, worth recording
so they don't get re-assumed:

- **"`scrapling` accesses almost every website"** — overstated but defensible at its core. It
  reliably bypasses Cloudflare Turnstile/Interstitial; other commercial anti-bot vendors
  (DataDome, Akamai, PerimeterX, Kasada) are undocumented for it and should be assumed unsolved.
- **"`scrapling` can reuse my browser's login via its cache"** — inaccurate. `real_chrome=True`
  uses the Chrome *binary* for fingerprint authenticity, not your profile or cookies; there's no
  read-your-browser-cache feature. Moot in v1 anyway, since auth is out of scope (§2).
- **"`crawl4ai` gives clean output without asking"** — filters must be explicitly enabled; the
  library's own default emits the full unfiltered page. This is exactly why §7 makes filtering the
  wrapper's default rather than trusting the library's.

---
**Next:** [Architecture](Architecture.md) to see these decisions reflected in the actual data flow,
or [Validation History](Validation-History.md) for how the resulting defaults held up against real
sites. Back to the [index](README.md).
