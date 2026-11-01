# parsai

`parsai` is a document parsing and chunking library.

## Command line

After installing the package, use `parsai` to extract a supported local file or
static HTTP(S) page:

```bash
parsai /tmp/report.pdf
parsai https://example.com/article
```

For a local path, the command selects the reader from its extension. Supported
types are `.txt`, `.md`, `.pdf`, `.docx`, `.pptx`, `.eml`, `.html`, and `.htm`.
HTTP(S) URLs are read with `read_html()`. Static pages are supported; pages whose
content requires JavaScript are not.

By default, the command writes extracted text only, making it suitable for
piping to another command:

```bash
parsai /tmp/report.pdf > report.txt
```

Choose one of these optional output formats when document context is useful:

| Option | Output |
| --- | --- |
| `--pretty` | Source and metadata followed by readable extracted text. |
| `--json` | Formatted JSON with `source`, `metadata`, and `content` fields. |

For example:

```bash
parsai /tmp/report.pdf --pretty
parsai /tmp/report.pdf --json
```

When both output flags are supplied, `--json` takes precedence over `--pretty`.
Unsupported file types, unreadable files, and non-HTTP(S) URLs are reported on
standard error and return a nonzero exit status. `python -m parsai SOURCE`
provides the same interface when running from a source checkout.

## Recommended API

Most users should start with:

```python
from parsai import parse_and_chunk_file

chunks = parse_and_chunk_file("/tmp/report.pdf")
```

That is the main happy path:

- parse a file
- select the default chunker for the file type
- return structured chunks with metadata

If you only want parsing:

```python
from parsai import parse_file

text, metadata = parse_file("/tmp/report.pdf")
```

For local HTML files or static web pages, use `read_html()`:

```python
from parsai import read_html

local_text, local_metadata = read_html("/tmp/article.html")
web_text, web_metadata = read_html("https://example.com/article")
```

`read_html()` extracts reader-style article text from static HTML and retains article
link targets. It does not run page JavaScript, so JavaScript-rendered pages are not
supported.

If you already have parsed text:

```python
from parsai import chunk_text

chunks = chunk_text(
    text=text,
    source_path="/tmp/report.pdf",
    file_type="pdf",
    metadata=metadata,
)
```

## Public Top-Level API

The recommended top-level imports are:

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

## Submodules

Lower-level functions, registry factories, modifiers, and specialized chunkers remain available from submodules:

```python
from parsai.parsers import read_txt, read_md, read_docx, read_pptx, read_eml, read_analyse_pdf
from parsai.chunkers import PptxChunker, MarkdownChunker, PdfChunker, EmailChunker
from parsai.registry import create_default_parser_registry, create_default_chunker_registry
from parsai.modifiers import strip_markdown_text
```

`parse_file()` and `parse_and_chunk_file()` live in `parsai.parsers`, while `chunk_text()` and `chunk_document()` live in `parsai.chunkers`.

`strip_markdown_text()` is used by `MarkdownChunker`, but it is not part of the top-level `parsai` API.

## Chunking Behavior

`DefaultChunker` splits text by paragraphs, splits oversized paragraphs by sentences, falls back to word windows when needed, and prefers whole-sentence overlap between chunks. `ChunkingOptions` validates `max_words`, `overlap_words`, and `min_words`; short chunks below `min_words` are merged into neighboring chunks.

See `PARSai_DESIGN.md` for the fuller API and architecture.
