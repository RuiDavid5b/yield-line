from stock_news.processing.html_cleaning import clean_filing_html
from stock_news.processing.routing._periodic import extract_section


def test_strips_basic_html_tags():
    html = "<html><body><p>Revenue grew 20%.</p></body></html>"
    assert clean_filing_html(html) == "Revenue grew 20%."


def test_removes_script_and_style_content_entirely():
    html = """
    <html>
    <head><style>.foo { color: red; }</style></head>
    <body>
    <script>console.log('should not appear');</script>
    <p>Revenue grew 20%.</p>
    </body>
    </html>
    """
    cleaned = clean_filing_html(html)
    assert "color: red" not in cleaned
    assert "should not appear" not in cleaned
    assert "Revenue grew 20%." in cleaned


def test_reproduces_and_fixes_the_real_snps_bug():
    raw_html = (
        "<div><span>Item</span><span>2.</span>"
        "<span>Management&#8217;s Discussion and Analysis</span>"
        "<p>Revenue grew due to strong demand.</p>"
        "<span>Item</span><span>3.</span>"
        "<span>Quantitative and Qualitative Disclosures</span></div>"
    )

    cleaned = clean_filing_html(raw_html)

    section = extract_section(
        cleaned,
        start_pattern=r"Item\s*2\.?\s*Management.s\s+Discussion\s+and\s+Analysis",
        end_pattern=r"Item\s*3\.?\s*Quantitative\s+and\s+Qualitative\s+Disclosures",
    )

    assert section is not None
    assert "Revenue grew due to strong demand." in section


def test_does_not_collapse_adjacent_inline_elements_into_one_word():
    raw_html = "<span>Item</span><span>2.</span><span>Management's Discussion</span>"
    cleaned = clean_filing_html(raw_html)
    assert "Item2." not in cleaned


def test_normalizes_non_breaking_spaces():
    html = "<p>Item&nbsp;2.&nbsp;Management's Discussion</p>"
    cleaned = clean_filing_html(html)
    assert "\xa0" not in cleaned
    assert "Item 2. Management's Discussion" in cleaned


def test_collapses_excessive_blank_lines_but_keeps_paragraph_breaks():
    html = "<p>First section.</p>\n\n\n\n<p>Second section.</p>"
    cleaned = clean_filing_html(html)
    assert "\n\n\n" not in cleaned
    assert "First section." in cleaned
    assert "Second section." in cleaned
