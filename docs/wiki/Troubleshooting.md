# Troubleshooting & Reading Results

`catalog` (and [CLI Reference §7](CLI-Reference.md#7-exit-codes)) documents what each exit code
*means*. This page says what to *do* — and, just as importantly, how to read a **successful** (exit
0) result that's still not what you wanted. Most failure modes here are informative rather than
transient: a blocked site stays blocked, an empty filter stays empty, a cap stays hit. Read the
signal, change something specific, and only then retry.

## 1. Read the two cheap signals first

Every run returns two things worth reading as probe results, not just success/failure:

- **The stderr summary line** — which access tier resolved it, how many characters, and whether the
  output was `clean`, `query-filtered`, or `unfiltered`.
- **The file itself.**

You cannot know a page's shape before fetching it (article vs. link index vs. forum board vs. JS
shell), so don't try to classify up front — run once, read what comes back, adjust.

## 2. Result far smaller than the page should plausibly be

The page's value was probably in a structure the pruner scored as navigation junk — content
filtering keeps prose and drops link-dense blocks, which is right for an article and wrong whenever
the links, list items, or table rows *were* the content. Re-run with `--no-filter`. Measured on a
real news index page: 0 article links survived filtering, 295 with `--no-filter`. General rule:
whenever what you wanted is structural rather than prose, filtering works against you.

## 3. Labels present but values missing

On generated API references (Sphinx, javadoc-style docs), parameter names and their prose
descriptions survive filtering, but the **function signature** — where default values live — does
not. The result looks complete and isn't: you get `has_header` and its explanation with no `=True`
anywhere. If the question is about defaults, types, or call syntax, go straight to `--no-filter` and
read the signature directly.

## 4. Content is there but buried in site furniture

The reverse move: add `--query` with the words you actually care about. On one forum post this cut
21,399 bytes to 3,941 and removed every pinned-notice line while keeping the article intact.
`--query` is as useful for *removing* boilerplate the pruner missed as for narrowing a long page.

## 5. Result reads off-topic after `--query`

BM25 is lexical (see [Concepts §2](Concepts.md#2-content-refinement)) — it ranks passages by how
much they stand out *within that one page*, not by whether they're semantically related to your
query. Two things that look like malfunctions and aren't:

- A page uniformly about your query has nothing that "stands out," so filtering keeps nothing and
  falls back to the full clean page — correct, since all of it was relevant.
- A page that never discusses your query still returns its least-bad passages rather than an
  explicit "not found" — so if the result reads off-topic, re-run without `--query` to see what the
  page actually says.

The CLI warns in both cases; heed the warning rather than trusting the summary line alone.

## 6. A crawl kept landing on boilerplate

Read `manifest.json` before trusting a crawl — the titles tell you where the page budget actually
went. If they cluster on pinned notices, terms-of-service, or a sister domain, the traversal spent
its cap on site furniture and the real content is still unvisited (common on forum boards that pin
links above the fold). Re-aim with `--include`/`--exclude`, or invert the approach entirely: `map`
the site (or `fetch --no-filter` the listing page) to see what URLs exist, pick the ones that
matter, and `fetch` those individually — more precise and usually cheaper than crawling and
discarding.

## 7. `max_depth_reached: 1` and a crawl that looks shallow

This is almost always **correct, not a failure.** Depth is hop-count from the start URL, and a nav
sidebar or tag cloud links most of a site's pages directly from the front page — genuinely one hop
away. `--max-pages` is what actually binds on nearly every real site; raising `--max-depth` doesn't
fix a crawl that stopped at depth 1, because there usually isn't a depth-2+ frontier being missed.
Judge completeness by `pages`/`partial`/`stop_reason` in the manifest, and reach for real depth only
on a site whose content is genuinely chained (sequential pagination with no full pager).

## 8. Exit-code playbook

| Code | What likely happened | What to do |
|---|---|---|
| 2 | Venv or browsers missing/broken. | `ultra-fetch setup --browsers` — a one-time large download, not a bug. |
| 3 | Even the stealth tier was refused. | Report the site unreachable. `scrapling`'s documented anti-bot coverage is Cloudflare; DataDome/Akamai/PerimeterX/Kasada fail here every time. A retry loop spends minutes reaching the same conclusion. |
| 4 (empty page) | Real HTML, no usable text. | Drop `--query`, add `--no-filter`, or try `--wait-selector` for late-rendering JS. |
| 4 (unsupported content) | The URL is a PDF/image/office doc/archive, not a web page. | Don't retry with flags — nothing converts it. Report it as a file to download, not a page to read. |
| 5 | Crawl/map found nothing (empty sitemap, no matching links). | Report honestly; not retryable by rote. |
| 7 | A cap stopped the run early. | State what you actually got (pages, depth, `stop_reason`) — never present a capped crawl as the whole site. |

## 9. General discipline

- **Crawling ignores `robots.txt` by default** — fine for personal research; pass
  `--respect-robots` when a task calls for politeness, and keep fan-out bounded regardless.
- **Mind your own context.** A crawl directory can be large — read `manifest.json` first, then read
  only the pages you actually need. Dumping a whole crawl into context recreates the exact problem
  this tool exists to solve.

---
**Next:** [CLI Reference](CLI-Reference.md) for the flags mentioned above, or [Validation
History](Validation-History.md) to see the real-site testing that surfaced each of these gotchas.
Back to the [index](README.md).
