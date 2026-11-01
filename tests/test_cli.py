import json

import pytest

from parsai.cli import main, read_source
from parsai.types import DocumentMetadata


def test_cli_prints_extracted_text(chunking_overlap_file, capsys):
    result = main([str(chunking_overlap_file)])

    captured = capsys.readouterr()

    assert result == 0
    assert captured.out == chunking_overlap_file.read_text() + "\n"
    assert captured.err == ""


def test_cli_pretty_output_includes_metadata(chunking_overlap_file, capsys):
    result = main([str(chunking_overlap_file), "--pretty"])

    captured = capsys.readouterr()

    assert result == 0
    assert f"Source: {chunking_overlap_file}" in captured.out
    assert f"'filename': '{chunking_overlap_file.name}'" in captured.out
    assert "Content:\n\n" in captured.out
    assert chunking_overlap_file.read_text() in captured.out


def test_cli_json_output_is_structured(chunking_overlap_file, capsys):
    result = main([str(chunking_overlap_file), "--json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert result == 0
    assert output == {
        "source": str(chunking_overlap_file),
        "metadata": {"filename": chunking_overlap_file.name, "extra": {}},
        "content": chunking_overlap_file.read_text(),
    }
    assert captured.err == ""


def test_cli_routes_http_urls_to_html_reader(monkeypatch, capsys):
    monkeypatch.setattr(
        "parsai.cli.read_html",
        lambda source: ("page text", DocumentMetadata(filename="page")),
    )

    result = main(["https://example.com/article"])

    captured = capsys.readouterr()

    assert result == 0
    assert captured.out == "page text\n"


def test_read_source_rejects_non_http_urls():
    with pytest.raises(ValueError, match="Unsupported URL scheme"):
        read_source("ftp://example.com/document")


def test_cli_returns_error_for_unsupported_file(unsupported_file, capsys):
    result = main([str(unsupported_file)])

    captured = capsys.readouterr()

    assert result == 1
    assert captured.out == ""
    assert "Unsupported file type 'unknown'" in captured.err


def test_cli_json_takes_precedence_over_pretty(chunking_overlap_file, capsys):
    result = main([str(chunking_overlap_file), "--pretty", "--json"])

    captured = capsys.readouterr()

    assert result == 0
    assert json.loads(captured.out)["content"] == chunking_overlap_file.read_text()
    assert "Source:" not in captured.out
