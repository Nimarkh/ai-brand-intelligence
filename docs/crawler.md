# Website crawler

Phase 07 collects factual pages from a brand's website. It does not decide whether those pages are good, and it does not calculate scores.

The crawler answers: what came back from the site?

Later phases answer: what is wrong with it, and how good is it?

## Architecture

```
POST /audits/{id}/crawl
        |
        v
crawl_service.run_crawl()     status + database snapshot
        |
        v
WebsiteCrawler.crawl()        queue, limits, HTTP, robots
        |
        +-- url_utils.py      normalization, same-origin, SSRF checks
        +-- robots.py         robots.txt allow/disallow
        +-- parser.py         HTML metadata and JSON-LD types
```

`WebsiteCrawler` does not import the database. `run_crawl()` is the only place that changes `Audit.status` and `website_pages`. A background worker can call those same functions later. This phase does not add Celery, a Redis queue, or a browser.

The HTTP client is `httpx`. Requests are sequential. JavaScript is not executed, so content that appears only after client-side rendering is not collected.

## Audit lifecycle

An audit is created with `POST /api/v1/brands/{brand_id}/audits`. Status is `PENDING`. Every score column stays null.

`POST /api/v1/audits/{audit_id}/crawl` then:

1. Confirms the signed-in user owns the audit's brand. Anyone else, and unknown ids, get 404.
2. Commits `RUNNING` and `started_at` before any page request, so the database lock is not held during HTTP.
3. Deletes existing `website_pages` for this audit only, once the start URL is allowed.
4. Crawls.
5. Inserts the new rows and commits `COMPLETED`.

`COMPLETED` means the crawl finished. It does not mean the website is healthy. `overall_score`, `website_score`, `seo_score`, `ai_visibility_score`, `entity_score`, and `semantic_score` are not modified.

If the crawl raises, the in-progress page insert is rolled back, the audit is set to `FAILED`, and the API returns a generic error. One page that times out, returns 404 or 500, or contains broken HTML does not fail the audit. A rejected start URL (for example a loopback address) marks the audit `FAILED` and leaves any previous pages in place, because crawling never started.

Crawling the same audit again replaces that audit's page rows. Rows for other audits stay. A failed attempt that already deleted pages does not restore the previous snapshot.

There is no schema migration in this phase. `website_pages` already stores URL, status, title, meta description, canonical URL, word count, heading counts, schema flags, and load time.

## Limits

These come from environment settings. A crawl request cannot raise them.

| Setting | Default | Meaning |
| --- | --- | --- |
| `CRAWLER_MAX_PAGES` | 20 | Pages fetched from the queue |
| `CRAWLER_MAX_DEPTH` | 3 | Link depth. The start URL is depth 0 |
| `CRAWLER_REQUEST_TIMEOUT_SECONDS` | 10 | Per-request timeout |
| `CRAWLER_DELAY_SECONDS` | 0.1 | Pause between HTTP requests, including robots.txt |
| `CRAWLER_MAX_RESPONSE_BYTES` | 5000000 | Body cap. Larger bodies are not parsed |
| `CRAWLER_USER_AGENT` | `AI-Brand-Intelligence-Crawler/1.0` | User-Agent sent on every request |
| `CRAWLER_MAX_REDIRECTS` | 5 | Same-origin redirects followed for one page |

The crawl is breadth-first. It stops when the queue is empty or the page limit is reached. Depth and page count are separate. Common static extensions (images, PDF, CSS, JavaScript, fonts, video, archives) are not requested.

## URL normalization

One helper resolves relative URLs and normalizes them before the visited set, duplicate checks, and database storage:

- `http` and `https` only
- scheme and hostname lowercased, hostname in IDNA form
- default ports removed
- fragments removed
- root path stored without a trailing slash
- other paths preserved, including a trailing slash
- query keys and values preserved, sorted so reordered queries match
- credentials, `javascript:`, `mailto:`, `tel:`, `data:`, `blob:`, `file:`, and `ftp:` rejected

## Same-host policy

The crawl origin is the brand URL's scheme, hostname, and port.

`https://example.com` may include `https://example.com/about`.

It does not include:

- `https://blog.example.com`
- `https://www.example.com`
- `http://example.com`
- `https://example.com:8443`
- any other site

`www` is not stripped. Subdomains are not crawled unless the brand URL itself uses that hostname.

Same-origin redirects are followed, and the final URL is stored. A redirect that leaves the origin is not followed. The in-domain response is stored with its redirect status. Redirect loops stop at the redirect limit.

## robots.txt

Before page fetches, the crawler requests `/robots.txt` on the origin.

- 404, or any missing file: crawling continues
- network error, HTTP error, or a body over 512 KB: crawling continues, and the failure is logged
- a Disallow rule that matches this user-agent: that URL is not requested

Allow and Disallow are interpreted by Python's `RobotFileParser`. Sitemap directives and Crawl-delay are ignored. The crawler does not try to bypass robots.txt.

## What is stored

For an HTML response (`text/html` or `application/xhtml+xml`) the crawler stores:

- URL and HTTP status
- title and meta description, or null when absent
- canonical URL when a `link rel=canonical` is present and normalizes; the current URL is not assumed to be canonical
- H1 count, H2 count, and a whitespace word count from visible text
- `has_schema` and `schema_types` from parseable JSON-LD, including `@type` arrays and `@graph`
- `load_time_ms` from a monotonic clock

Malformed JSON-LD is skipped. Other JSON-LD blocks on the same page are still read. The crawler does not invent titles or descriptions.

Non-HTML successes, such as images that were requested anyway, are not stored. Error responses are stored with their status so one 404 does not disappear. Network failures are stored with a null status. Oversized bodies are stored with a status and without extracted fields.

`script`, `style`, and `noscript` are excluded from the word count. Heading counts are counts only.

## SSRF

The crawler only requests `http` and `https` URLs derived from the owned brand website. It rejects credentials and non-HTTP schemes, refuses redirects to another host, and does not send the user's cookie to the target site.

Before a request, the hostname is checked against loopback, private, link-local, reserved, and other non-public addresses. This includes literal addresses such as `127.0.0.1`, `localhost`, `0.0.0.0`, and `::1`, integer forms such as `2130706433`, and DNS answers. If any resolved address is non-public, or DNS fails, the URL is not requested. A blocked start URL fails the crawl.

This is not full DNS-rebinding protection. The check resolves the name, then `httpx` resolves it again when connecting. Those lookups are not pinned to one address.

## Logging

Logs include the audit id, brand id, start, completion, page count, page-level failure reason, and duration. They do not include passwords, JWTs, cookies, or response bodies. API errors do not include stack traces.

## Frontend

The brand detail page has **Start website crawl**. That creates an audit and calls the crawl endpoint. The page shows:

- No audits yet
- Audit pending
- Crawling website…
- Website crawl completed, with the number of pages stored
- Crawl failed

It does not show a score.
