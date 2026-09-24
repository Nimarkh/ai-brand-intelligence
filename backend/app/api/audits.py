from collections.abc import Generator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_configured_ai_provider, get_current_user
from app.core.database import get_db
from app.models.brand import Brand
from app.models.user import User
from app.schemas.ai_query import (
    AiQueryDetailResponse,
    AiQueryListResponse,
    AiQueryRunResponse,
    serialize_query_detail,
    serialize_query_list_item,
)
from app.schemas.ai_visibility import AIVisibilityResponse, serialize_visibility
from app.schemas.entity import EntityStrengthResponse, serialize_entity
from app.schemas.recommendation import (
    RecommendationListResponse,
    RecommendationRunResponse,
    serialize_recommendation,
)
from app.schemas.audit import AuditListResponse, AuditResponse, CrawlResponse, serialize_audit
from app.schemas.seo import (
    SeoAnalyzeResponse,
    SeoFindingListResponse,
    serialize_seo_finding,
)
from app.schemas.score import AuditScoreResponse, serialize_score
from app.services import brand_service, crawl_service, seo_analysis_service, score_service
from app.services import ai_visibility_service, entity_service, recommendation_service
from app.services.ai.provider import AIProvider
from app.services.ai.query_engine import (
    InsufficientBrandContextError,
    get_ai_query,
    list_ai_queries,
    run_ai_query_analysis,
)
from app.services.crawler import WebsiteCrawler
from app.services.crawl_service import (
    BrandWebsiteMissingError,
    CrawlAlreadyRunningError,
    CrawlFailedError,
)

router = APIRouter(tags=["audits"])

NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")

AUTH_RESPONSES = {
    401: {"description": "Not authenticated"},
    404: {"description": "Not found"},
}


def get_crawler() -> Generator[WebsiteCrawler, None, None]:
    crawler = crawl_service.build_crawler()
    try:
        yield crawler
    finally:
        crawler.close()


def _require_brand(db: Session, owner_id: UUID, brand_id: UUID) -> Brand:
    brand = brand_service.get_user_brand(db, owner_id, brand_id)
    if brand is None:
        raise NOT_FOUND
    return brand


@router.post(
    "/brands/{brand_id}/audits",
    response_model=AuditResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an audit",
    description=(
        "Create a pending audit for a brand owned by the authenticated user. "
        "Scores stay null. This does not crawl the website or calculate a score. "
        "Unknown brands and brands owned by someone else both return 404."
    ),
    responses=AUTH_RESPONSES,
)
def create_audit(
    brand_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditResponse:
    brand = _require_brand(db, current_user.id, brand_id)
    audit = crawl_service.create_audit(db, brand)
    return serialize_audit(audit, pages_crawled=0)


@router.get(
    "/brands/{brand_id}/audits",
    response_model=AuditListResponse,
    summary="List audits for a brand",
    description=(
        "Return audits for a brand owned by the authenticated user, newest first. "
        "Unknown brands and brands owned by someone else both return 404."
    ),
    responses=AUTH_RESPONSES,
)
def list_audits(
    brand_id: UUID,
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditListResponse:
    brand = _require_brand(db, current_user.id, brand_id)
    audits = crawl_service.list_brand_audits(db, brand.id, limit=limit)
    return AuditListResponse(
        items=[serialize_audit(audit, crawl_service.page_count(db, audit.id)) for audit in audits]
    )


@router.get(
    "/audits/{audit_id}",
    response_model=AuditResponse,
    summary="Get an audit",
    description=(
        "Return one audit whose brand is owned by the authenticated user. "
        "Unknown audits and audits owned by someone else both return 404."
    ),
    responses=AUTH_RESPONSES,
)
def get_audit(
    audit_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditResponse:
    audit = crawl_service.get_owned_audit(db, current_user.id, audit_id)
    if audit is None:
        raise NOT_FOUND
    return serialize_audit(audit, crawl_service.page_count(db, audit.id))


@router.post(
    "/audits/{audit_id}/crawl",
    response_model=CrawlResponse,
    summary="Crawl a brand website",
    description=(
        "Crawl the website of the audit's brand and store factual page data. "
        "Requires the authenticated user to own that brand. "
        "Unknown audits and audits owned by someone else both return 404. "
        "COMPLETED means the crawl finished. It does not mean the site was scored."
    ),
    responses={
        **AUTH_RESPONSES,
        409: {"description": "A crawl is already running for this audit"},
        422: {"description": "The brand has no website URL"},
        500: {"description": "The crawl failed"},
    },
)
def crawl_audit(
    audit_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    crawler: WebsiteCrawler = Depends(get_crawler),
) -> CrawlResponse:
    audit = crawl_service.get_owned_audit(db, current_user.id, audit_id)
    if audit is None:
        raise NOT_FOUND
    brand = audit.brand
    try:
        result = crawl_service.run_crawl(db, audit, brand, crawler)
    except BrandWebsiteMissingError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Add a website URL before starting a crawl.",
        ) from None
    except CrawlAlreadyRunningError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A crawl is already running for this audit.",
        ) from None
    except CrawlFailedError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Website crawl failed. Please try again.",
        ) from None
    return CrawlResponse(
        audit_id=result.audit_id,
        status=result.status,
        pages_crawled=result.pages_crawled,
    )


@router.post(
    "/audits/{audit_id}/analyze-seo",
    response_model=SeoAnalyzeResponse,
    summary="Analyze SEO for a crawled audit",
    description=(
        "Run the deterministic SEO analyzer against stored WebsitePage data. "
        "Replaces existing SeoFinding rows for this audit only. "
        "Does not calculate scores, call an LLM, or crawl the website again. "
        "AuditStatus is unchanged: COMPLETED still means the crawl finished."
    ),
    responses={
        **AUTH_RESPONSES,
    },
)
def analyze_seo(
    audit_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SeoAnalyzeResponse:
    audit = crawl_service.get_owned_audit(db, current_user.id, audit_id)
    if audit is None:
        raise NOT_FOUND
    result = seo_analysis_service.run_seo_analysis(db, audit, audit.brand)
    return SeoAnalyzeResponse(
        audit_id=result.audit_id,
        findings_count=result.findings_count,
        status=result.status,
    )


@router.get(
    "/audits/{audit_id}/seo-findings",
    response_model=SeoFindingListResponse,
    summary="List SEO findings for an audit",
    description=(
        "Return deterministic SEO findings for an owned audit, ordered by severity "
        "(HIGH, MEDIUM, LOW, INFO), then page_id, category, and created_at. "
        "Unknown audits and audits owned by someone else both return 404."
    ),
    responses=AUTH_RESPONSES,
)
def list_seo_findings(
    audit_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SeoFindingListResponse:
    audit = crawl_service.get_owned_audit(db, current_user.id, audit_id)
    if audit is None:
        raise NOT_FOUND
    findings = seo_analysis_service.list_seo_findings(db, audit.id)
    return SeoFindingListResponse(
        items=[serialize_seo_finding(finding) for finding in findings],
        total=len(findings),
    )


@router.post(
    "/audits/{audit_id}/calculate-score",
    response_model=AuditScoreResponse,
    summary="Calculate deterministic audit scores",
    description=(
        "Score stored WebsitePage and SeoFinding data for an owned audit. "
        "Persists website_score, seo_score, and a provisional overall_score. "
        "Does not crawl, re-analyze SEO, call an LLM, or set AI/entity scores. "
        "AuditStatus is unchanged."
    ),
    responses=AUTH_RESPONSES,
)
def calculate_score(
    audit_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditScoreResponse:
    audit = crawl_service.get_owned_audit(db, current_user.id, audit_id)
    if audit is None:
        raise NOT_FOUND
    result = score_service.run_score_calculation(db, audit)
    return serialize_score(result.audit_id, result.result)


@router.get(
    "/audits/{audit_id}/score",
    response_model=AuditScoreResponse,
    summary="Get audit scores",
    description=(
        "Return persisted (or unavailable) scores for an owned audit. "
        "Does not calculate scores. Unknown audits and audits owned by someone else "
        "both return 404."
    ),
    responses=AUTH_RESPONSES,
)
def get_score(
    audit_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditScoreResponse:
    audit = crawl_service.get_owned_audit(db, current_user.id, audit_id)
    if audit is None:
        raise NOT_FOUND
    snapshot = score_service.load_score_snapshot(db, audit)
    return serialize_score(audit.id, snapshot)


@router.post(
    "/audits/{audit_id}/ai-queries/run",
    response_model=AiQueryRunResponse,
    summary="Run AI query analysis",
    description=(
        "Generate a deterministic brand query set, execute each query through the "
        "configured AI provider, and persist successful responses. "
        "Replaces any previous AI query snapshot for this audit. "
        "Does not calculate AI Visibility scores. Does not change AuditStatus. "
        "Partial provider failures are reported in responses_failed."
    ),
    responses={
        **AUTH_RESPONSES,
        422: {"description": "Brand context is insufficient for query generation"},
    },
)
async def run_ai_queries(
    audit_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    provider: AIProvider = Depends(get_configured_ai_provider),
) -> AiQueryRunResponse:
    audit = crawl_service.get_owned_audit(db, current_user.id, audit_id)
    if audit is None:
        raise NOT_FOUND
    try:
        result = await run_ai_query_analysis(db, audit, audit.brand, provider)
    except InsufficientBrandContextError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from None
    return AiQueryRunResponse(
        audit_id=result.audit_id,
        queries_generated=result.queries_generated,
        responses_succeeded=result.responses_succeeded,
        responses_failed=result.responses_failed,
        status=result.status,
    )


@router.get(
    "/audits/{audit_id}/ai-queries",
    response_model=AiQueryListResponse,
    summary="List AI queries for an audit",
    description=(
        "Return the current AI query snapshot for an owned audit. "
        "Unknown audits and audits owned by someone else both return 404."
    ),
    responses=AUTH_RESPONSES,
)
def list_audit_ai_queries(
    audit_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AiQueryListResponse:
    audit = crawl_service.get_owned_audit(db, current_user.id, audit_id)
    if audit is None:
        raise NOT_FOUND
    queries = list_ai_queries(db, audit.id)
    return AiQueryListResponse(
        items=[serialize_query_list_item(query) for query in queries],
        total=len(queries),
    )


@router.get(
    "/audits/{audit_id}/ai-queries/{query_id}",
    response_model=AiQueryDetailResponse,
    summary="Get one AI query and its response",
    description=(
        "Return one AI query and its response (if any) for an owned audit. "
        "semantic_alignment is populated by the AI Visibility Engine (Phase 12). "
        "Unknown audits/queries and cross-user access both return 404."
    ),
    responses=AUTH_RESPONSES,
)
def get_audit_ai_query(
    audit_id: UUID,
    query_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AiQueryDetailResponse:
    audit = crawl_service.get_owned_audit(db, current_user.id, audit_id)
    if audit is None:
        raise NOT_FOUND
    query = get_ai_query(db, audit.id, query_id)
    if query is None:
        raise NOT_FOUND
    return serialize_query_detail(query)


@router.post(
    "/audits/{audit_id}/calculate-ai-visibility",
    response_model=AIVisibilityResponse,
    summary="Calculate AI Visibility",
    description=(
        "Score persisted AI queries/responses into Mention, Citation, Position, "
        "and Semantic Match metrics and an overall AI Visibility score. "
        "Persists audit.ai_visibility_score and audit.semantic_score only. "
        "Does not modify overall_score, website_score, or seo_score. "
        "Does not change AuditStatus."
    ),
    responses=AUTH_RESPONSES,
)
def calculate_ai_visibility(
    audit_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AIVisibilityResponse:
    audit = crawl_service.get_owned_audit(db, current_user.id, audit_id)
    if audit is None:
        raise NOT_FOUND
    result = ai_visibility_service.run_visibility_calculation(db, audit)
    return serialize_visibility(result.audit_id, result.result)


@router.get(
    "/audits/{audit_id}/ai-visibility",
    response_model=AIVisibilityResponse,
    summary="Get AI Visibility",
    description=(
        "Return the latest calculated AI Visibility result for an owned audit. "
        "If visibility has not been calculated (or was cleared after an AI query "
        "re-run), status is UNAVAILABLE and scores are null — not zero."
    ),
    responses=AUTH_RESPONSES,
)
def get_ai_visibility(
    audit_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AIVisibilityResponse:
    audit = crawl_service.get_owned_audit(db, current_user.id, audit_id)
    if audit is None:
        raise NOT_FOUND
    snapshot = ai_visibility_service.load_visibility_snapshot(db, audit)
    return serialize_visibility(audit.id, snapshot)


@router.post(
    "/audits/{audit_id}/calculate-entity",
    response_model=EntityStrengthResponse,
    summary="Calculate Entity Intelligence",
    description=(
        "Score brand entity clarity from persisted WebsitePage and AI response "
        "evidence. Persists audit.entity_score only. Does not query external "
        "entity databases. Does not modify overall/website/seo/ai_visibility scores."
    ),
    responses=AUTH_RESPONSES,
)
def calculate_entity(
    audit_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EntityStrengthResponse:
    audit = crawl_service.get_owned_audit(db, current_user.id, audit_id)
    if audit is None:
        raise NOT_FOUND
    result = entity_service.run_entity_calculation(db, audit, audit.brand)
    return serialize_entity(result.audit_id, result.result)


@router.get(
    "/audits/{audit_id}/entity",
    response_model=EntityStrengthResponse,
    summary="Get Entity Intelligence",
    description=(
        "Return the latest calculated Entity Strength result for an owned audit. "
        "If entity scoring has not been calculated (or was cleared after a crawl "
        "or AI query re-run), status is UNAVAILABLE and scores are null — not zero."
    ),
    responses=AUTH_RESPONSES,
)
def get_entity(
    audit_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EntityStrengthResponse:
    audit = crawl_service.get_owned_audit(db, current_user.id, audit_id)
    if audit is None:
        raise NOT_FOUND
    snapshot = entity_service.load_entity_snapshot(db, audit, audit.brand)
    return serialize_entity(audit.id, snapshot)


@router.post(
    "/audits/{audit_id}/calculate-recommendations",
    response_model=RecommendationRunResponse,
    summary="Calculate recommendations",
    description=(
        "Generate a deterministic recommendation snapshot from SEO findings, "
        "website health, AI Visibility, and Entity Intelligence evidence. "
        "Replaces prior recommendations for this audit. Does not modify score columns."
    ),
    responses=AUTH_RESPONSES,
)
def calculate_recommendations(
    audit_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecommendationRunResponse:
    audit = crawl_service.get_owned_audit(db, current_user.id, audit_id)
    if audit is None:
        raise NOT_FOUND
    result = recommendation_service.run_recommendation_calculation(db, audit, audit.brand)
    return RecommendationRunResponse(
        audit_id=result.audit_id,
        recommendations_generated=result.recommendations_generated,
        high=result.high,
        medium=result.medium,
        low=result.low,
        status=result.status,
    )


@router.get(
    "/audits/{audit_id}/recommendations",
    response_model=RecommendationListResponse,
    summary="List recommendations",
    description=(
        "Return the current recommendation snapshot for an owned audit, "
        "ordered by priority, impact, and effort. Empty when not yet calculated "
        "or after evidence invalidation."
    ),
    responses=AUTH_RESPONSES,
)
def get_recommendations(
    audit_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecommendationListResponse:
    audit = crawl_service.get_owned_audit(db, current_user.id, audit_id)
    if audit is None:
        raise NOT_FOUND
    items = recommendation_service.list_recommendations(db, audit.id)
    return RecommendationListResponse(
        items=[serialize_recommendation(row) for row in items],
        total=len(items),
    )
