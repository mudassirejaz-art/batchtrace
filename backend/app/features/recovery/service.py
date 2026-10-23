"""Read-only, explainable opportunity classification (not eligibility approval)."""
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.recovery.repository import latest_observations, policies_for_suppliers
from app.features.recovery.schema import OpportunityResponse


class EvaluationDateOverflow(Exception):
    pass


def classify_window(policy, expiry_date: date, as_of: date):
    """Mirror Step 8 supplier-level policy selection and inclusive boundaries."""
    if policy is None:
        return "no_policy", None, None
    if policy.effective_to is not None and as_of > policy.effective_to:
        return "policy_expired", None, None
    try:
        opens = expiry_date - timedelta(days=policy.days_before_expiry)
        closes = expiry_date + timedelta(days=policy.days_after_expiry)
    except OverflowError as exc:
        raise EvaluationDateOverflow from exc
    if as_of < opens:
        return "not_yet_open", opens, closes
    if as_of > closes:
        return "window_closed", opens, closes
    return "window_open", opens, closes


def classify_opportunity(window_status: str, observed_quantity: int, stale: bool) -> str:
    # A window being open is never sufficient to claim that units are returnable.
    if window_status != "window_open":
        return window_status
    if observed_quantity == 0:
        return "zero_observed"
    if stale:
        return "stale_snapshot"
    return "verify_stock"


async def list_opportunities(
    db: AsyncSession,
    organization_id: UUID,
    *,
    as_of: date,
    max_snapshot_age_days: int,
    product_id: UUID | None,
    supplier_id: UUID | None,
    limit: int,
    offset: int,
) -> list[OpportunityResponse]:
    records = await latest_observations(
        db, organization_id, as_of,
        product_id=product_id, supplier_id=supplier_id,
        limit=limit, offset=offset,
    )
    policies = await policies_for_suppliers(
        db, organization_id, as_of, {item[0].supplier_id for item in records},
    )
    opportunities = []
    for (lot, product_sku, supplier_code, quantity, import_id, observed_on, imported_at) in records:
        policy = policies.get(lot.supplier_id)
        window, opens, closes = classify_window(policy, lot.expiry_date, as_of)
        age = (as_of - observed_on).days
        stale = age > max_snapshot_age_days
        opportunities.append(OpportunityResponse(
            organization_id=organization_id,
            lot_id=lot.id, product_id=lot.product_id, supplier_id=lot.supplier_id,
            product_sku=product_sku, supplier_code=supplier_code,
            batch_number=lot.batch_number, expiry_date=lot.expiry_date,
            import_id=import_id, imported_at=imported_at, observed_on=observed_on,
            observed_quantity=quantity, snapshot_age_days=age, snapshot_is_stale=stale,
            as_of=as_of, policy_id=policy.id if policy else None,
            policy_version=policy.version if policy else None,
            return_opens_on=opens, return_closes_on=closes,
            date_window_status=window,
            opportunity_status=classify_opportunity(window, quantity, stale),
        ))
    return opportunities
