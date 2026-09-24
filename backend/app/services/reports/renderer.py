"""Render a report snapshot to a PDF document.

The renderer does not read the database and does not calculate scores.
"""

from __future__ import annotations

from contextvars import ContextVar
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.services.reports.models import ReportSnapshot

NAVY = HexColor("#1e40af")
INK = HexColor("#0f172a")
MUTED = HexColor("#475569")
LINE = HexColor("#e2e8f0")
ZEBRA = HexColor("#f8fafc")
HIGH = "#b91c1c"
MEDIUM = "#b45309"
LOW = "#1d4ed8"

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_fonts: ContextVar[tuple[str, str]] = ContextVar("report_fonts", default=("Helvetica", "Helvetica-Bold"))
_FONT_FILES = (
    (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
    (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
)


def render_pdf(snapshot: ReportSnapshot, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    token = _fonts.set(_choose_fonts(snapshot))
    try:
        _render(snapshot, destination)
    finally:
        _fonts.reset(token)


def _render(snapshot: ReportSnapshot, destination: Path) -> None:
    document = SimpleDocTemplate(
        str(destination),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        title=_pdf_metadata_title(snapshot.title),
        author="AI Brand Intelligence",
        pageCompression=0,
    )
    styles = _styles()
    story = _story(snapshot, styles)
    document.build(
        story,
        onFirstPage=lambda canv, doc: _decorate(canv, doc, snapshot),
        onLaterPages=lambda canv, doc: _decorate(canv, doc, snapshot),
        canvasmaker=_stable_canvas,
    )


def _choose_fonts(snapshot: ReportSnapshot) -> tuple[str, str]:
    parts = [
        snapshot.brand.name,
        snapshot.brand.website or "",
        snapshot.brand.description or "",
        snapshot.brand.industry or "",
        snapshot.brand.country or "",
        snapshot.brand.target_market or "",
    ]
    parts.extend(item.title for item in snapshot.recommendations)
    parts.extend(item.description or "" for item in snapshot.recommendations)
    parts.extend(item.text for item in snapshot.queries.examples)
    parts.extend(item.title for item in snapshot.seo.findings)
    sample = _normalize_punctuation(" ".join(parts))
    try:
        sample.encode("latin-1")
        return ("Helvetica", "Helvetica-Bold")
    except UnicodeEncodeError:
        pass
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    registered = set(pdfmetrics.getRegisteredFontNames())
    for regular, bold in _FONT_FILES:
        if not Path(regular).is_file():
            continue
        if "ReportSans" not in registered:
            pdfmetrics.registerFont(TTFont("ReportSans", regular))
            bold_file = bold if Path(bold).is_file() else regular
            pdfmetrics.registerFont(TTFont("ReportSans-Bold", bold_file))
        return ("ReportSans", "ReportSans-Bold")
    return ("Helvetica", "Helvetica-Bold")


def _stable_canvas(filename: str, **kwargs: object) -> canvas.Canvas:
    kwargs["invariant"] = 1
    kwargs["pageCompression"] = 0
    return canvas.Canvas(filename, **kwargs)


def _story(snapshot: ReportSnapshot, styles: dict[str, ParagraphStyle]) -> list:
    usable = A4[0] - 32 * mm
    story: list = []
    story.extend(_cover(snapshot, styles, usable))
    story.extend(_executive(snapshot, styles, usable))
    story.extend(_website(snapshot, styles, usable))
    story.extend(_seo(snapshot, styles, usable))
    story.extend(_visibility(snapshot, styles, usable))
    story.extend(_entity(snapshot, styles, usable))
    story.extend(_recommendations(snapshot, styles, usable))
    story.extend(_queries(snapshot, styles, usable))
    story.extend(_methodology(snapshot, styles))
    return story


def _cover(snapshot: ReportSnapshot, styles: dict[str, ParagraphStyle], usable: float) -> list:
    brand = snapshot.brand
    audit_date = snapshot.audit.completed_at or snapshot.audit.created_at
    return [
        Paragraph("AI Brand Intelligence", styles["kicker"]),
        Paragraph("Audit Intelligence Report", styles["title"]),
        Spacer(1, 4),
        Paragraph(_text(brand.name), styles["brand"]),
        Paragraph(_text(brand.website or "Website not available"), styles["meta"]),
        Paragraph(f"Audit date {_date(audit_date)}", styles["meta"]),
        Paragraph(f"Generated {_date(snapshot.generated_at)}", styles["meta"]),
        Spacer(1, 6),
        _table(
            ["Brand", "Value"],
            [
                ["Name", brand.name],
                ["Website", brand.website or "Not available"],
                ["Industry", brand.industry or "Not available"],
                ["Country", brand.country or "Not available"],
                ["Target market", brand.target_market or "Not available"],
                ["Description", brand.description or "Not available"],
            ],
            [usable * 0.32, usable * 0.68],
        ),
        Spacer(1, 8),
        HRFlowable(width="100%", thickness=1, color=NAVY, spaceAfter=10),
    ]


def _executive(snapshot: ReportSnapshot, styles: dict[str, ParagraphStyle], usable: float) -> list:
    overall = snapshot.overall
    blocks = [
        _heading("Executive Summary", styles),
        Paragraph("Overall Intelligence Score", styles["label"]),
        Paragraph(_score(overall.score), styles["score"]),
        Paragraph(_status_label(overall.status), styles["status"]),
        Paragraph(_text(overall.note or "Not available"), styles["body"]),
        Spacer(1, 6),
        _table(
            ["Dimension", "Score", "Availability"],
            [
                [line.label, _score(line.score), _status_label(line.status)]
                for line in snapshot.scores
            ],
            [usable * 0.42, usable * 0.28, usable * 0.30],
        ),
    ]
    return blocks


def _website(snapshot: ReportSnapshot, styles: dict[str, ParagraphStyle], usable: float) -> list:
    site = snapshot.website
    rows = [
        ["Pages crawled", str(site.pages_crawled)],
        ["Analyzable pages", str(site.analyzable_pages)],
        ["Successful HTTP pages", str(site.successful_http)],
        ["4xx pages", str(site.client_errors)],
        ["5xx pages", str(site.server_errors)],
        ["Average load time", _load(site.average_load_ms)],
        ["Structured data coverage", _percent(site.structured_data_coverage)],
    ]
    story = [
        _heading("Website Health", styles),
        Paragraph(
            "Crawl summary and technical metrics from stored pages. This report does not recrawl the website.",
            styles["body"],
        ),
        _table(["Metric", "Value"], rows, [usable * 0.62, usable * 0.38]),
    ]
    if site.common_issues:
        issue_rows = [[issue.title, str(issue.count)] for issue in site.common_issues]
        story.append(Spacer(1, 6))
        story.append(Paragraph("Common technical issues", styles["subhead"]))
        story.append(_table(["Issue", "Count"], issue_rows, [usable * 0.78, usable * 0.22]))
    else:
        story.append(Paragraph("No common technical issues are stored for this audit.", styles["body"]))
    return story


def _seo(snapshot: ReportSnapshot, styles: dict[str, ParagraphStyle], usable: float) -> list:
    seo = snapshot.seo
    story = [
        _heading("SEO Analysis", styles),
        Paragraph("Findings below are stored SEO results. The analyzer is not run again for this report.", styles["body"]),
        _table(
            ["Severity", "Count"],
            [
                ["Total", str(seo.total)],
                [_severity("HIGH"), str(seo.high)],
                [_severity("MEDIUM"), str(seo.medium)],
                [_severity("LOW"), str(seo.low)],
            ],
            [usable * 0.62, usable * 0.38],
        ),
    ]
    if seo.categories:
        story.append(Spacer(1, 6))
        story.append(Paragraph("Findings by category", styles["subhead"]))
        story.append(
            _table(
                ["Category", "Count"],
                [[item.category, str(item.count)] for item in seo.categories],
                [usable * 0.78, usable * 0.22],
            )
        )
    if seo.findings:
        story.append(Spacer(1, 6))
        story.append(Paragraph("Major findings", styles["subhead"]))
        story.append(
            _table(
                ["Severity", "Finding", "Page"],
                [
                    [
                        _severity(item.severity),
                        item.title,
                        item.page_url or "Not available",
                    ]
                    for item in seo.findings
                ],
                [usable * 0.18, usable * 0.46, usable * 0.36],
            )
        )
    else:
        story.append(Paragraph("No SEO findings are stored for this audit.", styles["body"]))
    return story


def _visibility(snapshot: ReportSnapshot, styles: dict[str, ParagraphStyle], usable: float) -> list:
    visibility = snapshot.visibility
    coverage = "Not available"
    if visibility.total_queries:
        coverage = f"{visibility.successful_responses} / {visibility.total_queries}"
    rows = [
        ["AI visibility score", _score(visibility.score)],
        ["Availability", _status_label(visibility.status)],
        ["Mention rate", _rate(visibility.mention_rate)],
        ["Citation rate", _rate(visibility.citation_rate)],
        ["Average position", _plain_number(visibility.average_position)],
        ["Position score", _score(visibility.position_score)],
        ["Semantic alignment", _semantic(visibility)],
        ["Query coverage", coverage],
    ]
    return [
        _heading("AI Visibility", styles),
        Paragraph(
            "The score is the stored AI Visibility value. Rates are shown only when that stored result exists.",
            styles["body"],
        ),
        _table(["Metric", "Value"], rows, [usable * 0.62, usable * 0.38]),
    ]


def _entity(snapshot: ReportSnapshot, styles: dict[str, ParagraphStyle], usable: float) -> list:
    entity = snapshot.entity
    rows = [
        ["Entity score", _score(entity.score)],
        ["Availability", _status_label(entity.status)],
        ["Entity presence", _score(entity.presence)],
        ["Entity consistency", _score(entity.consistency)],
        ["Structured identity", _score(entity.structured_identity)],
        ["AI recognition", _score(entity.ai_recognition)],
    ]
    return [
        _heading("Entity Intelligence", styles),
        Paragraph(
            "The entity score is the stored value. Component figures are omitted when that score is not available.",
            styles["body"],
        ),
        _table(["Metric", "Value"], rows, [usable * 0.62, usable * 0.38]),
    ]


def _recommendations(snapshot: ReportSnapshot, styles: dict[str, ParagraphStyle], usable: float) -> list:
    story = [
        _heading("Recommendations", styles),
        Paragraph(
            "Stored recommendations in their existing order. This report does not generate new recommendations.",
            styles["body"],
        ),
    ]
    if not snapshot.recommendations:
        story.append(Paragraph("No recommendations are stored for this audit.", styles["body"]))
        return story
    rows = []
    for item in snapshot.recommendations:
        detail = item.title
        if item.description:
            detail = f"{item.title} - {item.description}"
        rows.append(
            [
                _severity(item.priority),
                item.category,
                detail,
                _plain_number(item.impact),
                _plain_number(item.effort),
            ]
        )
    story.append(
        _table(
            ["Priority", "Category", "Recommendation", "Impact", "Effort"],
            rows,
            [usable * 0.14, usable * 0.16, usable * 0.46, usable * 0.12, usable * 0.12],
        )
    )
    return story


def _queries(snapshot: ReportSnapshot, styles: dict[str, ParagraphStyle], usable: float) -> list:
    queries = snapshot.queries
    story = [
        _heading("AI Query Snapshot", styles),
        Paragraph(
            "Compact summary of stored queries. Raw AI responses are not included.",
            styles["body"],
        ),
        _table(
            ["Metric", "Value"],
            [
                ["Total queries", str(queries.total_queries)],
                ["Successful responses", str(queries.successful_responses)],
                ["Brand mentions", str(queries.brand_mentions)],
                ["Citations", str(queries.citations)],
            ],
            [usable * 0.62, usable * 0.38],
        ),
    ]
    if queries.categories:
        story.append(Spacer(1, 6))
        story.append(
            _table(
                ["Category", "Queries"],
                [[item.category, str(item.count)] for item in queries.categories],
                [usable * 0.78, usable * 0.22],
            )
        )
    if queries.examples:
        story.append(Spacer(1, 6))
        story.append(Paragraph("Relevant queries", styles["subhead"]))
        story.append(
            _table(
                ["Category", "Query", "Mention", "Citation"],
                [
                    [
                        item.category,
                        item.text,
                        "Yes" if item.brand_mentioned else "No",
                        "Yes" if item.citation_found else "No",
                    ]
                    for item in queries.examples
                ],
                [usable * 0.18, usable * 0.52, usable * 0.15, usable * 0.15],
            )
        )
    elif queries.total_queries == 0:
        story.append(Paragraph("No AI queries are stored for this audit.", styles["body"]))
    return story


def _methodology(snapshot: ReportSnapshot, styles: dict[str, ParagraphStyle]) -> list:
    story = [_heading("Methodology", styles)]
    for note in snapshot.methodology:
        story.append(Paragraph(_text(note), styles["body"]))
    return story


def _heading(text: str, styles: dict[str, ParagraphStyle]) -> Paragraph:
    return Paragraph(_text(text), styles["heading"])


def _table(headers: list[str], rows: list[list[str]], widths: list[float]) -> Table:
    body_font, bold_font = _fonts.get()
    header = [
        Paragraph(
            _text(cell),
            ParagraphStyle(
                "report-th",
                fontName=bold_font,
                fontSize=8,
                leading=10,
                textColor=white,
            ),
        )
        for cell in headers
    ]
    body = []
    for row in rows:
        body.append(
            [
                Paragraph(
                    cell if cell.startswith("<font") else _text(cell),
                    ParagraphStyle(
                        "report-td",
                        fontName=body_font,
                        fontSize=8,
                        leading=11,
                        textColor=INK,
                    ),
                )
                for cell in row
            ]
        )
    table = Table([header, *body], colWidths=widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), white),
                ("FONTNAME", (0, 0), (-1, 0), bold_font),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, ZEBRA]),
                ("GRID", (0, 0), (-1, -1), 0.3, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _styles() -> dict[str, ParagraphStyle]:
    body, bold = _fonts.get()
    return {
        "kicker": ParagraphStyle(
            "report-kicker",
            fontName=body,
            fontSize=9,
            leading=12,
            textColor=NAVY,
        ),
        "title": ParagraphStyle(
            "report-title",
            fontName=bold,
            fontSize=20,
            leading=24,
            textColor=INK,
            spaceBefore=2,
            spaceAfter=4,
        ),
        "brand": ParagraphStyle(
            "report-brand",
            fontName=bold,
            fontSize=13,
            leading=16,
            textColor=INK,
            spaceBefore=2,
        ),
        "meta": ParagraphStyle(
            "report-meta",
            fontName=body,
            fontSize=9,
            leading=12,
            textColor=MUTED,
        ),
        "heading": ParagraphStyle(
            "report-heading",
            fontName=bold,
            fontSize=13,
            leading=16,
            textColor=NAVY,
            spaceBefore=12,
            spaceAfter=4,
        ),
        "subhead": ParagraphStyle(
            "report-subhead",
            fontName=bold,
            fontSize=10,
            leading=13,
            textColor=INK,
            spaceBefore=2,
            spaceAfter=3,
        ),
        "label": ParagraphStyle(
            "report-label",
            fontName=body,
            fontSize=8,
            leading=10,
            textColor=MUTED,
        ),
        "score": ParagraphStyle(
            "report-score",
            fontName=bold,
            fontSize=16,
            leading=20,
            textColor=INK,
        ),
        "status": ParagraphStyle(
            "report-status",
            fontName=bold,
            fontSize=9,
            leading=12,
            textColor=NAVY,
            spaceBefore=1,
            spaceAfter=2,
        ),
        "body": ParagraphStyle(
            "report-body",
            fontName=body,
            fontSize=9,
            leading=12,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=4,
        ),
    }


def _decorate(pdf: canvas.Canvas, document: SimpleDocTemplate, snapshot: ReportSnapshot) -> None:
    pdf.saveState()
    pdf.setFillColor(NAVY)
    pdf.rect(0, A4[1] - 8 * mm, A4[0], 8 * mm, fill=1, stroke=0)
    pdf.setFillColor(white)
    pdf.setFont("Helvetica", 8)
    pdf.drawString(16 * mm, A4[1] - 5.2 * mm, "AI Brand Intelligence")
    pdf.drawRightString(A4[0] - 16 * mm, A4[1] - 5.2 * mm, _canvas_text(snapshot.brand.name))
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 8)
    pdf.drawString(16 * mm, 8 * mm, f"Generated {_date(snapshot.generated_at)}")
    pdf.drawRightString(A4[0] - 16 * mm, 8 * mm, f"Page {document.page}")
    pdf.restoreState()


def _score(value: Decimal | None) -> str:
    if value is None:
        return "Not available"
    shown = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    text = format(shown, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return f"{text} / 100"


def _semantic(visibility: object) -> str:
    alignment = getattr(visibility, "semantic_alignment", None)
    if alignment is not None:
        return _rate(alignment)
    return _score(getattr(visibility, "semantic_score", None))


def _rate(value: Decimal | None) -> str:
    if value is None:
        return "Not available"
    number = Decimal(str(value))
    if number <= 1:
        number = number * Decimal("100")
    shown = number.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return f"{int(shown)}%"


def _percent(value: Decimal | None) -> str:
    return _rate(value)


def _plain_number(value: Decimal | None) -> str:
    if value is None:
        return "Not available"
    shown = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    text = format(shown, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _load(value: Decimal | None) -> str:
    if value is None:
        return "Not available"
    return f"{_plain_number(value)} ms"


def _status_label(status: str) -> str:
    if status == "PROVISIONAL":
        return "Provisional"
    if status == "AVAILABLE":
        return "Available"
    return "Not available"


def _severity(value: str) -> str:
    colors = {"HIGH": HIGH, "MEDIUM": MEDIUM, "LOW": LOW}
    color = colors.get(value, "#334155")
    return f'<font color="{color}">{_text(value)}</font>'


def _date(value: object) -> str:
    if value is None or not hasattr(value, "month"):
        return "Not available"
    return f"{_MONTHS[value.month - 1]} {value.day}, {value.year}"


def _text(value: str | None) -> str:
    if value is None or not str(value).strip():
        return "Not available"
    normalized = _normalize_punctuation(str(value))
    escaped = normalized.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    unicode_ok = _fonts.get()[0] != "Helvetica"
    safe = []
    for char in escaped:
        if char in "&;" or 32 <= ord(char) <= 255 or (unicode_ok and char.isprintable()):
            safe.append(char)
        elif char in ("\n", "\r", "\t"):
            safe.append(" ")
        else:
            safe.append("?")
    return "".join(safe)


def _normalize_punctuation(value: str) -> str:
    return value.replace("\u2014", "-").replace("\u2013", "-").replace("\u2026", "...")


def _pdf_metadata_title(title: str) -> str:
    return _normalize_punctuation(title).encode("latin-1", "replace").decode("latin-1")


def _canvas_text(value: str) -> str:
    cleaned = " ".join(_normalize_punctuation(value or "Brand").split()) or "Brand"
    return cleaned.encode("latin-1", "replace").decode("latin-1")
