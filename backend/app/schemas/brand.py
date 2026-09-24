from datetime import datetime
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

NAME_MAX_LENGTH = 255
SHORT_TEXT_MAX_LENGTH = 255
URL_MAX_LENGTH = 2048
DESCRIPTION_MAX_LENGTH = 5000

_ALLOWED_SCHEMES = frozenset({"http", "https"})
_DEFAULT_PORTS = {"http": 80, "https": 443}


def normalize_website_url(value: str) -> str:
    """Normalize a public website URL without changing its destination.

    Applied rules:
    - Leading and trailing whitespace is removed. Internal whitespace is rejected.
    - Only http and https are accepted. javascript, data, file, and other schemes are rejected.
    - Userinfo (username or password) is rejected.
    - Scheme and host are lowercased. International hosts are stored in IDNA ASCII form.
    - Default ports (:80 for http, :443 for https) are removed. Other ports are kept.
    - A trailing slash is removed only when the path is empty or exactly "/".
    - A non-root path, including a trailing slash on that path, is preserved.
    - The query string is preserved. The fragment is removed because it is not sent to the server.
    - www is preserved. http is not rewritten to https.
    """
    candidate = value.strip()
    if not candidate or any(character.isspace() for character in candidate) or "\\" in candidate:
        raise ValueError("Enter a valid http or https URL")

    try:
        parts = urlsplit(candidate)
    except ValueError as exc:
        raise ValueError("Enter a valid http or https URL") from exc

    scheme = parts.scheme.lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise ValueError("website_url must use http or https")

    if parts.username is not None or parts.password is not None:
        raise ValueError("website_url must not include credentials")

    host = parts.hostname
    if host is None:
        raise ValueError("website_url must include a host")

    try:
        port = parts.port
    except ValueError as exc:
        raise ValueError("Enter a valid http or https URL") from exc

    try:
        host_ascii = host.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise ValueError("Enter a valid http or https URL") from exc

    if ":" in host_ascii:
        host_ascii = f"[{host_ascii}]"

    if port is None or port == _DEFAULT_PORTS[scheme]:
        netloc = host_ascii
    else:
        netloc = f"{host_ascii}:{port}"

    path = "" if parts.path in {"", "/"} else parts.path
    normalized = urlunsplit((scheme, netloc, path, parts.query, ""))
    if len(normalized) > URL_MAX_LENGTH:
        raise ValueError("website_url is too long")
    return normalized


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class BrandCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(
        min_length=1,
        max_length=NAME_MAX_LENGTH,
        description="Brand display name.",
    )
    website_url: str = Field(
        min_length=1,
        max_length=URL_MAX_LENGTH,
        description="Public http or https website URL. Stored in normalized form.",
    )
    industry: str = Field(
        min_length=1,
        max_length=SHORT_TEXT_MAX_LENGTH,
        description="Industry label.",
    )
    country: str = Field(
        min_length=1,
        max_length=SHORT_TEXT_MAX_LENGTH,
        description="Country the brand operates from.",
    )
    target_market: str = Field(
        min_length=1,
        max_length=SHORT_TEXT_MAX_LENGTH,
        description="Market the brand wants to reach.",
    )
    description: str | None = Field(
        default=None,
        max_length=DESCRIPTION_MAX_LENGTH,
        description="Optional description. Blank values are stored as null.",
    )

    @field_validator("website_url")
    @classmethod
    def validate_website_url(cls, value: str) -> str:
        return normalize_website_url(value)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return _blank_to_none(value)


class BrandUpdate(BaseModel):
    """Explicit update payload. Ownership, id, and timestamps cannot be set."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=NAME_MAX_LENGTH)
    website_url: str | None = Field(default=None, min_length=1, max_length=URL_MAX_LENGTH)
    industry: str | None = Field(default=None, min_length=1, max_length=SHORT_TEXT_MAX_LENGTH)
    country: str | None = Field(default=None, min_length=1, max_length=SHORT_TEXT_MAX_LENGTH)
    target_market: str | None = Field(default=None, min_length=1, max_length=SHORT_TEXT_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=DESCRIPTION_MAX_LENGTH)

    @field_validator("website_url")
    @classmethod
    def validate_website_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_website_url(value)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return _blank_to_none(value)


class BrandResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    website_url: str | None
    industry: str | None
    country: str | None
    target_market: str | None
    description: str | None
    created_at: datetime
    updated_at: datetime


class BrandListResponse(BaseModel):
    items: list[BrandResponse]
    total: int = Field(description="Number of brands owned by the authenticated user.")
