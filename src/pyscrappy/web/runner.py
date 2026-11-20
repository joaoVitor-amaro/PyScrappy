"""Validation and execution of curated job scrapers for the web dashboard."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from pyscrappy.core.config import ScraperConfig
from pyscrappy.registry import get_scraper
from pyscrappy.scrapers.arbeitnow import ArbeitnowScraper
from pyscrappy.scrapers.linkedin import LinkedInJobsScraper
from pyscrappy.web.catalog import FieldSpec, ScraperSpec, common_fields, get_spec

_CACHE_TTL = 300.0
_MAX_TEXT_INPUT = 200
_MAX_CELL_CHARS = 1200
_MAX_ROWS = 50
_MAX_RESPONSE_CHARS = 400_000

_SCRAPERS = {
    "arbeitnow": ArbeitnowScraper,
    "linkedin": LinkedInJobsScraper,
}


def coerce_params(spec: ScraperSpec, raw: dict[str, Any]) -> dict[str, Any]:
    """Validate browser-supplied parameters against the common job-search form."""
    common = {field.name: field for field in common_fields()}
    unknown = sorted(set(raw) - set(common))
    if unknown:
        raise ValueError(f"parâmetro não permitido: {', '.join(unknown)}")

    params: dict[str, Any] = {}
    for name in spec.supported_fields:
        field: FieldSpec = common[name]
        params[name] = _coerce_field(field, raw.get(name, field.default))
    return params


def _coerce_field(field: FieldSpec, value: Any) -> Any:
    if field.type == "text":
        if value is None:
            if field.required:
                raise ValueError(f"{field.name} é obrigatório")
            return ""
        if not isinstance(value, str):
            raise ValueError(f"{field.name} deve ser texto")
        text = value.strip()
        if field.required and not text:
            raise ValueError(f"{field.name} é obrigatório")
        if len(text) > _MAX_TEXT_INPUT:
            raise ValueError(f"{field.name} excede {_MAX_TEXT_INPUT} caracteres")
        return text

    if field.type == "number":
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            raise ValueError(f"{field.name} deve ser um número inteiro")
        try:
            number = int(str(value).strip())
        except ValueError as exc:
            raise ValueError(f"{field.name} deve ser um número inteiro") from exc
        if field.minimum is not None and number < field.minimum:
            raise ValueError(f"{field.name} deve ser >= {field.minimum}")
        if field.maximum is not None and number > field.maximum:
            raise ValueError(f"{field.name} deve ser <= {field.maximum}")
        return number

    if field.type == "select":
        allowed = [option for option, _ in field.options]
        if not isinstance(value, str) or value not in allowed:
            raise ValueError(f"{field.name} deve ser um de: {', '.join(allowed)}")
        return value

    if field.type == "tri":
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return value
        if value in ("true", "false"):
            return value == "true"
        raise ValueError(f"{field.name} deve ser 'true', 'false' ou vazio")

    raise ValueError(f"tipo de campo não suportado: {field.type}")


def _truncate(data: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    truncated = len(data) > _MAX_ROWS
    rows: list[dict[str, Any]] = []
    for item in data[:_MAX_ROWS]:
        row: dict[str, Any] = {}
        for key, value in item.items():
            if isinstance(value, str) and len(value) > _MAX_CELL_CHARS:
                row[key] = value[:_MAX_CELL_CHARS] + "…"
                truncated = True
            else:
                row[key] = value
        rows.append(row)
    return rows, truncated


def _scraper_class(name: str) -> type:
    scraper_cls = _SCRAPERS.get(name)
    if scraper_cls is not None:
        return scraper_cls
    try:
        return get_scraper(name)
    except KeyError as exc:
        raise KeyError(name) from exc


async def run_scrape(name: str, raw_params: dict[str, Any]) -> dict[str, Any]:
    """Run one curated job scraper off the event loop and return its JSON envelope."""
    spec = get_spec(name)
    if spec is None:
        raise KeyError(name)

    params = coerce_params(spec, raw_params)
    scraper_cls = _scraper_class(name)
    rate_limit = 5.0 if name == "linkedin" else 1.0

    def _sync() -> Any:
        with scraper_cls(ScraperConfig(cache_ttl=_CACHE_TTL, rate_limit=rate_limit)) as scraper:
            return scraper.scrape(**params)

    started = time.perf_counter()
    result = await asyncio.to_thread(_sync)
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    payload: dict[str, Any] = json.loads(result.to_json())
    data, truncated = _truncate(payload.get("data", []))
    payload.update(
        scraper=name,
        params=params,
        data=data,
        count=len(data),
        elapsed_ms=elapsed_ms,
        truncated=truncated,
    )

    while data and len(json.dumps(payload, ensure_ascii=False, default=str)) > _MAX_RESPONSE_CHARS:
        data.pop()
        payload["data"] = data
        payload["count"] = len(data)
        payload["truncated"] = True

    return payload
