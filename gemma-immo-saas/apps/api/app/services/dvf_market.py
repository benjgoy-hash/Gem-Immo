from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from statistics import median
from typing import Any

import pandas as pd
import requests

from app.services.scoring import clean_number


DVF_API_URL = "https://api.cquest.org/dvf"
GEO_API_URL = "https://geo.api.gouv.fr/communes"
DEFAULT_TIMEOUT = 20

MARKET_COLUMNS = [
    "Ville",
    "Code_Commune",
    "Prix_Appartement_m2",
    "Prix_Maison_m2",
    "Loyer_Appartement_m2",
    "Loyer_Maison_m2",
    "Source",
    "Nb_Appartement_DVF",
    "Nb_Maison_DVF",
]


@dataclass(frozen=True)
class CityKey:
    city: str
    postal_code: str | None = None


class DvfMarketError(RuntimeError):
    """Raised when the external market price source cannot be used."""


def build_market_prices_from_dvf(
    ads_df: pd.DataFrame,
    fallback_prices_df: pd.DataFrame | None = None,
    cache_path: Path | None = None,
    max_age_days: int = 30,
    years: int = 3,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    """Build a price reference table from DVF, with optional CSV cache and fallback rents."""
    if cache_path and _is_fresh_cache(cache_path, max_age_days):
        return pd.read_csv(cache_path, encoding="utf-8-sig")

    http = session or requests.Session()
    fallback = _normalize_fallback_prices(fallback_prices_df)
    rows = []

    for city_key in _extract_city_keys(ads_df):
        commune_code = resolve_commune_code(http, city_key)
        if not commune_code:
            rows.append(_fallback_row(city_key.city, fallback, reason="geo_api_missing"))
            continue

        mutations = fetch_dvf_mutations(http, commune_code, years=years)
        row = _build_city_price_row(city_key.city, commune_code, mutations)
        row = _merge_missing_values_with_fallback(row, fallback)
        rows.append(row)

    market_df = pd.DataFrame(rows, columns=MARKET_COLUMNS)
    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        market_df.to_csv(cache_path, index=False, encoding="utf-8-sig")

    return market_df


def resolve_commune_code(session: requests.Session, city_key: CityKey) -> str | None:
    params = {
        "nom": city_key.city,
        "fields": "code,nom,codesPostaux",
        "format": "json",
        "boost": "population",
        "limit": 5,
    }
    if city_key.postal_code:
        params["codePostal"] = city_key.postal_code

    response = session.get(GEO_API_URL, params=params, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    candidates = response.json()
    if not candidates:
        return None

    if city_key.postal_code:
        for candidate in candidates:
            if city_key.postal_code in candidate.get("codesPostaux", []):
                return candidate.get("code")

    return candidates[0].get("code")


def fetch_dvf_mutations(session: requests.Session, commune_code: str, years: int = 3) -> list[dict[str, Any]]:
    min_date = date.today() - timedelta(days=365 * years)
    params = {
        "code_commune": commune_code,
        "date_min": min_date.isoformat(),
    }

    response = session.get(DVF_API_URL, params=params, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    return _extract_records(response.json())


def _extract_city_keys(ads_df: pd.DataFrame) -> list[CityKey]:
    keys = set()
    for _, row in ads_df.iterrows():
        city = str(row.get("city", "")).strip()
        if not city:
            continue
        postal_code = row.get("postal_code") or row.get("postalCode")
        postal_code = str(postal_code).strip() if not pd.isna(postal_code) else None
        keys.add(CityKey(city=city, postal_code=postal_code or None))
    return sorted(keys, key=lambda item: (item.city.casefold(), item.postal_code or ""))


def _extract_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if isinstance(payload.get("features"), list):
            return [feature.get("properties", {}) for feature in payload["features"]]
        for key in ("results", "data", "mutations"):
            if isinstance(payload.get(key), list):
                return payload[key]
    raise DvfMarketError("Unexpected DVF response format.")


def _build_city_price_row(city: str, commune_code: str, mutations: list[dict[str, Any]]) -> dict[str, Any]:
    apartment_prices = []
    house_prices = []

    for mutation in mutations:
        price_m2 = _mutation_price_m2(mutation)
        if not price_m2:
            continue

        property_type = _mutation_property_type(mutation)
        if property_type == "Appartement":
            apartment_prices.append(price_m2)
        elif property_type == "Maison":
            house_prices.append(price_m2)

    return {
        "Ville": city,
        "Code_Commune": commune_code,
        "Prix_Appartement_m2": round(median(apartment_prices), 2) if apartment_prices else None,
        "Prix_Maison_m2": round(median(house_prices), 2) if house_prices else None,
        "Loyer_Appartement_m2": None,
        "Loyer_Maison_m2": None,
        "Source": "dvf",
        "Nb_Appartement_DVF": len(apartment_prices),
        "Nb_Maison_DVF": len(house_prices),
    }


def _mutation_price_m2(mutation: dict[str, Any]) -> float | None:
    value = _first_number(
        mutation,
        [
            "valeur_fonciere",
            "valeurFonciere",
            "valeur",
            "prix",
            "Valeur fonciere",
        ],
    )
    surface = _first_number(
        mutation,
        [
            "surface_reelle_bati",
            "surfaceReelleBati",
            "surface_bati",
            "surface",
            "Surface reelle bati",
        ],
    )
    if not value or not surface or surface <= 0:
        return None
    price_m2 = value / surface
    if price_m2 < 300 or price_m2 > 30000:
        return None
    return price_m2


def _mutation_property_type(mutation: dict[str, Any]) -> str | None:
    raw = str(
        mutation.get("type_local")
        or mutation.get("typeLocal")
        or mutation.get("Type local")
        or ""
    ).casefold()
    if "appartement" in raw:
        return "Appartement"
    if "maison" in raw:
        return "Maison"
    return None


def _first_number(mutation: dict[str, Any], keys: list[str]) -> float | None:
    for key in keys:
        if key in mutation:
            value = clean_number(mutation[key])
            if value is not None:
                return value
    return None


def _normalize_fallback_prices(prices_df: pd.DataFrame | None) -> pd.DataFrame | None:
    if prices_df is None or prices_df.empty:
        return None
    fallback = prices_df.copy()
    fallback["Ville"] = fallback["Ville"].astype(str).str.casefold().str.strip()
    return fallback


def _merge_missing_values_with_fallback(row: dict[str, Any], fallback: pd.DataFrame | None) -> dict[str, Any]:
    fallback_row = _find_fallback(row["Ville"], fallback)
    if fallback_row is None:
        return row

    for column in (
        "Prix_Appartement_m2",
        "Prix_Maison_m2",
        "Loyer_Appartement_m2",
        "Loyer_Maison_m2",
    ):
        current_value = clean_number(row.get(column))
        fallback_value = clean_number(fallback_row.get(column))
        if current_value is None and fallback_value is not None:
            row[column] = fallback_value

    if row["Source"] == "dvf" and (
        row["Prix_Appartement_m2"] == fallback_row.get("Prix_Appartement_m2")
        or row["Prix_Maison_m2"] == fallback_row.get("Prix_Maison_m2")
    ):
        row["Source"] = "dvf+fallback_csv"

    return row


def _fallback_row(city: str, fallback: pd.DataFrame | None, reason: str) -> dict[str, Any]:
    row = {
        "Ville": city,
        "Code_Commune": None,
        "Prix_Appartement_m2": None,
        "Prix_Maison_m2": None,
        "Loyer_Appartement_m2": None,
        "Loyer_Maison_m2": None,
        "Source": reason,
        "Nb_Appartement_DVF": 0,
        "Nb_Maison_DVF": 0,
    }
    return _merge_missing_values_with_fallback(row, fallback)


def _find_fallback(city: str, fallback: pd.DataFrame | None) -> pd.Series | None:
    if fallback is None:
        return None
    city_key = city.casefold().strip()
    matches = fallback[fallback["Ville"].apply(lambda value: value in city_key or city_key in value)]
    if matches.empty:
        return None
    return matches.iloc[0]


def _is_fresh_cache(path: Path, max_age_days: int) -> bool:
    if not path.exists():
        return False
    modified = date.fromtimestamp(path.stat().st_mtime)
    return (date.today() - modified).days <= max_age_days

