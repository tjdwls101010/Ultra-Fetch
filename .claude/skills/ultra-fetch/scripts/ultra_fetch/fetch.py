"""The `fetch` command: one URL -> one clean markdown file.

Orchestration only -- access.py decides how to reach the page, refine.py decides
what is worth keeping, output.py decides where it lands. This module's whole job
is to sequence them and report honestly on what happened.
"""

from . import config, output
from .access import fetch_html
from .errors import EXIT_OK, AccessError, EmptyContentError
from .refine import refine

SUFFIXES = {"markdown": ".md", "text": ".txt", "html": ".html"}


def run(args) -> int:
    mode = "auto"
    if args.fast:
        mode = "fast"
    elif args.stealth:
        mode = "stealth"

    result = fetch_html(
        args.url, mode=mode, timeout=args.timeout, wait_selector=args.wait_selector
    )

    def _refine(html):
        return refine(html, query=args.query, no_filter=args.no_filter, fmt=args.format)

    refined = _refine(result.html)

    # Second-chance escalation, judged on the refined text rather than the raw
    # page. access.py can only see how much text arrived, and a JS-rendered
    # article arrives wrapped in enough navigation to look healthy; only after
    # refining is it clear that almost none of it was content. See
    # config.MIN_ARTICLE_CHARS.
    # Two shapes of "we fetched a shell": refining left almost nothing, or
    # refining found no article at all and fell back to the whole page. The
    # second must be checked separately, because that fallback re-inflates the
    # output with the very navigation that hid the problem -- so a size check
    # alone would see a healthy-looking result and never fire.
    refined_len = len(refined.text.strip())
    raw_len = len(result.html)
    looks_shell = (
        refined_len < config.SHELL_MAX_CHARS
        and raw_len > 0
        and refined_len / raw_len < config.SHELL_MAX_RATIO
    )
    looks_empty = (
        refined_len < config.MIN_ARTICLE_CHARS
        or looks_shell
        or (refined.pruning_collapsed and not args.no_filter)
    )

    if mode == "auto" and result.tier == "fast" and looks_empty:
        try:
            retried = fetch_html(
                args.url, mode="stealth", timeout=args.timeout, wait_selector=args.wait_selector
            )
        except AccessError:
            # The retry is opportunistic: we already hold a response the host
            # served willingly. If the browser cannot repeat it -- a 204 has no
            # document to navigate to, for instance -- that says nothing about
            # reachability, so keep what we have and let the empty-content path
            # report it. Propagating here would relabel a reachable-but-empty
            # page as unreachable and send the caller after a nonexistent wall.
            retried = None
        retried_refined = _refine(retried.html) if retried else refined
        # Prefer the retry only if it actually found an article. Comparing raw
        # length would let a browser-rendered navigation shell beat a small but
        # genuine article, so compare on whether refining succeeded first.
        better = (not retried_refined.pruning_collapsed and refined.pruning_collapsed) or (
            retried_refined.pruning_collapsed == refined.pruning_collapsed
            and len(retried_refined.text.strip()) > len(refined.text.strip())
        )
        if retried and better:
            result, refined = retried, retried_refined
            result.escalated_because = (
                "fast tier refined to almost nothing (content is rendered client-side)"
            )

    if result.selector_missing:
        output.warn(
            f"--wait-selector {result.selector_missing!r} never matched; the page was "
            f"captured after the wait timed out, so the content you were waiting for is "
            f"probably not in this result. Check the selector against the live page."
        )

    for message in refined.warnings:
        output.warn(message)

    if not refined.text.strip():
        raise EmptyContentError(
            f"{args.url} produced no usable content (fetched via {result.tier} tier)",
            hint="Try --no-filter, or --wait-selector if the page renders late.",
        )

    path = output.resolve_output_path(args.output, args.url, SUFFIXES[args.format])
    chars = output.write_text(path, refined.text)

    escalation = f" (escalated: {result.escalated_because})" if result.escalated_because else ""
    output.summarize(
        f"fetched {args.url} via {result.tier}{escalation}, "
        f"{chars:,} chars ({refined.mode}), saved to {path}"
    )
    return EXIT_OK
