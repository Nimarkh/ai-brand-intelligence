from app.services.crawler.url_utils import endpoint_is_allowed, normalize_url, same_crawl_origin

ORIGIN = "https://example.com"


def test_relative_and_absolute_urls() -> None:
    assert normalize_url("/about", base="https://example.com/docs/guide") == "https://example.com/about"
    assert normalize_url("../about", base="https://example.com/docs/guide") == "https://example.com/about"
    assert normalize_url("team", base="https://example.com/docs/") == "https://example.com/docs/team"
    assert normalize_url("https://example.com/pricing") == "https://example.com/pricing"


def test_fragments_root_slash_ports_and_case() -> None:
    assert normalize_url("https://example.com/about#pricing") == "https://example.com/about"
    assert normalize_url("https://example.com/") == "https://example.com"
    assert normalize_url("https://example.com") == "https://example.com"
    assert normalize_url("https://example.com:443/docs") == "https://example.com/docs"
    assert normalize_url("http://example.com:80/docs") == "http://example.com/docs"
    assert normalize_url("http://example.com:8080/docs") == "http://example.com:8080/docs"
    assert normalize_url("HTTPS://Example.COM/Path/") == "https://example.com/Path/"


def test_query_strings_are_preserved_and_stable() -> None:
    assert normalize_url("https://example.com/search?b=2&a=1") == "https://example.com/search?a=1&b=2"
    assert normalize_url("https://example.com/search?q=hello%20world") == "https://example.com/search?q=hello%20world"
    assert normalize_url("https://example.com/docs?q=1#section") == "https://example.com/docs?q=1"


def test_credentials_and_unsupported_schemes_are_rejected() -> None:
    assert normalize_url("https://user:secret@example.com/admin") is None
    assert normalize_url("javascript:alert(1)") is None
    assert normalize_url("mailto:person@example.com") is None
    assert normalize_url("tel:+15551212") is None
    assert normalize_url("data:text/html,hi") is None
    assert normalize_url("blob:https://example.com/id") is None
    assert normalize_url("file:///etc/passwd") is None
    assert normalize_url("ftp://example.com/file") is None
    assert normalize_url("#only-fragment", base=ORIGIN) is None


def test_same_host_is_accepted_and_other_hosts_are_rejected() -> None:
    assert same_crawl_origin("https://example.com/about", ORIGIN) is True
    assert same_crawl_origin("https://example.com", ORIGIN) is True
    assert same_crawl_origin("https://other-site.com/", ORIGIN) is False
    assert same_crawl_origin("https://blog.example.com/", ORIGIN) is False
    assert same_crawl_origin("https://www.example.com/", ORIGIN) is False
    assert same_crawl_origin("http://example.com/", ORIGIN) is False
    assert same_crawl_origin("https://example.com:8443/", ORIGIN) is False


def test_private_and_local_destinations_are_blocked() -> None:
    public = lambda _host: ["93.184.216.34"]
    private = lambda _host: ["10.1.2.3"]
    mixed = lambda _host: ["93.184.216.34", "127.0.0.1"]

    assert endpoint_is_allowed("https://example.com/about", public) is True
    assert endpoint_is_allowed("https://example.com/about", private) is False
    assert endpoint_is_allowed("https://example.com/about", mixed) is False
    assert endpoint_is_allowed("https://example.com/about", lambda _host: (_ for _ in ()).throw(OSError("dns"))) is False

    for url in (
        "http://127.0.0.1/",
        "http://127.0.0.1:8080/admin",
        "http://localhost/",
        "http://localhost.localdomain/",
        "http://0.0.0.0/",
        "http://10.0.0.8/",
        "http://172.16.0.4/",
        "http://192.168.1.9/",
        "http://169.254.169.254/latest",
        "http://[::1]/",
        "http://[::]/",
        "http://[fe80::1]/",
        "http://[ff02::1]/",
        "http://[::ffff:127.0.0.1]/",
        "http://[::ffff:10.0.0.1]/",
        "http://2130706433/",
        "http://0x7f000001/",
        "http://224.0.0.1/",
        "http://255.255.255.255/",
    ):
        assert endpoint_is_allowed(url, public) is False


def test_dangerous_schemes_rejected() -> None:
    for raw in (
        "gopher://example.com/",
        "dict://example.com/",
        "sftp://example.com/",
        "jar:http://example.com!/",
    ):
        assert normalize_url(raw) is None
