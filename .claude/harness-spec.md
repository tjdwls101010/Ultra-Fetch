# Harness Spec — Ultra Fetch

> Status: **validated** (generated 2026-07-21; hardened 2026-07-22 through an 11-round e2e improvement loop, all scenarios PASS at HEAD). Detailed implementation brief lives in `docs/plan/` (read 00→06). This spec is the canonical anchor a future harness-creator invocation audits against.

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

Final scenario state (each in its most recent run): **20 of 20 PASS.** Unit tests 36 → 39.

### Round 7 — auditing a claim I had made without checking it

Round 5 asserted that "every CLI code path is now exercised against a real site." Auditing that against `catalog`'s own flag list showed it was **false**: eleven flags had never been run against anything. The claim was the same species of error the skill exists to prevent — a confident statement not traced to evidence — so it was checked and closed rather than softened.

Newly exercised, all passing: `fetch --format text` (links stripped), `map --format txt`, `map --pattern` (8/8 matched the glob), `map --live-check`, `crawl --query` (recorded in the manifest, per-page filtering applied), `crawl --strategy bfs` and `dfs`, `crawl --respect-robots`, `crawl --exclude` (0 of 4 pages matched the excluded glob), `crawl --include-external`, `crawl --timeout`, and `setup --upgrade`.

`setup --upgrade` was the one carrying real risk, since it mutates the shared venv and rewrites `requirements.txt`. Run behind a restore point (the file is git-tracked and was backed up first): it upgraded, found both libraries already current, re-pinned to identical versions, preserved the file's comments, and left the tests and a live fetch passing. `git diff` on the file is empty afterwards.

**Coverage is now literal rather than asserted:** every flag in `catalog` has been run against a real site or a real venv.

### Round 8 — the cold start, which had never once run

The launcher's first-run branch (B9/B10) provisions the venv, installs both browser stacks, and prints the one-time-download notice. It had **never executed in this entire effort**: the venv was created by hand in the session's first minutes for the coexistence de-risk, so every subsequent run took the already-provisioned path. This is the first thing a new user hits and it was the least tested thing in the project.

Run properly, with the existing venv moved aside rather than deleted: provisioning completed and a stealth fetch succeeded in **52 seconds**, after which all three commands, the Cloudflare-bypassing stealth tier, and the full unit suite passed against the freshly built environment. One caveat worth recording honestly — the browser caches (`~/Library/Caches/ms-playwright`, Patchright's equivalent) live outside the venv and were already warm, so a genuine first run on a clean machine downloads several hundred MB and takes correspondingly longer. The notice exists for exactly that case.

### Rounds 9–11 — three error paths, and a fix that provoked a regression twice

Testing the exit-code paths, which had never been exercised, found two wrong and then re-testing found a third that an earlier improvement had silently broken:

- **`setup --browsers` crashed with a raw traceback and exit 1** when a venv binary was missing — precisely the damaged install exit 2 exists for, so SKILL.md's own advice ("on exit 2, run setup --browsers") misrouted at the moment it was needed.
- **A 204 No Content returned exit 3, "unreachable"**, hinting at Cloudflare timeouts. The host answered perfectly and simply had no body; the browser retry cannot navigate to a 204 and its exception was propagating. The retry is opportunistic — we already hold a response the host served willingly — so a failed retry now keeps the original and lets exit 4 report it.
- **The regression:** preserving headings and inline tags lifted news1.kr's unrendered shell from 465 to 834 chars, clearing the 500-char floor that triggers JS escalation. It stopped escalating and returned a headline plus photo captions as though it were the article. A floor calibrated against one page stops working the moment extraction improves, so escalation now also weighs what share of the page survives refining — a shell keeps a sliver (news1 9.5%) where real pages keep a lot (slownews 18.7%, ddanzi 61.9%, anthropic 63.1%, docs 65.0%).

**The grounding fix then provoked a regression of its own, twice over, which is the most instructive sequence in this whole effort.** A re-verification run failed on a figure ("49년") lifted from a WebSearch snippet into the lead — aggravated by the answer having quarantined that same snippet sentence's sibling figure as untrustworthy while silently promoting this one. Three additions closed it: rejecting a source rejects *all* of it; the lead is not exempt from the discipline applied to the body; and a grep self-check over every numeral before sending.

The next run then failed on a *different* item: it opened with "확인 끝났습니다. 모든 수치가 제가 직접 연 파일에서 검증됐습니다" — a blanket provenance vouch, which is exactly what the first-sentence rule bans. The cause was the fix itself: told to run a verification check, the model ran it and then announced it. The claim was also false, since the same answer conceded one source it could not reach and another it never opened. Resolved by making the check explicitly silent — *do it, fix what it finds, then just answer*.

Third attempt passed all four criteria, with the grader confirming the sweep still ran (visible in the transcript) while nothing about it surfaced in the output.

**The standing lesson for this harness:** improvements here are not monotonic. A change that repairs one behaviour can move a threshold or add an instruction that breaks another, and both regressions in this sequence were introduced by fixes, not by drift. Re-verify the full suite after any change to extraction thresholds or to the grounding section — spot-checking the thing you just fixed is what let both of these through.

### The provenance-vouch, which took six attempts and taught the most

A full-suite re-verification (8 scenarios) after the grounding-section change came back 7/8. The Korean multi-source research scenario failed again — but grounding, attribution (18/18) and selective-retention all *passed*; the sole defect was the answer opening with a process-vouch ("모든 수치의 출처가 파일에 대조되어 확인됐습니다" — every figure verified against the files). This is the single most stubborn behaviour in the whole harness, and the sequence of six attempts to remove it is worth keeping as a case study:

1. Rule stated as one bullet inside the grounding section → the model opened with a source count ("11건의 기사를 확인했습니다").
2. Own paragraph with a delete-test → opened with a verification verb instead of a count.
3. Made explicitly silent ("run the check, don't report it") → opened with "확인 끝났습니다. 모든 수치가 검증됐습니다" — the check instruction itself provoked the announcement.
4. Hoisted to its own top-level section with the impulse named → opened with "5건의 기사를 본문까지 읽어 확인했습니다", a count-plus-verb the model didn't perceive as "the first sentence" because it read as a preamble.
5. Closed the preamble loophole and *redirected* the sourcing-scope urge to a neutral Sources list → the opener finally became a clean substantive claim, but the verdict **migrated to a closing line** ("위 수치는 모두 아래 기사 본문에서 직접 확인한 것입니다").
6. Banned the closing verdict with its own concrete ✗ example and made the Sources list stand alone → **PASS**, adversarially graded across four axes: topic-heading opener, no verdict anywhere, grounding 32/32, attribution 12/12.

Two things generalise from this. First, **suppression relocates a drive; redirection dissolves it.** The sourcing-scope impulse had an honest home (a list of what you read), and pointing it there fixed the opener permanently. The verification-*verdict* impulse has no honest home — a global "I verified everything" is epistemically hollow, since it asks the reader to trust one blanket assurance over the per-figure citations that are the actual evidence — so it can only be suppressed, and suppression had to be applied to *every* slot (top, then bottom) before it stopped migrating. Second, the residual failures across attempts 2–5 were **truthful** statements introducing zero false claims; the tool's actual purpose (never present ungrounded web content) was met the entire time. The vouch rule protects against a *different* answer where the blanket assurance would launder an ungrounded figure — which is why it is worth enforcing even though every observed violation was itself accurate.

After the fix, G1 and G5 (the other vouch-eligible multi-item scenarios) were re-run at HEAD to confirm no regression: both opened with clean substantive claims, and G5's derived counts (Einstein 3, 8 authors, 10 quotes on page 1) were verified against the crawled artifact and reconcile. **Full suite 8/8 at HEAD.**

### Round 13 — content-type handling and hint accuracy

Probing input shapes the e2e suite never used surfaced two real defects:

- **A PDF URL was processed as HTML.** An arXiv PDF ran through the markdown pipeline and produced **1,982,087 chars of binary mojibake saved at exit 0** — garbage reported as success, the exact failure this tool exists to prevent. `fetch` now reads the `Content-Type` header (available on both tiers) and refuses definitively non-page types (PDF, images including SVG, audio/video, office documents, archives) with a clear exit-4 message and no file written. XML and JSON are deliberately allowed through as text. Japanese and Chinese pages were checked in passing and are clean UTF-8 — the encoding handling is genuinely general, not Korean-tuned, so that was *not* a gap.
- **A dead domain and a malformed URL both got a Cloudflare-flavoured hint** ("raise --timeout … anti-bot vendor"), advice with nothing to do with the actual failure. Hints are now matched to the underlying error: a DNS non-resolution says "check the URL for a typo, this is not a bot wall"; a refused connection says the host may be down; only a genuine wall keeps the anti-bot hint.

Unit tests 41→47.

### Round 14 — large-crawl stress test: no defect, one corrected assumption

The 25-page-default crawl had only ever been run at 3–6 pages. Stress-tested at 30 pages against a real docs site (docs.astral.sh/uv): **30 pages in 10.4s, peak RSS 250 MB, 0 failed, 0 empty, exit 7 honestly reported, content 476–43,556 chars/page.** The mechanics scale cleanly — no defect.

The test did overturn a stored assumption. Every crawl reported `max_depth_reached: 1` regardless of `--max-depth`, and probing crawl4ai's own per-result `metadata['depth']` confirmed the manifest is faithful — the depth-1 dominance is *correct*, because nav sidebars and tag clouds link most of a site's pages directly from the start page (they are genuinely one hop away). A prior memory note claimed `--query` restores depth by fixing best-first ordering; tested directly, it does not — scores came back uniform (0.333) and the cap still bound at depth 1. So `--max-pages`, not `--max-depth`, is the real constraint on nearly all sites, and a shallow crawl is usually complete rather than deficient. Corrected the project memory and added a SKILL.md line so a correct shallow crawl isn't misreported as a failure.

### Round 6 — the layer re-decision: why grounding stays advisory, measured

Grounding was the one behaviour that failed repeatedly (three times, in three different surface forms) before prose finally held it. The harness-creator feedback-routing table prescribes exactly one move for that pattern: *"An always-required rule gets ignored → strengthen the phrasing. If that's still not enough after a re-run, escalate it to a hook — this is a real re-decision about which layer the requirement belongs in."* The original **no hooks** decision predates all of this evidence and was argued on safety grounds (fetching is read-only), not on grounding. So the re-decision was actually evaluated rather than assumed.

A prototype detector was built — extract every numeric token from a session's final answer, check each against the artifacts that session fetched — and measured against seven e2e runs whose verdicts were already known:

| run | verdict | unmatched / total | ratio |
|---|---|---|---|
| R2E | **FAIL** | 4/4 | 100% |
| R3E | PASS | 4/5 | 80% |
| R5W | PASS | 2/3 | 67% |
| R3G | PASS | 2/5 | 40% |
| R5A | PASS | 3/9 | 33% |
| R2B | **FAIL** | 12/97 | 12% |
| R4B | PASS | 5/81 | 6% |

**No threshold separates the two classes** — the lowest FAIL (12%) sits beneath four PASSes ranging to 80%. The detector has essentially no discriminative power, and the reason is structural rather than tunable: R3E is the *exemplar* of correct behaviour, where every count was computed with `sort | uniq -c` and reconciled against its own stated total. Its numbers (`20 authors`, `30 quotes`) are **derived**, therefore correct, therefore by construction absent from the artifact text. A fabricated count is absent for the opposite reason. To any text-matching check the two are indistinguishable, and the very discipline the skill teaches — compute rather than eyeball — is what makes the check fire hardest.

**Conclusion:** the evidence that separates a warranted number from an invented one lives in the *process* (was a command run over the artifact, does the arithmetic reconcile), not in the text, so it is invisible to the layer that could enforce it. Grounding therefore belongs in prose, and the harness's original "no hooks" routing is confirmed — now on measured grounds. Do not re-litigate this without new evidence of a different kind; a numeric-presence hook would fire on the best runs in this suite.

This is also the honest ceiling on the harness. Everything mechanically checkable is checked and passing; the one remaining property is one no harness layer can guarantee, only make more likely — which the five preceding rounds did, by converting a rule that failed three times into a testable output-shape gate that then held.

## Change history

- **2026-07-22 — coverage closed (improve, rounds 5–8).** Closed the items earlier passes had *described* rather than tested, each of which turned up something real. Testing `--wait-selector` found that an unmatched selector waited out the timeout and then reported success; fixed and warned. Redesigning the one non-passing scenario against a library absent from the machine found that `<dt>` parameter labels were being dropped on API references, leaving anonymous descriptions that read as complete. Evaluating whether grounding should escalate from prose to a hook produced a measured negative result (see Validation, Round 6). Auditing the claim "every code path is exercised" found it false — eleven flags had never run — and closed all of them, including `setup --upgrade` behind a restore point. Finally exercised the launcher's **cold-start provisioning path**, which had never run because the venv existed from the session's first minutes: from no venv to a working stealth fetch in 52s on a machine with warm browser caches. Unit tests 36→39.
- **2026-07-22 — hardened (improve).** Four-round e2e improvement loop over realistic WebSearch→fetch research scenarios, terminated on convergence rather than on exhaustion. Fixed five silent defects (inline-tag and heading deletion, short-list-item loss, JS-rendered articles passing the access check, and ungrounded claims/derived numbers/provenance vouching), each with a regression test or a measured before/after. See the Validation section's loop table. Unit tests 31→36.
- **2026-07-21 — generated + validated.** Implemented the skill and CLI from `docs/plan/`. De-risked coexistence first as the plan required (scrapling 0.4.11 + crawl4ai 0.9.2, no conflicts), then built fetch → crawl → map → cli/launcher → tests → skill. Corrected three things the plan had left open or wrong: the `allowed-tools` pattern (`Bash(ultra-fetch:*)` could never match an absolute-path invocation — now `${CLAUDE_SKILL_DIR}`-based), the markdown-from-HTML path (direct generator, no `AsyncWebCrawler`), and dropped the unused `platformdirs` dependency. Added `errors.py` and `fetch.py` to the planned module list. Four bugs found by running the tool against real sites rather than by unit tests — thin-page-treated-as-blocked, hard-blocked-response-winning-on-size, library log noise breaking the stderr contract, and a `--deep` hint that advised `--deep` — each now regression-tested or encoded as a documented gotcha. e2e 12/12 with cited evidence.
- **2026-07-21 — planned (new).** Full planning interview (Korean, ~4 AskUserQuestion rounds) after a thorough read of both libraries' official docs (delegated to two subagents). Produced `docs/plan/00–06` and this spec. Decided: custom skill-bundled CLI (no PyPI), both libraries role-split, `fetch`/`crawl`/`map`, file+stderr output, clean-markdown-default with BM25 `--query`, permissive-but-bounded crawl, offline-only (no LLM/auth/screenshots) v1, English artifacts. Implementation is a separate future session.
