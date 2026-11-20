"""Catalog and parameter-validation tests for the job-search web UI."""

from __future__ import annotations

import pytest

from pyscrappy.web import catalog
from pyscrappy.web.catalog import common_fields, get_spec, list_specs
from pyscrappy.web.runner import coerce_params


def test_catalog_only_lists_job_sources():
    ids = {spec.id for spec in list_specs()}
    assert {"arbeitnow", "linkedin"} <= ids
    assert not ({"wikipedia", "hackernews", "github"} & ids)


def test_gupy_is_listed_when_registered(monkeypatch: pytest.MonkeyPatch):
    class FakeGupy:
        def scrape(self, query: str, location: str = "", max_pages: int = 1):
            return None

    monkeypatch.setattr(catalog, "list_scrapers", lambda: {"gupy": FakeGupy})
    monkeypatch.setattr(catalog, "get_scraper", lambda name: FakeGupy)

    gupy = get_spec("gupy")
    assert gupy is not None
    assert gupy.supported_fields == ("query", "location", "max_pages")


def test_common_fields_are_shared_by_every_source():
    fields = {field.name: field for field in common_fields()}
    assert list(fields) == ["query", "location", "remote", "job_type", "max_pages", "max_results"]
    assert fields["query"].required is True
    assert fields["max_pages"].minimum == 1
    assert fields["max_pages"].maximum == 5
    assert [option[0] for option in fields["remote"].options] == ["", "true", "false"]


def test_sources_declare_which_common_fields_they_support():
    arbeitnow = get_spec("arbeitnow")
    linkedin = get_spec("linkedin")
    assert arbeitnow is not None
    assert linkedin is not None
    assert arbeitnow.supported_fields == tuple(field.name for field in common_fields())
    assert linkedin.supported_fields == ("query", "location", "max_pages")
    assert get_spec("wikipedia") is None


def test_coerce_params_coerces_and_ignores_unsupported_fields():
    arbeitnow = get_spec("arbeitnow")
    linkedin = get_spec("linkedin")
    assert arbeitnow is not None
    assert linkedin is not None

    params = coerce_params(
        arbeitnow,
        {
            "query": " python ",
            "remote": "true",
            "max_pages": "2",
            "max_results": 10,
            "location": "Berlin",
            "job_type": "Full Time",
        },
    )
    assert params == {
        "query": "python",
        "location": "Berlin",
        "remote": True,
        "job_type": "Full Time",
        "max_pages": 2,
        "max_results": 10,
    }

    linkedin_params = coerce_params(
        linkedin,
        {"query": "python", "remote": "true", "job_type": "Full Time", "max_results": 10},
    )
    assert linkedin_params == {"query": "python", "location": "", "max_pages": 1}


@pytest.mark.parametrize(
    ("field_value", "expected"),
    [("", None), ("true", True), ("false", False), (True, True), (False, False)],
)
def test_coerce_tri_values(field_value, expected):
    spec = get_spec("arbeitnow")
    assert spec is not None
    assert coerce_params(spec, {"query": "python", "remote": field_value})["remote"] is expected


def test_coerce_rejects_invalid_values():
    spec = get_spec("linkedin")
    assert spec is not None
    with pytest.raises(ValueError, match="não permitido"):
        coerce_params(spec, {"query": "python", "token": "secret"})
    with pytest.raises(ValueError, match="obrigatório"):
        coerce_params(spec, {"query": ""})
    with pytest.raises(ValueError, match=">= 1"):
        coerce_params(spec, {"query": "python", "max_pages": 0})
    with pytest.raises(ValueError, match="<= 5"):
        coerce_params(spec, {"query": "python", "max_pages": 99})
