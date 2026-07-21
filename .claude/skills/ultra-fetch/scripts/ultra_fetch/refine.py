"""The refine layer: HTML string in, context-efficient markdown out.

crawl4ai owns this, and it never touches the network here -- both content
filters accept a raw HTML string, which is precisely what lets scrapling do the
access and crawl4ai do the cleaning on one fetch.

The pipeline is prune-then-BM25, in that order and on the same HTML:

    raw html --[PruningContentFilter]--> article-ish html --[BM25]--> on-topic chunks

Pruning is heuristic (text density, link density, tag importance) and query-blind,
so it strips nav/footer/ads and leaves the article. BM25 is lexical and
query-driven, so it keeps only the passages that share vocabulary with the
query. Running BM25 on already-pruned HTML means it scores article prose against
the query instead of wasting its ranking budget discriminating against a sidebar
it was never going to keep.

The BM25 trap, which is not obvious and bites in testing: BM25 ranks a chunk by
how much it stands out *within this one page*. A term appearing in most chunks
gets a near-zero or negative IDF, so on a page that is uniformly about the query,
nothing stands out, every chunk scores below threshold, and filtering keeps
NOTHING. That looks like a bug and is not: `--query` narrows a *mixed* page (an
article plus unrelated sections, a long doc where one passage matters), and on a
page wholly about the query the collapse guard returns the whole clean page --
which is the correct answer for that page anyway.
"""

from dataclasses import dataclass, field

from . import config


@dataclass
class RefineResult:
    text: str
    mode: str  # "clean" | "query-filtered" | "unfiltered"
    warnings: list[str] = field(default_factory=list)


def _markdown(html: str, plain: bool = False) -> str:
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

    options = {"body_width": 0}  # never hard-wrap; wrapping corrupts code blocks
    if plain:
        options.update({"ignore_links": True, "ignore_images": True})

    generator = DefaultMarkdownGenerator(options=options)
    result = generator.generate_markdown(
        input_html=html, citations=config.MARKDOWN_CITATIONS
    )
    return result.raw_markdown.strip()


def _prune(html: str) -> str:
    from crawl4ai.content_filter_strategy import PruningContentFilter

    chunks = PruningContentFilter(
        threshold=config.PRUNE_THRESHOLD,
        min_word_threshold=config.PRUNE_MIN_WORD_THRESHOLD,
    ).filter_content(html)
    return "\n".join(chunks)


def _bm25(html: str, query: str) -> str:
    from crawl4ai.content_filter_strategy import BM25ContentFilter

    chunks = BM25ContentFilter(
        user_query=query, bm25_threshold=config.BM25_THRESHOLD
    ).filter_content(html)
    return "\n".join(chunks)


def refine(
    html: str,
    query: str | None = None,
    no_filter: bool = False,
    fmt: str = "markdown",
) -> RefineResult:
    """Turn fetched HTML into what Claude should actually read."""
    warnings: list[str] = []

    if no_filter:
        body = _markdown(html, plain=(fmt == "text")) if fmt != "html" else html
        return RefineResult(text=body, mode="unfiltered", warnings=warnings)

    pruned_html = _prune(html)
    if not pruned_html.strip():
        # Pruning removed everything. Usually a page that is genuinely almost
        # all chrome, or one whose markup defeats the density heuristic. Raw is
        # noisy but honest; silently returning nothing is not.
        warnings.append("content pruning removed everything; falling back to unfiltered page")
        body = _markdown(html, plain=(fmt == "text")) if fmt != "html" else html
        return RefineResult(text=body, mode="unfiltered", warnings=warnings)

    if not query:
        body = pruned_html if fmt == "html" else _markdown(pruned_html, plain=(fmt == "text"))
        return RefineResult(text=body, mode="clean", warnings=warnings)

    fit_html = _bm25(pruned_html, query)
    fit_body = fit_html if fmt == "html" else _markdown(fit_html, plain=(fmt == "text"))
    clean_body = pruned_html if fmt == "html" else _markdown(pruned_html, plain=(fmt == "text"))

    fit_length = len(fit_body.strip())

    if fit_length < config.MIN_FIT_CHARS:
        # The collapse guard. See config.MIN_FIT_CHARS for why this is an
        # absolute floor rather than a ratio.
        warnings.append(
            f"--query filtering collapsed to {fit_length} chars "
            f"(BM25 is lexical: the page may word this topic differently); "
            f"falling back to clean markdown"
        )
        return RefineResult(text=clean_body, mode="clean", warnings=warnings)

    clean_length = max(len(clean_body.strip()), 1)
    if fit_length < config.LOW_YIELD_RATIO * clean_length:
        warnings.append(
            f"--query kept only {fit_length} of {clean_length} chars "
            f"({fit_length / clean_length:.0%}); if the result reads off-topic the page "
            f"probably does not discuss this query -- re-run without --query to confirm"
        )

    return RefineResult(text=fit_body, mode="query-filtered", warnings=warnings)
