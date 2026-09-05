from pathlib import Path
import pandas as pd
from modules.deep_company_analysis.table_format import format_numeric, infer_numeric_kind, static_table_html

def test_numeric_contract():
    assert infer_numeric_kind('Doanh thu (tỷ)') == 'amount_bil'
    assert infer_numeric_kind('ROIC canonical %') == 'percent'
    assert infer_numeric_kind('Debt/EBITDA (x)') == 'ratio'
    assert infer_numeric_kind('CCC ngày') == 'days'
    assert format_numeric(1234.56, 'amount_bil') == '1,235'
    assert format_numeric(12.345, 'percent') == '12.3%'
    assert format_numeric(2.345, 'ratio') == '2.3x'
    assert format_numeric(45.67, 'days') == '45.7'

def test_html_contract():
    df = pd.DataFrame([
        {'Kỳ':'2025','FCF (tỷ)':-123.6,'Tăng trưởng DT %':10.25,'Debt/EBITDA (x)':2.34},
        {'Kỳ':'2026','FCF (tỷ)':250.4,'Tăng trưởng DT %':-5.44,'Debt/EBITDA (x)':3.11},
    ])
    html = static_table_html(df)
    assert 'table-layout:fixed' in html
    assert 'white-space:normal' in html
    assert 'overflow-wrap:anywhere' in html
    assert 'rgba(185,28,28' in html
    assert 'rgba(4,120,87' in html
    assert '-124' in html and '250' in html
    assert '10.2%' in html and '-5.4%' in html and '2.3x' in html

def test_no_legacy_static_dataframes_ch2_ch5():
    root = Path(__file__).resolve().parent
    files = ['chapter2.py','chapter2_page_support.py','chapter3.py','chapter3_page_support.py','chapter4.py','chapter4_page_support.py','chapter5.py','chapter5_page_support.py']
    for name in files:
        text = (root / name).read_text(encoding='utf-8')
        assert 'st.dataframe(' not in text, name
        assert 'render_static_table(' in text, name

def test_ch5_amount_metric_zero_decimals():
    text = (Path(__file__).resolve().parent / 'chapter5_page_support.py').read_text(encoding='utf-8')
    assert '_fmt(latest.get("Nợ vay ròng (tỷ)"), " tỷ", decimals=0)' in text
