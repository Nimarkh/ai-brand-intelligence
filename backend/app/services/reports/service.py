"""Create and retrieve audit intelligence reports.

Generation is synchronous. A READY file is immutable. A later request creates
a new report row and a new file.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit import Audit
from app.models.brand import Brand
from app.models.enums import AuditStatus, ReportStatus
from app.models.report import Report
from app.models.user import User
from app.services.reports.data import build_snapshot
from app.services.reports.models import REPORT_SECTIONS, ReportSnapshot
from app.services.reports.renderer import render_pdf
from app.services.reports.security import (
    delete_report_files,
    download_filename,
    pdf_path,
    report_title,
    stored_pdf_name,
    summary_path,
)

logger = logging.getLogger("app.reports")

FAILED_MESSAGE = "The report could not be generated. Please try again."
INCOMPLETE_MESSAGE = "Complete the audit before generating a report."
GENERATING_MESSAGE = "This report is still generating."
FAILED_DOWNLOAD_MESSAGE = "This report failed and cannot be downloaded."
MISSING_FILE_MESSAGE = "The report file is not available."


class ReportNotFound(Exception):
    """The report or audit is missing or belongs to another user."""


class AuditNotReportable(Exception):
    def __init__(self) -> None:
        super().__init__(INCOMPLETE_MESSAGE)


class ReportNotDownloadable(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


def create_report(db: Session, user: User, audit_id: UUID) -> tuple[Report, str | None]:
    audit, brand = _owned_audit(db, user, audit_id)
    if audit.status != AuditStatus.COMPLETED:
        raise AuditNotReportable()

    report = Report(
        audit_id=audit.id,
        title=report_title(brand.name),
        status=ReportStatus.GENERATING,
        file_path=None,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    try:
        generated_at = datetime.now(timezone.utc)
        snapshot = build_snapshot(db, audit, brand, generated_at=generated_at)
        render_pdf(snapshot, pdf_path(report.id))
        _write_summary(report.id, snapshot)
        report.status = ReportStatus.READY
        report.file_path = stored_pdf_name(report.id)
        report.completed_at = generated_at
        db.commit()
        db.refresh(report)
        return report, None
    except Exception:
        logger.exception("report_generation_failed report_id=%s", report.id)
        db.rollback()
        failed = db.get(Report, report.id)
        if failed is None:
            raise
        delete_report_files(failed.id)
        failed.status = ReportStatus.FAILED
        failed.file_path = None
        failed.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(failed)
        return failed, FAILED_MESSAGE


def list_reports(
    db: Session,
    user: User,
    *,
    audit_id: UUID | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[tuple[Report, str, datetime | None]], int, list[tuple[Audit, str]]]:
    if audit_id is not None:
        _owned_audit(db, user, audit_id)

    filters = [Brand.owner_id == user.id]
    if audit_id is not None:
        filters.append(Report.audit_id == audit_id)

    total = db.scalar(
        select(func.count())
        .select_from(Report)
        .join(Audit, Report.audit_id == Audit.id)
        .join(Brand, Audit.brand_id == Brand.id)
        .where(*filters)
    )
    rows = db.execute(
        select(Report, Brand.name, Audit.completed_at)
        .join(Audit, Report.audit_id == Audit.id)
        .join(Brand, Audit.brand_id == Brand.id)
        .where(*filters)
        .order_by(Report.created_at.desc(), Report.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    audits = db.execute(
        select(Audit, Brand.name)
        .join(Brand, Audit.brand_id == Brand.id)
        .where(Brand.owner_id == user.id, Audit.status == AuditStatus.COMPLETED)
        .order_by(Audit.completed_at.desc(), Audit.created_at.desc(), Audit.id.desc())
        .limit(100)
    ).all()
    return list(rows), int(total or 0), list(audits)


def get_report(db: Session, user: User, report_id: UUID) -> tuple[Report, Brand, Audit, dict | None]:
    row = db.execute(
        select(Report, Brand, Audit)
        .join(Audit, Report.audit_id == Audit.id)
        .join(Brand, Audit.brand_id == Brand.id)
        .where(Report.id == report_id, Brand.owner_id == user.id)
    ).first()
    if row is None:
        raise ReportNotFound
    report, brand, audit = row
    return report, brand, audit, _read_summary(report.id)


def download_report(db: Session, user: User, report_id: UUID) -> tuple[Path, str]:
    report, brand, _audit, _summary = get_report(db, user, report_id)
    if report.status == ReportStatus.GENERATING:
        raise ReportNotDownloadable(GENERATING_MESSAGE)
    if report.status != ReportStatus.READY:
        raise ReportNotDownloadable(FAILED_DOWNLOAD_MESSAGE)
    path = pdf_path(report.id)
    if not path.is_file():
        raise ReportNotDownloadable(MISSING_FILE_MESSAGE)
    return path, download_filename(brand.name)


def _owned_audit(db: Session, user: User, audit_id: UUID) -> tuple[Audit, Brand]:
    row = db.execute(
        select(Audit, Brand)
        .join(Brand, Audit.brand_id == Brand.id)
        .where(Audit.id == audit_id, Brand.owner_id == user.id)
    ).first()
    if row is None:
        raise ReportNotFound
    return row


def _write_summary(report_id: UUID, snapshot: ReportSnapshot) -> None:
    payload = {
        "brand_name": snapshot.brand.name,
        "website": snapshot.brand.website,
        "audit_date": _iso(snapshot.audit.completed_at or snapshot.audit.created_at),
        "generated_at": _iso(snapshot.generated_at),
        "overall_score": _number(snapshot.overall.score),
        "overall_status": snapshot.overall.status,
        "overall_note": snapshot.overall.note,
        "scores": [
            {
                "key": line.key,
                "label": line.label,
                "score": _number(line.score),
                "status": line.status,
            }
            for line in snapshot.scores
        ],
        "sections": list(REPORT_SECTIONS),
    }
    path = summary_path(report_id)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _read_summary(report_id: UUID) -> dict | None:
    path = summary_path(report_id)
    if not path.is_file():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning("report_summary_unreadable report_id=%s", report_id)
        return None
    if not isinstance(loaded, dict):
        return None
    return loaded


def _number(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()
