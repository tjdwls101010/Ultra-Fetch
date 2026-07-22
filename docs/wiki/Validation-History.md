# Validation History

Ultra Fetch has been validated more heavily than most personal tools this size, because unit tests
alone cannot tell you whether a site's bot wall moved. This page is the record of what was actually
tested against real sites, what it found, and why several rounds exist instead of one. For anyone
deciding how much to trust a given code path, or wanting the methodology before adding their own
feature.

## 1. Two layers of validation

- **Mechanical** — unit tests over pure logic only (escalation decisions, the collapse guard,
  catalog integrity, output-path rules), plus `pyflakes` and a harness-structure validator. None of
  this touches the network, because a mocked fetch can't tell you whether a real site's defenses
  changed.
- **Real end-to-end** — a real Claude Code session (`claude -p`, headless) driven against real
  target sites, with the resulting transcript graded adversarially against cited evidence from the
  saved files. This is the layer that actually found every defect below.

## 2. Initial validation — 12/12

The first full pass covered ten scenarios against real conditions: reading a live blog with and
without `--query`, a Cloudflare-challenged page, three Korean-language sites (Hangul round-trips
correctly), a deliberately mismatched query (to confirm the tool reports "not relevant" rather than
inventing content), a bounded crawl, a `map` run, and three near-miss checks (a trivial fact, an
authenticated-content request, editing the tool's own code) to confirm the skill stays silent when
it should. All ten passed, including every user-required site.

## 3. The hardening loop — five silent defects

A further round of realistic WebSearch → fetch research scenarios, iterated to convergence, found
five defects — every one of them silent (exit 0, plausible-looking output, wrong anyway):

| # | Defect | Fix |
|---|---|---|
| 1 | `PruningContentFilter` deleted the **text inside every inline tag** — code spans, bold, link text vanished, leaving `"parameters like , , or"` in place of the real list; a model reading it filled the blanks from memory. | Whitelist inline tags (`code`, `strong`, `a`, …) from deletion. |
| 2 | Headings were dropped too, flattening structured docs into an undifferentiated wall of text. | Whitelist `h1`–`h6` the same way. |
| 3 | Short list items (under 5 words) were dropped, eating parameter-definition lines in reference docs. | Lower the minimum word threshold to 2. |
| 4 | A JS-rendered article shipped enough navigation shell to pass the "did we get content" check while containing no article — the fast tier reported success on photo captions alone. | Add a second escalation check on the *refined* text, not just the raw page. |
| 5 | Claims leaking from WebSearch snippets into the final answer as if they'd been read from the fetched page, plus uncomputed "derived numbers" stated as fact. | Rewrote the skill's grounding guidance as a standalone, testable rule (see [§11](#11-why-grounding-stays-advisory)). |

Defect 5 is the one worth understanding in depth, because the *fix* to it went on to cause its own
regressions — see [§7](#7-error-paths-and-a-regression-the-fix-itself-caused).

## 4. Closing gaps that had been labelled rather than fixed

Two items were initially described as "out of scope" and left there. Both turned out to be
testable, and testing them found real defects:

- **`--wait-selector` had never been run against a real late-rendering page.** It turned out that a
  selector which never matches isn't treated as an error — the fetcher waits out the full timeout
  (measured: 63s vs. 3.4s for a matching selector) and returns the page anyway, silently reporting
  success on content that never arrived. Now detected and warned on.
- **The one scenario that hadn't passed was called a design flaw instead of being fixed.**
  Redesigned against a library genuinely absent from the test machine so a real fetch was required,
  and re-run: passed cleanly.

That redesign surfaced one more defect and one accepted limit:

- **Fixed:** `<dt>` tags (the label half of a definition list — how Sphinx/javadoc-style API docs
  render a parameter name) are one word by construction, so they failed the same short-item check
  as §3's fix, leaving anonymous parameter descriptions that still read as complete. Whitelisted.
- **Accepted:** function-signature default values live in a tag that, when whitelisted, cost 23% on
  unrelated pages for no real recovery of the signature. The model already handles this correctly by
  re-fetching with `--no-filter`, so the fix was to document the symptom rather than force a code
  change with a worse trade-off elsewhere.

## 5. Auditing coverage claims

A stated claim — "every CLI code path has now been run against a real site" — was checked against
`catalog`'s own flag list rather than taken on faith, and turned out to be **false**: eleven flags
had never actually been exercised (`--format text`, `map --format txt`, `--pattern`, `--live-check`,
`crawl --query`, both non-default `--strategy` values, `--respect-robots`, `--exclude`,
`--include-external`, `--timeout`, and `setup --upgrade`). All eleven were then run for real and
passed, including `--upgrade` — the riskiest of them, since it mutates the shared virtualenv and
rewrites `requirements.txt` — which was run behind a restore point and left the repo's tests and a
live fetch passing with no diff in the pinned file.

## 6. The cold start that had never run

The launcher's first-run provisioning branch had never actually executed in the project's entire
development — the virtualenv had been created by hand at the very start for an unrelated de-risking
step, so every later test run took the already-provisioned path. This is the first thing any new
user hits, and it was the least-tested thing in the project. Run properly (with the existing venv
moved aside), provisioning completed and a stealth fetch succeeded in 52 seconds.

## 7. Error paths, and a regression the fix itself caused

Testing the exit-code paths that had never been exercised found two real bugs and then, on
re-testing, a third that an earlier fix had silently introduced:

- `setup --browsers` crashed with a raw traceback (exit 1) on a damaged install — exactly the case
  exit 2 exists to report, so the skill's own advice ("on exit 2, run setup --browsers") misfired at
  the moment it mattered.
- A `204 No Content` response was reported as unreachable (exit 3) — the retry logic couldn't
  navigate a browser to a bodyless response and its exception was propagating, even though the host
  had answered perfectly. Fixed to keep the original response when a retry fails.
- **The regression:** whitelisting headings and inline tags (§3, fixes 1–2) incidentally lifted an
  unrendered JS shell's character count past the threshold that used to trigger escalation, so it
  stopped escalating and returned a headline plus photo captions as the whole article. A fixed
  character floor stops working the moment extraction quality improves elsewhere — the fix was to
  also weigh what *share* of the raw page survives refining (a shell keeps a sliver; a real page
  keeps much more), not just an absolute count.

The grounding fix from §3 then triggered two further regressions of its own, described fully in
[§11](#11-why-grounding-stays-advisory) — the most instructive sequence in this project's history:
a fix that suppresses one failure mode can open another, and both times here the cause was the fix
itself, not drift.

## 8. Content-type handling and hint accuracy

Probing input shapes the earlier suite never used found two real defects: a PDF URL was processed
as if it were HTML, producing nearly two million characters of binary mojibake reported as a
successful fetch (exit 0) — the exact failure this tool exists to prevent. `fetch` now reads the
`Content-Type` header and refuses non-page types (PDF, images, audio/video, office documents,
archives) with a clear message and no file written; XML/JSON are deliberately still allowed through
as text. Separately, a dead domain and a malformed URL were both getting the same "this looks like
an anti-bot vendor" hint as a genuine Cloudflare block — hints are now matched to the actual
underlying error (DNS failure, connection refused, or a real wall).

## 9. Large-crawl stress test

The default 25-page crawl cap had only ever been exercised at 3–6 pages in practice. Stress-tested
at 30 pages against a real documentation site: 30 pages in 10.4 seconds, 250 MB peak memory, zero
failures, correctly reported as partial. No defect — but it did overturn a stored assumption: every
crawl reported `max_depth_reached: 1` regardless of the `--max-depth` value passed, and this turned
out to be **correct**, not a bug (see [Troubleshooting §7](Troubleshooting.md#7-max_depth_reached-1-and-a-crawl-that-looks-shallow)).
A separate claim — that `--query` restores real depth by improving traversal ordering — was tested
directly and found false; `--max-pages`, not `--max-depth`, is the real constraint on nearly every
site.

## 10. `map --deep` verification

The last real-use path that had only ever been run manually, never Claude-driven and graded: two
adversarial scenarios, both passed. One surfaced Claude noticing that a sampled discovery method
under-counted a site's true scale and pivoting to parse sitemaps directly for a far more complete
answer; the other had Claude correctly diagnose an off-target result and fall back to a different
discovery method rather than reporting a bad list as complete.

## 11. Why grounding stays advisory

One behavior — never stating an ungrounded number, and never announcing "I verified this" as a
substitute for citing it — failed repeatedly across several rounds, in different surface forms each
time, before a rewritten SKILL.md section finally held. Before accepting prose as the answer, a
detector was actually built and measured: extract every number from a session's answer, check each
against the files that session fetched. Tested against seven prior runs with known verdicts, it had
**no discriminative power** — the lowest-scoring failing run (12% unmatched numbers) sat beneath
four passing runs (up to 80% unmatched). The reason is structural: a correctly *derived* number
(a count computed with `sort | uniq -c` and reconciled against its own stated total) is, by
construction, absent from the source text — indistinguishable from a fabricated one to any
text-matching check. The evidence that separates a warranted number from an invented one lives in
the *process* (was a command actually run, does the arithmetic reconcile), which is invisible to a
mechanical check. Grounding therefore stays a documented discipline in `SKILL.md` rather than a
hook — a deliberate, measured re-confirmation of the project's original "no hooks" decision, not an
assumption.

## 12. Current state

Every documented CLI code path — all three access tiers and the content-type guard, `crawl` at
scale, `map` both plain and `--deep`, `setup` including `--upgrade` and the cold-start provisioning
branch, and every exit code — has been run against a real site or a real environment at least once.
The remaining known limits are the ones deliberately scoped out of v1 (see [Design Decisions
§2, §10](Design-Decisions.md#2-why-loginauth-is-out-of-scope-for-v1)) and grounding discipline,
which is enforced by review rather than by code, for the measured reason in [§11](#11-why-grounding-stays-advisory).

---
**Next:** [Design Decisions](Design-Decisions.md) for the reasoning these tests were checking
against, or [Troubleshooting](Troubleshooting.md) for the gotchas these rounds turned into guidance.
Back to the [index](README.md).
