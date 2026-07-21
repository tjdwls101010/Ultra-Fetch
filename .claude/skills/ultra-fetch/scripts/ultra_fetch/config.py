"""Defaults, paths, and tuning constants.

Every number here carries its reason. A threshold without a rationale is
un-tunable: the next maintainer can't tell a measured value from a guess, so they
either never touch it or change it blindly.
"""

import os
import re
import tempfile
from pathlib import Path

# --- Environment -----------------------------------------------------------

# The dedicated venv lives outside the repo so it survives skill edits, is never
# committed, and gives both browser stacks a fixed home. The bash launcher
# resolves this same path independently -- keep the two in sync.
VENV_DIR = Path(
    os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
) / "ultra-fetch" / "venv"

# Where --output-less runs land. Predictable rather than random so a re-run
# overwrites its own previous artifact instead of littering temp.
DEFAULT_OUTPUT_DIR = Path(tempfile.gettempdir()) / "ultra-fetch"


# --- Access tier (scrapling) ------------------------------------------------

DEFAULT_TIMEOUT = 30  # seconds, fast static tier

# Solving a Cloudflare challenge involves waiting out a JS interstitial that can
# legitimately take most of a minute. scrapling's docs are explicit that the
# timeout must be >= 60s when solve_cloudflare is on; a shorter timeout doesn't
# fail fast, it fails *wrongly* -- aborting a solve that was about to succeed.
CLOUDFLARE_MIN_TIMEOUT = 60

# Below this much text, a 200 response is almost certainly a challenge page, a
# JS shell, or an empty template rather than an article -- the trigger to
# escalate to the browser tier. Set from observed block pages: Cloudflare
# interstitials land around 1-3 KB of HTML but only a few hundred chars of text.
MIN_TEXT_CHARS = 500

# Phrases that mean "you are being challenged", not "here is the page". Matched
# against the visible text of an otherwise-successful response, because a
# challenge page usually returns 200, not 403 -- status alone won't catch it.
BLOCK_MARKERS = (
    "just a moment",
    "checking your browser",
    "enable javascript and cookies to continue",
    "verifying you are human",
    "cf-browser-verification",
    "cf_chl_opt",
    "attention required! | cloudflare",
    "access denied",
    "please turn javascript on",
    "ddos protection by",
    "why have i been blocked",
)

# Statuses that mean "blocked" rather than "genuinely absent". A 404 is a real
# answer and must NOT trigger escalation -- burning a 60s browser fetch on a
# page that truly doesn't exist is the most common way this kind of tool wastes
# a minute. 403/429/503 are the classic bot-wall codes.
BLOCK_STATUSES = (401, 403, 406, 409, 429, 503)


# --- Refine tier (crawl4ai) -------------------------------------------------

# crawl4ai's own default. Higher = more aggressive junk removal. 0.48 keeps
# article bodies while dropping nav/footer/sidebar on most sites.
PRUNE_THRESHOLD = 0.48
PRUNE_MIN_WORD_THRESHOLD = 5

# BM25: higher = fewer, more relevant chunks. 1.0 is crawl4ai's default and is
# already fairly permissive; the collapse guard below is what protects us when
# it turns out to be too strict for a given page.
BM25_THRESHOLD = 1.0

# The collapse guard. BM25 is *lexical* -- if the page words the topic
# differently than the query does, every chunk scores near zero and fit_markdown
# comes back nearly empty. Returning 80 chars of nothing while claiming success
# is the worst outcome, so below this we fall back to the pruned markdown and
# say so on stderr. Deliberately an absolute floor, not a ratio: a ratio would
# misfire on exactly the case query-filtering is *for* -- a long page where only
# one short passage is on-topic.
MIN_FIT_CHARS = 200

# A second, softer signal. BM25 has no notion of "none of this is relevant" -- it
# ranks chunks and returns the best scorers even when every score is poor, so a
# query the page never discusses comes back as a few hundred chars of the
# least-bad paragraphs rather than as nothing. That is not a collapse, so it must
# not trigger the fallback (which would destroy the case query-filtering exists
# for: one short on-topic passage inside a long page). It is worth *saying* out
# loud, though, so the caller can judge. Warn, keep the result, decide nothing.
LOW_YIELD_RATIO = 0.10

# html2text emits either inline [text](url) or footnote-style [text][1] plus a
# trailing reference list. Inline keeps each link next to the prose that
# explains it, which is what a reader (human or model) actually needs; the
# footnote list separates them and reads as noise.
MARKDOWN_CITATIONS = False


# --- Crawl ------------------------------------------------------------------

# Runaway guards. These are non-negotiable defaults (D9): crawl4ai's own
# strategies default max_pages to infinity, and depth grows exponentially --
# its docs warn specifically that depth > 3 explodes. A bounded-by-default crawl
# that reports itself as partial beats an unbounded one that eats the machine.
DEFAULT_MAX_PAGES = 25
DEFAULT_MAX_DEPTH = 2
DEFAULT_CRAWL_DELAY = 0.5  # seconds between requests, politeness without crawling at a snail's pace
DEFAULT_PAGE_TIMEOUT = 30  # seconds per page


# --- Map --------------------------------------------------------------------

DEFAULT_MAX_URLS = 500  # A cap that still lets a real sitemap through; --max-urls raises it.


# --- Output -----------------------------------------------------------------

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def slugify(text: str, max_length: int = 48) -> str:
    """A filesystem-safe, human-recognizable stem for an output filename.

    Non-ASCII (Korean URLs and titles are in scope) collapses to hyphens rather
    than being transliterated -- the slug is for humans skimming a directory
    listing, and the manifest carries the authoritative URL.
    """
    slug = _SLUG_STRIP.sub("-", text.lower()).strip("-")
    return slug[:max_length].strip("-") or "page"
