import pytest

from parsai import ChunkingOptions, DefaultChunker, DocumentInfo, DocumentMetadata
from parsai import parse_and_chunk_file
from parsai.chunkers import MarkdownChunker, PptxChunker, chunk_document, chunk_text
from parsai.registry import create_default_chunker_registry


def test_chunking_options_reject_invalid_values():
    invalid_options = [
        ({"max_words": 0}, "max_words must be greater than 0"),
        ({"overlap_words": -1}, "overlap_words must be greater than or equal to 0"),
        ({"min_words": -1}, "min_words must be greater than or equal to 0"),
        ({"max_words": 10, "min_words": 11}, "min_words must be less than or equal to max_words"),
        ({"max_words": 10, "overlap_words": 10, "min_words": 1}, "overlap_words must be less than max_words"),
    ]

    for kwargs, message in invalid_options:
        with pytest.raises(ValueError, match=message):
            ChunkingOptions(**kwargs)


def test_chunking_options_reject_non_integer_values():
    with pytest.raises(TypeError, match="max_words must be an integer"):
        ChunkingOptions(max_words=10.5)


def test_default_chunker_builds_metadata(chunking_overlap_file):
    registry = create_default_chunker_registry(ChunkingOptions(max_words=6, overlap_words=2, min_words=3))
    text = chunking_overlap_file.read_text()

    chunks = chunk_text(
        text,
        source_path=str(chunking_overlap_file),
        file_type="txt",
        metadata=DocumentMetadata(filename=chunking_overlap_file.name, extra={"source": "unit-test"}),
        registry=registry,
    )

    assert len(chunks) == 2
    assert chunks[0].chunk_id == f"{chunking_overlap_file.name}:default:0"
    assert chunks[0].metadata.chunker == "default"
    assert chunks[0].metadata.chunk_index == 0
    assert chunks[0].metadata.word_count == 4
    assert chunks[0].metadata.extra["source"] == "unit-test"


def test_registry_uses_file_type_default_chunker():
    registry = create_default_chunker_registry()
    document = DocumentInfo(source_path="/tmp/notes.md", file_type="md")

    chunks = chunk_document("# Title\n\nBody text", document=document, registry=registry)

    assert chunks[0].metadata.chunker == "markdown"
    assert "#" not in chunks[0].text


def test_pptx_chunker_splits_on_slide_markers():
    chunker = PptxChunker()
    document = DocumentInfo(
        source_path="/tmp/slides.pptx",
        file_type="pptx",
        metadata=DocumentMetadata(filename="slides.pptx", extra={"section_type": "deck", "deck": "demo"}),
    )

    chunks = chunker.chunk("<slide 1> Intro\n\n<slide 2> Details", document=document)

    assert len(chunks) == 2
    assert chunks[0].metadata.extra["deck"] == "demo"
    assert chunks[0].metadata.extra["section_type"] == "slide"
    assert chunks[0].metadata.extra["slide_number"] == 1
    assert chunks[1].metadata.extra["slide_number"] == 2


def test_markdown_chunker_strips_markdown_before_chunking():
    chunker = MarkdownChunker()
    document = DocumentInfo(source_path="/tmp/notes.md", file_type="md")

    chunks = chunker.chunk("# Title\n\nThis is **bold** text.", document=document)

    assert len(chunks) == 1
    assert chunks[0].text.startswith("Title")
    assert "**" not in chunks[0].text


def test_parse_and_chunk_file_uses_override(pdf_file):
    chunks = parse_and_chunk_file(str(pdf_file), chunker_name="default")

    assert chunks
    assert chunks[0].metadata.chunker == "default"
    assert chunks[0].metadata.extra["page_count"] == 16


def test_default_chunker_adds_overlap_between_chunks(chunking_overlap_file):
    chunker = DefaultChunker(options=ChunkingOptions(max_words=6, overlap_words=2, min_words=3))
    document = DocumentInfo(source_path=str(chunking_overlap_file), file_type="txt")

    chunks = chunker.chunk(chunking_overlap_file.read_text(), document=document)

    assert len(chunks) == 2
    assert chunks[1].text.startswith("three four")


def test_default_chunker_prefers_sentence_overlap(chunking_sentence_overlap_file):
    chunker = DefaultChunker(options=ChunkingOptions(max_words=6, overlap_words=3, min_words=1))
    document = DocumentInfo(source_path=str(chunking_sentence_overlap_file), file_type="txt")

    chunks = chunker.chunk(chunking_sentence_overlap_file.read_text(), document=document)

    assert len(chunks) >= 2
    assert chunks[1].text.startswith("Beta keeps context.")
    assert not chunks[1].text.startswith("keeps context.")


def test_default_chunker_merges_short_final_chunk(chunking_short_tail_file):
    chunker = DefaultChunker(options=ChunkingOptions(max_words=6, overlap_words=0, min_words=3))
    document = DocumentInfo(source_path=str(chunking_short_tail_file), file_type="txt")

    chunks = chunker.chunk(chunking_short_tail_file.read_text(), document=document)

    assert len(chunks) == 1
    assert chunks[0].metadata.word_count == 8
    assert chunks[0].text.endswith("seven eight")
