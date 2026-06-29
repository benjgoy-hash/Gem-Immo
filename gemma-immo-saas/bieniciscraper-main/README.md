# Bien'ici Scraper

Ce dossier contient le scraper charge de recuperer des annonces immobilieres depuis une URL de recherche Bien'ici et de les exporter en CSV.

Il sert de premiere etape au pipeline Gemma Immo :

```text
Bien'ici -> scraper CSV -> analyse decote/rendement -> API SaaS -> interface web / IA
```

## Ce que le scraper fait

- Lit une URL de recherche Bien'ici, par exemple une recherche d'achat en Haute-Garonne.
- Convertit cette URL en parametres pour l'API JSON Bien'ici.
- Resout la zone geographique via `https://res.bienici.com/suggest.json`.
- Parcourt les pages de resultats.
- Extrait les champs utiles de chaque annonce.
- Ecrit un fichier CSV exploitable par le script d'analyse du SaaS.

## Champs exportes

Le CSV contient :

- `city`
- `postal_code`
- `ad_type`
- `property_type`
- `reference`
- `title`
- `publication_date`
- `modification_date`
- `new_property`
- `rooms_quantity`
- `bedrooms_quantity`
- `price`
- `surfaceArea`
- `url`

## Installation

Depuis ce dossier :

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Utilisation simple

```powershell
python main.py --url "https://www.bienici.com/recherche/achat/haute-garonne-31/appartement" --limit 100 --output data/bienici.csv
```

Options :

- `--url` : URL de recherche Bien'ici.
- `--limit` : nombre maximum d'annonces a recuperer, entre 1 et 2500.
- `--output` : fichier CSV de sortie. Le dossier est cree automatiquement si besoin.

## Scraping complet par tranches de prix

Bien'ici limite la pagination autour de 2500 annonces. Pour une recherche large, utilise `scrape_all.py`, qui decoupe automatiquement la recherche en tranches de prix.

```powershell
python scrape_all.py --url "https://www.bienici.com/recherche/achat/haute-garonne-31" --output data/bienici_all.csv
```

## Corrections apportees

La version precedente etait fragile sur plusieurs points :

- elle utilisait `assert`, ce qui provoquait des erreurs peu explicites ;
- elle plantait si Bien'ici retournait 0 resultat ;
- elle ne creait pas le dossier de sortie avant d'ecrire le CSV ;
- elle n'avait pas de timeout clair sur les appels reseau ;
- les messages et certaines regex avaient un encodage casse ;
- l'URL d'annonce pouvait etre incomplete si `adTypeFR` etait absent dans la reponse.

La version actuelle gere ces cas plus proprement et affiche des messages actionnables.

## Limites connues

- Bien'ici peut changer son API ou limiter certaines requetes.
- Des erreurs 403 ou 429 peuvent apparaitre si le scraping est trop rapide ou trop volumineux.
- Le scraper doit rester raisonnable : reduis `--limit`, ajoute des pauses, ou utilise les tranches de prix pour les grosses recherches.

## Sortie attendue

Exemple de commande de test :

```powershell
python main.py --url "https://www.bienici.com/recherche/achat/haute-garonne-31/appartement" --limit 1 --output data/test.csv
```

Si tout va bien, le terminal affiche le nombre de resultats trouves, scrape une annonce, puis cree `data/test.csv`.
