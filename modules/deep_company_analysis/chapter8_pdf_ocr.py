from __future__ import annotations

"""Chapter 8 Phase 8N — bounded OCR fallback for scanned official PDFs.

The OCR layer is intentionally evidence-conservative:
* it runs only when the caller explicitly enables it after normal PDF text extraction returns empty;
* it requires local ``pdftoppm`` + Tesseract and the requested language packs;
* OCR text is tagged with page provenance markers before candidate extraction;
* OCR output remains ``Candidate — analyst verify`` and is never promoted automatically;
* no analyst conclusion/status/confidence, management score, MOS, Research Gate or signal is written.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

from pypdf import PdfReader


DEFAULT_OCR_LANGUAGES = "vie+eng"
DEFAULT_OCR_DPI = 170
DEFAULT_OCR_MAX_PAGES = 80
DEFAULT_OCR_WORKERS = 2
PAGE_MARKER_RE = re.compile(r"\[\[OCR_PAGE:(\d+)\]\]")


@dataclass(frozen=True)
class OCRPage:
    page_number: int
    text: str
    status: str
    duration_ms: int
    image_bytes: int


@dataclass(frozen=True)
class PDFOCRResult:
    text: str
    method: str
    runtime_ok: bool
    runtime_note: str
    languages: str
    page_count: int
    attempted_pages: int
    successful_pages: int
    failed_pages: int
    pages: tuple[OCRPage, ...]


def _safe_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _requested_languages(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in str(value or "").split("+") if part.strip())


def _tesseract_languages() -> tuple[str, ...]:
    try:
        proc = subprocess.run(
            ["tesseract", "--list-langs"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        lines = [line.strip() for line in (proc.stdout or "").splitlines()]
        return tuple(line for line in lines if line and "list of available languages" not in line.casefold())
    except Exception:
        return ()


def ocr_runtime_status(languages: str = DEFAULT_OCR_LANGUAGES) -> tuple[bool, str]:
    missing_bins = [name for name in ("pdftoppm", "tesseract") if not shutil.which(name)]
    if missing_bins:
        return False, "missing binary: " + ", ".join(missing_bins)
    available = set(_tesseract_languages())
    requested = _requested_languages(languages)
    missing_langs = [lang for lang in requested if lang not in available]
    if missing_langs:
        return False, "missing tesseract language pack: " + ", ".join(missing_langs)
    return True, f"pdftoppm+tesseract ready; languages={'+'.join(requested)}"


def _page_chunks(text: str, page_number: int, *, chunk_chars: int = 480) -> list[str]:
    """Keep a page marker close enough to any target term for 650-char evidence windows."""
    clean = _safe_text(text)
    if not clean:
        return []
    out: list[str] = []
    cursor = 0
    while cursor < len(clean):
        end = min(len(clean), cursor + max(200, int(chunk_chars)))
        if end < len(clean):
            split = clean.rfind(" ", cursor, end)
            if split > cursor + 120:
                end = split
        part = clean[cursor:end].strip()
        if part:
            out.append(f"[[OCR_PAGE:{page_number}]] {part}")
        cursor = max(end, cursor + 1)
    return out


def ocr_page_numbers_from_text(value: str) -> tuple[int, ...]:
    return tuple(sorted({int(match) for match in PAGE_MARKER_RE.findall(str(value or ""))}))


def _ocr_one_image(path: Path, page_number: int, languages: str, psm: int, timeout_seconds: int) -> OCRPage:
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            [
                "tesseract",
                str(path),
                "stdout",
                "-l",
                languages,
                "--oem",
                "1",
                "--psm",
                str(int(psm)),
            ],
            capture_output=True,
            text=True,
            timeout=max(5, int(timeout_seconds)),
            check=False,
        )
        text = _safe_text(proc.stdout or "")
        if proc.returncode != 0 and not text:
            status = "OCR failed: " + _safe_text(proc.stderr or f"exit={proc.returncode}")[:240]
        elif text:
            status = "OCR text extracted"
        else:
            status = "OCR empty"
    except subprocess.TimeoutExpired:
        text = ""
        status = f"OCR timeout after {timeout_seconds}s"
    except Exception as exc:
        text = ""
        status = f"OCR failed: {exc}"
    duration_ms = int((time.perf_counter() - started) * 1000)
    try:
        image_bytes = int(path.stat().st_size)
    except Exception:
        image_bytes = 0
    return OCRPage(page_number, text, status, duration_ms, image_bytes)


def ocr_pdf_bytes(
    data: bytes,
    *,
    languages: str = DEFAULT_OCR_LANGUAGES,
    dpi: int = DEFAULT_OCR_DPI,
    max_pages: int = DEFAULT_OCR_MAX_PAGES,
    workers: int = DEFAULT_OCR_WORKERS,
    psm: int = 6,
    max_chars: int = 320_000,
    render_timeout_seconds: int = 180,
    page_timeout_seconds: int = 35,
) -> PDFOCRResult:
    if not data or data.lstrip()[:5] != b"%PDF-":
        return PDFOCRResult("", "OCR not run", False, "input is not PDF bytes", languages, 0, 0, 0, 0, ())

    runtime_ok, runtime_note = ocr_runtime_status(languages)
    try:
        page_count = len(PdfReader(BytesIO(data)).pages)
    except Exception as exc:
        return PDFOCRResult("", "OCR not run", runtime_ok, f"cannot read PDF page count: {exc}", languages, 0, 0, 0, 0, ())
    attempted = min(page_count, max(1, int(max_pages)))
    if not runtime_ok:
        return PDFOCRResult("", "OCR unavailable", False, runtime_note, languages, page_count, attempted, 0, attempted, ())

    dpi = max(120, min(int(dpi), 260))
    workers = max(1, min(int(workers), 4))
    with tempfile.TemporaryDirectory(prefix="trecapital_ch8_ocr_") as tmp:
        root = Path(tmp)
        pdf_path = root / "input.pdf"
        prefix = root / "page"
        pdf_path.write_bytes(data)
        try:
            render = subprocess.run(
                [
                    "pdftoppm",
                    "-f",
                    "1",
                    "-l",
                    str(attempted),
                    "-r",
                    str(dpi),
                    "-jpeg",
                    "-gray",
                    str(pdf_path),
                    str(prefix),
                ],
                capture_output=True,
                text=True,
                timeout=max(30, int(render_timeout_seconds)),
                check=False,
            )
        except subprocess.TimeoutExpired:
            return PDFOCRResult("", "OCR render timeout", True, "pdftoppm render timeout", languages, page_count, attempted, 0, attempted, ())
        except Exception as exc:
            return PDFOCRResult("", "OCR render failed", True, f"pdftoppm failed: {exc}", languages, page_count, attempted, 0, attempted, ())
        if render.returncode != 0:
            note = _safe_text(render.stderr or f"pdftoppm exit={render.returncode}")[:400]
            return PDFOCRResult("", "OCR render failed", True, note, languages, page_count, attempted, 0, attempted, ())

        images = sorted(root.glob("page-*.jpg"))
        if not images:
            return PDFOCRResult("", "OCR render produced no pages", True, "pdftoppm produced no JPEG pages", languages, page_count, attempted, 0, attempted, ())

        page_jobs: list[tuple[int, Path]] = []
        for idx, image in enumerate(images[:attempted], start=1):
            match = re.search(r"-(\d+)\.jpg$", image.name)
            page_number = int(match.group(1)) if match else idx
            page_jobs.append((page_number, image))

        pages: list[OCRPage] = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(_ocr_one_image, image, page_number, languages, psm, page_timeout_seconds): page_number
                for page_number, image in page_jobs
            }
            for future in as_completed(futures):
                pages.append(future.result())
        pages.sort(key=lambda item: item.page_number)

    chunks: list[str] = []
    for page in pages:
        if page.text:
            chunks.extend(_page_chunks(page.text, page.page_number))
        if sum(len(part) for part in chunks) >= max_chars:
            break
    text = _safe_text(" ".join(chunks))[:max_chars]
    successful = sum(1 for page in pages if page.text)
    failed = max(0, attempted - successful)
    method = f"Tesseract OCR {languages} via pdftoppm {dpi}dpi ({successful}/{attempted} page(s) with text)"
    note = runtime_note if text else f"{runtime_note}; OCR produced no text"
    return PDFOCRResult(text, method, True, note, languages, page_count, attempted, successful, failed, tuple(pages))


__all__ = [
    "DEFAULT_OCR_DPI",
    "DEFAULT_OCR_LANGUAGES",
    "DEFAULT_OCR_MAX_PAGES",
    "DEFAULT_OCR_WORKERS",
    "OCRPage",
    "PAGE_MARKER_RE",
    "PDFOCRResult",
    "ocr_page_numbers_from_text",
    "ocr_pdf_bytes",
    "ocr_runtime_status",
]
