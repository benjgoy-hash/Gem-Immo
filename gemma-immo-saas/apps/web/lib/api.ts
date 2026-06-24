export type Opportunity = {
  city: string;
  property_type: string;
  price: number;
  listing_price_m2: number;
  reference_price_m2: number;
  discount_percent: number;
  gross_yield: number;
  label: string;
  url: string;
};

export type OpportunityResponse = {
  count: number;
  items: Opportunity[];
};

export type SearchFilters = {
  city?: string;
  propertyType?: string;
  maxPrice?: string;
  minDiscountPercent?: string;
  minGrossYield?: string;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function fetchOpportunities(filters: SearchFilters): Promise<OpportunityResponse> {
  const params = new URLSearchParams();

  if (filters.city) params.set("city", filters.city);
  if (filters.propertyType && filters.propertyType !== "Tous") {
    params.set("property_type", filters.propertyType);
  }
  if (filters.maxPrice) params.set("max_price", filters.maxPrice);
  if (filters.minDiscountPercent) params.set("min_discount_percent", filters.minDiscountPercent);
  if (filters.minGrossYield) params.set("min_gross_yield", filters.minGrossYield);

  const response = await fetch(`${API_URL}/opportunities?${params.toString()}`, {
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error("Impossible de charger les opportunites");
  }

  return response.json();
}

