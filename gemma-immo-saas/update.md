# update.md — Historique des suppressions et changements cassants

---

## v2.0.0 — 2026-06-29

### Fichiers supprimés

| Fichier | Raison |
|---------|--------|
| `scrape_dvf_haute_garonne.py` (v1) | Remplacé par la v2 — l'ancien script produisait un format incompatible avec `run_analysis.py` (colonnes DVF brutes au lieu du format `prix_immo.csv`) |
| `download_dvf_31.py` | Fusionné dans `scrape_dvf_haute_garonne.py` — le mode `csv` couvre le même besoin sans fichier supplémentaire |

### Changements de comportement

- Le script DVF produit désormais `Ville, Prix_Appartement_m2, Prix_Maison_m2, Loyer_Appartement_m2, Loyer_Maison_m2` — format identique à `prix_immo.csv`, passable directement via `--prices` à `run_analysis.py`.
- L'ancienne sortie (`dvf_haute_garonne.csv` avec colonnes brutes DVF) n'est plus générée.
- Les colonnes `Loyer_*` sont vides dans la sortie DVF — les données de loyer ne sont pas disponibles dans les fichiers DVF.
