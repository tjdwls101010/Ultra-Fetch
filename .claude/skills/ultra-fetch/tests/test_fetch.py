"""The fetch command's orchestration, especially the second-chance escalation."""

from types import SimpleNamespace

from ultra_fetch import access, fetch as fetch_command
from ultra_fetch.access import FetchResult

SHELL = "<html><body><nav>" + ("Menu Home Login Search Subscribe " * 60) + "</nav></body></html>"
RENDERED = (
    "<html><body><article><h1>The real headline</h1><p>"
    + ("The article body that only appears once JavaScript has run. " * 40)
    + "</p></article></body></html>"
)
STATIC = (
    "<html><body><article><p>"
    + ("Server-rendered prose that the fast tier already returned in full. " * 40)
    + "</p></article></body></html>"
)


def _args(**over):
    base = dict(
        url="https://example.com", output=None, query=None, fast=False, stealth=False,
        timeout=30, format="markdown", no_filter=False, wait_selector=None,
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_js_rendered_article_escalates_after_refining(monkeypatch, tmp_path):
    # The gap this closes: a client-side-rendered article still ships a full
    # navigation shell, so the raw page looks thick enough to pass access.py's
    # check while containing no article at all. Only refining reveals it.
    monkeypatch.setattr(access, "_fetch_fast", lambda *a, **k: FetchResult(SHELL, "fast", 200))
    monkeypatch.setattr(access, "_fetch_stealth", lambda *a, **k: FetchResult(RENDERED, "stealth", 200))

    out = tmp_path / "page.md"
    assert fetch_command.run(_args(output=str(out))) == 0
    assert "real headline" in out.read_text(encoding="utf-8").lower()


def test_a_healthy_static_page_does_not_pay_for_a_browser(monkeypatch, tmp_path):
    def _never(*a, **k):
        raise AssertionError("must not escalate: the fast tier already had the article")

    monkeypatch.setattr(access, "_fetch_fast", lambda *a, **k: FetchResult(STATIC, "fast", 200))
    monkeypatch.setattr(access, "_fetch_stealth", _never)

    out = tmp_path / "page.md"
    assert fetch_command.run(_args(output=str(out))) == 0
    assert "Server-rendered prose" in out.read_text(encoding="utf-8")


def test_escalation_keeps_the_fast_result_when_the_browser_adds_nothing(monkeypatch, tmp_path):
    # A genuinely tiny page (example.com is 142 chars and blocked by nobody)
    # must not end up worse off for having been retried.
    tiny = "<html><body><h1>Example Domain</h1><p>Short but real.</p></body></html>"
    monkeypatch.setattr(access, "_fetch_fast", lambda *a, **k: FetchResult(tiny, "fast", 200))
    monkeypatch.setattr(access, "_fetch_stealth", lambda *a, **k: FetchResult("<html><body></body></html>", "stealth", 200))

    out = tmp_path / "page.md"
    assert fetch_command.run(_args(output=str(out))) == 0
    assert "Example Domain" in out.read_text(encoding="utf-8")
