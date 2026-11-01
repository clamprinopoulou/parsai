from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import docx2txt
from email import policy
from email.parser import BytesParser

import pymupdf
import pymupdf.layout
import pymupdf4llm
import requests
from pptx import Presentation
from trafilatura import bare_extraction, extract_metadata

from parsai.types import DocumentInfo, DocumentMetadata

pymupdf.layout.activate()

RawParserResult = str | tuple[str, DocumentMetadata] | tuple[str, dict[str, Any]]
ParserResult = tuple[str, DocumentMetadata]

REQUEST_TIMEOUT = (5, 20)
MAX_RESPONSE_BYTES = 5 * 1024 * 1024


class WebFetchError(RuntimeError):
    """Raised when a URL cannot be fetched as an HTML document."""


def _is_http_url(source: str) -> bool:
    parsed = urlparse(source)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _is_url(source: str) -> bool:
    parsed = urlparse(source)
    return bool(parsed.scheme and parsed.netloc)


def _filename_for_url(url: str) -> str:
    parsed = urlparse(url)
    return Path(parsed.path).name or parsed.netloc


def fetch_url(url: str) -> tuple[bytes, str]:
    """Fetch an HTML document and return its bytes and final URL."""
    if not _is_http_url(url):
        raise ValueError("URL must be an absolute http(s) URL")

    try:
        with requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": "parsai/0.1 (+document parser)"},
            stream=True,
        ) as response:
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "").lower()
            if content_type and not (
                "text/html" in content_type or "application/xhtml+xml" in content_type
            ):
                raise WebFetchError(f"Expected HTML, received {content_type}")

            content = bytearray()
            for chunk in response.iter_content(chunk_size=64 * 1024):
                content.extend(chunk)
                if len(content) > MAX_RESPONSE_BYTES:
                    raise WebFetchError(f"Page exceeds {MAX_RESPONSE_BYTES} byte limit")

            return bytes(content), response.url
    except requests.RequestException as err:
        raise WebFetchError(f"Could not fetch {url}") from err


def extract_readable_html(
    html: bytes | str,
    *,
    filename: str,
    source_url: str | None = None,
) -> ParserResult:
    """Extract article-like plain text and metadata from static HTML."""
    article = bare_extraction(
        html,
        url=source_url,
        include_comments=False,
        include_tables=True,
        include_links=True,
        favor_precision=True,
    )
    metadata = extract_metadata(html, default_url=source_url)

    text = article.text.strip() if article and article.text else ""
    extra = {
        key: value
        for key, value in {
            "source_url": source_url,
            "title": getattr(metadata, "title", None)
            or getattr(article, "title", None),
            "author": getattr(metadata, "author", None)
            or getattr(article, "author", None),
            "date": getattr(metadata, "date", None) or getattr(article, "date", None),
            "site_name": getattr(metadata, "sitename", None)
            or getattr(article, "sitename", None),
            "language": getattr(metadata, "language", None)
            or getattr(article, "language", None),
        }.items()
        if value
    }
    return text, DocumentMetadata(filename=filename, extra=extra)


def read_html(source: str | Path) -> ParserResult:
    """Parse reader-style text from either a local HTML file or an HTTP(S) URL."""
    source_text = str(source)
    if _is_url(source_text):
        html, final_url = fetch_url(source_text)
        return extract_readable_html(
            html,
            filename=_filename_for_url(final_url),
            source_url=final_url,
        )

    path = Path(source_text)
    return extract_readable_html(path.read_bytes(), filename=path.name)



def read_txt(file_path: str) -> ParserResult:
    with open(file_path, "r") as text_file:
        return text_file.read(), DocumentMetadata(filename=Path(file_path).name)


def read_analyse_pdf(file_path: str) -> ParserResult:
    extra = {}
    doc = pymupdf.open(file_path)

    json_obj = json.loads(pymupdf4llm.to_json(doc))
    if "metadata" in json_obj:
        for key in ["title", "author"]:
            value = json_obj["metadata"].get(key)
            if value:
                extra[key] = value
    if "page_count" in json_obj:
        extra["page_count"] = json_obj["page_count"]

    return pymupdf4llm.to_text(doc, footer=False), DocumentMetadata(
        filename=Path(file_path).name,
        extra=extra,
    )


def read_md(file_path: str) -> ParserResult:
    md_text, _metadata = read_txt(file_path)
    return md_text, DocumentMetadata(filename=Path(file_path).name)


def read_docx(file_path: str) -> ParserResult:
    try:
        return docx2txt.process(file_path) or "", DocumentMetadata(filename=Path(file_path).name)
    except Exception:
        return "", DocumentMetadata(filename=Path(file_path).name)


def read_pptx(file_path: str) -> ParserResult:
    presentation = Presentation(file_path)
    text_runs = []
    for index, slide in enumerate(presentation.slides):
        text_runs.append(f" <slide {index + 1}> ")
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    text_runs.append(f"{run.text} ")
    return "".join(text_runs), DocumentMetadata(filename=Path(file_path).name)


def read_eml(file_path: str) -> str:
    def save_attachments(attachments, output_dir: str):
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        saved_files = []
        for i, att in enumerate(attachments, start=1):
            name = att["filename"] or f"attachment-{i}.bin"
            path = out / name
            path.write_bytes(att["data"])
            saved_files.append(str(path))



    text, attachments = "",[]
    try:
        with open(file_path, "rb") as handle:
            msg = BytesParser(policy=policy.default).parse(handle)

        plain = msg.get_body(preferencelist=("plain",))
        ## if the email has pain text, capture it
        if plain:
            text = plain.get_content()
        ## if plain text is not captured, try to get the html content
        if not text:
            text = msg.get_body(preferencelist=("html",))
        

        """ TODO
        ## examine if there are attachments
        for part in msg.iter_attachments():
            filename = part.get_filename()
            if not filename:
                filename = "attachment.bin"

            payload = part.get_payload(decode=True)  ## returns the attachment or body content as decoded raw bytes 
            if payload is None:
                continue

            attachments.append({
                "filename": filename,
                "content_type": part.get_content_type(),
                "data": payload,
            })
        ## TODO: Save them to disk and parse them if you can
        if attachments:
            saved_files = save_attachments(attachments, "tmp_attachments/")
        """ 

        return text

    except Exception:
        return ""


###########
# DEFUNCT #
###########
#from fast_mail_parser import ParseError, parse_email

def read_eml_old(file_path: str) -> ParserResult:
    """ """
    with open(file_path, "r") as handle:
        message_payload = handle.read()

    try:
        email = parse_email(message_payload)
        return email.text_plain[0], DocumentMetadata(filename=Path(file_path).name)
    except ParseError:
        return "", DocumentMetadata(filename=Path(file_path).name)




def normalize_parser_result(result: RawParserResult, file_path: str) -> ParserResult:
    if isinstance(result, str):
        return result, DocumentMetadata(filename=Path(file_path).name)

    if not isinstance(result, tuple) or len(result) != 2:
        raise TypeError("Parser must return text or (text, metadata)")

    text, metadata = result
    if isinstance(metadata, DocumentMetadata):
        return text, metadata
    if isinstance(metadata, dict):
        return text, DocumentMetadata(filename=Path(file_path).name, extra=metadata)

    raise TypeError("Parser metadata must be DocumentMetadata or dict")


def parse_file(path: str, registry=None) -> ParserResult:
    file_path = str(path)
    file_type = Path(file_path).suffix[1:].lower()
    if registry is None:
        from parsai.registry import create_default_parser_registry

        registry = create_default_parser_registry()

    try:
        parser = registry.get(file_type)
    except KeyError as err:
        raise ValueError(f"Unsupported file type '{file_type}'") from err

    return normalize_parser_result(parser(file_path), file_path)


def parse_and_chunk_file(
    path: str,
    chunker_name: str | None = None,
    parser_registry=None,
    chunker_registry=None,
):
    from parsai.chunkers import chunk_document

    file_path = str(path)
    text, metadata = parse_file(file_path, registry=parser_registry)
    file_type = Path(file_path).suffix[1:].lower() or None
    document = DocumentInfo(
        source_path=file_path,
        file_type=file_type,
        metadata=metadata,
    )
    return chunk_document(
        text=text,
        document=document,
        registry=chunker_registry,
        chunker_name=chunker_name,
    )
