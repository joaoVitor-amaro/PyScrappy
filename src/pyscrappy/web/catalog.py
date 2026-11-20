"""Curated catalog of job scrapers exposed by the local web dashboard.

Only sources listed here can be executed through HTTP: the dashboard is a demo of
known job sources, not a generic remote-code or arbitrary-URL endpoint.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, replace
from typing import Any

from pyscrappy.registry import get_scraper, list_scrapers


@dataclass(frozen=True)
class FieldSpec:
    """One field of the common job-search form."""

    name: str
    label: str
    type: str
    required: bool = False
    default: Any = None
    options: tuple[tuple[str, str], ...] = ()
    minimum: int | None = None
    maximum: int | None = None
    help: str = ""


@dataclass(frozen=True)
class ScraperSpec:
    """Metadata and supported parameters of a job source in the dashboard."""

    id: str
    label: str
    description: str
    source_url: str
    supported_fields: tuple[str, ...]
    attribution: str = ""


_COMMON_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec(
        "query",
        "Palavra-chave",
        "text",
        required=True,
        default="python",
        help="Ex.: python developer",
    ),
    FieldSpec("location", "Localização", "text", default="", help="Ex.: Berlim, remoto."),
    FieldSpec(
        "remote",
        "Trabalho remoto",
        "tri",
        default="",
        options=(("", "Qualquer"), ("true", "Sim"), ("false", "Não")),
    ),
    FieldSpec("job_type", "Tipo de vaga", "text", default="", help="Ex.: Full Time."),
    FieldSpec("max_pages", "Máx. de páginas", "number", default=1, minimum=1, maximum=5),
    FieldSpec("max_results", "Máx. de resultados", "number", default=20, minimum=1, maximum=50),
)

_ALL_FIELDS = tuple(field.name for field in _COMMON_FIELDS)

_ARBEITNOW = ScraperSpec(
    id="arbeitnow",
    label="Arbeitnow",
    description="API pública de vagas, com foco na Europa. Filtros aplicados localmente.",
    source_url="https://www.arbeitnow.com",
    supported_fields=_ALL_FIELDS,
    attribution="Dados: Arbeitnow — use de forma moderada e cite a fonte.",
)

_LINKEDIN = ScraperSpec(
    id="linkedin",
    label="LinkedIn Jobs",
    description="Busca pública do LinkedIn (experimental); pode exigir login ou sofrer bloqueio.",
    source_url="https://www.linkedin.com/jobs",
    supported_fields=("query", "location", "max_pages"),
    attribution="Dados: LinkedIn — acesso público e experimental.",
)

_GUPY = ScraperSpec(
    id="gupy",
    label="Gupy",
    description="Busca de vagas no Gupy, quando o scraper estiver registrado.",
    source_url="https://portal.gupy.io",
    supported_fields=_ALL_FIELDS,
    attribution="Dados: Gupy.",
)


def common_fields() -> tuple[FieldSpec, ...]:
    """Return the single form shared by every job source."""
    return _COMMON_FIELDS


def list_specs() -> tuple[ScraperSpec, ...]:
    """Return the job sources available in the dashboard, in display order."""
    specs = [_ARBEITNOW, _LINKEDIN]
    if "gupy" in list_scrapers():
        specs.append(replace(_GUPY, supported_fields=_supported_fields(get_scraper("gupy"))))
    return tuple(specs)


def get_spec(name: str) -> ScraperSpec | None:
    """Return the spec for ``name`` or ``None`` when it is not curated."""
    for spec in list_specs():
        if spec.id == name:
            return spec
    return None


def _supported_fields(scraper_cls: type) -> tuple[str, ...]:
    try:
        parameters = inspect.signature(scraper_cls.scrape).parameters
    except (TypeError, ValueError):
        return _ALL_FIELDS
    return tuple(field for field in _ALL_FIELDS if field in parameters)
