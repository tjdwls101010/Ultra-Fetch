"""Refining, and specifically the guards that keep a filtered result honest."""

from ultra_fetch import config
from ultra_fetch.refine import refine

ARTICLE = (
    "<html><body>"
    "<nav>Home About Contact Login Signup</nav>"
    "<article><h1>Falcon nesting habits</h1>"
    "<p>" + ("Peregrine falcons nest on tall cliff ledges and skyscrapers. " * 30) + "</p>"
    "</article>"
    "<footer>Copyright 2026</footer>"
    "</body></html>"
)

# A page where only some passages are on topic -- the shape `--query` is for.
MIXED = (
    "<html><body><article>"
    + "".join(
        f"<p>Quarterly municipal bond amortization schedules were revised in fiscal note {i}, "
        f"affecting treasury yield curves and debt service coverage ratios substantially.</p>"
        for i in range(9)
    )
    + "".join(
        f"<p>Peregrine falcons nest on tall cliff ledges and skyscraper cornices, returning "
        f"to the same eyrie each breeding season number {i}.</p>"
        for i in range(3)
    )
    + "</article></body></html>"
)


def test_clean_mode_drops_chrome_and_keeps_the_article():
    result = refine(ARTICLE)
    assert result.mode == "clean"
    assert "falcons nest" in result.text.lower()
    assert "login signup" not in result.text.lower()


def test_query_filtering_keeps_the_relevant_passages_of_a_mixed_page():
    result = refine(MIXED, query="falcon nesting cliff ledges")
    assert result.mode == "query-filtered"
    assert "falcon" in result.text.lower()
    assert "municipal bond" not in result.text.lower()
    assert len(result.text) < len(refine(MIXED).text), "filtering should actually cut content"


def test_uniformly_on_topic_page_falls_back_to_the_whole_page():
    # The BM25 trap (see refine.py's module docstring): when every chunk matches
    # the query, no chunk stands out, IDF collapses, and filtering keeps nothing.
    # Returning the whole clean page is correct here -- all of it is on topic.
    result = refine(ARTICLE, query="falcon nesting cliff ledges")
    assert result.mode == "clean"
    assert "falcon" in result.text.lower()


def test_no_filter_keeps_everything_including_chrome():
    result = refine(ARTICLE, no_filter=True)
    assert result.mode == "unfiltered"
    assert "login" in result.text.lower()


def test_collapse_guard_falls_back_rather_than_returning_nothing():
    # BM25 is lexical, so a query sharing no vocabulary with the page can score
    # every chunk to nothing. Returning near-empty text while reporting success
    # is the failure this guard exists to prevent.
    result = refine(ARTICLE, query="quarterly amortization schedules for municipal bonds")
    assert result.mode == "clean", "should fall back, not return a collapsed result"
    assert len(result.text) >= config.MIN_FIT_CHARS
    assert any("collapsed" in w for w in result.warnings)


DOC_PAGE = (
    "<html><body><article>"
    "<p>Skip the download with the <code>--no-shell</code> flag, or set "
    "<code>PLAYWRIGHT_SKIP_BROWSER_GC=1</code> to <strong>disable</strong> it entirely.</p>"
    + "".join(
        f"<p>Filler prose giving the pruner enough body text to retain the blocks above, line {i}.</p>"
        for i in range(12)
    )
    + "</article></body></html>"
)


def test_pruning_keeps_the_text_inside_inline_tags():
    # The defect this guards against is silent: the pruner deleted the text
    # inside every inline tag while leaving the sentence around it intact, so
    # "parameters like `a`, `b`, or `c`" became "parameters like , , or" and
    # read as fine prose. A model then filled the blanks from memory. Flag names
    # and env vars are exactly what a technical page is read for.
    result = refine(DOC_PAGE)
    assert "--no-shell" in result.text
    assert "PLAYWRIGHT_SKIP_BROWSER_GC=1" in result.text
    assert "disable" in result.text


def test_query_filtering_also_keeps_inline_code():
    result = refine(DOC_PAGE, query="skip download flag environment variable")
    assert "--no-shell" in result.text or "PLAYWRIGHT_SKIP_BROWSER_GC=1" in result.text


def test_empty_html_does_not_crash():
    result = refine("<html><body></body></html>")
    assert result.text.strip() == ""


def test_text_format_strips_links():
    html = '<html><body><article><p>' + ("Body text here. " * 30) + '<a href="https://example.com">a link</a></p></article></body></html>'
    result = refine(html, fmt="text")
    assert "https://example.com" not in result.text


def test_html_format_returns_markup():
    result = refine(ARTICLE, fmt="html")
    assert "<" in result.text
