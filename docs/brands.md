# Brand management

Brands are the records later audits and analysis will belong to. This phase stores brand details only. It does not crawl websites or create audit results.

## Ownership

Every brand has one owner: `brands.owner_id`, a foreign key to `users.id`.

The API sets `owner_id` from the authenticated user (`get_current_user()`). `BrandCreate` and `BrandUpdate` reject unknown fields, including `owner_id`, with HTTP 422.

List, get, update, and delete queries include `owner_id = current user`. If the id is missing, or the row belongs to someone else, the API returns:

```json
{ "detail": "Brand not found." }
```

HTTP status is 404 in both cases. The API does not return 403 for another user's brand.

## Endpoints

All of these require the session cookie. Unauthenticated calls return 401.

| Method | Path | Success | Purpose |
| ------ | ---- | ------- | ------- |
| GET | `/api/v1/brands` | 200 | Brands owned by the current user |
| POST | `/api/v1/brands` | 201 | Create a brand |
| GET | `/api/v1/brands/{brand_id}` | 200 | One owned brand |
| PATCH | `/api/v1/brands/{brand_id}` | 200 | Update an owned brand |
| DELETE | `/api/v1/brands/{brand_id}` | 204 | Delete an owned brand |

`GET /api/v1/brands` accepts `limit` (default 100, maximum 100) and `offset` (default 0). Results are ordered by `created_at` descending, then `id` descending. The body is `{ "items": [...], "total": N }`. `total` counts every brand the user owns, not only the page.

Responses use `BrandResponse` and do not include `owner_id`.

## Validation

| Field | Create | Update | Rules |
| ----- | ------ | ------ | ----- |
| name | required | optional | Trimmed, 1–255 characters |
| website_url | required | optional | http or https, normalized, max 2048 characters |
| industry | required | optional | Trimmed, 1–255 characters |
| country | required | optional | Trimmed, 1–255 characters |
| target_market | required | optional | Trimmed, 1–255 characters |
| description | optional | optional | Trimmed, max 5000 characters. Blank becomes null |

`PATCH` changes only fields present in the body. `id`, `owner_id`, `created_at`, and `updated_at` cannot be set by the client.

Duplicate brand names are allowed. There is no 409 conflict for brands.

The database columns for website, industry, country, and target market are still nullable from Phase 02. The API requires them when a brand is created. No migration was added.

## Website URL normalization

Normalization does not request the website and does not change which host or path is addressed.

- Whitespace around the value is removed. Internal whitespace is rejected.
- The scheme must be `http` or `https`. `javascript:`, `data:`, `file:`, `ftp:`, and URLs without a scheme are rejected.
- Credentials in the URL (`user:password@host`) are rejected.
- Scheme and host are lowercased. International hostnames are stored in IDNA ASCII form.
- Default ports (`:80` on http, `:443` on https) are removed. Any other port is kept.
- A trailing slash is removed only when the path is empty or `/`.
- A real path is kept as entered, including a trailing slash on that path.
- The query string is kept. The fragment is dropped.
- `www` is kept. `http` is not rewritten to `https`.

Examples:

| Input | Stored |
| ----- | ------ |
| `https://example.com` | `https://example.com` |
| `https://www.example.com/` | `https://www.example.com` |
| `HTTPS://Example.COM/Path/` | `https://example.com/Path/` |
| `https://example.com/docs?q=1#section` | `https://example.com/docs?q=1` |

## Deletion and future audits

`DELETE` removes that brand row and returns 204 with an empty body. It does not delete other brands.

`audits.brand_id` uses `ON DELETE CASCADE`. The ORM marks that relationship `passive_deletes="all"`, so SQLAlchemy does not load audits or clear `brand_id`. Today there are no audit rows, so only the brand is removed.

When audits exist, the database cascade will also delete those audits and the rows that cascade from an audit (pages, SEO findings, AI queries and responses, recommendations, and reports). Before storing audit data, decide whether that cascade should remain or whether deletion should be blocked while audits exist.

## Frontend

Protected routes:

- `/brands` lists the signed-in user's brands
- `/brands/new` creates a brand
- `/brands/:id` shows the brand. Intelligence sections are empty until a later phase
- `/brands/:id/edit` updates the brand

`/brands/new` is registered before `/brands/:id`, so `new` is not treated as an id.

The UI uses the application shell, design tokens, and shared components. Brand detail can create an audit, start a website crawl, and surface latest stored scores when present. Full SEO / AI / entity analysis lives on the audit detail page.
