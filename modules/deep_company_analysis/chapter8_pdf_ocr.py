from __future__ import annotations

"""Chapter 8 Phase 8N — bounded OCR fallback for scanned official PDFs.

The OCR layer is intentionally evidence-conservative and runtime-bounded:
* it runs only when the caller explicitly enables it after normal PDF text extraction returns empty;
* it requires local ``pdftoppm`` + Tesseract and the requested language packs;
* long PDFs are sampled in windows across the whole document instead of blindly OCR'ing only page 1..N;
* OCR work is processed in small batches with per-page and per-document wall-clock budgets;
* OCR text is tagged with page provenance markers before candidate extraction;
* OCR output remains ``Candidate — analyst verify`` and is never promoted automatically;
* no analyst conclusion/status/confidence, management score, MOS, Research Gate or signal is written.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import math
import re
import shutil
import subprocess
import tempfile
import time

from pypdf import PdfReader


DEFAULT_OCR_LANGUAGES = "vie+eng"
DEFAULT_OCR_DPI = 140
DEFAULT_OCR_MAX_PAGES = 40
DEFAULT_OCR_WORKERS = 2
DEFAULT_OCR_PSM = 11
DEFAULT_OCR_PAGE_TIMEOUT_SECONDS = 15
DEFAULT_OCR_TIME_BUDGET_SECONDS = 240
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


def select_ocr_page_numbers(page_count: int, max_pages: int) -> tuple[int, ...]:
    """Select bounded page windows across the whole document.

    Short documents are OCR'd fully. Longer documents use 3–8 compact windows spread from the
    beginning through the middle to the end, so management/employee/governance sections are not
    systematically missed while avoiding an unbounded all-page OCR run.
    """
    count = max(0, int(page_count))
    limit = max(1, int(max_pages))
    if count <= 0:
        return ()
    if count <= limit:
        return tuple(range(1, count + 1))

    window_count = min(8, max(3, limit // 6))
    base_width = max(1, limit // window_count)
    widths = [base_width] * window_count
    for idx in range(limit - base_width * window_count):
        widths[idx % window_count] += 1

    selected: set[int] = set()
    for idx, width in enumerate(widths):
        center = 1 if idx == 0 else count if idx == window_count - 1 else int(round(1 + idx * (count - 1) / (window_count - 1)))
        start = max(1, min(count - width + 1, center - width // 2))
        selected.update(range(start, min(count, start + width - 1) + 1))

    # Overlap between windows can leave fewer than ``limit`` pages. Fill the remaining slots with
    # the farthest unselected pages to preserve document-wide coverage deterministically.
    while len(selected) < limit:
        candidates = [page for page in range(1, count + 1) if page not in selected]
        if not candidates:
            break
        if not selected:
            selected.add(candidates[0])
            continue
        page = max(candidates, key=lambda x: min(abs(x - y) for y in selected))
        selected.add(page)
    return tuple(sorted(selected)[:limit])


def _contiguous_runs(pages: tuple[int, ...]) -> list[tuple[int, int]]:
    if not pages:
        return []
    runs: list[tuple[int, int]] = []
    start = prev = pages[0]
    for page in pages[1:]:
        if page == prev + 1:
            prev = page
            continue
        runs.append((start, prev))
        start = prev = page
    runs.append((start, prev))
    return runs


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


def _render_selected_pages(
    pdf_path: Path,
    root: Path,
    selected: tuple[int, ...],
    *,
    dpi: int,
    render_timeout_seconds: int,
    deadline: float,
) -> tuple[list[tuple[int, Path]], list[str]]:
    jobs: list[tuple[int, Path]] = []
    notes: list[str] = []
    for run_idx, (start, end) in enumerate(_contiguous_runs(selected), start=1):
        remaining = max(1, int(deadline - time.perf_counter()))
        if remaining <= 1:
            notes.append("render stopped: OCR document time budget reached")
            break
        prefix = root / f"run{run_idx}"
        try:
            render = subprocess.run(
                [
                    "pdftoppm",
                    "-f",
                    str(start),
                    "-l",
                    str(end),
                    "-r",
                    str(dpi),
                    "-jpeg",
                    "-gray",
                    str(pdf_path),
                    str(prefix),
                ],
                capture_output=True,
                text=True,
                timeout=max(20, min(int(render_timeout_seconds), remaining)),
                check=False,
            )
        except subprocess.TimeoutExpired:
            notes.append(f"render timeout pages {start}-{end}")
            continue
        except Exception as exc:
            notes.append(f"render failed pages {start}-{end}: {exc}")
            continue
        if render.returncode != 0:
            notes.append(f"render failed pages {start}-{end}: {_safe_text(render.stderr)[:180]}")
            continue
        images = sorted(root.glob(f"run{run_idx}-*.jpg"))
        expected_pages = list(range(start, end + 1))
        for page_number, image in zip(expected_pages, images):
            jobs.append((page_number, image))
        if len(images) < len(expected_pages):
            notes.append(f"render incomplete pages {start}-{end}: {len(images)}/{len(expected_pages)}")
    jobs.sort(key=lambda row: row[0])
    return jobs, notes


def ocr_pdf_bytes(
    data: bytes,
    *,
    languages: str = DEFAULT_OCR_LANGUAGES,
    dpi: int = DEFAULT_OCR_DPI,
    max_pages: int = DEFAULT_OCR_MAX_PAGES,
    workers: int = DEFAULT_OCR_WORKERS,
    psm: int = DEFAULT_OCR_PSM,
    max_chars: int = 320_000,
    render_timeout_seconds: int = 90,
    page_timeout_seconds: int = DEFAULT_OCR_PAGE_TIMEOUT_SECONDS,
    time_budget_seconds: int = DEFAULT_OCR_TIME_BUDGET_SECONDS,
) -> PDFOCRResult:
    if not data or data.lstrip()[:5] != b"%PDF-":
        return PDFOCRResult("", "OCR not run", False, "input is not PDF bytes", languages, 0, 0, 0, 0, ())

    runtime_ok, runtime_note = ocr_runtime_status(languages)
    try:
        page_count = len(PdfReader(BytesIO(data)).pages)
    except Exception as exc:
        return PDFOCRResult("", "OCR not run", runtime_ok, f"cannot read PDF page count: {exc}", languages, 0, 0, 0, 0, ())
    selected = select_ocr_page_numbers(page_count, max_pages)
    attempted = len(selected)
    if not runtime_ok:
        return PDFOCRResult("", "OCR unavailable", False, runtime_note, languages, page_count, attempted, 0, attempted, ())

    dpi = max(110, min(int(dpi), 260))
    workers = max(1, min(int(workers), 4))
    psm = max(3, min(int(psm), 13))
    page_timeout_seconds = max(5, min(int(page_timeout_seconds), 45))
    time_budget_seconds = max(30, min(int(time_budget_seconds), 900))
    started = time.perf_counter()
    deadline = started + time_budget_seconds

    pages: list[OCRPage] = []
    render_notes: list[str] = []
    with tempfile.TemporaryDirectory(prefix="trecapital_ch8_ocr_") as tmp:
        root = Path(tmp)
        pdf_path = root / "input.pdf"
        pdf_path.write_bytes(data)
        page_jobs, render_notes = _render_selected_pages(
            pdf_path,
            root,
            selected,
            dpi=dpi,
            render_timeout_seconds=render_timeout_seconds,
            deadline=deadline,
        )
        if not page_jobs:
            note = "; ".join(render_notes) or "pdftoppm produced no selected JPEG pages"
            return PDFOCRResult("", "OCR render produced no pages", True, note, languages, page_count, attempted, 0, attempted, ())

        batch_size = max(workers, workers * 2)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for offset in range(0, len(page_jobs), batch_size):
                if time.perf_counter() >= deadline:
                    break
                batch = page_jobs[offset: offset + batch_size]
                futures = {
                    pool.submit(_ocr_one_image, image, page_number, languages, psm, page_timeout_seconds): page_number
                    for page_number, image in batch
                }
                for future in as_completed(futures):
                    pages.append(future.result())
                if sum(len(page.text) for page in pages if page.text) >= max_chars:
                    break
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
    processed = len(pages)
    elapsed = max(0.0, time.perf_counter() - started)
    method = (
        f"Tesseract OCR {languages} via pdftoppm {dpi}dpi psm={psm} "
        f"({successful}/{attempted} sampled page(s) with text; processed={processed}; {elapsed:.1f}s)"
    )
    note_parts = [runtime_note]
    if render_notes:
        note_parts.extend(render_notes[:4])
    if processed < attempted:
        note_parts.append(f"bounded OCR stopped after {processed}/{attempted} sampled pages")
    if not text:
        note_parts.append("OCR produced no text")
    return PDFOCRResult(text, method, True, "; ".join(note_parts), languages, page_count, attempted, successful, failed, tuple(pages))


__all__ = [
    "DEFAULT_OCR_DPI",
    "DEFAULT_OCR_LANGUAGES",
    "DEFAULT_OCR_MAX_PAGES",
    "DEFAULT_OCR_PAGE_TIMEOUT_SECONDS",
    "DEFAULT_OCR_PSM",
    "DEFAULT_OCR_TIME_BUDGET_SECONDS",
    "DEFAULT_OCR_WORKERS",
    "OCRPage",
    "PAGE_MARKER_RE",
    "PDFOCRResult",
    "ocr_page_numbers_from_text",
    "ocr_pdf_bytes",
    "ocr_runtime_status",
    "select_ocr_page_numbers",
]
