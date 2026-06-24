from pydantic import BaseModel, Field


class Opportunity(BaseModel):
    city: str
    property_type: str
    price: float
    listing_price_m2: float
    reference_price_m2: float
    discount_percent: float
    gross_yield: float
    label: str
    url: str


class OpportunityFilters(BaseModel):
    city: str | None = None
    property_type: str | None = Field(default=None, examples=["Appartement", "Maison"])
    max_price: float | None = None
    min_discount_percent: float | None = None
    min_gross_yield: float | None = None
    limit: int = Field(default=50, ge=1, le=200)


class OpportunityResponse(BaseModel):
    count: int
    items: list[Opportunity]

