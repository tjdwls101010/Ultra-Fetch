"""The access layer: get the bytes, however hard that turns out to be.

scrapling owns this and crawl4ai never fetches here. The division matters: it
means a `fetch` makes exactly one network round-trip, and the refine step
operates on an HTML string that is already in hand.

The tier ladder is the whole point of the module. The fast tier is curl_cffi
with a real-Chrome TLS fingerprint -- no browser process, so it returns in
well under a second and handles the large majority of the public web. The
stealth tier is Patchright (a de-fingerprinted Playwright) and costs seconds
plus hundreds of MB of resident browser, but solves Cloudflare. Starting fast
and escalating only on evidence gives the common case its speed without making
Claude choose a tier it has no way to choose correctly in advance.
"""

from dataclasses import dataclass

from . import config
from .errors import AccessError
from .output import silence_library_logging


@dataclass
class FetchResult:
    html: str
    tier: str  # "fast" | "stealth"
    status: int
    escalated_because: str | None = None
    # Set to the selector when --wait-selector was given and never matched, so
    # the caller can be told the thing it waited for never appeared.
    selector_missing: str | None = None


def _visible_text(html: str) -> str:
    """Rough text extraction, only good enough to judge 'is there a page here'."""
    import re

    without_code = re.sub(
        r"<(script|style|noscript)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I
    )
    return re.sub(r"<[^>]+>", " ", without_code)


@dataclass
class Diagnosis:
    """Why a response looks wrong, and how sure we are.

    The hard/soft split is load-bearing. A *hard* signal (a bot-wall status, a
    Cloudflare interstitial) is positive evidence that we were refused -- if it
    survives the stealth tier the page is genuinely unreachable. A *soft* signal
    is merely suspicious: a thin body might be a JS shell that needs a browser,
    but it might equally be a page that is honestly just short. Treating soft
    evidence as terminal is how a working fetch gets reported as a failure --
    example.com has 142 characters of text and is not blocked by anyone.
    """

    reason: str
    hard: bool


def diagnose(status: int, html: str) -> Diagnosis | None:
    """Return why this response should be escalated, or None if it looks real.

    Kept pure and separate from the fetching so it can be unit-tested against
    captured block pages without touching the network -- the escalation decision
    is the part of this module most likely to need tuning as sites change.
    """
    if status in config.BLOCK_STATUSES:
        return Diagnosis(f"HTTP {status}", hard=True)

    text = " ".join(_visible_text(html).split())
    lowered = text.lower()
    for marker in config.BLOCK_MARKERS:
        if marker in lowered:
            return Diagnosis(f"challenge page detected ({marker!r})", hard=True)

    if len(text) < config.MIN_TEXT_CHARS:
        # A 404 is a true answer, not a wall: escalating it burns a browser
        # fetch to re-confirm the page still doesn't exist.
        if status == 404:
            return None
        return Diagnosis(
            f"only {len(text)} chars of text (JS-rendered, or just a short page)",
            hard=False,
        )

    return None


def _fetch_fast(url: str, timeout: int) -> FetchResult:
    from scrapling.fetchers import Fetcher

    silence_library_logging()  # after the import -- see the note in output.py

    try:
        response = Fetcher.get(
            url,
            timeout=timeout,
            stealthy_headers=True,  # real browser headers + a Google referer
            retries=2,
        )
    except Exception as exc:  # network-level failure, DNS, TLS, timeout
        raise AccessError(
            f"fast fetch of {url} failed: {exc}",
            hint="The host may be down or refusing non-browser clients; "
            "a --stealth retry is worth one attempt.",
        ) from exc

    return FetchResult(html=str(response.html_content), tier="fast", status=response.status)


def _stealth_fetcher():
    """Import seam: keeps the browser import lazy and lets tests substitute it."""
    from scrapling.fetchers import StealthyFetcher

    silence_library_logging()  # after the import -- see the note in output.py
    return StealthyFetcher


def _fetch_stealth(
    url: str, timeout: int, wait_selector: str | None, solve_cloudflare: bool
) -> FetchResult:
    fetcher = _stealth_fetcher()

    # scrapling's browser fetchers take milliseconds while its HTTP fetcher takes
    # seconds. Our CLI is seconds-everywhere (one unit for Claude to reason
    # about), so the conversion happens here, at the boundary, exactly once.
    effective = max(timeout, config.CLOUDFLARE_MIN_TIMEOUT) if solve_cloudflare else timeout
    timeout_ms = effective * 1000

    kwargs = {
        "headless": True,
        "network_idle": True,
        "timeout": timeout_ms,
        "solve_cloudflare": solve_cloudflare,
        "block_ads": True,
        # allow_webgl stays at its default True: WAFs actively check for a
        # missing WebGL context, so disabling it makes us *more* detectable.
    }
    if wait_selector:
        kwargs["wait_selector"] = wait_selector

    try:
        response = fetcher.fetch(url, **kwargs)
    except Exception as exc:
        raise AccessError(
            f"stealth fetch of {url} failed: {exc}",
            hint="If this is a timeout on a Cloudflare-protected site, raise --timeout "
            "(solving needs >=60s). Otherwise the site likely uses an anti-bot vendor "
            "scrapling does not document support for.",
        ) from exc

    result = FetchResult(html=str(response.html_content), tier="stealth", status=response.status)

    # Waiting for a selector that never arrives is not an error to the fetcher:
    # it waits out the timeout and hands back whatever the page had. Silently
    # succeeding is the wrong answer, because the caller asked to wait for
    # something specific -- they believe that content is in the result. Say so,
    # rather than letting a page missing the very thing that was waited for pass
    # as a normal fetch.
    if wait_selector:
        try:
            matched = len(response.css(wait_selector))
        except Exception:
            matched = None  # an invalid selector expression; not worth failing over
        if matched == 0:
            result.selector_missing = wait_selector

    return result


def fetch_html(
    url: str,
    mode: str = "auto",
    timeout: int = config.DEFAULT_TIMEOUT,
    wait_selector: str | None = None,
) -> FetchResult:
    """Fetch `url`, escalating fast -> stealth when the fast tier looks blocked.

    mode: "auto" (escalate on evidence), "fast" (never open a browser),
    "stealth" (skip straight to the browser).
    """
    if mode == "stealth":
        return _fetch_stealth(url, timeout, wait_selector, solve_cloudflare=True)

    if wait_selector and mode == "fast":
        raise AccessError(
            "--wait-selector needs a browser tier but --fast forbids one",
            hint="Drop --fast, or drop --wait-selector.",
        )

    try:
        fast = _fetch_fast(url, timeout)
    except AccessError:
        if mode == "fast":
            raise
        # Some walls refuse at the transport level rather than returning a block
        # page -- curl_cffi gets a TLS or connection reset where a real browser
        # completes the handshake. Auto mode promises to escalate on evidence,
        # and a refused connection is evidence; failing here would hand back
        # "unreachable" for a site the browser tier can actually open.
        return _fetch_stealth(url, timeout, wait_selector, solve_cloudflare=True)

    finding = diagnose(fast.status, fast.html)

    if mode == "fast":
        # The user forbade a browser, so only a hard wall is worth failing on.
        # A thin page still gets returned -- it may be all there is, and the
        # caller explicitly opted out of the tier that could tell us otherwise.
        if finding and finding.hard:
            raise AccessError(
                f"fast tier could not retrieve {url}: {finding.reason}",
                hint="Re-run without --fast to allow the stealth browser tier.",
            )
        return fast

    if finding is None:
        return fast

    # Always solve Cloudflare on the escalation path, even when the evidence was
    # only a thin body. Cloudflare's interstitial does not always announce
    # itself: a challenge can arrive as a near-empty shell with no marker and a
    # 200 status, which reads as "soft" here. Gating the solve on hard evidence
    # therefore skips it on exactly the pages this tool exists to reach --
    # measured on nowsecure.nl, which returns 56 chars and needs the solve. The
    # cost when there is no challenge is a few seconds on a path that only runs
    # because something already looked wrong.
    stealth = _fetch_stealth(url, timeout, wait_selector, solve_cloudflare=True)
    stealth.escalated_because = finding.reason

    after = diagnose(stealth.status, stealth.html)
    if after and after.hard:
        raise AccessError(
            f"{url} unreachable: fast tier {finding.reason}; stealth tier {after.reason}",
            hint="scrapling documents Cloudflare bypass only -- DataDome, Akamai, "
            "PerimeterX and Kasada are undocumented. Treat this site as blocked.",
        )

    if finding.hard:
        # The fast response was a wall, so it is not a candidate no matter how
        # many bytes it had -- a Cloudflare interstitial is often *larger* than
        # the real page behind it. Measured: a 403 challenge at 5,950 bytes vs
        # the solved page at 4,060. Choosing on size here returned the block
        # page and reported it as a successful fast fetch.
        return stealth

    # Both tiers came back merely thin, which is now evidence the page really is
    # short rather than evidence of a wall. Hand back whichever has more to it;
    # refine.py decides whether it amounts to anything usable (exit 4).
    if after and len(stealth.html) < len(fast.html):
        return fast
    return stealth
