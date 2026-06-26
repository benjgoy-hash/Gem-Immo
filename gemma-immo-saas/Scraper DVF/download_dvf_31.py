#!/usr/bin/env python3
"""
download_dvf_31.py
==================
Télécharge les fichiers CSV DVF officiels pour la Haute-Garonne (31)
depuis data.gouv.fr / etalab et les fusionne en dvf_haute_garonne.csv.

Usage rapide (sans arguments) :
    python download_dvf_31.py



Dépendances : uniquement la stdlib Python 3.8+
              (urllib, gzip, csv — pas de requests nécessaire ici)
"""

import csv
import gzip
import io
import logging
import os
import sys
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

# ----- Configuration --------------------------------------------------------

ANNEES = ["2024", "2025", "2026"]  # Années à télécharger (2024+ pour les données récentes)

# Template URL — source officielle etalab/DVF
# Alternative: https://www.data.gouv.fr/fr/datasets/demandes-de-valeurs-foncieres/
URL_TEMPLATE = "https://files.data.gouv.fr/geo-dvf/latest/csv/{annee}/departements/31.csv.gz"

OUTPUT_FILE = "dvf_haute_garonne.csv"
CACHE_DIR   = Path(".dvf_cache")  # Fichiers .gz mis en cache localement

# Colonnes à conserver + calculées
KEEP_COLS = [
    "id_mutation", "date_mutation", "numero_disposition", "nature_mutation",
    "valeur_fonciere", "adresse_numero", "adresse_suffixe", "adresse_nom_voie",
    "adresse_code_voie", "code_postal", "code_commune", "nom_commune",
    "code_departement", "ancien_code_commune", "ancien_nom_commune",
    "id_parcelle", "ancien_id_parcelle", "numero_volume",
    "lot1_numero", "lot1_surface_carrez", "lot2_numero", "lot2_surface_carrez",
    "lot3_numero", "lot3_surface_carrez", "lot4_numero", "lot4_surface_carrez",
    "lot5_numero", "lot5_surface_carrez", "nombre_lots",
    "code_type_local", "type_local", "surface_reelle_bati",
    "nombre_pieces_principales", "code_nature_culture", "nature_culture",
    "code_nature_culture_speciale", "nature_culture_speciale",
    "surface_terrain", "longitude", "latitude",
    # calculées
    "prix_m2", "annee", "mois",
]


def download_gz(url: str, dest: Path) -> bool:
    """Télécharge un fichier gzip avec barre de progression simple."""
    if dest.exists():
        log.info(f"  → Déjà en cache : {dest.name}")
        return True
    log.info(f"  → Téléchargement : {url}")
    try:
        def progress(count, block_size, total_size):
            if total_size > 0:
                pct = min(count * block_size * 100 // total_size, 100)
                print(f"\r     {pct}%", end="", flush=True)
        urllib.request.urlretrieve(url, dest, reporthook=progress)
        print()
        return True
    except Exception as e:
        log.error(f"  ✗ Erreur téléchargement : {e}")
        log.info(f"    Téléchargez manuellement depuis :")
        log.info(f"    {url}")
        log.info(f"    Et placez le fichier dans : {dest}")
        return False


def parse_gz_csv(gz_path: Path, annee: str):
    """Parse un .csv.gz DVF, retourne un itérateur de dicts normalisés."""
    log.info(f"  → Parsing {gz_path.name}…")
    with gzip.open(gz_path, "rt", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        count = ok = 0
        for row in reader:
            count += 1
            if row.get("nature_mutation") != "Vente":
                continue

            # Valeur foncière
            raw_val = row.get("valeur_fonciere", "").replace(",", ".").replace("\xa0", "")
            try:
                valeur = float(raw_val)
            except ValueError:
                continue
            if valeur <= 0:
                continue

            # Surface bâtie
            raw_surf = row.get("surface_reelle_bati", "").replace(",", ".")
            try:
                surface = float(raw_surf) if raw_surf else None
            except ValueError:
                surface = None

            prix_m2 = round(valeur / surface, 2) if surface and surface > 0 else ""

            date = row.get("date_mutation", "")
            mois = date[5:7] if len(date) >= 7 else ""

            out = {col: row.get(col, "") for col in KEEP_COLS
                   if col not in ("prix_m2", "annee", "mois")}
            out["valeur_fonciere"]    = valeur
            out["surface_reelle_bati"] = surface or ""
            out["prix_m2"]            = prix_m2
            out["annee"]              = annee
            out["mois"]               = mois
            out["code_departement"]   = "31"
            ok += 1
            yield out

    log.info(f"     {ok}/{count} lignes ventes retenues")


def main():
    CACHE_DIR.mkdir(exist_ok=True)

    all_rows = []

    for annee in ANNEES:
        url   = URL_TEMPLATE.format(annee=annee)
        dest  = CACHE_DIR / f"31_{annee}.csv.gz"
        log.info(f"\n[{annee}]")
        if download_gz(url, dest):
            for row in parse_gz_csv(dest, annee):
                all_rows.append(row)

    if not all_rows:
        log.error("Aucune donnée récupérée. Vérifiez la connexion ou téléchargez manuellement.")
        sys.exit(1)

    log.info(f"\nÉcriture de {OUTPUT_FILE}…")
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=KEEP_COLS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)

    log.info(f"✓ {len(all_rows)} ventes exportées → {OUTPUT_FILE}")
    log.info("Prêt pour : python run_analysis.py")


if __name__ == "__main__":
    main()
