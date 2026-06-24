from pathlib import Path

import pandas as pd

from app.schemas import Opportunity


COLUMN_ALIASES = {
    "Ville": "city",
    "Type": "property_type",
    "Prix": "price",
    "Prix_annonce_m2": "listing_price_m2",
    "Prix_reference_m2": "reference_price_m2",
    "Decote_%": "discount_percent",
    "Décote_%": "discount_percent",
    "DÃ©cote_%": "discount_percent",
    "Rendement_brut": "gross_yield",
    "Label": "label",
    "Url": "url",
}


def _read_csv(path: Path) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "utf-8", "ISO-8859-1"):
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path)


def load_opportunities(path: Path) -> list[Opportunity]:
    if not path.exists():
        return []

    df = _read_csv(path).rename(columns=COLUMN_ALIASES)
    required = set(COLUMN_ALIASES.values())
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Colonnes manquantes dans {path}: {sorted(missing)}")

    df = df.dropna(subset=["city", "property_type", "price", "url"])
    df["city"] = df["city"].astype(str).str.strip().str.title()
    df["property_type"] = df["property_type"].astype(str).str.strip()
    df["label"] = df["label"].astype(str).str.strip()

    for column in ("price", "listing_price_m2", "reference_price_m2", "discount_percent", "gross_yield"):
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df = df.dropna(subset=["price", "listing_price_m2", "reference_price_m2", "discount_percent"])
    df = df.sort_values(["discount_percent", "gross_yield"], ascending=[False, False])

    return [Opportunity.model_validate(row) for row in df.to_dict(orient="records")]

