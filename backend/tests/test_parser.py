from app.services.crawler.parser import extract_links, parse_html

PAGE = "https://example.com/docs/guide"


def test_extracts_title_description_canonical_and_headings() -> None:
    html = """
    <html><head>
      <title>  Hello   world  </title>
      <meta name="Description" content="  A   short   summary ">
      <link rel="canonical" href="/home">
    </head><body>
      <h1>One</h1><h1>Two</h1><h2>Sub</h2>
      <p>Visible words here</p>
    </body></html>
    """
    parsed = parse_html(html, PAGE)
    assert parsed.title == "Hello world"
    assert parsed.meta_description == "A short summary"
    assert parsed.canonical_url == "https://example.com/home"
    assert parsed.h1_count == 2
    assert parsed.h2_count == 1
    assert parsed.word_count == 6


def test_word_count_skips_script_style_and_noscript() -> None:
    html = """
    <html><body>
      <script>var hidden = 1;</script>
      <style>.x { color: red; }</style>
      <noscript>enable javascript now</noscript>
      <p>Counted words</p>
    </body></html>
    """
    parsed = parse_html(html, PAGE)
    assert parsed.word_count == 2
    assert parsed.h1_count == 0
    assert parsed.h2_count == 0


def test_missing_elements_stay_null() -> None:
    parsed = parse_html("<html><body><p>Only text</p></body></html>", PAGE)
    assert parsed.title is None
    assert parsed.meta_description is None
    assert parsed.canonical_url is None
    assert parsed.has_schema is False
    assert parsed.schema_types == []
    assert parsed.word_count == 2


def test_json_ld_collects_multiple_and_nested_types() -> None:
    html = """
    <html><head>
      <script type="application/ld+json">
        {"@type": ["Organization", "WebSite"], "publisher": {"@type": "Organization"}}
      </script>
      <script type="application/ld+json">
        {"@graph": [{"@type": "WebPage"}, {"@type": "BreadcrumbList"}]}
      </script>
    </head><body><p>Hi</p></body></html>
    """
    parsed = parse_html(html, PAGE)
    assert parsed.has_schema is True
    assert parsed.schema_types == ["BreadcrumbList", "Organization", "WebPage", "WebSite"]


def test_malformed_json_ld_does_not_fail_parsing() -> None:
    html = """
    <html><head>
      <title>Still here</title>
      <script type="application/ld+json">{not json</script>
    </head><body><h1>Heading</h1></body></html>
    """
    parsed = parse_html(html, PAGE)
    assert parsed.title == "Still here"
    assert parsed.h1_count == 1
    assert parsed.has_schema is False
    assert parsed.schema_types == []


def test_malformed_html_still_extracts_a_title() -> None:
    parsed = parse_html("<html><title>Partial", PAGE)
    assert parsed.title == "Partial"


def test_extract_links_reads_anchors() -> None:
    html = '<a href="/about">About</a><a href="mailto:a@b.c">Mail</a><a>None</a>'
    assert extract_links(html) == ["/about", "mailto:a@b.c"]
