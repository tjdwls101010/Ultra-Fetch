# SKILL.md Plan

The skill is half the product. Its job: teach Claude *when* to reach for Ultra Fetch and *how to read what comes back* — not to restate the CLI's flags (that's `catalog`'s job, and prose copies rot). Model the structure on the sibling `scraper-for-x/.claude/skills/x/SKILL.md`, which is an excellent, battle-tested template for this exact shape (published-tool-driven-by-a-skill).

Write it in **English** (D13). Single file (no `references/` unless a genuine branch emerges — see end).

## Frontmatter

```yaml
---
name: Ultra Fetch
description: <see below>
allowed-tools: Bash(ultra-fetch:*), Read
---
```
- The invocable command is `/ultra-fetch` (from the **directory name**, not `name:`) — so the directory MUST be `ultra-fetch`.
- `allowed-tools` pre-approves the launcher invocation and Read so Claude doesn't stall on permission prompts. (If the launcher is called by absolute path, ensure the allow pattern matches how the body actually calls it — verify with a real run.)

### `description` (the ONLY trigger signal — draft, tune against near-misses)

Must trigger on the **preferred-default** intent the user chose (D-trigger): any substantive reading/crawling/saving of web content, however phrased, plus explicit "WebFetch can't reach this" situations. Must name near-misses so it doesn't steal triggers.

Draft:
> "Fetch, crawl, or map web pages into clean, context-efficient markdown saved to a file — using a stealth browser that reaches sites the built-in WebFetch can't (bot-protected, Cloudflare, JS-rendered), and BM25 filtering that keeps only the parts relevant to a query. Use this as the default for actually reading a web page's content, following a search result deeper, scraping across a whole site, or discovering a site's URLs — especially after a WebSearch, or whenever WebFetch is blocked, returns junk, or you need to save the result. NOT for a trivial quick fact where WebFetch already suffices, NOT for logged-in/authenticated pages (out of scope — use the dedicated scrape-x/scrape-fb tools for X/Facebook), and NOT for developing the ultra-fetch tool itself (that's ordinary repo work)."

Triggering notes for the implementer:
- Lead with the capability + the WebFetch-gap intent; current models under-trigger, so lean toward firing.
- The three near-misses (trivial fact, authenticated pages, developing the tool) are the boundary language — keep them.
- Re-read this description against any sibling skill descriptions installed in the same scope to avoid collisions.

## Body structure (sections, in order)

Keep it tight and judgment-focused. Suggested sections:

1. **What this is / the division of labor.** One paragraph: `ultra-fetch` gives access + clean output; *you* decide which command and how deep. State the preferred-default posture and the near-misses in one or two lines so the running model re-confirms scope.

2. **Step 1 — first run / setup.** The launcher auto-provisions on first use; if a command returns exit 2, run `ultra-fetch setup --browsers` and tell the user it's a one-time large browser download. Don't silently hang.

3. **Step 2 — ask the CLI what it can do.** `ultra-fetch catalog` prints every command, real flags, exit codes, and output types, generated from the parser — **work from what it says, do not trust a flag list memorized here.** (Same discipline as the `x` skill: the catalog is correct for the installed version; a prose copy would drift.)

4. **The output contract (the thing that will trip you up).** Every command writes to a **file** and prints only a one-line summary to **stderr** — nothing useful on stdout. Always pass `--output` with a path you choose, then `Read` the file. This is deliberate: it hands you control over how much enters context. (Mirror the `x` skill's blunt framing of this.)

5. **Which command for which job.**
   - `fetch <url>` — one page. Reach for it as the default way to actually read a page's content (not a headline peek). Auto-escalates access; pass `--query` (usually the same query you searched for) to get only the relevant blocks.
   - `crawl <url>` — many pages within a site. Bound it: set `--max-pages`/`--max-depth` to what the question needs, don't crawl a whole domain to answer a narrow question.
   - `map <domain>` — discover URLs first when a site is big and you need to pick the right pages (pairs with WebSearch: search → map → fetch the few that matter).

6. **Reading results well (the gotchas that matter):**
   - **`--query` can over-filter.** If a fetch comes back tiny or empty, BM25's threshold was too high or the page's vocabulary didn't match your query (BM25 is lexical, not semantic). Re-run without `--query` or with `--no-filter`, or rephrase the query with the page's likely wording. The CLI warns on collapse — heed it.
   - **Access escalation is automatic but not infinite.** Exit 3 means even the stealth tier failed — the site likely uses a commercial anti-bot beyond Cloudflare (DataDome/Akamai/PerimeterX are undocumented for scrapling). Report it unreachable; don't loop.
   - **A crawl that hit its cap is partial (exit 7).** Report the shape of what you actually got (N pages, depth, stop reason from `manifest.json`) — never present a capped crawl as the whole site.
   - **Permissive by default.** `crawl` ignores robots.txt by default; if a task calls for politeness, add `--respect-robots`. Keep fan-out bounded.
   - **Context discipline.** These files can be large. Read the manifest first for a crawl; Read only the pages you need. Don't dump a whole crawl directory into context.

7. **When something fails.** Point at `catalog` for what each exit code *means*; state what to *do* (from the exit-code table in `03-cli-spec.md`). Theme, like the `x` skill: most failures are informative, not transient — retrying the same command rarely helps.

## The one CLAUDE.md line (optional but recommended)

The skill listing does **not** survive `/compact`; CLAUDE.md does. For a preferred-default tool this matters over long sessions. Add a single trigger line to the repo `CLAUDE.md` (do not enumerate components):

> When you need to actually read a web page's content, reach a site WebFetch can't, crawl a site, or save fetched content, use the `/ultra-fetch` skill rather than WebFetch.

Keep it to that. If the skill is later copied to `~/.claude/skills/` for global use, the equivalent line belongs in the user-level CLAUDE.md.

## Progressive disclosure

Default to a **single SKILL.md**. Split into `references/` only if a real branch appears where Claude picks exactly one file per invocation (e.g. a deep `references/crawl-tuning.md` for threshold/strategy tuning that a simple fetch never needs). Do not split by length alone — per the skills doctrine, that just adds a routing decision with nothing saved.
