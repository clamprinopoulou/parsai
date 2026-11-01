"""Command-line interface for reading supported documents."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pprint import pformat
from typing import Sequence

from parsai.parsers import _is_http_url, _is_url, parse_file, read_html
from parsai.types import DocumentMetadata


def read_source(source: str) -> tuple[str, DocumentMetadata]:
    """Read a URL as HTML or dispatch a local path through the parser registry."""
    if _is_http_url(source):
        return read_html(source)
    if _is_url(source):
        raise ValueError("Unsupported URL scheme; use an http(s) URL")
    return parse_file(source)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="parsai",
        description="Extract readable text from a supported local file or HTTP(S) URL.",
    )
    parser.add_argument(
        "source",
        help="A local file path or an absolute HTTP(S) URL.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Print source and metadata above the extracted text.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print source, metadata, and extracted text as formatted JSON.",
    )
    return parser


def _print_pretty(source: str, text: str, metadata: DocumentMetadata) -> None:
    print(f"Source: {source}")
    print("Metadata:")
    print(pformat(asdict(metadata), sort_dicts=False))
    print("\nContent:\n")
    print(text)


def _print_json(source: str, text: str, metadata: DocumentMetadata) -> None:
    payload = {
        "source": source,
        "metadata": asdict(metadata),
        "content": text,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


def main(argv: Sequence[str] | None = None) -> int:
    """Run the ``parsai`` command and return its process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        text, metadata = read_source(args.source)
    except Exception as err:
        print(f"{parser.prog}: error: {err}", file=sys.stderr)
        return 1

    if args.json:
        _print_json(args.source, text, metadata)
    elif args.pretty:
        _print_pretty(args.source, text, metadata)
    else:
        print(text)
    return 0
