"""Exit-code contract and the exceptions that map onto it.

Every failure mode Claude needs to react to differently gets its own exit code.
The codes are part of the CLI's public contract -- `catalog` prints them, SKILL.md
tells Claude what to *do* per code -- so treat them as stable. Adding a code is
cheap; changing what an existing one means silently breaks the skill's advice.
"""


class UltraFetchError(Exception):
    """Base for every failure that maps to a non-zero exit code."""

    exit_code = 1

    def __init__(self, message: str, hint: str | None = None):
        super().__init__(message)
        self.hint = hint


class UsageError(UltraFetchError):
    """Bad arguments. The invocation is wrong, not the world."""

    exit_code = 1


class SetupError(UltraFetchError):
    """The venv or the browsers are missing and auto-setup could not fix it."""

    exit_code = 2


class AccessError(UltraFetchError):
    """The page is unreachable even after escalating to the stealth tier.

    This is a terminal verdict, not a transient hiccup: scrapling's documented
    anti-bot coverage is Cloudflare, so a site behind DataDome/Akamai/PerimeterX
    fails here every time. Retrying the same URL is wasted work -- which is why
    this gets its own code instead of being folded into a generic failure.
    """

    exit_code = 3


class EmptyContentError(UltraFetchError):
    """The page was reached but yielded no usable text.

    Usually a JS-gated page whose content arrives after load (try --wait-selector)
    or a filter that ate everything (try --no-filter).
    """

    exit_code = 4


class NoResultsError(UltraFetchError):
    """A crawl or map completed but found nothing. Honest zero, not an error."""

    exit_code = 5


EXIT_OK = 0
EXIT_PARTIAL = 7  # Success, but a cap stopped us short. Results are incomplete.

EXIT_CODE_MEANINGS = {
    0: "Success. Read the output file.",
    1: "Usage or bad arguments. Fix the invocation.",
    2: "Setup needed: venv or browsers missing and auto-setup failed. "
       "Run `ultra-fetch setup --browsers` (one-time large browser download).",
    3: "Access failed: unreachable even after stealth escalation. The site likely uses a "
       "commercial anti-bot beyond Cloudflare, or is down. Report it; do not retry in a loop.",
    4: "Content empty or the filter collapsed with no usable fallback. Retry without --query, "
       "or with --no-filter; if the page is JS-gated try --wait-selector.",
    5: "Crawl or map produced zero results (empty sitemap, no matching links). "
       "Report honestly; not retryable by rote.",
    7: "Partial result: a cap (--max-pages/--max-depth/--max-urls) stopped the run before "
       "completion. The output is real but incomplete -- say so, and raise the cap only if warranted.",
}
