import pandas as pd


PROPERTY_TYPE_MAPPING = {
    "flat": ("Appartement", "Prix_Appartement_m2", "Loyer_Appartement_m2"),
    "house": ("Maison", "Prix_Maison_m2", "Loyer_Maison_m2"),
}


def clean_number(value: object) -> float | None:
    if pd.isna(value):
        return None

    normalized = str(value).replace(" ", "").replace(",", ".")
    try:
        return float(normalized)
    except ValueError:
        return None


def find_matching_city(city_name: str, prices_df: pd.DataFrame) -> str | None:
    city_name = city_name.casefold().strip()
    for city in prices_df["Ville"].astype(str).str.casefold().str.strip():
        if city and city in city_name:
            return city
    return None


def build_opportunities(ads_df: pd.DataFrame, prices_df: pd.DataFrame) -> pd.DataFrame:
    ads = ads_df.copy()
    prices = prices_df.copy()

    for column in ("price", "surfaceArea"):
        ads[column] = ads[column].apply(clean_number)

    price_columns = [
        "Prix_Appartement_m2",
        "Prix_Maison_m2",
        "Loyer_Appartement_m2",
        "Loyer_Maison_m2",
    ]
    for column in price_columns:
        if column not in prices.columns:
            prices[column] = None
        prices[column] = prices[column].apply(clean_number)

    prices["Ville"] = prices["Ville"].astype(str).str.casefold().str.strip()
    ads["city"] = ads["city"].astype(str).str.casefold().str.strip()
    ads["property_type"] = ads["property_type"].astype(str).str.casefold().str.strip()

    results: list[dict[str, object]] = []

    for _, row in ads.iterrows():
        price = row.get("price")
        surface = row.get("surfaceArea")
        property_type = row.get("property_type")
        city = row.get("city")

        if pd.isna(price) or pd.isna(surface) or surface == 0:
            continue

        matched_city = find_matching_city(str(city), prices)
        if matched_city is None or property_type not in PROPERTY_TYPE_MAPPING:
            continue

        type_label, price_column, rent_column = PROPERTY_TYPE_MAPPING[str(property_type)]
        reference_row = prices[prices["Ville"] == matched_city].iloc[0]
        reference_price = reference_row[price_column]
        reference_rent = reference_row[rent_column]

        if not reference_price or pd.isna(reference_price):
            continue

        listing_price_m2 = float(price) / float(surface)
        discount = ((float(reference_price) - listing_price_m2) / float(reference_price)) * 100
        gross_yield = (float(reference_rent) * 12) / listing_price_m2 if reference_rent else 0

        if discount <= 10:
            continue

        results.append(
            {
                "Ville": matched_city,
                "Type": type_label,
                "Prix": price,
                "Prix_annonce_m2": round(listing_price_m2, 2),
                "Prix_reference_m2": reference_price,
                "Decote_%": round(discount, 2),
                "Rendement_brut": round(gross_yield, 4),
                "Label": "Decote >20%" if discount > 20 else "Decote >10%",
                "Url": row.get("url", ""),
            }
        )

    return pd.DataFrame(results)
