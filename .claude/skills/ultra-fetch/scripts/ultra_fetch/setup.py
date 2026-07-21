"""Provision, repair, upgrade and diagnose the dedicated venv.

Two browser stacks is the real cost of using both libraries: scrapling installs
Patchright's Chromium via `scrapling install`, crawl4ai installs Playwright's via
`crawl4ai-setup`. They land in separate caches and coexist fine, but together
they are the "one-time large download" the launcher warns about. Everything here
is idempotent -- re-running is how you repair a half-finished install.

This module is named setup.py but is a plain module inside the package, not a
setuptools build script. Nothing here is ever executed by pip.
"""

import shutil
import subprocess
import sys
from pathlib import Path

from . import config, output
from .errors import EXIT_OK, SetupError

REQUIREMENTS = Path(__file__).resolve().parent.parent / "requirements.txt"


def _run(command: list[str], description: str) -> subprocess.CompletedProcess:
    output.summarize(f"ultra-fetch setup: {description}...")
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "").strip().splitlines()[-5:]
        raise SetupError(
            f"{description} failed (exit {result.returncode})",
            hint="\n".join(tail) if tail else None,
        )
    return result


def _venv_python() -> Path:
    return config.VENV_DIR / "bin" / "python"


def ensure_venv(upgrade: bool = False) -> None:
    """Create the venv if absent and install pinned dependencies into it."""
    uv = shutil.which("uv")

    if not _venv_python().exists():
        config.VENV_DIR.parent.mkdir(parents=True, exist_ok=True)
        if uv:
            _run([uv, "venv", str(config.VENV_DIR), "--python", "3.12"], "creating venv (uv)")
        else:
            _run([sys.executable, "-m", "venv", str(config.VENV_DIR)], "creating venv")

    if upgrade:
        # D12's manual freshness path: bump both libraries, then re-pin so the
        # versions that were actually proven to work together are recorded.
        packages = ["scrapling[fetchers]", "crawl4ai"]
        if uv:
            _run([uv, "pip", "install", "--python", str(_venv_python()), "--upgrade", *packages],
                 "upgrading scrapling and crawl4ai")
        else:
            _run([str(_venv_python()), "-m", "pip", "install", "--upgrade", *packages],
                 "upgrading scrapling and crawl4ai")
        _repin()
        return

    if uv:
        _run([uv, "pip", "install", "--python", str(_venv_python()), "-r", str(REQUIREMENTS)],
             "installing pinned dependencies (uv)")
    else:
        _run([str(_venv_python()), "-m", "pip", "install", "-r", str(REQUIREMENTS)],
             "installing pinned dependencies")


def _repin() -> None:
    """Rewrite requirements.txt with the versions now actually installed."""
    result = subprocess.run(
        [str(_venv_python()), "-c",
         "import scrapling, crawl4ai.__version__ as v; print(scrapling.__version__); print(v.__version__)"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise SetupError("could not read installed versions after upgrade", hint=result.stderr.strip())

    scrapling_version, crawl4ai_version = result.stdout.split()
    REQUIREMENTS.write_text(
        "# Pinned deliberately (D12): dependencies are upgraded manually via\n"
        "# `ultra-fetch setup --upgrade`, which re-pins this file to whatever it\n"
        "# just proved installable together. Both libraries are Playwright-family\n"
        "# and share one venv, so unpinned drift is how they start conflicting.\n"
        f"scrapling[fetchers]=={scrapling_version}\n"
        f"crawl4ai=={crawl4ai_version}\n",
        encoding="utf-8",
    )
    output.summarize(
        f"ultra-fetch setup: re-pinned scrapling=={scrapling_version}, crawl4ai=={crawl4ai_version}"
    )


def install_browsers() -> None:
    bin_dir = config.VENV_DIR / "bin"
    output.summarize(
        "ultra-fetch setup: installing browser engines -- this is a one-time download "
        "of several hundred MB (Patchright + Playwright Chromium)."
    )
    _run([str(bin_dir / "scrapling"), "install"], "scrapling install")
    _run([str(bin_dir / "crawl4ai-setup")], "crawl4ai-setup")


def doctor() -> None:
    bin_dir = config.VENV_DIR / "bin"

    result = subprocess.run([str(bin_dir / "crawl4ai-doctor")], capture_output=True, text=True)
    output.summarize(f"ultra-fetch doctor: crawl4ai-doctor exit {result.returncode}")

    smoke = subprocess.run(
        [str(_venv_python()), "-c",
         "from scrapling.fetchers import Fetcher;"
         "r = Fetcher.get('https://example.com', timeout=20);"
         "print('scrapling ok' if r.status == 200 else f'scrapling status {r.status}')"],
        capture_output=True, text=True,
    )
    verdict = smoke.stdout.strip() or (smoke.stderr.strip().splitlines() or ["failed"])[-1]
    output.summarize(f"ultra-fetch doctor: {verdict}")

    from crawl4ai.content_filter_strategy import PruningContentFilter

    chunks = PruningContentFilter().filter_content(
        "<html><body><article><p>" + ("refine round trip " * 30) + "</p></article></body></html>"
    )
    output.summarize(
        f"ultra-fetch doctor: refine round-trip {'ok' if chunks else 'FAILED'} ({len(chunks)} chunks)"
    )


def run(args) -> int:
    # Bare `setup` still provisions -- the useful default for "it is broken,
    # fix it" is to repair everything, not to print usage.
    do_everything = not (args.browsers or args.upgrade or args.doctor)

    if do_everything or args.upgrade:
        ensure_venv(upgrade=args.upgrade)
    else:
        ensure_venv()

    if do_everything or args.browsers:
        install_browsers()

    if args.doctor:
        doctor()

    output.summarize(f"ultra-fetch setup: ready ({config.VENV_DIR})")
    return EXIT_OK
