"""
scrape_all.py
-------------
Scrape l'intégralité des annonces Bien'ici en découpant automatiquement
par tranches de prix (chaque tranche < 2 496 résultats, limite de l'API).

Utile pour les recherches larges (département entier) qui dépassent la limite
de pagination de l'API Bien'ici (~2 500 résultats par requête).

Usage :
    python scrape_all.py --url "https://www.bienici.com/recherche/achat/haute-garonne-31"
    python scrape_all.py --url "https://www.bienici.com/recherche/achat/haute-garonne-31" --output mon_export.csv

Options :
    --url       URL de recherche Bien'ici (obligatoire)
    --output    Fichier CSV final (défaut : apps/api/app/data/bienici.csv)
    --max       Nombre max de biens par tranche de prix (défaut : 2 400)
"""

import argparse
import copy
import csv
import json
import os
import time
from pathlib import Path

import requests

# Chemin par défaut : répertoire data de l'API, compatible avec run_analysis.py
DEFAULT_OUTPUT = str(
    Path(__file__).resolve().parent.parent
    / "apps" / "api" / "app" / "data" / "bienici.csv"
)

# Tranches de prix (€) — suffisamment fines pour rester sous 2 496 résultats chacune
PRICE_SLICES = [
    (0,         100_000),
    (100_000,   150_000),
    (150_000,   200_000),
    (200_000,   250_000),
    (250_000,   300_000),
    (300_000,   350_000),
    (350_000,   400_000),
    (400_000,   500_000),
    (500_000,   700_000),
    (700_000,   1_000_000),
    (1_000_000, 2_000_000),
    (2_000_000, 99_000_000),
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Referer": "https://www.bienici.com/",
}

FIELDNAMES = [
    "city", "postal_code", "ad_type", "property_type",
    "reference", "title", "publication_date", "modification_date",
    "new_property", "rooms_quantity", "bedrooms_quantity",
    "price", "surfaceArea", "url",
]

SLEEP_BETWEEN_PAGES = 5
SLEEP_ON_RATE_LIMIT = 30
SLEEP_ON_FORBIDDEN  = 60
MAX_API_PAGE        = 104


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_base_filters(url: str) -> dict:
    """Convertit une URL Bien'ici en paramètres API."""
    from urllib.parse import urlparse, parse_qs

    FILTER_TYPE_OPTIONS = {"achat": "buy", "location": "rent"}
    FRENCH_SLUG_TO_DB = {
        "parkingbox": "parking", "maison": "house", "maisonvilla": "house",
        "appartement": "flat", "parking": "parking", "terrain": "terrain",
        "batiment": "building", "chateau": "castle", "loft": "loft",
        "bureau": "office", "local": "premises", "commerce": "shop",
        "hotel": "townhouse", "annexe": "annexe", "autres": "others",
    }
    DEFAULT_PROPERTY_TYPES = ["house", "flat", "loft", "castle", "townhouse"]

    parsed = urlparse(url)
    path   = parsed.path

    filters = {
        "size": 24,
        "from": None,
        "page": None,
        "onTheMarket": [True],
    }

    for k, v in FILTER_TYPE_OPTIONS.items():
        if k in path:
            filters["filterType"] = v

    prop_types = [v for k, v in FRENCH_SLUG_TO_DB.items() if k in path]
    filters["propertyType"] = prop_types if prop_types else DEFAULT_PROPERTY_TYPES

    path_parts = [p for p in path.split("/") if p]
    if len(path_parts) >= 3:
        location_slug = path_parts[2]
        if location_slug != "france":
            try:
                resp = requests.get(
                    f"https://res.bienici.com/suggest.json?q={location_slug}",
                    headers=HEADERS, timeout=10,
                )
                if resp.status_code == 200 and resp.json():
                    zone_ids = resp.json()[0].get("zoneIds", [])
                    if zone_ids:
                        filters["zoneIdsByTypes"] = {"zoneIds": zone_ids}
                        print(f"  → zone ids : {zone_ids[:3]}{'...' if len(zone_ids) > 3 else ''}")
            except Exception as e:
                print(f"  ⚠ Résolution zone '{location_slug}' échouée : {e}")

    filters.setdefault("sortBy", "relevance")
    filters.setdefault("sortOrder", "desc")

    return filters


def count_results(session: requests.Session, filters: dict) -> int:
    f = copy.deepcopy(filters)
    f["page"] = 1
    f["from"] = 0
    try:
        r = session.get(
            "https://www.bienici.com/realEstateAds.json",
            params={"filters": json.dumps(f)},
            headers=HEADERS,
            timeout=15,
        )
        if r.status_code == 200:
            return r.json().get("total", 0)
    except Exception:
        pass
    return 0


def parse_ad(ad: dict) -> dict:
    import unicodedata

    DB_TO_FR = {
        "house": "maison", "flat": "appartement", "parking": "parking",
        "terrain": "terrain", "building": "batiment", "castle": "chateau",
        "loft": "loft", "office": "bureau", "premises": "local",
        "shop": "commerce", "townhouse": "hotel", "annexe": "annexe",
        "others": "autres", "programme": "programme",
    }

    city          = ad.get("city", "")
    postal_code   = ad.get("postalCode", "")
    ad_type       = ad.get("adType", "")
    property_type = ad.get("propertyType", "")
    reference     = ad.get("reference", "")
    title         = ad.get("title", "")
    pub_date      = ad.get("publicationDate", "")
    mod_date      = ad.get("modificationDate", "")
    new_prop      = ad.get("newProperty", "")
    rooms         = ad.get("roomsQuantity", "")
    bedrooms      = ad.get("bedroomsQuantity", "")
    price         = ad.get("price", "")
    surface       = ad.get("surfaceArea", "")

    ad_id      = ad.get("id", "")
    ad_type_fr = ad.get("adTypeFR") or {"buy": "vente", "rent": "location"}.get(ad_type, ad_type)
    city_norm  = unicodedata.normalize("NFD", city).encode("ascii", "ignore").decode("ascii")
    city_slug  = city_norm.lower().replace(" ", "-").replace("'", "-")
    prop_slug  = DB_TO_FR.get(property_type, property_type)
    rooms_slug = f"{rooms}pieces" if rooms else ""
    url        = f"https://www.bienici.com/annonce/{ad_type_fr}/{city_slug}/{prop_slug}/{rooms_slug}/{ad_id}"

    return dict(zip(FIELDNAMES, [
        city, postal_code, ad_type, property_type, reference, title,
        pub_date, mod_date, new_prop, rooms, bedrooms, price, surface, url,
    ]))


def scrape_slice(
    session: requests.Session,
    filters: dict,
    label: str,
    max_results: int = 2400,
) -> list[dict]:
    results = []
    page    = 1

    while True:
        if page > MAX_API_PAGE:
            print(f"  ⚠ [{label}] Limite API atteinte ({MAX_API_PAGE} pages).")
            break

        f = copy.deepcopy(filters)
        f["page"] = page
        f["from"] = (page - 1) * 24
        params = {"filters": json.dumps(f)}

        print(f"  [{label}] page {page}…", end=" ", flush=True)
        time.sleep(SLEEP_BETWEEN_PAGES)

        for attempt in range(3):
            try:
                r = session.get(
                    "https://www.bienici.com/realEstateAds.json",
                    params=params, headers=HEADERS, timeout=20,
                )
                status = r.status_code
                print(f"HTTP {status}", end=" ")

                if status == 429:
                    print(f"→ pause {SLEEP_ON_RATE_LIMIT}s…", end=" ")
                    time.sleep(SLEEP_ON_RATE_LIMIT)
                    continue
                if status == 403:
                    print(f"→ pause {SLEEP_ON_FORBIDDEN}s…", end=" ")
                    time.sleep(SLEEP_ON_FORBIDDEN)
                    continue
                if status == 400:
                    print("→ fin de pagination.")
                    return results
                if status != 200:
                    print("→ erreur inattendue.")
                    return results
                break
            except requests.RequestException as e:
                print(f"→ erreur réseau ({e}), retry…")
                time.sleep(10)
        else:
            print("→ 3 tentatives échouées.")
            break

        data  = r.json()
        total = data.get("total", 0)
        ads   = data.get("realEstateAds", [])
        print(f"({len(ads)} annonces, total={total})")

        for ad in ads:
            results.append(parse_ad(ad))
            if len(results) >= max_results:
                print(f"  [{label}] Limite de {max_results} atteinte.")
                return results

        if not ads or len(results) >= total:
            break

        page += 1

    return results


def write_csv(rows: list[dict], path: str) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  → {len(rows)} lignes écrites dans {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Scrape Bien'ici — toutes les annonces via découpage par tranches de prix",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Exemples :
  python scrape_all.py --url "https://www.bienici.com/recherche/achat/haute-garonne-31"
  python scrape_all.py --url "https://www.bienici.com/recherche/achat/toulouse-31000" --output data/toulouse.csv

Sortie par défaut (compatible run_analysis.py) :
  {DEFAULT_OUTPUT}
""",
    )
    parser.add_argument("--url",    required=True,               help="URL de recherche Bien'ici")
    parser.add_argument("--output", default=DEFAULT_OUTPUT,      help=f"Fichier CSV final (défaut : {DEFAULT_OUTPUT})")
    parser.add_argument("--max",    type=int, default=2400,      help="Max annonces par tranche de prix (défaut : 2 400)")
    args = parser.parse_args()

    session = requests.Session()
    session.headers.update(HEADERS)

    print("=" * 60)
    print("  Bien'ici — scraping complet par tranches de prix")
    print("=" * 60)
    print(f"URL    : {args.url}")
    print(f"Sortie : {args.output}")
    print()

    print("[1/3] Résolution des paramètres de recherche…")
    base_filters = build_base_filters(args.url)

    print("\n[2/3] Comptage des résultats par tranche de prix…")
    slices_to_scrape = []
    for (pmin, pmax) in PRICE_SLICES:
        f = copy.deepcopy(base_filters)
        f["minPrice"] = pmin
        f["maxPrice"] = pmax
        n = count_results(session, f)
        label = f"{pmin//1000}k–{pmax//1000}k€"
        flag  = "  ⚠ dépasse 2 496" if n > 2496 else ""
        print(f"  {label:22s} → {n:5d} résultats{flag}")
        if n > 0:
            slices_to_scrape.append((pmin, pmax, label, n))
        time.sleep(2)

    total_expected = sum(n for _, _, _, n in slices_to_scrape)
    print(f"\nTotal estimé : {total_expected} annonces en {len(slices_to_scrape)} tranches")

    print("\n[3/3] Scraping…\n")
    all_rows = []
    seen_urls = set()
    tmp_dir   = Path("tmp_slices")
    tmp_dir.mkdir(exist_ok=True)

    for i, (pmin, pmax, label, _) in enumerate(slices_to_scrape, 1):
        print(f"── Tranche {i}/{len(slices_to_scrape)} : {label} ──")
        f = copy.deepcopy(base_filters)
        f["minPrice"] = pmin
        f["maxPrice"] = pmax

        rows   = scrape_slice(session, f, label, max_results=args.max)
        before = len(rows)
        rows   = [r for r in rows if r["url"] not in seen_urls]
        seen_urls.update(r["url"] for r in rows)
        if before != len(rows):
            print(f"  → {before - len(rows)} doublons supprimés")

        all_rows.extend(rows)

        tmp_path = tmp_dir / f"slice_{i:02d}_{pmin}_{pmax}.csv"
        write_csv(rows, str(tmp_path))
        print(f"  Cumulé : {len(all_rows)} annonces\n")

    print(f"{'=' * 60}")
    print(f"  Fusion finale → {args.output}")
    print(f"{'=' * 60}")
    write_csv(all_rows, args.output)
    print(f"\n✓ {len(all_rows)} annonces uniques exportées.")


if __name__ == "__main__":
    main()
