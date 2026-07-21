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

## Reading results well

These are the traps that produce a confidently wrong answer rather than an obvious error.

**`--query` filters lexically, and can correctly return nothing.** BM25 ranks a passage by how much it *stands out within that page*. On a page uniformly about your query, nothing stands out, every passage scores low, and filtering keeps nothing — so the tool falls back to the full clean page and says so on stderr. That fallback is the right answer, not a failure. Conversely, if a result reads off-topic, BM25 kept the least-bad passages of a page that doesn't discuss your query: re-run without `--query` to see what the page actually says. Heed the warnings; they exist because the summary line alone can't tell you this.

**On index and listing pages, the cleaner strips the links — which were the content.** Content filtering scores link-dense blocks as navigation junk, which is right for an article and exactly wrong for a homepage, a blog index, or a forum board. Symptom: a listing page comes back as a few hundred characters of orphaned teaser text with no titles or URLs. Fix: re-run with `--no-filter`, or use `map` if you wanted the URLs anyway. (Measured on a real news index: 0 article links survived filtering, 295 with `--no-filter`.)

**Exit 3 is a verdict, not a hiccup.** It means even the stealth browser was refused. Cloudflare is the documented bypass; DataDome, Akamai, PerimeterX and Kasada are not, so a site using one fails identically every time. Report it unreachable and move on — a retry loop just spends minutes to reach the same conclusion.

**Exit 7 means partial.** A cap stopped the run early. Read `manifest.json`'s `stop_reason` and say what you actually got ("18 of an unknown total, depth ≤ 2"). Presenting a capped crawl as the whole site is the failure mode here, and it's invisible unless you check.

**Crawling ignores robots.txt by default.** Fine for personal research, which is what this is for; pass `--respect-robots` when a task calls for politeness, and keep fan-out bounded regardless.

**Mind your own context.** A crawl directory can be large. Read `manifest.json` first, pick the pages you need from it, and read only those. Dumping a whole crawl into context re-creates the problem this tool exists to solve.

## When it fails

`catalog` documents what each exit code *means*; the notes above say what to *do*. The theme: most failures here are informative rather than transient. A blocked site stays blocked, an empty filter stays empty, and a cap stays hit — so read the code and the warning, change something specific, and only then retry.
