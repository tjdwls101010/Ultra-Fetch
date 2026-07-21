"""Ultra Fetch -- a local CLI that reaches, cleans and traverses web pages.

Internal code structure for the ultra-fetch skill. Deliberately not a
distributable package: it is imported only via `python -m ultra_fetch` from the
skill's dedicated venv, so it carries no pyproject.toml and no entry points.
"""

__version__ = "0.1.0"
