"""FastAPI application that serves the local scraper dashboard."""

from __future__ import annotations

import argparse
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from pyscrappy.web.catalog import common_fields, list_specs
from pyscrappy.web.runner import run_scrape
from pyscrappy.web.schemas import (
    FieldInfo,
    FieldOption,
    RunResult,
    ScrapeRequest,
    ScraperInfo,
    ScraperList,
)

_STATIC = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    """Build the dashboard app with its JSON API and static single-page UI."""
    app = FastAPI(
        title="PyScrappy · Buscador de Vagas de TI",
        description="Busque e compare vagas de TI entre fontes públicas com PyScrappy.",
        version="1.6.4",
    )
    app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(_STATIC / "index.html")

    @app.get("/api/scrapers", response_model=ScraperList)
    async def scrapers() -> ScraperList:
        return ScraperList(
            fields=[
                FieldInfo(
                    name=field.name,
                    label=field.label,
                    type=field.type,
                    required=field.required,
                    default=field.default,
                    options=[
                        FieldOption(value=value, label=label) for value, label in field.options
                    ],
                    minimum=field.minimum,
                    maximum=field.maximum,
                    help=field.help,
                )
                for field in common_fields()
            ],
            scrapers=[
                ScraperInfo(
                    id=spec.id,
                    label=spec.label,
                    description=spec.description,
                    source_url=spec.source_url,
                    attribution=spec.attribution,
                    fields=list(spec.supported_fields),
                )
                for spec in list_specs()
            ],
        )

    @app.post("/api/scrape/{name}", response_model=RunResult)
    async def scrape(name: str, request: ScrapeRequest) -> RunResult:
        try:
            payload = await run_scrape(name, request.params)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"scraper desconhecido: {name}") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"{type(exc).__name__}: {exc}") from exc
        return RunResult(**payload)

    return app


app = create_app()


def main() -> None:
    """Console entry point for ``pyscrappy-web``."""
    parser = argparse.ArgumentParser(description="Start the PyScrappy scraper dashboard.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1).")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000).")
    args = parser.parse_args()

    import uvicorn

    uvicorn.run(create_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
