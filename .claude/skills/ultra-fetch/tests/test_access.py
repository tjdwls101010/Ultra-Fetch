"""The escalation decision -- the part most likely to need retuning as sites change.

Every case here is a real failure shape, not a hypothetical: the short-page case
is example.com, which an earlier version of `diagnose` wrongly reported as
unreachable after successfully fetching it.
"""

import pytest

from ultra_fetch import access
from ultra_fetch.access import FetchResult, diagnose
from ultra_fetch.errors import AccessError

ARTICLE = "<html><body><article><p>" + ("real sentences about a topic " * 40) + "</p></article></body></html>"


def test_healthy_page_is_not_escalated():
    assert diagnose(200, ARTICLE) is None


def test_bot_wall_status_is_a_hard_signal():
    finding = diagnose(403, ARTICLE)
    assert finding is not None and finding.hard
    assert "403" in finding.reason


def test_cloudflare_interstitial_is_hard_even_with_status_200():
    # The trap: a challenge page returns 200, so status alone never catches it.
    html = "<html><body><h1>Just a moment...</h1><p>Checking your browser</p></body></html>"
    finding = diagnose(200, html)
    assert finding is not None and finding.hard


def test_thin_page_is_only_a_soft_signal():
    # example.com is genuinely ~142 chars and blocked by nobody. Escalating is
    # fine; declaring it unreachable is not, so this must never be hard.
    html = "<html><body><h1>Example Domain</h1><p>This domain is for examples.</p></body></html>"
    finding = diagnose(200, html)
    assert finding is not None
    assert not finding.hard


def test_short_404_does_not_escalate():
    # A 404 is a true answer. Escalating burns a browser fetch to re-confirm
    # that a page still does not exist.
    assert diagnose(404, "<html><body><h1>Not Found</h1></body></html>") is None


def _stub_tiers(monkeypatch, fast: FetchResult, stealth: FetchResult | None):
    monkeypatch.setattr(access, "_fetch_fast", lambda *a, **k: fast)

    def _stealth(*a, **k):
        if stealth is None:
            raise AssertionError("should not have escalated")
        return stealth

    monkeypatch.setattr(access, "_fetch_stealth", _stealth)


def test_a_blocked_fast_tier_never_wins_on_size(monkeypatch):
    # The regression that shipped a Cloudflare block page as a successful fetch:
    # the 403 interstitial (5,950 bytes) was *larger* than the solved page
    # (4,060 bytes), so choosing by size returned the wall. A hard-blocked
    # response is not a candidate at any size.
    challenge = FetchResult(html="<html>" + "x" * 5900 + "</html>", tier="fast", status=403)
    solved = FetchResult(
        html="<html><body><p>You bypassed the challenge</p></body></html>", tier="stealth", status=200
    )
    _stub_tiers(monkeypatch, challenge, solved)

    result = access.fetch_html("https://example.com", mode="auto")
    assert result.tier == "stealth"
    assert "bypassed" in result.html
    assert result.escalated_because == "HTTP 403"


def test_both_tiers_walled_is_terminal(monkeypatch):
    wall = FetchResult(html="<html><body>Just a moment...</body></html>", tier="fast", status=403)
    _stub_tiers(monkeypatch, wall, FetchResult(html=wall.html, tier="stealth", status=403))

    with pytest.raises(AccessError) as caught:
        access.fetch_html("https://example.com", mode="auto")
    assert caught.value.exit_code == 3


def test_a_refused_connection_still_escalates(monkeypatch):
    # Some walls reject at the transport level instead of serving a block page.
    # Giving up here would report a site as unreachable that the browser opens.
    def _boom(*a, **k):
        raise AccessError("connection reset")

    monkeypatch.setattr(access, "_fetch_fast", _boom)
    monkeypatch.setattr(
        access, "_fetch_stealth",
        lambda *a, **k: FetchResult(html=ARTICLE, tier="stealth", status=200),
    )
    assert access.fetch_html("https://example.com", mode="auto").tier == "stealth"


def test_fast_mode_does_not_escalate_a_refused_connection(monkeypatch):
    def _boom(*a, **k):
        raise AccessError("connection reset")

    monkeypatch.setattr(access, "_fetch_fast", _boom)
    monkeypatch.setattr(access, "_fetch_stealth", lambda *a, **k: pytest.fail("--fast must not open a browser"))
    with pytest.raises(AccessError):
        access.fetch_html("https://example.com", mode="fast")


def test_a_healthy_fast_response_never_opens_a_browser(monkeypatch):
    _stub_tiers(monkeypatch, FetchResult(html=ARTICLE, tier="fast", status=200), None)
    assert access.fetch_html("https://example.com", mode="auto").tier == "fast"


def test_thin_page_keeps_the_richer_of_the_two_tiers(monkeypatch):
    # Neither tier is walled -- the page is simply small. Escalating is fine,
    # but the result must be content, not a failure.
    thin_fast = FetchResult(html="<html><body><p>Short but real page.</p></body></html>", tier="fast", status=200)
    thinner_stealth = FetchResult(html="<html><body></body></html>", tier="stealth", status=200)
    _stub_tiers(monkeypatch, thin_fast, thinner_stealth)

    result = access.fetch_html("https://example.com", mode="auto")
    assert "Short but real page" in result.html


def test_script_content_does_not_count_as_text():
    # A JS shell whose bulk is inline script must still read as thin, otherwise
    # a single-page app looks like a full page and never escalates.
    html = "<html><body><div id=root></div><script>" + ("var x = 1; " * 500) + "</script></body></html>"
    finding = diagnose(200, html)
    assert finding is not None and not finding.hard
