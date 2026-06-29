"""
scrape_all.py
-------------
Scrape l'intégralité des annonces BienIci en découpant automatiquement
par tranches de prix (chaque tranche < 2496 résultats, limite de l'API).

Usage :
    python scrape_all.py --url "https://www.bienici.com/recherche/achat/haute-garonne-31" --output resultats_31.csv

Options :
    --url       URL de recherche BienIci (obligatoire)
    --output    Fichier CSV final (défaut : output_all.csv)
    --max       Nombre max de biens par tranche (défaut : 2400, sécurité sous 2496)
"""

import argparse
import copy
import csv
import json
import os
import time

import requests

# ── Tranches de prix à tester (en €) ──────────────────────────────────────────
# Suffisamment fines pour que chaque tranche reste sous 2496 résultats.
# Ajuste-les si une tranche dépasse encore la limite.
PRICE_SLICES = [
    (0,       100_000),
    (100_000, 150_000),
    (150_000, 200_000),
    (200_000, 250_000),
    (250_000, 300_000),
    (300_000, 350_000),
    (350_000, 400_000),
    (400_000, 500_000),
    (500_000, 700_000),
    (700_000, 1_000_000),
    (1_000_000, 2_000_000),
    (2_000_000, 99_000_000),  # luxe
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

SLEEP_BETWEEN_PAGES  = 5   # secondes entre chaque page
SLEEP_ON_RATE_LIMIT  = 30  # secondes si 429
SLEEP_ON_FORBIDDEN   = 60  # secondes si 403
MAX_API_PAGE         = 104 # limite dure de l'API BienIci


# ── Helpers ───────────────────────────────────────────────────────────────────

def build_base_filters(url: str) -> dict:
    """Convertit une URL BienIci en paramètres API (version simplifiée)."""
    from urllib.parse import urlparse, parse_qs
    import re

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
    qp     = parse_qs(parsed.query)

    filters = {
        "size": 24, "from": None, "page": None,
        "onTheMarket": [True],
    }

    # Type de transaction
    for k, v in FILTER_TYPE_OPTIONS.items():
        if k in path:
            filters["filterType"] = v

    # Types de biens
    prop_types = [v for k, v in FRENCH_SLUG_TO_DB.items() if k in path]
    filters["propertyType"] = prop_types if prop_types else DEFAULT_PROPERTY_TYPES

    # Localisation (zones)
    path_parts  = [p for p in path.split("/") if p]
    if len(path_parts) >= 3:
        location_slug = path_parts[2]
        if location_slug != "france":
            try:
                resp = requests.get(
                    f"https://res.bienici.com/suggest.json?q={location_slug}",
                    headers=HEADERS, timeout=10
                )
                if resp.status_code == 200 and resp.json():
                    zone_ids = resp.json()[0].get("zoneIds", [])
                    if zone_ids:
                        filters["zoneIdsByTypes"] = {"zoneIds": zone_ids}
                        print(f"  → zone ids trouvés : {zone_ids[:3]}...")
            except Exception as e:
                print(f"  ⚠ Impossible de résoudre la zone '{location_slug}' : {e}")

    # Tri par défaut
    filters.setdefault("sortBy", "relevance")
    filters.setdefault("sortOrder", "desc")

    return filters


def count_results(session: requests.Session, filters: dict) -> int:
    """Retourne le nombre total de résultats pour ces filtres."""
    f = copy.deepcopy(filters)
    f["page"] = 1
    f["from"] = 0
    params = {"filters": json.dumps(f)}
    try:
        r = session.get(
            "https://www.bienici.com/realEstateAds.json",
            params=params, headers=HEADERS, timeout=15
        )
        if r.status_code == 200:
            return r.json().get("total", 0)
    except Exception:
        pass
    return 0


def parse_ad(ad: dict) -> dict:
    """Extrait les champs utiles d'une annonce et construit l'URL."""
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

    ad_id         = ad.get("id", "")
    ad_type_fr    = ad.get("adTypeFR", "")
    city_norm     = unicodedata.normalize("NFD", city).encode("ascii", "ignore").decode("ascii")
    city_slug     = city_norm.lower().replace(" ", "-").replace("'", "-")
    prop_slug     = DB_TO_FR.get(property_type, property_type)
    rooms_slug    = f"{rooms}pieces" if rooms else ""
    url           = f"https://www.bienici.com/annonce/{ad_type_fr}/{city_slug}/{prop_slug}/{rooms_slug}/{ad_id}"

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
    """Scrape une tranche et retourne la liste des annonces."""
    results = []
    page    = 1

    while True:
        if page > MAX_API_PAGE:
            print(f"  ⚠ [{label}] Limite API atteinte ({MAX_API_PAGE} pages), arrêt.")
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
                    params=params, headers=HEADERS, timeout=20
                )
                status = r.status_code
                print(f"HTTP {status}", end=" ")

                if status == 429:
                    print(f"→ attente {SLEEP_ON_RATE_LIMIT}s…", end=" ")
                    time.sleep(SLEEP_ON_RATE_LIMIT)
                    continue
                if status == 403:
                    print(f"→ attente {SLEEP_ON_FORBIDDEN}s…", end=" ")
                    time.sleep(SLEEP_ON_FORBIDDEN)
                    continue
                if status == 400:
                    print("→ fin de pagination.")
                    return results
                if status != 200:
                    print(f"→ erreur inattendue, on arrête.")
                    return results
                break
            except requests.RequestException as e:
                print(f"→ erreur réseau ({e}), retry…")
                time.sleep(10)
        else:
            print("→ 3 tentatives échouées, on passe.")
            break

        data      = r.json()
        total     = data.get("total", 0)
        ads       = data.get("realEstateAds", [])
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


def write_csv(rows: list[dict], path: str):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  → {len(rows)} lignes écrites dans {path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Scrape BienIci — toutes les annonces via découpage par prix")
    parser.add_argument("--url",    required=True, help="URL de recherche BienIci")
    parser.add_argument("--output", default="output_all.csv", help="Fichier CSV final")
    parser.add_argument("--max",    type=int, default=2400,   help="Max annonces par tranche")
    args = parser.parse_args()

    session = requests.Session()
    session.headers.update(HEADERS)

    print("=== BienIci — scraping complet par tranches de prix ===\n")
    print(f"URL source : {args.url}")

    # Résolution des filtres de base (zone, type de bien, etc.)
    print("\n[1/3] Résolution des paramètres…")
    base_filters = build_base_filters(args.url)

    # Comptage par tranche pour information
    print("\n[2/3] Comptage des résultats par tranche…")
    slices_to_scrape = []
    for (pmin, pmax) in PRICE_SLICES:
        f = copy.deepcopy(base_filters)
        f["minPrice"] = pmin
        f["maxPrice"] = pmax
        n = count_results(session, f)
        label = f"{pmin//1000}k–{pmax//1000}k€"
        flag  = " ⚠ TROP GRAND" if n > 2496 else ""
        print(f"  {label:20s} → {n:5d} résultats{flag}")
        if n > 0:
            slices_to_scrape.append((pmin, pmax, label, n))
        time.sleep(2)

    total_expected = sum(n for _, _, _, n in slices_to_scrape)
    print(f"\nTotal estimé : {total_expected} annonces en {len(slices_to_scrape)} tranches")

    # Scraping tranche par tranche
    print("\n[3/3] Scraping…\n")
    all_rows   = []
    seen_ids   = set()
    tmp_dir    = "tmp_slices"
    os.makedirs(tmp_dir, exist_ok=True)

    for i, (pmin, pmax, label, _) in enumerate(slices_to_scrape, 1):
        print(f"── Tranche {i}/{len(slices_to_scrape)} : {label} ──")
        f = copy.deepcopy(base_filters)
        f["minPrice"] = pmin
        f["maxPrice"] = pmax

        rows = scrape_slice(session, f, label, max_results=args.max)

        # Déduplication par URL
        before = len(rows)
        rows   = [r for r in rows if r["url"] not in seen_ids]
        seen_ids.update(r["url"] for r in rows)
        if before != len(rows):
            print(f"  → {before - len(rows)} doublons supprimés")

        all_rows.extend(rows)

        # Sauvegarde intermédiaire
        tmp_path = os.path.join(tmp_dir, f"slice_{i:02d}_{pmin}_{pmax}.csv")
        write_csv(rows, tmp_path)
        print(f"  Cumulé : {len(all_rows)} annonces\n")

    # Fichier final
    print(f"=== Fusion finale → {args.output} ===")
    write_csv(all_rows, args.output)
    print(f"\n✓ Terminé. {len(all_rows)} annonces uniques exportées.")


if __name__ == "__main__":
    main()
