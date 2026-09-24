from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.reports import (
    ReportCreateRequest,
    ReportDetail,
    ReportListResponse,
    serialize_completed_audit,
    serialize_detail,
    serialize_list_item,
)
from app.services.reports.service import (
    AuditNotReportable,
    ReportNotDownloadable,
    ReportNotFound,
    create_report,
    download_report,
    get_report,
    list_reports,
)

router = APIRouter(prefix="/reports", tags=["reports"])

NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")


@router.get(
    "",
    response_model=ReportListResponse,
    summary="List reports owned by the current user",
    responses={401: {"description": "Not authenticated"}, 404: {"description": "Not found"}},
)
def list_owned_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    audit_id: Annotated[UUID | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ReportListResponse:
    try:
        rows, total, audits = list_reports(
            db,
            current_user,
            audit_id=audit_id,
            page=page,
            page_size=page_size,
        )
    except ReportNotFound:
        raise NOT_FOUND from None
    return ReportListResponse(
        items=[serialize_list_item(report, brand_name, audit_date) for report, brand_name, audit_date in rows],
        total=total,
        page=page,
        page_size=page_size,
        completed_audits=[serialize_completed_audit(audit, brand_name) for audit, brand_name in audits],
    )


@router.post(
    "",
    response_model=ReportDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Generate an Audit Intelligence Report",
    responses={
        401: {"description": "Not authenticated"},
        404: {"description": "Not found"},
        422: {"description": "Audit is not completed"},
    },
)
def generate_report(
    payload: ReportCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReportDetail:
    try:
        report, message = create_report(db, current_user, payload.audit_id)
    except ReportNotFound:
        raise NOT_FOUND from None
    except AuditNotReportable as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from None
    stored, brand, audit, summary = get_report(db, current_user, report.id)
    return serialize_detail(stored, brand, audit, summary, message)


@router.get(
    "/{report_id}",
    response_model=ReportDetail,
    summary="Report metadata",
    responses={401: {"description": "Not authenticated"}, 404: {"description": "Not found"}},
)
def read_report(
    report_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReportDetail:
    try:
        report, brand, audit, summary = get_report(db, current_user, report_id)
    except ReportNotFound:
        raise NOT_FOUND from None
    return serialize_detail(report, brand, audit, summary)


@router.get(
    "/{report_id}/download",
    summary="Download a ready report PDF",
    responses={
        401: {"description": "Not authenticated"},
        404: {"description": "Not found"},
        409: {"description": "Report is not ready to download"},
    },
)
def download_ready_report(
    report_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    try:
        path, filename = download_report(db, current_user, report_id)
    except ReportNotFound:
        raise NOT_FOUND from None
    except ReportNotDownloadable as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=filename,
    )
