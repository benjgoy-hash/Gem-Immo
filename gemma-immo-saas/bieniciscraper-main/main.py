#!/usr/bin/env python3

import argparse

from bieniciscraper.constants import MAX_LIMIT_VAL, MIN_LIMIT_VAL
from bieniciscraper.scraper import scrape


def range_limited_integer_type(arg: str) -> int:
    try:
        value = int(arg)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc

    if value < MIN_LIMIT_VAL or value > MAX_LIMIT_VAL:
        raise argparse.ArgumentTypeError(f"must be between {MIN_LIMIT_VAL} and {MAX_LIMIT_VAL}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Scraper d'annonces Bien'ici vers CSV")

    parser.add_argument(
        "-u",
        "--url",
        type=str,
        required=False,
        default="https://www.bienici.com/recherche/achat/france/appartement",
        help="URL de recherche Bien'ici a scraper",
    )

    parser.add_argument(
        "-l",
        "--limit",
        type=range_limited_integer_type,
        required=False,
        default=100,
        help="nombre maximum d'annonces a scraper",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=str,
        required=False,
        default="data_bienici_lobstr_io.csv",
        help="chemin du fichier CSV de sortie",
    )

    args = parser.parse_args()
    scrape(url=args.url, limit=args.limit, output=args.output)


if __name__ == "__main__":
    main()

