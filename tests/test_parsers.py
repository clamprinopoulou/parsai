import pytest

from parsai.parsers import parse_file, read_html
from parsai.registry import ParserRegistry
from parsai.types import DocumentMetadata


def test_parse_file_parses_real_pdf_fixture(pdf_file):
    text, metadata = parse_file(str(pdf_file))

    assert "Constructing ancestral recombination graphs" in text
    assert metadata.filename == pdf_file.name
    assert metadata.extra["page_count"] == 16


def test_parse_file_uses_custom_registry(pdf_file):
    registry = ParserRegistry()
    registry.register("pdf", lambda path: ("parsed pdf", DocumentMetadata(filename=pdf_file.name)))

    text, metadata = parse_file(str(pdf_file), registry=registry)

    assert text == "parsed pdf"
    assert metadata.filename == pdf_file.name
    assert metadata.extra == {}


def test_parse_file_normalises_string_parser_result(pdf_file):
    registry = ParserRegistry()
    registry.register("pdf", lambda path: "parsed pdf")

    text, metadata = parse_file(str(pdf_file), registry=registry)

    assert text == "parsed pdf"
    assert metadata.filename == pdf_file.name
    assert metadata.extra == {}


def test_parse_file_normalises_dict_metadata(pdf_file):
    registry = ParserRegistry()
    registry.register("pdf", lambda path: ("parsed pdf", {"pages": 16}))

    text, metadata = parse_file(str(pdf_file), registry=registry)

    assert text == "parsed pdf"
    assert metadata.filename == pdf_file.name
    assert metadata.extra == {"pages": 16}


def test_parse_file_rejects_unknown_extension(unsupported_file):
    try:
        parse_file(str(unsupported_file))
    except ValueError as err:
        assert "Unsupported file type" in str(err)
    else:
        raise AssertionError("Expected ValueError for unknown parser")


def test_read_html_extracts_reader_text_from_local_file(html_file):
    text, metadata = read_html(html_file)

    assert "A clearer way to organize research notes" in text
    assert "The article's second paragraph" in text
    assert "https://example.test/guidance" in text
    assert "Primary navigation link" not in text
    assert "Cookie banner text" not in text
    assert "window.trackingToken" not in text
    assert metadata.filename == html_file.name
    assert metadata.extra["title"] == "A clearer way to organize research notes"
    assert metadata.extra["author"] == "Par Sai"


def test_parse_file_uses_html_parser(html_file):
    text, metadata = parse_file(str(html_file))

    assert "A clearer way to organize research notes" in text
    assert metadata.filename == html_file.name


def test_read_html_fetches_urls_before_extracting(monkeypatch, html_file):
    final_url = "https://example.com/articles/research-notes"

    monkeypatch.setattr(
        "parsai.parsers.fetch_url",
        lambda url: (html_file.read_bytes(), final_url),
    )

    text, metadata = read_html("https://example.com/original")

    assert "A clearer way to organize research notes" in text
    assert metadata.filename == "research-notes"
    assert metadata.extra["source_url"] == final_url


def test_read_html_treats_non_http_values_as_local_paths(tmp_path):
    missing_file = tmp_path / "https:example.com.html"

    with pytest.raises(FileNotFoundError):
        read_html(missing_file)


def test_read_html_rejects_non_http_urls():
    with pytest.raises(ValueError, match="absolute http\\(s\\) URL"):
        read_html("ftp://example.com/article.html")
