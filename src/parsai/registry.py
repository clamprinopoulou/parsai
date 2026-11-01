from __future__ import annotations

from typing import Callable

from parsai.parsers import (
    RawParserResult,
    read_html,
    read_analyse_pdf,
    read_docx,
    read_eml,
    read_md,
    read_pptx,
    read_txt,
)
from parsai.types import ChunkingOptions


ParserFn = Callable[[str], RawParserResult]


class ParserRegistry:
    def __init__(self):
        self._parsers: dict[str, ParserFn] = {}

    def register(self, file_type: str, reader: ParserFn) -> None:
        self._parsers[file_type] = reader

    def get(self, file_type: str) -> ParserFn:
        try:
            return self._parsers[file_type]
        except KeyError as err:
            raise KeyError(f"Unknown parser for file type '{file_type}'") from err

    def supports(self, file_type: str) -> bool:
        return file_type in self._parsers


class ChunkerRegistry:
    def __init__(self):
        self._chunkers = {}
        self._file_type_defaults = {}

    def register(self, name: str, chunker) -> None:
        self._chunkers[name] = chunker

    def set_default_for_file_type(self, file_type: str, chunker_name: str) -> None:
        self._file_type_defaults[file_type] = chunker_name

    def get(self, chunker_name: str | None = None, file_type: str | None = None):
        if chunker_name:
            try:
                return self._chunkers[chunker_name]
            except KeyError as err:
                raise KeyError(f"Unknown chunker '{chunker_name}'") from err

        if file_type:
            default_name = self._file_type_defaults.get(file_type)
            if default_name:
                return self._chunkers[default_name]

        try:
            return self._chunkers["default"]
        except KeyError as err:
            raise KeyError("Chunker registry has no default chunker") from err


def create_default_parser_registry() -> ParserRegistry:
    registry = ParserRegistry()
    registry.register("txt", read_txt)
    registry.register("md", read_md)
    registry.register("docx", read_docx)
    registry.register("pptx", read_pptx)
    registry.register("eml", read_eml)
    registry.register("pdf", read_analyse_pdf)
    registry.register("html", read_html)
    registry.register("htm", read_html)
    return registry


def create_default_chunker_registry(options: ChunkingOptions | None = None) -> ChunkerRegistry:
    from parsai.chunkers import DefaultChunker, EmailChunker, MarkdownChunker, PdfChunker, PptxChunker

    registry = ChunkerRegistry()
    registry.register("default", DefaultChunker(options=options))
    registry.register("markdown", MarkdownChunker(options=options))
    registry.register("pdf", PdfChunker(options=options))
    registry.register("pptx", PptxChunker(options=options))
    registry.register("email", EmailChunker(options=options))

    registry.set_default_for_file_type("txt", "default")
    registry.set_default_for_file_type("md", "markdown")
    registry.set_default_for_file_type("pdf", "pdf")
    registry.set_default_for_file_type("pptx", "pptx")
    registry.set_default_for_file_type("eml", "email")
    return registry
