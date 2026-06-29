#!/usr/bin/env python3

import argparse
from pathlib import Path

from bieniciscraper.constants import MAX_LIMIT_VAL, MIN_LIMIT_VAL
from bieniciscraper.scraper import scrape

# Chemin par défaut : répertoire data de l'API, compatible avec run_analysis.py
DEFAULT_OUTPUT = str(
    Path(__file__).resolve().parent.parent
    / "apps" / "api" / "app" / "data" / "bienici.csv"
)


def range_limited_integer_type(arg: str) -> int:
    try:
        value = int(arg)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc

    if value < MIN_LIMIT_VAL or value > MAX_LIMIT_VAL:
        raise argparse.ArgumentTypeError(f"must be between {MIN_LIMIT_VAL} and {MAX_LIMIT_VAL}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scraper d'annonces Bien'ici vers CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Exemples :
  # Scraper les appartements en Haute-Garonne (100 annonces) :
  python main.py --url "https://www.bienici.com/recherche/achat/haute-garonne-31/appartement" --limit 100

  # Scraper vers un fichier personnalisé :
  python main.py --url "https://www.bienici.com/recherche/achat/haute-garonne-31" --output data/test.csv

  # Sortie par défaut (compatible run_analysis.py) :
  {DEFAULT_OUTPUT}
""",
    )

    parser.add_argument(
        "-u",
        "--url",
        type=str,
        required=False,
        default="https://www.bienici.com/recherche/achat/haute-garonne-31",
        help="URL de recherche Bien'ici à scraper",
    )

    parser.add_argument(
        "-l",
        "--limit",
        type=range_limited_integer_type,
        required=False,
        default=500,
        help=f"nombre maximum d'annonces à récupérer (entre {MIN_LIMIT_VAL} et {MAX_LIMIT_VAL}, défaut : 500)",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=str,
        required=False,
        default=DEFAULT_OUTPUT,
        help=f"chemin du fichier CSV de sortie (défaut : {DEFAULT_OUTPUT})",
    )

    args = parser.parse_args()

    print(f"URL      : {args.url}")
    print(f"Limite   : {args.limit} annonces")
    print(f"Sortie   : {args.output}")
    print()

    scrape(url=args.url, limit=args.limit, output=args.output)


if __name__ == "__main__":
    main()
