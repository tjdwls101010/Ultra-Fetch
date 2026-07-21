"""The `crawl` command: traverse a site into a directory of markdown + a manifest.

crawl4ai drives this end to end -- it owns both the traversal and the per-page
refining, and its own browser handles rendering. scrapling's stealth tier is not
wired in here: mid-crawl escalation would mean running two browser stacks
against one site, and a crawl is normally aimed at a site we already know is
reachable. If a crawl target turns out to be walled, `fetch` the pages
individually instead -- that path does escalate.

The manifest is the point of the output shape. A crawl can produce dozens of
files; reading them all defeats the purpose. manifest.json gives the caller a
table of contents -- URL, depth, size, relevance score, and why the crawl
stopped -- so it can pick the two pages it actually needs.
"""

import asyncio
from pathlib import Path

from . import config, output
from .errors import EXIT_OK, EXIT_PARTIAL, NoResultsError
from .output import silence_library_logging


def _build_strategy(args):
    from crawl4ai.deep_crawling import (
        BFSDeepCrawlStrategy,
        BestFirstCrawlingStrategy,
        DFSDeepCrawlStrategy,
    )
    from crawl4ai.deep_crawling.filters import FilterChain, URLPatternFilter
    from crawl4ai.deep_crawling.scorers import KeywordRelevanceScorer

    filters = []
    if args.include:
        filters.append(URLPatternFilter(patterns=args.include))
    if args.exclude:
        filters.append(URLPatternFilter(patterns=args.exclude, reverse=True))

    common = {
        "max_depth": args.max_depth,
        "max_pages": args.max_pages,
        "include_external": args.include_external,
        "filter_chain": FilterChain(filters) if filters else FilterChain([]),
    }

    if args.strategy == "bfs":
        return BFSDeepCrawlStrategy(**common)
    if args.strategy == "dfs":
        return DFSDeepCrawlStrategy(**common)

    # best-first: with a query we can steer the traversal itself toward
    # promising links, which is the whole reason this strategy is the default --
    # under a page cap, the order pages are visited in decides what you get.
    scorer = None
    if args.query:
        scorer = KeywordRelevanceScorer(keywords=args.query.split(), weight=1.0)
    return BestFirstCrawlingStrategy(url_scorer=scorer, **common)


async def _crawl(args):
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
    from crawl4ai.content_filter_strategy import BM25ContentFilter, PruningContentFilter
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

    silence_library_logging()  # after the import -- see the note in output.py

    content_filter = (
        BM25ContentFilter(user_query=args.query, bm25_threshold=config.BM25_THRESHOLD)
        if args.query
        else PruningContentFilter(
            threshold=config.PRUNE_THRESHOLD,
            min_word_threshold=config.PRUNE_MIN_WORD_THRESHOLD,
            preserve_tags=config.PRUNE_PRESERVE_TAGS,
        )
    )

    run_config = CrawlerRunConfig(
        deep_crawl_strategy=_build_strategy(args),
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=content_filter, options={"body_width": 0}
        ),
        # crawl4ai's own docs describe the cache default inconsistently across
        # versions, so pin it rather than inherit it. BYPASS because a crawl the
        # caller just asked for should reflect the site as it is now.
        cache_mode=CacheMode.BYPASS,
        check_robots_txt=args.respect_robots,
        mean_delay=args.delay,
        page_timeout=args.timeout * 1000,  # crawl4ai wants milliseconds
        stream=False,
        verbose=False,
    )

    async with AsyncWebCrawler(config=BrowserConfig(headless=True, verbose=False)) as crawler:
        return await crawler.arun(args.url, config=run_config)


def run(args) -> int:
    results = asyncio.run(_crawl(args))

    # With a deep-crawl strategy arun returns a list; guard anyway so a
    # single-result shape can't crash the writer.
    if not isinstance(results, list):
        results = [results]

    successful = [r for r in results if getattr(r, "success", False)]
    if not successful:
        raise NoResultsError(
            f"crawl of {args.url} produced no pages",
            hint="Check the URL is reachable, and that --include/--exclude are not "
            "filtering everything out. A site that blocks crawl4ai's browser may "
            "still be reachable one page at a time via `ultra-fetch fetch`.",
        )

    out_dir = Path(args.output).expanduser() if args.output else (
        config.DEFAULT_OUTPUT_DIR / config.slugify(args.url)
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    entries = []
    for index, result in enumerate(successful, start=1):
        markdown = ""
        if result.markdown:
            # fit_markdown exists only when a content_filter was set, and is
            # empty when the filter kept nothing on this particular page. Falling
            # back per page keeps one over-filtered page from becoming a hole in
            # the crawl.
            markdown = (getattr(result.markdown, "fit_markdown", "") or "").strip()
            if not markdown:
                markdown = (getattr(result.markdown, "raw_markdown", "") or "").strip()

        metadata = result.metadata or {}
        depth = metadata.get("depth", 0)
        filename = f"{index:03d}-{config.slugify(result.url.split('://')[-1])}.md"
        title = metadata.get("title") or ""

        body = f"# {title}\n\n" if title else ""
        body += f"<!-- source: {result.url} -->\n\n{markdown}\n"
        output.write_text(out_dir / filename, body)

        entries.append({
            "url": result.url,
            "title": title,
            "depth": depth,
            "score": round(metadata.get("score", 0) or 0, 4),
            "chars": len(markdown),
            "file": filename,
        })

    capped = len(successful) >= args.max_pages
    max_depth_seen = max((e["depth"] for e in entries), default=0)
    stop_reason = (
        f"max_pages cap ({args.max_pages}) reached -- the site has more pages"
        if capped
        else "traversal exhausted within the depth limit"
    )

    manifest = {
        "start_url": args.url,
        "pages": len(entries),
        "max_depth_requested": args.max_depth,
        "max_depth_reached": max_depth_seen,
        "max_pages": args.max_pages,
        "query": args.query,
        "partial": capped,
        "stop_reason": stop_reason,
        "failed": len(results) - len(successful),
        "entries": entries,
    }
    output.write_json(out_dir / "manifest.json", manifest)

    empty = sum(1 for e in entries if e["chars"] == 0)
    notes = f", {empty} empty" if empty else ""
    output.summarize(
        f"crawled {len(entries)} pages under {args.url} (depth<={max_depth_seen}"
        f"{'/' + str(args.max_depth) if max_depth_seen != args.max_depth else ''}"
        f"{notes}), saved to {out_dir}/ (see manifest.json)"
    )
    if capped:
        output.warn(f"this crawl is partial: {stop_reason}")
        return EXIT_PARTIAL
    return EXIT_OK
