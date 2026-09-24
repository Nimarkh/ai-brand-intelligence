"""Safe report filenames and storage paths.

Filesystem locations are derived from the report UUID and REPORTS_DIR.
User-supplied strings are never used as path segments.
"""

from __future__ import annotations

import re
from pathlib import Path
from uuid import UUID

from app.core.config import settings

_FILENAME = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(pdf|json)$"
)
_SLUG = re.compile(r"[^A-Za-z0-9]+")


class UnsafeReportPath(ValueError):
    """A report path escaped the configured storage directory."""


def reports_directory() -> Path:
    root = Path(settings.REPORTS_DIR).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def stored_pdf_name(report_id: UUID) -> str:
    return f"{report_id}.pdf"


def stored_summary_name(report_id: UUID) -> str:
    return f"{report_id}.json"


def pdf_path(report_id: UUID) -> Path:
    return _contained(stored_pdf_name(report_id))


def summary_path(report_id: UUID) -> Path:
    return _contained(stored_summary_name(report_id))


def delete_report_files(report_id: UUID) -> None:
    """Remove only this report's PDF and summary. Other reports stay in place."""
    for path in (pdf_path(report_id), summary_path(report_id)):
        if path.is_file():
            path.unlink()


def report_title(brand_name: str) -> str:
    cleaned = "".join(ch for ch in (brand_name or "") if ch.isprintable())
    cleaned = " ".join(cleaned.split())
    if not cleaned:
        cleaned = "Brand"
    return f"{cleaned} — Audit Intelligence Report"[:500]


def download_filename(brand_name: str) -> str:
    """ASCII Content-Disposition name. Slashes and control characters are removed."""
    slug = _SLUG.sub("-", brand_name or "").strip("-")[:48]
    if not slug:
        slug = "audit"
    return f"{slug}-audit-intelligence-report.pdf"


def redact_secrets(text: str | None) -> str:
    if not text:
        return ""
    cleaned = text
    for secret in (
        settings.OPENAI_API_KEY or "",
        settings.JWT_SECRET or "",
    ):
        if len(secret) >= 8 and secret in cleaned:
            cleaned = cleaned.replace(secret, "[redacted]")
    try:
        from urllib.parse import urlsplit

        password = urlsplit(settings.DATABASE_URL).password
        if password and len(password) >= 4 and password in cleaned:
            cleaned = cleaned.replace(password, "[redacted]")
    except ValueError:
        pass
    return cleaned


def _contained(name: str) -> Path:
    if not _FILENAME.match(name):
        raise UnsafeReportPath("Report filename is not a report id.")
    root = reports_directory()
    path = (root / name).resolve()
    if path.parent != root:
        raise UnsafeReportPath("Report path escaped the storage directory.")
    return path
