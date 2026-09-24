from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.brand import Brand
from app.schemas.brand import normalize_website_url

USER_A = {
    "email": "owner-a@example.com",
    "password": "password123",
    "full_name": "Owner A",
}
USER_B = {
    "email": "owner-b@example.com",
    "password": "password123",
    "full_name": "Owner B",
}

BRAND_A = {
    "name": "Northwind",
    "website_url": "https://northwind.example",
    "industry": "Retail",
    "country": "United States",
    "target_market": "North America",
    "description": "Outdoor goods",
}
BRAND_B = {
    "name": "Contoso",
    "website_url": "https://contoso.example",
    "industry": "Software",
    "country": "Germany",
    "target_market": "Europe",
}

PUBLIC_FIELDS = {
    "id",
    "name",
    "website_url",
    "industry",
    "country",
    "target_market",
    "description",
    "created_at",
    "updated_at",
}


def _register_and_login(client: TestClient, user: dict[str, str]) -> dict[str, str]:
    registered = client.post("/api/v1/auth/register", json=user)
    assert registered.status_code == 201
    logged_in = client.post(
        "/api/v1/auth/login",
        json={"email": user["email"], "password": user["password"]},
    )
    assert logged_in.status_code == 200
    body = logged_in.json()
    assert isinstance(body, dict)
    return body


def _create_brand(client: TestClient, payload: dict[str, str] | None = None) -> dict:
    response = client.post("/api/v1/brands", json=payload or BRAND_A)
    assert response.status_code == 201
    body = response.json()
    assert isinstance(body, dict)
    return body


def test_normalize_website_url_preserves_destination() -> None:
    assert normalize_website_url(" https://example.com ") == "https://example.com"
    assert normalize_website_url("https://www.example.com/") == "https://www.example.com"
    assert normalize_website_url("HTTPS://Example.COM/Path/") == "https://example.com/Path/"
    assert normalize_website_url("https://example.com/docs?q=1#section") == "https://example.com/docs?q=1"
    assert normalize_website_url("https://example.com:443/docs") == "https://example.com/docs"
    assert normalize_website_url("http://example.com:8080") == "http://example.com:8080"


def test_normalize_website_url_rejects_unsafe_values() -> None:
    for value in (
        "javascript:alert(1)",
        "data:text/html,hi",
        "file:///etc/passwd",
        "ftp://example.com",
        "example.com",
        "http://",
        "https://user:secret@example.com",
        "https://example.com/spaced path",
    ):
        try:
            normalize_website_url(value)
        except ValueError:
            continue
        raise AssertionError(f"expected rejection for {value}")


def test_unauthenticated_brand_requests_are_rejected(client: TestClient) -> None:
    brand_id = uuid4()
    requests = (
        client.get("/api/v1/brands"),
        client.post("/api/v1/brands", json=BRAND_A),
        client.get(f"/api/v1/brands/{brand_id}"),
        client.patch(f"/api/v1/brands/{brand_id}", json={"name": "Other"}),
        client.delete(f"/api/v1/brands/{brand_id}"),
    )

    assert [response.status_code for response in requests] == [401, 401, 401, 401, 401]


def test_create_brand_sets_owner_from_session(client: TestClient, db: Session) -> None:
    user = _register_and_login(client, USER_A)
    created = _create_brand(client)

    assert set(created.keys()) == PUBLIC_FIELDS
    assert "owner_id" not in created
    assert created["name"] == "Northwind"
    assert created["website_url"] == "https://northwind.example"
    assert created["description"] == "Outdoor goods"

    stored = db.get(Brand, UUID(created["id"]))
    assert stored is not None
    assert str(stored.owner_id) == user["id"]


def test_create_rejects_client_owner_id(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    response = client.post("/api/v1/brands", json={**BRAND_A, "owner_id": str(uuid4())})

    assert response.status_code == 422
    assert db.query(Brand).count() == 0


def test_create_trims_name_and_normalizes_url(client: TestClient) -> None:
    _register_and_login(client, USER_A)
    created = _create_brand(
        client,
        {
            **BRAND_A,
            "name": "  Northwind  ",
            "website_url": "https://www.example.com/",
            "description": "   ",
        },
    )

    assert created["name"] == "Northwind"
    assert created["website_url"] == "https://www.example.com"
    assert created["description"] is None


def test_create_rejects_missing_fields(client: TestClient) -> None:
    _register_and_login(client, USER_A)
    response = client.post("/api/v1/brands", json={"name": "Northwind"})

    assert response.status_code == 422


def test_create_rejects_invalid_urls(client: TestClient) -> None:
    _register_and_login(client, USER_A)
    for website_url in ("javascript:alert(1)", "data:text/html,x", "file:///tmp/a", "notaurl", ""):
        response = client.post("/api/v1/brands", json={**BRAND_A, "website_url": website_url})
        assert response.status_code == 422


def test_create_rejects_whitespace_name_and_long_fields(client: TestClient) -> None:
    _register_and_login(client, USER_A)

    blank = client.post("/api/v1/brands", json={**BRAND_A, "name": "   "})
    long_name = client.post("/api/v1/brands", json={**BRAND_A, "name": "n" * 256})
    long_industry = client.post("/api/v1/brands", json={**BRAND_A, "industry": "i" * 256})
    long_country = client.post("/api/v1/brands", json={**BRAND_A, "country": "c" * 256})
    long_market = client.post("/api/v1/brands", json={**BRAND_A, "target_market": "m" * 256})
    long_description = client.post("/api/v1/brands", json={**BRAND_A, "description": "d" * 5001})

    assert blank.status_code == 422
    assert long_name.status_code == 422
    assert long_industry.status_code == 422
    assert long_country.status_code == 422
    assert long_market.status_code == 422
    assert long_description.status_code == 422


def test_list_returns_only_owned_brands_newest_first(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    older = _create_brand(client, BRAND_A)
    newer = _create_brand(client, {**BRAND_A, "name": "Newer"})

    older_row = db.get(Brand, UUID(older["id"]))
    newer_row = db.get(Brand, UUID(newer["id"]))
    assert older_row is not None and newer_row is not None
    older_row.created_at = datetime.now(timezone.utc) - timedelta(days=2)
    newer_row.created_at = datetime.now(timezone.utc)
    db.commit()

    with TestClient(app) as other:
        _register_and_login(other, USER_B)
        hidden = _create_brand(other, BRAND_B)
        other_list = other.get("/api/v1/brands")

    listed = client.get("/api/v1/brands")
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 2
    assert [item["id"] for item in body["items"]] == [newer["id"], older["id"]]
    assert hidden["id"] not in {item["id"] for item in body["items"]}
    assert all("owner_id" not in item for item in body["items"])

    assert other_list.status_code == 200
    other_body = other_list.json()
    assert other_body["total"] == 1
    assert other_body["items"][0]["id"] == hidden["id"]
    assert older["id"] not in {item["id"] for item in other_body["items"]}


def test_list_limit_and_offset(client: TestClient) -> None:
    _register_and_login(client, USER_A)
    _create_brand(client, BRAND_A)
    _create_brand(client, {**BRAND_A, "name": "Second"})

    page = client.get("/api/v1/brands", params={"limit": 1, "offset": 0})

    assert page.status_code == 200
    assert page.json()["total"] == 2
    assert len(page.json()["items"]) == 1


def test_get_brand_for_owner_and_hide_others(client: TestClient) -> None:
    _register_and_login(client, USER_A)
    created = _create_brand(client)

    owner_get = client.get(f"/api/v1/brands/{created['id']}")
    missing = client.get(f"/api/v1/brands/{uuid4()}")
    invalid = client.get("/api/v1/brands/not-a-uuid")

    assert owner_get.status_code == 200
    assert owner_get.json()["id"] == created["id"]
    assert "owner_id" not in owner_get.json()
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Brand not found."}
    assert invalid.status_code == 422

    with TestClient(app) as other:
        _register_and_login(other, USER_B)
        foreign = other.get(f"/api/v1/brands/{created['id']}")

    assert foreign.status_code == 404
    assert foreign.json() == {"detail": "Brand not found."}


def test_update_brand_and_reject_owner_change(client: TestClient, db: Session) -> None:
    user = _register_and_login(client, USER_A)
    created = _create_brand(client)
    updated = client.patch(
        f"/api/v1/brands/{created['id']}",
        json={"name": "  Northwind Goods  ", "website_url": "https://goods.example/path/"},
    )

    assert updated.status_code == 200
    assert updated.json()["name"] == "Northwind Goods"
    assert updated.json()["website_url"] == "https://goods.example/path/"
    assert updated.json()["industry"] == "Retail"
    assert updated.json()["description"] == "Outdoor goods"
    assert "owner_id" not in updated.json()

    rejected = client.patch(
        f"/api/v1/brands/{created['id']}",
        json={"owner_id": str(uuid4()), "name": "Stolen"},
    )
    assert rejected.status_code == 422

    stored = db.get(Brand, UUID(created["id"]))
    assert stored is not None
    assert stored.name == "Northwind Goods"
    assert str(stored.owner_id) == user["id"]


def test_update_non_owner_and_missing_brand_are_not_found(client: TestClient) -> None:
    _register_and_login(client, USER_A)
    created = _create_brand(client)

    with TestClient(app) as other:
        _register_and_login(other, USER_B)
        foreign = other.patch(f"/api/v1/brands/{created['id']}", json={"name": "Stolen"})

    missing = client.patch(f"/api/v1/brands/{uuid4()}", json={"name": "Missing"})

    assert foreign.status_code == 404
    assert foreign.json() == {"detail": "Brand not found."}
    assert missing.status_code == 404
    assert client.get(f"/api/v1/brands/{created['id']}").json()["name"] == "Northwind"


def test_delete_brand_only_removes_the_owned_row(client: TestClient, db: Session) -> None:
    _register_and_login(client, USER_A)
    created = _create_brand(client)
    kept = _create_brand(client, {**BRAND_A, "name": "Kept"})

    deleted = client.delete(f"/api/v1/brands/{created['id']}")
    missing = client.delete(f"/api/v1/brands/{uuid4()}")

    assert deleted.status_code == 204
    assert deleted.content == b""
    assert client.get(f"/api/v1/brands/{created['id']}").status_code == 404
    assert missing.status_code == 404
    assert db.get(Brand, UUID(kept["id"])) is not None
    assert db.get(Brand, UUID(created["id"])) is None


def test_delete_non_owner_does_not_remove_brand(client: TestClient) -> None:
    _register_and_login(client, USER_A)
    created = _create_brand(client)

    with TestClient(app) as other:
        _register_and_login(other, USER_B)
        foreign = other.delete(f"/api/v1/brands/{created['id']}")

    assert foreign.status_code == 404
    assert client.get(f"/api/v1/brands/{created['id']}").status_code == 200


def test_openapi_documents_brand_schemas(client: TestClient) -> None:
    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    body = schema.json()
    paths = body["paths"]

    assert set(paths["/api/v1/brands"]) >= {"get", "post"}
    assert set(paths["/api/v1/brands/{brand_id}"]) >= {"get", "patch", "delete"}

    models = body["components"]["schemas"]
    for name in ("BrandCreate", "BrandUpdate", "BrandResponse", "BrandListResponse"):
        assert name in models
        assert "owner_id" not in models[name].get("properties", {})
