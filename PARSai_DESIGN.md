# PARSai API Design

## Purpose

`parsai` is a document parsing and chunking library.

It is responsible for:

- parsing files into text
- preserving document-level metadata
- modifying raw parser text before chunking when a format needs it
- chunking parsed text into structured chunk objects
- providing explicit registries for parsers and chunkers
- supporting file-type defaults and explicit chunker overrides

It is not responsible for:

- LLM connections
- embeddings
- vector databases
- retrieval
- RAG orchestration

This keeps the dependency direction clean:

- `parsai`: parsing + text modification + chunking
- `connai`: LLM communication
- `ragai`: can import both `parsai` and `connai`

## Conceptual Pipeline

The core pipeline is:

```text
file
  -> ParserX
  -> (text, document_metadata)
  -> optional text modifier
  -> ChunkerX
  -> list[Chunk]
```

More concretely:

```text
report.pdf
  -> read_analyse_pdf
  -> (
       "full parsed text",
       DocumentMetadata(filename="report.pdf", extra={"page_count": 12})
     )
  -> PdfChunker
  -> [
       Chunk(...),
       Chunk(...),
       Chunk(...),
     ]
```

Mental model:

- parsers produce `text + DocumentMetadata`
- modifiers transform raw text before chunking
- chunkers consume `text + DocumentInfo`
- chunkers return structured `Chunk` objects
- each chunk contains text plus metadata suitable for indexing or later serialization

## Package Layout

```text
parsai/
  pyproject.toml
  README.md
  PARSai_DESIGN.md
  src/
    parsai/
      __init__.py
      types.py
      parsers.py
      modifiers.py
      chunkers.py
      registry.py
```

## Core Data Types

### `DocumentMetadata`

Represents metadata produced by a parser.

```python
@dataclass
class DocumentMetadata:
    filename: str
    extra: dict[str, Any] = field(default_factory=dict)
```

`extra` is where parser-specific values live, such as `title`, `author`, `page_count`, or ingestion metadata.

### `DocumentInfo`

Represents document-level context passed into chunkers.

```python
@dataclass
class DocumentInfo:
    source_path: str
    file_type: str | None = None
    document_id: str | None = None
    metadata: DocumentMetadata | None = None

    def resolved_document_id(self) -> str:
        ...
```

Document ID resolution uses:

1. explicit `document_id`
2. `metadata.filename`
3. the basename of `source_path`

### `ChunkMetadata`

Represents metadata for one chunk.

```python
@dataclass
class ChunkMetadata:
    chunker: str
    chunk_index: int
    word_count: int
    extra: dict[str, Any] = field(default_factory=dict)
```

`extra` contains merged document metadata plus any chunk-specific metadata. Chunk-specific metadata wins on key collisions.

### `Chunk`

Represents one chunk ready for downstream use.

```python
@dataclass
class Chunk:
    chunk_id: str
    text: str
    chunk_index: int
    document_id: str
    source_path: str
    file_type: str | None = None
    metadata: ChunkMetadata | None = None
```

Conceptually, a chunk is:

```json
{
  "chunk_id": "report.pdf:pdf:0",
  "text": "This is chunk text",
  "chunk_index": 0,
  "document_id": "report.pdf",
  "source_path": "/docs/report.pdf",
  "file_type": "pdf",
  "metadata": {
    "chunker": "pdf",
    "chunk_index": 0,
    "word_count": 312,
    "extra": {
      "page_count": 12,
      "title": "Quarterly Report"
    }
  }
}
```

### `ChunkingOptions`

Defines chunking behavior.

```python
@dataclass
class ChunkingOptions:
    max_words: int = 400
    overlap_words: int = 50
    min_words: int = 20
```

Validation rules:

- all three values must be integers
- `max_words` must be greater than `0`
- `overlap_words` must be greater than or equal to `0`
- `min_words` must be greater than or equal to `0`
- `min_words` must be less than or equal to `max_words`
- `overlap_words` must be less than `max_words`

`min_words=0` disables small-chunk merging.

## Parsing API

### Design Rule

Parsers are explicit. No `globals()` discovery.

If a new parser is added, it must also be registered.

### Parser Functions

Low-level parser functions live in `parsers.py`.

```python
def read_txt(path: str) -> tuple[str, DocumentMetadata]: ...
def read_md(path: str) -> tuple[str, DocumentMetadata]: ...
def read_docx(path: str) -> tuple[str, DocumentMetadata]: ...
def read_pptx(path: str) -> tuple[str, DocumentMetadata]: ...
def read_eml(path: str) -> tuple[str, DocumentMetadata]: ...
def read_analyse_pdf(path: str) -> tuple[str, DocumentMetadata]: ...
def read_html(source: str | Path) -> tuple[str, DocumentMetadata]: ...
```

Built-in parsers return normalized `(text, DocumentMetadata)` tuples.

Custom parser return rules:

- a parser may return plain `str`
- a parser may return `(text, DocumentMetadata)`
- a parser may return `(text, dict)`

`parse_file()` normalizes all supported custom parser results to `(text, DocumentMetadata)`.

### `ParserRegistry`

```python
class ParserRegistry:
    def register(self, file_type: str, reader: ParserFn) -> None: ...
    def get(self, file_type: str) -> ParserFn: ...
    def supports(self, file_type: str) -> bool: ...
```

Purpose:

- explicit parser registration
- easy extension
- no naming magic
- no dynamic `globals()` lookup

### `create_default_parser_registry()`

```python
from parsai.registry import create_default_parser_registry
```

Registers built-in parsers for:

- `txt`
- `md`
- `docx`
- `pptx`
- `eml`
- `pdf`
- `html` and `htm`

### `parse_file(path)`

Unified entry point for parsing.

```python
def parse_file(
    path: str,
    registry: ParserRegistry | None = None,
) -> tuple[str, DocumentMetadata]:
    ...
```

Behavior:

1. infer file type from extension
2. resolve parser from registry
3. parse file
4. normalize result to `(text, DocumentMetadata)`
5. raise `ValueError` if unsupported

Example:

```python
from parsai import parse_file

text, metadata = parse_file("/tmp/report.pdf")
```

### `read_html(source)`

Parses readable text from a local HTML file or an absolute HTTP(S) URL:

```python
from parsai import read_html

text, metadata = read_html("/tmp/article.html")
text, metadata = read_html("https://example.com/article")
```

For a URL, `read_html()` fetches the static HTML before extracting the page's main
article text. For a local file it extracts directly from the file's HTML bytes.
The extractor stores available title, author, date, site name, language, and source
URL values in `DocumentMetadata.extra`, and preserves article link targets. No page
JavaScript is executed or rendered.

## Modifiers

Modifiers live in `modifiers.py`.

They transform raw parser text before chunking, but they are not part of the top-level `parsai` API.

Current modifier:

```python
from parsai.modifiers import strip_markdown_text
```

`MarkdownChunker` uses `strip_markdown_text()` so `read_md()` can preserve raw Markdown while Markdown-specific cleanup happens at chunking time.

## Chunking API

### Design Rule

Chunkers accept parsed text and document context.

They do not parse files themselves.

Core shape:

```text
(text, document_info) -> list[Chunk]
```

### `BaseChunker`

Abstract base class for all chunkers.

```python
class BaseChunker(ABC):
    name: str

    def __init__(self, options: ChunkingOptions | None = None):
        ...

    @abstractmethod
    def chunk(self, text: str, document: DocumentInfo) -> list[Chunk]:
        ...

    def build_chunk(
        self,
        text: str,
        chunk_index: int,
        document: DocumentInfo,
        metadata: dict[str, Any] | None = None,
    ) -> Chunk:
        ...
```

Responsibilities:

- define the chunking contract
- centralize chunk construction
- centralize document/chunk metadata merging
- centralize chunk ID creation

### `DefaultChunker`

The generic chunker and the main extension base for downstream libraries.

Current behavior:

1. strip leading and trailing text whitespace
2. split into paragraphs
3. split oversized paragraphs by sentences
4. fall back to word windows when sentence splitting is not possible
5. assemble chunks up to `max_words`
6. prefer whole-sentence overlap between chunks
7. fall back to word overlap when needed
8. merge chunks below `min_words` into a neighboring chunk

The overlap behavior is intentionally sentence-aware where possible because it avoids starting chunks in the middle of a sentence.

### Built-in Chunkers

```python
class MarkdownChunker(DefaultChunker): ...
class PdfChunker(DefaultChunker): ...
class PptxChunker(DefaultChunker): ...
class EmailChunker(DefaultChunker): ...
```

Current behavior:

- `DefaultChunker`: paragraph-first chunking with sentence-aware overlap
- `MarkdownChunker`: strips Markdown text via `strip_markdown_text()` before default chunking
- `PdfChunker`: uses default chunking for PDF text
- `PptxChunker`: splits on `<slide N>` markers and adds slide metadata
- `EmailChunker`: uses default chunking for email text

## Chunker Registry

### `ChunkerRegistry`

```python
class ChunkerRegistry:
    def register(self, name: str, chunker: BaseChunker) -> None: ...
    def set_default_for_file_type(self, file_type: str, chunker_name: str) -> None: ...
    def get(self, chunker_name: str | None = None, file_type: str | None = None) -> BaseChunker: ...
```

Purpose:

- register chunkers explicitly
- support defaults by file type
- support explicit caller override

### `create_default_chunker_registry()`

```python
from parsai.registry import create_default_chunker_registry
```

Registers built-ins and default file-type mappings:

- `txt -> default`
- `md -> markdown`
- `pdf -> pdf`
- `pptx -> pptx`
- `eml -> email`

## Chunker Resolution Rules

Chunker selection follows this order:

1. if caller passes `chunker_name`, use that
2. else if file type has a default chunker, use that
3. else use the generic `default` chunker

This supports both automatic selection by document type and explicit user override.

## High-Level Helpers

### `chunk_document(...)`

```python
def chunk_document(
    text: str,
    document: DocumentInfo,
    registry: ChunkerRegistry | None = None,
    chunker_name: str | None = None,
) -> list[Chunk]:
    ...
```

Use when `DocumentInfo` already exists.

### `chunk_text(...)`

```python
def chunk_text(
    text: str,
    source_path: str,
    file_type: str | None = None,
    document_id: str | None = None,
    metadata: DocumentMetadata | None = None,
    registry: ChunkerRegistry | None = None,
    chunker_name: str | None = None,
) -> list[Chunk]:
    ...
```

Use when parsed text already exists and a convenient entry point is needed.

This wraps the inputs into `DocumentInfo` and delegates to `chunk_document(...)`.

### `parse_and_chunk_file(...)`

```python
def parse_and_chunk_file(
    path: str,
    chunker_name: str | None = None,
    parser_registry: ParserRegistry | None = None,
    chunker_registry: ChunkerRegistry | None = None,
) -> list[Chunk]:
    ...
```

Use when one-step local processing is desired:

```text
file -> parse -> chunk
```

Behavior:

1. parse file with `parse_file(path)`
2. build `DocumentInfo`
3. resolve chunker
4. return `list[Chunk]`

If `chunker_name` is omitted, the file-type default chunker is used.

## Public API

### Top-Level API

The top-level `parsai` package intentionally exposes the common happy path and core types:

```python
from parsai import (
    parse_file,
    read_html,
    parse_and_chunk_file,
    chunk_text,
    chunk_document,
    DocumentInfo,
    DocumentMetadata,
    Chunk,
    ChunkMetadata,
    ChunkingOptions,
    ParserRegistry,
    ChunkerRegistry,
    DefaultChunker,
)
```

### Submodule API

Lower-level and specialized APIs remain available from submodules:

```python
from parsai.parsers import read_txt, read_md, read_docx, read_pptx, read_eml, read_analyse_pdf
from parsai.chunkers import BaseChunker, MarkdownChunker, PdfChunker, PptxChunker, EmailChunker
from parsai.registry import create_default_parser_registry, create_default_chunker_registry
from parsai.modifiers import strip_markdown_text
```

`strip_markdown_text()` is a modifier helper. It is importable from `parsai.modifiers`, but it is not promoted as a top-level public API.

## Typical Usage

### Parse Only

```python
from parsai import parse_file

text, metadata = parse_file("/tmp/report.pdf")
```

### Parse Then Chunk

```python
from parsai import parse_file, chunk_text

text, metadata = parse_file("/tmp/report.pdf")

chunks = chunk_text(
    text=text,
    source_path="/tmp/report.pdf",
    file_type="pdf",
    metadata=metadata,
)
```

### One-Step Parse + Chunk

```python
from parsai import parse_and_chunk_file

chunks = parse_and_chunk_file("/tmp/report.pdf")
```

### Explicit Chunker Override

```python
from parsai import parse_and_chunk_file

chunks = parse_and_chunk_file(
    "/tmp/slides.pptx",
    chunker_name="default",
)
```

### Register A New Parser

```python
from parsai import parse_file
from parsai.registry import create_default_parser_registry

def read_csv(path: str) -> str:
    ...

registry = create_default_parser_registry()
registry.register("csv", read_csv)

text, metadata = parse_file("/tmp/data.csv", registry=registry)
```

### Register A Custom Chunker

```python
from parsai import DefaultChunker, chunk_text
from parsai.registry import create_default_chunker_registry

class CsvChunker(DefaultChunker):
    name = "csv"

registry = create_default_chunker_registry()
registry.register("csv", CsvChunker())
registry.set_default_for_file_type("csv", "csv")

chunks = chunk_text("a,b,c", source_path="/tmp/data.csv", file_type="csv", registry=registry)
```

## Extension Model

### Adding A New Parser

To support a new file type:

1. add `read_xxx(path)` in `parsers.py`
2. register it in `ParserRegistry`

`parse_file()` does not auto-discover functions by name.

This avoids:

- `globals()`
- hidden magic
- accidental parser exposure
- brittle dispatch logic

### Adding A New Modifier

To add text cleanup or transformation that should happen after parsing but before chunking, add a function to `modifiers.py` and call it from the relevant chunker.

Keep modifiers small and deterministic. LLM-powered cleanup belongs outside `parsai`.

### Adding A New Chunker

To add a new chunker:

1. subclass `DefaultChunker` or `BaseChunker`
2. register it in `ChunkerRegistry`
3. optionally assign it as the default for one or more file types

Rule of thumb:

- subclass `DefaultChunker` if chunk assembly, overlap, metadata merging, and chunk ID creation should be reused
- subclass `BaseChunker` if the logic is fundamentally different

## Compatibility With Future AI Chunking

`parsai` itself should remain non-AI.

That means:

- `parsai` must not import `connai`
- AI chunking should live in a higher-level package such as `ragai`

Example:

```python
from parsai import DefaultChunker
from parsai.types import DocumentInfo

class AIChunker(DefaultChunker):
    name = "ai"

    def _prepare_parts(self, text: str, document: DocumentInfo) -> list[str]:
        # use an LLM in ragai, not in parsai
        ...
```

Dependency direction:

- `parsai`: no LLM dependency
- `connai`: can import `parsai`
- `ragai`: can import both `parsai` and `connai`

This avoids circular imports.

## Compatibility With The Target Schematic

Target model:

```text
ParserX --> text --> ChunkerX --> list of jsons
```

Current API design:

```text
ParserX --> (text, DocumentMetadata) --> optional modifier --> ChunkerX --> list[Chunk]
```

Where each `Chunk` contains:

- chunk text
- chunk ID
- source path
- file type
- chunk index
- document ID
- chunk metadata
- merged document/chunk metadata in `ChunkMetadata.extra`

So the API matches the target schematic and extends it in the right place: document metadata is preserved instead of being lost between parsing and chunking.

## Final Summary

The current `parsai` design is:

- explicit, registry-based, and free of `globals()`
- parser-driven for `file -> (text, DocumentMetadata)`
- modifier-aware for format-specific raw text cleanup
- chunker-driven for `(text, DocumentInfo) -> list[Chunk]`
- compatible with file-type defaults and explicit chunker overrides
- conservative about the top-level public API
- designed so `DefaultChunker` can be subclassed later
- safe to use from both `connai` and future `ragai`-style packages
