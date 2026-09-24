from __future__ import annotations

import ipaddress
import re
import socket
from collections.abc import Callable
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlsplit, urlunsplit

_ALLOWED_SCHEMES = frozenset({"http", "https"})
_DEFAULT_PORTS = {"http": 80, "https": 443}
_IGNORED_PREFIXES = ("javascript:", "mailto:", "tel:", "data:", "blob:", "file:", "ftp:")
_BLOCKED_HOSTS = frozenset({"localhost", "localhost.localdomain"})
_INTEGER_HOST = re.compile(r"\d{1,10}\Z")
_HEX_HOST = re.compile(r"0x[0-9a-fA-F]+\Z")

Resolver = Callable[[str], list[str]]


def default_resolver(host: str) -> list[str]:
    """Resolve a hostname to IP strings. Raises OSError when resolution fails."""
    infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    addresses: list[str] = []
    for info in infos:
        address = info[4][0]
        if address not in addresses:
            addresses.append(address)
    return addresses


def is_ignorable_reference(raw: str) -> bool:
    """True for links the crawler must not queue."""
    value = raw.strip()
    if not value or value.startswith("#"):
        return True
    lowered = value.lower()
    return lowered.startswith(_IGNORED_PREFIXES)


def normalize_url(raw: str, *, base: str | None = None) -> str | None:
    """Resolve and normalize a URL for visited-set checks and storage.

    Returns None when the URL must be rejected: unsupported scheme, credentials,
    missing host, whitespace, or a fragment-only / non-HTTP reference.

    Rules:
    - Relative references are resolved against ``base``.
    - Scheme and hostname are lowercased. Hosts are stored in IDNA ASCII form.
    - Default ports are removed. Other ports are kept.
    - Fragments are removed.
    - The root path is stored without a trailing slash. Other paths, including
      a trailing slash, are preserved.
    - Query keys and values are preserved. Parameter order is sorted so
      reordered queries collapse to one URL. Spaces stay percent-encoded.
    """
    if raw is None:
        return None
    candidate = raw.strip()
    if not candidate or any(character.isspace() for character in candidate) or "\\" in candidate:
        return None
    if is_ignorable_reference(candidate):
        return None

    try:
        joined = urljoin(base, candidate) if base else candidate
        parts = urlsplit(joined)
    except ValueError:
        return None

    scheme = parts.scheme.lower()
    if scheme not in _ALLOWED_SCHEMES:
        return None
    if parts.username is not None or parts.password is not None:
        return None

    host = parts.hostname
    if host is None or "%" in host:
        return None

    try:
        port = parts.port
    except ValueError:
        return None

    try:
        host_ascii = host.encode("idna").decode("ascii").lower()
    except UnicodeError:
        return None

    if ":" in host_ascii:
        host_ascii = f"[{host_ascii}]"

    if port is None or port == _DEFAULT_PORTS.get(scheme):
        netloc = host_ascii
    else:
        netloc = f"{host_ascii}:{port}"

    path = "" if parts.path in {"", "/"} else parts.path
    query = _normalize_query(parts.query)
    normalized = urlunsplit((scheme, netloc, path, query, ""))
    if len(normalized) > 2048:
        return None
    return normalized


def same_crawl_origin(candidate: str, origin: str) -> bool:
    """True when scheme, hostname, and port all match.

    ``example.com`` does not match ``blog.example.com`` or ``www.example.com``.
    ``https://example.com`` does not match ``http://example.com`` or a non-default port.
    """
    left = urlsplit(candidate)
    right = urlsplit(origin)
    return left.scheme == right.scheme and left.hostname == right.hostname and left.port == right.port


def origin_root(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, "", "", ""))


def endpoint_is_allowed(url: str, resolver: Resolver | None = None) -> bool:
    """Reject local, private, link-local, and otherwise non-public destinations.

    Hostname matching is not enough: a public name can resolve to a private address.
    Resolution failure is treated as not allowed.

    This check is not a full DNS-rebinding defense. The address is resolved before
    the request, and the HTTP client resolves it again when connecting. Those two
    lookups are not pinned to each other.
    """
    parts = urlsplit(url)
    host = parts.hostname
    if host is None:
        return False
    if _host_name_blocked(host):
        return False

    literal = _coerce_ip(host)
    if literal is not None:
        return _is_public(literal)

    resolve = resolver or default_resolver
    try:
        addresses = resolve(host)
    except OSError:
        return False
    if not addresses:
        return False
    return all(_is_public(address) for address in addresses)


def _normalize_query(query: str) -> str:
    if not query:
        return ""
    pairs = parse_qsl(query, keep_blank_values=True, strict_parsing=False)
    pairs.sort()
    return urlencode(pairs, doseq=True, quote_via=quote)


def _host_name_blocked(host: str) -> bool:
    lowered = host.lower().rstrip(".")
    if lowered in _BLOCKED_HOSTS or lowered.endswith(".localhost"):
        return True
    return False


def _coerce_ip(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass
    if _INTEGER_HOST.fullmatch(host):
        value = int(host)
        if 0 <= value <= 0xFFFFFFFF:
            return ipaddress.IPv4Address(value)
    if _HEX_HOST.fullmatch(host):
        value = int(host, 16)
        if 0 <= value <= 0xFFFFFFFF:
            return ipaddress.IPv4Address(value)
    return None


def _is_public(address: str | ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    try:
        parsed = address if isinstance(address, (ipaddress.IPv4Address, ipaddress.IPv6Address)) else ipaddress.ip_address(address)
    except ValueError:
        return False
    if isinstance(parsed, ipaddress.IPv6Address) and parsed.ipv4_mapped is not None:
        parsed = parsed.ipv4_mapped
    # Prefer explicit negatives: some Python builds report multicast as is_global.
    if (
        parsed.is_private
        or parsed.is_loopback
        or parsed.is_link_local
        or parsed.is_multicast
        or parsed.is_unspecified
        or parsed.is_reserved
    ):
        return False
    return bool(parsed.is_global)
