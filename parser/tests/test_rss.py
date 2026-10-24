from pathlib import Path
from xml.etree.ElementTree import ParseError

import pytest

from parser.config import Config, PARSER_DIR
from parser.rss import MAX_XML_BYTES, clean_html, parse_date, read_rss


def test_fixture_and_wire_contract():
    items = read_rss(PARSER_DIR / "fixtures/synthetic.xml", "configured-source")
    valid = [item for item in items if item.payload]
    assert len(items) == 10 and len(valid) == 5
    assert all(item.payload.source_name == "configured-source" for item in valid)
    assert valid[0].payload.content == "Invented workshop update & test."
    assert valid[1].payload.content == "Invented extended text. Second line."
    assert valid[0].payload.model_dump(mode="json")["published_at"] == "2026-01-01T09:00:00Z"
    assert valid[2].payload.published_at is None and valid[2].issues == []
    assert valid[3].payload.published_at is None and valid[3].issues == ["INVALID_PUBDATE"]
    assert valid[4].payload.published_at is None and valid[4].issues == ["INVALID_PUBDATE"]
    assert [item.issues for item in items[5:]] == [
        ["MISSING_CONTENT"], ["MISSING_TITLE"], ["NO_RELIABLE_IDENTITY"],
        ["INVALID_FIELDS:url"], ["INVALID_FIELDS:source_id"]]
    assert set(valid[0].payload.model_dump()) == {
        "title", "content", "url", "source_name", "source_id", "published_at", "language"}


@pytest.mark.parametrize("html,expected", [
    ("<p>A <b>bold</b> &amp; B</p><p>Next<br/>line.</p>", "A bold & B Next line."),
    ('A<script src="https://example.invalid/no-fetch">secret()</script>B', "AB"),
    ("<style>css</style><iframe>hidden</iframe><div>Visible</div>", "Visible"),
    ('<a href="https://example.invalid/no-fetch">Text</a><img src="missing"/>', "Text"),
    ("<!-- comment --><p>A&nbsp;B</p>", "A B"),
    ("<script>unclosed must be suppressed", ""),
])
def test_html_to_text(html, expected):
    assert clean_html(html) == expected


@pytest.mark.parametrize("raw,expected,warning", [
    (None, None, []), ("", None, ["INVALID_PUBDATE"]),
    ("Thu, 01 Jan 2026 12:00:00 +0300", "2026-01-01T09:00:00+00:00", []),
    ("2026-01-02T10:00:00-02:00", "2026-01-02T12:00:00+00:00", []),
    ("2026-01-02", None, ["INVALID_PUBDATE"]),
    ("Thu, 01 Jan 2026 12:00:00 -0000", None, ["INVALID_PUBDATE"]),
    ("31 February 2026", None, ["INVALID_PUBDATE"]),
])
def test_dates_do_not_invent_timestamp(raw, expected, warning):
    value, issues = parse_date(raw)
    assert (value.isoformat() if value else None) == expected
    assert issues == warning


@pytest.mark.parametrize("identity", ["<link>https://example.invalid/a</link>", "<guid>SYNTH-ID-ONLY</guid>"])
def test_either_reliable_identity_is_enough(tmp_path, identity):
    path = tmp_path / "rss.xml"
    path.write_text(f'<rss version="2.0"><channel><item><title>Synthetic</title><description>Text</description>{identity}</item></channel></rss>')
    assert read_rss(path, "synthetic-demo")[0].payload


@pytest.mark.parametrize("xml,error", [
    ('<!DOCTYPE rss [<!ENTITY x "forbidden">]><rss version="2.0"><channel/></rss>', ValueError),
    ('<rss version="2.0"><channel>', ParseError),
    ('<feed/>', ValueError),
])
def test_unsafe_or_invalid_xml(tmp_path, xml, error):
    path = tmp_path / "rss.xml"
    path.write_text(xml)
    with pytest.raises(error):
        read_rss(path, "synthetic-demo")


def test_limits_and_no_content_fallback(tmp_path):
    path = tmp_path / "rss.xml"
    path.write_bytes(b"x" * (MAX_XML_BYTES + 1))
    with pytest.raises(ValueError, match="1 MiB"):
        read_rss(path, "synthetic-demo")
    path.write_text('<rss version="2.0"><channel><item><title>Synthetic</title><guid>SYNTH-ID</guid><description>' +
                    'x' * 100001 + '</description></item></channel></rss>')
    assert read_rss(path, "synthetic-demo")[0].issues == ["INVALID_FIELDS:content"]


def test_config_is_independent_and_paths_are_portable(tmp_path):
    config = Config.from_env({"PARSER_SOURCE_NAME": "fixture-source", "DATABASE_URL": "must-not-be-used",
                              "LLM_API_KEY": "must-not-be-used", "PARSER_REPORT_PATH": str(tmp_path / "report.json")})
    assert config.rss_path == PARSER_DIR / "fixtures/synthetic.xml"
    assert config.source_name == "fixture-source" and config.timeout == 10
    assert not hasattr(config, "database_url") and not hasattr(config, "llm_api_key")


@pytest.mark.parametrize("env", [
    {"PARSER_RSS_PATH": "https://example.invalid/rss"},
    {"PARSER_BACKEND_URL": "https://example.invalid"},
    {"PARSER_BACKEND_URL": "http://user:password@localhost:8000"},
    {"PARSER_BACKEND_URL": "http://localhost:8000/api"},
    {"PARSER_SOURCE_NAME": "DISPLAY NAME"}, {"PARSER_SOURCE_NAME": "UPPER"},
    {"PARSER_HTTP_TIMEOUT": "0"}, {"PARSER_HTTP_TIMEOUT": "nan"},
    {"PARSER_REPORT_PATH": "fixtures/synthetic.xml"},
])
def test_invalid_configuration(env):
    with pytest.raises(ValueError):
        Config.from_env(env)
