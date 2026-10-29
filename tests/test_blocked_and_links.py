"""Blocked collection (found in a real run): fail fast, point to what works, print manual-export links."""
import re
import sys
import types

import pytest
from conftest import SCRIPTS
from gtrends import fetch_playwright as fp
from gtrends import links

sys.path.insert(0, str(SCRIPTS))
import trends_cli


# ---- links ------------------------------------------------------------------------------------
def test_more_than_five_terms_become_several_links():
    terms = ["стрижка", "барбершоп", "перукарня", "барбер", "стрижка київ", "чоловіча стрижка", "дитяча стрижка"]
    items = links.build_links(terms, ["UA"], "today 5-y", ["web", "shopping"])
    assert [i["set"] for i in items] == [1, 1, 2, 2]
    assert items[0]["terms"] == terms[:5] and items[2]["terms"] == terms[5:]
    for i in items:
        assert i["url"].startswith("https://trends.google.com/trends/explore?") and "hl=en" in i["url"]
    assert "gprop=froogle" in items[1]["url"] and "gprop" not in items[0]["url"]


def test_links_validate_their_input():
    with pytest.raises(ValueError):
        links.build_links(["a,b"], ["UA"], "today 5-y", ["web"])
    with pytest.raises(ValueError):
        links.build_links(["a", "b"], ["UA", "PL"], "today 5-y", ["web"])  # several geos need exactly one term
    with pytest.raises(ValueError):
        links.build_links(["a"], ["UA"], "today 5-y&x=1", ["web"])


def test_several_geos_with_one_term_give_one_set():
    items = links.build_links(["standing desk"], ["PL", "DE", "CZ"], "today 5-y", ["web"])
    assert len(items) == 1 and "geo=PL,DE,CZ" in items[0]["url"]


def test_links_markdown_for_a_product():
    items = links.build_links(["air fryer"], ["UA"], "today 5-y", ["web", "shopping"])
    md = links.render_markdown(items, ["UA"], "product")
    assert "Set 1: air fryer" in md and "Google Shopping: <https://trends.google.com/" in md
    assert "import-csv --geo UA --web-timeline" in md and "--shopping-timeline" in md
    assert "--kind service" not in md


def test_links_markdown_for_a_service_and_unimportable_sources():
    items = links.build_links(["yoga"], ["UA"], "today 5-y", ["web", "youtube"])
    md = links.render_markdown(items, ["UA"], "service")
    assert "--kind service" in md and "--shopping-timeline" not in md
    assert "cannot be imported" in md


def test_links_escape_markdown_in_terms():
    items = links.build_links(["[click](http://evil.example)"], ["UA"], "today 5-y", ["web"])
    md = links.render_markdown(items, ["UA"], "product")
    assert "Set 1: \\[click\\]" in md and "## Set 1: [click](" not in md
    assert all(u.startswith("https://trends.google.com/") for u in re.findall(r"<(https?://[^>]+)>", md))


def test_cli_links_prints_and_saves(tmp_path, capsys):
    out = tmp_path / "google-trends-output"
    assert trends_cli.main(["links", "--terms", "a", "b", "c", "d", "e", "f", "--geo", "UA", "--save", "--out", str(out)]) == 0
    text = capsys.readouterr().out
    assert "Set 1:" in text and "Set 2:" in text
    assert (out / "links.md").read_text(encoding="utf-8").startswith("# Google Trends: links for manual export")
    assert (out / ".gitignore").is_file()


def test_cli_links_default_sources_follow_kind(capsys):
    trends_cli.main(["links", "--terms", "yoga", "--kind", "service"])
    out = capsys.readouterr().out
    assert "web search:" in out and "Google Shopping" not in out and "YouTube" not in out
    trends_cli.main(["links", "--terms", "air fryer"])
    assert "Google Shopping" in capsys.readouterr().out


def test_cli_links_rejects_bad_input(capsys):
    assert trends_cli.main(["links", "--terms", "a,b"]) == 2


# ---- blocked pages fail fast --------------------------------------------------------------------
def test_blocked_error_defaults_to_not_retryable():
    assert fp.BlockedError("x").retryable is False
    assert fp.BlockedError("x", retryable=True).retryable is True


class _Resp:
    def __init__(self, status, url, ok):
        self.status, self.url, self.ok = status, url, ok


class _Page:
    url = "https://trends.google.com/trends/explore?q=x"

    def __init__(self, goto_status=200):
        self.goto_calls, self._status = 0, goto_status

    def on(self, *_):
        pass

    def goto(self, *_, **__):
        self.goto_calls += 1
        return _Resp(self._status, self.url, False)

    def wait_for_timeout(self, _ms):
        pass


class _Context:
    def __init__(self, page):
        self.page = page

    def route(self, *_):
        pass

    def new_page(self):
        return self.page

    def close(self):
        pass


def _fake_playwright(monkeypatch, page):
    browser = types.SimpleNamespace(new_context=lambda **_: _Context(page), close=lambda: None)
    pw = types.SimpleNamespace(chromium=types.SimpleNamespace(launch=lambda **_: browser))

    class _Cm:
        def __enter__(self):
            return pw

        def __exit__(self, *_):
            return False

    mod = types.ModuleType("playwright.sync_api")
    mod.sync_playwright = lambda: _Cm()
    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.sync_api", mod)


def test_blocked_explore_page_stops_at_once_without_waiting(monkeypatch, tmp_path):
    page = _Page(goto_status=429)
    _fake_playwright(monkeypatch, page)
    slept = []
    monkeypatch.setattr(fp.time, "sleep", lambda s: slept.append(s))
    with pytest.raises(fp.BlockedError) as err:
        fp.fetch(["x"], ["UA"], "today 5-y", ["web"], tmp_path)
    assert "explore page" in str(err.value) and err.value.retryable is False
    assert page.goto_calls == 1 and slept == []  # no 60 s wait, no second attempt


def test_429_on_a_data_request_is_retried_once_after_a_pause(monkeypatch, tmp_path):
    page = _Page(goto_status=200)
    page.seen = None
    _fake_playwright(monkeypatch, page)
    slept = []
    monkeypatch.setattr(fp.time, "sleep", lambda s: slept.append(s))

    def fake_gather(_ctx):
        raise fp.BlockedError("HTTP 429 (rate limited) on a data request", retryable=True)

    monkeypatch.setattr(fp, "_gather", fake_gather)
    with pytest.raises(fp.BlockedError):
        fp.fetch(["x"], ["UA"], "today 5-y", ["web"], tmp_path)
    assert page.goto_calls == 2 and slept == [60]


def test_check_prints_links_and_a_helpful_message_when_blocked(monkeypatch, tmp_path, capsys):
    def blocked(*_a, **_k):
        raise fp.BlockedError("HTTP 429 (rate limited) on the explore page")

    monkeypatch.setattr(trends_cli, "fetch", blocked)
    code = trends_cli.main(["check", "--terms", "стрижка", "барбершоп", "--geo", "UA", "--out", str(tmp_path / "o")])
    cap = capsys.readouterr()
    assert code == 3
    assert "links for manual export" in cap.out and "https://trends.google.com/trends/explore?" in cap.out
    assert "Claude in Chrome" in cap.err and "do not retry" in cap.err and "import-csv" in cap.err


def test_docs_name_the_right_requirements_path():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "skills" / "google-trends"
    for doc in (root / "SKILL.md", root / "references" / "cli-mode.md"):
        text = doc.read_text(encoding="utf-8")
        assert "pip install -r requirements.txt" not in text and "scripts/requirements.txt" in text
    assert "list_connected_browsers" in (root / "SKILL.md").read_text(encoding="utf-8")
