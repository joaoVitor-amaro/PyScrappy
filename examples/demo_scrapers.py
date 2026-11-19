"""Run a small live demonstration of the built-in scrapers.

Usage::

    python examples/demo_scrapers.py
    python examples/demo_scrapers.py --query python --limit 3

The demo uses public endpoints and does not require API keys. Network failures are
reported per scraper so one unavailable service does not hide the other result.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from pyscrappy import HackerNewsScraper, WikipediaScraper


def _sample(data: list[dict[str, Any]], limit: int) -> str:
    """Render only a few rows so the terminal output stays readable."""
    return json.dumps(data[:limit], ensure_ascii=False, indent=2, default=str)


def run_demo(query: str = "Python programming", limit: int = 3) -> int:
    """Execute the demo and return a non-zero status only if every scraper fails."""
    runs = [
        (
            "Wikipedia",
            WikipediaScraper,
            lambda scraper: scraper.scrape(query=query, mode="summary"),
        ),
        (
            "Hacker News",
            HackerNewsScraper,
            lambda scraper: scraper.scrape(query=query, max_results=limit),
        ),
    ]
    successful = 0

    print(f"PyScrappy scraper demo | query={query!r}\n")
    for label, scraper_cls, scrape in runs:
        print(f"[{label}]")
        try:
            with scraper_cls() as scraper:
                result = scrape(scraper)
        except Exception as exc:  # noqa: BLE001 - demo must show failures clearly
            print(f"status: ERROR ({type(exc).__name__}: {exc})\n")
            continue

        if result.data:
            successful += 1
            print(f"status: OK | items: {len(result.data)}")
            print(_sample(result.data, limit))
        else:
            print("status: ERROR | items: 0")

        for error in result.errors:
            print(f"error: {error.message}")
        print()

    print(f"Summary: {successful}/{len(runs)} scrapers returned data.")
    return 0 if successful else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Show PyScrappy scrapers running live.")
    parser.add_argument("--query", default="Python programming", help="Search term/article.")
    parser.add_argument("--limit", type=int, default=3, help="Maximum sample rows to print.")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be at least 1")
    raise SystemExit(run_demo(args.query, args.limit))


if __name__ == "__main__":
    main()
