from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "modules" / "deep_company_analysis" / "chapter5_evidence.py"
text = TARGET.read_text(encoding="utf-8")

marker = 'QUESTIONS = ("Q21", "Q22", "Q23", "Q24", "Q25", "Q26")\n'
block = '''# Chapter 5 keeps the shared Chapter-2 trusted source registry, but adds resilient DGC fallbacks\n# for operating-health research. The 2025 annual-report PDF endpoint can intermittently return an\n# HTML/WAF body to non-browser clients; these additional first-party sources prevent one endpoint\n# from becoming a single point of failure without introducing a parallel financial source.\nCHAPTER5_OFFICIAL_PAGES = {**CHAPTER2_OFFICIAL_PAGES}\nCHAPTER5_OFFICIAL_PAGES["DGC"] = tuple(CHAPTER2_OFFICIAL_PAGES.get("DGC", ())) + (\n    ("ĐHĐCĐ thường niên 2025", "https://ducgiangchem.vn/9329-2/"),\n    ("Báo cáo thường niên 2025 — trang công bố", "https://ducgiangchem.vn/bao-cao-thuong-nien-nam-2025/"),\n)\n\nCHAPTER5_OFFICIAL_PDFS = {**CHAPTER2_OFFICIAL_PDFS}\nCHAPTER5_OFFICIAL_PDFS["DGC"] = tuple(CHAPTER2_OFFICIAL_PDFS.get("DGC", ())) + (\n    (\n        "Tài liệu ĐHĐCĐ 2025 — kế hoạch SXKD và đầu tư",\n        "https://ducgiangchem.vn/wp-content/uploads/2025/03/20250303-DGC-CBTT-NQ-HDQT-thong-qua-tai-lieu-hop-DHDCD-thuong-nien-2025.pdf",\n    ),\n    (\n        "Báo cáo thường niên 2024 — fallback lịch sử gần nhất",\n        "https://ducgiangchem.vn/wp-content/uploads/2025/03/20250314-DGC-Bao-cao-thuong-nien-Annual-Report-2024.pdf",\n    ),\n)\n\n'''
if "CHAPTER5_OFFICIAL_PDFS" not in text:
    if marker not in text:
        raise SystemExit("chapter5_evidence.py: question marker not found")
    text = text.replace(marker, block + marker, 1)

text = text.replace("CHAPTER2_OFFICIAL_PAGES.get(ticker, ())", "CHAPTER5_OFFICIAL_PAGES.get(ticker, ())")
text = text.replace("CHAPTER2_OFFICIAL_PDFS.get(ticker, ())", "CHAPTER5_OFFICIAL_PDFS.get(ticker, ())")

TARGET.write_text(text, encoding="utf-8")
print("Applied Chapter 5 Phase 5D official-source resilience hotfix")
