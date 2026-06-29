# Gemma Immo SaaS

Pipeline d'analyse immobilière qui compare les annonces Bien'ici avec les prix de marché réels issus des données DVF (Demandes de Valeurs Foncières, DGFiP).

---

## Architecture

```
gemma-immo-saas/
├── bieniciscraper-main/              Scraper Bien'ici → bienici.csv
│   ├── bieniciscraper/
│   │   ├── scraper.py                Logique de scraping (BienIciScraper)
│   │   └── constants.py              Constantes, mappings, FIELDNAMES
│   ├── main.py                       Point d'entrée simple (limite + URL)
│   ├── scrape_all.py                 Scraping complet par tranches de prix
│   └── requirements.txt
├── apps/
│   ├── api/                          API FastAPI + moteur d'analyse
│   │   ├── app/
│   │   │   ├── data/
│   │   │   │   ├── bienici.csv           Export Bien'ici (généré par le scraper)
│   │   │   │   ├── prix_immo.csv         Prix de référence statiques
│   │   │   │   ├── dvf_haute_garonne.csv Prix DVF générés (gitignored)
│   │   │   │   └── resultats.csv         Opportunités calculées (gitignored)
│   │   │   ├── routers/
│   │   │   └── services/
│   │   │       ├── dvf_market.py         Calcul des prix de marché via DVF
│   │   │       └── scoring.py            Calcul décotes et rendements
│   │   └── scripts/
│   │       └── run_analysis.py           Script principal d'analyse
│   └── web/                          Frontend Next.js
├── scrape_dvf_haute_garonne.py       Génère dvf_haute_garonne.csv
└── docs/
    └── ROADMAP_SAAS.md
```

---

## Pipeline complet

```
Bien'ici (scraper) → bienici.csv → run_analysis.py → resultats.csv → API → UI
                                          ↑
                          prix_immo.csv ou dvf_haute_garonne.csv
```

---

## Installation

```bash
cd apps/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # Windows
# source .venv/bin/activate    # Linux / macOS
pip install -e .
```

Pour le scraper Bien'ici :

```bash
cd bieniciscraper-main
pip install -r requirements.txt
```

---

## Étape 1 — Scraper les annonces Bien'ici

Le scraper interroge l'API interne de Bien'ici à partir d'une URL de recherche et exporte les annonces en CSV. Par défaut, il écrit directement dans `apps/api/app/data/bienici.csv`, qui est le fichier attendu par `run_analysis.py`.

### `main.py` — scraping simple

Pour des recherches ciblées (une ville, un type de bien), ou pour tester.

```bash
cd bieniciscraper-main

# Haute-Garonne — appartements (500 annonces, sortie par défaut)
python main.py --url "https://www.bienici.com/recherche/achat/haute-garonne-31/appartement"

# Toulouse — maisons et appartements, 200 annonces
python main.py --url "https://www.bienici.com/recherche/achat/toulouse-31000" --limit 200

# Sortie personnalisée
python main.py --url "https://www.bienici.com/recherche/achat/haute-garonne-31" --output data/test.csv
```

Options :

| Option | Défaut | Description |
|--------|--------|-------------|
| `--url` / `-u` | Haute-Garonne achat | URL de recherche Bien'ici |
| `--limit` / `-l` | 500 | Nombre max d'annonces (1–2 500) |
| `--output` / `-o` | `apps/api/app/data/bienici.csv` | Chemin du CSV de sortie |

### `scrape_all.py` — scraping complet par tranches de prix

Bien'ici limite la pagination à ~2 496 résultats par requête. Pour récupérer toutes les annonces d'un département, `scrape_all.py` découpe automatiquement la recherche par tranches de prix, scrape chaque tranche séparément, puis fusionne les résultats en dédupliquant par URL.

```bash
cd bieniciscraper-main

# Haute-Garonne complète (toutes tranches de prix)
python scrape_all.py --url "https://www.bienici.com/recherche/achat/haute-garonne-31"

# Sortie personnalisée
python scrape_all.py --url "https://www.bienici.com/recherche/achat/haute-garonne-31" --output data/hg_complet.csv
```

Options :

| Option | Défaut | Description |
|--------|--------|-------------|
| `--url` | — | URL de recherche Bien'ici (obligatoire) |
| `--output` | `apps/api/app/data/bienici.csv` | Fichier CSV final |
| `--max` | 2 400 | Max annonces par tranche (sécurité sous 2 496) |

Les fichiers intermédiaires par tranche sont sauvegardés dans `tmp_slices/` au fur et à mesure, ce qui permet de reprendre en cas d'interruption.

### Format du CSV exporté

Les deux scripts produisent le même format, attendu par `run_analysis.py` / `scoring.py` :

| Colonne | Description |
|---------|-------------|
| `city` | Ville |
| `postal_code` | Code postal |
| `ad_type` | `buy` ou `rent` |
| `property_type` | `flat`, `house`, `loft`, `castle`, `townhouse` |
| `reference` | Référence agence |
| `title` | Titre de l'annonce |
| `publication_date` | Date de publication |
| `modification_date` | Date de dernière modification |
| `new_property` | Bien neuf (`True`/`False`) |
| `rooms_quantity` | Nombre de pièces |
| `bedrooms_quantity` | Nombre de chambres |
| `price` | Prix en euros |
| `surfaceArea` | Surface en m² |
| `url` | URL de l'annonce |

### Limites

- Bien'ici peut changer son API ou bloquer des requêtes trop fréquentes (HTTP 429/403). Les scripts attendent automatiquement avant de relancer.
- Le scraping reste dans les usages raisonnables : ne pas dépasser plusieurs milliers d'annonces par session.

---

## Étape 2 — Générer les prix de marché DVF

`scrape_dvf_haute_garonne.py` interroge les données DVF pour la Haute-Garonne et produit un fichier de prix médians par ville, au format de `prix_immo.csv`, utilisable directement via `--prices` dans `run_analysis.py`.

### Source des données

| Source | URL |
|--------|-----|
| API cquest | `https://api.cquest.org/dvf` (doc : [github.com/cquest/dvf_as_api](https://github.com/cquest/dvf_as_api)) |
| CSV officiels | `https://files.data.gouv.fr/geo-dvf/latest/csv/{annee}/departements/31.csv.gz` |

### Mode CSV (recommandé)

```bash
# Génère dvf_haute_garonne.csv à la racine
python scrape_dvf_haute_garonne.py --mode csv --annees 2022,2023,2024

# Directement dans le répertoire data de l'API
python scrape_dvf_haute_garonne.py --mode csv --output apps/api/app/data/dvf_haute_garonne.csv
```

Les fichiers `.gz` sont mis en cache dans `.dvf_cache/` pour ne pas être retéléchargés.

### Mode API

```bash
python scrape_dvf_haute_garonne.py --mode api
```

### Téléchargement manuel

Si le téléchargement automatique est bloqué, récupérer les fichiers sur data.gouv.fr et les placer dans `.dvf_cache/` sous la forme `31_{annee}.csv.gz`.

### Format de sortie

Identique à `prix_immo.csv` :

```
Ville,Prix_Appartement_m2,Prix_Maison_m2,Loyer_Appartement_m2,Loyer_Maison_m2
Toulouse,3462,4091,,
Muret,2708,2857,,
```

---

## Étape 3 — Lancer l'analyse

```bash
cd apps/api

# Avec les prix DVF :
python scripts/run_analysis.py \
    --ads app/data/bienici.csv \
    --prices app/data/dvf_haute_garonne.csv \
    --output app/data/resultats.csv

# Avec les prix statiques :
python scripts/run_analysis.py \
    --ads app/data/bienici.csv \
    --prices app/data/prix_immo.csv \
    --output app/data/resultats.csv

# Mode hybride (DVF avec fallback CSV si l'API est inaccessible) :
python scripts/run_analysis.py \
    --ads app/data/bienici.csv \
    --market-source auto \
    --dvf-cache app/data/market_prices_dvf.csv \
    --output app/data/resultats.csv
```

`resultats.csv` est lu automatiquement par l'API au démarrage. Si le fichier est absent, l'API charge `resultats.sample.csv`.

---

## Étape 4 — Lancer l'API

```bash
cd apps/api
uvicorn app.main:app --reload --port 8000
```

Endpoints :

- `GET /health`
- `GET /opportunities`
- `GET /opportunities?max_price=200000&property_type=Appartement&min_discount_percent=15`

---

## Étape 5 — Lancer le frontend

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

- `bieniciscraper-main/main.py` : sortie par défaut corrigée — pointe maintenant vers `apps/api/app/data/bienici.csv` (était `data_bienici_lobstr_io.csv` à la racine du scraper)
- `bieniciscraper-main/scrape_all.py` : même correction sur la sortie par défaut
- `scrape_dvf_haute_garonne.py` : refonte complète — produit le format `prix_immo.csv`, compatible `--prices`
- Suppression des anciens scripts de scraping DVF (voir `update.md`)
- Nettoyage du README
