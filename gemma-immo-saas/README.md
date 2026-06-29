# Gemma Immo SaaS

Pipeline d'analyse immobilière qui compare les annonces Bien'ici avec les prix de marché réels issus des données DVF (Demandes de Valeurs Foncières, DGFiP).

---

## Architecture

```
gemma-immo-saas/
├── apps/
│   ├── api/                          API FastAPI + moteur d'analyse
│   │   ├── app/
│   │   │   ├── data/
│   │   │   │   ├── bienici.csv           Export Bien'ici (à fournir)
│   │   │   │   ├── prix_immo.csv         Prix de référence statiques
│   │   │   │   ├── dvf_haute_garonne.csv Prix DVF générés (gitignored)
│   │   │   │   └── resultats.csv         Opportunités calculées (gitignored)
│   │   │   ├── routers/
│   │   │   ├── services/
│   │   │   │   ├── dvf_market.py         Calcul des prix depuis DVF via API cquest
│   │   │   │   └── scoring.py            Calcul décotes et rendements
│   │   │   └── main.py
│   │   └── scripts/
│   │       └── run_analysis.py           Script principal d'analyse
│   └── web/                          Frontend Next.js
├── scrape_dvf_haute_garonne.py       Génère dvf_haute_garonne.csv (ce repo)
└── docs/
    └── ROADMAP_SAAS.md
```

---

## Installation

```bash
cd apps/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # Windows
# source .venv/bin/activate    # Linux/macOS
pip install -e .
```

---

## Lancer l'API

```bash
uvicorn app.main:app --reload --port 8000
```

Endpoints :

- `GET /health`
- `GET /opportunities`
- `GET /opportunities?max_price=200000&property_type=Appartement&min_discount_percent=15`

---

## Générer les données DVF

`scrape_dvf_haute_garonne.py` interroge les données DVF pour la Haute-Garonne et produit un fichier de prix médians par ville, au même format que `prix_immo.csv`. Ce fichier peut ensuite être passé directement à `run_analysis.py` via `--prices`.

### Source des données DVF

| Source | URL |
|--------|-----|
| API cquest | `https://api.cquest.org/dvf` (doc : [github.com/cquest/dvf_as_api](https://github.com/cquest/dvf_as_api)) |
| CSV officiels | `https://files.data.gouv.fr/geo-dvf/latest/csv/{annee}/departements/31.csv.gz` |

Le mode `csv` est recommandé : il ne dépend pas de la disponibilité de l'API tierce et couvre l'ensemble des communes du département.

### Mode CSV (recommandé)

Télécharge les fichiers DVF officiels depuis data.gouv.fr et calcule les médianes de prix par ville et type de bien.

```bash
python scrape_dvf_haute_garonne.py --mode csv --annees 2022,2023,2024
```

Les fichiers `.gz` sont mis en cache dans `.dvf_cache/` pour éviter de les retélécharger.

Écriture directement dans le répertoire data de l'API :

```bash
python scrape_dvf_haute_garonne.py --mode csv --output apps/api/app/data/dvf_haute_garonne.csv
```

### Mode API

Interroge `api.cquest.org/dvf` pour chaque ville connue de Haute-Garonne. Utile pour un rafraîchissement ciblé sur quelques communes.

```bash
python scrape_dvf_haute_garonne.py --mode api
```

### Téléchargement manuel

Si le téléchargement automatique échoue (réseau restreint, proxy) :

```
https://files.data.gouv.fr/geo-dvf/latest/csv/2024/departements/31.csv.gz
https://files.data.gouv.fr/geo-dvf/latest/csv/2023/departements/31.csv.gz
https://files.data.gouv.fr/geo-dvf/latest/csv/2022/departements/31.csv.gz
```

Placer les fichiers dans `.dvf_cache/` sous la forme `31_{annee}.csv.gz`, puis relancer le script.

### Format de sortie `dvf_haute_garonne.csv`

Identique à `prix_immo.csv` — directement utilisable via `--prices` :

```
Ville,Prix_Appartement_m2,Prix_Maison_m2,Loyer_Appartement_m2,Loyer_Maison_m2
Toulouse,3462,4091,,
Muret,2708,2857,,
Blagnac,3104,3945,,
```

Les colonnes `Loyer_*` restent vides (données non disponibles dans DVF) — `run_analysis.py` se rabat sur `prix_immo.csv` pour les loyers si nécessaire.

---

## Lancer l'analyse

```bash
cd apps/api

# Avec les prix DVF générés :
python scripts/run_analysis.py \
    --ads app/data/bienici.csv \
    --prices app/data/dvf_haute_garonne.csv \
    --output app/data/resultats.csv

# Avec les prix statiques (fallback) :
python scripts/run_analysis.py \
    --ads app/data/bienici.csv \
    --prices app/data/prix_immo.csv \
    --output app/data/resultats.csv

# Mode hybride — DVF avec fallback CSV si l'API cquest est inaccessible :
python scripts/run_analysis.py \
    --ads app/data/bienici.csv \
    --market-source auto \
    --dvf-cache app/data/market_prices_dvf.csv \
    --output app/data/resultats.csv
```

`resultats.csv` est ensuite lu automatiquement par l'API. Si le fichier est absent, l'API utilise `resultats.sample.csv`.

---

## Format du CSV Bien'ici

`bienici.csv` est un export direct depuis Bien'ici. Les colonnes exploitées par `scoring.py` :

| Colonne | Valeurs attendues |
|---------|-------------------|
| `city` | Nom de la ville |
| `postal_code` | Code postal |
| `property_type` | `flat` ou `house` |
| `price` | Prix en euros |
| `surfaceArea` | Surface en m² |
| `url` | URL de l'annonce |

---

## Lancer le frontend

```bash
cd apps/web
npm install
npm run dev
```

Accessible sur `http://localhost:3000`.

---

## Changelog

Voir [`update.md`](./update.md) pour l'historique des suppressions et changements cassants.

### v2.0.0 — 2026-06-29

- Refonte complète de `scrape_dvf_haute_garonne.py` :
  - Mode `csv` : téléchargement des fichiers DVF officiels data.gouv.fr (dept 31), calcul des médianes, mise en cache locale
  - Mode `api` : interrogation de `api.cquest.org/dvf` commune par commune avec résolution INSEE via `geo.api.gouv.fr`
  - Sortie au format `prix_immo.csv` — compatible directement avec `--prices` de `run_analysis.py`
  - Aucune dépendance tierce requise (stdlib uniquement)
- Suppression des scripts de scraping précédents (voir `update.md`)
- Nettoyage du README
