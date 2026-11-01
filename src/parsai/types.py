from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DocumentMetadata:
    filename: str
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChunkMetadata:
    chunker: str
    chunk_index: int
    word_count: int
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentInfo:
    source_path: str
    file_type: str | None = None
    document_id: str | None = None
    metadata: DocumentMetadata | None = None

    def resolved_document_id(self) -> str:
        if self.document_id:
            return self.document_id
        if self.metadata is not None:
            return self.metadata.filename
        return Path(self.source_path).name


@dataclass
class Chunk:
    chunk_id: str
    text: str
    chunk_index: int
    document_id: str
    source_path: str
    file_type: str | None = None
    metadata: ChunkMetadata | None = None


@dataclass
class ChunkingOptions:
    max_words: int = 400
    overlap_words: int = 50
    min_words: int = 20

    def __post_init__(self) -> None:
        for field_name in ("max_words", "overlap_words", "min_words"):
            if type(getattr(self, field_name)) is not int:
                raise TypeError(f"{field_name} must be an integer")

        if self.max_words <= 0:
            raise ValueError("max_words must be greater than 0")
        if self.overlap_words < 0:
            raise ValueError("overlap_words must be greater than or equal to 0")
        if self.min_words < 0:
            raise ValueError("min_words must be greater than or equal to 0")
        if self.min_words > self.max_words:
            raise ValueError("min_words must be less than or equal to max_words")
        if self.overlap_words >= self.max_words:
            raise ValueError("overlap_words must be less than max_words")
