# update.md — Historique des suppressions et changements cassants

---

## v2.0.0 — 2026-06-29

### Fichiers supprimés

| Fichier | Raison |
|---------|--------|
| `scrape_dvf_haute_garonne.py` (v1) | Remplacé par la v2 — produisait un format incompatible avec `run_analysis.py` (colonnes DVF brutes au lieu du format `prix_immo.csv`) |
| `download_dvf_31.py` | Fusionné dans `scrape_dvf_haute_garonne.py` — le mode `csv` couvre le même besoin |

### Changements de comportement

**`bieniciscraper-main/main.py`**
- Sortie par défaut modifiée : `data_bienici_lobstr_io.csv` (racine du scraper) → `apps/api/app/data/bienici.csv`
- Le dossier de sortie est créé automatiquement si absent (comportement inchangé via `Path.mkdir(parents=True, exist_ok=True)`)
- Limite par défaut modifiée : 100 → 500 annonces
- URL par défaut modifiée : `france/appartement` → `haute-garonne-31` (périmètre du projet)

**`bieniciscraper-main/scrape_all.py`**
- Sortie par défaut modifiée : `output_all.csv` (racine du scraper) → `apps/api/app/data/bienici.csv`

**`scrape_dvf_haute_garonne.py`**
- Sortie entièrement reformatée : colonnes DVF brutes → format `prix_immo.csv` (`Ville, Prix_Appartement_m2, Prix_Maison_m2, Loyer_Appartement_m2, Loyer_Maison_m2`)
- Le fichier généré est maintenant passable directement à `run_analysis.py` via `--prices`
