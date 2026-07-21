"""The output contract: results go to a file, one summary line goes to stderr.

Nothing substantive is ever printed to stdout. This is the deliberate inversion
of how a normal CLI behaves, and it exists because the caller is a language
model with a finite context window: printing a 200 KB page to stdout would force
all of it into context, whereas writing it to a file lets Claude decide how much
to read. The stderr line is the receipt -- enough to know what happened and
whether it is worth reading, and nothing more.
"""

import json
import logging
import os
import sys
from pathlib import Path

from . import config


def silence_library_logging() -> None:
    """Keep scrapling and crawl4ai from writing to our stderr.

    Both libraries log chattily by default -- scrapling prints an INFO line per
    request, and logs a bare "No Cloudflare challenge found." at ERROR level on
    every stealth fetch of a site that simply isn't behind Cloudflare, which
    reads as a failure when nothing failed. That noise would break the one-line
    stderr contract this module exists to enforce, and a model reading a spurious
    ERROR reasonably concludes the fetch went wrong.

    We surface real failures ourselves, as typed exceptions with exit codes, so
    nothing diagnostic is lost. Set ULTRA_FETCH_DEBUG=1 to get the raw chatter
    back when debugging the libraries themselves.

    MUST be called *after* the library is imported, not before. scrapling sets a
    level on its own logger at import time, so a call made earlier -- for
    instance once at CLI startup, which is the obvious place -- is silently
    overwritten by the import and the chatter comes back. Calling it repeatedly
    is cheap and idempotent, so every import site calls it again.
    """
    if os.environ.get("ULTRA_FETCH_DEBUG"):
        return
    for name in ("scrapling", "crawl4ai"):
        logger = logging.getLogger(name)
        logger.setLevel(logging.CRITICAL)
        logger.propagate = False


def resolve_output_path(explicit: str | None, url: str, suffix: str) -> Path:
    """Pick where the artifact goes. Explicit wins; otherwise a predictable temp path."""
    if explicit:
        return Path(explicit).expanduser()

    from urllib.parse import urlparse

    parsed = urlparse(url)
    stem = config.slugify(f"{parsed.netloc}{parsed.path}")
    return config.DEFAULT_OUTPUT_DIR / f"{stem}{suffix}"


def write_text(path: Path, text: str) -> int:
    """Write UTF-8 text, creating parents. Returns the character count."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return len(text)


def write_json(path: Path, data) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    # ensure_ascii=False so Korean page titles stay readable in the manifest
    # rather than becoming \uXXXX escapes.
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    path.write_text(payload, encoding="utf-8")
    return len(payload)


def warn(message: str) -> None:
    print(f"ultra-fetch: warning: {message}", file=sys.stderr)


def summarize(message: str) -> None:
    print(message, file=sys.stderr)


def error(message: str, hint: str | None = None) -> None:
    print(f"ultra-fetch: error: {message}", file=sys.stderr)
    if hint:
        print(f"ultra-fetch: hint: {hint}", file=sys.stderr)
