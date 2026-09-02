from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"Expected block not found in {path}: {old[:160]}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_ambiguous_country_aliases() -> None:
    path = ROOT / "modules" / "deep_company_analysis" / "chapter2_auto.py"
    replace_once(
        path,
        '    "Hoa Kỳ": ("hoa kỳ", "hoa ky", "mỹ", "my", "united states", "u.s.", "usa"),',
        '    "Hoa Kỳ": ("hoa kỳ", "hoa ky", "united states", "u.s.", "usa", "thị trường mỹ", "thi truong my", "tại mỹ", "tai my", "sang mỹ", "sang my"),',
    )
    replace_once(
        path,
        '    "Lào": ("lào", "lao", "laos"),',
        '    "Lào": ("laos", "thị trường lào", "thi truong lao", "tại lào", "tai lao", "sang lào", "sang lao"),',
    )
    replace_once(
        path,
        '    "Úc": ("úc", "uc", "australia"),',
        '    "Úc": ("australia", "australian", "thị trường úc", "thi truong uc", "tại úc", "tai uc", "sang úc", "sang uc"),',
    )
    replace_once(
        path,
        '    "Đức": ("đức", "duc", "germany", "german"),',
        '    "Đức": ("germany", "german", "thị trường đức", "thi truong duc", "tại đức", "tai duc", "sang đức", "sang duc", "ở đức", "o duc"),',
    )


def patch_pdf_fallback_quality() -> None:
    path = ROOT / "modules" / "deep_company_analysis" / "chapter2_evidence.py"
    old = '''            interim = pd.DataFrame(rows)\n            sections = base.classify_evidence(interim) if not interim.empty else {"Q6": pd.DataFrame()}\n            # Parse the official annual report only when Q6 is still weak. This avoids a large PDF\n            # download on every refresh while giving Chapter 2 a source-first fallback for geography/FX.\n            q6 = sections.get("Q6", pd.DataFrame())\n            q6_quality = 0 if not isinstance(q6, pd.DataFrame) else len(q6)\n            if q6_quality < 2 and CHAPTER2_OFFICIAL_PDFS.get(safe):\n                pdf_rows, pdf_audit = self._fetch_official_pdf_rows(safe, client)\n                rows.extend(pdf_rows)\n                audit["official_pdf"] = pdf_audit\n'''
    new = '''            interim = pd.DataFrame(rows)\n            sections = base.classify_evidence(interim) if not interim.empty else {"Q6": pd.DataFrame()}\n            # Q6 quality cannot be measured by row-count alone: generic phrases such as "ngoài nước"\n            # may create several Q6 rows but still contain no actual geography or currency evidence.\n            # Parse the official annual report when either layer is still missing.\n            q6 = sections.get("Q6", pd.DataFrame())\n            foreign_candidates = base.extract_foreign_market_candidates(q6) if isinstance(q6, pd.DataFrame) else []\n            currency_candidates = base.extract_currency_candidates(q6) if isinstance(q6, pd.DataFrame) else []\n            needs_pdf = not foreign_candidates or not currency_candidates\n            if needs_pdf and CHAPTER2_OFFICIAL_PDFS.get(safe):\n                pdf_rows, pdf_audit = self._fetch_official_pdf_rows(safe, client)\n                rows.extend(pdf_rows)\n                audit["official_pdf"] = pdf_audit\n'''
    replace_once(path, old, new)


def main() -> None:
    patch_ambiguous_country_aliases()
    patch_pdf_fallback_quality()
    print("Chapter 2 Q6 quality patch applied.")


if __name__ == "__main__":
    main()
