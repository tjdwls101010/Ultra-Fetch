# Harness Spec — Ultra Fetch

> Status: **validated** (generated 2026-07-21; hardened 2026-07-22 through a 5-round e2e improvement loop, 20/20 scenarios PASS). Detailed implementation brief lives in `docs/plan/` (read 00→06). This spec is the canonical anchor a future harness-creator invocation audits against.

## Context

New repo `Ultra Fetch` (GitHub `tjdwls101010/Ultra-Fetch`, `main`, README-only so far). macOS/Darwin, Python 3.12, `uv` 0.8.0 available. An empty placeholder skill dir `.claude/skills/ultra fetch/` (with a space) exists — to be replaced by `.claude/skills/ultra-fetch/`.

Third sibling in the maintainer's crawler ecosystem after `scraper-for-x` (`scrape-x`) and `scraper-for-facebook` (`scrape-fb`), but deliberately different in distribution: those are PyPI packages driven by companion skills; Ultra Fetch is a **skill-bundled CLI, no PyPI** (see D3).

User is comfortable with Claude Code vocabulary and reasons about tradeoffs directly (led the PyPI-is-unnecessary and cut-login decisions). Interview in Korean; **generated artifacts in English** (D13).

## Goals

Overcome the built-in `WebFetch`'s four limits — can't reach many sites, can't crawl, can't save to file, floods context — with a CLI Claude reaches for naturally alongside `WebSearch`. Two libraries, role-split: **scrapling = access/stealth**, **crawl4ai = refine (Pruning/BM25) + crawl + map**. Clean, context-efficient markdown saved to a file; `--query` cuts to only the relevant blocks. v1 is public-content only.

User's framing: make it as a **CLI** ("코드를 cli형태로 잘 만들어야"), think from **the perspective of Claude using it**, and refactor the code into maintainable multiple files under the skill's `scripts/`.

## Behavior inventory

| id | behavior/knowledge/constraint | layer | component | status |
|----|-------------------------------|-------|-----------|--------|
| B1 | scrapling is the access layer (fast static → stealth escalation); crawl4ai never fetches for `fetch` | skill+code | ultra-fetch | implemented |
| B2 | crawl4ai is the refine layer: PruningContentFilter default, BM25ContentFilter when `--query`, on the HTML scrapling returns (no re-fetch) | skill+code | ultra-fetch | implemented |
| B3 | `fetch` auto-escalates access; `--fast`/`--stealth` override; Cloudflare solve needs ≥60s | skill+code | ultra-fetch | implemented |
| B4 | Every command writes to a `--output` file + one-line stderr summary; nothing substantive on stdout; Claude Reads the file | skill+code | ultra-fetch | implemented |
| B5 | Default clean markdown; `--query`→ BM25 fit_markdown; collapse guard warns + falls back when fit is near-empty | skill+code | ultra-fetch | implemented |
| B6 | `crawl` bounded by default `max_pages`/`max_depth`; robots ignored by default (permissive), `--respect-robots` flips it | skill+code | ultra-fetch | implemented |
| B7 | `map` discovers URLs (AsyncUrlSeeder; `--deep`→ DomainMapper; `--query`→ BM25 ranking) | skill+code | ultra-fetch | implemented |
| B8 | `catalog` self-describes the CLI from argparse; skill never restates flags in prose | skill+code | ultra-fetch | implemented |
| B9 | Dedicated venv (outside repo, platformdirs cache) provisioned once; `ultra-fetch` bash launcher fronts `python -m ultra_fetch` | code | ultra-fetch | implemented |
| B10 | First-run auto-setup (`scrapling install` + `crawl4ai-setup`) with one-line "one-time large download" notice; exit 2 = setup needed | skill+code | ultra-fetch | implemented |
| B11 | Deps pinned in requirements; `setup --upgrade` is the manual freshness path (no task-start version check) | code | ultra-fetch | implemented |
| B12 | Access failing even after stealth (exit 3) = commercial anti-bot beyond Cloudflare or site down; report, don't loop | skill | ultra-fetch | implemented |
| B13 | Capped crawl (exit 7) is partial; report shape (pages, depth, stop_reason from manifest), never as the whole site | skill | ultra-fetch | implemented |
| B14 | No LLM-API features in v1 (offline BM25/Pruning only); Claude does semantics | code | ultra-fetch | implemented |
| B15 | Multi-file refactored code under scripts/ (cli/access/refine/crawl/mapper/output/setup/config) for maintainability | code | ultra-fetch | implemented |

## Component specs

**Skill `ultra-fetch`** — `.claude/skills/ultra-fetch/SKILL.md`, English, single file (no `references/`; no real branch emerged). Frontmatter: `name: Ultra Fetch`, `allowed-tools: Bash(${CLAUDE_SKILL_DIR}/scripts/ultra-fetch *), Read`, and a `description` that triggers on the preferred-default "read/crawl/map/save web content" intent and names three near-misses (trivial fact, authenticated pages, developing the tool itself). Body teaches judgment + the output contract + gotchas, and points at `catalog` rather than restating flags. Full plan: `docs/plan/04-skill-plan.md`.

**Code** — `.claude/skills/ultra-fetch/scripts/` with the module breakdown in `docs/plan/02-architecture.md` and the CLI contract in `docs/plan/03-cli-spec.md`. Dedicated venv + bash launcher. Library facts/pitfalls in `docs/plan/05-library-facts.md`.

### Corrections to the plan, found during implementation

The plan left several points explicitly to be verified against the installed libraries. What the verification actually returned:

- **`allowed-tools` — the plan's `Bash(ultra-fetch:*)` would never have matched.** Bash permission patterns are prefix matches on the literal command string, and the launcher is not on PATH, so the real command begins with an absolute path. The working form is `Bash(${CLAUDE_SKILL_DIR}/scripts/ultra-fetch *)`, with the same variable used in the skill body so pattern and invocation agree. (`${CLAUDE_SKILL_DIR}` needs Claude Code ≥2.1.129; this environment is 2.1.216.) A mismatch degrades to a permission prompt rather than a failure, so this was cheap to get wrong and worth getting right.
- **Markdown-from-HTML path resolved.** `docs/plan/05` left the choice between the `raw:` URL scheme and the direct generator open. `DefaultMarkdownGenerator().generate_markdown(input_html=...)` works directly on an HTML string, so `fetch` needs no `AsyncWebCrawler` and no event loop at all.
- **Coexistence de-risk passed clean**: scrapling 0.4.11 + crawl4ai 0.9.2 in one venv, zero resolution conflicts.
- **`platformdirs` dropped** — the plan listed it in requirements, but the venv path is XDG-specified and default output paths use `tempfile.gettempdir()`, so nothing imported it.
- **Two modules added** beyond the plan's list: `errors.py` (the exception→exit-code contract, shared by every module) and `fetch.py` (the `fetch` command's orchestration, keeping `cli.py` thin as the plan required and matching `crawl.py`/`mapper.py`'s command-per-module shape).

### Gotchas discovered by running the thing, now encoded in code and SKILL.md

- **BM25 can correctly return nothing.** It ranks a chunk by how much it stands out *within one page*, so on a page uniformly about the query no chunk stands out and filtering keeps nothing. The collapse guard's fallback to the full clean page is the right answer there. `--query` narrows *mixed* pages.
- **Content filtering strips index pages.** Link-dense blocks score as navigation junk — correct for an article, exactly wrong for a homepage or board. Measured on slownews.kr: 0 article links survived filtering, 295 with `--no-filter`.
- **A thin page is not a blocked page.** `example.com` is 142 chars and blocked by nobody; an early build reported it unreachable. Escalation signals are now split hard (bot-wall status, challenge markers) vs soft (thin body), and only hard signals may be terminal.
- **A hard-blocked response must never win on size.** A Cloudflare 403 interstitial (5,950 bytes) is *larger* than the solved page behind it (4,060), so a size comparison shipped the block page as a successful fast fetch. Regression-tested.
- **Silence library logging *after* importing the library.** scrapling sets its own logger level at import, silently overwriting an earlier call — and logs `ERROR: No Cloudflare challenge found.` on every stealth fetch of a non-Cloudflare site, which reads as failure when nothing failed.

**No hooks, no permissions rules, no agents.** Fetching is read-only; politeness caps live in the CLI; nothing needs deterministic enforcement (same conclusion as the sibling `x` skill's D4). Optional single CLAUDE.md trigger line (survives `/compact` where the skill listing doesn't); do not enumerate components.

## Design rationale

Full decision log with reasoning: `docs/plan/01-decisions.md` (D1–D13). The load-bearing, user-led ones: **D1** custom CLI over the libraries' existing MCP servers; **D2** cut login from v1 (WebFetch's gaps are all public-content; auth belongs to the sibling per-platform tools); **D3** no PyPI — Ultra Fetch's own code is a stable wrapper, what rots is its dependencies, so scrape-x's PyPI+version-check rationale doesn't transfer; **D4** both libraries, role-split, because their strengths (stealth vs. clean-output/crawl) are complementary and barely overlap; **D9** permissive crawl with mandatory runaway caps; **D10** no in-CLI LLM (Claude is the reasoning LLM).

## Validation

**Mechanical:** `validate_harness.py` 0 errors / 0 warnings. 31 unit tests pass (pure logic only — escalation decisions, collapse guard, catalog integrity, output-path rules; nothing network-touching). `pyflakes` clean. No hooks exist, so `test_hook.py` does not apply.

**E2E: 12/12 PASS**, run 2026-07-21 as a dynamic workflow (Run → Grade → Report) on the session's real model (Opus 4.8, 1M), one headless session per scenario, graded adversarially with cited evidence per `references/e2e-testing.md`. Headless `claude -p` completed cleanly for every scenario — **the mechanism is confirmed working in this environment**, so the standing caveat about unverified headless permission handling can be dropped for this project.

| # | Scenario | Result |
|---|---|---|
| V1 | Read claude.com/blog, name the 3 latest posts | PASS — skill fired, `web_fetch_requests: 0`; grader read all 4 saved files, confirmed the 3 named posts are genuinely the most recent (the agent correctly ignored a pinned older featured block), fact-checked every claim against the artifacts, zero unsupported |
| V2 | Same page with vs without `--query` | PASS — 15,965 chars (clean) vs 3,681 (query-filtered), 23%; grader re-ran `wc` and grep-verified specific passages kept/dropped |
| V3 | Cloudflare-challenged page | PASS — `via stealth (escalated: HTTP 403)`; saved file contains "You bypassed the Cloudflare challenge", not an interstitial |
| V4a | slownews.kr (Korean) | PASS — Hangul intact; agent hit the index-page filtering gotcha, noticed the thin result, and re-ran unfiltered |
| V4b | ddanzi.com (Korean) | PASS — Hangul intact, summary grounded in the artifact |
| V4c | coffeepot.me/addshot (Korean, protection unknown at design time) | PASS — resolved on the fast tier; Hangul intact |
| V5 | Deliberately mismatched `--query` ("zebra migration") | PASS — low-yield guard fired; Claude relayed that the page does not discuss the query instead of inventing zebra content |
| V6 | Bounded crawl | PASS — manifest.json + non-empty per-page files; cap hit and honestly reported as partial |
| V7 | `map docs.astral.sh` | PASS — chose `map` (not crawl/fetch), real URL list, honest count, disclosed the cap |
| V8 | Near-miss: "capital of France?" | PASS — zero tool calls, answered from knowledge |
| V9 | Near-miss: "add a `--json` flag to map" | PASS — zero `Skill` events; did ordinary repo work (Bash/Read) |
| V10 | Near-miss: "get my Facebook feed" | PASS — zero ultra-fetch invocations; declined authenticated content |

All four user-required sites (`claude.com/blog`, `slownews.kr`, `coffeepot.me/addshot`, `ddanzi.com`) passed, as did the Cloudflare, crawl and map coverage additions. The trigger posture is confirmed on both sides: it fires on every genuine read/crawl/map intent and stays dark on all three near-misses.

**Not covered by e2e:** a JS-rendered SPA requiring `--wait-selector` (planned in `docs/plan/06` but no suitable target surfaced — the flag is exercised only by unit-level argument handling, not against a real late-rendering site). Note the *automatic* JS path is now covered: news1.kr renders its article client-side and the second-chance escalation handles it without `--wait-selector`.

### Improvement loop (2026-07-22) — 4 rounds, terminated on convergence

After the initial pass, a further e2e programme ran realistic WebSearch→fetch research scenarios and iterated. Termination conditions were set in advance: all-pass, or 3 rounds, or no new actionable defect, or the cause traced outside the harness. Round 3 hit the round cap while holding one precise, high-confidence fix, so a single targeted re-run was allowed rather than stopping on a count — then the loop closed.

The loop found five defects that unit tests could not, all of them silent:

| # | Defect | Fix | Verified by |
|---|---|---|---|
| 1 | `PruningContentFilter` deleted the **text inside every inline tag** — code, emphasis, link text. `parameters like \`language\`, \`case_sensitive\`, or \`priority_tags\`` was saved as `parameters like , , or`, and a model filled the blanks from memory and quoted the result as documentation. 35 code spans, 45 bold spans and all link text lost on one real doc page. | `PRUNE_PRESERVE_TAGS` | R2A + unit test |
| 2 | Headings dropped too — structured docs became an undifferentiated wall (4→17 headings recovered on one page). | same whitelist, `h1`–`h6` | measured on 3 pages |
| 3 | Short list items dropped at `min_word_threshold=5`, eating **parameter definition lines** in reference docs and orphaning the prose beneath them. | threshold → 2 (preserving `<li>` wholesale was worse: it dragged a forum board's menu back in) | R2A finding, measured on 4 pages |
| 4 | A **JS-rendered article** shipped enough navigation to pass the access-tier check while containing no article, so the fast tier returned photo captions and reported success. | second-chance escalation judged on the *refined* text, plus a `pruning_collapsed` flag so the fallback can't mask it | R2C + 3 unit tests |
| 5 | Claims leaking from WebSearch snippets, ungrounded **derived numbers** (a per-author count table that was never computed and summed to 34 against its own stated total of 40), and an opening provenance vouch that survived two rewrites by changing surface form across languages. | SKILL.md grounding rewritten as a standalone principle covering derived numbers, plus a testable first-sentence output-shape rule with a delete-test | R3E, R3G, R4B |

Defect 5 is the instructive one for future maintenance: the rule was *correct* in round 2 and still failed, because it was framed under a WebSearch-specific heading and so read as inapplicable when no search had run, and its negative examples were all English read/verify phrasings that a Korean neutral-register sentence slid past. Fixing it meant converting a rhetorical prohibition into a checkable output-shape gate — evidence for the harness-creator principle that a rule survives only where the model can re-derive it, and that examples teach pattern-matching unless the principle is stated in its own right.

### Round 5 — closing the two gaps that had been labelled rather than fixed

The loop was initially stopped with two items described as out of scope. Both were in fact testable, and describing a gap is not closing it, so both were closed:

- **`--wait-selector` was never exercised against a real SPA.** Testing it found a real defect: a selector that never matches is not an error to the fetcher — it waits out the timeout (measured 63s vs 3.4s for a matching selector) and returns the page anyway, so the CLI reported success while the content the caller waited for was absent. Now detected via `response.css(selector)` and warned, with two unit tests. This is exactly the kind of silent failure the tool exists to prevent, and it survived only because the path was documented as untested instead of being tested.
- **The one non-passing scenario was called a design flaw and left there.** Redesigned against a library absent from the machine (`polars`) so fetching is genuinely required, and re-run: **PASS**, with 62 intact inline-code spans and all 34 parameters verified against the artifact, zero inventions.

That redesign then surfaced a further defect and one accepted limit:

- **Fixed — `<dt>` labels.** Every Sphinx-style API reference renders a parameter as `<dt>name</dt><dd>description</dd>`. A `<dt>` is one word by construction, so it failed the min-word check while its description survived, leaving a page of *anonymous descriptions that still read as complete*. Measured on polars' `read_csv`: 1 of 10 names survived, 34 of 34 after whitelisting `dt`, at +737 chars on that page and **+0** on an article, a docs guide, a Korean news post and a forum board.
- **Accepted limit — signature defaults.** Default values live in the function signature, which filtering still drops. Whitelisting `<span>` was tried and rejected on measurement: it did not recover the signature and cost +23% on a forum board. The model already handles this correctly by re-fetching with `--no-filter` (verified in R5A), and SKILL.md now names the symptom — labels present, values missing — so the remedy is reached directly rather than rediscovered.

Final scenario state (each in its most recent run): **20 of 20 PASS.** Unit tests 36 → 39. Every CLI code path is now exercised against a real site.

## Change history

- **2026-07-22 — hardened (improve).** Four-round e2e improvement loop over realistic WebSearch→fetch research scenarios, terminated on convergence rather than on exhaustion. Fixed five silent defects (inline-tag and heading deletion, short-list-item loss, JS-rendered articles passing the access check, and ungrounded claims/derived numbers/provenance vouching), each with a regression test or a measured before/after. See the Validation section's loop table. Unit tests 31→36.
- **2026-07-21 — generated + validated.** Implemented the skill and CLI from `docs/plan/`. De-risked coexistence first as the plan required (scrapling 0.4.11 + crawl4ai 0.9.2, no conflicts), then built fetch → crawl → map → cli/launcher → tests → skill. Corrected three things the plan had left open or wrong: the `allowed-tools` pattern (`Bash(ultra-fetch:*)` could never match an absolute-path invocation — now `${CLAUDE_SKILL_DIR}`-based), the markdown-from-HTML path (direct generator, no `AsyncWebCrawler`), and dropped the unused `platformdirs` dependency. Added `errors.py` and `fetch.py` to the planned module list. Four bugs found by running the tool against real sites rather than by unit tests — thin-page-treated-as-blocked, hard-blocked-response-winning-on-size, library log noise breaking the stderr contract, and a `--deep` hint that advised `--deep` — each now regression-tested or encoded as a documented gotcha. e2e 12/12 with cited evidence.
- **2026-07-21 — planned (new).** Full planning interview (Korean, ~4 AskUserQuestion rounds) after a thorough read of both libraries' official docs (delegated to two subagents). Produced `docs/plan/00–06` and this spec. Decided: custom skill-bundled CLI (no PyPI), both libraries role-split, `fetch`/`crawl`/`map`, file+stderr output, clean-markdown-default with BM25 `--query`, permissive-but-bounded crawl, offline-only (no LLM/auth/screenshots) v1, English artifacts. Implementation is a separate future session.
