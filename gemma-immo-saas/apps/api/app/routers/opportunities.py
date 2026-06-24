from fastapi import APIRouter, Depends, Query

from app.config import Settings, get_settings
from app.schemas import OpportunityFilters, OpportunityResponse
from app.services.filters import filter_opportunities
from app.services.repository import load_opportunities

router = APIRouter(prefix="/opportunities", tags=["opportunities"])


@router.get("", response_model=OpportunityResponse)
def list_opportunities(
    city: str | None = None,
    property_type: str | None = None,
    max_price: float | None = Query(default=None, ge=0),
    min_discount_percent: float | None = Query(default=None, ge=0),
    min_gross_yield: float | None = Query(default=None, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    settings: Settings = Depends(get_settings),
) -> OpportunityResponse:
    filters = OpportunityFilters(
        city=city,
        property_type=property_type,
        max_price=max_price,
        min_discount_percent=min_discount_percent,
        min_gross_yield=min_gross_yield,
        limit=limit,
    )
    items = filter_opportunities(load_opportunities(settings.results_path), filters)
    return OpportunityResponse(count=len(items), items=items)

