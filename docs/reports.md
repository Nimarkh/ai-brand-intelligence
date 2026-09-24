# Reports

Phase 18 turns one completed audit into an **Audit Intelligence Report**. The report is a PDF snapshot of data that is already stored. Generating it does not crawl, rescore, call an AI provider, or create recommendations.

## Lifecycle

1. `POST /api/v1/reports` with `{ "audit_id": "..." }` checks that the audit belongs to the signed-in user and that `audit.status` is `COMPLETED`.
2. A `reports` row is inserted with status `GENERATING`.
3. The server builds a snapshot from persisted rows, renders a PDF, and writes a small JSON summary beside it.
4. The row becomes `READY`, with `file_path` set to the file name `{report_id}.pdf` and `completed_at` set.
5. If rendering fails, that report's partial files are removed, the row becomes `FAILED`, and the API returns a short message. The response does not include a stack trace.

An audit that is not completed returns `422` with `Complete the audit before generating a report.` No report row is created, and the missing audit steps are not run.

`READY` files are immutable. A later change to the audit does not rewrite the PDF. Generating again inserts a new row and a new file. Retry in the UI is that same create call. A failed row is left as-is.

## Snapshot

The snapshot is built in `backend/app/services/reports/data.py`.

It includes:

- Brand name, website, industry, country, target market, and description
- Audit id, status, created date, and completed date
- Stored overall, website health, SEO, AI visibility, and entity scores
- Website page counts, HTTP status groups, average load time, structured-data coverage, and common stored issue titles
- SEO finding counts, categories, and the highest-severity findings with page URLs when stored
- AI visibility score plus mention rate, citation rate, position, and semantic alignment when a visibility score is already stored
- Entity score plus presence, consistency, structured identity, and AI recognition when an entity score is already stored
- Up to 20 stored recommendations, in the existing Phase 14 order
- A compact AI query summary: counts, categories, and a few query texts. Raw response text is not included
- Methodology notes

There is no recommendation-to-finding foreign key. The report prints each recommendation's stored description. It does not invent an evidence link.

### Scores that are not available

`null` stays unavailable. It is never shown as zero.

Overall status:

- No stored overall score: `UNAVAILABLE` / Not available
- Stored overall score, but AI visibility or entity is null: `PROVISIONAL`, using the same explanation as the dashboard
- All three of overall, AI visibility, and entity are stored: `AVAILABLE`

Visibility rates and entity components are read only when the matching score column is already set. That read uses the existing snapshot loaders and does not write score columns. When the score column is null, those figures stay unavailable even if queries or pages exist. Query and page counts are still shown, because they are stored counts.

## PDF

`backend/app/services/reports/renderer.py` uses ReportLab. The document has a cover, executive summary, website health, SEO analysis, AI visibility, entity intelligence, recommendations, an AI query snapshot, and methodology. Pages include the brand name, generation date, and page number.

The body uses standard PDF fonts for Latin-1 text so the file stays portable. If the snapshot contains characters outside Latin-1 and DejaVu or Arial is installed, those characters use that font. Otherwise they are replaced. The Docker image installs `fonts-dejavu-core`.

PDF is the only format. There is no DOCX, PPTX, CSV, email, or public link.

## Storage

`REPORTS_DIR` defaults to `./data/reports`. Docker uses `/data/reports` on the `reports_data` volume.

Files are named from the report UUID only: `{report_id}.pdf` and `{report_id}.json`. The database stores the PDF file name, not an absolute path. Download ignores any other value in `file_path`. The API never returns a filesystem path.

Failed reports may have no file. Ready reports are not deleted automatically. Deleting one report's files does not delete another report's files.

## API

All routes require the session cookie. Another user's audit or report is `404`.

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/api/v1/reports` | List owned reports, newest first (`created_at DESC`, `id DESC`). Optional `audit_id`, `page`, and `page_size`. Also returns completed owned audits for the generate dialog. |
| POST | `/api/v1/reports` | Create a snapshot. `201` with status `READY` or `FAILED`. |
| GET | `/api/v1/reports/{id}` | Metadata and score summary. No PDF bytes. |
| GET | `/api/v1/reports/{id}/download` | `READY` file as `application/pdf`. `GENERATING` and `FAILED` return `409`. |

The download name is an ASCII slug such as `Acme-audit-intelligence-report.pdf`.

## UI

`/reports` lists reports, shows the empty state, and opens a dialog of completed owned audits. `/reports/:id` shows the summary and a Download PDF action when the report is ready. The PDF is not rendered inside Angular.

`GENERATING` cannot be downloaded. `FAILED` offers Try again, which creates a new report.

## Security

- Authentication and ownership checks on every route
- No user-controlled filesystem path
- No absolute paths in JSON responses
- Stored API keys are stripped from text copied into the snapshot
- Generation does not call the AI provider

## Limitations

- One report type: Audit Intelligence Report
- Synchronous generation in the API process. No Celery, Redis queue, or worker
- No sharing links, email, or cloud storage
- No new scoring and no new AI analysis
- A completed audit with little stored data still produces a report; missing figures are shown as not available
- Visibility and entity breakdowns are included only when those score columns are already stored
