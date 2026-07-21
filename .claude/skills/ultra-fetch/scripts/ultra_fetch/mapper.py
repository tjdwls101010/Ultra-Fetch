"""The `map` command: discover what URLs a site has, without fetching them.

This is the reconnaissance step. On a big site, guessing URLs or crawling
blindly wastes far more time than asking the site's own sitemap and the public
indexes what exists, then fetching the two pages that matter.

Two tiers, because breadth costs time:
  default  -- AsyncUrlSeeder over sitemap + Common Crawl. Fast, and enough
              whenever the site publishes a sitemap.
  --deep   -- DomainMapper across eight sources, including crt.sh certificate
              transparency for subdomains and the Wayback Machine. Far broader
              (crawl4ai's own docs show 4 URLs vs 171 on the same domain) and
              correspondingly slower.
"""

import asyncio
from urllib.parse import urlparse

from . import output
from .errors import EXIT_OK, EXIT_PARTIAL, NoResultsError
from .output import silence_library_logging


def _normalize_domain(value: str) -> str:
    """Accept either a bare domain or a full URL; both are natural to pass."""
    if "://" in value:
        return urlparse(value).netloc
    return value.strip("/")


async def _seed(domain: str, args):
    from crawl4ai import AsyncUrlSeeder, SeedingConfig

    silence_library_logging()  # after the import -- see the note in output.py

    seeding = SeedingConfig(
        source="sitemap+cc",
        pattern=args.pattern,
        max_urls=args.max_urls,
        query=args.query,
        scoring_method="bm25" if args.query else None,
        # filter_nonsense_urls drops the asset/tracking noise that would
        # otherwise dominate a large sitemap.
        filter_nonsense_urls=True,
        live_check=args.live_check,
        extract_head=bool(args.query),  # scoring reads page metadata
        verbose=False,
    )
    async with AsyncUrlSeeder() as seeder:
        return await seeder.urls(domain, seeding)


async def _deep_map(domain: str, args):
    from crawl4ai import DomainMapper, DomainMapperConfig

    silence_library_logging()  # after the import -- see the note in output.py

    mapper_config = DomainMapperConfig(
        max_urls=args.max_urls,
        query=args.query,
        scoring_method="bm25" if args.query else None,
        filter_nonsense_urls=True,
        verbose=False,
    )
    mapper = DomainMapper()
    try:
        return await mapper.scan(domain, mapper_config)
    finally:
        close = getattr(mapper, "close", None)
        if close:
            result = close()
            if asyncio.iscoroutine(result):
                await result


def run(args) -> int:
    domain = _normalize_domain(args.domain)

    discovered = asyncio.run(
        _deep_map(domain, args) if args.deep else _seed(domain, args)
    )
    discovered = [d for d in (discovered or []) if d.get("url")]

    if not discovered:
        # Don't advise --deep to someone who already passed it -- a hint that
        # repeats what the caller just did reads as the tool not listening.
        hint = (
            "Even the deep multi-source scan found nothing indexed for this domain. "
            "Small or new sites are often absent from sitemaps, Common Crawl and Wayback "
            "alike; crawl the site directly instead."
            if args.deep
            else "The site may publish no sitemap and be absent from Common Crawl. "
            "Try --deep for a much broader search, or loosen --pattern."
        )
        raise NoResultsError(f"no URLs discovered for {domain}", hint=hint)

    # A query makes the seeder sort by relevance; without one, alphabetical
    # order at least makes the list diffable and scannable by section.
    if args.query:
        discovered.sort(key=lambda d: d.get("relevance_score", 0) or 0, reverse=True)
    else:
        discovered.sort(key=lambda d: d["url"])

    suffix = ".json" if args.format == "json" else ".txt"
    path = output.resolve_output_path(args.output, f"{domain}-map", suffix)

    if args.format == "txt":
        output.write_text(path, "\n".join(d["url"] for d in discovered) + "\n")
    else:
        entries = []
        for item in discovered:
            entry = {"url": item["url"]}
            if item.get("relevance_score") is not None:
                entry["relevance_score"] = round(item["relevance_score"], 4)
            head = item.get("head_data") or {}
            if head.get("title"):
                entry["title"] = head["title"]
            entries.append(entry)
        output.write_json(path, entries)

    capped = len(discovered) >= args.max_urls > 0
    ranked = " (query-ranked)" if args.query else ""
    source = "deep multi-source scan" if args.deep else "sitemap+cc"
    output.summarize(
        f"mapped {len(discovered)} urls for {domain}{ranked} via {source}, saved to {path}"
    )
    if capped:
        output.warn(
            f"hit the --max-urls cap ({args.max_urls}); the site has more URLs than this list shows"
        )
        return EXIT_PARTIAL
    return EXIT_OK
