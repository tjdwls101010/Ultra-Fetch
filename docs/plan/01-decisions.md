# Decision Log

Every decision below was agreed with the user during the planning interview (Korean), most via explicit AskUserQuestion choices. Each records the choice **and the reasoning**, so the implementer can re-derive the intent when a case comes up that the plan didn't enumerate. Where the user overrode an initial recommendation, that's noted — those are the load-bearing ones.

---

### D1 — Custom CLI, not the built-in MCP servers
**Choice:** Build a local CLI wrapped by the skill.
**Context:** Both scrapling (`scrapling mcp`) and crawl4ai (Docker MCP at `:11235/mcp/sse`) already ship MCP servers Claude Code can connect to. This was surfaced honestly to the user as a real fork.
**Why CLI wins here:** (1) A skill+CLI loads **on demand** — it costs no always-on context budget, unlike MCP tools which sit in the tool listing every session. (2) A CLI **unifies both libraries** behind one escalation story; two separate MCP servers can't cooperate. (3) crawl4ai's MCP needs a **running Docker container**. (4) Native **file-output** (a core WebFetch gap) is natural for a CLI. (5) Matches the maintainer's existing `scrape-x`/`scrape-fb` ecosystem.

### D2 — v1 excludes login / authenticated fetching (CDP-attach deferred, not blocked)
**Choice:** Public content only in v1. Do not build auth. Do **not** architect in a way that forecloses a future CDP-attach path.
**Why:** The four WebFetch limits are all about *public* content — login is a different axis. Verified from the scrapling docs: authenticated browser fetching isn't even reachable through scrapling's `extract` CLI (no `--cookies`/`--user-data-dir`/`--cdp-url` on the browser commands). The realistic auth mechanisms (persistent `user_data_dir`, CDP attach) carry heavy fragility (profile locking, session expiry, bans) and belong to per-site tools. Logged-in X/Facebook are already the sibling tools' job. The user raised this doubt themselves and agreed to cut it.
**User's original belief, corrected:** "scrapling can use my browser cache to access logged-in sites" is inaccurate — there is no read-your-Chrome-cache feature. `real_chrome=True` uses the Chrome *binary* (fingerprint authenticity), not your profile/cookies. Moot for v1 anyway.

### D3 — Skill-bundled multi-file code under `scripts/`, no PyPI, no distributable package
**Choice:** Code lives in `.claude/skills/ultra-fetch/scripts/` as **several well-refactored modules** (not one monolith), run via a dedicated venv. No PyPI publish, no `pip install`-able package.
**Why (user-led):** The user questioned whether PyPI is needed at all, correctly. Reasoning: the PyPI + task-start-version-check pattern from `scrape-x` was justified because *scrape-x's own code rots*. Ultra Fetch's own code is a thin stable wrapper; what rots is its **dependencies**, upgraded independently. So PyPI's core benefit doesn't transfer. The user explicitly asked for multi-file, refactored code for maintainability ("굳이 코드를 꼭 하나로 만들어야 하는건 아니고, 리팩토링도 잘 해주면 좋겠어"). A `requirements.txt` (or minimal uv project purely for dependency management) is fine — that is *not* the same as a distributable package.

### D4 — Libraries: both, role-split
**Choice:** scrapling = access/stealth; crawl4ai = refine (Pruning/BM25) + crawl + map.
**Why:** Verified from both docs that the strengths are complementary and barely overlap. scrapling is stealth-first (bypasses Cloudflare; the docs are explicit and repeated). crawl4ai is refine-first (its whole `fit_markdown` machinery exists to cut tokens) and owns deep crawling + URL discovery. crawl4ai's own stealth is only "moderate" (its docs' own word; undetected mode isn't even a config flag and wants `headless=False`). scrapling's parser has no markdown/clean-content converter from Python. So each covers exactly the other's gap.
**Coexistence:** Both are Playwright-family and both must live in one venv. Signal they're meant to coexist: crawl4ai widened its `lxml` ceiling to `<7` in v0.9.1 specifically for "co-install with scrapling etc." Still a **de-risk item** — see `04-library-facts.md`.

### D5 — Command surface: `fetch` + `crawl` + `map`
**Choice:** Three subcommands.
**Why:** `fetch` and `crawl` directly answer the two hardest WebFetch limits (access, crawl). The user chose to include `map` (URL discovery / site mapping via crawl4ai's `AsyncUrlSeeder`/`DomainMapper`) — useful for "map a big site first, then fetch the right pages," which pairs with the WebSearch workflow.

### D6 — Output model: file + stderr summary; Claude reads the file
**Choice:** Every command writes its result to a `--output` path and prints only a one-line summary to stderr. Nothing substantive on stdout.
**Why:** Directly fixes the WebFetch "can't save" gap, and it hands **context control to Claude** — Claude decides how much of the saved file to `Read`, which is the anti-pollution goal. This mirrors the proven sibling pattern (`scrape-x`/`scrape-fb` write JSON files + a stderr summary line).

### D7 — Default format clean markdown; `--query` → BM25 fit
**Choice:** No `--query` → `PruningContentFilter` clean markdown. With `--query` → `BM25ContentFilter` → `fit_markdown` (only query-relevant blocks). Recommended internal refinement: **prune first, then BM25** (two-pass on the same HTML, no re-fetch).
**Why:** crawl4ai's docs are explicit that context-efficiency is *not* the default — `DefaultMarkdownGenerator()` with no filter emits the whole page. A wrapper must make the filtered path the default. WebSearch always carries a query, so `--query` integration is natural.
**Gotcha to implement:** if `fit_markdown` collapses to near-empty (BM25 threshold too high or lexical mismatch), the CLI must **warn and fall back** to clean/raw markdown rather than returning almost nothing silently.

### D8 — `fetch` auto-escalates access tier
**Choice:** Try fast static (scrapling `Fetcher`, curl_cffi + TLS impersonation) first; auto-escalate to the stealth browser (`StealthyFetcher`, `solve_cloudflare` when needed) on block/empty/JS-required. `--fast` and `--stealth` force a tier.
**Why (user picked over alternatives):** "Just works" for Claude — no judgment call about which tier to use in the common case, but full override when Claude knows better. Note the stealth path needs a ≥60s timeout when solving Cloudflare.

### D9 — Crawl politeness: permissive default
**Choice:** `crawl` ignores robots.txt by default (matches crawl4ai's own `check_robots_txt=False`); the only guardrails are **page/depth caps** to prevent runaway. `--ignore-robots` (explicit), `--respect-robots`, `--max-pages`, `--max-depth` available.
**Why (user's choice, with the ethical tradeoff surfaced):** A personal research tool; the user judged politeness per-task. **Runaway prevention is non-negotiable** regardless — always ship default `max_pages`/`max_depth` caps (crawl4ai's docs warn `max_depth > 3` grows exponentially and urge hard `max_pages`).

### D10 — LLM-API features excluded from v1
**Choice:** Only offline filters (BM25, Pruning). No `-q`, no `LLMContentFilter`, no `LLMExtractionStrategy`.
**Why:** Architecturally right, not just cost-avoidance — Claude is already the reasoning LLM. The CLI delivers clean relevant text; Claude extracts/summarizes. An LLM inside the CLI is redundant, adds API-key/cost/config burden. Offline BM25/Pruning need **no ML extras**.

### D11 — First-run setup is automatic
**Choice:** On first use the skill provisions the venv, installs deps, and runs the browser setup (`scrapling install`, `crawl4ai-setup`), announcing the one-time large download in one line. Claude does not stall on it.
**Why:** Both libraries download hundreds of MB of browsers on first run. Making the skill own this (idempotently) is smoother than asking the user, and the one-line notice keeps it diagnosable.

### D12 — Dependency freshness: pin + manual upgrade
**Choice:** `requirements.txt` pins scrapling/crawl4ai versions; the user upgrades explicitly when a problem appears. **No** task-start version check (that was scrape-x's pattern, and its rationale doesn't apply here — D3).
**Why:** The user chose predictability over auto-upgrade churn. Document the upgrade command in the skill/README so a "sites started blocking me" situation has an obvious remedy.

### D13 — Generated artifacts in English
**Choice:** SKILL.md, code, comments, docstrings, README, CLI output — all English. The planning interview was Korean.
**Why:** Matches the sibling skills, the CLI ecosystem, and is the most stable substrate for Claude's skill-triggering and technical vocabulary. (Independent of the conversation language — this is a deliberate I4 decision, not an assumption.)

---

## Corrections applied to the user's initial mental model (all verified against the official docs)

- **"scrapling accesses almost every website"** — overstated but with a defensible core. Verified: it *does* claim to bypass all Cloudflare Turnstile/Interstitial automatically. But only Cloudflare is named; DataDome/Akamai/PerimeterX/Kasada are undocumented (a scrapling sponsor even *sells* those bypasses separately). Frame as: "handles static, JS-heavy, and Cloudflare-protected sites well; other commercial anti-bot vendors are undocumented — assume unsolved."
- **"scrapling uses my browser cache for logged-in sites"** — inaccurate; see D2. No such feature.
- **"crawl4ai = single-site clean scrapes without polluting context"** — mostly fair, but (1) it's not limited to one site (multi-domain seeding, DomainMapper), (2) it's more than a scraper (structured extraction, etc.), and critically (3) **"without polluting context" is not the default** — filters must be explicitly enabled. This is exactly why D7 makes filtering the default.
