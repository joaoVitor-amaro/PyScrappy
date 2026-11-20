"""Pydantic contracts for the web dashboard HTTP API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FieldOption(BaseModel):
    value: str
    label: str


class FieldInfo(BaseModel):
    name: str
    label: str
    type: str
    required: bool = False
    default: Any = None
    options: list[FieldOption] = Field(default_factory=list)
    minimum: int | None = None
    maximum: int | None = None
    help: str = ""


class ScraperInfo(BaseModel):
    id: str
    label: str
    description: str
    source_url: str
    attribution: str = ""
    fields: list[str] = Field(default_factory=list)


class ScraperList(BaseModel):
    fields: list[FieldInfo]
    scrapers: list[ScraperInfo]


class ScrapeRequest(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)


class ErrorInfo(BaseModel):
    url: str
    message: str
    selector: str | None = None


class RunResult(BaseModel):
    scraper: str
    params: dict[str, Any]
    count: int
    data: list[dict[str, Any]]
    metadata: dict[str, Any]
    errors: list[ErrorInfo]
    elapsed_ms: int
    truncated: bool = False
