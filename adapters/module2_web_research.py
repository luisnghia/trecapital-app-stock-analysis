from __future__ import annotations

"""Internet research helper for Định giá chuyên sâu.

V23.18 improves evidence quality by:
- searching with both ticker and company name;
- prioritizing official/IR/exchange/finance domains;
- filtering out search-engine placeholder rows such as "DuckDuckGo";
- decoding DuckDuckGo redirect links;
- saving full query audit trail for later verification.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
import json
import re
import time
from urllib.parse import quote_plus, urlparse, parse_qs, unquote

import httpx
import pandas as pd
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 AppleWebKit Chrome/124 Safari/537.36",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
}

PRIORITY_DOMAINS = {
    "masanconsumer.com": "Nguồn doanh nghiệp/IR",
    "masanconsumerholdings.com": "Nguồn doanh nghiệp/IR",
    "masangroup.com": "Nguồn doanh nghiệp/IR",
    "hnx.vn": "Nguồn công bố chính thức",
    "hsx.vn": "Nguồn công bố chính thức",
    "hose.vn": "Nguồn công bố chính thức",
    "upcom.vn": "Nguồn công bố chính thức",
    "ssc.gov.vn": "Nguồn công bố chính thức",
    "vietstock.vn": "Dữ liệu/tin tài chính",
    "finance.vietstock.vn": "Dữ liệu/tin tài chính",
    "cafef.vn": "Dữ liệu/tin tài chính",
    "fireant.vn": "Dữ liệu/tin tài chính",
    "fiintrade.vn": "Dữ liệu/tin tài chính",
    "stockbiz.vn": "Dữ liệu/tin tài chính",
}


KNOWN_COMPANY_DOMAINS = {
    "HPG": ["https://www.hoaphat.com.vn/quan-he-co-dong", "https://www.hoaphat.com.vn/bao-cao-thuong-nien"],
    "MCH": ["https://masanconsumer.com/", "https://www.masangroup.com/investor-relations/"],
    "MSN": ["https://www.masangroup.com/investor-relations/"],
    "VNM": ["https://www.vinamilk.com.vn/vi/quan-he-co-dong"],
    "FPT": ["https://fpt.com/vi/nha-dau-tu"],
    "MWG": ["https://mwg.vn/quan-he-co-dong/"],
    "VCB": ["https://www.vietcombank.com.vn/vi-VN/Nha-dau-tu"],
    "TCB": ["https://techcombank.com/nha-dau-tu"],
    "ACB": ["https://acb.com.vn/nha-dau-tu"],
    "BID": ["https://www.bidv.com.vn/vn/quan-he-nha-dau-tu"],
    "CTG": ["https://www.vietinbank.vn/web/home/vn/investor/"],
    "DGC": ["https://ducgiangchem.vn/quan-he-co-dong/"],
    "RAL": ["https://rangdong.com.vn/quan-he-co-dong"],
    "SCS": ["https://www.scsc.vn/vi/quan-he-co-dong"],
}


@dataclass
class EvidenceResult:
    table: pd.DataFrame
    raw_path: Path | None
    note: str


class WebEvidenceAgent:
    def __init__(self, raw_dir: str | Path):
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def _save_raw(self, ticker: str, payload: Dict[str, Any]) -> Path:
        folder = self.raw_dir / "internet_evidence" / ticker.upper()
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"evidence_{int(time.time())}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    @staticmethod
    def _clean_company_name(company_name: str) -> str:
        name = re.sub(r"\s+", " ", str(company_name or "")).strip()
        for token in ["CTCP", "Công ty Cổ phần", "Công ty cổ phần", "Công ty CP", "CP "]:
            name = name.replace(token, " ")
        return re.sub(r"\s+", " ", name).strip()

    @staticmethod
    def _decode_ddg_url(href: str) -> str:
        if not href:
            return ""
        href = href.strip()
        if href.startswith("//"):
            href = "https:" + href
        try:
            parsed = urlparse(href)
            qs = parse_qs(parsed.query)
            if "uddg" in qs and qs["uddg"]:
                return unquote(qs["uddg"][0])
        except Exception:
            pass
        return href

    @staticmethod
    def _domain(url: str) -> str:
        try:
            netloc = urlparse(url).netloc.lower().replace("www.", "")
            return netloc
        except Exception:
            return ""

    @staticmethod
    def _domain_group(domain: str) -> str:
        for key, group in PRIORITY_DOMAINS.items():
            if domain == key or domain.endswith("." + key):
                return group
        return "Tin tham khảo"

    @staticmethod
    def _tag_from_text(text: str, domain: str = "") -> str:
        t = (text or "").lower()
        tags = []
        domain_group = WebEvidenceAgent._domain_group(domain)
        if domain_group != "Tin tham khảo":
            tags.append(domain_group)
        if any(k in t for k in ["báo cáo thường niên", "annual report", "bctn", "integrated report"]):
            tags.append("BCTN")
        if any(k in t for k in ["báo cáo tài chính", "financial statement", "bctc", "financial report"]):
            tags.append("BCTC")
        if any(k in t for k in ["công bố thông tin", "cbtt", "disclosure", "quan hệ cổ đông", "ir"]):
            tags.append("CBTT/IR")
        if any(k in t for k in ["thị phần", "market share", "dẫn đầu", "leader", "leading"]):
            tags.append("Thị phần")
        if any(k in t for k in ["cạnh tranh", "lợi thế", "competitive", "moat", "thương hiệu", "brand", "phân phối"]):
            tags.append("Moat")
        if any(k in t for k in ["rủi ro", "kiểm toán", "ngoại trừ", "phạt", "lawsuit", "sanction", "risk"]):
            tags.append("Rủi ro")
        return ", ".join(dict.fromkeys(tags)) if tags else "Tin tham khảo"

    @staticmethod
    def _is_bad_result(title: str, url: str, snippet: str) -> bool:
        t = (title or "").strip().lower()
        u = (url or "").strip().lower()
        s = (snippet or "").strip().lower()
        if not t and not s:
            return True
        if t in {"duckduckgo", "bing", "google"}:
            return True
        if u in {"/html/", "html/", ""} and t in {"duckduckgo", ""}:
            return True
        if "duckduckgo.com/html" in u or "lite.duckduckgo.com/lite" in u:
            return True
        return False

    def _search_duckduckgo(self, client: httpx.Client, q: str, max_results: int) -> tuple[list[dict], dict]:
        urls = [
            "https://duckduckgo.com/html/?q=" + quote_plus(q),
            "https://lite.duckduckgo.com/lite/?q=" + quote_plus(q),
        ]
        out: list[dict] = []
        q_payload: Dict[str, Any] = {"query": q, "urls": urls, "items": [], "errors": []}
        for url in urls:
            try:
                resp = client.get(url)
                q_payload.setdefault("status_codes", []).append({"url": url, "status_code": resp.status_code})
                soup = BeautifulSoup(resp.text, "html.parser")
                candidates = soup.select(".result") or soup.select("tr") or []
                # Fallback: anchors with non-navigation href.
                if not candidates:
                    candidates = soup.find_all("a", href=True)
                for item in candidates:
                    a = item.select_one("a.result__a") if hasattr(item, "select_one") else None
                    if a is None and getattr(item, "name", "") == "a":
                        a = item
                    if a is None:
                        # lite DDG often stores result anchors inside td.
                        aa = item.find_all("a", href=True) if hasattr(item, "find_all") else []
                        aa = [x for x in aa if x.get_text(" ", strip=True) and not x.get("href", "").startswith("/html")]
                        a = aa[0] if aa else None
                    title = a.get_text(" ", strip=True) if a else ""
                    href = self._decode_ddg_url(a.get("href") if a else "")
                    snippet_el = item.select_one(".result__snippet") if hasattr(item, "select_one") else None
                    snippet = snippet_el.get_text(" ", strip=True) if snippet_el else item.get_text(" ", strip=True)[:500]
                    snippet = re.sub(r"\s+", " ", snippet)
                    title = re.sub(r"\s+", " ", title)
                    if self._is_bad_result(title, href, snippet):
                        continue
                    domain = self._domain(href)
                    row = {
                        "Nhóm thông tin": self._tag_from_text(f"{title} {snippet}", domain),
                        "Tiêu đề": title[:240],
                        "Nguồn/URL": href,
                        "Tên miền": domain,
                        "Trích yếu": snippet[:650],
                        "Trạng thái": "Tìm thấy",
                        "Gợi ý sử dụng": self._usage_hint(domain),
                        "Truy vấn": q,
                    }
                    if row not in out:
                        out.append(row)
                    if len(out) >= max_results:
                        break
            except Exception as exc:
                q_payload["errors"].append({"url": url, "error": str(exc)})
            if len(out) >= max_results:
                break
        q_payload["items"] = out
        return out, q_payload

    @staticmethod
    def _usage_hint(domain: str) -> str:
        group = WebEvidenceAgent._domain_group(domain)
        if group == "Nguồn doanh nghiệp/IR":
            return "Ưu tiên cao: dùng để kiểm tra BCTN, chiến lược, thị phần, hệ thống phân phối, rủi ro và giải trình của doanh nghiệp."
        if group == "Nguồn công bố chính thức":
            return "Ưu tiên rất cao: dùng để đối chiếu BCTC/CBTT chính thức trước khi kết luận."
        if group == "Dữ liệu/tin tài chính":
            return "Nguồn tham khảo tốt: dùng để đối chiếu dữ liệu/tin tức, nhưng vẫn cần kiểm tra lại với BCTC/CBTT gốc."
        return "Dùng làm bằng chứng định tính phụ; cần kiểm tra độ tin cậy và đối chiếu nguồn chính thức."


    def _search_bing(self, client: httpx.Client, q: str, max_results: int) -> tuple[list[dict], dict]:
        """Fallback search via Bing HTML. It is only used when DuckDuckGo is blocked/empty."""
        url = "https://www.bing.com/search?q=" + quote_plus(q)
        out: list[dict] = []
        q_payload: Dict[str, Any] = {"query": q, "urls": [url], "items": [], "errors": []}
        try:
            resp = client.get(url)
            q_payload.setdefault("status_codes", []).append({"url": url, "status_code": resp.status_code})
            soup = BeautifulSoup(resp.text, "html.parser")
            for item in soup.select("li.b_algo"):
                a = item.select_one("h2 a") or item.select_one("a")
                if not a:
                    continue
                title = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
                href = self._decode_ddg_url(a.get("href", ""))
                snippet_el = item.select_one("p")
                snippet = snippet_el.get_text(" ", strip=True) if snippet_el else item.get_text(" ", strip=True)[:500]
                snippet = re.sub(r"\s+", " ", snippet)
                if self._is_bad_result(title, href, snippet):
                    continue
                domain = self._domain(href)
                row = {
                    "Nhóm thông tin": self._tag_from_text(f"{title} {snippet}", domain),
                    "Tiêu đề": title[:240],
                    "Nguồn/URL": href,
                    "Tên miền": domain,
                    "Trích yếu": snippet[:650],
                    "Trạng thái": "Tìm thấy",
                    "Gợi ý sử dụng": self._usage_hint(domain),
                    "Truy vấn": q,
                }
                out.append(row)
                if len(out) >= max_results:
                    break
        except Exception as exc:
            q_payload["errors"].append({"url": url, "error": str(exc)})
        q_payload["items"] = out
        return out, q_payload

    def _direct_source_rows(self, ticker: str, company_name: str) -> list[dict]:
        """Reliable fallback: direct official/financial pages when search engines are blocked.
        These rows are not treated as final conclusions; they are high-priority links to open/check.
        """
        ticker = ticker.upper().strip()
        clean_name = self._clean_company_name(company_name)
        urls: list[tuple[str, str, str]] = []
        for u in KNOWN_COMPANY_DOMAINS.get(ticker, []):
            urls.append(("Nguồn doanh nghiệp/IR", f"{ticker} - trang IR/quan hệ cổ đông doanh nghiệp", u))
        # Standard financial information pages used as starting points for all VN tickers.
        urls.extend([
            ("Dữ liệu/tin tài chính", f"{ticker} - Vietstock Finance hồ sơ & BCTC", f"https://finance.vietstock.vn/{ticker}"),
            ("Dữ liệu/tin tài chính", f"{ticker} - Vietstock Finance tài chính", f"https://finance.vietstock.vn/{ticker}/tai-chinh.htm"),
            ("Dữ liệu/tin tài chính", f"{ticker} - CafeF công bố thông tin", f"https://cafef.vn/du-lieu/cong-bo-thong-tin.chn?symbol={ticker}"),
            ("Dữ liệu/tin tài chính", f"{ticker} - FireAnt mã chứng khoán", f"https://fireant.vn/ma-chung-khoan/{ticker}"),
            ("Dữ liệu/tin tài chính", f"{ticker} - TradingView financials", f"https://www.tradingview.com/symbols/HOSE-{ticker}/financials-overview/"),
            ("Nguồn công bố chính thức", f"{ticker} - SSC tìm công bố thông tin", f"https://congbothongtin.ssc.gov.vn/faces/NewsSearch"),
            ("Nguồn công bố chính thức", f"{ticker} - HOSE công bố thông tin", f"https://www.hsx.vn/Modules/Listed/Web/Symbols"),
            ("Nguồn công bố chính thức", f"{ticker} - HNX công bố thông tin", f"https://hnx.vn/vi-vn/thong-tin-cong-bo.html"),
        ])
        rows = []
        for group, title, url in urls:
            domain = self._domain(url)
            rows.append({
                "Nhóm thông tin": group,
                "Tiêu đề": title,
                "Nguồn/URL": url,
                "Tên miền": domain,
                "Trích yếu": f"Nguồn ưu tiên để kiểm tra {ticker} {('- ' + clean_name) if clean_name else ''}: BCTC/BCTN/CBTT, thông tin IR, tin tài chính, thị phần và rủi ro. Mở link để đối chiếu với dữ liệu trong app.",
                "Trạng thái": "Link nguồn ưu tiên",
                "Gợi ý sử dụng": self._usage_hint(domain),
                "Truy vấn": "Nguồn trực tiếp theo mã cổ phiếu và tên doanh nghiệp",
                "Điểm phù hợp": 30 if group == "Nguồn công bố chính thức" else 26 if group == "Nguồn doanh nghiệp/IR" else 18,
            })
        return rows

    def _build_queries(self, ticker: str, company_name: str) -> list[str]:
        clean_name = self._clean_company_name(company_name)
        name_or_ticker = clean_name or company_name or ticker
        queries = [
            f'"{ticker}" "{name_or_ticker}" báo cáo thường niên',
            f'"{ticker}" "{name_or_ticker}" báo cáo tài chính',
            f'"{ticker}" "{name_or_ticker}" công bố thông tin',
            f'"{ticker}" "{name_or_ticker}" lợi thế cạnh tranh thị phần',
            f'"{ticker}" "{name_or_ticker}" rủi ro kiểm toán',
            f'"{ticker}" "{name_or_ticker}" báo cáo phân tích',
            f'site:hnx.vn "{ticker}" "{name_or_ticker}"',
            f'site:upcom.vn "{ticker}" "{name_or_ticker}"',
            f'site:finance.vietstock.vn "{ticker}"',
            f'site:cafef.vn "{ticker}" "{name_or_ticker}"',
            f'site:fireant.vn "{ticker}"',
        ]
        if clean_name:
            queries += [
                f'"{clean_name}" "annual report"',
                f'"{clean_name}" "investor relations"',
                f'"{clean_name}" "market share"',
            ]
        return list(dict.fromkeys([q for q in queries if q.strip()]))

    @staticmethod
    def _score_row(row: dict, ticker: str, company_name: str) -> int:
        text = f"{row.get('Tiêu đề','')} {row.get('Trích yếu','')} {row.get('Nguồn/URL','')}".lower()
        score = 0
        if ticker.lower() in text:
            score += 10
        for token in re.findall(r"[A-Za-zÀ-ỹ0-9]+", company_name.lower()):
            if len(token) >= 4 and token in text:
                score += 2
        domain = row.get("Tên miền", "")
        if WebEvidenceAgent._domain_group(domain) == "Nguồn công bố chính thức":
            score += 20
        elif WebEvidenceAgent._domain_group(domain) == "Nguồn doanh nghiệp/IR":
            score += 18
        elif WebEvidenceAgent._domain_group(domain) == "Dữ liệu/tin tài chính":
            score += 12
        if any(k in text for k in ["báo cáo tài chính", "bctc", "financial statement"]):
            score += 8
        if any(k in text for k in ["báo cáo thường niên", "annual report", "bctn"]):
            score += 8
        if any(k in text for k in ["thị phần", "market share", "lợi thế", "moat", "phân phối", "thương hiệu"]):
            score += 5
        return score

    def search(self, ticker: str, company_name: str = "", max_results_per_query: int = 5) -> EvidenceResult:
        ticker = ticker.upper().strip()
        company_name = re.sub(r"\s+", " ", str(company_name or "")).strip()
        # Giới hạn số truy vấn để app không bị treo trên mạng công ty/search engine bị chặn.
        queries = self._build_queries(ticker, company_name)[:2]
        rows: List[Dict[str, Any]] = []
        payload: Dict[str, Any] = {"ticker": ticker, "company_name": company_name, "created_at": datetime.now().isoformat(), "queries": []}
        with httpx.Client(headers=HEADERS, timeout=httpx.Timeout(1.5, connect=0.8), follow_redirects=True) as client:
            for q in queries:
                found, q_payload = self._search_duckduckgo(client, q, max_results_per_query)
                # DuckDuckGo often returns HTTP 202/empty body on corporate networks; use Bing fallback for that query.
                if not found:
                    found_bing, bing_payload = self._search_bing(client, q, max_results_per_query)
                    q_payload["fallback_bing"] = bing_payload
                    found = found_bing
                payload["queries"].append(q_payload)
                rows.extend(found)
        # Always add direct trusted source links so the evidence tab remains usable even when search engines block scraping.
        rows.extend(self._direct_source_rows(ticker, company_name))
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.drop_duplicates(subset=["Tiêu đề", "Nguồn/URL"]).copy()
            df["Điểm phù hợp"] = df.apply(lambda r: self._score_row(r.to_dict(), ticker, company_name), axis=1)
            df = df.sort_values(["Điểm phù hợp", "Nhóm thông tin"], ascending=[False, True]).reset_index(drop=True)
            # Keep only rows that are at least somewhat related; preserve official/finance sources.
            df = df[(df["Điểm phù hợp"] >= 8) | (df["Nhóm thông tin"].astype(str).str.contains("Nguồn công bố|Nguồn doanh nghiệp|Dữ liệu", na=False))]
        if df.empty:
            df = pd.DataFrame([
                {
                    "Nhóm thông tin": "Cần kiểm tra thủ công",
                    "Tiêu đề": f"Chưa tìm được bằng chứng chất lượng cao cho {ticker} - {company_name}",
                    "Nguồn/URL": "",
                    "Tên miền": "",
                    "Trích yếu": "Công cụ tìm kiếm không trả kết quả đủ tin cậy hoặc mạng đang chặn. Hãy ưu tiên website IR doanh nghiệp, HNX/UPCoM/HOSE/SSC, Vietstock/CafeF/FireAnt và báo cáo thường niên gốc.",
                    "Trạng thái": "Chưa đủ chất lượng",
                    "Gợi ý sử dụng": "Không dùng kết quả này làm bằng chứng; cần nhập/link thủ công trong lần kiểm tra tiếp theo.",
                    "Truy vấn": "; ".join(queries[:3]),
                    "Điểm phù hợp": 0,
                }
            ])
        raw_path = self._save_raw(ticker, payload)
        return EvidenceResult(df.reset_index(drop=True), raw_path, f"Đã lưu nhật ký web research: {raw_path}")
