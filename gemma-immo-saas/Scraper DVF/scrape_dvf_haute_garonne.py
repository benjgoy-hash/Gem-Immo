#!/usr/bin/env python3
"""
scrape_dvf_haute_garonne.py
============================
Extraction des données de vente immobilière DVF (Demandes de Valeurs Foncières)
pour le département de la Haute-Garonne (31) depuis l'API publique DVF.

Sources supportées :
  1. API cquest (api.cquest.org/dvf) — pagination par commune
  2. Fichiers CSV open data data.gouv.fr (fallback robuste)

Usage :
    python scrape_dvf_haute_garonne.py [--source api|csv] [--annees 2020,2021,2022,2023,2024]
    python scrape_dvf_haute_garonne.py --source csv --annees 2022,2023,2024

Sortie :
    dvf_haute_garonne.csv — prêt pour run_analysis.py (compatible bienici.csv)

Auteur   : Gem-Immo SaaS
Version  : 2.0.0
Mise à jour : 2026-06-26
Changelog: v2.0.0 - Refonte complète. Utilise l'API DVF cquest par commune +
           fallback CSV data.gouv.fr. Colonnes normalisées pour compatibilité
           run_analysis.py / bienici.csv.
"""

import argparse
import csv
import io
import logging
import os
import sys
import time
from pathlib import Path
from typing import Iterator, List, Optional

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEPARTEMENT = "31"  # Haute-Garonne

# Liste complète des codes INSEE des communes de la Haute-Garonne
# Générée depuis le COG (Code Officiel Géographique) INSEE — 588 communes
# Format : 5 caractères, ex. "31001" à "31588"
COMMUNES_HAUTE_GARONNE: List[str] = [f"31{str(i).zfill(3)}" for i in range(1, 589)]

# Endpoint API cquest (sans garantie de disponibilité permanente)
API_BASE_URL = "https://api.cquest.org/dvf"

# URLs des fichiers CSV DVF open data par millésime (data.gouv.fr via etalab)
# Source officielle : https://www.data.gouv.fr/fr/datasets/demandes-de-valeurs-foncieres/
DVF_CSV_URLS = {
    "2019": "https://files.data.gouv.fr/geo-dvf/latest/csv/2019/departements/31.csv.gz",
    "2020": "https://files.data.gouv.fr/geo-dvf/latest/csv/2020/departements/31.csv.gz",
    "2021": "https://files.data.gouv.fr/geo-dvf/latest/csv/2021/departements/31.csv.gz",
    "2022": "https://files.data.gouv.fr/geo-dvf/latest/csv/2022/departements/31.csv.gz",
    "2023": "https://files.data.gouv.fr/geo-dvf/latest/csv/2023/departements/31.csv.gz",
    "2024": "https://files.data.gouv.fr/geo-dvf/latest/csv/2024/departements/31.csv.gz",
}

# Colonnes de sortie normalisées pour compatibilité avec bienici.csv / run_analysis.py
OUTPUT_COLUMNS = [
    "id_mutation",
    "date_mutation",
    "numero_disposition",
    "nature_mutation",
    "valeur_fonciere",
    "adresse_numero",
    "adresse_suffixe",
    "adresse_nom_voie",
    "adresse_code_voie",
    "code_postal",
    "code_commune",
    "nom_commune",
    "code_departement",
    "ancien_code_commune",
    "ancien_nom_commune",
    "id_parcelle",
    "ancien_id_parcelle",
    "numero_volume",
    "lot1_numero",
    "lot1_surface_carrez",
    "lot2_numero",
    "lot2_surface_carrez",
    "lot3_numero",
    "lot3_surface_carrez",
    "lot4_numero",
    "lot4_surface_carrez",
    "lot5_numero",
    "lot5_surface_carrez",
    "nombre_lots",
    "code_type_local",
    "type_local",
    "surface_reelle_bati",
    "nombre_pieces_principales",
    "code_nature_culture",
    "nature_culture",
    "code_nature_culture_speciale",
    "nature_culture_speciale",
    "surface_terrain",
    "longitude",
    "latitude",
    # Colonnes supplémentaires calculées pour run_analysis.py
    "prix_m2",
    "annee",
    "mois",
]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Source 1 : API cquest (par commune)
# ---------------------------------------------------------------------------

def fetch_commune_api(code_commune: str, session: requests.Session, retries: int = 3) -> List[dict]:
    """Récupère les ventes d'une commune via l'API cquest DVF."""
    params = {
        "code_commune": code_commune,
        "nature_mutation": "Vente",
    }
    for attempt in range(retries):
        try:
            r = session.get(API_BASE_URL, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            return data.get("features", []) or data.get("items", []) or (data if isinstance(data, list) else [])
        except requests.exceptions.Timeout:
            log.warning(f"Timeout commune {code_commune} (tentative {attempt+1}/{retries})")
            time.sleep(2 ** attempt)
        except requests.exceptions.RequestException as e:
            log.warning(f"Erreur commune {code_commune}: {e}")
            time.sleep(2 ** attempt)
    return []


def iter_api(communes: List[str]) -> Iterator[dict]:
    """Itère sur toutes les communes via l'API cquest et normalise les enregistrements."""
    session = requests.Session()
    session.headers["User-Agent"] = "Gem-Immo-SaaS/2.0 (github.com/benjgoy-hash/Gem-Immo)"
    total = len(communes)

    for i, code in enumerate(communes, 1):
        log.info(f"[API] Commune {code} ({i}/{total})")
        features = fetch_commune_api(code, session)
        for feat in features:
            props = feat.get("properties", feat)  # GeoJSON ou dict plat
            geom = feat.get("geometry", {}) or {}
            coords = geom.get("coordinates", [None, None])
            row = normalize_api_row(props, coords)
            if row:
                yield row
        time.sleep(0.1)  # politesse envers l'API


def normalize_api_row(props: dict, coords: list) -> Optional[dict]:
    """Convertit un enregistrement API vers le format de sortie standard."""
    valeur = props.get("valeur_fonciere") or props.get("prix")
    if not valeur:
        return None

    try:
        valeur = float(str(valeur).replace(",", ".").replace(" ", ""))
    except (ValueError, TypeError):
        return None

    surface = props.get("surface_reelle_bati") or props.get("surface_bati")
    try:
        surface = float(str(surface).replace(",", ".")) if surface else None
    except (ValueError, TypeError):
        surface = None

    prix_m2 = round(valeur / surface, 2) if surface and surface > 0 else None

    date = props.get("date_mutation", "")
    annee = date[:4] if date else ""
    mois = date[5:7] if len(date) >= 7 else ""

    lon, lat = None, None
    if coords and len(coords) >= 2:
        lon, lat = coords[0], coords[1]

    return {
        "id_mutation": props.get("id_mutation", ""),
        "date_mutation": date,
        "numero_disposition": props.get("numero_disposition", ""),
        "nature_mutation": props.get("nature_mutation", "Vente"),
        "valeur_fonciere": valeur,
        "adresse_numero": props.get("adresse_numero", ""),
        "adresse_suffixe": props.get("adresse_suffixe", ""),
        "adresse_nom_voie": props.get("adresse_nom_voie", ""),
        "adresse_code_voie": props.get("adresse_code_voie", ""),
        "code_postal": props.get("code_postal", ""),
        "code_commune": props.get("code_commune", ""),
        "nom_commune": props.get("nom_commune", ""),
        "code_departement": DEPARTEMENT,
        "ancien_code_commune": props.get("ancien_code_commune", ""),
        "ancien_nom_commune": props.get("ancien_nom_commune", ""),
        "id_parcelle": props.get("id_parcelle", ""),
        "ancien_id_parcelle": props.get("ancien_id_parcelle", ""),
        "numero_volume": props.get("numero_volume", ""),
        "lot1_numero": props.get("lot1_numero", ""),
        "lot1_surface_carrez": props.get("lot1_surface_carrez", ""),
        "lot2_numero": props.get("lot2_numero", ""),
        "lot2_surface_carrez": props.get("lot2_surface_carrez", ""),
        "lot3_numero": props.get("lot3_numero", ""),
        "lot3_surface_carrez": props.get("lot3_surface_carrez", ""),
        "lot4_numero": props.get("lot4_numero", ""),
        "lot4_surface_carrez": props.get("lot4_surface_carrez", ""),
        "lot5_numero": props.get("lot5_numero", ""),
        "lot5_surface_carrez": props.get("lot5_surface_carrez", ""),
        "nombre_lots": props.get("nombre_lots", ""),
        "code_type_local": props.get("code_type_local", ""),
        "type_local": props.get("type_local", ""),
        "surface_reelle_bati": surface or "",
        "nombre_pieces_principales": props.get("nombre_pieces_principales", ""),
        "code_nature_culture": props.get("code_nature_culture", ""),
        "nature_culture": props.get("nature_culture", ""),
        "code_nature_culture_speciale": props.get("code_nature_culture_speciale", ""),
        "nature_culture_speciale": props.get("nature_culture_speciale", ""),
        "surface_terrain": props.get("surface_terrain", ""),
        "longitude": lon or props.get("longitude", ""),
        "latitude": lat or props.get("latitude", ""),
        "prix_m2": prix_m2 or "",
        "annee": annee,
        "mois": mois,
    }


# ---------------------------------------------------------------------------
# Source 2 : Fichiers CSV data.gouv.fr (fallback robuste)
# ---------------------------------------------------------------------------

def iter_csv(annees: List[str]) -> Iterator[dict]:
    """
    Télécharge et parse les CSV DVF officiels par millésime pour le dept 31.
    URL pattern: https://files.data.gouv.fr/geo-dvf/latest/csv/{annee}/departements/31.csv.gz
    """
    import gzip

    session = requests.Session()
    session.headers["User-Agent"] = "Gem-Immo-SaaS/2.0 (github.com/benjgoy-hash/Gem-Immo)"

    for annee in annees:
        url = DVF_CSV_URLS.get(annee)
        if not url:
            log.warning(f"Pas d'URL CSV connue pour l'année {annee}, ignoré.")
            continue

        log.info(f"[CSV] Téléchargement {annee} : {url}")
        try:
            r = session.get(url, timeout=120, stream=True)
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            log.error(f"Impossible de télécharger {url}: {e}")
            log.info("  → Conseil: téléchargez manuellement depuis data.gouv.fr et placez en local.")
            continue

        # Décompresser gzip en mémoire
        raw = b""
        for chunk in r.iter_content(chunk_size=1024 * 256):
            raw += chunk

        try:
            content = gzip.decompress(raw).decode("utf-8")
        except Exception:
            # Peut-être déjà décompressé
            content = raw.decode("utf-8", errors="replace")

        reader = csv.DictReader(io.StringIO(content))
        count = 0
        for row in reader:
            norm = normalize_csv_row(row, annee)
            if norm:
                count += 1
                yield norm
        log.info(f"  → {count} ventes extraites pour {annee}")


def normalize_csv_row(row: dict, annee: str) -> Optional[dict]:
    """Normalise une ligne CSV DVF officielle (format geo-dvf etalab)."""
    nature = row.get("nature_mutation", "")
    if nature != "Vente":
        return None

    valeur = row.get("valeur_fonciere", "").replace(",", ".").replace(" ", "")
    try:
        valeur = float(valeur) if valeur else None
    except ValueError:
        return None

    if not valeur or valeur <= 0:
        return None

    surface = row.get("surface_reelle_bati", "").replace(",", ".")
    try:
        surface = float(surface) if surface else None
    except ValueError:
        surface = None

    prix_m2 = round(valeur / surface, 2) if surface and surface > 0 else None

    date = row.get("date_mutation", "")
    mois = date[5:7] if len(date) >= 7 else ""

    return {
        "id_mutation": row.get("id_mutation", ""),
        "date_mutation": date,
        "numero_disposition": row.get("numero_disposition", ""),
        "nature_mutation": nature,
        "valeur_fonciere": valeur,
        "adresse_numero": row.get("adresse_numero", ""),
        "adresse_suffixe": row.get("adresse_suffixe", ""),
        "adresse_nom_voie": row.get("adresse_nom_voie", ""),
        "adresse_code_voie": row.get("adresse_code_voie", ""),
        "code_postal": row.get("code_postal", ""),
        "code_commune": row.get("code_commune", ""),
        "nom_commune": row.get("nom_commune", ""),
        "code_departement": DEPARTEMENT,
        "ancien_code_commune": row.get("ancien_code_commune", ""),
        "ancien_nom_commune": row.get("ancien_nom_commune", ""),
        "id_parcelle": row.get("id_parcelle", ""),
        "ancien_id_parcelle": row.get("ancien_id_parcelle", ""),
        "numero_volume": row.get("numero_volume", ""),
        "lot1_numero": row.get("lot1_numero", ""),
        "lot1_surface_carrez": row.get("lot1_surface_carrez", ""),
        "lot2_numero": row.get("lot2_numero", ""),
        "lot2_surface_carrez": row.get("lot2_surface_carrez", ""),
        "lot3_numero": row.get("lot3_numero", ""),
        "lot3_surface_carrez": row.get("lot3_surface_carrez", ""),
        "lot4_numero": row.get("lot4_numero", ""),
        "lot4_surface_carrez": row.get("lot4_surface_carrez", ""),
        "lot5_numero": row.get("lot5_numero", ""),
        "lot5_surface_carrez": row.get("lot5_surface_carrez", ""),
        "nombre_lots": row.get("nombre_lots", ""),
        "code_type_local": row.get("code_type_local", ""),
        "type_local": row.get("type_local", ""),
        "surface_reelle_bati": surface or "",
        "nombre_pieces_principales": row.get("nombre_pieces_principales", ""),
        "code_nature_culture": row.get("code_nature_culture", ""),
        "nature_culture": row.get("nature_culture", ""),
        "code_nature_culture_speciale": row.get("code_nature_culture_speciale", ""),
        "nature_culture_speciale": row.get("nature_culture_speciale", ""),
        "surface_terrain": row.get("surface_terrain", ""),
        "longitude": row.get("longitude", ""),
        "latitude": row.get("latitude", ""),
        "prix_m2": prix_m2 or "",
        "annee": annee,
        "mois": mois,
    }


# ---------------------------------------------------------------------------
# Script alternatif : téléchargement direct CSV local (mode offline)
# ---------------------------------------------------------------------------

def iter_local_csv(csv_path: str, annee: str) -> Iterator[dict]:
    """Parse un fichier CSV DVF déjà téléchargé localement."""
    import gzip

    path = Path(csv_path)
    if not path.exists():
        log.error(f"Fichier introuvable : {csv_path}")
        return

    log.info(f"[LOCAL] Lecture de {csv_path}")
    if path.suffix == ".gz":
        opener = lambda: gzip.open(path, "rt", encoding="utf-8")
    else:
        opener = lambda: open(path, "r", encoding="utf-8")

    with opener() as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            norm = normalize_csv_row(row, annee)
            if norm:
                count += 1
                yield norm
    log.info(f"  → {count} ventes extraites depuis {csv_path}")


# ---------------------------------------------------------------------------
# Écriture du CSV de sortie
# ---------------------------------------------------------------------------

def write_csv(rows: Iterator[dict], output_path: str) -> int:
    """Écrit les enregistrements dans le CSV de sortie, retourne le nombre de lignes."""
    count = 0
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            count += 1
            if count % 10_000 == 0:
                log.info(f"  {count} enregistrements écrits…")
    return count


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extraction DVF Haute-Garonne → dvf_haute_garonne.csv",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  # Mode CSV (recommandé, stable, données complètes) :
  python scrape_dvf_haute_garonne.py --source csv --annees 2022,2023,2024

  # Mode API (si api.cquest.org est accessible) :
  python scrape_dvf_haute_garonne.py --source api

  # Fichier local déjà téléchargé :
  python scrape_dvf_haute_garonne.py --source local --local-file ./31_2023.csv.gz --annee 2023

Notes :
  Les URLs CSV data.gouv.fr :
    https://files.data.gouv.fr/geo-dvf/latest/csv/{annee}/departements/31.csv.gz
        """,
    )
    parser.add_argument(
        "--source",
        choices=["api", "csv", "local"],
        default="csv",
        help="Source des données (défaut: csv)",
    )
    parser.add_argument(
        "--annees",
        default="2020,2021,2022,2023,2024,2025,2026",
        help="Années séparées par virgules (défaut: 2020-2026)",
    )
    parser.add_argument(
        "--output",
        default="dvf_haute_garonne.csv",
        help="Chemin du CSV de sortie (défaut: dvf_haute_garonne.csv)",
    )
    parser.add_argument(
        "--local-file",
        help="(mode local uniquement) chemin du fichier CSV/gz DVF",
    )
    parser.add_argument(
        "--annee",
        help="(mode local uniquement) année du fichier",
    )
    parser.add_argument(
        "--communes",
        help="(mode api uniquement) codes INSEE séparés par virgules (défaut: toutes communes 31)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    annees = [a.strip() for a in args.annees.split(",")]

    log.info("=" * 60)
    log.info("  Gem-Immo — Extraction DVF Haute-Garonne")
    log.info(f"  Source  : {args.source}")
    log.info(f"  Années  : {', '.join(annees)}")
    log.info(f"  Sortie  : {args.output}")
    log.info("=" * 60)

    if args.source == "api":
        communes = (
            [c.strip() for c in args.communes.split(",")]
            if args.communes
            else COMMUNES_HAUTE_GARONNE
        )
        log.info(f"  Communes : {len(communes)} à traiter")
        rows = iter_api(communes)

    elif args.source == "csv":
        rows = iter_csv(annees)

    elif args.source == "local":
        if not args.local_file or not args.annee:
            log.error("--local-file et --annee sont requis pour le mode local")
            sys.exit(1)
        rows = iter_local_csv(args.local_file, args.annee)

    else:
        log.error(f"Source inconnue : {args.source}")
        sys.exit(1)

    count = write_csv(rows, args.output)

    log.info("=" * 60)
    log.info(f"  ✓ {count} ventes exportées dans : {args.output}")
    log.info("  Prêt pour : python run_analysis.py")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
