# Library Facts & Pitfalls (verified against the official docs in `.tmp/`)

Distilled from a thorough read of both docs snapshots (`.tmp/docs_scrapling`, `.tmp/docs_crawl4ai`). These are the facts that shape the implementation and the traps to avoid. When in doubt, verify against the **installed** version — the docs mix versions.

## scrapling — the access layer

- **Install:** `pip install "scrapling[fetchers]"` then **`scrapling install`** (mandatory post-install; downloads browsers + fingerprint deps). Bare `pip install scrapling` gives NO fetchers — importing `scrapling.fetchers` raises `ModuleNotFoundError`. Python ≥3.10. BSD-3.
- **Three fetchers** (not four; `AsyncFetcher` is just the async twin of `Fetcher`):
  - `Fetcher` / `AsyncFetcher` — engine **curl_cffi** (not httpx). Fast static. Key args: `impersonate` (TLS fingerprint, defaults to latest Chrome; accepts a list → random per request), `stealthy_headers=True` (real headers + Google referer), `timeout=30`, `retries=3`, `follow_redirects="safe"` (SSRF-safe). No `OPTIONS`/`HEAD`.
  - `DynamicFetcher` — vanilla Playwright Chromium/Chrome. JS rendering. `.fetch()`/`.async_fetch()`. Args incl. `headless=True`, `network_idle`, `wait_selector`, `wait_selector_state`, `google_search=True`, `real_chrome`, `cdp_url`, `page_action`, `block_ads`, `timeout=30000` (**ms**).
  - `StealthyFetcher` — engine **Patchright** (a patched Playwright; replaced Camoufox at 0.3.13). Same args as Dynamic **plus** `solve_cloudflare`, `block_webrtc`, `hide_canvas`, `allow_webgl=True` (don't disable — WAFs check WebGL). Same speed/memory rating as Dynamic — **no documented speed penalty over Dynamic** except when actually solving Cloudflare.
- **Anti-bot:** StealthyFetcher "easily bypasses all types of Cloudflare's Turnstile/Interstitial automatically." `solve_cloudflare=True` handles JS/interactive/invisible/embedded-captcha challenges. **Limits:** timeout must be **≥60s** when solving Cloudflare; custom implementations may need a manual `wait_selector`; **only Cloudflare is named** — DataDome/Akamai/PerimeterX/Kasada are undocumented (assume unsolved). No general CAPTCHA solving.
- **Output/markdown:** the **Python API has no markdown converter**. It gives HTML (`.html_content`), text (`.get_all_text(...)`), JSON (`.json()`). Markdown + LLM-clean output exist only at the **CLI** (`scrapling extract ... --ai-targeted`, format by `.md`/`.txt`/`.html` extension) and the **MCP** layer (`main_content_only`). **Implication:** since we drive scrapling from Python for access, **we do NOT use scrapling's markdown path — crawl4ai does the cleaning** (see below). Use scrapling to get **HTML**, hand it to crawl4ai.
- **`--timeout` unit trap:** scrapling's HTTP CLI uses **seconds**, its browser CLI uses **milliseconds**. In our own CLI, pick one unit (seconds, per `03-cli-spec.md`) and convert internally.
- **CLI can't do auth browser fetch** (no `--cookies`/`--user-data-dir`/`--cdp-url` on `fetch`/`stealthy-fetch`) — irrelevant since v1 has no auth, but it's why we call the Python API, not the scrapling CLI.
- **Sessions / `user_data_dir`** exist (persistent, session-only) — relevant only if v2 revisits CDP-attach. Not used in v1.

## crawl4ai — the refine + crawl + map layer

- **Install:** `pip install crawl4ai` then **`crawl4ai-setup`** (handles browsers; supersedes `playwright install`). Optionally `crawl4ai-doctor`. Python ≥3.10. Apache-2.0 (+ attribution) — confirm against repo LICENSE. **Pruning/BM25 need NO ML extras** (don't install `[torch]`/`[transformer]`/`[all]`). Assume version **≥0.9.2** is current.
- **The refine engine (our core use):**
  - `DefaultMarkdownGenerator(content_source="cleaned_html"|"raw_html"|"fit_html", content_filter=..., options={...})`. `result.markdown` is a `MarkdownGenerationResult` with `raw_markdown` and — only when a `content_filter` is set — **`fit_markdown`** (the filtered one).
  - `PruningContentFilter(threshold=0.48, threshold_type="fixed"|"dynamic", min_word_threshold=5, preserve_classes=[], preserve_tags=[])` — heuristic junk removal by text/link density + tag importance. **No query.** Right default for a clean fetch. v0.9.1 caveat: it can strip short metadata (author/date) — whitelist with `preserve_classes`/`preserve_tags` if that bites.
  - `BM25ContentFilter(user_query=..., bm25_threshold=1.0, language="english", use_stemming=True)` — classical BM25 over text chunks; keeps only query-relevant ones. **Higher threshold = fewer/more-relevant.** Needs a query ("realistically, supply a query"). **Lexical, not semantic** — vocabulary mismatch scores poorly.
  - **Both filters expose `filter_content(html) -> list[str]` and take a raw HTML string.** This is what lets scrapling do the fetch and crawl4ai do the cleaning, with **no second network request**. Two-pass recipe: `PruningContentFilter(...).filter_content(result_html)` → join → `BM25ContentFilter(...).filter_content(pruned)`.
  - **Collapse guard (implement):** if `fit_markdown` is near-empty, the BM25 threshold was too high or the query mismatched. Warn and fall back to pruned/raw. (Docs flag this explicitly.)
- **Crawl (`crawl` command):**
  - `AsyncWebCrawler(config=BrowserConfig(...))`, `arun(url, config=CrawlerRunConfig(deep_crawl_strategy=...))`. With a deep strategy `arun` returns a **list** (or async generator if `stream=True`).
  - Strategies (`crawl4ai.deep_crawling`): `BestFirstCrawlingStrategy` (⭐ docs-recommended), `BFSDeepCrawlStrategy`, `DFSDeepCrawlStrategy` — all take `max_depth`, `max_pages` (**default infinite — always set it**), `include_external=False`, `filter_chain`, `url_scorer`.
  - Filters (`crawl4ai.deep_crawling.filters`): `URLPatternFilter`, `DomainFilter`, `ContentTypeFilter`, `ContentRelevanceFilter(query=, threshold=)`, `SEOFilter`, composed via `FilterChain([...])`.
  - `check_robots_txt=False` by default (matches D9). Flip via `--respect-robots`.
  - **`cache_mode` default is documented inconsistently** — set it **explicitly** (`CacheMode.BYPASS` for fresh, or `ENABLED` to reuse). Don't rely on the default.
- **Map (`map` command):**
  - `AsyncUrlSeeder` + `SeedingConfig(source="sitemap+cc", pattern="*", query=..., scoring_method="bm25", score_threshold=..., filter_nonsense_urls=True, max_urls=-1)`. Query scoring auto-sorts by relevance.
  - `DomainMapper.scan(domain)` — 8 sources (sitemap, Common Crawl, wayback, crt.sh subdomains, path-probe, robots, feeds, homepage). Much broader (docs example: 4 URLs via seeder vs 171 via mapper). Wire to `--deep`.
- **CLI (`crwl`) exists** with `-f filter_bm25.yml -o markdown-fit` etc., **but file-output flag is undocumented** and `crwl`'s docs are incomplete. **Do NOT shell out to `crwl`** — drive crawl4ai through its **Python API** for a stable contract. (We control our own CLI surface.)
- **MCP/Docker server exists** — not used (D1 chose a local CLI).

## Coexistence & environment (DE-RISK THIS FIRST)

- Both libraries are Playwright-family and must share one venv. **Signal they're meant to coexist:** crawl4ai widened its `lxml` ceiling to `<7` in v0.9.1 explicitly "to co-install with scrapling etc." Still: **the first implementation step should be to create the venv, install both, and run a trivial fetch+refine round-trip** before building anything. If resolution conflicts appear, pin compatible versions and record them in `requirements.txt`.
- Browser installs: scrapling → `scrapling install` (Patchright/Chromium); crawl4ai → `crawl4ai-setup` (Playwright Chromium). These download to separate caches and can coexist; both are the "one-time large download" the setup notice warns about.
- **Two browser stacks** is the real cost of the both-libraries decision (D4). Accept it; it's paid once at setup.
- **macOS:** the docs flag no macOS-specific blockers for scrapling; crawl4ai's known platform bugs were Windows/Linux (Windows `channel='chromium'` crash fixed 0.9.1; Linux system libs). Target env here is macOS (Darwin) — should be smooth, but run `crawl4ai-doctor` in setup.
- **Version freshness (D12):** pin both in `requirements.txt`; `ultra-fetch setup --upgrade` is the documented manual bump. Note crawl4ai's stream-cancel leak was fixed in **≥0.9.2** — pin at least that.

## Concrete integration sketch (for the `fetch` path — verify against installed versions)

```python
# access.py (sketch)
from scrapling.fetchers import Fetcher, StealthyFetcher
def fetch_html(url, force=None, timeout=30):
    if force != "stealth":
        r = Fetcher.get(url, timeout=timeout)          # fast static, TLS-impersonated
        if force == "fast" or _looks_ok(r):            # _looks_ok: status ok, non-trivial body, not a block page
            return r.html_content, "fast"
    r = StealthyFetcher.fetch(url, network_idle=True,  # escalate
                              solve_cloudflare=True, timeout=max(timeout, 60) * 1000)
    return r.html_content, "stealth"

# refine.py (sketch)
from crawl4ai.content_filter_strategy import PruningContentFilter, BM25ContentFilter
def to_markdown(html, query=None):
    pruned = PruningContentFilter(threshold=0.48, min_word_threshold=5).filter_content(html)
    pruned_html = "\n".join(pruned)
    if query:
        chunks = BM25ContentFilter(user_query=query, bm25_threshold=1.0).filter_content(pruned_html)
        md = _html_chunks_to_markdown(chunks)
        if _too_small(md):                             # collapse guard
            md = _html_to_markdown(pruned_html)        # fall back to clean, warn on stderr
        return md
    return _html_to_markdown(pruned_html)
```
`_html_..._to_markdown` should use crawl4ai's markdown generator (e.g. feed the HTML via the `raw:` scheme through `AsyncWebCrawler` with a `DefaultMarkdownGenerator`, or use the generator directly if importable). The implementer must confirm the cleanest markdown-from-HTML-string path against the installed crawl4ai — both `raw:` and direct-generator paths are documented.
