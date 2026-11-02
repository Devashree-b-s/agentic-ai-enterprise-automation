"""Document validation, text extraction, cleaning, and recursive chunking service."""

import io
import os
import re
from pathlib import Path

import docx
import pypdf

# Supported file extensions and magic headers
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal attacks and illegal filesystem characters."""
    # Strip any directory path components
    basename = os.path.basename(filename.replace("\\", "/"))
    # Remove null bytes and non-printable characters
    cleaned = re.sub(r"[\x00-\x1f\x7f]", "", basename).strip()
    if not cleaned or cleaned in {".", ".."}:
        return "unnamed_document.txt"
    return cleaned


def validate_file_upload(
    filename: str,
    file_bytes: bytes,
    max_size_bytes: int = 10 * 1024 * 1024,
) -> tuple[str, str]:
    """Validate uploaded document file for safe format, extension, and size limits.

    Returns:
        tuple[sanitized_filename, normalized_file_type]

    Raises:
        ValueError: If file is empty, oversized, unsupported, or malformed.
    """
    if not file_bytes or len(file_bytes) == 0:
        raise ValueError("Uploaded file is empty (0 bytes).")

    if len(file_bytes) > max_size_bytes:
        max_mb = max_size_bytes / (1024 * 1024)
        raise ValueError(f"File size exceeds maximum permitted limit of {max_mb:.1f} MB.")

    safe_name = sanitize_filename(filename)
    ext = Path(safe_name).suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported document format '{ext}'. Supported formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))}."
        )

    # Basic header verification to detect disguised executables or malformed headers
    if ext == ".pdf":
        if not file_bytes.startswith(b"%PDF-"):
            raise ValueError("Malformed PDF: Missing %PDF- magic signature.")
    elif ext == ".docx" and not file_bytes.startswith(b"PK\x03\x04"):
        raise ValueError("Malformed DOCX: Missing standard PK zip container header.")

    file_type = ext.lstrip(".")
    return safe_name, file_type


def clean_extracted_text(text: str) -> str:
    """Normalize extracted text by stripping control characters and collapsing whitespace."""
    if not text:
        return ""

    # Remove null bytes and control characters (except newline, tab, carriage return)
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # Standardize line endings to Unix style
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")

    # Collapse consecutive horizontal whitespace (spaces, tabs) into single space
    cleaned = re.sub(r"[ \t]+", " ", cleaned)

    # Collapse more than two consecutive newlines into double newline (preserve paragraph breaks)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned.strip()


def extract_text_from_txt(file_bytes: bytes) -> str:
    """Extract and decode text from TXT file bytes with charset fallback."""
    try:
        raw_text = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            raw_text = file_bytes.decode("latin-1")
        except Exception as exc:
            raise ValueError(f"Failed to decode text file content: {exc}") from exc

    cleaned = clean_extracted_text(raw_text)
    if not cleaned:
        raise ValueError("Text file contains no extractable text content.")
    return cleaned


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF pages safely using pypdf.

    Handles empty or scanned PDFs by explicitly raising an informative error
    without pretending OCR has been performed.
    """
    try:
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    except Exception as exc:
        raise ValueError(f"Corrupted or invalid PDF structure: {exc}") from exc

    if len(reader.pages) == 0:
        raise ValueError("PDF file contains zero pages.")

    extracted_pages: list[str] = []
    for page_num, page in enumerate(reader.pages):
        try:
            page_text = page.extract_text() or ""
            extracted_pages.append(page_text)
        except Exception:
            extracted_pages.append("")

    full_text = clean_extracted_text("\n\n".join(extracted_pages))

    if not full_text or len(full_text.strip()) == 0:
        raise ValueError(
            "Scanned or image-only PDF detected. OCR is not supported. "
            "Please upload a searchable text-based PDF."
        )

    return full_text


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract text from DOCX paragraphs and tables safely using python-docx."""
    try:
        doc = docx.Document(io.BytesIO(file_bytes))
    except Exception as exc:
        raise ValueError(f"Corrupted or invalid DOCX document: {exc}") from exc

    text_parts: list[str] = []

    # Extract all body paragraphs
    for p in doc.paragraphs:
        t = p.text.strip()
        if t:
            text_parts.append(t)

    # Extract all table cells
    for table in doc.tables:
        for row in table.rows:
            row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if row_cells:
                text_parts.append(" | ".join(row_cells))

    full_text = clean_extracted_text("\n\n".join(text_parts))

    if not full_text or len(full_text.strip()) == 0:
        raise ValueError("DOCX document contains no extractable text content.")

    return full_text


def extract_document_text(file_bytes: bytes, file_type: str) -> str:
    """Dispatch document text extraction according to normalized file format."""
    ft = file_type.lower().lstrip(".")
    if ft == "pdf":
        return extract_text_from_pdf(file_bytes)
    if ft == "docx":
        return extract_text_from_docx(file_bytes)
    if ft == "txt":
        return extract_text_from_txt(file_bytes)
    raise ValueError(f"Unsupported file format '{file_type}'.")


def chunk_text(
    text: str,
    chunk_size: int = 600,
    chunk_overlap: int = 100,
) -> list[str]:
    """Split text into overlapping chunks using hierarchical boundary splitting.

    Respects natural paragraph and sentence delimiters before splitting on word or
    character boundaries to preserve semantic coherence.
    """
    if not text or not text.strip():
        return []

    if len(text) <= chunk_size:
        return [text.strip()]

    # Delimiters in order of semantic preference
    delimiters = ["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " "]

    def recursive_split(subtext: str, delim_idx: int) -> list[str]:
        if len(subtext) <= chunk_size:
            return [subtext.strip()] if subtext.strip() else []

        if delim_idx >= len(delimiters):
            # Hard character slice fallback
            chunks: list[str] = []
            start = 0
            while start < len(subtext):
                end = min(start + chunk_size, len(subtext))
                c = subtext[start:end].strip()
                if c:
                    chunks.append(c)
                if end == len(subtext):
                    break
                start += chunk_size - chunk_overlap
            return chunks

        delimiter = delimiters[delim_idx]
        parts = subtext.split(delimiter)
        
        # If the delimiter didn't break down the text, try next delimiter
        if len(parts) == 1:
            return recursive_split(subtext, delim_idx + 1)

        result_chunks: list[str] = []
        current_chunk = ""

        for part in parts:
            part_str = part.strip()
            if not part_str:
                continue

            test_chunk = (
                f"{current_chunk}{delimiter}{part_str}"
                if current_chunk
                else part_str
            )

            if len(test_chunk) <= chunk_size:
                current_chunk = test_chunk
            else:
                if current_chunk:
                    result_chunks.append(current_chunk.strip())

                # If the single part itself exceeds chunk_size, break it down further
                if len(part_str) > chunk_size:
                    sub_chunks = recursive_split(part_str, delim_idx + 1)
                    result_chunks.extend(sub_chunks)
                    current_chunk = ""
                else:
                    # Apply overlap from previous chunk if available
                    if result_chunks and chunk_overlap > 0:
                        prev_text = result_chunks[-1]
                        overlap_seed = prev_text[-chunk_overlap:].strip()
                        current_chunk = f"{overlap_seed} {part_str}".strip()
                    else:
                        current_chunk = part_str

        if current_chunk and current_chunk.strip():
            result_chunks.append(current_chunk.strip())

        return [c for c in result_chunks if c]

    raw_chunks = recursive_split(text, 0)
    # Deduplicate empty or degenerate fragments
    final_chunks: list[str] = []
    for c in raw_chunks:
        c_clean = c.strip()
        if c_clean and (not final_chunks or final_chunks[-1] != c_clean):
            final_chunks.append(c_clean)

    return final_chunks
