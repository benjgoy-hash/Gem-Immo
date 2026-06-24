import argparse
from pathlib import Path

import pandas as pd

from app.services.scoring import build_opportunities


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calcule les opportunites immobilieres.")
    parser.add_argument("--ads", required=True, type=Path, help="CSV issu du scraper Bien'ici.")
    parser.add_argument("--prices", required=True, type=Path, help="CSV des prix de reference.")
    parser.add_argument("--output", required=True, type=Path, help="CSV resultats a generer.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ads_df = pd.read_csv(args.ads, encoding="utf-8-sig")
    prices_df = pd.read_csv(args.prices, encoding="ISO-8859-1")
    result_df = build_opportunities(ads_df, prices_df)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"{len(result_df)} opportunites ecrites dans {args.output}")


if __name__ == "__main__":
    main()

