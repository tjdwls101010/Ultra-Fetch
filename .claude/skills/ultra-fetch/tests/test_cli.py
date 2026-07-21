"""The CLI contract: parsing, the catalog, and the output-path rules.

The catalog tests matter more than they look. SKILL.md deliberately does not
restate flags -- it tells Claude to run `catalog` instead -- so if the catalog
stops describing a command accurately, the skill's advice silently rots with it.
"""

from pathlib import Path

from ultra_fetch.cli import build_catalog, build_parser, main
from ultra_fetch.errors import EXIT_CODE_MEANINGS
from ultra_fetch.output import resolve_output_path


def test_every_command_is_in_the_catalog():
    catalog = build_catalog()
    assert set(catalog["commands"]) == {"fetch", "crawl", "map", "setup", "catalog"}


def test_catalog_documents_every_exit_code_the_code_can_return():
    catalog = build_catalog()
    assert set(catalog["exit_codes"]) == {str(c) for c in EXIT_CODE_MEANINGS}


def test_catalog_reflects_real_defaults_rather_than_prose():
    options = {tuple(o["flags"]): o for o in build_catalog()["commands"]["crawl"]["options"]}
    assert options[("--max-pages",)]["default"] == 25
    assert options[("--max-depth",)]["default"] == 2


def test_catalog_states_the_output_contract():
    contract = build_catalog()["output_contract"]
    assert "Never parse stdout" in contract["stdout"]
    assert set(contract["artifact"]) == {"fetch", "crawl", "map"}


def test_fast_and_stealth_are_mutually_exclusive():
    assert main(["fetch", "https://example.com", "--fast", "--stealth"]) == 1


def test_no_command_is_a_usage_error():
    assert main([]) == 1


def test_crawl_defaults_are_bounded():
    # An unbounded crawl is the one runaway this tool must never allow by
    # default, whatever else changes.
    args = build_parser().parse_args(["crawl", "https://example.com"])
    assert args.max_pages > 0
    assert args.max_depth > 0


def test_include_and_exclude_are_repeatable():
    args = build_parser().parse_args(
        ["crawl", "https://example.com", "--include", "*/blog/*", "--include", "*/docs/*"]
    )
    assert args.include == ["*/blog/*", "*/docs/*"]


def test_explicit_output_path_wins():
    assert resolve_output_path("/tmp/mine.md", "https://example.com", ".md") == Path("/tmp/mine.md")


def test_default_output_path_is_predictable_and_derived_from_the_url():
    first = resolve_output_path(None, "https://example.com/blog/post", ".md")
    second = resolve_output_path(None, "https://example.com/blog/post", ".md")
    assert first == second, "a re-run must overwrite its own artifact, not litter temp"
    assert "example-com" in first.name
    assert first.suffix == ".md"


def test_non_ascii_urls_produce_a_usable_filename():
    # Korean sites are in scope; a slug that collapses to nothing would make
    # every such page collide on one filename.
    path = resolve_output_path(None, "https://slownews.kr/기사", ".md")
    assert path.name.endswith(".md")
    assert "slownews-kr" in path.name
