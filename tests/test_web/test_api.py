"""HTTP tests for the job-search web UI, with scrapers mocked (no network)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from pyscrappy.core.models import ScrapeError, ScrapeMetadata, ScrapeResult  # noqa: E402
from pyscrappy.web import app as web_app  # noqa: E402
from pyscrappy.web import runner  # noqa: E402


@pytest.fixture()
def client() -> TestClient:
    return TestClient(web_app.create_app())


def _mock_scraper(monkeypatch: pytest.MonkeyPatch, name: str, result: ScrapeResult) -> MagicMock:
    instance = MagicMock()
    instance.__enter__.return_value = instance
    instance.__exit__.return_value = False
    instance.scrape.return_value = result
    monkeypatch.setitem(runner._SCRAPERS, name, MagicMock(return_value=instance))
    return instance


def _job() -> dict:
    return {
        "title": "Python Developer",
        "company": "Example GmbH",
        "location": "Berlin",
        "url": "https://www.arbeitnow.com/jobs/example",
        "tags": ["Python", "Backend"],
        "job_types": ["Full Time"],
        "remote": True,
        "created_at": "2026-01-03T12:00:00+00:00",
        "description": "Build APIs.",
    }


def _result(name: str = "arbeitnow", data: list[dict] | None = None) -> ScrapeResult:
    return ScrapeResult(
        data=data if data is not None else [_job()],
        metadata=ScrapeMetadata(
            source_urls=["https://www.arbeitnow.com/api/job-board-api"], scraper=name
        ),
    )


def test_index_and_openapi_are_served(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    assert "PyScrappy · Buscador de Vagas de TI" in response.text
    assert "Comparar fontes" in response.text
    assert "Nota: o Arbeitnow tem foco em vagas na Europa." in response.text
    assert "Wikipedia" not in response.text
    assert "Hacker News" not in response.text
    assert client.get("/docs").status_code == 200


def test_catalog_exposes_common_fields_and_job_sources_only(client: TestClient):
    response = client.get("/api/scrapers")
    assert response.status_code == 200

    payload = response.json()
    assert [field["name"] for field in payload["fields"]] == [
        "query",
        "location",
        "remote",
        "job_type",
        "max_pages",
        "max_results",
    ]
    specs = {item["id"]: item for item in payload["scrapers"]}
    assert set(specs) == {"arbeitnow", "linkedin"}
    assert specs["arbeitnow"]["fields"] == [field["name"] for field in payload["fields"]]
    assert specs["linkedin"]["fields"] == ["query", "location", "max_pages"]
    assert "Europa" in specs["arbeitnow"]["description"]


def test_run_arbeitnow_forwards_common_params(client: TestClient, monkeypatch):
    instance = _mock_scraper(monkeypatch, "arbeitnow", _result())

    response = client.post(
        "/api/scrape/arbeitnow",
        json={
            "params": {
                "query": " python ",
                "location": "Berlin",
                "remote": "true",
                "job_type": "Full Time",
                "max_pages": "2",
                "max_results": 10,
            }
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["scraper"] == "arbeitnow"
    assert body["count"] == 1
    assert body["data"][0]["tags"] == ["Python", "Backend"]
    assert body["params"]["query"] == "python"
    assert body["params"]["remote"] is True
    assert body["params"]["max_pages"] == 2
    assert isinstance(body["elapsed_ms"], int)
    assert body["metadata"]["source_urls"] == ["https://www.arbeitnow.com/api/job-board-api"]
    assert body["errors"] == []

    kwargs = instance.scrape.call_args.kwargs
    assert kwargs["query"] == "python"
    assert kwargs["remote"] is True
    assert kwargs["max_pages"] == 2


def test_run_linkedin_ignores_unsupported_params(client: TestClient, monkeypatch):
    result = _result(
        "linkedin", [{"title": "Dev", "company": "ACME", "url": "https://example.com"}]
    )
    instance = _mock_scraper(monkeypatch, "linkedin", result)

    response = client.post(
        "/api/scrape/linkedin",
        json={
            "params": {
                "query": "python",
                "location": "Berlin",
                "remote": "true",
                "job_type": "Full Time",
                "max_pages": 2,
                "max_results": 10,
            }
        },
    )

    assert response.status_code == 200
    assert response.json()["params"] == {"query": "python", "location": "Berlin", "max_pages": 2}
    assert instance.scrape.call_args.kwargs == {
        "query": "python",
        "location": "Berlin",
        "max_pages": 2,
    }


def test_zero_jobs_without_errors_is_not_a_failure(client: TestClient, monkeypatch):
    _mock_scraper(monkeypatch, "arbeitnow", _result(data=[]))

    response = client.post("/api/scrape/arbeitnow", json={"params": {"query": "rust"}})

    assert response.status_code == 200
    assert response.json()["count"] == 0
    assert response.json()["errors"] == []


def test_typed_errors_are_preserved(client: TestClient, monkeypatch):
    result = _result(data=[])
    result.errors.append(
        ScrapeError(
            url="https://www.linkedin.com/jobs/search/",
            message="LinkedIn requires authentication for this page.",
        )
    )
    _mock_scraper(monkeypatch, "linkedin", result)

    response = client.post("/api/scrape/linkedin", json={"params": {"query": "python"}})

    assert response.status_code == 200
    assert response.json()["errors"] == [
        {
            "url": "https://www.linkedin.com/jobs/search/",
            "message": "LinkedIn requires authentication for this page.",
            "selector": None,
        }
    ]


def test_removed_sources_are_not_executable(client: TestClient):
    for name in ("wikipedia", "hackernews", "github"):
        response = client.post(f"/api/scrape/{name}", json={"params": {"query": "python"}})
        assert response.status_code == 404


@pytest.mark.parametrize(
    "params",
    [
        {"query": "python", "proxy": "http://localhost:8080"},
        {"query": ""},
        {"query": "python", "max_pages": 99},
        {"query": "python", "remote": "maybe"},
    ],
)
def test_invalid_params_return_400(client: TestClient, params: dict):
    response = client.post("/api/scrape/arbeitnow", json={"params": params})
    assert response.status_code == 400
    assert response.json()["detail"]


def test_scraper_exception_returns_502(client: TestClient, monkeypatch):
    instance = _mock_scraper(monkeypatch, "linkedin", _result("linkedin"))
    instance.scrape.side_effect = RuntimeError("API offline")

    response = client.post("/api/scrape/linkedin", json={"params": {"query": "python"}})

    assert response.status_code == 502
    assert "RuntimeError: API offline" in response.json()["detail"]


def test_long_text_and_excess_rows_are_truncated(client: TestClient, monkeypatch):
    data = [{"description": "x" * 1400} for _ in range(60)]
    _mock_scraper(monkeypatch, "arbeitnow", _result(data=data))

    response = client.post(
        "/api/scrape/arbeitnow",
        json={"params": {"query": "python", "max_results": 50}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["truncated"] is True
    assert body["count"] == 50
    assert body["data"][0]["description"].endswith("…")
    assert len(body["data"][0]["description"]) == 1201
