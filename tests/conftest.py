import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TEST_FILES = ROOT / "tests" / "test_files"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture
def pdf_file() -> Path:
    return TEST_FILES / "fgene-16-1569358.pdf"


@pytest.fixture
def unsupported_file() -> Path:
    return TEST_FILES / "unsupported.unknown"


@pytest.fixture
def html_file() -> Path:
    return TEST_FILES / "reader_article.html"


@pytest.fixture
def chunking_overlap_file() -> Path:
    return TEST_FILES / "chunking_overlap.txt"


@pytest.fixture
def chunking_short_tail_file() -> Path:
    return TEST_FILES / "chunking_short_tail.txt"


@pytest.fixture
def chunking_sentence_overlap_file() -> Path:
    return TEST_FILES / "chunking_sentence_overlap.txt"
