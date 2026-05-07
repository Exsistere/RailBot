"""
Developer-only FAQ ingestion script for Qdrant.

Usage:
  python scripts/ingest_faq_docs.py --file docs/faq_paths.json

Input JSON format:
[
  "docs/faq_seed.json",
  {"path": "docs/faq_seed.json", "source": "railway_faq"},
  {"file": "docs/faq_seed.json", "title": "FAQ bundle"}
]

The referenced files may be:
- JSON documents list with objects containing text/title/source
- JSON object containing a single FAQ document
- Plain text or markdown files

Each loaded document is chunked before embedding.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.services.rag_ingest_service import RAGIngestService

try:
    from PyPDF2 import PdfReader
except ImportError as exc:
    raise ImportError(
        "PyPDF2 is required to ingest PDF files. Install it with `pip install PyPDF2`."
    ) from exc


def _load_path_item(item: Any) -> Dict[str, Any]:
    if isinstance(item, str):
        return {"path": item}
    if isinstance(item, dict):
        if "path" in item:
            return dict(item)
        if "file" in item:
            copy = dict(item)
            copy["path"] = copy.pop("file")
            return copy
    raise ValueError(
        "Each item in the input JSON must be either a file path string or an object with a 'path' or 'file' key"
    )


def _resolve_source_path(path: str, base_dir: Path) -> Path:
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = base_dir / resolved
    return resolved


def _load_documents_from_file(path_item: Dict[str, Any], base_dir: Path) -> List[Dict[str, Any]]:
    file_path = _resolve_source_path(str(path_item["path"]), base_dir)
    if not file_path.exists():
        raise FileNotFoundError(f"Document file not found: {file_path}")

    source = path_item.get("source", "internal_faq")
    title = path_item.get("title", file_path.stem)

    if file_path.suffix.lower() == ".json":
        raw = json.loads(file_path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            documents: List[Dict[str, Any]] = []
            for entry in raw:
                if not isinstance(entry, dict):
                    raise ValueError("JSON file must contain a list of document objects")
                text = str(entry.get("text", "")).strip()
                if not text:
                    continue
                documents.append(
                    {
                        "text": text,
                        "source": entry.get("source", source),
                        "title": entry.get("title", title),
                    }
                )
            return documents
        if isinstance(raw, dict) and raw.get("text"):
            return [
                {
                    "text": str(raw.get("text", "")).strip(),
                    "source": raw.get("source", source),
                    "title": raw.get("title", title),
                }
            ]
        raise ValueError(
            f"JSON document file must contain either a list of docs or a single object with a 'text' field: {file_path}"
        )

    if file_path.suffix.lower() == ".pdf":
        logger.info("Loading PDF document: %s", file_path)
        reader = PdfReader(str(file_path))
        pages: List[str] = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            pages.append(page_text.strip())
        text = "\n\n".join(p for p in pages if p)
        if not text:
            return []
        logger.info("Loaded PDF document %s with %d pages", file_path, len(pages))
        return [{"text": text, "source": source, "title": title}]

    text = file_path.read_text(encoding="utf-8").strip()
    if not text:
        return []

    return [{"text": text, "source": source, "title": title}]


def _chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    tokens = text.split()
    if chunk_size <= chunk_overlap:
        raise ValueError("chunk-size must be greater than chunk-overlap")
    if not tokens:
        return []

    chunks: List[str] = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunks.append(" ".join(tokens[start:end]))
        if end == len(tokens):
            break
        start = end - chunk_overlap

    logger.debug(
        "Chunked text into %d chunks (%d tokens, size=%d, overlap=%d)",
        len(chunks),
        len(tokens),
        chunk_size,
        chunk_overlap,
    )
    return chunks


def _prepare_documents(
    input_path: Path,
    path_entries: List[Any],
    chunk_size: int,
    chunk_overlap: int,
) -> List[Dict[str, str]]:
    base_dir = input_path.parent
    prepared: List[Dict[str, str]] = []

    for raw_item in path_entries:
        path_item = _load_path_item(raw_item)
        docs = _load_documents_from_file(path_item, base_dir)
        for document in docs:
            text = document["text"].strip()
            if not text:
                continue
            chunks = _chunk_text(text, chunk_size, chunk_overlap)
            logger.info(
                "Preparing document %s from source %s: %d chunk(s)",
                document.get("title", "<untitled>"),
                document.get("source", "internal_faq"),
                len(chunks),
            )
            if len(chunks) <= 1:
                prepared.append(
                    {
                        "text": text,
                        "source": document.get("source", "internal_faq"),
                        "title": document.get("title", ""),
                    }
                )
                continue

            base_title = document.get("title", "")
            for index, chunk in enumerate(chunks, start=1):
                prepared.append(
                    {
                        "text": chunk,
                        "source": document.get("source", "internal_faq"),
                        "title": f"{base_title} (chunk {index}/{len(chunks)})" if base_title else f"chunk {index}/{len(chunks)}",
                    }
                )

    return prepared


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest FAQ documents into Qdrant")
    parser.add_argument("--file", required=True, help="Path to JSON file containing source file paths")
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=450,
        help="Maximum number of words per chunk",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=50,
        help="Number of overlapping words between adjacent chunks",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    file_path = Path(args.file)
    if not file_path.exists():
        raise FileNotFoundError(f"Input file not found: {file_path}")

    path_entries = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(path_entries, list):
        raise ValueError("Input JSON must be a list of file path entries")

    logger.info("Ingesting FAQ paths from %s", file_path)
    logger.info("Found %d path entries", len(path_entries))

    documents = _prepare_documents(file_path, path_entries, args.chunk_size, args.chunk_overlap)
    if not documents:
        raise ValueError("No documents were loaded from the provided file paths")

    service = RAGIngestService()
    count = service.ingest_documents(documents)
    print(f"Ingested {count} chunks into Qdrant collection.")


if __name__ == "__main__":
    main()

