"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { Building2, ExternalLink, Filter, Home, Loader2, Search } from "lucide-react";
import { fetchOpportunities, Opportunity, SearchFilters } from "../lib/api";

const euroFormatter = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0
});

const numberFormatter = new Intl.NumberFormat("fr-FR", {
  maximumFractionDigits: 0
});

export default function HomePage() {
  const [filters, setFilters] = useState<SearchFilters>({
    propertyType: "Tous",
    minDiscountPercent: "10"
  });
  const [items, setItems] = useState<Opportunity[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load(nextFilters = filters) {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchOpportunities(nextFilters);
      setItems(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inconnue");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void load();
  }

  const bestDiscount = useMemo(
    () => items.reduce((best, item) => Math.max(best, item.discount_percent), 0),
    [items]
  );

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brandIcon">
            <Building2 size={22} />
          </div>
          <div>
            <p>Gemma Immo</p>
            <span>Chasseur de decotes</span>
          </div>
        </div>

        <form className="filters" onSubmit={onSubmit}>
          <div className="sectionTitle">
            <Filter size={16} />
            <span>Filtres</span>
          </div>

          <label>
            Ville
            <input
              placeholder="Toulouse, Muret..."
              value={filters.city ?? ""}
              onChange={(event) => setFilters({ ...filters, city: event.target.value })}
            />
          </label>

          <label>
            Type
            <select
              value={filters.propertyType ?? "Tous"}
              onChange={(event) => setFilters({ ...filters, propertyType: event.target.value })}
            >
              <option>Tous</option>
              <option>Appartement</option>
              <option>Maison</option>
            </select>
          </label>

          <label>
            Budget maximum
            <input
              inputMode="numeric"
              placeholder="100000"
              value={filters.maxPrice ?? ""}
              onChange={(event) => setFilters({ ...filters, maxPrice: event.target.value })}
            />
          </label>

          <label>
            Decote minimum (%)
            <input
              inputMode="decimal"
              placeholder="10"
              value={filters.minDiscountPercent ?? ""}
              onChange={(event) =>
                setFilters({ ...filters, minDiscountPercent: event.target.value })
              }
            />
          </label>

          <label>
            Rendement minimum
            <input
              inputMode="decimal"
              placeholder="0.06"
              value={filters.minGrossYield ?? ""}
              onChange={(event) => setFilters({ ...filters, minGrossYield: event.target.value })}
            />
          </label>

          <button type="submit" disabled={isLoading}>
            {isLoading ? <Loader2 className="spin" size={18} /> : <Search size={18} />}
            Rechercher
          </button>
        </form>
      </aside>

      <section className="content">
        <header className="topbar">
          <div>
            <p className="eyebrow">Opportunites detectees</p>
            <h1>Les biens avec decote remontent ici.</h1>
          </div>
          <div className="stats">
            <strong>{items.length}</strong>
            <span>resultats</span>
          </div>
          <div className="stats">
            <strong>{bestDiscount.toFixed(1)}%</strong>
            <span>meilleure decote</span>
          </div>
        </header>

        {error ? <div className="notice">{error}</div> : null}

        <div className="grid">
          {items.map((item) => (
            <article className="opportunity" key={item.url}>
              <div className="cardHeader">
                <div className="propertyIcon">
                  <Home size={18} />
                </div>
                <div>
                  <h2>{item.city}</h2>
                  <p>{item.property_type}</p>
                </div>
                <span className="badge">{item.label}</span>
              </div>

              <div className="price">{euroFormatter.format(item.price)}</div>

              <dl className="metrics">
                <div>
                  <dt>Decote</dt>
                  <dd>{item.discount_percent.toFixed(1)}%</dd>
                </div>
                <div>
                  <dt>Rendement</dt>
                  <dd>{(item.gross_yield * 100).toFixed(1)}%</dd>
                </div>
                <div>
                  <dt>Annonce / m2</dt>
                  <dd>{numberFormatter.format(item.listing_price_m2)} EUR</dd>
                </div>
                <div>
                  <dt>Reference / m2</dt>
                  <dd>{numberFormatter.format(item.reference_price_m2)} EUR</dd>
                </div>
              </dl>

              <a href={item.url} target="_blank" rel="noreferrer">
                Voir l'annonce
                <ExternalLink size={16} />
              </a>
            </article>
          ))}
        </div>

        {!isLoading && items.length === 0 ? (
          <div className="empty">Aucun bien ne correspond aux filtres actuels.</div>
        ) : null}
      </section>
    </main>
  );
}

