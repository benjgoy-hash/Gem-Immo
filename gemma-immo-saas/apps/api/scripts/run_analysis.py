import argparse
from pathlib import Path

import pandas as pd

from app.services.dvf_market import DvfMarketError, build_market_prices_from_dvf
from app.services.scoring import build_opportunities


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calcule les opportunites immobilieres.")
    parser.add_argument("--ads", required=True, type=Path, help="CSV issu du scraper Bien'ici.")
    parser.add_argument(
        "--prices",
        required=False,
        type=Path,
        default=Path("app/data/prix_immo.csv"),
        help="CSV de fallback des prix de reference.",
    )
    parser.add_argument("--output", required=True, type=Path, help="CSV resultats a generer.")
    parser.add_argument(
        "--market-source",
        choices=["csv", "dvf", "auto"],
        default="csv",
        help="Source des prix de reference: csv, dvf, ou auto avec fallback CSV.",
    )
    parser.add_argument(
        "--dvf-cache",
        type=Path,
        default=Path("app/data/market_prices_dvf.csv"),
        help="Cache CSV des prix calcules depuis DVF.",
    )
    parser.add_argument(
        "--dvf-cache-max-age-days",
        type=int,
        default=30,
        help="Age maximum du cache DVF avant rafraichissement.",
    )
    parser.add_argument(
        "--dvf-years",
        type=int,
        default=3,
        help="Nombre d'annees DVF a utiliser pour calculer les medianes.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ads_df = pd.read_csv(args.ads, encoding="utf-8-sig")
    fallback_prices_df = pd.read_csv(args.prices, encoding="ISO-8859-1") if args.prices.exists() else None

    if args.market_source == "csv":
        if fallback_prices_df is None:
            raise FileNotFoundError(f"Fichier prix introuvable: {args.prices}")
        prices_df = fallback_prices_df
    else:
        try:
            prices_df = build_market_prices_from_dvf(
                ads_df=ads_df,
                fallback_prices_df=fallback_prices_df,
                cache_path=args.dvf_cache,
                max_age_days=args.dvf_cache_max_age_days,
                years=args.dvf_years,
            )
            print(f"Prix de reference charges depuis DVF/cache: {args.dvf_cache}")
        except (DvfMarketError, OSError, ValueError) as exc:
            if args.market_source == "dvf" or fallback_prices_df is None:
                raise
            print(f"DVF indisponible ({exc}). Fallback vers {args.prices}.")
            prices_df = fallback_prices_df

    result_df = build_opportunities(ads_df, prices_df)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"{len(result_df)} opportunites ecrites dans {args.output}")


if __name__ == "__main__":
    main()
