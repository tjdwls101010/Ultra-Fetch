---
name: Ultra Fetch
description: Fetch, crawl, or map web pages into clean, context-efficient markdown saved to a file — using a stealth browser that reaches sites the built-in WebFetch can't (bot-protected, Cloudflare, JS-rendered), plus BM25 filtering that keeps only the parts relevant to a query. Use this as the default for actually reading a web page's content, following a search result deeper, reading across a whole site, or discovering what URLs a site has — especially after a WebSearch, or whenever WebFetch is blocked, returns junk, or you need the result saved to disk. NOT for a trivial quick fact where WebFetch already suffices, NOT for logged-in or authenticated pages (out of scope — use the dedicated scrape-x / scrape-fb tools for X and Facebook), and NOT for developing the ultra-fetch tool itself, which is ordinary repo work.
allowed-tools: Bash(${CLAUDE_SKILL_DIR}/scripts/ultra-fetch *), Read
---

# Ultra Fetch

## The division of labor

`ultra-fetch` gets you **access** (a stealth browser that reaches what WebFetch can't) and **clean output** (markdown with the boilerplate stripped, written to a file). Everything else is your judgment: which command fits the question, how deep to go, how much of the result to actually read.

Reach for it by default when you need a page's real content. Stay away from it for a fact you already know, for anything behind a login, and when the task is editing this tool's own code.

## Step 1 — run it

```bash
${CLAUDE_SKILL_DIR}/scripts/ultra-fetch fetch <url> --output <path>
```

The first run provisions a dedicated environment and downloads browser engines — several hundred MB, once. It prints a notice and proceeds; don't treat the pause as a hang. If a command exits **2**, setup didn't finish: run `${CLAUDE_SKILL_DIR}/scripts/ultra-fetch setup --browsers` and tell the user about the one-time download.

## Step 2 — ask the CLI what it can do

```bash
${CLAUDE_SKILL_DIR}/scripts/ultra-fetch catalog
```

Prints every command, flag, default, exit code and output shape as JSON, generated from the argument parser itself. **Work from what it prints, not from a flag list you remember** — including any in this file. The catalog is correct for the installed version by construction; prose copies rot silently.

## The output contract (this will trip you up if you skim)

Every command writes its result to a **file** and prints **one summary line to stderr**. Nothing useful goes to stdout — don't pipe it, don't parse it.

So: always pass `--output` with a path you pick, read the stderr line to see what happened, then `Read` the file. This is deliberate. It hands you control over how much enters your context, which is the entire point of using this over a tool that dumps a page into the conversation.

## Which command

- **`fetch <url>`** — one page. The default way to actually read something. Access escalates on its own (fast HTTP first, stealth browser only if that looks blocked), so don't reach for `--stealth` preemptively; it costs seconds and a browser. Pass `--query` — usually the same words you searched for — to cut a long page down to the relevant passages.
- **`crawl <url>`** — many pages under one site. Bound it to the question: `--max-pages`/`--max-depth` default to 25/2, and a narrow question rarely justifies raising them. Writes one markdown file per page plus `manifest.json`.
- **`map <domain>`** — what URLs exist, without fetching them. The move when a site is big and you need to pick the right pages. Pairs naturally with search: search → map → fetch the two that matter.

## Treat the first run as a probe, then adapt

You cannot know a page's shape before you fetch it. Sites don't announce whether they're an article, a link index, a forum board with pinned notices, or a JS shell — and any rule keyed to "site type" fails on the first site that doesn't match its categories. So don't try to classify up front. **Run once, read the evidence it hands back, and adjust.** A re-run costs seconds; guessing right the first time is not required and not expected.

Every run returns two cheap signals: the **stderr line** (which access tier resolved it, how many characters, and whether the output was `clean`, `query-filtered` or `unfiltered`) and the **file itself**. Read them as probe results:

**Far smaller than the page should plausibly be?** The page's value was in a structure the cleaner scored as navigation junk. Content filtering keeps prose and drops link-dense blocks — right for an article, wrong whenever the links, list items, or table rows *were* the content. Re-run with `--no-filter`. (Measured on a real news index: 0 article links survived filtering, 295 with `--no-filter`.) The general form: whenever what you wanted is structural rather than prose, filtering is working against you.

**Labels present but values missing?** On generated API references (Sphinx and friends), parameter names and their prose descriptions survive filtering, but the **function signature** — which is where the default values live — does not. The result looks complete and is not: you get `has_header` and its explanation with no `=True` anywhere. If the question was about defaults, types, or call syntax, go straight to `--no-filter` and read the signature.

**Got the content but buried in site furniture?** The reverse move — add `--query` with the words you actually care about. On one forum post this cut 21,399 bytes to 3,941 and removed every pinned-notice line while keeping the article intact. `--query` is as useful for *removing* boilerplate the pruner missed as for narrowing a long page.

**Result reads off-topic after `--query`?** BM25 is lexical, and it ranks passages by how much they stand out *within that one page*. Two consequences worth internalizing, because both look like malfunctions and aren't: on a page uniformly about your query nothing stands out, so filtering keeps nothing and the tool falls back to the full clean page (correct — all of it was relevant); and on a page that never discusses your query it returns the least-bad passages anyway (so re-run without `--query` to see what the page actually says). The CLI warns in both cases. Heed the warnings — the summary line alone can't distinguish them.

**Crawling: read `manifest.json` before you trust the crawl.** The titles tell you where the page budget actually went. If they cluster on boilerplate — pinned notices, terms-of-service, a sister domain — the traversal spent its cap on site furniture and the real content is still unvisited. This happens on any site that pins links above the fold, forum boards especially. Re-aim with `--include`/`--exclude`, or drop to the pattern below.

**When a crawl keeps missing, invert it.** `map` (or a `--no-filter` fetch of the listing page) to see what URLs exist, pick the handful that matter, then `fetch` those individually. This is more precise *and* cheaper than crawling and discarding, and it is the better default whenever the target is a board, an index, or any site where you can recognize the right pages by their URLs or titles.

## Every number you state must come from a file you opened

This is the discipline that matters most, and it applies to every use of this tool — a one-page fetch as much as a ten-source research sweep. Fetching is cheap and reading is cheap; the expensive mistake is a fluent paragraph whose figures came from somewhere other than the artifact.

**Point to it or don't say it.** Every figure, date, name and quote in your answer must be one you can locate in a specific saved file. When a number matters and you couldn't ground it, drop it or mark it explicitly unverified — don't soften the wording and keep it.

**Derived numbers are claims too.** Counts, totals, rankings, "most common", per-item breakdowns: having fetched the file does not make your tally of it true. Eyeballing a page and reporting "6 quotes by Einstein" is a guess wearing a statistic's clothes. Compute it — `grep -c`, `sort | uniq -c` — and report what the command printed. Then reconcile: if your per-item numbers don't add up to the total you already stated, at least one of them is invented, and that arithmetic check costs nothing.

**Your first sentence must be a substantive claim about the subject, not about your process.** It may not state a count of sources, articles or files, and may not apply a verb of reading, checking or verifying to your own work — in any language, in any register, and even when the count is exactly right. Here is the test: delete your first sentence. If the answer lost nothing about the topic, it was a vouch, and it was doing harm — a true statement about your bibliography says nothing about the claims that follow while making every one of them look vetted.

> Bad: "I checked 11 articles. Here are the issues." / "11건의 기사를 확인했습니다."
> Good: "Q3 rates were frozen: the fuel-cost adjustment stays at +5 won/kWh even though the calculated requirement was −3.4."

Scoping a *limitation* to what you read is the opposite move and is encouraged — "this figure appeared in only one of the articles I opened" attributes a specific gap, and belongs in the body next to the claim it qualifies.

**Search results are leads, not sources.** When WebSearch precedes a fetch — the normal shape of a research task, and the reason this tool pairs with it — remember that a title and snippet are *claims about* a page. A specific-looking figure from a snippet will slide into your answer as though you had read it. If a lead looked promising but you didn't open it, give it its own line ("found but not read") and let nothing from it into the body. A source list longer than the set of files you actually opened is the tell.

## The rest of the failure modes

**Exit 3 is a verdict, not a hiccup.** Even the stealth browser was refused. Cloudflare is the documented bypass; DataDome, Akamai, PerimeterX and Kasada are not, so a site using one fails identically every time. Report it unreachable and move on — a retry loop spends minutes reaching the same conclusion.

**Exit 7 means partial.** A cap stopped the run early. Read `manifest.json`'s `stop_reason` and say what you actually got ("8 pages, depth ≤ 1, cap hit — the site has more"). Presenting a capped crawl as the whole site is the failure that's invisible unless you check.

**Crawling ignores robots.txt by default.** Fine for personal research, which is what this is for; pass `--respect-robots` when a task calls for politeness, and keep fan-out bounded regardless.

**Mind your own context.** A crawl directory can be large. Read `manifest.json` first, pick the pages you need, read only those. Dumping a whole crawl into context re-creates the problem this tool exists to solve.

## When it fails

`catalog` documents what each exit code *means*; the notes above say what to *do*. The theme: most failures here are informative rather than transient. A blocked site stays blocked, an empty filter stays empty, and a cap stays hit — so read the code and the warning, change something specific, and only then retry.
