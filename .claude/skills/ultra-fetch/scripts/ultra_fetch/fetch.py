"""The `fetch` command: one URL -> one clean markdown file.

Orchestration only -- access.py decides how to reach the page, refine.py decides
what is worth keeping, output.py decides where it lands. This module's whole job
is to sequence them and report honestly on what happened.
"""

from . import output
from .access import fetch_html
from .errors import EXIT_OK, EmptyContentError
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

    refined = refine(
        result.html, query=args.query, no_filter=args.no_filter, fmt=args.format
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
