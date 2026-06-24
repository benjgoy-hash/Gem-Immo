# Gemma Immo SaaS

Gemma Immo SaaS transforme ton pipeline local `scraping -> resultats.csv -> filtrage IA Telegram` en application web.

Le projet contient :

- une API FastAPI qui expose les opportunites immobilieres filtrees ;
- un moteur Python reutilisable pour recalculer les decotes et rendements ;
- une interface Next.js pour rechercher les biens par budget, type, ville et rendement ;
- une structure prete pour ajouter comptes utilisateurs, abonnements, base de donnees et jobs planifies.

## Architecture

```text
gemma-immo-saas/
  apps/
    api/                 API FastAPI + moteur metier Python
      app/
        data/            CSV de reference et resultats
        routers/         Routes HTTP
        services/        Calculs, chargement CSV, filtres
      scripts/           Scripts batch pour regenerer resultats.csv
    web/                 Frontend Next.js
  docs/
    ROADMAP_SAAS.md      Etapes pour passer du prototype au SaaS
```

## Lancer l'API

```powershell
cd C:\Users\benjg\OneDrive\Bureau\DEV\Gemma\gemma-immo-saas\apps\api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
uvicorn app.main:app --reload --port 8000
```

Endpoints utiles :

- `GET http://localhost:8000/health`
- `GET http://localhost:8000/opportunities`
- `GET http://localhost:8000/opportunities?max_price=100000&property_type=Appartement`

## Lancer le web

```powershell
cd C:\Users\benjg\OneDrive\Bureau\DEV\Gemma\gemma-immo-saas\apps\web
npm install
npm run dev
```

Puis ouvre `http://localhost:3000`.

## Regenerer les resultats

Place un export Bien'ici dans `apps/api/app/data/bienici.csv`, puis lance :

```powershell
cd C:\Users\benjg\OneDrive\Bureau\DEV\Gemma\gemma-immo-saas\apps\api
python scripts/run_analysis.py --ads app/data/bienici.csv --prices app/data/prix_immo.csv --output app/data/resultats.csv
```

Le SaaS lit `resultats.csv` si present, sinon il utilise `resultats.sample.csv`.

## Publication GitHub

Je n'ai pas pu creer le repo GitHub automatiquement depuis cette machine car la CLI `gh` n'est pas installee et le connecteur disponible ne propose pas la creation de repository. Pour publier :

```powershell
cd C:\Users\benjg\OneDrive\Bureau\DEV\Gemma\gemma-immo-saas
git init
git add .
git commit -m "Initial SaaS scaffold"
```

Ensuite, cree un repo vide sur GitHub, par exemple `gemma-immo-saas`, puis :

```powershell
git branch -M main
git remote add origin https://github.com/<ton-user>/gemma-immo-saas.git
git push -u origin main
```

Si tu installes GitHub CLI :

```powershell
winget install GitHub.cli
gh auth login
gh repo create gemma-immo-saas --private --source . --remote origin --push
```

## Prochaines briques SaaS

1. Stocker les annonces dans PostgreSQL au lieu d'un CSV.
2. Lancer le scraping en job planifie avec historique des annonces.
3. Ajouter authentification, espaces utilisateurs et favoris.
4. Brancher Stripe pour les plans payants.
5. Ajouter le connecteur IA Gemma pour requetes en langage naturel.
6. Deployer API + worker sur Render/Railway/Fly, front sur Vercel.

