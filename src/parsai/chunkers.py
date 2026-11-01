from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
import re
from typing import Any


from parsai.types import Chunk, ChunkMetadata, ChunkingOptions, DocumentInfo, DocumentMetadata
from parsai.modifiers import strip_markdown_text

class BaseChunker(ABC):
    name = "base"

    def __init__(self, options: ChunkingOptions | None = None):
        self.options = options or ChunkingOptions()

    @abstractmethod
    def chunk(self, text: str, document: DocumentInfo) -> list[Chunk]:
        raise NotImplementedError

    def build_chunk(
        self,
        text: str,
        chunk_index: int,
        document: DocumentInfo,
        metadata: dict[str, Any] | None = None,
    ) -> Chunk:
        document_id = document.resolved_document_id()
        chunk_id = f"{document_id}:{self.name}:{chunk_index}"
        merged_metadata = {}
        if document.metadata is not None:
            merged_metadata.update(document.metadata.extra)
        if metadata:
            merged_metadata.update(metadata)

        chunk_metadata = ChunkMetadata(
            chunker=self.name,
            chunk_index=chunk_index,
            word_count=len(text.split()),
            extra=merged_metadata,
        )

        return Chunk(
            chunk_id=chunk_id,
            text=text,
            chunk_index=chunk_index,
            document_id=document_id,
            source_path=document.source_path,
            file_type=document.file_type,
            metadata=chunk_metadata,
        )

    def _last_words(self, text: str, count: int) -> str:
        words = text.split()
        if count <= 0 or not words:
            return ""
        return " ".join(words[-count:])

    def _split_sentences(self, text: str) -> list[str]:
        return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text.strip()) if sentence.strip()]

    def _overlap_text(self, text: str) -> str:
        if self.options.overlap_words <= 0:
            return ""

        sentences = self._split_sentences(text)
        if len(sentences) <= 1:
            return self._last_words(text, self.options.overlap_words)

        selected = []
        selected_words = 0

        for sentence in reversed(sentences):
            sentence_words = len(sentence.split())
            if sentence_words > self.options.overlap_words:
                if not selected:
                    return self._last_words(sentence, self.options.overlap_words)
                break
            if selected and selected_words + sentence_words > self.options.overlap_words:
                break

            selected.append(sentence)
            selected_words += sentence_words

            if selected_words >= self.options.overlap_words:
                break

        if not selected:
            return self._last_words(text, self.options.overlap_words)

        return " ".join(reversed(selected)).strip()

    def _split_large_text(self, text: str) -> list[str]:
        words = text.split()
        if len(words) <= self.options.max_words:
            return [text.strip()]

        sentences = self._split_sentences(text)
        if len(sentences) <= 1:
            return self._split_large_words(words)

        chunks = []
        current = []
        current_words = 0

        for sentence in sentences:
            sentence_words = sentence.split()
            if len(sentence_words) > self.options.max_words:
                if current:
                    chunks.append(" ".join(current).strip())
                    current = []
                    current_words = 0
                chunks.extend(self._split_large_words(sentence_words))
                continue

            if current and current_words + len(sentence_words) > self.options.max_words:
                chunks.append(" ".join(current).strip())
                current = [sentence]
                current_words = len(sentence_words)
            else:
                current.append(sentence)
                current_words += len(sentence_words)

        if current:
            chunks.append(" ".join(current).strip())

        return [chunk for chunk in chunks if chunk]

    def _split_large_words(self, words: list[str]) -> list[str]:
        return [
            " ".join(words[index:index + self.options.max_words]).strip()
            for index in range(0, len(words), self.options.max_words)
            if words[index:index + self.options.max_words]
        ]


class DefaultChunker(BaseChunker):
    name = "default"

    def chunk(self, text: str, document: DocumentInfo) -> list[Chunk]:
        parts = self._prepare_parts(text, document)
        return self._assemble_chunks(parts, document)

    def _prepare_parts(self, text: str, document: DocumentInfo) -> list[str]:
        text = text.strip()
        if not text:
            return []

        paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()]
        parts = []
        for paragraph in paragraphs:
            parts.extend(self._split_large_text(paragraph))
        return parts

    def _assemble_chunks(self, parts: list[str], document: DocumentInfo) -> list[Chunk]:
        chunk_texts = []
        current_parts = []
        current_words = 0

        for part in parts:
            part_words = len(part.split())

            if current_parts and current_words + part_words > self.options.max_words:
                chunk_text = "\n\n".join(current_parts).strip()
                chunk_texts.append(chunk_text)

                overlap = self._overlap_text(chunk_text)
                current_parts = [piece for piece in [overlap, part] if piece]
                current_words = len(" ".join(current_parts).split())
                continue

            current_parts.append(part)
            current_words += part_words

        if current_parts:
            chunk_text = "\n\n".join(current_parts).strip()
            chunk_texts.append(chunk_text)

        chunk_texts = self._merge_small_chunks(chunk_texts)
        return [
            self.build_chunk(chunk_text, chunk_index, document)
            for chunk_index, chunk_text in enumerate(chunk_texts)
        ]

    def _merge_small_chunks(self, chunk_texts: list[str]) -> list[str]:
        if self.options.min_words <= 0 or len(chunk_texts) <= 1:
            return chunk_texts

        merged = []
        for chunk_text in chunk_texts:
            if len(chunk_text.split()) < self.options.min_words and merged:
                merged[-1] = "\n\n".join([merged[-1], chunk_text]).strip()
            else:
                merged.append(chunk_text)

        if len(merged) > 1 and len(merged[0].split()) < self.options.min_words:
            merged[1] = "\n\n".join([merged[0], merged[1]]).strip()
            merged = merged[1:]

        return merged


class MarkdownChunker(DefaultChunker):
    name = "markdown"

    def chunk(self, text: str, document: DocumentInfo) -> list[Chunk]:
        plain_text = strip_markdown_text(text)
        return super().chunk(plain_text, document)


class PdfChunker(DefaultChunker):
    name = "pdf"

    def chunk(self, text: str, document: DocumentInfo) -> list[Chunk]:
        return super().chunk(text, document)


class EmailChunker(DefaultChunker):
    name = "email"

    def chunk(self, text: str, document: DocumentInfo) -> list[Chunk]:
        return super().chunk(text, document)


class PptxChunker(DefaultChunker):
    name = "pptx"

    def chunk(self, text: str, document: DocumentInfo) -> list[Chunk]:
        text = text.strip()
        if not text:
            return []

        parts = re.split(r"(<slide\s+\d+>)", text)
        slides = []
        marker = None

        for part in parts:
            part = part.strip()
            if not part:
                continue
            if re.fullmatch(r"<slide\s+\d+>", part):
                marker = part
                continue
            slides.append((marker, part))
            marker = None

        if not slides:
            return super().chunk(text, document)

        chunks = []
        for index, (marker, slide_text) in enumerate(slides):
            slide_number = None
            if marker:
                match = re.search(r"\d+", marker)
                if match:
                    slide_number = int(match.group())
                slide_text = f"{marker}\n{slide_text}".strip()

            chunks.append(
                self.build_chunk(
                    slide_text,
                    index,
                    document,
                    metadata={"section_type": "slide", "slide_number": slide_number},
                )
            )
        return chunks


def chunk_document(
    text: str,
    document: DocumentInfo,
    registry=None,
    chunker_name: str | None = None,
) -> list[Chunk]:
    if registry is None:
        from parsai.registry import create_default_chunker_registry

        registry = create_default_chunker_registry()
    chunker = registry.get(chunker_name=chunker_name, file_type=document.file_type)
    return chunker.chunk(text=text, document=document)


def chunk_text(
    text: str,
    source_path: str,
    file_type: str | None = None,
    document_id: str | None = None,
    metadata: DocumentMetadata | None = None,
    registry=None,
    chunker_name: str | None = None,
) -> list[Chunk]:
    document = DocumentInfo(
        source_path=source_path,
        file_type=file_type,
        document_id=document_id,
        metadata=metadata or DocumentMetadata(filename=Path(source_path).name),
    )
    return chunk_document(text=text, document=document, registry=registry, chunker_name=chunker_name)
