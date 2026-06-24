from app.schemas import Opportunity, OpportunityFilters


def filter_opportunities(
    opportunities: list[Opportunity],
    filters: OpportunityFilters,
) -> list[Opportunity]:
    items = opportunities

    if filters.city:
        city = filters.city.casefold().strip()
        items = [item for item in items if city in item.city.casefold()]

    if filters.property_type:
        property_type = filters.property_type.casefold().strip()
        items = [item for item in items if item.property_type.casefold() == property_type]

    if filters.max_price is not None:
        items = [item for item in items if item.price <= filters.max_price]

    if filters.min_discount_percent is not None:
        items = [item for item in items if item.discount_percent >= filters.min_discount_percent]

    if filters.min_gross_yield is not None:
        items = [item for item in items if item.gross_yield >= filters.min_gross_yield]

    return items[: filters.limit]

