"""Static mobile-contract checks for Weekly Plan V14.

Pixel/device QA still requires a real browser, but these assertions prevent the
most common regressions that previously caused horizontal scrolling or tiny touch
targets on 360-430 px phones.
"""
from pathlib import Path


def main():
    source = Path(__file__).with_name("weekly_plan_v14.py").read_text(encoding="utf-8")
    required = [
        "@media(max-width:430px)",
        "@media(max-width:380px)",
        "min-height:44px",
        "overflow-x:hidden",
        "font-size:16px",
        "grid-template-columns:repeat(2,minmax(0,1fr))",
        "Q1–Q4 được hệ thống xác định như thế nào?",
    ]
    for token in required:
        assert token in source, f"Missing V14 mobile contract: {token}"

    # V14 must not re-introduce a fixed wide table that forces phone scrolling.
    forbidden = ["min-width:680px", "min-width:700px", "width:680px", "width:700px"]
    for token in forbidden:
        assert token not in source, f"V14 reintroduced fixed mobile width: {token}"

    print("KHDN Weekly Plan V14 mobile contract checks: OK")


if __name__ == "__main__":
    main()
