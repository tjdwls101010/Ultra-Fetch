# Validation & Release Plan

E2E validation runs in the **implementation session**, not this one (planning). This file specifies what to test, against which sites, and how to grade it, plus the git/PR/release flow. The user explicitly asked for broad, careful e2e.

## Implementation order (do this, in this order)

1. **De-risk coexistence first.** Create the dedicated venv, `pip install scrapling[fetchers]` + `crawl4ai`, run `scrapling install` + `crawl4ai-setup`. Do a throwaway `Fetcher.get()` + `PruningContentFilter().filter_content(html)` round-trip. If deps conflict, resolve and pin *before* building anything. (See `05-library-facts.md`.)
2. Build `config.py`, `output.py`, `access.py`, `refine.py` → wire `fetch`. Get `fetch` fully working (both tiers, `--query`, collapse guard, file+stderr) before touching crawl/map.
3. Build `crawl.py` → `crawl`; then `mapper.py` → `map`.
4. `cli.py` (argparse, dispatch, exit codes, `catalog`), `setup.py`, the `ultra-fetch` bash launcher.
5. `tests/` — pytest on the pure logic (arg parsing, format/tier selection, summary formatting, collapse-guard decision, exit-code mapping). Network-touching paths can be smoke-tested separately, not in unit tests.
6. `SKILL.md` (per `04-skill-plan.md`), the optional CLAUDE.md trigger line, `.gitignore` (venv path, `.DS_Store`, any `.e2e-runs/`), README.
7. `validate_harness.py --path .` until **0 errors**. Re-read the skill `description` against the skills doctrine (triggering + near-misses).
8. Broad e2e (below). Fix, re-run only what failed.
9. Commit / PR / merge / release.

## E2E scenarios

Compose the run as a dynamic workflow (Run → Grade → Report) per the e2e reference, or sequential subagents if workflows are unavailable. Default to the user's **actually-configured model** for fidelity. Grade with **cited evidence** — a transcript claiming success without the output file actually containing the right content is a FAIL. For artifact scenarios, **read the saved file**, don't trust the summary line.

### Target sites (user-provided + additions)

User-requested (must include):
- `https://claude.com/blog` — English, likely fetchable; good baseline + crawl candidate (blog index → posts).
- `https://slownews.kr/` — Korean long-form; tests UTF-8 + BM25 on Korean text.
- `https://coffeepot.me/addshot/` — Korean; unknown protection — good real-world unknown.
- `https://www.ddanzi.com/ddanziNews` — Korean news/board; list + article structure, possible mild protection.

Additions for coverage (pick/extend as sensible at run time):
- A **Cloudflare-protected** page (to prove stealth escalation actually engages — e.g. a known CF-fronted site). If none handy, find one that returns a challenge to the fast tier.
- A **JS-rendered SPA** where the fast tier returns an empty shell and the browser tier is required (tests escalation on the "empty body" trigger, and `--wait-selector`).
- A **small multi-page docs site** for `crawl` (bounded depth-2, verify manifest + per-page files + partial/`stop_reason` on cap).
- A **sitemap-having domain** for `map` (verify URL discovery; `--query` ranking; `--deep` broadening).
- A page where **`--query` should meaningfully cut content** vs the same page without `--query` (prove the fit_markdown is genuinely smaller and on-topic), plus a **deliberately mismatched query** to prove the collapse-guard fallback fires.

### Scenario matrix (expected behavior → assertion type)

| # | Prompt / action | Expected | Assertion |
|---|---|---|---|
| V1 | "Read <claude.com/blog post URL> for me." | Skill triggers; `fetch`; clean markdown saved; Claude Reads it | Skill-trigger + artifact quality (file has real article text, low boilerplate) |
| V2 | Fetch a page **with** `--query` vs without | fit_markdown is smaller and on-topic; clean version is fuller | Artifact quality (compare the two files) |
| V3 | Fetch a Cloudflare/JS page | Fast tier fails/empties → auto-escalates to stealth → succeeds; summary names `via stealth` | Behavior compliance (escalation happened) + artifact |
| V4 | Fetch `slownews.kr` / `ddanzi.com` article | Correct Korean content, UTF-8 intact, readable markdown | Artifact quality (Korean text correct) |
| V5 | Deliberately mismatched `--query` on a real page | Collapse guard warns + falls back to clean markdown (not near-empty) | Behavior compliance (fallback fired) |
| V6 | "Crawl the docs at <small docs site>, a couple levels deep." | Bounded crawl; `manifest.json` + per-page files; `stop_reason` honest; capped = reported partial | Artifact quality + behavior (caps enforced, partial reported) |
| V7 | "What URLs are under <domain>?" | `map` returns a URL list; `--query` ranks; honest count | Artifact quality |
| V8 (near-miss) | "What's the capital of France?" | Skill does **not** trigger (trivial fact; WebFetch/knowledge suffices) | Near-miss (absence of skill invocation) |
| V9 (near-miss) | "Add a `--json` flag to ultra-fetch's map command." | Skill does **not** trigger — this is repo/dev work | Near-miss |
| V10 (near-miss) | "Get my Facebook feed." | Skill does **not** trigger — authenticated, out of scope; route to scrape-fb | Near-miss |

Keep the *core* run to ~4-6 deep scenarios (per the e2e doctrine: look deeply, don't spread thin); the near-misses (V8-V10) are cheap trigger checks worth including because the trigger posture is preferred-default and must not over-fire. Expand only if a Behavior-inventory item isn't covered.

### Grading discipline (from the e2e reference)
- Every verdict cites a specific transcript event or file content.
- Surface compliance is a FAIL: a crawl that "worked" but whose files are empty, a fetch whose fit_markdown is off-topic, a near-miss that technically didn't call the skill but answered from a hallucination — all FAIL.
- Record results in `.claude/harness-spec.md` → Validation. Note whether headless e2e (`run_e2e.py`'s `claude -p`) actually completes here — the sibling `scrape-x` pass **already confirmed headless e2e works in this environment**, so the mechanism should be trusted; still record the outcome.

## Git / PR / Release flow

The repo already exists (GitHub `tjdwls101010/Ultra-Fetch`, `main`, one commit). No PyPI (D3), so "release" = a GitHub tag/release of the skill + code, not a package publish.

1. Work on a feature branch (e.g. `feat/ultra-fetch-skill`), not `main`.
2. Commit in coherent chunks (setup/config, fetch, crawl, map, cli+launcher, skill, tests, docs). Conventional, focused commits.
3. Open a PR; include a summary of the design (link these plan docs), the validate_harness result, and the e2e results table.
4. Merge to `main`.
5. Tag a release (e.g. `v0.1.0`) with notes covering: what the skill does, the both-libraries architecture, v1 scope (and explicit exclusions: no auth, no LLM features, no screenshots/PDF), and the one-time setup requirement. A CHANGELOG entry if the maintainer wants sibling-consistency.
6. Commit the plan docs and `.claude/harness-spec.md` too — they're the record the next maintenance pass audits against.

## What "done" means

- `validate_harness.py` exits 0.
- `fetch`/`crawl`/`map` all work end-to-end against real sites, saving correct files.
- The skill triggers on the preferred-default intent and stays dark on the three near-misses.
- e2e results (including the user's four target sites) recorded in the harness-spec.
- Branch merged, release tagged.
