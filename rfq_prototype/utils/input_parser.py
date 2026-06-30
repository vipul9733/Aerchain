"""Lightweight vendor input parsing: txt, md, json, pdf (best-effort)."""

from __future__ import annotations

import io
import json


def parse_uploaded_file(filename: str, raw_bytes: bytes) -> str:
    name = filename.lower()
    if name.endswith((".txt", ".md")):
        return raw_bytes.decode("utf-8", errors="replace")
    if name.endswith(".json"):
        try:
            obj = json.loads(raw_bytes.decode("utf-8", errors="replace"))
            return json.dumps(obj, indent=2)
        except Exception:
            return raw_bytes.decode("utf-8", errors="replace")
    if name.endswith(".pdf"):
        return _parse_pdf(raw_bytes)
    if name.endswith((".docx",)):
        return _parse_docx(raw_bytes)
    # Fallback: best-effort decode.
    return raw_bytes.decode("utf-8", errors="replace")


def _parse_pdf(raw_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return "[PDF parsing requires `pypdf`. Install it, or paste the text instead.]"
    try:
        reader = PdfReader(io.BytesIO(raw_bytes))
        return "\n".join((page.extract_text() or "") for page in reader.pages).strip()
    except Exception as e:
        return f"[Could not parse PDF: {e}. Paste the text instead.]"


def _parse_docx(raw_bytes: bytes) -> str:
    try:
        import docx
    except ImportError:
        return "[DOCX parsing requires `python-docx`. Install it, or paste the text instead.]"
    try:
        document = docx.Document(io.BytesIO(raw_bytes))
        return "\n".join(p.text for p in document.paragraphs).strip()
    except Exception as e:
        return f"[Could not parse DOCX: {e}. Paste the text instead.]"
