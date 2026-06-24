# Roadmap SaaS

## Phase 1 - Prototype web

- Conserver les CSV existants comme source de donnees.
- Exposer les resultats avec une API FastAPI.
- Ajouter une interface web avec filtres.
- Garder le calcul decote/rendement dans un service Python testable.

## Phase 2 - Produit utilisable

- Remplacer `resultats.csv` par PostgreSQL.
- Creer les tables `listings`, `market_prices`, `opportunity_scores`, `users`, `saved_searches`.
- Ajouter un job de scraping quotidien.
- Detecter les nouvelles annonces et les baisses de prix.
- Ajouter favoris, alertes email/Telegram et recherches sauvegardees.

## Phase 3 - SaaS commercial

- Authentification avec Clerk, Auth.js ou Supabase Auth.
- Abonnements Stripe : gratuit, investisseur, pro.
- Limites par plan : nombre de recherches, alertes, exports, zones.
- Back-office admin pour surveiller scraping, erreurs et qualite des donnees.

## Phase 4 - IA Gemma

- Ajouter un endpoint `/assistant/search`.
- Transformer une demande comme "appartement a Toulouse sous 100000 euros avec decote de 15%" en filtres structures.
- Faire repondre Gemma avec les meilleurs biens, les hypotheses et les risques.
- Garder les calculs financiers deterministes cote backend.

## Phase 5 - Production

- API et worker sur Render, Railway ou Fly.io.
- Frontend sur Vercel.
- Base PostgreSQL managée.
- Logs et alerting avec Sentry.
- Backups automatiques de la base.

